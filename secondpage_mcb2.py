# test script to play with beautiful soup 4

import re
import urllib2
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
    

# get a page of car listings; # at end gives # to pull
page = urllib2.urlopen('http://www.specialtysales.com/inventory?per_page=1')

# soupify it
soup = BeautifulSoup(page)

# get all the relative URLs to go to next pages
carids = (soup.find_all(class_='carid'))
carids_length = len(carids)

# now go through those next pages & pull the relevant information

# get each car listing's id (& related URL)
vid=[]
for i in range(carids_length):
	vid.append(carids[i]['value'])

# iterate over every listing & pull info from each page
for i in range(len(vid)):
	URL='http://www.specialtysales.com/vehicles/'+vid[i]
	page = urllib2.urlopen(URL)
	soup = BeautifulSoup(page)
	
	test_listing = {}
	listing ={}
	
	test_listing['status'] = 'F';
	test_listing['model_year'] = '1955';    
	test_listing['make'] = 'Ford';
	listing['model'] = soup.h1.string.partition(' ')[0]
	#listing['model'] = soup.h1.string
	listing['price'] = str(re.sub('[^\d\.]','',soup.find('h2').get_text()))
	test_listing['listing_text'] = 'This is a fake thunderbird listing'
	test_listing['pic_href'] = 'http://www.google.com'
	test_listing['listing_href'] = 'http://www.yahoo.com'
    test_listing['source'] = 'dbtest'
    test_listing['source_id'] = '1'
    test_listing['stock_no'] = 'stock1234'
    tag = soup.find_all('td')
    print tag[1]," ",type(tag)

    #words = listing.find('h2').get_text().split(" ",2) # pull out year & make; remaining string is model
    #year = int(words[0])
		


"""    test_listing = {}
    test_listing['listing_text'] = 'This is a fake thunderbird listing';
    test_listing['pic_href'] = 'http://www.google.com';
    test_listing['listing_href'] = 'http://www.yahoo.com';
    test_listing['source'] = 'dbtest';
    test_listing['source_id'] = '1';
    test_listing['stock_no'] = 'stock1234';
"""
