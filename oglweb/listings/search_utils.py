# search_utils.py

# builtin modules used
import copy
import datetime
import pytz
import time

# third party modules used
from bunch import Bunch
from django.utils.datastructures import MultiValueDictKeyError
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

# OGL modules used
from listings.actions import log_action, calc_quality_adj, apply_quality_adj
from listings.constants import *
from listings.display_utils import prettify_listing
from listings.models import Zipcode, Listing, SavedQuery, ActionLog
from listings.favlist_utils import favdict_for_user
from listings.query_utils import *
from listings.utils import *



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
        args.query_date = force_date(args.query_date)

    # GET params
    if not args.action:
        # used on some GET forms too (e.g. switching new-cars-only on/off)
        args.action = request.GET.get('action', '')
    if base_url:
        args.base_url = base_url
    else:
        args.base_url = request.GET.get('base_url', 'cars/')

    # two other places (besides POST vars above) that might set query_ref
    if not args.query_ref:
        if query_ref:
            args.query_ref = query_ref
        else:
            # URLs use s=; forms (even GET forms) use query_ref inputs
            args.query_ref = request.GET.get('query_ref', request.GET.get('s', ''))

    args.query_string = request.GET.get('query_string', '')

    try:
        junk = request.GET['limit']  # anything in there we'll consider a YES
        args.limit = True
    except MultiValueDictKeyError:
        args.limit = None;

    args.limit_zip = request.GET.get('zip','') # set only if user specifies
    # if the user does not specify a zip limit, we still want one for relevance etc
    args.zip = args.limit_zip
    if not 'zip' in args or not args.zip:
        args.zip = '95112';  # GEE TODO: get default zip from client IP

    # validate zip
    args.lat = None
    args.lon = None
    try:
        zipcode = Zipcode.objects.get(zip=args.zip)
        args.lat = float(zipcode.lat)
        args.lon = float(zipcode.lon)
    except Zipcode.DoesNotExist:
        args.errors['invalid_zip'] = True

    args.min_price = extract_int(request.GET.get('price_min', None))
    args.max_price = extract_int(request.GET.get('price_max', None))

    args.min_year = extract_int(request.GET.get('year_min', None))
    args.max_year = extract_int(request.GET.get('year_max', None))

    args.has_criteria = (args.query_string or
                         args.limit or
                         args.min_price or args.max_price or
                         args.min_year or args.max_year)

    # is there also a filter?
    # GEE TODO: this is probably dead/unused code by now (dec '14): remove?
    if filter:
        if filter in VALID_FILTERS:
            #error_message = 'Limiting as per filter {}: {}'.format(filter, VALID_FILTERS[filter])
            args.filter_term = VALID_FILTERS[filter]
        else:
            args.errors['invalid_filter'] = True
    return args


# populate_search_context()
#
# populates the given context with values for UI fields
#
# NOTES: I'm not entirely comfortable with the mixing of display and other
# concerns here, but it works for now....
def populate_search_context(context, args, query):
    if args.query_ref and query and args.query_ref == query.ref:
        # paint the page with the saved tab open
        context['tab'] = 'saved'
        # and populate the context from the query
        if query.type == QUERYTYPE_DEFAULT:  # default query, no parms
            return

        if query.params:
            for key, value in query.params.items():
                context[key] = value
        else:  # might be an old pre-params-field query (from 2014)
            try:
                context['query_string'] = query.query['query']['filtered']['query']['query_string']['query']
            except KeyError:
                pass
            filters = None
            try:
                filters = query.query['query']['filtered']['filter']['and']
            except KeyError:
                return  # no filters present
            for filter in filters:
                if 'geo_distance' in filter:
                    context['limit'] = True
                    # GEE TODO: really store input zip -- this is a BIG cheat! :)
                    list = query.descr.split(" ")
                    near_found = False
                    for word in list:
                        if word == 'near':
                            near_found = True
                        elif near_found:
                            context['zip'] = word.translate({ord(','):None})
                            break
                if 'range' in filter:
                    if 'price' in filter['range']:
                        context['min_price'] = filter['range']['price'].get('gte', None)
                        context['max_price'] = filter['range']['price'].get('lte', None)
                    if 'model_year' in filter['range']:
                        context['min_year'] = filter['range']['model_year'].get('gte', None)
                        context['max_year'] = filter['range']['model_year'].get('lte', None)
    else: # repop the user's most recent inputs
        if args.limit or args.limit_zip or args.min_price or args.max_price or args.min_year or args.max_year:
            context['tab'] = 'advanced'
        else:
            context['tab'] = 'simple'
        context['query_string'] = args.query_string
        context['limit'] = args.limit
        context['zip'] = args.limit_zip
        context['min_price'] = args.min_price
        context['max_price'] = args.max_price
        context['min_year'] = args.min_year
        context['max_year'] = args.max_year


# add_date_limit()
#
# adds a clause to an es query limiting to cars newer than the given datetime
# NOTE: uses add_filter() which deep copied & then returns a new querybody!
#
def add_date_limit(querybody, date):
    date_term = {
        "range": {
            "listing_date": {
                "from": force_date(date)
            }
        }
    }
    return add_filter(querybody, date_term, do_copy=True)


# get_listings()
#
# gets listings from elasticsearch & prettifies them
#
# returns a tuple of the number of records & a list listings;
# the listings are Bunches with extra info from the prettify method
#
def get_listings(query, number=50, offset=0, user=None, show='new_only'):

    querybody = query.query
    # limit results requested *and* query has date to limit to
    if query.mark_date and show == 'new_only':
        querybody = add_date_limit(querybody, query.mark_date)

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

    tossed = 0
    for item in search_resp['hits']['hits']:
        LOG.info('SCORE: ' + str(item['_score']) + '(' + str(item['_source']['static_quality']) + '/' + str(item['_source']['dynamic_quality']) + '/' + str(item['_source']['listing_date']) + '): ' + item['_source']['listing_text'][:20])
        car = Bunch(item['_source'])
        removal_date = force_date(car.removal_date, None)
        if int(car.id) in flag_set:
            pass  # throw it out
            tossed += 1
        elif removal_date and removal_date < now_utc():
            pass # expired, throw it out
            tossed += 1
        else:
            listing = prettify_listing(car,
                                       favorites=fav_dict,
                                       mark_since=query.mark_date)
            listings.append(listing)
    return search_resp['hits']['total'], listings, tossed


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
    LOG.info('user {} flagging the listing {} as {}{}'.format(user,
                                                              listing_id,
                                                              reason,
                                                              other_reason))
    remove = False
    if user.is_authenticated() and user.is_superuser:
        remove = True
    adj = calc_quality_adj(user, ACTION_FLAG, reason)
    listing = Listing.objects.get(pk=listing_id)
    if not listing:
        return False
    if not listing.dynamic_quality:
        listing.dynamic_quality = 0
    if listing.dynamic_quality + adj < -1100:  # arbitrary threshold :)
        remove = True

    apply_quality_adj(user, ACTION_FLAG, reason, adj, listing)

    if remove:
        es = Elasticsearch()
        try:
            es.delete(index="carbyr-index",
                      doc_type="listing-type",
                      id=listing_id)
        except NotFoundError as err:
            pass
        # load listing again to make sure it isn't stale (missing adj?)
        listing = Listing.objects.get(pk=listing_id)
        listing.status = 'X'
        listing.save()

    long_reason = reason
    if reason == FLAG_REASON_OTHER:
        long_reason = long_reason + ':' + other_reason
    log_action(user, ACTION_FLAG, long_reason, adj, listing)

    return True
