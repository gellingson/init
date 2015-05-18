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

from django.contrib.syndication.views import Feed, FeedDoesNotExist
from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404

# OGL imports
from  listings.models import Listing
from listings.query_utils import *
from listings.search_utils import *

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
        return '<img href="' + str(item.pic_href) + '"><p>' + str(item.listing_text) + '</p>'
#        return item.listing_text

    # item_link is only needed if NewsItem has no get_absolute_url method.
    def item_link(self, item):
        return item.listing_href

class QueryFeed(Feed):
    description_template = 'listings/feeds/listing_description.html'

    def get_object(self, request, user_id, query_id):
        # GEE - note that we are going to db, not session (don't have one)
        q = get_object_or_404(SavedQuery, pk=query_id)
        if str(q.user.id) == user_id:
            return q
        return None

    def title(self, obj):
        return "Listings for: " + obj.descr

    def link(self, obj):
        if obj:
            return 'http://carbyr.com/cars/' + str(obj.user.id) + '/' + str(obj.id) + '/rss/'
        return 'http://carbyr.com/'

    def description(self, obj):
        return "A continuous stream of Carbyr car listings for your query: " + str(obj.descr)

    def items(self, obj):
        LOG.info('%s: feed: %s [%s]',
                 obj.user.username or 'anon',
                 obj.ref or '', obj.descr)        
        num, listings, tossed = get_listings(obj)
        return listings

    def item_title(self, item):
        return '{} {} {}'.format(item.model_year, item.make, item.model)

#    def item_description(self, item):
#        return '<img href="' + item.pic_href + '"><p>' + item.listing_text + '</p>'

    # item_link is only needed if NewsItem has no get_absolute_url method.
    def item_link(self, item):
        return item.listing_href
