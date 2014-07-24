#!/usr/local/bin/python3
#
# tempindex.pu
#
# this creates a temporary listings page with all the car listings
# (pulls from db, not files)

import sys
import re
import json
import os
import errno
import logging
import pymysql as db
from bs4 import BeautifulSoup

# set up logging
logging.basicConfig(level='DEBUG')

con = db.connect('localhost', 'carsdbuser', 'car4U', 'carsdb', charset='utf8')
outf = open('/tmp/listings/index.html', 'w')
outf.write("""<table>""")
listing_fmt = """<tr><td><a href='{0}'><img src='{1}' width='200'></a></td><td><a href='{0}'><b>{2} {3} {4}</b></a></td><td><a href='{0}'>{5}</a></td><td><a href='{0}'>{6}</a></td></tr>\n"""
    
db_listing = {}
c = con.cursor(db.cursors.DictCursor) # get result as a dict rather than a list for prettier interaction
rows = c.execute("""select * from listing where status = 'F' order by model_year, make, model""")
rows_read = 0
while rows_read < rows:
    db_listing = c.fetchone()
    outf.write(listing_fmt.format(db_listing['listing_href'],
                                  db_listing['pic_href'],
                                  db_listing['model_year'],
                                  db_listing['make'],
                                  db_listing['model'],
                                  db_listing['price'] if db_listing['price'] > 0 else 'Price upon request',
                                  db_listing['listing_text']))
    rows_read = rows_read + 1
outf.write('</table>')
outf.write('<div><div>{0} cars total in db.'.format(rows))
