#!/usr/local/bin/python3
#
# importer.py
#
# this is the main import script for grabbing inventory from various sources

# builtin modules used
import sys
import argparse
import re
import json
import urllib.request, urllib.error, urllib.parse
import os
import errno
import logging

# third party modules used
from bunch import Bunch
from bs4 import BeautifulSoup
import ebaysdk
from ebaysdk.exception import ConnectionError
from ebaysdk.finding import Connection as ebaysdk_finding
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
import pymysql as db

# OGL modules used (none yet)

# ============================================================================
# CONSTANTS
# ============================================================================

# GEE TODO refine this: what headers do we want to send?
# some sites don't want to offer up inventory without any headers.
# Not sure why, but let's impersonate some real browser and such to get through
hdrs = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
              'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
              'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
              'Accept-Encoding': 'none',
              'Accept-Language': 'en-US,en;q=0.8',
              'Connection': 'keep-alive'}

boring_makes = ['Dodge','Chrysler', 'Ram', 'Jeep',
                'Honda', 'Acura', 'Toyota', 'Lexus', 'Scion', 'Nissan', 'Infiniti',
                'Mazda', 'Subaru', 'Isuzu', 'Mitsubishi',
                'Chevrolet','Chevy', 'Pontiac', 'Saturn', 'Cadillac', 'Buick',
                'GM','General','GMC',
                'Ford','Mercury',
                'BMW', 'Mini', 'Mercedes', 'Mercedes-Benz', 'MB', 'Volkswagen', 'VW', 'Audi',
                'Fiat', 'Volvo', 'Land Rover',
                'Hyundai', 'Kia', 'Suzuki']

interesting_models = ['Viper',
                      'NSX', 'MR2', 'MR-2', 'Supra', 'LFA', '300zx', 'Skyline', 'GTR',
                      'MX5', 'MX-5', 'Miata', 'MX-5 Miata', 'rx7', 'STI', 'Evolution', 'Evo',
                      'Corvette', 'Grand National', 
                      'Boss', 'Shelby', 'GT',
                      'M3', 'M5', 'M6', 'SLS', 'AMG', 'R8']

# ============================================================================
# UTILITY METHODS
# ============================================================================

# GEE TODO: deal properly with unicode/charset issues.
# should (can?) we switch to python 3 to get utf-8 default charset rather than ascii?

# regularize methods will take a string input that may be "messy" or vary a bit
# from site to site and regularize/standardize it

# def regularize_price
#
# take a price string, strip out any dollar signs and commas, convert to an int
# TODO: this is US-format-only right now & doesn't handle decimals or other garbage yet
# ... or currencies!

def regularize_price(price_string):
    if price_string == None:
        price = -1
    else:
        # strip out 'Price:' or similar if included
        if ':' in price_string: # then take the part after the colon
            (junk, junk, price_string) = price_string.rpartition(':')
        price_string = re.sub('[a-zA-Z]','', price_string) # strip out any letters that might remain...
        try:
            price = int(re.sub('[\$,]', '', price_string))
        except ValueError:
            try:
                price = int(float(re.sub('[\$,]', '', price_string)))
            except ValueError:
                price = -1
    return price


# regularize_year_make_model
#
# take a string containing year, make, and model (e.g. '1970 ford thunderbird')
# and split (intelligently) into year, make, and model
#
# NOTES:
# for now this is stupid; will be enhanced to use make/model dict info
# will return None for any elements we can't figure out (e.g. if passed '')
#
def regularize_year_make_model(year_make_model_string):
    # GEE TODOs:
    # make a better splitter that understands multiword makes (e.g. Alfa Romeo)
    # use the year/make/model database to reality check / standardize
    if year_make_model_string: # is not None or ''
        words = year_make_model_string.split(" ",2)
        if len(words) == 3: # assume it went as desired (for now)
            return words # should be year, make, model
        else: # oops...
            # maybe missing year?
            try:
                int(words[0])
            except ValueError:
                words.insert(0, None) # Stick in a None for year
            while (len(words) < 3):
                words.append(None) # pad out...
            return words
    else:
        return (None, None, None)


# make_sure_path_exists()
#
# utility method that will create any missing components of the given path
#
def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    return True


# is_car_interesting()
#
# crummy kludge to filter to cars we want for now vs ones we don't
#
def is_car_interesting(listing):
    if listing['model_year'] and int(listing['model_year']) <= 1975:
        return True # automatically interesting
    # GEE TODO: case of comparisons & substrings make this.... interesting
    if listing['make'] not in boring_makes: # wow is this inefficient - need make/model db stuff
        return True
    if listing['model'] in interesting_models: # pull particular models back in
        return True
    if listing['price'] > 100000: # Prima facia evidence of interesting status? :)
        return True
    return False

# soup_from_file()
#
# intended for interactive use anyway; quickly soupify a file for testing.
#
def soup_from_file(path):
    with open(path) as file:
        return BeautifulSoup(file)

    
# soup_from_file()
#
# intended for interactive use anyway; quickly soupify a file for testing.
# GEE TODO: write this
#
def soup_from_url(url):
    try:
        req = urllib.request.Request(url, headers=hdrs)
        page = urllib.request.urlopen(req)
    except urllib.error.HTTPError as error:
        logging.error('Unable to load inventory page ' + url + ': HTTP ' + str(error.code) + ' ' + error.reason)
        return None

    if page.getcode() != 200:
        logging.error('Failed to pull an inventory page for ' + url + ' with HTTP response code ' + str(page.getcode()))
        return None

    return BeautifulSoup(page)


