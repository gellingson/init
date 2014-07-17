#!/opt/local/bin/python
#
# tempindex.pu
#
# this creates a temporary listings page with all the car listings
# (pulls from db, not files)

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

# set up logging
logging.basicConfig(level='DEBUG')

con = db.connect('localhost', 'carsdbuser', 'car4U', 'carsdb')
outf = open('/tmp/listings/index.html', 'w')
listing_fmt = """<div><a href='{0}'><img src='{1}'><b>{2} {3} {4}</b> {5}'</a></div>\n"""
    
db_listing = {}
c = con.cursor(db.cursors.DictCursor) # get result as a dict rather than a list for prettier interaction
rows = c.execute("""select * from listing where status = 'F'""")
rows_read = 0
while rows_read < rows:
    db_listing = c.fetchone()
    outf.write(listing_fmt.format(db_listing['listing_href'],
                                  db_listing['pic_href'],
                                  db_listing['model_year'],
                                  db_listing['make'],
                                  db_listing['model'],
                                  db_listing['listing_text']))
    rows_read = rows_read + 1
outf.write('<div><div>{0} cars total in db.'.format(rows))
