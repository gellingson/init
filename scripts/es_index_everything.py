#!/usr/local/bin/python3
# this is a convenience script to index all the listings in the db (without having to go re-import them)

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
import pymysql as db

logging.basicConfig(level='INFO')

con = db.connect('localhost', 'carsdbuser', 'car4U', 'carsdb', charset='utf8')

es = Elasticsearch()
es.indices.delete(index="carbyr-index")

c = con.cursor(db.cursors.DictCursor) # get result as a dict rather than a list for prettier interaction
rows = c.execute("""select * from listing where status = 'F'""")
logging.info('found {} rows'.format(str(rows)))
for db_listing in c.fetchall():
    index_resp = es.index(index="carbyr-index", doc_type="listing-type", id=db_listing['id'], body=db_listing)