# test_inventory()
#
# creates a bogus listing since this is a test script :)
#
# returns a list containing that one bogus listing
#
def test_inventory():
    # 
    test_listing = Bunch()
    test_listing['status'] = 'T' # T -> test data (will exclude from website listings)
    test_listing['model_year'] = '1955'
    test_listing['make'] = 'Ford'
    test_listing['model'] = 'Thunderbird'
    test_listing['price'] = '25000'
    test_listing['listing_text'] = 'This is a fake thunderbird listing'
    test_listing['pic_href'] = 'http://www.google.com'
    test_listing['listing_href'] = 'http://www.yahoo.com'
    test_listing['source_textid'] = 'dbtest'
    test_listing['local_id'] = '1'
    test_listing['stock_no'] = 'stock1234'

    # GEE debug
    logging.info("listing: " + json.dumps(test_listing))

    # return a list containing this one listing dict
    list_of_listings = [test_listing]
    return list_of_listings


# ============================================================================
# PARSING METHODS
# ============================================================================

# placeholder method to copy-and-paste to form a new dealership-specific parse
#
def new_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing['model_year'],
    listing['make'],
    listing['model']) = regularize_year_make_model('')

    listing['listing_text'] = ''

    # pull the rest of the fields from the detail page

    listing['price'] = regularize_price('')

    return True


# autorevo_parse_listing
#
# developed to load VIP motors, and hopefully also works with other dealers
# who use autorevo for their inventory listings.
#
def autorevo_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing['model_year'],
    listing['make'],
    listing['model']) = regularize_year_make_model(entry.find('h1').text)

    try:
        listing['price'] = regularize_price(entry.find(class_='vehicleMainPriceRow').text)
    except AttributeError:
        listing['price'] = -1

    # doesn't have listing text on inventory page
    try:
        listing['listing_text'] = detail.find(class_='innerDescriptionText').find('p').text
    except AttributeError:
        listing['listing_text'] = ''

    return True


# carbuffs_parse_listing
#
#
def carbuffs_parse_listing(listing, entry, detail):

    # get the short listing text from the inventory page
    listing['listing_text'] = entry.find(class_="car-excerpt").text

    # pull the rest of the fields from the detail page
    (listing['model_year'],
    listing['make'],
    listing['model']) = regularize_year_make_model(detail.find(class_='car-name').text)

    # common name/value patterns in details page:
    #<li><strong>Car model year:</strong> 1963</li>
    #<p class="car-asking-price"><strong>Asking Price:</strong> $89,950</p>
    pe = detail.find('strong',text='Asking Price:')
    if pe != None:
        pe = pe.next_sibling
    listing['price'] = regularize_price(pe)

    return True


def ccw_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing['model_year'],
    listing['make'],
    listing['model']) = regularize_year_make_model(entry.find('strong').text)

    listing['listing_text'] = '' # no short text available, only longer text from detail page

    # pull the rest of the fields from the detail page

    return True


# cfc_parse_listing
#
def cfc_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing['model_year'],
    listing['make'],
    listing['model']) = regularize_year_make_model(entry.find('a').text)

    listing['listing_text'] = '' # no crisp text, just long text

    return True


# cvclassics_parse_listing
#
def cvclassics_parse_listing(listing, entry, detail):

    # this site is super-sparse, with no useful tagging...
    # we just have to make the best of it

    # get year/make/model and short listing text from the inventory page

    strings = entry.find_all(text=True)

    (listing['model_year'],
    listing['make'],
    listing['model']) = regularize_year_make_model(strings[0])

    listing['listing_text'] = strings[1]

    # no real patterns to mine on the details page.
    # but hey, at least it has the price! (unlike the inventory page)
    pe = detail.find(text=re.compile('Asking Price:'))
    if pe != None:
        pe = pe.split(':')[-1]
    listing['price'] = regularize_price(pe)

    return True


# dawydiak_parse_listing
#
# used for both porsche and non-porsche inventory from Cars Dawydiak
#
def dawydiak_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page

    listing['listing_text'] = entry.find(class_='introlist').text
    if entry.find(class_='dscprice'):
        listing['price'] = regularize_price(entry.find(class_='dscprice').text)

    # pull the rest of the fields from the detail page
    listing['model_year'] = detail.find('dt',text=re.compile('Year:')).parent.dd.text
    listing['make'] = detail.find('dt',text=re.compile('Make:')).parent.dd.text
    listing['model'] = detail.find('dt',text=re.compile('Model:')).parent.dd.text

    listing['local_id'] = detail.find('dt',text=re.compile('Stock')).parent.dd.text
    listing['stock_no'] = listing['local_id'] # no separate stock#

    return True


# fj_parse_listing
#
def fj_parse_listing(listing, entry, detail):

    # get the short listing text from the inventory page
    listing['listing_text'] = entry.find(class_="entry-subheader blue").get_text()

    # pull the rest of the fields from the detail page

    s = detail.find('title').text
    (listing['model_year'],
     listing['make'],
     listing['model']) = regularize_year_make_model(s)

    listing['local_id'] = detail.find(id="ContactCarId")['value']
    listing['stock_no'] = listing['local_id'] # no separate stock#

    # many interesting items are in an "alpha-inner-bottom' div, but for now just grab price
    # tabular format with labels & values in two td elements, e.g.:
    # <tr>
    # <td class="car-detail-name">Price</td>
    # <td class="car-detail-value"> $42,500</td>
    # </tr>
    elt = detail.find(id='alpha-inner-bottom')
    price_string = elt.find("td", text="Price").parent.find('td', class_="car-detail-value").text
    listing['price'] = regularize_price(price_string)

    return True


