#!/opt/local/bin/python
#
# import.py
#
# this is the main import script for grabbing inventory from various sources

import sys
import re
import json
import urllib2
import urlparse
import os
import errno
import logging
import MySQLdb as db
from bs4 import BeautifulSoup

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
#
def regularize_price(price_string):
    if price_string == None:
        price = -1
    else:
        try:
            price = int(re.sub('[\$,]', '', price_string))
        except ValueError:
            price = -1
    return price


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


# test_inventory()
#
# creates a bogus listing since this is a test script :)
#
# returns a list containing that one bogus listing
#
def test_inventory():
    # 
    test_listing = {}
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

# carbuffs_parse_listing
#
#
def carbuffs_parse_listing(listing, entry, detail):

    # get the short listing text from the inventory page
    listing['listing_text'] = entry.find(class_="car-excerpt").text

    # pull the rest of the fields from the detail page
    words = detail.find(class_='car-name').text.encode('ascii','ignore').split(" ", 2)
    listing['model_year'] = int(words[0])
    listing['make'] = words[1]
    listing['model'] = words[2]

    # carbuffs has no stock#/inventory ID; use the unique URL element
    listing['local_id'] = listing['listing_href'].split('inventory')[1].replace("'","")
    listing['stock_no'] = listing['local_id'] # no separate stock#

    # common name/value patterns in details page:
    #<li><strong>Car model year:</strong> 1963</li>
    #<p class="car-asking-price"><strong>Asking Price:</strong> $89,950</p>
    pe = detail.find('strong',text='Asking Price:')
    if pe != None:
        pe = pe.next_sibling
    listing['price'] = regularize_price(pe)

    return True


# cvclassics_parse_listing
#
#
def cvclassics_parse_listing(listing, entry, detail):

    # this site is super-sparse, with no useful tagging...
    # we just have to make the best of it
    strings = entry.find_all(text=True)

    # get the short listing text from the inventory page
    listing['listing_text'] = strings[1]

    # pull the rest of the fields from the detail page
    words = strings[0].split(" ", 2)
    listing['model_year'] = int(words[0])
    listing['make'] = words[1]
    listing['model'] = words[2]

    # cvclassics has no stock#/inventory ID; use the unique URL element
    listing['local_id'] = listing['listing_href'].split('/')[-1].replace('.html','')
    listing['stock_no'] = listing['local_id'] # no separate stock#

    # no real patterns to mine on the details page.
    # but hey, at least it has the price! (unlike the inventory page)
    pe = detail.find(text=re.compile('Asking Price:'))
    if pe != None:
        pe = pe.split(':')[-1]
    listing['price'] = regularize_price(pe)

    return True


# fj_parse_listing
#
def fj_parse_listing(listing, entry, detail):

    # get the short listing text from the inventory page
    listing['listing_text'] = entry.find(class_="entry-subheader blue").get_text()

    # pull the rest of the fields from the detail page
    # GEE TODO make a better splitter that understands multiword makes (e.g. Alfa Romeo)
    words = detail.find('title').get_text().split(" ",2) # pull out year & make; remaining string is model
    listing['model_year'] = int(words[0])
    listing['make'] = words[1]
    listing['model'] = words[2]

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
        return False

    # as with cvc, there is no useful tagging....
    # we just have to make the best of it

    # get the short listing text from the inventory page
    listing['listing_text'] = entry.find('h3').text.encode('ascii','ignore')

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
            words = detail.find('h1').text.split(" ", 2)
        else:
            words = entry.find('h2').text.split(" ", 2)
        listing['model_year'] = int(words[0])
        listing['make'] = words[1]
        listing['model'] = words[2]
    except ValueError:
        try:
            if detail:
                # GEE TODO HACKY HACKY HACKY
                words = listing['listing_href'].split('/')[-2] # trailing / in URL
                words.split("-", 2)
                listing['model_year'] = int(words[0])
                listing['make'] = words[1]
                listing['model'] = words[2]
            else:
                return False
        except ValueError:
            return False

    # cvclassics has no stock#/inventory ID; use the unique URL element
    listing['local_id'] = listing['listing_href'].split('/')[-1].replace('.html','')
    listing['stock_no'] = listing['local_id'] # no separate stock#

    # no real patterns to mine on the details page...

    return True


