
import copy
import datetime
import pytz
import time

# third party modules used
from bunch import Bunch
from django.utils.datastructures import MultiValueDictKeyError
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from money import Money

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
        if query.type == QUERYTYPE_DEFAULT::  # default query, no parms
            return
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
    q.type = QUERYTYPE_RECENT  # presume we have some args (checked below)
    descr_list = [] # used to assemble the descr of the query

    # building the query string:

    # querybody components
    filter_term = args.get('filter_term', None)
    geolimit_term = ''
    search_term = ''
    price_term = ''
    year_term = ''

    if not args.has_criteria:
        # no criteria at all; don't retrieve everything; give
        # cars from the last few days
        q.type = QUERYTYPE_DEFAULT
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
        descr_list.append("recently-listed cars")
    elif args.query_string:
        search_term = {
            "query_string": {
                "query": args.query_string,
                "default_operator": "AND"
            }
        }
        descr_list.append(args.query_string)
    else:
        descr_list.append('cars') # default first term of the query description

    if args.limit:
        # go ahead and use implicit zip if the user requests a limit func...
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
            descr_list.append('near ' + args.zip)

    if args.min_price or args.max_price:
        price_term = {
            "range": {
                "price": {
                }
            }
        }
        price_descr = ''
        min_pretty = None
        max_pretty = None
        if args.min_price:
            price_term['range']['price']['gte'] = args.min_price
            min_pretty = Money(args.min_price, 'USD').format('en_US', '$#,###')
        price_descr = price_descr + 'price'
        if args.max_price:
            price_term['range']['price']['lte'] = args.max_price
            max_pretty = Money(args.max_price, 'USD').format('en_US', '$#,###')
        if min_pretty and max_pretty:
            price_descr = min_pretty + ' to ' + max_pretty
        elif min_pretty:
            price_descr = 'over ' + min_pretty
        else:
            price_descr = 'under ' + max_pretty
        descr_list.append(price_descr)

    if args.min_year or args.max_year:
        year_term = {
            "range": {
                "model_year": {
                }
            }
        }
        year_descr = ''
        if args.min_year:
            year_term['range']['model_year']['gte'] = args.min_year
        if args.max_year:
            year_term['range']['model_year']['lte'] = args.max_year
        if args.min_year and args.max_year:
            year_descr = 'model year between ' + str(args.min_year) + ' and ' + str(args.max_year)
        elif args.min_year:
            year_descr = 'model year ' + str(args.min_year) + ' and newer'
        else:
            year_descr = 'model year ' + str(args.max_year) + ' and older'
        descr_list.append(year_descr)

    # sorting not currently exposed in the search UI
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
    if geolimit_term:
        add_filter(q.query, geolimit_term)

    # filter term is dead code now (dec '14)
    if filter_term:
        add_filter(q.query, filter_term)
    if price_term:
        add_filter(q.query, price_term)
    if year_term:
        add_filter(q.query, year_term)
    if sort_term:
        q.query['sort'] = sort_term

    # build query description out of all the descr_list terms
    q.descr = ', '.join(descr_list)

    LOG.info('NEW ES QUERY: ' + str(q.query))
    # return the user-friendly description and the actual es query body
    return q


# add_filter()
#
# adds a filtering clause to an es query
# NOTE: optionally deep copies & then returns a new querybody!
#
def add_filter(querybody, new_filter, copy=False):
    if copy:
        copybody = copy.deepcopy(querybody)
    else:
        copybody = querybody
    if not 'filter' in copybody['query']['filtered']:
        # then this is the first filter; add the filtering cruft
        copybody['query']['filtered']['filter'] = {}
        copybody['query']['filtered']['filter']['and'] = []
    copybody['query']['filtered']['filter']['and'].append(new_filter)
    return copybody


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
    return add_filter(querybody, date_term, copy=True)


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

    for item in search_resp['hits']['hits']:
        if int(item['_source']['id']) in flag_set:
            pass  # throw it out
        else:
            listing = prettify_listing(Bunch(item['_source']),
                                       favorites=fav_dict,
                                       mark_since=query.mark_date)
            listings.append(listing)
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
    LOG.info('user {} flagging the listing {} as {}{}'.format(user,
                                                              listing_id,
                                                              reason,
                                                              other_reason))
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
        