# lc_parse_listing
#
# this method handles both left coast classics (lcc) and left coast exotics (lce)
#
def lc_parse_listing(listing, entry, detail):

    logging.debug(entry)
    logging.debug(detail)
    # first of all, since the inventory page has so little useful tagging we may
    # get some entries that are not really car listings. Detect them here and
    # return False...
    if entry.name != 'tr':
        logging.debug('skipping putative entry because it is not in a <tr> (was a {})'.format(entry.name))
        return False

    # as with cvc, there is no useful tagging....
    # we just have to make the best of it

    # get the short listing text from the inventory page
    listing['listing_text'] = entry.find('h3').text

    # price is only on the inventory page, not on the detail page (!)
    # and it's often missing (text will just be CALL, SOLD, etc)
    price_string = entry.find('h2', align='center')
    if price_string != None:
        price_string = price_string.text
    listing['price'] = regularize_price(price_string)

    # pull the rest of the fields from the detail page, IF we loaded one
    # (sometimes there isn't one! Just "COMING SOON" and a phone number)
    # 

    # GEE TODO: better splitter that understands alfa romeo AND
    # is robust enough to handle unexpected inputs (like missing model year)
    # without puking...
    # Note: the <h1> appears to be handmade and in at least one case omitted
    # model year, so I'm going to pull year/make/model from the detail URL
    # (ugh!) if I can't find it in the <h1>... and if there is no detail URL
    # then I will just return False. Heh, and sometimes the detail HAS no h1!
    try:
        if detail and detail.find('h1'):
            s = detail.find('h1').text
        else:
            s = entry.find('h2').text

        (listing['model_year'],
             listing['make'],
             listing['model']) = regularize_year_make_model(s)

        # removed a hacky bit here since I don't think it chains correctly off the revised code above, and I hope I don't need it!

    except ValueError: # should happen only if there is no h1 and then no h2
        return False

    # no real patterns to mine on the details page...

    return True


# def mhc_parse_listing
#
# GEE TODO: this page only loads the first 50 cars and then uses js to pull
# more and do "infinite scrolling". Needt o find a way to get the rest!
#
def mhc_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing['model_year'],
    listing['make'],
    listing['model']) = regularize_year_make_model(entry.find('h2').text)

    # GEE TODO: some don't have any description, but others do (on the detail page)
    listing['listing_text'] = '' 

    # pull the rest of the fields from the detail page

    listing['price'] = regularize_price(entry.find('span').text)

    return True


# sfs_parse_listing
#
def sfs_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing['model_year'],
    listing['make'],
    listing['model']) = regularize_year_make_model(entry.find('h2').text)

    listing['listing_text'] = entry.find('h3').text

    if entry.find('h6'):
        listing['price'] = regularize_price(entry.find('h6').text)
    else:
        listing['price'] = -1

    # pull the rest of the fields from the detail page

    return True


# specialty_parse_listing
#
def specialty_parse_listing(listing, entry, detail):

    # get the short listing text from the inventory page
    listing['listing_text'] = entry.get_text()

    # grab price from the main listings page entry
    if entry.find(class_='vehicle-price-label'):
        price_string = entry.find(class_='vehicle-price-label').text
    else:
        price_string = ''
    listing['price'] = regularize_price(price_string)

    # grab year/make/model
    if entry.find(class_='vehicle-heading'):
        s = entry.find(class_='vehicle-heading').text
    else:
        s = ''
    (listing['model_year'],
     listing['make'],
     listing['model']) = regularize_year_make_model(s)

    s = ''
    if entry.find(class_='vehicle-stock'):
        s = entry.find(class_='vehicle-stock').text
        if '#' in s:
            junk, s = s.split('#')
    listing['local_id'] = s
    listing['stock_no'] = listing['local_id'] # no separate stock#

    # NOTE: we got everything from the inventory page;
    # not currently using the detail page at all
    # specialty used to have nice elements like the below on the detail
    # page but doesn't any more:
    # <tr>
    #   <td><h3>Stock: </h3></td>
    #   <td>F13011</td>
    # </tr>
    # the first td has an h3 with the fieldname, initcaps with colon and a trailing space
    # the second td has the value (raw, not in an h3)
    # the h3 in there seems to toast next_sibling/next_element, but find_next_sibling('td') works
    
    return True


# ============================================================================
# PRIMARY INVENTORY PULLING METHODS
# ============================================================================

