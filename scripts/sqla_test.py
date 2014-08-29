#!/usr/bin/env python3

from orm.models import Classified
from orm.models import Listing
from orm.session import session

c = session.query(Classified).get(3)
print(c)

#listing = session.query(Listing).first()
#print(listing)
#print('tagset is: {}'.format('/'.join(listing.tagset)))
#print('adding tags')
#listing.add_tag('musclecar')
#listing.add_tag('hotrod')
#print('removing tag')
#listing.remove_tag('hotrod')
#print(listing)
#print('tagset is: {}'.format('/'.join(listing.tagset)))
#session.commit()
result = session.execute("update listing set markers = concat(ifnull(markers,''), 'P') where source_type = :source_type and source_id = :source_id and status = 'F'", {'source_type': 'D', 'source_id': 1})
session.commit()
