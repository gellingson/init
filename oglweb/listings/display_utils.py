
from urllib.parse import urlparse

from money import Money

def prettify_listing(listing):

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

    return listing