# pull_dealer_inventory()
#
# pulls inventory from common dealer sites as directed
#
# parameters:
# dealer (textid of the dealer to be imported)
#
# returns a list of listings dicts
#
# NOTES:
# 
# this is a generic puller which accepts (and to perform decently, requires)
# site-specific helper functions to extract all the listing details.
#
# see sample inventory and detail pages:
# samples/fantasy_junction_inventory_page.html
# samples/fantasy_junction_detail_page.html
# samples/specialty_inventory_page.html
# samples/specialty_detail_page.html
#
def pull_dealer_inventory(dealer):

    list_of_listings = []
    last_local_id = None

    # the 300 parm should mean that all car listings are in one page & there
    # will be a next page link; our standard pagination loop should cope

    try:
        full_inv_url = urllib.parse.urljoin(dealer['base_url'], dealer['inventory_url'])
        logging.info('Pulling ' + dealer['textid'] + ' inventory from ' + full_inv_url + '....')
        req = urllib.request.Request(full_inv_url, headers=hdrs)
        page = urllib.request.urlopen(req)
    except urllib.error.HTTPError as error:
        logging.error('Unable to load inventory page ' + full_inv_url + ': HTTP ' + str(error.code) + ' ' + error.reason)
        return list_of_listings

    # GEE TODO: handle URLError that might have been raised...
    if page.getcode() != 200:
        logging.error('Failed to pull an inventory page for ' + full_inv_url + ' with HTTP response code ' + str(page.getcode()))
        return list_of_listings

    while True:
        # soupify it
        soup = BeautifulSoup(page)

        # extract all the listings

        myfunc = eval(dealer['extract_car_list_func'])
        
        listings = myfunc(soup)
        logging.info('Number of car listings found: {}'.format(len(listings)))
        for item in listings:
            ok = True
            listing = Bunch() # build a listing dict/bunch for this car

            # for some sites the full entry is actually a parent or sibling
            # or similar permutation of the list item we just grabbed
            myfunc = eval(dealer['listing_from_list_item_func'])
            entry = myfunc(item)

            # try standard grabs; then call the dealer-specific method for
            # overrides & improvements
            listing['source_textid'] = dealer['textid']

            # try to find the URL of the detail listing page
            detail = None # if we don't find one, we can pass down this None
            if entry.get('href'):
                # the found item may itself be an <a> with an href to the detail page
                detail_url = entry.get('href')
            elif entry.find('a'):
                detail_url_elt = entry.find('a')
                # or the first (likely only) href in the block is the detail page
                detail_url = detail_url_elt.get('href')
            else:
                # or alternately, there may be an onclick property we can grab?
                # the onclick property could be on entry or a subentity
                detail_url_attr = None
                try:
                    detail_url_attr = entry.attrs['onclick']
                except KeyError:
                    pass
                if detail_url_attr == None:
                    detail_url_elt = entry.find(onclick=True)
                    if detail_url_elt != None:
                        detail_url_attr = detail_url_elt.attrs['onclick']
                if detail_url_attr != None:
                    detail_url = detail_url_attr.split('href=')[1].replace("'","")
            # if we found a detail page URL, store & load it
            if detail_url:
                detail_url=detail_url.lstrip()
                # is it an http reference? Sometimes there is a phone URL...
                scheme = urllib.parse.urlsplit(detail_url).scheme
                # oops -- apparent bug, or at least difference in practical effect
                # between safari and urlsplit. urlsplit doesn't recognize
                # tel:8005551212
                # it recognizes some variants -- basically it expects at least one '/'
                # somewhere. Without that, it returns None as the scheme. So:
                if (detail_url[:4] == 'tel:'):
                    scheme = 'tel'
                if (scheme and scheme != 'http' and scheme != 'https'):
                    # uh... let's skip this one if we can't link to it as http
                    logging.info('found non-http detail URL: {}'.format(detail_url))
                    listing['listing_href'] = detail_url # just to prevent barfs
                    ok = False
                else:
                    try:
                        # GEE TODO: occasionally detail_url is NOT escaped properly
                        # (e.g. contains spaces), but calling urllib.parse.quote()
                        # on it quotes chars that shouldn't be quoted. What to do?
                        listing['listing_href'] = urllib.parse.urljoin(full_inv_url, detail_url)
                        logging.debug('detail page: ' + listing['listing_href'])
                        req = urllib.request.Request(listing['listing_href'], headers=hdrs)
                        detail_page = urllib.request.urlopen(req)
                        detail = BeautifulSoup(detail_page)
                    except urllib.error.HTTPError as error:
                        logging.error('Unable to load detail page ' +
                                      listing['listing_href'] + ': HTTP ' +
                                      str(error.code) + ' ' + error.reason)
                        ok = False

            # look for an image in the entry
            if entry.find('img'):
                listing['pic_href'] = urllib.parse.urljoin(full_inv_url, str(entry.find('img').attrs['src']))
            elif detail and detail.find('img'): # failover to 1st detail img
                listing['pic_href'] = urllib.parse.urljoin(full_inv_url, str(detail.find('img').attrs['src']))
            else:
                listing['pic_href'] = None

            # many sites have no stock#/inventory ID; default to the unique URL element
            # note that this will be wonky for item(s) that are 'coming soon'
            # (no detail page exists yet)
            listing['local_id'] = listing['listing_href'].rstrip('/').split('/')[-1].replace('.html','')
            listing['stock_no'] = listing['local_id'] # no separate stock_no

            # see if the listing is marked as sold?
            # GEE TODO improve this; using uppercase intentionally as a cheat
            if entry.find(text=re.compile('SOLD')):
                # used to also check detail but that was getting too many false
                # positives due to 'VIEW CARS SOLD' link or similar on the page
                listing['status'] = 'S' # 'S' -> Sold
            elif (entry.find(text=re.compile('SALE PENDING')) or
                (detail and detail.find(text=re.compile('SALE PENDING')))):
                listing['status'] = 'P' # 'P' -> Sale Pending
            else:
                listing['status'] = 'F' # 'F' -> For Sale

            # $ followed by a number is likely to be a price :-)
            # look first in the entry on the inventory page
            listing['price'] = regularize_price(entry.find(text=re.compile('\$[0-9]')))
            # try detail page if we didn't get one from the inventory page
            if listing['price'] == -1 and detail:
                listing['price'] = regularize_price(detail.find(text=re.compile('\$[0-9]')))

            # call the dealer-specific method
            # GEE TODO need to define some sort of error-handling protocol...
            ok = (ok and globals()[dealer['parse_listing_func']](listing, entry, detail))
            if ok:
                # check for common errors / signs of trouble
                if listing['local_id'] == last_local_id:
                    # not getting clean, unique local_ids from this dealer's page
                    logging.warning('Duplicate local_ids [{}] from {} inventory'.format(last_local_id, dealer['textid']))
                    ok = False
                last_local_id = listing['local_id']
            if ok:
                list_of_listings.append(listing)
                logging.debug('pulled listing: ' + json.dumps(listing))
            else:
                logging.warning('skipped listing: ' + json.dumps(listing))

            # END LOOP over listings on the page

        # is there another page of listings? Look for a link with "next" text
        # Note that there may be multiple such links (e.g. @ top & bottom of list);
        # they should be identical so just grab the first
        next_ref = soup.find('a', text=re.compile("[Nn]ext"))
        if next_ref:
            # build the full URL (it may be relative to current URL)
            full_inv_url = urllib.parse.urljoin(full_inv_url, next_ref.get('href'))
            req = urllib.request.Request(full_inv_url, headers=hdrs)
            page = urllib.request.urlopen(req)
            # GEE TODO - check that this is really a listings page and has
            # different listings, ie detect and avoid infinite loops
        else:
            break
        # END LOOP over all inventory pages

    logging.info('Loaded ' + str(len(list_of_listings)) + ' cars from ' + dealer['textid'])
    return list_of_listings


