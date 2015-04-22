# actions.py
#
# code for logging and adjusting listing quality based on user actions
#
# provides methods:
#    log_action()
#    calc_quality_adj()
#    apply_quality_adj()
#    log_and_adj_quality()  <- convenience method; calls the others

# builtin modules used
import logging

# third party modules used
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

# OGL modules used
from listings.constants import *
from listings.models import Listing, ActionLog


LOG = logging.getLogger(__name__)


def log_and_adj_quality(user, action,
                        reason=None, adj=None,
                        listing=None, listing_id=None):
    if listing_id and not listing:
        # fetch listing since we'll need to update it
        listing = Listing.objects.get(pk=listing_id)
    if listing and not adj:
        adj = calc_quality_adj(user, action, reason)
    if listing and adj:
        apply_quality_adj(user, action, reason, adj, listing)
    log_action(user, action, reason, adj, listing)
    return True

# calc_quality_adj()
#
# calculates a quality adjustment to apply from a given user action
#
# e.g. admin flags as fraud might be -10000, whereas an anonymous user
# clicking on the link might be +10 (if we track that at all....)
#
def calc_quality_adj(user, action, reason=None):
    # GEE TODO: would be great if users had an impact factor to apply...
    adj = 0
    if action == ACTION_FLAG:
        if reason == FLAG_REASON_UNINTERESTING:
            adj = -100
        elif reason == FLAG_REASON_NONCAR:
            adj = -1000
        elif reason == FLAG_REASON_INCORRECT:
            adj = -300
        elif reason == FLAG_REASON_FRAUD:
            adj = -1000
        elif reason == FLAG_REASON_SOLD:
            adj = -5000
        else:
            adj = -300
        if user.is_authenticated():
            if user.is_superuser:
                adj = adj * 10  # 10x the adjustment for superuser acts
        else:
            adj = adj / 10
    elif action == ACTION_FAV:
        if user.is_authenticated():
            adj = +150
        else:
            adj = +50
    elif action == ACTION_UNFAV:
        if user.is_authenticated():
            adj = -50  # give back 1/3 of the favoriting bonus
        else:
            adj = -25  # give back 1/2 of the favoriting bonus
    elif action == ACTION_VIEW:
        # this means view on the site but not click through to source
        if user.is_authenticated():
            adj = 15
        else:
            adj = 5
    elif action == ACTION_CLICKTHROUGH:
        # roughly 1/3 of the value of a favoriting...
        # may be too high once we get meaningful traffic levels
        if user.is_authenticated():
            adj = 50
        else:
            adj = 15
    # ...else adj remains 0
    return adj


# apply_quality_adj()
#
# applies a quality adjustment to a listing based on user & action (etc)
#
# Notes:
# can be passed either listing_id or an actual listing object (for speed)
# calls calc_quality_adj if adj is not passed in (again, efficiency...)
# this action should getting logged separately (this does not log)
#
def apply_quality_adj(user, action,
                      reason=None, adj=None,
                      listing=None, listing_id=None):
    if not listing and listing.id:  # seemingly a valid listing obj?
        if not listing_id:
            return False
        listing = Listing.objects.get(pk=listing_id)
        if not listing:
            return False
    if adj is None:
        adj = calc_quality_adj(user, listing_id, action, reason)
    if adj:
        # save to the listing itself in the db (denormalizing for performance)
        if not listing.dynamic_quality:
            listing.dynamic_quality = 0
        listing.dynamic_quality += adj
        listing.save()

    # now apply the update to elasticsearch, which uses it for scoring;
    # always fetch the listing from es since the listing object we have will
    # be from the db, not es, and will have wrong geo info & misc issues
    es = Elasticsearch()
    try:
        r = es.get(index="carbyr-index",
                   doc_type="listing-type",
                   id=listing.id)
        if r['found']:
            es_listing = r['_source']
            if not es_listing['dynamic_quality']:
                es_listing['dynamic_quality'] = 0
            es_listing['dynamic_quality'] += adj
            es.index(index="carbyr-index",
                     doc_type="listing-type",
                     id=es_listing['id'],
                     body=es_listing)
    except NotFoundError as err:
        pass
        return False
    return True


# log_action()
#
# logs the given action by the given user
#
# Notes:
# includes the applied adjustment, if any.
# calcs the adjustment if such applies and None is passed in.
#
def log_action(user, action,
               reason=None, adj=None,
               listing=None, listing_id=None):
    logentry = ActionLog()
    if user.is_authenticated():
        logentry.user = user;
    # two ways we might get listing info... or we may get neither:
    if listing_id and not listing:
        listing = Listing();
        listing.id = listing_id
    if listing:  # whether passed as a listing or listing_id
        logentry.listing = listing
    logentry.action = action
    if reason:
        logentry.reason = reason
    if listing_id and adj is None:
        adj = calc_quality_adj(user, listing_id, action, reason)
    logentry.adjustment = adj
    logentry.save()
    return True
