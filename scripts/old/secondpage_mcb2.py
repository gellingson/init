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

# sloppy, sloppy, sloppy but functional
def removetd(tag_object):
	tag_str=str(tag_object)    
	tag_str = tag_str.replace('<td>','')
	tag_str = tag_str.replace('</td>','')
	return tag_str

# get a page of car listings; # at end gives # to pull
page = urllib2.urlopen('http://www.specialtysales.com/inventory?per_page=800')

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
	
	listing['make'] = soup.h1.string.partition(' ')[0]
	listing['model'] = soup.h1.string.partition(' ')[2]
	listing['price'] = str(re.sub('[^\d\.]','',soup.find('h2').get_text()))

	test_listing['pic_href'] = 'http://www.google.com'
	listing['listing_href'] = URL
	listing['stock_no'] = 'xxx' #position 1
	
	tag = soup.find_all('td')
	#for t in range(len(tag)):
	#	print t," ",tag[t]
	listing['price']=removetd(tag[3])
	listing['odometer']=removetd(tag[9])
	listing['engine']=removetd(tag[11])
	listing['transmission']=removetd(tag[13])
	listing['VIN']=removetd(tag[15])
	if listing['price'] > 0:
		listing['status'] = 'F'
	print 'make/model ',listing['make'],' ** ',listing['model']