# specialty_parse_listing
#
def specialty_parse_listing(listing, entry, detail):

    # get the short listing text from the inventory page
    listing['listing_text'] = entry.find(class_='intro-text').get_text()

    # discarded way to pull the source ID from the inventory page...
    # listing['local_id'] = str(entry.find(class_='stockno').get_text()).split()[-1]

    # pull the rest of the fields from the detail page
    # NOTES:
    # most elements are coming from a table with rows of the form:
    # <tr>
    #   <td><h3>Stock: </h3></td>
    #   <td>F13011</td>
    # </tr>
    # the first td has an h3 with the fieldname, initcaps with colon and a trailing space
    # the second td has the value (raw, not in an h3)
    # the h3 in there seems to toast next_sibling/next_element, but find_next_sibling('td') works
    
    listing['model_year'] = detail.find('td',text='Year: ').find_next_sibling('td').text 
    listing['make'] = detail.find('td',text='Make: ').find_next_sibling('td').text 
    listing['model'] = detail.find('td',text='Model: ').find_next_sibling('td').text
    listing['local_id'] = detail.find('td',text='Stock: ').find_next_sibling('td').text
    listing['stock_no'] = listing['local_id'] # no separate stock#

    # price is different:
    price_string = str(detail.find('h2').text).split(':')[1]
    listing['price'] = regularize_price(price_string)

    return True

# ============================================================================
# PRIMARY IMPORT METHODS
# ============================================================================

