
import datetime
import time

# third party modules used
from bunch import Bunch
from django.utils.datastructures import MultiValueDictKeyError
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

# OGL modules used
from listings.display_utils import prettify_listing
from listings.models import Zipcode
from listings.constants import *

#
# builds an es query based on request vars
#
# factored out into a utility method to facilitate multiple search views/urls
#

def handle_search_args(request, filter=None, base_url = None, search_id=None):

    args = Bunch()
    args.errors = {}
    args.sort = "relevance"

    # POST params
    args.save_id = request.POST.get('save_id', '')
    args.save_desc = request.POST.get('save_desc', '')
    args.unsave_id = request.POST.get('unsave_id', '')

    # GET params
    if base_url:
        args.base_url = base_url
    else:
        args.base_url = request.GET.get('base_url', 'cars/')

    if search_id:
        args.search_id = search_id
    else:
        args.search_id = request.GET.get('s','')

    args.search_string = request.GET.get('search_string', '')

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

    #print('params:', str(args))
    return args


def build_query(args):
    # querybody components
    filter_term = args.get('filter_term', None)
    geolimit_term = ''
    search_term = ''
    search_type = 'U'  # presume we have some args from user (checked below)

    if args.search_string:
        search_term = {
            "query_string": {
                "query": args.search_string,
                "default_operator": "AND"
            }
        }
    else:
        if not args.limit:
            # no criteria at all; don't retrieve everything; give
            # cars from the last few days
            args.search_string = "recently-listed cars"
            search_type = 'D'  # default search
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
    querybody = {"query": {"filtered": {}}}
    if search_term:
        querybody['query']['filtered']['query'] = search_term
    if geolimit_term or filter_term:
        querybody['query']['filtered']['filter'] = {}
        querybody['query']['filtered']['filter']['and'] = []
        if geolimit_term:
            querybody['query']['filtered']['filter']['and'].append(geolimit_term)
        if filter_term:
            querybody['query']['filtered']['filter']['and'].append(filter_term)
    if sort_term:
        querybody['sort'] = sort_term

    # so... how shall we describe this query to the user?
    if geolimit_term:
        if args.search_string:
            search_desc = args.search_string + ", near " + args.zip
        else:
            search_desc = "cars near " + args.zip
    else:
        search_desc = args.search_string

    # return the user-friendly description and the actual es query body
    return querybody, search_desc, search_type


def save_query(id, desc, request):
    recents = request.session.get('recents', [])
    favorites = request.session.get('favorites', [])
    from_search = None
    # id will normally be in recents[0] but let's be flexible just in case
    if recents and id.startswith('R'):
        for search in recents:
            if search['id'] == id:
                from_search = search.copy()
                break
    if from_search:
        from_search['id'] = 'F' + from_search['id'][1:]
        from_search['desc'] = desc
        favorites.append(from_search)
        request.session['favorites'] = favorites
        return from_search['id']  # show it now...
    # else fail silently
    return None


def get_listings(querybody, number=50, offset=0):
    es = Elasticsearch()
    search_resp = es.search(index='carbyr-index',
                            doc_type='listing-type',
                            size=number,
                            from_=offset,
                            body=querybody)
    listings = []
    for item in search_resp['hits']['hits']:
        es_listing = prettify_listing(Bunch(item['_source']))
        listings.append(es_listing)
    return search_resp['hits']['total'], listings


def unsave_query(id, request):
    favorites = request.session.get('favorites', [])
    if favorites:
        i = 0
        while i < len(favorites):
            if favorites[i]['id'] == id:
                favorites.pop(i)
                request.session['favorites'] = favorites
                break
            i += 1
    return
