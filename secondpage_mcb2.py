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
    

# get a page of car listings
page = urllib2.urlopen('http://www.specialtysales.com/inventory?per_page=8')

# soupify it
soup = BeautifulSoup(page)

# get all the relative URLs to go to next pages
x = (soup.find_all(class_='carid'))
y = len(x)

# now go through those next pages & pull the relevant information

# get each car listing's id (& related URL)
vid=[]
for i in range(y):
	vid.append(x[i]['value'])

# iterate over every listing & pull info from each page
for i in range(len(vid)):
	URL='http://www.specialtysales.com/vehicles/'+vid[i]
	page = urllib2.urlopen(URL)
	soup = BeautifulSoup(page)

