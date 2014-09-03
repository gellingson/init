
# search
#curl 'http://search.3taps.com?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,account_id,source,category,location,external_id,external_url,heading,body,timestamp,timestamp_deleted,expires,language,price,currency,images,annotations,deleted,flagged_status,state,status&source=AUTOD&price=100000..250000&status=for_sale&state=available'

# polling, get an anchor
curl 'http://polling.3taps.com/anchor?auth_token=a7e282009ed50537b7f3271b753c803a&timestamp=1408593675'

# polling, simple example
#curl 'http://polling.3taps.com/poll?auth_token=a7e282009ed50537b7f3271b753c803a&source=HMNGS&category=VAUT&anchor=1329711562'

# polling, similar to what we actually want
#curl 'http://polling.3taps.com/poll?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,account_id,source,category,location,external_id,external_url,heading,body,timestamp,timestamp_deleted,expires,language,price,currency,images,annotations,deleted,flagged_status,state,status&source=CRAIG&anchor=1329711562&location.state=USA-CA'
# with full HTML requested
#curl 'http://polling.3taps.com/poll?auth_token=a7e282009ed50537b7f3271b753c803a&category=VAUT&retvals=id,account_id,source,category,location,external_id,external_url,heading,body,timestamp,timestamp_deleted,expires,language,price,currency,images,annotations,deleted,flagged_status,state,status,html&source=CRAIG&anchor=1329711562&location.state=USA-CA'

# reference pulls
#curl http://reference.3taps.com/sources?auth_token=a7e282009ed50537b7f3271b753c803a
#curl http://reference.3taps.com/category_groups?auth_token=a7e282009ed50537b7f3271b753c803a
#curl http://reference.3taps.com/categories?auth_token=a7e282009ed50537b7f3271b753c803a
#curl 'http://reference.3taps.com/locations?auth_token=a7e282009ed50537b7f3271b753c803a&level=country'
#curl 'http://reference.3taps.com/locations?auth_token=a7e282009ed50537b7f3271b753c803a&country=USA&level=state'
#curl 'http://reference.3taps.com/locations?auth_token=a7e282009ed50537b7f3271b753c803a&state=USA-CA&level=metro
#curl 'http://reference.3taps.com/locations?auth_token=a7e282009ed50537b7f3271b753c803a&state=USA-CA&level=metro'
