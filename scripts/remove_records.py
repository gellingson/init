#!/usr/bin/env python3
#
# remove_records.py
#
# removes old listings (markes them status 'R')
#

from elasticsearch import Elasticsearch
import elasticsearch.exceptions
import pymysql as db

# OGL modules used
from inventory.importer import *

def remove_old_records_for_source(con, es, source_textid, daysold):
    count = 0
    logging.info("De-indexing records from %s: that are %s days old",
                 source_textid, daysold)
    # cursor type SSDictCursor to get result as a dict rather than a list for
    # prettier interaction, and store result set server side to save memory
    c = con.cursor(db.cursors.SSDictCursor)
    c.execute("select * from listing"
              " where status = 'F'"
              "   and source_textid = %s"
              "   and last_update < date_sub(curdate(), INTERVAL %s DAY)",
              (source_textid, daysold))
    db_listing = c.fetchone()
    while db_listing is not None:
        try:
            index_resp = es.delete(index="carbyr-index",
                                   doc_type="listing-type",
                                   id=db_listing['id'])
        except NotFoundError as err:
            pass
        count += 1
        if (count % 1000) == 0:
            print(str(datetime.datetime.now()), "Records processed:", count)
        db_listing = c.fetchone()
    print(str(datetime.datetime.now()), "Total records processed:", count)
    logging.info('Marking db records')
    c = con.cursor(db.cursors.Cursor)
    r = c.execute("update listing set status = 'R', removal_date = now(), last_update = now()"
                  " where status = 'F'"
                  "   and source_textid = %s"
                  "   and last_update < date_sub(curdate(), INTERVAL %s DAY)",
                  (source_textid, daysold))
    logging.info('Marked %s records', str(r))
    con.commit()
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
    es = Elasticsearch()
    con = None
    try:
        con = db.connect(os.environ['OGL_DB_HOST'],
                         os.environ['OGL_DB_USERACCOUNT'],
                         os.environ['OGL_DB_USERACCOUNT_PASSWORD'],
                         os.environ['OGL_DB'],
                         charset='utf8')
    except KeyError:
        print("Please set environment variables for OGL DB connectivity and rerun.")
        sys.exit(1)

    # GEE TODO: test session success here

    # check that we have a useful # for daysold
    daysold = int(args.daysold)
    if daysold < 2 or daysold > 30:
        print("Are you sure you know what you are doing? :-)")
        sys.exit(1)

    # now do it
    for source in args.sources:
        remove_old_records_for_source(con, es, source, daysold)
    return True
    
if __name__ == "__main__":
    status = main()
    sys.exit(status)
