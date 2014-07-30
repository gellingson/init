# listings/feeds.py
#
# Publishes feeds of all, or a particular subset of, listings as an RSS feed
#
# Trivial to expand to feeds by make, make/model, etc.
# Once we add user accounts (heh) we can do custom feeds per account.
# Will use the DB to map feed URL component to a listings filter, e.g.:
# feed with 'make=ford' -> filter as directed
# feed with 'user=gee' -> custom filter for user gee
# (and we get the parm info through the feed url, e.g. rss/make/ford)

# third party imports

from django.contrib.syndication.views import Feed
from django.core.urlresolvers import reverse

# OGL imports

from  listings.models import Listing

# This feed is RSS, not Atom.
# See https://docs.djangoproject.com/en/dev/ref/contrib/syndication/ for how to expand & improve it

class ListingsFeed(Feed):
    title = 'Feed of car listings'
    link = '/rss/'
    description = 'Car listings as they post up.'

    def items(self):
        return Listing.objects.order_by('-pk')[:50]

    def item_title(self, item):
        return '{} {} {}'.format(item.model_year, item.make, item.model)

    def item_description(self, item):
        return item.listing_text

    # item_link is only needed if NewsItem has no get_absolute_url method.
    def item_link(self, item):
        return item.listing_href
