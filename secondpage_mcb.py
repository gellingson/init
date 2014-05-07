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
#page = urllib2.urlopen('http://www.specialtysales.com/allvehicles.php?pg=1&dir=asc&order=year&lim=15')
page = urllib2.urlopen('http://www.specialtysales.com/inventory?per_page=8')

# soupify it
soup = BeautifulSoup(page)

# get all the relative URLs to go to next pages

#x = soup.find_all(href=re.compile("vehicles"))
#x = soup.find_all(href=re.compile("vehicles"))
#x = soup(id=True)
x = (soup.find_all(class_='carid'))
for links in soup.find_all('carid'):
	print (links.get('href')
		
#print x
#print type(x[0])

# now go through those next pages & pull the relevant information

# iterate over instances of x
#vid="30913"
#URL='http://www.specialtysales.com/vehicles/'+vid
#print URL
#page = urllib2.urlopen(URL)

#soup = BeautifulSoup(page)