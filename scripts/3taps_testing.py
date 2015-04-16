#!/usr/bin/env python3
from base64 import b64decode
import json
import urllib.request
import urllib.error

# search
#query= 'http://search.3taps.com?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,account_id,source,category,location,external_id,external_url,heading,body,timestamp,timestamp_deleted,expires,language,price,currency,images,annotations,deleted,flagged_status,state,status&source=AUTOD&price=100000..250000&status=for_sale&state=available'
#query= 'http://search.3taps.com?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,external_id,external_url,body,timestamp,timestamp_deleted,expires,annotations,deleted,flagged_status,state,status&source=AUTOD&annotations={make:Mazda%20AND%20year:1999}&status=for_sale&state=available'
query= 'http://search.3taps.com?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,external_id,external_url,body,timestamp,timestamp_deleted,expires,annotations,deleted,flagged_status,state,status&source=AUTOD&external_id=AT-17ADC84E&status=for_sale&state=available'

# polling, get an anchor
#query= 'http://polling.3taps.com/anchor?auth_token=a7e282009ed50537b7f3271b753c803a&timestamp=1418851854'
# 1409157998 was aug 27th ~9am, yielded anchor 1349824942
# 1410293416 is 9/9/14, yielded anchor 1376049713
# 1418851854 is 12/17/14, yielded anchor 1647479925

# polling, simple example
#query= 'http://polling.3taps.com/poll?auth_token=a7e282009ed50537b7f3271b753c803a&source=HMNGS&category=VAUT&anchor=1329711562'

# polling, a query similar to what we actually execute in importer.py:
#query= 'http://polling.3taps.com/poll?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,account_id,source,category,location,external_id,external_url,heading,body,timestamp,timestamp_deleted,expires,language,price,currency,images,annotations,deleted,flagged_status,state,status,html&source=CRAIG&anchor=1376049713&location.state=USA-CA'
#query= 'http://polling.3taps.com/poll?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,account_id,source,category,location,external_id,external_url,heading,body,timestamp,timestamp_deleted,expires,language,price,currency,images,annotations,deleted,flagged_status,state,status&source=AUTOC&anchor=1666562836'

# with full HTML requested (which we do when we have to):
#query= 'http://polling.3taps.com/poll?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,account_id,source,category,location,external_id,external_url,heading,body,timestamp,timestamp_deleted,expires,language,price,currency,images,annotations,deleted,flagged_status,state,status,html&source=CRAIG&anchor=1329711562&location.state=USA-CA'

# reference pulls
#query= http://reference.3taps.com/sources?auth_token=a7e282009ed50537b7f3271b753c803a
#query= http://reference.3taps.com/category_groups?auth_token=a7e282009ed50537b7f3271b753c803a
#query= http://reference.3taps.com/categories?auth_token=a7e282009ed50537b7f3271b753c803a
#query= 'http://reference.3taps.com/locations?auth_token=a7e282009ed50537b7f3271b753c803a&level=country'
#query= 'http://reference.3taps.com/locations?auth_token=a7e282009ed50537b7f3271b753c803a&country=USA&level=state'
#query= 'http://reference.3taps.com/locations?auth_token=a7e282009ed50537b7f3271b753c803a&state=USA-CA&level=metro
#query= 'http://reference.3taps.com/locations?auth_token=a7e282009ed50537b7f3271b753c803a&state=USA-CA&level=metro'

try:
    req = urllib.request.Request(query)
    page = urllib.request.urlopen(req)
    bytestream = page.read()
    r = json.loads(bytestream.decode())
    print(json.dumps(r, indent=4, sort_keys=True))
    # comment out this loop if you only want the first page....
    # note that the below is broken because next_page is never -1 as the docs state
#    while r['next_page'] >= -1:
#       paged_query = query + '&page=' + str(r['next_page']) + '&tier=' + str(r['next_tier']) + '&anchor=' + str(r['anchor'])
#        print('NEXT QUERY IS: ' + paged_query)
#        req = urllib.request.Request(query)
#        page = urllib.request.urlopen(req)
#        bytestream = page.read()
#        r = json.loads(bytestream.decode())
#        print(json.dumps(r, indent=4, sort_keys=True))
        
except urllib.error.HTTPError as error:
    logging.error('Unable to poll 3taps at ' + query + ': HTTP ' +
                  str(error.code) + ' ' + error.reason)

