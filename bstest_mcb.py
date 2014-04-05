
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
page = urllib2.urlopen('http://www.specialtysales.com/allvehicles.php?pg=1&dir=asc&order=year&lim=800')

# soupify it
soup = BeautifulSoup(page)

# extract all the listings
# look for these: <input class="carid" type="hidden" value="4181"/> and then grab the enclosing <li> node

carids = soup.find_all(class_='carid')
print('Number of car listings found: {}'.format(len(carids))) # should be 800 max
for carid in carids:
    listing = carid.parent # shorthand for find_parent()?
    words = listing.find('h2').get_text().split(" ",2) # pull out year & make; remaining string is model
    year = int(words[0])
    make = words[1]
    model = words[2]
    pic = listing.find('img')
    text = listing.find(class_='intro-text').get_text()
    price = regularize_price(listing.find('h3').get_text())
    try:
    	vin = re.search('VIN(.+?)*',text).group(1)
    except AttributeError:
    	vin = "nada"
    print(vin)
    #re.IGNORECASE

    #print('{} {} {} {} {}'.format(year, make, model, price, text.encode('ascii', 'replace')))
    #print('{} ** {} ** {} ** {} ** {}'.format(year, make, model, price, pic))
