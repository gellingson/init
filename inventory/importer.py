#!/usr/local/bin/python3
#
# importer.py
#
# this is the main import script for grabbing inventory from various sources
#
# NOTES:
# GEE TODO currency handling

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
# CLASSES
# ============================================================================

# class Listing
#
# GEE TODO: finish this class and start using it :)
# could harcode a field list or not import from Dict, BUT we want to use
# buildit PyMYSQL row-as-dict reads so... ?
#
class Listing(Bunch):
    """A simple class that extends Dict/Bunch to describe a listing"""
    def __init__(self):
        self.id = None
        self.markers = None
        self.status = None
        self.model_year = None
        self.make = None
        self.model = None
        self.price = None
        self.listing_text = None
        self.pic_href = None
        self.listing_href = None
        self.source_type = None
        self.source_id = None
        self.source_textid = None
        self.local_id = None
        self.stock_no = None
        self.listing_date = None
        self.removal_date = None
        self.last_update = None
        

# ============================================================================
# CONSTANTS AND GLOBALS
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

boring_makes = ['Dodge','Chrysler', 'Ram', 'RAM', 'Jeep',
                'Honda', 'Acura', 'Toyota', 'Lexus', 'Scion', 'Nissan', 'Infiniti',
                'Mazda', 'Subaru', 'Isuzu', 'Mitsubishi',
                'Chevrolet','Chevy', 'Pontiac', 'Saturn', 'Cadillac', 'Buick', 'Oldsmobile',
                'GM','General','GMC',
                'Ford','Mercury', 'Lincoln',
                'BMW', 'Mini', 'MINI', 'Mercedes', 'Mercedes-Benz', 'MB',
                'Volkswagen', 'VW', 'Audi',
                'Fiat', 'Volvo', 'Land Rover', 'Range Rover', 'Saab',
                'Hyundai', 'Kia', 'Suzuki',
                'Smart']

interesting_models = ['Viper',
                      'NSX', 'MR2', 'MR-2', 'Supra', 'LFA', '300zx', 'Skyline', 'GTR',
                      'MX5', 'MX-5', 'Miata', 'MX-5 Miata', 'rx7', 'STI', 'Evolution', 'Evo',
                      'Corvette', 'Grand National', 
                      'Boss', 'Shelby', 'GT',
                      'M3', 'M5', 'M6', 'SLS', 'AMG', 'R8']

# will populate via associated method
# GEE TODO: yes, I should be using OOP (sigh)
non_canonical_makes = {}

# ============================================================================
# UTILITY METHODS
# ============================================================================

