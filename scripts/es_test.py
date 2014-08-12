
from bunch import Bunch
from datetime import datetime
from elasticsearch import Elasticsearch
import json

test_listing = Bunch()
test_listing['id'] = 1
test_listing['status'] = 'T' # T -> test data (will exclude from website listings)
test_listing['model_year'] = '1955'
test_listing['make'] = 'Ford'
test_listing['model'] = 'Thunderbird'
test_listing['price'] = '25000'
test_listing['listing_text'] = 'This is a fake thunderbird listing'
test_listing['pic_href'] = 'http://www.google.com'
test_listing['listing_href'] = 'http://www.yahoo.com'
test_listing['source_textid'] = 'dbtest'
test_listing['local_id'] = '1'
test_listing['stock_no'] = 'stock1234'
test_listing['timestamp'] = datetime.now()
es = Elasticsearch()
#index_resp = es.index(index="carbyr-index", doc_type="listing-type", id=test_listing.id, body=test_listing)
#print('index response: ' + index_resp)
#get_resp = es.get(index="carbyr-index", doc_type="listing-type", id=1)['_source']
#print('get response: ' + get_resp)
#search_resp = es.search(index="carbyr-index", doc_type="listing-type", q='make:ford')
#print('search response: ' + json.dumps(search_resp))
#search_resp = es.search(index="carbyr-index", doc_type="listing-type", q='fake')
#print('search response: ' + json.dumps(search_resp))
search_resp = es.search(index="carbyr-index", doc_type="listing-type", size=50, q='carbuffs')
#search_resp = es.search(index="carbyr-index", doc_type="listing-type", q='model_year:2008')
print('search response: ' + json.dumps(search_resp))
