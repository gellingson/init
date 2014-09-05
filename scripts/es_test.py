#!/usr/bin/env python3
from bunch import Bunch
from datetime import datetime
from elasticsearch import Elasticsearch
import json
from orm.models import Listing
import time

test_listing = Bunch()
#test_listing = Listing()
test_listing.id = 1
test_listing.status = 'F' # T -> test data (will exclude from website listings)
test_listing.model_year = '1955'
test_listing.make = 'Furd'
test_listing.model = 'Thunderbird'
test_listing.price = '25000'
test_listing.listing_text = 'This is a fake thunderbird listing'
test_listing.pic_href = 'http://www.google.com'
test_listing.listing_href = 'http://www.yahoo.com'
test_listing.source_textid = 'dbtest'
test_listing.local_id = '1'
test_listing.stock_no = 'stock1234'
test_listing.timestamp = datetime.now()
test_listing.lat = 40
test_listing.lon = -80
test_listing.location = {'lat': 35, 'lon': -75} # diff from .lat/.lon for testing purposes

#print(json.dumps(test_listing))
tl2 = {"make": "Furd",
       "model": "Thunderbird",
       "id": 2,
       "model_year": "1975"}

#listing_index_mapping = {
#    "mytype":
mytype_mapping = {
        "properties": {
            "tags": {
                "type" : "string"
            },
            "price": {
                "type": "long"
            },
            "id": {
                "type": "long"
            },
            "model_year": {
                "type": "string"
            },
            "make": {
                "type": "string"
            },
            "model": {
                "type": "string"
            },
            "listing_text": {
                "type": "string"
            },
            "source_textid": {
                "type": "string"
            },
            "location": {
                "type": "geo_point"
            }
        }
    }
#}

querybody={"query": {"match": {"model":"Thunderbird"}},
           "filter": {
               "geo_distance": {
                   "distance": "50mi",
                   "location": {
                       "lat": 36,
                       "lon": -75
                   }
               }
           }
}
querybody2={"query": {"match": {"make":"Ford"}},
           "filter": {
               "geo_distance": {
                   "distance": "50mi",
                   "location": {
                       "lat": 37.34,
                       "lon": -12.88
                   }
               }
           }
}
querybody3={
    "query": {
        "filtered": {
            "query": {
                "query_string": {
                    "query": "(model:miata)&&(1999)"
                }
            },
            "filter": {
                "and": [
                    {
                        "term": {
                            "model": "miata"
                        },
                    },
                    {
                        "geo_distance": {
                            "distance": "50mi",
                            "location": {
                                "lat": 37.34,
                                "lon": -121.88
                            }
                        }
                    }
                ]
           }
        }
    }
}



es = Elasticsearch()

# delete and recreate a test index
#index_resp = es.indices.delete(index="mytestindex")
#print(index_resp)
#index_resp = es.indices.create(index="mytestindex",
#                               body={"settings": {"number_of_shards" : 1},
#                                     "mappings": {"mytype": mytype_mapping}})
#print(index_resp)
#time.sleep(2)

#mapping_resp = es.indices.get_mapping(index="carbyr-index")
#print("\n{}".format(json.dumps(mapping_resp, indent=2, sort_keys=True)))

#index_resp = es.index(index="mytestindex", doc_type="mytype", id=test_listing.id, body=test_listing)
#print('index response: {}'.format(json.dumps(index_resp, indent=2, sort_keys=True)))

#get_resp = es.get(index="mytestindex", doc_type="mytype", id=1)#['_source']
#print('\nget returns this _source: {}'.format(json.dumps(get_resp, indent=2, sort_keys=True)))
#time.sleep(2)
#search_resp = es.search(index="mytestindex", doc_type="mytype",
#                        body=querybody,
#                        fields='location,model_year,make,model', _source=True)
#print('\nsearch response: {}'.format(json.dumps(search_resp, indent=2, sort_keys=True)))

#index_resp = es.index(index="carbyr-index", doc_type="listing-type", id=1, body=test_listing)
#print('index response: {}'.format(json.dumps(index_resp, indent=2, sort_keys=True)))

#get_resp = es.get(index="carbyr-index", doc_type="listing-type", id=1)#['_source']
#print('\nget returns this _source: {}'.format(json.dumps(get_resp, indent=2, sort_keys=True)))

#search_resp = es.search(index="carbyr-index", doc_type="listing-type", q='make:furd')
#print('\nsearch response: {}'.format(json.dumps(search_resp, indent=2, sort_keys=True)))

#search_resp = es.search(index="mytestindex", doc_type="mytype", body=querybody2)
search_resp = es.search(index="carbyr-index", doc_type="listing-type", body=querybody3)
print('\nsearch response: {}'.format(json.dumps(search_resp, indent=2, sort_keys=True)))

#search_resp = es.search(index="carbyr-index", doc_type="listing-type", size=50,
#                        q='carbuffs')
#print('\nsearch response: {}'.format(json.dumps(search_resp)))

#search_resp = es.search(index="carbyr-index", doc_type="listing-type", size=50, q='furd')
#print('\nsearch response: {}'.format(json.dumps(search_resp,  indent=2, sort_keys=True)))

#search_resp = es.search(index="carbyr-index", doc_type="listing-type", q='make:furd',
#                        fields='model_year,make,model')
#print('\nsearch response: {}'.format(json.dumps(search_resp,  indent=2, sort_keys=True)))

#search_resp = es.search(index="carbyr-index", doc_type="listing-type", q='fake')
#print('search response: ' + json.dumps(search_resp))
#search_resp = es.search(index="carbyr-index", doc_type="listing-type",
#                        body={"query": {"match":{"model":"miata"}}})
#search_resp = es.search(index="carbyr-index", doc_type="listing-type",
#                        body={"query": {"match": {"model":"miata"}},
#                              "filter": {
#                                  "geo_distance": {
#                                      "distance": "800km",
#                                      "listing": {
#                                          "lat": 40,
#                                          "lon": -70
#                                          }
#                                      }
#                                  }
#                               })
#search_resp = es.search(index="carbyr-index", doc_type="listing-type", q='model_year:2008')
#print('search response: ' + json.dumps(search_resp))