# populate_non_canonical_makes
#
# populates a hash of non-canonical makes
#
# NOTES:
#
# Yeah, yeah, this is a hack. But it works for now :).
#
def populate_non_canonical_makes(con):
    c = con.cursor(db.cursors.DictCursor)
    rows = c.execute("""select * from non_canonical_make""")
    for ncm in c.fetchall():
        if ncm['consume_words']:
            ncm['consume_words'] = ncm['consume_words'].split(" ")
        if ncm['push_words']:
            ncm['push_words'] = ncm['push_words'].split(" ")
        non_canonical_makes[ncm['non_canonical_name']] = ncm
    return True


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
    elif isinstance(price_string, str):
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
    else: # was passed something other than a string (int, float, ...?)
        # lets try force-converting it; if that fails then....
        try:
            price = int(price_string) # which isn't a string
        except: # eat any error here
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
    year = None
    makemodel = None
    make = None
    model = None
    if year_make_model_string: # is not None or ''
        words = year_make_model_string.split(" ")
        for word in range (0, len(words)-1):
            try:
                s = words[word].strip("'`\"") # strip likely junk (e.g. '67)
                s = s.split('.')[0] # chop any trailing decimal (e.g. 1973.5)
                num = int(s)
                if num > 1900 and num < 2020:
                    year = num
                if num >= 20 and num <= 99:
                    year = 1900 + num
                if num < 20:
                    year = 2000 + num
                if year: # only look for makemodel in the remaining words
                    if len(words) > word:
                        makemodel = words[(word+1):]
                break
            except ValueError:
                pass # that wasn't it... no harm, no foul

        if not year: # then we see no year in the offered string
            # this means we're not doing well and will probably trash this
            # anyway, but let's see what we get when we look for a make
            for word in range (0, len(words)-1):
                try:
                    s = words[0].strip("'` *~_\"\t") # strip likely junk
                    ncm = non_canonical_makes[s.upper()]
                    make = ncm['canonical_name']
                    # apply the ncm's deltas, then take the rest as model
                    modellist = []
                    if word == len(words)-1: # this is the end of the string
                        modellist = []
                    else:
                        modellist =  words[(word+1):]
                    # GEE TODO handle multiple words here; for now just the first
                    if ncm['consume_words'] and modellist and modellist[0] in ncm['consume_words']:
                        modellist.pop(0) # throw it away
                    if ncm['push_words']:
                        modellist = ncm['push_words'] + modellist
                    # GEE TODO: check if the push word(s) are already there (e.g. 'vette corvette stingray')
                    model = ' '.join(modellist).strip("'` *~_\"\t")
                    break
                except KeyError:
                    pass # that wasn't it... no harm, no foul
            # if the for loop finishes without finding a make, then screw it...
            # leave stuff blank
                
            makemodel = words # use the whole list-of-words from the string

        elif year and makemodel: # we did find both year and remaining string
            # jackpot!
            # GEE TODO: apply the real make/model regularization here
            make = makemodel[0].strip("'` *~_\"\t")
            try:
                model_list = []
                modelstem = []
                ncm = non_canonical_makes[make.upper()]
                make = ncm['canonical_name']
                makemodel.pop(0) # throw away the noncanonical
                # GEE TODO handle multiple words here; for now just the first
                if ncm['consume_words'] and makemodel and makemodel[0] in ncm['consume_words']:
                    makemodel.pop(0) # throw it away
                if ncm['push_words']:
                    modelstem = ncm['push_words']
                    # GEE TODO: check if the push word(s) are already there (e.g. 'vette corvette stingray')
                else:
                    modelstem = []
                model_list = modelstem + makemodel
            except KeyError as e:
                # didn't find it; assume we're OK with make as given
                make = make.title().strip("'` *~_\"\t") # initcap it
                if len(makemodel) > 1:
                    model_list = makemodel[1:]
            model = ' '.join(model_list).strip("'` *~_\"\t")
        else: # found a potential year string but no make/model after it
            # this is likely a false positive; let's chuck even the year
            # and tell the caller we found nothing
            year = None
            make = None
            model = None

        return (str(year), make, model) # backconvert year to string


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
def is_car_interesting(listing, include_unknown_makes=True):
    if int(listing['model_year']) > 1800 and int(listing['model_year']) <= 1975:
        return True # automatically interesting
    if not include_unknown_makes:
        try:
            discard = non_canonical_makes[listing['make']]
            # if it's in there, do nothing and continue checks
        except KeyError as e:
            return False # something odd -- chuck it
        
    # GEE TODO: case of comparisons & substrings make this.... interesting
    if listing['make'] not in boring_makes: # wow is this inefficient - need make/model db stuff
        return True
    if listing['model'] in interesting_models: # pull particular models back in
        return True
    if int(listing['price']) > 100000: # Prima facia evidence of interesting status? :)
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


