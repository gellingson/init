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

    
def find():

    api = finding(debug=True, appid=None, config_file='../conf/ebay.yaml',warnings=True)
    api_request = {
        #'keywords': u'niño',
        'categoryId': 6001,
        'GLOBAL-ID': 100,
        'buyerPostalCode': 95112,
#        'keywords': u'Corvette',
        'itemFilter': [
            {'name': 'MaxDistance', 'value': 500},
            ],
        'aspectFilter': [
            {'aspectName': 'Model Year',
             'aspectValueName': '1963'
             },
            {'aspectName': 'Model Year',
             'aspectValueName': '1964'
             },
            {'aspectName': 'Model Year',
             'aspectValueName': '2011'
             },
            {'aspectName': 'Make',
             'aspectValueName': 'Chevrolet'},
            ],
        'affiliate': {'trackingId': 1},
        'sortOrder': 'YearAscending',
#        'outputSelector': 'categoryHistogram',  # example has initcap on Cat too??
        'outputSelector': ['PictureURLLarge', 'PictureURLSuperSize'],
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
    find()
    print("done")
