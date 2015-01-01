#!/usr/bin/env python3
from bunch import Bunch
from datetime import datetime
from elasticsearch import Elasticsearch
import json
from orm.models import Zipcode
from orm.session import session

ziptype_mapping = {
        "properties": {
            "zip": {
                "type" : "string"
            },
            "country_code": {
                "type": "string"
            },
            "city": {
                "type": "string"
            },
            "location": {
                "type": "geo_point"
            }
        }
    }
#}

querybody={"filter": {
               "geo_distance": {
                   "distance": "10mi",
                   "location": {
                       "lat": 1,
                       "lon": 2
                   }
               }
           }
}



es = Elasticsearch()

# delete and recreate a temp index of zipcodes
try:
    index_resp = es.indices.delete(index="zipindex")
    print(index_resp)
except elasticsearch.exceptions.NotFoundError:
    logging.warning('Index not found while attempting to drop it')

index_resp = es.indices.create(index="zipindex",
                               body={"settings": {"number_of_shards" : 5},
                                     "mappings": {"ziptype": ziptype_mapping}})
print(index_resp)

mapping_resp = es.indices.get_mapping(index="zipindex")
print("\n{}".format(json.dumps(mapping_resp, indent=2, sort_keys=True)))

zips = session.query(Zipcode).all()
i = 1
for zip in zips:
    z = dict(zip)
    index_resp = es.index(index="zipindex", doc_type="ziptype", id=i, body=z)
    i = i + 1
    if i<5:
        print('index response: {}'.format(json.dumps(index_resp, indent=2, sort_keys=True)))