# cvc_parse_listing
#
def cvc_parse_listing(listing, entry, detail):

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

    # if dawydiak has any listing text, it's in the introlist
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

    if (detail.find('title')):
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
# samples/<dealer>_inventory_page.html
# samples/<dealer>_detail_page.html
#
# this was first developed on/for specialty & fantasy junction sites
#
def pull_dealer_inventory(dealer):

    list_of_listings = []
    last_local_id = None

    # get a page of listings; we have pagination logic to loop over addl pages

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
            listing.markers = None
            listing.model_year = None
            listing.make = None
            listing.model = None
            listing.price = None
            listing.listing_text = None

            # for some sites the full entry is actually a parent or sibling
            # or similar permutation of the list item we just grabbed
            myfunc = eval(dealer['listing_from_list_item_func'])
            entry = myfunc(item)

            # try standard grabs; then call the dealer-specific method for
            # overrides & improvements
            listing.source_type = 'D'
            listing.source_id = dealer.id
            listing.source_textid = dealer.textid

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
                    logging.warn('found non-http detail URL: {}'.format(detail_url))
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
                        # if the detail page is well-formed (has a body)
                        # then throw out the rest & keep just the body
                        body = detail.find('body')
                        if (body):
                            detail = body

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

            # look for a string to use as listing text:
            # pick the longest string in a likely tag within the entry
            listing['listing_text'] = ''
            for tag in entry.descendants:
                if (tag.name == 'p' or tag.name == 'div' or tag.name == 'li' or
                    tag.name == 'span' or tag.name == 'td'):
                    if (len(tag.text) > 50 and
                        len(tag.text) > len(listing['listing_text'])):
                        listing['listing_text'] = tag.text
            # if that failed, try to find something on the detail page
            if detail and not listing['listing_text']:
                for tag in detail.descendants:
                    if (tag.name == 'p' or tag.name == 'div' or tag.name == 'li' or
                        tag.name == 'span' or tag.name == 'td'):
                        if (len(tag.text) > 50 and
                            len(tag.text) > len(listing['listing_text'])):
                            listing['listing_text'] = tag.text

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
                # check for common errors / signs of trouble:
                # need a listing_id
                if listing['local_id'] == last_local_id:
                    # not getting clean, unique local_ids from this dealer's page
                    logging.warning('Duplicate local_ids [{}] from {} inventory'.format(last_local_id, dealer['textid']))
                    ok = False
                last_local_id = listing['local_id']
                # model_year must be a string containing an integer
                # (not None or a string that doesn't become an int, etc)
                if not listing['model_year']:
                    listing['model_year'] = '1'
                elif isinstance(listing['model_year'], int):
                    listing['model_year'] = str(listing['model_year'])
                else:
                    try:
                        junk = int(listing['model_year']) # convert it                        
                    except ValueError:
                        listing['model_year'] = '1' #oops

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
            logging.debug('Loading next page of inventory via URL: {}'.format(full_inv_url))
            req = urllib.request.Request(full_inv_url, headers=hdrs)
            page = urllib.request.urlopen(req)
            # GEE TODO - check that this is really a listings page and has
            # different listings, ie detect and avoid infinite loops
            # GEE TODO - catch the ugly exceptions I get for a bogus URL (errno 8 & a big splat) and also errno 54 / connection reset by peer -> ConnectionResetError, etc (here & in all other URL gets)
        else:
            break
        # END LOOP over all inventory pages

    logging.info('Loaded ' + str(len(list_of_listings)) + ' cars from ' + dealer['textid'])
    return list_of_listings


# pull_classified_inventory()
#
# pulls inventory from common classified sites as directed
#
# NOTES: NOT WRITTEN YET; need to understand if this really != dealer method
#
def pull_classified_inventory(classified, inventory_marker):
    return [], inventory_marker


# pull_ebay_inventory()
#
# Pulls ebay listings via the ebay python sdk over the ebay finding api
#
# Accepts some input about what to pull & what not to
# (at least temporarily, we don't want everything ebay lists)
#
# parameters:
# classified: the classified site we are to pull (ebay motors in this case)
# inventory_marker: a marker used to chunk the work; opaque to caller
# area: 'Local' => limits to local area (see notes)
# car_type: 'Interesting' => limits to "interesting" cars (see notes)
#
# returns:
# list_of_listings: a set of listings (could be partial or entire set)
# inventory_marker: pagination/subset marker (will be None if done)
#
# NOTES:
#
# Must chunk queries into 10K items (100 items each x 100 pages) or ebay
# will give an error on page 101. eBay queries on the website are a messed
# up pile o' crap, so hopefully these APIs will give better results
#
# For now, 'local' = 150 miles of 95112 and 'interesting' filters as
# described in the named method
#
# GEE TODO: chunking by years may not be entirely sufficient to avoid the 10K
# limit (and gives us some pretty big work bundles). Should get more granular.
#
def pull_ebay_inventory(classified, inventory_marker, area='Local', car_type='Interesting'):

    list_of_listings = []

    # wonky workaround for ebay's 10K limit. Works with locality 95112
    # (no set approaching 10K) but will need more work if/as I scale up
    # note: we're throwing away most of the cars post-1975 (per def of
    # is_car_interesting() method) but I'd like to tweak that method to
    # give me some decent mid-term results, so... into the fray we go!
    ebay_year_batches = [ (1900, 2010), (2011, 2012), (2013, 2013), (2014, 2014), (2015, 2020) ]
    if not inventory_marker:
        inventory_marker = 0 # start with the first batch...

    api = ebaysdk_finding(debug=False, appid=None, config_file='../conf/ebay.yaml',warnings=True)
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

    if area == 'Local':
        logging.debug('limiting to local cars')
        api_request['itemFilter'].append({'name': 'MaxDistance',
                                          'value': 150 })
    else:
        logging.debug('NOT limiting to local cars')

    # batching by years to avoid ebay's 10K limit and manage our commit blocks
    for year in range(ebay_year_batches[inventory_marker][0], ebay_year_batches[inventory_marker][1]+1):
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
        if r['searchResult']['_count'] == 0:
            logging.warning('eBay returned a set of zero records')
            break
        logging.info('Number of car listings found: {}'.format(r['searchResult']['_count']))
        for item in r['searchResult']['item']:
            ok = True
            logging.debug('eBay ITEM: {}'.format(item['itemId']))
            listing = Bunch() # build a listing bunch/dict for this car
            listing.markers = None
            listing.source_type = 'C'
            listing.source_id = classified.id
            listing.source_textid = classified.textid
            try:
                for attr in item['attribute']:
                    if attr['name'] == 'Year':
                        listing['model_year'] = attr['value'][:4]
            except KeyError:
                listing['model_year'] = 'None'
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
                listing['model_year'] = '1'

            if (ok and car_type == 'Interesting'):
                ok = is_car_interesting(listing)

            if ok:
                list_of_listings.append(listing)
                logging.debug('pulled listing: ' + json.dumps(listing))
            else:
                logging.debug('skipped listing: ' + json.dumps(listing)) # debug not warn b/c we're throwing out lots of stuff

            # END LOOP over listings on the page

        # is there another page of listings?
        # IMPORTANT NOTE: eBay page counts are *approximate*, meaning you might
        # get back page 48 of 50, then the next page will be empty and that is
        # the end of the list. Also, the "of 50" might say "of 49" on one page
        # and "of 53" on another page of the same pull
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

    inventory_marker = inventory_marker + 1
    if inventory_marker == len(ebay_year_batches):
        inventory_marker = None # done!

    return list_of_listings, inventory_marker


