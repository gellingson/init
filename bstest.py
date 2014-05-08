# test script to play with beautiful soup 4

import sys
import re
import json
import urllib2
import os
import errno
import MySQLdb as db
from bs4 import BeautifulSoup

# regularize methods will take a string input that may be "messy" or vary a bit
# from site to site and regularize/standardize it

# take a price string, strip out any dollar signs and commas, convert to an int
# TODO: this is US-format-only right now & doesn't handle decimals or other garbage yet

def regularize_price(price_string):
    try:
        price = int(re.sub('[\$,]', '', price_string))
    except ValueError:
        price = -1
    return price

# test_inventory()
#
# creates a bogus listing since this is a test script :)
#
# returns a list containing that one bogus listing
#
def test_inventory():
    # 
    test_listing = {}
    test_listing['status'] = 'F';
    test_listing['model_year'] = '1955';
    test_listing['make'] = 'Ford';
    test_listing['model'] = 'Thunderbird';
    test_listing['price'] = '25000';
    test_listing['listing_text'] = 'This is a fake thunderbird listing';
    test_listing['pic_href'] = 'http://www.google.com';
    test_listing['listing_href'] = 'http://www.yahoo.com';
    test_listing['source'] = 'dbtest';
    test_listing['source_id'] = '1';
    test_listing['stock_no'] = 'stock1234';

    # GEE debug
    print("item" + json.dumps(test_listing))

    # return a list containing this one listing dict
    list_of_listings = [test_listing]
    return list_of_listings


# fantasyjunction_inventory()
#
# Pull inventory from fantasyjunction.com
#
# returns a list of listings dicts
#
# see sample inventory and detail pages:
# samples/fantasy_junction_inventory_page.html
# samples/fantasy_junction_detail_page.html
#
def fantasyjunction_inventory():

    list_of_listings = []

    # get a page of car listings
    # GEE TODO get full listing in one page or deal with pagination (now just gets first page)
    page = urllib2.urlopen('http://www.fantasyjunction.com/inventory');

    # soupify it
    soup = BeautifulSoup(page)

    # extract all the listings
    # each listing is in a class="list-entry pkg list-entry-link"
    # note: also surrounded by CAR ENTRY START/END comments but that seems messier

    listings = soup.find_all(class_='list-entry pkg list-entry-link')
    print('Number of car listings found: {}'.format(len(listings))) # should be 20 max by default
    for entry in listings:
        listing = {} # build a listing dict for this car

        # get the smaller img from the inventory page, not the big pics on the detail page
        # GEE TODO make a generalized relative URL->absolute URL handler
        listing['pic_href'] = "http://fantasyjunction.com" + entry.find('img').get_text()

        # get the short listing text from the inventory page as well
        listing['listing_text'] = entry.find(class_="entry-subheader blue").get_text()

        # get detail page
        listing['listing_href'] = "http://fantasyjunction.com" + entry.find('a').get('href') # detail page URL is first/only link in each listing

        # load it
        detail_page = urllib2.urlopen(listing['listing_href'])
        detail_soup = BeautifulSoup(detail_page)

        # pull the rest of the fields from the detail page

        words = detail_soup.find('title').get_text().split(" ",2) # pull out year & make; remaining string is model
        listing['model_year'] = int(words[0])
        listing['make'] = words[1]
        listing['model'] = words[2]
        # GEE TODO make a better splitter that understands multiword makes (e.g. Alfa Romeo)

        listing['source'] = 'fantasyjunction'
        listing['source_id'] = detail_soup.find(id="ContactCarId")['value']
        listing['stock_no'] = listing['source_id'] # no separate stock#

        listing['status'] = 'F'

        # many interesting items are in an "alpha-inner-bottom' div, but for now just grab price
        # tabular format with labels & values in two td elements, e.g.:
        # <tr>
        # <td class="car-detail-name">Price</td>
        # <td class="car-detail-value"> $42,500</td>
        # </tr>
        # GEE note: I can't get the regular parent/child nav to work reliably on these elts
        # E.g. using .parent or .parent() on the td gives me a list of tds, not the tr ?!
        # Not sure why... but the find_parent() seems to work even though .parent() goes funky
        elt = detail_soup.find(id="alpha-inner-bottom")
        price_tr = elt.find("td", text="Price").find_parent("tr")
        price_string = price_tr.find("td", class_="car-detail-value").get_text()
        listing['price'] = regularize_price(price_string)

        # GEE debug
        print("item" + json.dumps(listing))

        list_of_listings.append(listing)

    return list_of_listings