# pull_ebay_inventory()
#
# Pulls ebay listings via the ebay python sdk over the ebay finding api
#
# Accepts some input about what to pull & what not to
# (at least temporarily, we don't want everything ebay lists)
#
# parameters:
# area: 'Limit' => limits to local area (see notes)
# car_type: 'Interesting' => limits to "interesting" cars (see notes)
#
# NOTES:
# Must chunk queries into 10K items (100 items each x 100 pages) or ebay
# will give an error on page 101. eBay queries on the website are a messed
# up pile o' crap, so hopefully these APIs will give better results
#
# For now, 'local' = 150 miles of 95112 and 'interesting' filters as
# described in the named method, but it's a NOP since we're already
# limiting the current query to <= 1975 in order to avoid the 10K limit
#
def pull_ebay_inventory(area='Local', car_type='Interesting'):

    list_of_listings = []

    api = ebaysdk_finding(debug=False, appid=None, config_file='../conf/ebay.yaml',warnings=True)
    # GEE TODO check 'area' parameter before adding MaxDistance filter
    api_request = {
        'categoryId': 6001,
        'GLOBAL-ID': 100,
        'buyerPostalCode': 95112,
        'itemFilter': [
            ],
        'aspectFilter': [],
        'affiliate': {'trackingId': 1},
        'sortOrder': 'CountryDescending',
        'paginationInput': {
            'entriesPerPage': 150,
            'pageNumber': 1}
        }

    if area=='Local':
        api_request['itemFilter'].append({'name': 'MaxDistance',
                                          'value': 150 })

    # GEE TODO: temporary workaround for 10K limit; should iterate through years
    # in batches or something.
    for year in range(1900,1975):
        api_request['aspectFilter'].append({'aspectName': 'Model Year',
                                            'aspectValueName': year})

    while True:
        response = api.execute('findItemsAdvanced', api_request)
        r = response.dict()
        if r['ack'] != 'Success':
            # Hmm, when I get an error back from eBay the response can't be JSON dumped
            # for some reason. This command barfs saying it isn't JSON serializable:
            # print(response.json().dump())
            print(response.json())
            logging.error('eBay reports failure: {}'.format(response))
            break
        logging.info('Number of car listings found: {}'.format(r['searchResult']['_count']))
        for item in r['searchResult']['item']:
            ok = True
            logging.debug('eBay ITEM: {}'.format(item['itemId']))
            listing = Bunch() # build a listing bunch/dict for this car
            listing['source_textid'] = 'ebay'
            for attr in item['attribute']:
                if attr['name'] == 'Year':
                    listing['model_year'] = attr['value'][:4]
            listing['make'] = item['title'].split(':')[0].strip()
            listing['model'] = item['primaryCategory']['categoryName'] # alternatively could often get more info from title
            try:
                listing['pic_href'] = item['galleryURL']
            except KeyError:
                listing['pic_href'] = 'N/A'
            listing['listing_href'] = item['viewItemURL']
            listing['local_id'] = item['itemId']
            listing['stock_no'] = item['itemId']
            listing['status'] = 'F' # 'F' -> For Sale
            listing['listing_text'] = item['title']

            # GEE TODO: this is ignoring ebay price weirdness and currency
            try:
                listing['price'] = regularize_price(item['sellingStatus']['buyItNowPrice']['value']) 
            except:                
                listing['price'] = regularize_price(item['sellingStatus']['currentPrice']['value']) 

            # validate model_year
            try:
                junk = int(listing['model_year'])
            except ValueError:
                logging.warning('bad year [{}] for item {}'.format(listing['model_year'], listing['local_id']))
                listing['model_year'] = '1900'

            if (ok and car_type == 'Interesting'):
                ok = is_car_interesting(listing)

            if ok:
                list_of_listings.append(listing)
                logging.debug('pulled listing: ' + json.dumps(listing))
            else:
                logging.debug('skipped listing: ' + json.dumps(listing)) # debug nor warn b/c we're throwing out lots of stuff

            # END LOOP over listings on the page

        # is there another page of listings?
        current_page = int(r['paginationOutput']['pageNumber'])
        total_pages = int(r['paginationOutput']['totalPages'])
        logging.info('Loaded page {} of {}'.format(current_page, total_pages))
        if current_page < total_pages:
            api_request['paginationInput']['pageNumber'] = current_page + 1
            response = api.execute('findItemsAdvanced', api_request)
        else:
            break
        # END LOOP over all inventory pages

    logging.info('Loaded ' + str(len(list_of_listings)) + ' cars from ebay')
    
    return list_of_listings


