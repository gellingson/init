
# test script to play with mysql

import os
import errno
import json
import MySQLdb as db

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

        c.execute() # re-execute the same fetch which will now grab the new record
        db_listing = c.fetchone()
    elif (rows == 1):
        # matching listing already -- do we need to update?
        # GEE TODO full update check; for now just checking for price change
        db_listing = c.fetchone()
        if (listing['price'] != db_listing['price']):
            up = con.cursor(db.cursors.DictCursor);
            up.execute("""update listing set price = %s, last_update = CURRENT_TIMESTAMP where id = %s""", (listing['price'],db_listing['id']))
        # else listing is up to date; no update required
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


def text_store_listing(listing):
    list_dir = '/tmp/listings'
    # store car listing file in subdir by source (not the best, heh -- temporary, should really be some more reliable sharding mechanism)
    # and with the id (our internal id) as the filename root
    make_sure_path_exists(list_dir + '/' + listing['source'])
    list_file=open(list_dir + '/' + listing['source'] + '/' + str(listing['id']) + '.html',"w")
    list_file.write(json.dumps(listing))
    list_file.close()
    return True


con = db.connect('localhost', 'carsdbuser', 'car4U', 'carsdb')

with con:

    # create a bogus listing since this is a test script :)
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

    id = db_insert_or_update_listing(con, test_listing)
    test_listing['id'] = id
    text_store_listing(test_listing)
