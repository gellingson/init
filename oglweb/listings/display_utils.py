# display_utils.py
#
# utilities for displaying stuff (e.g. listings)
#
# there should be NO real logic here, just methods to make things pretty
#

# builtin modules used
import datetime
import pytz
from urllib.parse import urlparse

# third party modules used
from money import Money

# OGL modules used
from listings.models import Listing
from listings.utils import *

PRETTY_STATUS = {
    'F': 'is available',
    'P': 'is sale pending',
    'S': 'has been sold',
    'R': 'is no longer available',
    'T': 'is a test listing',
    'X': 'has been removed from the site'
}

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
# mark_since (if present) MUST be a TZ-aware datetime object or valid
# string that converts to same
#
def prettify_listing(listing, favorites={}, mark_since=None):

    # prettify price
    if not listing.price or listing.price == -1:
        listing.price = 'Contact for price'
    else:
        m = Money(listing.price, 'USD')
        listing.price = m.format('en_US')

    # add pretty status
    listing.pretty_status = PRETTY_STATUS[listing.status]

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
        mark_since = force_date(mark_since, None)
        listing_date = force_date(listing.listing_date)
        last_update = force_date(listing.last_update)

        if listing_date > mark_since:
            listing.since = 'New'
        elif last_update > mark_since:
            listing.since = 'Updated'
        else:
            listing.since = 'Old'
    return listing

