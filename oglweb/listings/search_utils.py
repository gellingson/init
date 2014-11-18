
import datetime
import pytz
import time

# third party modules used
from bunch import Bunch

from django.utils.datastructures import MultiValueDictKeyError
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

# OGL modules used
from listings.constants import *
from listings.display_utils import prettify_listing
from listings.models import Zipcode, Listing, SavedQuery, ActionLog
from listings.favlist_utils import favdict_for_user
from listings.query_utils import *

#
# builds an es query based on request vars
#
# factored out into a utility method to facilitate multiple search views/urls
#

def handle_search_args(request, filter=None, base_url = None, query_ref=None):

    args = Bunch()
    args.errors = {}
    args.sort = "relevance"

    # POST params
    args.action = request.POST.get('action', '')
    args.query_ref = request.POST.get('query_ref', '')
    args.query_descr = request.POST.get('query_descr', '')
    args.query_date = request.POST.get('query_date', '')
    if args.query_date:
        args.query_date = datetime.datetime.fromtimestamp(float(args.query_date), pytz.UTC)

    # GET params
    if base_url:
        args.base_url = base_url
    else:
        args.base_url = request.GET.get('base_url', 'cars/')

    # two other places (besides POST vars above) that might set query_ref
    if not args.query_ref:
        if query_ref:
            args.query_ref = query_ref
        else:
            args.query_ref = request.GET.get('s','')

    args.query_string = request.GET.get('query_string', '')

    try:
        junk = request.GET['limit']  # anything in there we'll consider a YES
        args.limit = True
    except MultiValueDictKeyError:
        args.limit = None;

    args.zip = request.GET.get('zip','')
    if not 'zip' in args or not args.zip:
        args.zip = '95112';  # GEE TODO: get default zip from client IP

    # validate zip
    try:
        zipcode = Zipcode.objects.get(zip=args.zip)
        args.lat = float(zipcode.lat)
        args.lon = float(zipcode.lon)
    except Zipcode.DoesNotExist:
        args.errors['invalid_zip'] = True

    # is there also a filter?
    if filter:
        if filter in VALID_FILTERS:
            #error_message = 'Limiting as per filter {}: {}'.format(filter, VALID_FILTERS[filter])
            args.filter_term = VALID_FILTERS[filter]
        else:
            args.errors['invalid_filter'] = True
    return args


# build_new_query()
#
# assembles a new query per the given args
#
# NOTES:
# returns a Query object, but not all fields are set:
# just type, descr, and query fields will be set.
# ref, mark_date, id (pk), and user mapping are left to the caller.
#
def build_new_query(args):
    q = Query()
    q.type = 'U'  # presume we have some args from user (checked below)

    # building the query string:

    # querybody components
    filter_term = args.get('filter_term', None)
    geolimit_term = ''
    search_term = ''

    if args.query_string:
        search_term = {
            "query_string": {
                "query": args.query_string,
                "default_operator": "AND"
            }
        }
    else:
        if not args.limit:
            # no criteria at all; don't retrieve everything; give
            # cars from the last few days
            args.query_string = "recently-listed cars"
            q.type = 'D'  # default search
            search_term = {
                "constant_score": {
                    "filter": {
                        "range": {
                            "listing_date": {
                                "from": datetime.date.fromtimestamp(
                                    time.time()-86400).__str__(),
                                "to": datetime.date.fromtimestamp(
                                    time.time()+86400).__str__()
                            }
                        }
                    }
                }
            }

    if args.limit:
        if not args.zip or 'zip_error' in args.errors:
            error_message = 'Unknown zip code "{}"; geographic limit not applied.'.format(zip)
        else:
            geolimit_term = {
                "geo_distance" : {
                    "distance": "100mi",
                    "location": {
                        "lat": args.lat,
                        "lon": args.lon
                    }
                }
            }
    sort_term = None
    if args.sort == 'nearest':
        sort_term = [
            {
                "_geo_distance": {
                    "location": {
                        "lat": args.lat,
                        "lon": args.lon
                    },
                    "order": "asc",
                    "unit": "mi"
                }
            }
    ]

    # assemble the pieces
    q.query = {"query": {"filtered": {}}}
    if search_term:
        q.query['query']['filtered']['query'] = search_term
    if geolimit_term or filter_term:
        q.query['query']['filtered']['filter'] = {}
        q.query['query']['filtered']['filter']['and'] = []
        if geolimit_term:
            q.query['query']['filtered']['filter']['and'].append(geolimit_term)
        if filter_term:
            q.query['query']['filtered']['filter']['and'].append(filter_term)
    if sort_term:
        q.query['sort'] = sort_term

    # so... how shall we describe this query to the user?
    q.descr = None
    if geolimit_term:
        if args.query_string:
            q.descr = args.query_string + ", near " + args.zip
        else:
            q.descr = "cars near " + args.zip
    else:
        q.descr = args.query_string

    # return the user-friendly description and the actual es query body
    return q