# pull_3taps_inventory()
#
# Pulls listings (for some source/classified) via the 3taps api
#
# This method is for all 3taps sources; the classified param tells which one
#
# Accepts some input about what to pull & what not to
#(at least temporarily, we don't want everything 3taps lists)
#
# parameters:
# classified: the classified site we are to pull
# inventory_marker: a marker used to chunk the work; opaque to caller
# area: 'Local' => limits to local area (see notes)
# car_type: 'Interesting' => limits to "interesting" cars (see notes)
#
# returns:
# list_of_listings: a set of listings (could be partial or entire set)
# inventory_marker: pagination/subset marker (will be None if done)
#
# NOTES:
#
# 3taps provides polling with an anchor, so unlike with other sites we don't
# have to reload all the active listings each time. Yay! Much simpler this way.
#
# We also get data already broken into useful json. Unfortunately we sometimes
# get less richness (e.g. very small thumbs or only partial text).

# We also have to decide (on a site-by-site basis) whether to load the detail
# pages or just use the 3taps data and avoid hitting the originating site.
#
# 3taps doesn't seem to offer control over the chunking of the polling results;
# it returns chunks of 1000 listings. We'll chunk that way too for simplicity.
#
# For now, 'local' = ???? GEE TODO ???? and 'interesting' filters as
# described in the named method
#
# GEE TODO (in this and other methods): switch action on 'interesting' from
# discarding to suitable tagging
#
# GEE TODO clean up the classified (and dealer) db entries/table structures
# for now, this method goes in custom_pull_method and the anchor goes in
# the extract_car_list_func field
#
def pull_3taps_inventory(classified, inventory_marker, area='Local', car_type='Interesting'):

    list_of_listings = []

    # for 3taps we want to keep the anchor in the classified record (which
    # ultimately means in the db) but we will also feed it through the
    # inventory_marker param as a mechanism for flow control only. Since
    # this routine only pulls records and doesn't touch the db, we will
    # update the classified record but trust the caller to update the db

    if inventory_marker:
        pass # run from the passed-in point
    else:
        # caller doesn't specify; start from the anchor in classified
        inventory_marker = classified.extract_car_list_func # see TODO - anchor is in temporary storage location

    logging.info('Pulling inventory from 3taps for {} starting with marker {}'.format(classified.textid, inventory_marker))

    # no dedicated python sdk, but simple enough JSON APIs to call directly
    url = 'http://polling.3taps.com/poll?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,account_id,source,category,location,external_id,external_url,heading,body,timestamp,timestamp_deleted,expires,language,price,currency,images,annotations,deleted,flagged_status,state,status'
    url_params = ['&source={}'.format(classified.textid.upper())]
    url_params.append('&anchor={}'.format(inventory_marker))
    if area == 'Local':
        logging.debug('limiting to local cars')
        # GEE TODO: note that the anchor will be invalidated if we switch back and forth between local and not
        url_params.append('&location.state=USA-CA')
    else:
        logging.debug('NOT limiting to local cars')

    url = url + ''.join(url_params)
    logging.debug('inventory URL is: {}'.format(url))

    try:
        req = urllib.request.Request(url, headers=hdrs)
        page = urllib.request.urlopen(req)
        bytestream = page.read()
        r = json.loads(bytestream.decode())
    except urllib.error.HTTPError as error:
        logging.error('Unable to poll 3taps at ' + url + ': HTTP ' + str(error.code) + ' ' + error.reason)
        return None, None
    
    if page.getcode() != 200:
        logging.error('Failed to poll 3taps at ' + url + ' with HTTP response code ' + str(page.getcode()))
        logging.error('Full error page:'.format(bytestream.decode()))
        return None, None

    if not r['success']:
        logging.error('3taps reports failure: {}'.format(json.dumps(r)))
        return None, None

    if len(r['postings']) == 0:
        logging.warning('3taps returned a set of zero records')
        return None, None

    logging.info('Number of car listings found: {}'.format(len(r['postings'])))
    for item in r['postings']:
        ok = True
        item = Bunch(item) # for convenience
        logging.debug('3taps ITEM: {}'.format(item.id))
        listing = Bunch() # build a listing bunch/dict for this car
        listing.markers = None
        listing.source_type = 'C'
        listing.source_id = classified.id
        listing.source_textid = classified.textid

        # GEE TODO: get whitelisted with 3taps for full html/annotation info (make/model/year)?
        # carsd seems to have consistent year/make/model
        # autod usually has all three but not always
        # craig sometimes has year, but usually not the other two
        # in all cases, let's take the best we can get
        # (without triggering key errors for missing annotations)
        model_year = None
        make = None
        model = None
        if 'year' in item.annotations:
            model_year = item.annotations['year']
        if 'make' in item.annotations:
            make = item.annotations['make']
        if 'model' in item.annotations:
            model = item.annotations['model']
        if model_year and make and model:
            (listing.model_year,
             listing.make,
             listing.model) = regularize_year_make_model(' '.join([model_year, make, model]))
        else:
            (listing.model_year,
             listing.make,
             listing.model) = regularize_year_make_model(item.heading)

            if listing.model_year == 1 and model_year:
                # then I didn't get any year from the heading
                # but I can use the model_year from the annotations
                listing.model_year = model_year
            elif model_year and (listing.model_year != model_year):
                # WTF, mismatch? Take the annotation one (more reliable)
                logging.warn('overriding heading year of {} with annotation year of {}'.format(listing.model_year, model_year))
                listing.model_year = model_year
        #logging.info('a: {} {} {} h: {} out: {} {} {}'.format(model_year, make, model, item.heading, listing.model_year, listing.make, listing.model))
        try:
            listing.pic_href = item.images[0]['full']
        except (KeyError, IndexError) as e:
            listing.pic_href = 'N/A'
        listing.listing_href = item.external_url
        listing.local_id = item.external_id # use the source identifier to minimize dupes
        listing.stock_no = item.id # keep the 3taps ID around too (at least the latest one)
        if not listing.local_id:
            # some feeds (e.g. autod) *occasionally* lack the local_id;
            # fall back to stock_no
            logging.warn('listing for a {} {} {} has no local ID; using 3taps ID {}'.format(listing.model_year, listing.make, listing.model, listing.stock_no))
            listing.local_id = listing.stock_no

        # GEE TODO: examine & use flagging info
        if item.status == 'for_sale' and item.deleted == False:
            listing.status = 'F' # 'F' -> For Sale
        else:
            listing.status = 'R' # 'R' -> Removed, unknown reason

        listing.listing_text = item.heading

        #try:
        #    listing.price = regularize_price(item.annotations['price']) 
        #except ValueError:
        listing.price = regularize_price(item.price)

        # validate model_year
        try:
            junk = int(listing['model_year'])
        except ValueError:
            logging.warning('bad year [{}] for item {}'.format(listing['model_year'], listing['local_id']))
            listing['model_year'] = '1'

        if (ok and car_type == 'Interesting'):
            if classified.textid == 'craig':
                # be tougher on these for now because there is so much junk
                ok = is_car_interesting(listing, include_unknown_makes=False)
            else:
                ok = is_car_interesting(listing)

        if ok:
            list_of_listings.append(listing)
            logging.debug('pulled listing: ' + json.dumps(listing))
        else:
            logging.debug('skipped listing: ' + json.dumps(listing)) # debug not warn b/c we're throwing out lots of stuff

        # END LOOP over listings in the feed pull

    logging.info('Loaded {} cars from 3taps for {}'.format(str(len(list_of_listings)), classified.textid))

    # update the classified record with the new 3taps anchor AND
    # send the same value back as the inventory marker.
    classified.extract_car_list_func = r['anchor']
    inventory_marker = r['anchor']

    # note: 3taps doesn't tell us when/if we are caught up -- we just won't see
    # a full set of new records. We could have a few that came in while we're
    # running but lets NOT endlessly cycle on that....
    if len(r['postings']) < 500: # arbitrary number
        inventory_marker = None # signal that we are done!

    return list_of_listings, inventory_marker


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
        rows = c.execute("""select * from listing where source_textid= %s""",
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


# import_from_classified
#
# Imports inventory from a classified site, overwriting (adding/updating) as needed
#
# parameters:
# con: db connection (None if no db access is possible/requested)
# es: indexing connection (None if no indexing is possible/requested)
#
# Notes:
#
# This is basically a wrapper around a generic or site-specific method
# [pull_<foo>_inventory()] that handles the persistence details of the
# pulled inventory. Handles chunking up the classified site's inventory
# into reasonable-size commit blocks (which this method commits)
#
# NOTE: no longer supporting writing files or skipping db or indexing
#
def import_from_classified(con, es, classified):

    # 3taps provides polling w/ only new/updated records in the stream, so
    # we explicitly get deletes/expirations/etc. All other sites we need
    # to treat disappearance of the listing as cause for cancellation

    if classified.custom_pull_func != 'pull_3taps_inventory':
        # mark the active listings stored in the db for this classified
        c = con.cursor(db.cursors.DictCursor)
        rows = c.execute("""update listing set markers = concat(ifnull(markers,''), 'P') where source_textid= %s and status = 'F'""",
                         (classified['textid']))
        logging.debug('Painted {} existing records for classified site {}'.format(rows, classified['full_name']))
        con.commit()

    inventory_marker = None
    done = False
    while not done:

        listings = []

        # get the current active inventory of website listings
        # or, in the case of 3taps, the deltas since the last polling
        # note the special-casing for some sites that have their own method

        if classified['custom_pull_func']:
            listings, inventory_marker = globals()[classified['custom_pull_func']](classified, inventory_marker)
        else:
            listings, inventory_marker = pull_classified_inventory(classified, inventory_marker)

        # now put the located records in the db & index
        if listings:
            for listing in listings:
                listing.id = db_insert_or_update_listing(con, listing)
                index_listing(es, listing)

            # and commit the block of listings
            con.commit()
            logging.debug('committed a block of listings for {}'.format(classified.textid))

        # check if we're done?
        if not inventory_marker:
            done = True
        # END LOOP over blocks of inventory (while not done)

    if classified.custom_pull_func == 'pull_3taps_inventory':
        # in the 3taps case we just need to update the anchor that tells what
        # records we have pulled and thus where to start from next time;
        # the pull method will already have updated the field in classified
        logging.debug('Saving the 3taps anchor')
        logging.info('func, id = {}, {}'.format(classified.extract_car_list_func, classified.id))
        c = con.cursor(db.cursors.DictCursor)
        rows = c.execute("""update classified set extract_car_list_func = %s where id = %s""",
                         (classified.extract_car_list_func, classified.id))
    else:
        # now mark all the listings that were in the db but not the website
        # inventory as closed; note that we have to load each one in order to
        # remove it from the index
        # GEE TODO: can I improve this to use an es delete-by-query somehow?

        logging.info('Removing listings that have been taken down since the last pull')
        c = con.cursor(db.cursors.DictCursor)
        rows = c.execute("""select id from listing where source_textid = %s and instr(markers,'P') != 0""",
                         (classified['textid']))
        result = c.fetchmany()
        while result:
            for listing_id in result:
                try:
                    es.delete(index="carbyr-index", doc_type="listing-type", id=listing_id)
                except NotFoundError as err:
                    logging.warning('record with id={} not found during attempted deletion: {}'.format(listing_id, err))
            result = c.fetchmany()

        # mark them all in the db in one query to avoid per-record round-trips
        c = con.cursor(db.cursors.DictCursor)
        rows = c.execute("""update listing set status = 'R', markers=replace(markers,'P',''), last_update = CURRENT_TIMESTAMP where source_textid = %s and instr(markers,'P') != 0""",
                         (classified['textid']))

    con.commit() # aaaaaand commit!
    logging.info('Completed inventory pull for {}'.format(classified.textid))

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


# match_from_hash()
#
# NOTE: assumes the hash has only records with matching source_textid
#
def match_from_hash(listing, hashset):
    if listing['local_id'] in hashset:
        return hashset[listing['local_id']]
    return None


# match_from_db()
def match_from_db(con, listing):
    db_listing = {}
    c = con.cursor(db.cursors.DictCursor) # get result as a dict rather than a list for prettier interaction
    rows = c.execute("""select * from listing where source_textid= %s and local_id = %s""",
                     (listing['source_textid'], listing['local_id'],))
    return c.fetchone()


# db_insert_or_update_listing
#
# parameters:
# con: db connection (None if no db access is possible/requested)
# listing: the current listing
# existing_inventory: hash of this dealer's existing/previous inventory
#
# returns the database ID of the listing (all other cases raise exceptions)
#
# NOTES:
#
# this method coordinates with the caller in one of two methods for catching
# and deleting records no longer found in current inventory:
#
# if an existing_inventory hash is passed, it is searched for matches and any
# matching record is marked so that the caller can identify matched records;
#      -or-
# if no hash is passed, this method searches the db for potential matches and
# ensures matched records are updated in the db (removes pending-delete marker)
#
# also: if there is a matching record, the new record overrides most fields
# but will NOT override a status of 'X' (removed, not-a-valid-listing).
#
def db_insert_or_update_listing(con, listing, existing_inventory = {}):
    db_listing = {}
    logging.debug('checking on existence of listing {}'.format(listing['local_id']))
    if existing_inventory:
        db_listing = match_from_hash(listing, existing_inventory)
    else:
        db_listing = match_from_db(con, listing)

    if db_listing: # found a match

        db_listing['found'] = True # mark it as still on the site
        # NOTE: in the using-hash case this actually modifies the hash,
        # which may be used by the caller for cleanup of old records
        # NOTE2: in the non-hash case we must force an update to remove
        # the pending-delete marker :(
        logging.debug('found: {}'.format(db_listing))
        update_required = False
        if db_listing['status'] == 'X':
            # remove the pending-delete marker but make no other changes
            update_required = True
            if db_listing['markers']:
                db_listing['markers'] == db_listing['markers'].translate({ord(i):None for i in 'P'})
        else:
            for field in ['markers','status','model_year','make','model','price','listing_text','pic_href','listing_href']:
                if str(listing[field]) != str(db_listing[field]):
                    logging.debug('value for {} changed from <{}> to <{}>'.format(field, db_listing[field], listing[field]))
                    db_listing[field] = listing[field]
                    update_required = True
        if update_required:
            up = con.cursor(db.cursors.DictCursor)
            up.execute("""update listing set
status = %s, markers = %s,
model_year = %s, make = %s, model = %s,
price = %s, listing_text = %s,
pic_href = %s, listing_href = %s,
source_type = %s, source_id = %s, source_textid = %s,
stock_no = %s,
last_update = CURRENT_TIMESTAMP where id = %s""",
                       (db_listing['status'], db_listing['markers'],
                        db_listing['model_year'], db_listing['make'], db_listing['model'],
                        db_listing['price'], db_listing['listing_text'],
                        db_listing['pic_href'], db_listing['listing_href'],
                        db_listing['source_type'], db_listing['source_id'], db_listing['source_textid'],
                        db_listing['stock_no'], 
                        db_listing['id']))
            logging.debug('found record id={}: {} {} {} (updated)'.format(db_listing['id'], db_listing['model_year'], db_listing['make'], db_listing['model']))
        else: # else listing is up to date; no update required
            logging.debug('found record id={}: {} {} {} (no update required)'.format(db_listing['id'],listing['model_year'],listing['make'], listing['model']))

    else: # no matching listing in the previously-existing inventory -- insert
        ins = con.cursor(db.cursors.DictCursor)
        ins.execute(
            """insert into listing
(status, markers,
model_year, make, model,
price, listing_text,
pic_href, listing_href,
source_type, source_id, source_textid,
local_id, stock_no,
listing_date, removal_date, last_update) values
(%s, %s,
%s, %s, %s,
%s, %s,
%s, %s,
%s, %s, %s,
%s, %s,
CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)""",
            (listing['status'], listing['markers'],
             listing['model_year'], listing['make'], listing['model'],
             listing['price'], listing['listing_text'],
             listing['pic_href'], listing['listing_href'],
             listing['source_type'], listing['source_id'],listing['source_textid'],
             listing['local_id'], listing['stock_no'],))

        # re-execute the same fetch which will now grab the new record
        c2 = con.cursor(db.cursors.DictCursor)
        c2.execute("""select * from listing where source_textid= %s and local_id = %s order by last_update desc""",
                   (listing['source_textid'], listing['local_id'],))
        db_listing = c2.fetchone()
        if (db_listing):
            logging.debug('inserted record id={}: {} {} {}'.format(db_listing['id'],listing['model_year'],listing['make'], listing['model']))
        else:
            logging.error('failed to find newly-inserted record: {} {} {} {}'.format(listing['local_id'],listing['model_year'],listing['make'], listing['model']))
            raise TypeError

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
            # NOTE: this can easily happen if we find a record of a SOLD car but did not already have the car listing open
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
cvc = {
    'textid' : 'cvc',
    'full_name' : 'Central Valley Classics',
    'base_url' : 'http://www.centralvalleyclassics.com',
    'inventory_url' : '/cars/carsfs.html',
    'extract_car_list_func' : "lambda s: s.find_all('img',alt=re.compile('Click'))", # Yuck!
    'listing_from_list_item_func' : "lambda s: s.parent.parent.parent", # Yuck again!
    'parse_listing_func' : "cvc_parse_listing"
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
    'cvc' : cvc,
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
    classifieds = {}

    if args.db:
        try:
            con = db.connect(os.environ['OGL_DB_HOST'],
                             os.environ['OGL_DB_USERACCOUNT'],
                             os.environ['OGL_DB_USERACCOUNT_PASSWORD'],
                             os.environ['OGL_DB'],
                             charset='utf8')
        except KeyError:
            print("Please set environment variables for OGL DB connectivity and rerun.")
            sys.exit(1)

        # GEE TODO: test db connection success here (since we are not just doing 'with con:' as db usage is conditional)

        # ... and go ahead and fetch the sources from the db here for simplicity
        # GEE TODO: once I retire the non-db path this can be turned into query-by-source-name for the import case
        c = con.cursor(db.cursors.DictCursor)
        rows = c.execute("""select * from dealership where status = 'I'""")
        for dealer in c.fetchall():
            dealerships[dealer['textid']] = Bunch(dealer)
        c = con.cursor(db.cursors.DictCursor)
        rows = c.execute("""select * from classified where status = 'I'""")
        for classified in c.fetchall():
            classifieds[classified['textid']] = Bunch(classified)
        # read in all the non-canonical makes into a hash for easy & quick ref
        populate_non_canonical_makes(con)
    else:
        dealerships = dealers; # use built-in/non-db dealership list
        # classifieds will remain NULL -- non-db func does not exist for any of them

    if args.index:
        es = Elasticsearch()

    # now do what the user requested (the action)
    if args.action == 'list':
        for dealer in dealerships:
            print('{} [dealer {}]'.format(dealerships[dealer]['textid'], dealerships[dealer]['full_name']))
        for classified in classifieds:
            print('{} [classified site {}]'.format(classifieds[classified]['textid'], classifieds[classified]['full_name']))

        # GEE TODO: remove these non-db sources, or clearly label as test-only
        print('test [special test file of 1 record]')
        print('norcal [special aggregation of norcal dealerships]')
        print('db_dealers [all dealers in the database]')

    elif args.action == 'import':
        for source in args.sources:
            if source in dealerships:
                import_from_dealer(con, es, dealerships[source])
            elif source in classifieds:
                import_from_classified(con, es, classifieds[source])
            elif source == 'norcal':
                for dealer in dealerships:
                    import_from_dealer(con, es, dealerships[dealer])
            else:
                logging.error('request of import from unknown source: {}'.format(source))
    else: # uh, shouldn't be possible?
        logging.error('oops -- action {} not recognized'.format(args.action))

    return True
    
if __name__ == "__main__":
    status = main()
    sys.exit(status)
