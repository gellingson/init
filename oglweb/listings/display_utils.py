
import datetime
import pytz
from urllib.parse import urlparse

from money import Money
from listings.models import Listing

# prettify_listing()
#
# marks up a listing for display
#
# NOTES:
#
# expects to be passed a Bunch so that it can munge it incl adding fields;
# convert elasticsearch result records or Listing model records to Bunches
#
# if a dict of favorites is provided it will be checked & used to mark up
#
# if a mark_since timestamp is provided then listings with listing_date or
# last_updated newer than the given timestamp will be annotated as such
#
# mark_since (if present) MUST be a TZ-aware datetime object
#
def prettify_listing(listing, favorites={}, mark_since=None):

    # prettify price
    if not listing.price or listing.price == -1:
        listing.price = 'Contact for price'
    else:
        m = Money(listing.price, 'USD')
        listing.price = m.format('en_US')

    # clean any bad pic_hrefs
    p = urlparse(listing.pic_href)
    if not p or not p.netloc:
        # relative URL means we have a problem
        listing.pic_href = ''

    # is this one of the user's favorite listings?
    fav = favorites.get(listing.id, None)
    if fav:
        listing.favorite = True
        listing.note = fav.note
    else:    
        listing.favorite = False

    # GEE TODO: fix the building of listing records so that timestamps
    # and other type gotchas are handled upstream of here! This probably
    # includes fixing how we store timestamps in elasticsearch (esp the
    # ugly implied UTC bullshit). But for now:
    
    if mark_since:
        # listing pulled from the db will have datetime objects;
        # listings pulled from elasticsearch will have strings
        #   (in the format below, with UTC implied -- yuck)
        # mark_since must be a TZ-aware datetime

        if type(listing.listing_date) == datetime.datetime:
            listing_date = listing.listing_date
        else:
            listing_date = datetime.datetime.strptime(listing.listing_date,
                                                      '%Y-%m-%dT%H:%M:%S').replace(tzinfo=pytz.UTC)
        if type(listing.last_update) == datetime.datetime:
            last_update = listing.last_update
        else:
            last_update = datetime.datetime.strptime(listing.last_update,
                                                      '%Y-%m-%dT%H:%M:%S').replace(tzinfo=pytz.UTC)
        if listing_date > mark_since:
            listing.since = 'New'
        elif last_update > mark_since:
            listing.since = 'Updated'
        else:
            listing.since = 'Old'
    return listing

