#!/usr/bin/env python3
#
# fix_records.py
#
# utility script to pull an arbirary set of records from the db,
# take an arbirary action upon them, then reindex them
#
# usage: edit the query where clause, edit the visit() method, then run
#

# builtin modules used
import argparse
import logging
import sys
import os

# third party modules used
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError, TransportError
import pymysql as db

# OGL modules used
#from inventory.importer import *


# query: this determines what listings will be visited
#
# *** EDIT WHERE CLAUSE HERE ***
#
query = """select * from listing
where status = 'F' and source_textid = 'autod'"""


# visit(): this determines what we will do to each listing
#
# by convention, returning None means no need to update es
#
def visit_record(con, listing):
    #
    # *** EDIT METHOD CONTENTS HERE ***
    #
#    # 2014-12-31: fix carsd pic hrefs:
#    if '&width' not in listing['pic_href']:
#        return None # OK, do nothing
#    listing['pic_href'] = listing['pic_href'].split('&width')[0]
#    up = con.cursor(db.cursors.DictCursor);
#    up.execute("""update listing set pic_href = %s where id = %s""",
#               (listing['pic_href'], listing['id']))
#    return listing

#    # 2014-12-31: fix autod pic hrefs:
#    if '/scaler/80/60/' not in listing['pic_href']:
#        return None  # OK, do nothing
#    listing['pic_href'] = listing['pic_href'].replace('/scaler/80/60/',
#                                                      '/scaler/544/408/')
#    up = con.cursor(db.cursors.DictCursor);
#    up.execute("""update listing set pic_href = %s where id = %s""",
#               (listing['pic_href'], listing['id']))
#    return listing

    # 2014-12-31: remove autod hrefs with bogus links
    if 'listingId=' in listing['listing_href']:
        return None  # OK, do nothing
    listing['status'] = 'X'
    up = con.cursor(db.cursors.DictCursor);
    up.execute("""update listing set listing_href = %s where id = %s""",
               (listing['listing_href'], listing['id']))
    return listing


def fetch_visit_index_all(readcon, writecon, es):
    read_count = 0
    write_count = 0
    logging.info("Start visiting records....")

    # cursor type SSDictCursor to get result as a dict rather than a list for
    # prettier interaction, and store result set server side to save memory
    c = readcon.cursor(db.cursors.SSDictCursor)
    c.execute(query)
    db_listing = c.fetchone()
    while db_listing is not None:
        read_count += 1
        db_listing = visit_record(writecon, db_listing)
        if db_listing:
            try:
                if db_listing['status'] == 'F':
                    resp = es.index(index="carbyr-index",
                                    doc_type="listing-type",
                                    id=db_listing['id'], body=db_listing)
                else:
                    resp = es.delete(index="carbyr-index",
                                     doc_type="listing-type",
                                     id=db_listing['id'])
            except (NotFoundError, TransportError) as err:
                pass  # elasticsearch will have already emitted a log message
            write_count += 1
            if (write_count % 1000) == 0:
                # commit on the write connection
                # if this fails, db may trail es. This is safer than the
                # converse. Just rerun & things should get into sync
                writecon.commit()
                logging.info("Records checked: %d", read_count)
                logging.info("Records touched: %d", write_count)
        db_listing = c.fetchone()
    writecon.commit()
    logging.info("Total records checked: %d", read_count)
    logging.info("Total records touched: %d", write_count)
    return


def process_command_line():
    parser = argparse.ArgumentParser(description='Imports car listings')
    parser.add_argument('--log_level', default='INFO',
                        choices=('DEBUG','INFO','WARNING','ERROR', 'CRITICAL'),
                        help='set the logging level')
    parser.add_argument('--daysold', default='7',
                        help='how many days old (and older) should be removed')
    parser.add_argument('sources', nargs='*', help='the source(s) to take action on')

    return parser.parse_args()


def main():
    args = process_command_line()

    # start logging
    logging.basicConfig(level=args.log_level.upper(),format='%(asctime)s %(message)s')

    # establish connections to required services (db & es)
    # 2 db connections: readcon for fetch & writecon for interim commits
    es = Elasticsearch()
    readcon = None
    try:
        readcon = db.connect(os.environ['OGL_DB_HOST'],
                             os.environ['OGL_DB_USERACCOUNT'],
                             os.environ['OGL_DB_USERACCOUNT_PASSWORD'],
                             os.environ['OGL_DB'],
                             charset='utf8')
    except KeyError:
        print("Please set environment variables for OGL DB connectivity and rerun.")
        sys.exit(1)
    writecon = None
    try:
        writecon = db.connect(os.environ['OGL_DB_HOST'],
                              os.environ['OGL_DB_USERACCOUNT'],
                              os.environ['OGL_DB_USERACCOUNT_PASSWORD'],
                              os.environ['OGL_DB'],
                              charset='utf8')
    except KeyError:
        print("Please set environment variables for OGL DB connectivity and rerun.")
        sys.exit(1)

    # now do it
    fetch_visit_index_all(readcon, writecon, es)
    return True
    
if __name__ == "__main__":
    status = main()
    sys.exit(status)

