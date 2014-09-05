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



es = Elasticsearch()

mapping_resp = es.indices.get_mapping(index="zipindex")
print("\n{}".format(json.dumps(mapping_resp, indent=2, sort_keys=True)))

get_resp = es.get(index="zipindex", doc_type="ziptype", id=1)#['_source']
print('\nget returns this _source: {}'.format(json.dumps(get_resp, indent=2, sort_keys=True)))

search_resp = es.search(index="zipindex", doc_type="ziptype",
                        body={
                            "query": {
                                "filtered": {
                                    "query": {
                                        "match_all": {}
                                        },
                                    "filter": {
                                        "geo_distance": {
                                            "distance": "150mi",
                                            "location": {
                                                "lat": 40.8,
                                                "lon": -73.0
                                            }}}}}})
print('\nsearch returns this {}'.format(json.dumps(search_resp, indent=2, sort_keys=True)))