# get_listings()
#
# gets listings from elasticsearch & prettifies them
#
# returns a tuple of the number of records & a list listings;
# the listings are Bunches with extra info from the prettify method
#
def get_listings(querybody, number=50, offset=0, user=None, mark_since=None):
    es = Elasticsearch()
    search_resp = es.search(index='carbyr-index',
                            doc_type='listing-type',
                            size=number,
                            from_=offset,
                            body=querybody)
    listings = []

    # if we know the user, see if they have any favorites
    fav_dict = {}
    flag_set = set()
    if user.is_authenticated():
        fav_dict = favdict_for_user(user)
        # a superuser flagging always nukes the post; other users may
        # have flagged posts and we should not show those posts again
        if not user.is_superuser:
            flag_set = flagset_for_user(user)

    for item in search_resp['hits']['hits']:
        if int(item['_source']['id']) in flag_set:
            pass  # throw it out
        else:
            es_listing = prettify_listing(Bunch(item['_source']),
                                          favorites=fav_dict,
                                          mark_since=mark_since)
            listings.append(es_listing)
    return search_resp['hits']['total'], listings


# flagset_for_user()
#
# returns the set of listing_ids a user has flagged
#
# NOTE: this will get S-L-O-W if we don't keep these pruned.
# GEE TODO: implement pruning of this table so we can afford to keep running
# this query all the time :-)
#
def flagset_for_user(user):
    flagset = ActionLog.objects.filter(user=user,
                                       action=ACTION_FLAG).values('listing_id')
    return  set(al['listing_id'] for al in flagset)


# flag_listing()
#
# GEE TODO error handling, logging the action, etc etc
def flag_listing(user, listing_id, reason, other_reason=None):
    remove = False
    if user.is_authenticated() and user.is_superuser:
        remove = True
    adj = calc_quality_adj(user, listing_id, ACTION_FLAG, reason)
    listing = Listing.objects.get(pk=listing_id)
    if not listing:
        return False
    if not listing.dynamic_quality:
        listing.dynamic_quality = 0
    if listing.dynamic_quality + adj < -800:  # arbitrary threshold :)
        remove = True

    apply_quality_adj(user, ACTION_FLAG, reason, adj, listing=listing)

    if remove:
        es = Elasticsearch()
        es.delete(index="carbyr-index",
                  doc_type="listing-type",
                  id=listing_id)
        # load listing again to make sure it isn't stale (missing adj?)
        listing = Listing.objects.get(pk=listing_id)
        listing.status = 'X'
        listing.save()

    long_reason = reason
    if reason == FLAG_REASON_OTHER:
        long_reason = long_reason + ':' + other_reason
    log_action(user, ACTION_FLAG, long_reason, adj, listing=listing)

    return True


# calc_quality_adj()
#
# calculates a quality adjustment to apply from a given user action
#
# e.g. admin flags as fraud might be -10000, whereas an anonymous user
# clicking on the link might be +10 (if we track that at all....)
#
def calc_quality_adj(user, listing_id, action, reason=None):
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
        if user.is_authenticated:
            if user.is_superuser:
                adj = adj * 10
        else:
            adj = adj / 10
    elif action == ACTION_FAV:
        if user.is_authenticated:
            adj = +300
        else:
            adj = +100
    elif action == ACTION_UNFAV:
        if user.is_authenticated:
            adj = -100  # give back 1/3 of the favoriting bonus
        else:
            adj = -50  # give back 1/2 of the favoriting bonus
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
                      listing=None, listing_id = None):
    if not listing and listing.id:  # seemingly a valid listing obj?
        if not listing_id:
            return False
        listing = Listing().objects.get(pk=listing_id)
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
        return True
    return False


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
               listing_id=None, listing=None):
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
        