# note: returns the database ID of the listing (if it succeeded -- will raise exception otherwise, I guess)
def db_insert_or_update_listing(con, listing):
    db_listing = {}
    c = con.cursor(db.cursors.DictCursor) # get result as a dict rather than a list for prettier interaction
    rows = c.execute("""select * from listing where source= %s and source_id = %s""", (listing['source'], listing['source_id'],))
    if (rows == 0):
        # no matching listing -- insert
        ins = con.cursor(db.cursors.DictCursor);
        ins.execute(
            """insert into listing
(status, model_year, make, model, price, listing_text, pic_href, listing_href, source, source_id, stock_no, listing_date, removal_date, last_update) values
(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)""",
            (listing['status'],listing['model_year'],listing['make'],listing['model'],listing['price'],listing['listing_text'],listing['pic_href'],listing['listing_href'],listing['source'],listing['source_id'],listing['stock_no'],));

        # re-execute the same fetch which will now grab the new record
        c2 = con.cursor(db.cursors.DictCursor);
        c2.execute("""select * from listing where source= %s and source_id = %s""", (listing['source'], listing['source_id'],))
        db_listing = c2.fetchone()

        # GEE debug
        print("item" + str(db_listing['id']) + db_listing['make'])
        print("inserted record id={}: {} {} {}".format(db_listing['id'],listing['model_year'],listing['make'], listing['model']))

    elif (rows == 1):
        # matching listing already -- do we need to update?
        # GEE TODO full update check; for now just checking for price change
        db_listing = c.fetchone()
        if (listing['price'] != db_listing['price']):
            up = con.cursor(db.cursors.DictCursor);
            up.execute("""update listing set price = %s, last_update = CURRENT_TIMESTAMP where id = %s""", (listing['price'],db_listing['id']))
        # else listing is up to date; no update required
        print("updated record id=%d: %s %s %s", (db_listing['id'],listing['model_year'],listing['make'], listing['model']))
    else:
        # WTF - multiple rows?
        print "YIKES! Multiple matching rows already in the listing table?"

    # if we get here, we succeeded... I assume
    return db_listing['id']


def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def text_store_listing(list_dir, listing):
    # store car listing file in subdir by source (not the best, heh -- temporary, should really be some more reliable sharding mechanism)
    # and with the id (our internal id) as the filename root
    make_sure_path_exists(list_dir + '/' + listing['source'])
    pathname=str(list_dir + '/' + listing['source'] + '/' + str(listing['id']) + '.html')
    list_file=open(pathname,"w")
    list_file.write(json.dumps(listing))
    list_file.close()

    # GEE debug
    print("wrote listing id {} ({} {} {}) to file {}".format(listing['id'], listing['model_year'],listing['make'], listing['model'], pathname))
    return True


# main

# check args to decide what to do; default is nothing (except printing usage)
write_to_db = False
write_to_file = False
requested_sites = False

# check for args tellings us what to do with what we retrieve
for arg in sys.argv:
    if arg == "-db":
        write_to_db = True
    if arg == "-file":
        write_to_file = True

# then take a second pass through the args and pull in the listings that are requested
for arg in sys.argv:
    listings = []

    if arg == "test":
        requested_sites=True;
        listings = test_inventory();
    if arg == "fj":
        requested_sites=True;
        listings = fantasyjunction_inventory();
    # add if statement for each additional site here

    for listing in listings:
        if write_to_db:
            con = db.connect('localhost', 'carsdbuser', 'car4U', 'carsdb')
            with con:
                id = db_insert_or_update_listing(con, listing)
        else: # temporary -- use something other than db id as filename
            id = listing['source_id']
        if write_to_file:
            listing['id'] = id # put it in the hash
            text_store_listing("/tmp/listings", listing)

if not requested_sites:
    print "Usage: [-db] [-file] site site site..."
    print "... where valid sites are: test, fj"