# pull_dealer_inventory()
#
# pulls inventory from common dealer sites as directed
#
# returns a list of listings dicts
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

    # the 300 parm should mean that all car listings are in one page & there
    # will be a next page link; our standard pagination loop should cope

    try:
        full_inv_url = urlparse.urljoin(dealer['base_url'], dealer['inventory_url'])
        logging.info('Pulling ' + dealer['textid'] + ' inventory from ' + full_inv_url + '....')
        req = urllib2.Request(full_inv_url, headers=hdrs)
        page = urllib2.urlopen(req)
    except urllib2.HTTPError as error:
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
        # each listing is in a <li> block that contains a <class="carid"> entry

        listings = dealer['extract_car_list_func'](soup)
        print('Number of car listings found: {}'.format(len(listings)))
        for item in listings:
            listing = {} # build a listing dict for this car

            # for some sites the full entry is actually a parent or sibling
            # or similar permutation of the list item we just grabbed
            entry = dealer['listing_from_list_item_func'](item)

            # try standard grabs; then call the dealer-specific method for
            # overrides & improvements
            listing['source_textid'] = dealer['textid']
            listing['pic_href'] = urlparse.urljoin(full_inv_url,str(entry.find('img').attrs['src']))

            # often the first (likely only) href in the block is the detail page
            detail = None # if we don't find one, we can pass down this None
            detail_url_elt = entry.find('a')
            if detail_url_elt != None:
                detail_url = detail_url_elt.get('href')
            else:
                # or alternately, there may be an onclick property we can grab?
                # the onclick property could be on entry or a subentity
                detail_url_attr = entry.attrs['onclick']
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
                scheme = urlparse.urlsplit(detail_url).scheme
                # oops -- apparent bug, or at least difference in practical effect
                # between safari and urlsplit. urlsplit doesn't recognize
                # tel:8005551212
                # it recognizes some variants -- basically it expects at least one '/'
                # somewhere. Without that, it returns None as the scheme. So:
                if (detail_url[:4] == 'tel:'):
                    scheme = 'tel'
                if (scheme and scheme != 'http' and scheme != 'https'):
                    # uh... point back to the main inventory page but DON'T
                    # load it again -- probably need some flag for this
                    listing['listing_href'] = full_inv_url
                else:
                    listing['listing_href'] = urlparse.urljoin(full_inv_url, detail_url)
                    logging.debug('detail page: ' + listing['listing_href'])
                    req = urllib2.Request(listing['listing_href'], headers=hdrs)
                    detail_page = urllib2.urlopen(req)
                    detail = BeautifulSoup(detail_page)

            # see if the listing is marked as sold?
            # GEE TODO improve this; using uppercase intentionally as a cheat
            if (entry.find(text=re.compile('SOLD')) or
                detail and detail.find(text=re.compile('SOLD'))):
                listing['status'] = 'S' # 'S' -> Sold
            elif (entry.find(text=re.compile('SALE PENDING')) or
                detail and detail.find(text=re.compile('SALE PENDING'))):
                listing['status'] = 'P' # 'P' -> Sale Pending
            else:
                listing['status'] = 'F' # 'F' -> For Sale

            # call the dealer-specific method
            # GEE TODO need to define some sort of error-handling protocol...
            ok = dealer['parse_listing_func'](listing, entry, detail)
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
            full_inv_url = urlparse.urljoin(full_inv_url, next_ref.get('href').encode('ascii','ignore'))
            req = urllib2.Request(full_inv_url, headers=hdrs)
            page = urllib2.urlopen(req)
            # GEE TODO - check that this is really a listings page and has
            # different listings, ie detect and avoid infinite loops
        else:
            break
        # END LOOP over all inventory pages

    logging.info('Loaded ' + str(len(list_of_listings)) + ' cars from ' + dealer['textid'])
    return list_of_listings


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
# note: returns the database ID of the listing (if it succeeded -- will raise exception otherwise, I guess)
#
def db_insert_or_update_listing(con, listing):
    db_listing = {}
    c = con.cursor(db.cursors.DictCursor) # get result as a dict rather than a list for prettier interaction
    rows = c.execute("""select * from listing where source_textid= %s and local_id = %s""", (listing['source_textid'], listing['local_id'],))
    if rows == 0:
        # no matching listing -- insert
        ins = con.cursor(db.cursors.DictCursor)
        ins.execute(
            """insert into listing
(status, model_year, make, model, price, listing_text, pic_href, listing_href, source_textid, local_id, stock_no, listing_date, removal_date, last_update) values
(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)""",
            (listing['status'],listing['model_year'],listing['make'],listing['model'],listing['price'],listing['listing_text'],listing['pic_href'],listing['listing_href'],listing['source_textid'],listing['local_id'],listing['stock_no'],))

        # re-execute the same fetch which will now grab the new record
        c2 = con.cursor(db.cursors.DictCursor)
        c2.execute("""select * from listing where source_textid= %s and local_id = %s""", (listing['source_textid'], listing['local_id'],))
        db_listing = c2.fetchone()

        logging.debug("inserted record id={}: {} {} {}".format(db_listing['id'],listing['model_year'],listing['make'], listing['model']))

    elif rows == 1:
        # matching listing already -- do we need to update?
        # GEE TODO full update check; for now just checking for price change
        db_listing = c.fetchone()
        if listing['price'] != db_listing['price']:
            up = con.cursor(db.cursors.DictCursor)
            up.execute("""update listing set price = %s, last_update = CURRENT_TIMESTAMP where id = %s""", (listing['price'],db_listing['id']))
        # else listing is up to date; no update required
        logging.debug("found (updated) record id=%d: %s %s %s", (db_listing['id'],listing['model_year'],listing['make'], listing['model']))
    else:
        # WTF - multiple rows?
        print "YIKES! Multiple matching rows already in the listing table?"

    # if we get here, we succeeded... I assume
    return db_listing['id']


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

    # GEE debug
    print("wrote listing id {} ({} {} {}) to file {}".format(listing['id'], listing['model_year'],listing['make'], listing['model'], pathname))
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
    'base_url' : 'http://carbuffs.com',
    'inventory_url' : '/inventory',
    'extract_car_list_func' : lambda s: s.find_all(class_='car-cont'),
    'listing_from_list_item_func' : lambda s: s,
    'parse_listing_func' : carbuffs_parse_listing
    }
