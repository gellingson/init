#!/usr/bin/env python3
from base64 import b64decode
import json
import urllib.request
import urllib.error

# search
#query= 'http://search.3taps.com?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,account_id,source,category,location,external_id,external_url,heading,body,timestamp,timestamp_deleted,expires,language,price,currency,images,annotations,deleted,flagged_status,state,status&source=AUTOD&price=100000..250000&status=for_sale&state=available'

# polling, get an anchor
query= 'http://polling.3taps.com/anchor?auth_token=a7e282009ed50537b7f3271b753c803a&timestamp=1409157998'
# 1409157998 was aug 27th ~9am, yielded anchor 1349824942
# 1410293416 is 9/9/14, yielded anchor 1376049713

# polling, simple example
#query= 'http://polling.3taps.com/poll?auth_token=a7e282009ed50537b7f3271b753c803a&source=HMNGS&category=VAUT&anchor=1329711562'

# polling, similar to what we actually want
#query= 'http://polling.3taps.com/poll?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,account_id,source,category,location,external_id,external_url,heading,body,timestamp,timestamp_deleted,expires,language,price,currency,images,annotations,deleted,flagged_status,state,status,html&source=CRAIG&anchor=1376049713&location.state=USA-CA'
query= 'http://polling.3taps.com/poll?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,account_id,source,category,location,external_id,external_url,heading,body,timestamp,timestamp_deleted,expires,language,price,currency,images,annotations,deleted,flagged_status,state,status&source=HMNGS&anchor=1362530738'

# with full HTML requested
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
except urllib.error.HTTPError as error:
    logging.error('Unable to poll 3taps at ' + query + ': HTTP ' +
                  str(error.code) + ' ' + error.reason)