# import_from_dealer
#
# Imports inventory from a dealership, overwriting (adding/updating) as needed
#
# parameters:
# con: db connection (None if no db access is possible/requested)
# es: indexing connection (None if no indexing is possible/requested)
#
# Notes:
#
# This is basically a wrapper around pull_dealer_inventory() that handles the
# persistence details of the pulled inventory. Assumes that a dealership's
# inventory is small enough to pull & update within a single db commit
# (and then this method commits)
#
def import_from_dealer(con, es, dealer, file=False):

    # get the active listings stored in the db for this dealer
    old_db_listing_hash = {}
    if con:
        c = con.cursor(db.cursors.DictCursor)
        rows = c.execute("""select * from listing where source_textid= %s and status = 'F'""",
                         (dealer['textid']))
        for listing in c.fetchall():
            logging.debug('existing record with (id, local_id) of ({}, {})'.format(listing['id'], listing['local_id']))
            old_db_listing_hash[listing['local_id']] = listing

    # get the current listings on the dealer's website inventory
    listings = pull_dealer_inventory(dealer)

    for listing in listings:
        if con:
            id = db_insert_or_update_listing(con, listing, old_db_listing_hash)
            listing.id = id
        else: # temporary -- use something other than db id as filename
            id = listing['local_id']
        if es:
            index_listing(es, listing)
        if file:
            listing['id'] = id # put it in the hash
            text_store_listing('/tmp/listings', listing)

    if con:
        # now mark all the listings that were in the db but not the website
        # inventory as closed
        for local_id, db_listing in old_db_listing_hash.items():
            if 'found' in db_listing:
                pass
            else:
                db_listing['status'] = 'R' # Removed, reason unknown
                if es:
                    index_listing(es, db_listing) # will remove based on status
                c = con.cursor(db.cursors.DictCursor)
                rows = c.execute("""update listing set status = %s, last_update = CURRENT_TIMESTAMP where id = %s""",
                                 (db_listing['status'], db_listing['id']))

        # and commit
        con.commit()

    return True


# all_norcal_inventory()
#
# Pull inventory from all the norcal sites we've written importers before
#
# This is a junk routine which should be replaced by something db-driven!
#
# returns a list of listings dicts
#
def all_norcal_inventory():
    list_of_listings = []
    for dealer in dealers:
        list_of_listings.extend(pull_dealer_inventory(dealers[dealer]))
    return list_of_listings


# db_insert_or_update_listing
#
# NOTES:
# returns the database ID of the listing (all other cases raise exceptions)
#
# updates the old_db_listing_hash entry by setting 'found' property, thus
# permitting easy deletion of records no longer found in current inventory
#
def db_insert_or_update_listing(con, listing, old_db_listing_hash = {}):
    db_listing = {}
    logging.debug('checking on existence of listing {}'.format(listing['local_id']))
    if listing['local_id'] in old_db_listing_hash:

        # matching listing already in the db
        db_listing = old_db_listing_hash[listing['local_id']]
        db_listing['found'] = True # mark it as still on the site
        logging.debug('found: {}'.format(db_listing))
        # now, do we need to update the record?
        update_required = False
        for field in ['status','model_year','make','model','price','listing_text','pic_href','listing_href']:
            if str(listing[field]) != str(db_listing[field]):
                # GEE TODO: check that currency isn't borked based on string/number comparison??
                # GEE TODO heh, currency handling generally (!!)
                logging.debug('value for {} changed from <{}> to <{}>'.format(field, db_listing[field], listing[field]))
                update_required = True
        if update_required:
            up = con.cursor(db.cursors.DictCursor)
            up.execute("""update listing set status = %s, model_year = %s, make = %s, model = %s, price = %s, listing_text = %s, pic_href = %s, listing_href = %s, source_textid = %s, stock_no = %s, last_update = CURRENT_TIMESTAMP where id = %s""",
                       (listing['status'], listing['model_year'], listing['make'],
                        listing['model'], listing['price'], listing['listing_text'],
                        listing['pic_href'], listing['listing_href'],
                        listing['source_textid'], listing['stock_no'],
                        db_listing['id']))
            logging.debug('found record id={}: {} {} {} (updated)'.format(db_listing['id'],listing['model_year'],listing['make'], listing['model']))
        else: # else listing is up to date; no update required
            logging.debug('found record id={}: {} {} {} (no update required)'.format(db_listing['id'],listing['model_year'],listing['make'], listing['model']))

    else: # no matching listing from the db -- insert
        ins = con.cursor(db.cursors.DictCursor)
        ins.execute(
            """insert into listing
(status, model_year, make, model, price, listing_text, pic_href, listing_href, source_textid, local_id, stock_no, listing_date, removal_date, last_update) values
(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)""",
            (listing['status'],listing['model_year'],listing['make'],listing['model'],listing['price'],listing['listing_text'],listing['pic_href'],listing['listing_href'],listing['source_textid'],listing['local_id'],listing['stock_no'],))

        # re-execute the same fetch which will now grab the new record
        c2 = con.cursor(db.cursors.DictCursor)
        c2.execute("""select * from listing where source_textid= %s and local_id = %s order by last_update desc""",
                   (listing['source_textid'], listing['local_id'],))
        db_listing = c2.fetchone()
        logging.debug('inserted record id={}: {} {} {}'.format(db_listing['id'],listing['model_year'],listing['make'], listing['model']))

    # if we get here, we succeeded... I assume
    return db_listing['id']


