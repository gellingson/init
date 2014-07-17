#!/opt/local/bin/python
#
# ca_dealerships.py

"""
This pulls california dealership info from the CA DMV. For now just dumps to a csv file.
"""

import sys
import argparse
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

dmvurl = 'http://www.dmv.ca.gov/wasapp/olinq2/'
search = 'search.do'

# GEE TODO refine this: what headers do we want to send?
# some sites don't want to offer up inventory without any headers.
# Not sure why, but let's impersonate some real browser and such to get through
hdrs = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.12\
71.64 Safari/537.11',
                      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                      'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
                      'Accept-Encoding': 'none',
              'Accept-Language': 'en-US,en;q=0.8',
                      'Connection': 'keep-alive'}

# ============================================================================
# UTILITY METHODS
# ============================================================================

def scrape_dealer_page(page):
    dealer = {}
    s = BeautifulSoup(page)
    # GEE TODO parse soup into dealer hash
    return dealer

def scrape_list_of_dealers_page(page):
    dealer_urls = []
    soup = BeautifulSoup(page)
    dealers = soup.find_all('div',id=re.compile('100'))
    for d in dealers:
        # GEE TODO question: do we want any other info from the main page (dealer name, alt name, zip, city?)
        relative_href = d.a.get('href')
        logging.debug('Dealer URL: ' + relative_href)
        dealer_urls.append(urlparse.urljoin(dmvurl, relative_href))
    logging.info('Found %d dealer URLs', (len(dealer_urls)))
    return dealer_urls

def process_list_of_dealer_urls(dealer_urls):
    dealers = []
    for url in dealer_urls:
        try:
            logging.info('Pulling URL ' + url)
            req = urllib2.Request(url, headers=hdrs)
            page = urllib2.urlopen(req)
        except urllib2.HTTPError as error:
            logging.error('Unable to load dealer info page ' + url + ': HTTP ' + str(error.code) + ' ' + error.reason)
        dealer = scrape_dealer_page(page)
        dealers.append(dealer)
    return dealers

def process_command_line():
    """
    """

    # initialize the parser object:
    parser = argparse.ArgumentParser(description='Imports CA DMV dealership info')
    parser.add_argument('-t', '--test', dest='testmode', action='store_true',
                        help='run some tests on preset (local) files')
#    parser.add_argument('--testfile', dest='testfile',
#                        help='file to run tests from')    
#    parser.add_argument('--test', dest='testmode', action='store_const',
#                        const=True, default=False,
#                        help='run some tests on preset (local) files')

    return parser.parse_args()

# ============================================================================
# MAIN
# ============================================================================

def main(argv=None):

    args = process_command_line()
    logging.basicConfig(level='DEBUG')
    if args.testmode:
        with open ("/Users/gee/Downloads/da_dmv_95112_dealers.html", "r") as myfile:
            data=myfile.read().replace('\n', '')
            scrape_list_of_dealers_page(data)
    else:
            # hardcoding for test files - TODO GEE replace with arg processing
        logging.error('oops -- only supported mode is test')

    return 0        # success

if __name__ == '__main__':
    status = main()
    sys.exit(status)
