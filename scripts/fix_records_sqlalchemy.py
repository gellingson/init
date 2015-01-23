#!/usr/bin/env python3
#
# fix_records_sqlalchemy.py
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
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound


# OGL modules used
from inventory.importer import *



# visit(): this determines what we will do to each listing
#
# by convention, returning None means no need to update es
#
def visit_record(listing):
    #
    # *** EDIT METHOD CONTENTS HERE ***
    #
    # 2015-01-08: apply new tagging
    before = listing.tags
    tagify(listing)
    after = listing.tags
    # heh, with tagging thisbefore/after test can yield false positives
    # based on reordered sequence of tags, but better than nothing
    if before != after:
        return listing
    return None


def fetch_visit_index_all(session, es):
    read_count = 0
    write_count = 0
    logging.info("Start visiting records....")

    #
    # *** EDIT SEARCH CRITERIA HERE ***
    #
    listings = session.query(Listing).filter_by(source_textid='autod',
                                                status='F').all()

    for listing in listings:
        read_count += 1
        l = visit_record(listing)
        if l:
            write_count += 1
            index_listing(es, listing)
#            try:
#                if l.status == 'F':
#                    
#                    resp = es.index(index="carbyr-index",
#                                    doc_type="listing-type",
#                                    id=l.id, body=dict(l))
#                else:
#                    resp = es.delete(index="carbyr-index",
#                                     doc_type="listing-type",
#                                     id=l.id)
#            except (NotFoundError, TransportError) as err:
#                pass  # elasticsearch will have already emitted a log message
    session.commit()
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
    es = Elasticsearch()
    session = None
    try:
        connect_str = 'mysql+pymysql://{}:{}@{}/{}?charset=utf8'
        sqla_db_string = connect_str.format(
            os.environ['OGL_DB_USERACCOUNT'],
            os.environ['OGL_DB_USERACCOUNT_PASSWORD'],
            os.environ['OGL_DB_HOST'],
            os.environ['OGL_DB']
        )
        engine = create_engine(sqla_db_string)
        Session = sessionmaker(bind=engine)
        session = Session()
    except KeyError:
        print("Please set environment variables for OGL DB connectivity and rerun.")
        sys.exit(1)

    load_refdata_cache(session)

    # now do it
    fetch_visit_index_all(session, es)
    return True
    
if __name__ == "__main__":
    status = main()
    sys.exit(status)

