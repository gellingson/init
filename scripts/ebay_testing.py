#
#
# this script is just a hacked-up copy of an ebaysdk script suitable for
# making random ebayapi calls without hacking on a more important script.
#
import ebaysdk
from ebaysdk.finding import Connection as finding
from ebaysdk.exception import ConnectionError

foo = 'bar'
response = None
cars = None

def getparms():
    api = mkt(debug=True, appid=None, config_file='../conf/ebay.yaml',warnings=True)

    
def find():
    print("finding")
    api = finding(debug=True, appid=None, config_file='../conf/ebay.yaml',warnings=True)
    api_request = {
        #'keywords': u'niño',
        'categoryId': 6001,
        'GLOBAL-ID': 100,
        'buyerPostalCode': 95112,
#        'keywords': u'Corvette',
        'itemFilter': [
            {'name': 'MaxDistance', 'value': 100},
            {'name': 'MaxYear', 'value': 1964},
            ],
        'aspectFilter': [
            {'aspectName': 'Model Year',
             'aspectValueName': '2002'
             },
            {'aspectName': 'Model Year',
             'aspectValueName': '2003'
             },
            {'aspectName': 'Make',
             'aspectValueName': 'Toyota'},
            ],
        'affiliate': {'trackingId': 1},
        'sortOrder': 'YearAscending',
        'outputSelector': 'categoryHistogram',
        }
    response = api.execute('findItemsAdvanced', api_request)
    cars = response.json()
    print(response.json())
#    print('{} cars found'.format(cars['_count']))
    return response, cars

if __name__ == "__main__":
    print("ho")
    find()
    print("done")