cvclassics = {
    'textid' : 'cvclassics',
    'base_url' : 'http://www.centralvalleyclassics.com',
    'inventory_url' : '/cars/carsfs.html',
    'extract_car_list_func' : lambda s: s.find_all('img',alt=re.compile('Click')), # Yuck!
    'listing_from_list_item_func' : lambda s: s.parent.parent.parent, # Yuck again!
    'parse_listing_func' : cvclassics_parse_listing
    }
fj = {
    'textid' : 'fj',
    'base_url' : 'http://www.fantasyjunction.com',
    'inventory_url' : '/inventory',
    'extract_car_list_func' : lambda s: s.find_all(class_='list-entry pkg list-entry-link'),
    'listing_from_list_item_func' : lambda s: s,
    'parse_listing_func' : fj_parse_listing
    }
lcc = {
    'textid' : 'lcc',
    'base_url' : 'http://www.leftcoastclassics.com',
    'inventory_url' : '/LCCofferings.html', # not sure why URLs are not parallel?
    'extract_car_list_func' : lambda s: s.find_all('h3'), # Yuck!
    'listing_from_list_item_func' : lambda s: s.parent.parent, # h3 under td under tr
    'parse_listing_func' : lc_parse_listing # shared parser for the 2 sets of cars
    }
lce = {
    'textid' : 'lce',
    'base_url' : 'http://www.leftcoastexotics.com',
    'inventory_url' : '/cars-for-sale.html', # not sure why URLs are not parallel?
    'extract_car_list_func' : lambda s: s.find_all('h3'), # Yuck!
    'listing_from_list_item_func' : lambda s: s.parent.parent, # h3 under td under tr
    'parse_listing_func' : lc_parse_listing # shared parser for the 2 sets of cars
    }
specialty = {
    'textid' : 'specialty',
    'base_url' : 'http://www.specialtysales.com',
    'inventory_url' : '/inventory?per_page=300',
    'extract_car_list_func' : lambda s: s.find_all(class_='carid'),
    'listing_from_list_item_func' : lambda s: s.parent,
    'parse_listing_func' : specialty_parse_listing
    }

# GEE TODO investigate using OrderedDict
dealers = {
    'carbuffs' : carbuffs,
    'cvclassics' : cvclassics,
    'fj' : fj,
    'lcc' : lcc,
    'lce' : lce,
    'specialty' : specialty,
    }

# ============================================================================
# MAIN
# ============================================================================

# check args to decide what to do; default is nothing (except printing usage)
write_to_db = False
write_to_file = False
requested_sites = False
log_level = 'INFO'
con = False # declare scope of db connection

# GEE TODO switch to proper pythonic arg processing (argparse)
# check for args tellings us what to do with what we retrieve
for arg in sys.argv:
    if arg == '-db':
        write_to_db = True
    if arg == '-file':
        write_to_file = True
    if arg.startswith('--log_level='):
        log_level = arg.partition('=')[2]

# set up logging
logging.basicConfig(level=log_level.upper())

# then take a second pass through the args and pull in the listings that are requested
for arg in sys.argv:
    listings = []

    if arg == 'test':
        requested_sites=True
        listings = test_inventory()
    if arg in sorted(dealers.keys()):
        requested_sites=True
        listings = pull_dealer_inventory(dealers[arg])
    if arg == 'norcal':
        requested_sites=True
        listings = all_norcal_inventory()
    # add if statement for each additional site here

    if write_to_db:
        con = db.connect('localhost', 'carsdbuser', 'car4U', 'carsdb')
        # GEE TODO: test db connection success here (since we are not just doing 'with con:' as db usage is conditional)
        # with con:

    for listing in listings:
        if write_to_db:
            id = db_insert_or_update_listing(con, listing)
        else: # temporary -- use something other than db id as filename
            id = listing['local_id']
        if write_to_file:
            listing['id'] = id # put it in the hash
            text_store_listing('/tmp/listings', listing)
    if write_to_db:
        con.commit()

if not requested_sites:
    print "Usage: [-db] [-file] [--log_level=FOO] site site site..."
    print "... where valid sites are: test, norcal, " + ", ".join(dealers.keys())
