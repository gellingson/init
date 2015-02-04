#!/usr/bin/env python3
#
#
# this script is just a hacked-up copy of an ebaysdk script suitable for
# making random ebayapi calls without hacking on a more important script.
#
import ebaysdk
import json
from ebaysdk.finding import Connection as finding
from ebaysdk.exception import ConnectionError

foo = 'bar'
response = None
cars = None

def getparms():
    api = mkt(debug=True, appid=None, config_file='../conf/ebay.yaml',warnings=True)

# method to pull using exactly the same api_request/params as importer.py
def pull_like_importer():
    api = finding(debug=True, appid=None, config_file='../conf/ebay.yaml',warnings=True)
    api_request = {
        'keywords': 'Camaro', # GEE cheat, not in the importer.py api_request
        'categoryId': 6001,
        'GLOBAL-ID': 100,
        'buyerPostalCode': 95112,
        'itemFilter': [
        ],
        'aspectFilter': [],
        'affiliate': {'trackingId': 1},
        'sortOrder': 'CountryDescending',
        'paginationInput': {
            'entriesPerPage': 100, # max allowed; higher would be ignored
            'pageNumber': 1},
        'outputSelector': ['PictureURLLarge', 'PictureURLSuperSize'],
        }
    api_request['aspectFilter'].append(
        {'aspectName': 'Model Year',
         'aspectValueName': '1968'})
    response = api.execute('findItemsAdvanced', api_request)
    cars = response.json()
    carsj = json.loads(cars)
    f = open('ebay_output.json', 'w')
    f.write(json.dumps(carsj, indent=4, sort_keys=True))
        
#    r = response.dict()
#    for car in r['searchResult']['item']:
#        print('postal code is : {}'.format(car['postalCode']))
#    print(response.json())
#    print('{} cars found'.format(cars['_count']))
    f.close()
    return response, cars
    
# a pull that may resemble but is not identical to importer.py;
# use for expermientation and/or to pull histograms
def find():

    api = finding(debug=True, appid=None, config_file='../conf/ebay.yaml',warnings=True)
    api_request = {
        #'keywords': u'niño',
        'keywords': 'WRX',
        'categoryId': 6001,
        'GLOBAL-ID': 100,
        'buyerPostalCode': 95112,
        #        'keywords': u'Corvette',
#        'itemFilter': [
#            {'name': 'MaxDistance', 'value': 500},
#        ],
        'aspectFilter': [
#            {'aspectName': 'Model Year',
#             'aspectValueName': '1963'},
            {'aspectName': 'Model Year',
             'aspectValueName': '2006'},
#            {'aspectName': 'Model Year',
#             'aspectValueName': '2011'},
            {'aspectName': 'Make',
             'aspectValueName': 'Subaru'},
        ],
        'affiliate': {'trackingId': 1},
        'sortOrder': 'YearAscending',
        # This is how you get a list of the aspects for a category:
        # note that some examples/docs have initcap on 1st word but that is WRONG
#        'outputSelector': ['categoryHistogram', 'aspectHistogram']
        'outputSelector': ['CategoryHistogram', 'AspectHistogram']
        #        'outputSelector': ['PictureURLLarge', 'PictureURLSuperSize', 'ItemSpecifics', 'GalleryInfo'],
        }
    response = api.execute('findItemsAdvanced', api_request)
    cars = response.json()
    carsj = json.loads(cars)
    print(json.dumps(carsj, indent=4, sort_keys=True))
    r = response.dict()
    for car in r['searchResult']['item']:
        print('postal code is : {}'.format(car['postalCode']))
#    print(response.json())
#    print('{} cars found'.format(cars['_count']))
    return response, cars

if __name__ == "__main__":
#    find()
    pull_like_importer()
    print("done")