# index_listing
#
# adds a listing to the carbyr elasticsearch index
# (or removes the listing from the index if the status != 'F')
#
# NOTES:
#
# es seems to automatically handle duplicates by id, so relying on that for now
#
# only indexing the fields, NOT sucking in the full listing detail pages
# (but we could, if we added the page text to the listing dict)
#
def index_listing(es, listing):
    if listing['status'] == 'F':
        es.index(index="carbyr-index", doc_type="listing-type", id=listing['id'], body=listing)
    else:
        try:
            es.delete(index="carbyr-index", doc_type="listing-type", id=listing['id'])
        except NotFoundError as err:
            logging.warning('record with id={} not found during attempted deletion: {}'.format(listing['id'], err))
    return True


# text_store_listing
#
# stores a text file (suitable for text indexing) of the given listing
# in the given directory
#
def text_store_listing(list_dir, listing):
    # store car listing file in subdir by source (not the best, heh -- temporary, should really be some more reliable sharding mechanism)
    # and with the id (our internal id) as the filename root
    make_sure_path_exists(list_dir + '/' + listing['source_textid'])
    pathname=str(list_dir + '/' + listing['source_textid'] + '/' + str(listing['id']) + '.html')
    list_file=open(pathname,"w")
    list_file.write(json.dumps(listing))
    list_file.close()

    logging.debug("wrote listing id {} ({} {} {}) to file {}".format(listing['id'], listing['model_year'],listing['make'], listing['model'], pathname))
    return True

# ============================================================================
# DATA STRUCTURES
# ============================================================================
# heh - can't put these up in constants because they reference funcs not yet defined
# and python doesn't really do forward declarations

# map of dealerships, URLs, functions
# GEE TODO move this to a db table, etc etc
#

carbuffs = {
    'textid' : 'carbuffs',
    'full_name' : 'Car Buffs',
    'base_url' : 'http://carbuffs.com',
    'inventory_url' : '/inventory',
    'extract_car_list_func' : "lambda s: s.find_all(class_='car-cont')",
    'listing_from_list_item_func' : "lambda s: s",
    'parse_listing_func' : "carbuffs_parse_listing"
    }
# ccw site has NO useful markup; best plan I can come up with to ID a car entry
# is to look for <img> tag where src does NOT start with 'New-Site'
ccw = {
    'textid' : 'ccw',
    'full_name' : 'Classic Cars West',
    'base_url' : 'http://www.classiccarswest.com',
    'inventory_url' : '/Inventory.html',
    'extract_car_list_func' : "lambda s: s.find_all('img',src=re.compile('^([^N][^e][^w])'))",
    'listing_from_list_item_func' : "lambda s: s.parent.parent.parent",
    'parse_listing_func' : "ccw_parse_listing"
    }
cvclassics = {
    'textid' : 'cvclassics',
    'full_name' : 'Central Valley Classics',
    'base_url' : 'http://www.centralvalleyclassics.com',
    'inventory_url' : '/cars/carsfs.html',
    'extract_car_list_func' : "lambda s: s.find_all('img',alt=re.compile('Click'))", # Yuck!
    'listing_from_list_item_func' : "lambda s: s.parent.parent.parent", # Yuck again!
    'parse_listing_func' : "cvclassics_parse_listing"
    }
cfc = {
    'textid' : 'cfc',
    'full_name' : 'Checkered Flag Classics',
    'base_url' : 'http://checkeredflagclassics.com',
    'inventory_url' : '/',
    'extract_car_list_func' : "lambda s: s.find_all('li')",
    'listing_from_list_item_func' : "lambda s: s",
    'parse_listing_func' : "cfc_parse_listing"
    }
dawydiak = {
    'textid' : 'dawydiak',
    'full_name' : 'Cars Dawydiak',
    'base_url' : 'http://www.carsauto.com',
    'inventory_url' : '/other-inventory.htm?limit=500&order_by=&d=backw',
    'extract_car_list_func' : "lambda s: s.find_all(class_='in-lst-buttoned-nm')",
    'listing_from_list_item_func' : "lambda s: s.parent",
    'parse_listing_func' : "dawydiak_parse_listing"
    }
dawydiakp = {
    'textid' : 'dawydiakp',
    'full_name' : 'Cars Dawydiak',
    'base_url' : 'http://www.carsauto.com',
    'inventory_url' : '/porsche-inventory.htm?limit=500&order_by=&d=backw',
    'extract_car_list_func' : "lambda s: s.find_all(class_='in-lst-buttoned-nm')",
    'listing_from_list_item_func' : "lambda s: s.parent",
    'parse_listing_func' : "dawydiak_parse_listing"
    }
# GEE TODO: should also handle FJ's off-site inventory
fj = {
    'textid' : 'fj',
    'full_name' : 'Fantasy Junction',
    'base_url' : 'http://www.fantasyjunction.com',
    'inventory_url' : '/inventory',
    'extract_car_list_func' : "lambda s: s.find_all(class_='list-entry pkg list-entry-link')",
    'listing_from_list_item_func' : "lambda s: s",
    'parse_listing_func' : "fj_parse_listing"
    }
lcc = {
    'textid' : 'lcc',
    'full_name' : 'Left Coast Classics',
    'base_url' : 'http://www.leftcoastclassics.com',
    'inventory_url' : '/LCCofferings.html', # not sure why URLs are not parallel?
    'extract_car_list_func' : "lambda s: s.find_all('h3')", # Yuck!
    'listing_from_list_item_func' : "lambda s: s.parent.parent", # h3 under td under tr
    'parse_listing_func' : "lc_parse_listing" # shared parser for the 2 sets of cars
    }
