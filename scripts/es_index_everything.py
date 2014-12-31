#!/usr/bin/env python3
# this is a convenience script to index all the listings in the db
# (without having to go re-import them)
#
# note that this script also contains the correct index mapping, and
# will stamp that into the index as it is recreated.

# builtin modules used
import sys
import argparse
import datetime
import re
import json
import urllib.request, urllib.error, urllib.parse
import os
import errno
import logging

# third party modules used
from elasticsearch import Elasticsearch
import elasticsearch.exceptions
import pymysql as db

# our stuff

listing_type_map = {
    "properties": {
        "city": {
            "type" : "string"
        },
        "color": {
            "type": "string"
        },
        "id": {
            "type": "long"
        },
        "int_color": {
            "type": "string"
        },
        "last_update": {
            "format": "dateOptionalTime",
            "type": "date"
        },
        "lat": {
            "type": "double"
        },
        "listing_date": {
            "format": "dateOptionalTime",
            "type": "date"
        },
        "listing_href": {
            "type": "string"
        },
        "listing_text": {
            "type": "string"
        },
        "local_id": {
            "type": "string"
        },
        "location": {
            "type": "geo_point"
        },
        "location_text": {
            "type": "string"
        },
        "lon": {
            "type": "double"
        },
        "make": {
            "type": "string"
        },
        "mileage": {
            "type": "long"
        },
        "model": {
            "type": "string"
        },
        "model_year": {
            "type": "string"
        },
        "markers": {
            "type": "string"
        },
        "pic_href": {
            "type": "string"
        },
        "price": {
            "type": "long"
        },
        "removal_date": {
            "format": "dateOptionalTime",
            "type": "date"
        },
        "source": {
            "type" : "string"
        },
        "source_id": {
            "type": "long"
        },
        "source_textid": {
            "type": "string"
        },
        "source_type": {
            "type": "string"
        },
        "status": {
            "type": "string"
        },
        "stock_no": {
            "type": "string"
        },
        "tags": {
            "type": "string"
        },
        "vin": {
            "type": "string"
        },
        "zip": {
            "type": "string"
        },
    }
}

es = Elasticsearch()

logging.basicConfig(level='INFO')

es = Elasticsearch()

# retrieve the mappings of the existing index
#mapping_resp = es.indices.get_mapping(index="carbyr-index")
#print("original mapping:\n{}".format(json.dumps(mapping_resp, indent=2, sort_keys=True)))

try:
    es.indices.delete(index="carbyr-index")
except elasticsearch.exceptions.NotFoundError:
    logging.warning('Index not found while attempting to drop it')

index_resp = es.indices.create(index="carbyr-index",
                               body={"settings": {"number_of_shards" : 5},
                                     "mappings": {"listing-type": listing_type_map}})
print(index_resp)

# alternatively, we could just put the mapping into an existing index
#mapping_resp = es.indices.put_mapping(index='carbyr-index',doc_type='listing-type',body=listing_type_map)
#print("result:\n{}".format(json.dumps(mapping_resp, indent=2, sort_keys=True)))

mapping_resp = es.indices.get_mapping(index="carbyr-index")
print("new mapping:\n{}".format(json.dumps(mapping_resp, indent=2, sort_keys=True)))

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

count = 0
print(str(datetime.datetime.now()), "Records processed:", count)
c = con.cursor(db.cursors.SSDictCursor) # get result as a dict rather than a list for prettier interaction, and store result set server side
c.execute("""select * from listing where status = 'F'""")
db_listing = c.fetchone()
while db_listing is not None:
    if db_listing['lat'] and db_listing['lon']:
        db_listing['location'] = {'lat': db_listing['lat'], 'lon': db_listing['lon']}
        index_resp = es.index(index="carbyr-index",
                              doc_type="listing-type",
                              id=db_listing['id'],
                              body=db_listing)
        count += 1
        if (count % 1000) == 0:
            print(str(datetime.datetime.now()), "Records processed:", count)
    db_listing = c.fetchone()

# fetchmany doesn't work with SSDictCursor, unfortunately....
#result = c.fetchmany(size=1000)
#while result:
#    for db_listing in result:
#        if db_listing['lat'] and db_listing['lon']:
#            db_listing['location'] = {
#                'lat': db_listing['lat'], 'lon': db_listing['lon']}
#        index_resp = es.index(index="carbyr-index",
#                              doc_type="listing-type",
#                              id=db_listing['id'],
#                              body=db_listing)
#    result = c.fetchmany()
