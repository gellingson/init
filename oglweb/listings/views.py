# views.py

import datetime
import time
import json

from bunch import Bunch
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.datastructures import MultiValueDictKeyError

from elasticsearch import Elasticsearch

from listings.models import Zipcode
from listings.display_utils import prettify_listing

# GLOBALS

# GEE TODO -- should probably move these to the db
# for now, to add a filter (sub-site) add it here & in db section below
_VALID_FILTERS = {'miatas': { "term": { "model": "miata"}},
                  'corvettes': { "term": { "model": "corvette"}},
                  'classics': { "range": { "model_year": { "to": "1975"}}}
}

# Create your views here.

def homepage(request):
    context = {'fubar': 'barfu'}
    return render(request, 'listings/homepage.html', context)


def about(request, filter=None):
    context = {'fubar': 'barfu'}
    if filter=='miatas':
        return render(request, 'listings/miatas-about.html', context)
    else:
        return render(request, 'listings/about.html', context)


def index(request, filter=None):

    error_message = None
    context = {}

    # querybody components
    filter_term = ''
    geolimit_term = ''
    search_term = ''

    # put current page into the context so we post back to the same URL
    context['post_url'] = request.path_info

    if filter:
        if filter in _VALID_FILTERS:
            #error_message = 'Limiting as per filter {}: {}'.format(filter, _VALID_FILTERS[filter])
            filter_term = _VALID_FILTERS[filter]
        else:
            #error_message = 'Invalid filter {}'.format(filter)
            # go to the main page sans filter
            return HttpResponseRedirect(reverse('allcars'))

    # get listings to display

    # GET params
    search_string = ''
    limit = ''
    zip = ''

    listings = []
    search_criteria = 'most recently-listed cars'  # default

    try:
        search_string = request.GET['search_string']
    except MultiValueDictKeyError:
        pass  # no criteria specified; get recent listings
    try:
        limit = request.GET['limit']
    except MultiValueDictKeyError:
        pass  # no criteria specified; get recent listings
    try:
        zip = request.GET['zip']
    except MultiValueDictKeyError:
        pass  # no criteria specified; get recent listings
        
    #print('params:', search_string, limit, zip)

    es = Elasticsearch()
    if search_string:
        search_term = {
            "query_string": {
                "query": search_string,
                "default_operator": "AND"
            }
        }
    else:
        if limit != "on":
            # no criteria at all; don't retrieve everything; give
            # cars from the last few days
            search_string = "recently-listed cars"
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

    ziperror = False
    lat = lon = 0
    if not zip:
        zip = "95112"
    try:
        zipcode = Zipcode.objects.get(zip=zip)
        lat = float(zipcode.lat)
        lon = float(zipcode.lon)
    except Zipcode.DoesNotExist:
        ziperror = True

    if limit=="on" and zip:
        if ziperror:
            error_message = 'Unknown zip code "{}"; geographic limit not applied.'.format(zip)
        else:
            geolimit_term = {
                "geo_distance" : {
                    "distance": "100mi",
                    "location": {
                        "lat": lat,
                        "lon": lon
                    }
                }
            }
            if search_string:
                search_string = search_string + ", near " + zip
            else:
                search_string = "cars near " + zip
        
    sort_term = [
        {
            "_geo_distance": {
                "location": {
                    "lat": lat,
                    "lon": lon
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
            
    print(json.dumps(querybody, indent=4, sort_keys=True))
    search_resp = es.search(index='carbyr-index',
                            doc_type='listing-type',
                            size=50,
                            body=querybody)
    search_criteria = search_string  # for display; filter is implied
    for item in search_resp['hits']['hits']:
        es_listing = prettify_listing(Bunch(item['_source']))
        listings.append(es_listing)

    context['listings'] = listings
    context['search_criteria'] = search_criteria
    if error_message:
        context['error_message'] = error_message

    return render(request, 'listings/index.html', context)