lce = {
    'textid' : 'lce',
    'full_name' : 'Left Coast Exotics',
    'base_url' : 'http://www.leftcoastexotics.com',
    'inventory_url' : '/cars-for-sale.html', # not sure why URLs are not parallel?
    'extract_car_list_func' : "lambda s: s.find_all('h3')", # Yuck!
    'listing_from_list_item_func' : "lambda s: s.parent.parent", # h3 under td under tr
    'parse_listing_func' : "lc_parse_listing" # shared parser for the 2 sets of cars
    }
mhc = {
    'textid' : 'mhc',
    'full_name' : 'My Hot Cars',
    'base_url' : 'http://www.myhotcars.com',
    'inventory_url' : '/inventory.htm',
    'extract_car_list_func' : "lambda s: s.find_all(class_='invebox')",
    'listing_from_list_item_func' : "lambda s: s",
    'parse_listing_func' : "mhc_parse_listing"
    }
sfs = {
    'textid' : 'sfs',
    'full_name' : 'San Francisco Sportscars',
    'base_url' : 'http://sanfranciscosportscars.com',
    'inventory_url' : '/cars-for-sale.html',
    'extract_car_list_func' : "lambda s: s.find_all('h2')",
    'listing_from_list_item_func' : "lambda s: s.parent",
    'parse_listing_func' : "sfs_parse_listing"
    }
specialty = {
    'textid' : 'specialty',
    'full_name' : 'Specialty Auto Sales',
    'base_url' : 'http://www.specialtysales.com',
    'inventory_url' : '/inventory?per_page=300',
    'extract_car_list_func' : "lambda s: s.find_all(class_='vehicle-entry')",
    'listing_from_list_item_func' : "lambda s: s",
    'parse_listing_func' : "specialty_parse_listing"
    }
vip = {
    'textid' : 'vip',
    'full_name' : 'VIP Motors',
    'base_url' : 'http://www.vipmotors.us',
    'inventory_url' : 'http://vipmotors.autorevo.com/vehicles?SearchString=',
    'extract_car_list_func' : "lambda s: s.find_all(class_='inventoryListItem')",
    'listing_from_list_item_func' : "lambda s: s",
    'parse_listing_func' : "autorevo_parse_listing"
    }
# ^^^
# Note that the page on VIP's main site is just a js that calls out to autorevo
# the VIP literally doesn't actually contain listing info so we HAVE to go to
# the autorevo site

# GEE TODO investigate using OrderedDict
dealers = {
    'carbuffs' : carbuffs,
    'ccw' : ccw,
    'cfc' : cfc,
    'cvclassics' : cvclassics,
    'dawydiak' : dawydiak,
    'dawydiakp' : dawydiakp,
    'fj' : fj,
    'lcc' : lcc,
    'lce' : lce,
    'mhc' : mhc,
    'sfs' : sfs,
    'specialty' : specialty,
    'vip' : vip,
    }

# ============================================================================
# MAIN
# ============================================================================

def process_command_line():
    # initialize the parser object:
    parser = argparse.ArgumentParser(description='Imports car listings')
    parser.add_argument('--nodb', dest='db', action='store_const',
                        const=False, default=True, help='skip writing the listings to db tables')
    parser.add_argument('--noindex', dest='index', action='store_const',
                        const=False, default=True, help='skip indexing the listings')
    parser.add_argument('--files', dest='file', action='store_const',
                        const=True, default=False, help='writes listings to files in /tmp')
    parser.add_argument('--log_level', default='INFO',
                        choices=('DEBUG','INFO','WARNING','ERROR', 'CRITICAL'),
                        help='set the logging level')
    parser.add_argument('action',
                        choices=('list','import'),
                        help='action: list sources which can be imported and exit, or import from those sources')
    parser.add_argument('sources', nargs='*', help='the source(s) to pull from if action=import')

    return parser.parse_args()


def main():
    args = process_command_line()

    # start logging
    logging.basicConfig(level=args.log_level.upper())

    con = None # declare scope of db connection
    es = None # and the indexing connection
    dealerships = {}

    if args.db:
        con = db.connect('localhost', 'carsdbuser', 'car4U', 'carsdb', charset='utf8')
        # GEE TODO: test db connection success here (since we are not just doing 'with con:' as db usage is conditional)

        # ... and go ahead and fetch the sources from the db here for simplicity
        c = con.cursor(db.cursors.DictCursor)
        rows = c.execute("""select * from dealership where (flags & 2) != 0""")
        # GEE TODO there has to be a more efficient way to do this, but I
        # get an odd error if I do this:
        # 
        for dealer in c.fetchall():
            dealerships[dealer['textid']] = dealer
    else:
        dealerships = dealers; # use built-in/non-db dealership list

    if args.index:
        es = Elasticsearch()

    # now do what the user requested (the action)
    if args.action == 'list':
        for dealer in dealerships:
            print('{} [{}]'.format(dealer['textid'], dealer['full_name']))

        # GEE TODO: db reads & associated list of non-dealership sources

        # GEE TODO: remove these non-db sources, or clearly label as test-only
        print('test [special test file of 1 record]')
        print('norcal [special aggregation of norcal dealerships]')
        print('db_dealers [all dealers in the database]')

    elif args.action == 'import':
        for source in args.sources:
            if source in dealerships:
                import_from_dealer(con, es, dealerships[source])
            elif source == 'ebay':
                import_from_ebay(con, es)
            elif source == 'norcal':
                for dealer in dealerships:
                    import_from_dealer(con, es, dealer)
            else:
                logging.error('request of import from unknown source: {}'.format(source))
    else: # uh, shouldn't be possible?
        logging.error('oops -- action {} not recognized'.format(args.action))

    return True
    
if __name__ == "__main__":
    status = main()
    sys.exit(status)

