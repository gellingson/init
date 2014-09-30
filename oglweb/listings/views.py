# views.py

# builtin modules used
import datetime
import time

# third party modules used
#import simplejson as json
from bunch import Bunch
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.template import RequestContext
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError

from listings.constants import *
from listings.display_utils import prettify_listing
from listings.models import Zipcode, Listing
from listings.search_utils import handle_search_args, build_query

# Create your views here.

def homepage(request):
    context = {'fubar': 'barfu'}
    return render(request, 'listings/homepage.html', context)


def about(request, filter=None):
    context = {'fubar': 'barfu'}
    if filter=='miatas':
        return render(request, 'listings/miatas-about.html', context)
    else:
        return render(request, ABOUTBASE, context)


def listingadmin(request, error_message=None):
    return index(request, template=LISTINGSADMIN)


def adminflag(request, id=None):
    if id:
        es = Elasticsearch()
        es.delete(index="carbyr-index",
                  doc_type="listing-type",
                  id=id)
        listing = Listing.objects.get(pk=id)
        listing.status = 'X'
        # GEE TODO: hmm, error_message won't make it through the redirect, and neither will the query string. Need to improve this!
        error_message = 'Flagged item {}: {} {} {}'.format(id, listing.model_year, listing.make, listing.model)
        return HttpResponseRedirect(reverse('allcarsadmin'))


def index(request, filter=None, base_url=None, search_id=None, template=LISTINGSBASE, error_message=None):
    print('base_url is "{}"'.format(base_url))
    args = handle_search_args(request, filter, base_url, search_id)
    if args.errors:
        # handle catastrophic errors
        if 'invalid_filter' in args.errors:
            return HttpResponseRedirect(reverse('allcars'))
        # queue up any messages related to nonfatal errors
        if 'invalid_zip' in args.errors:
            if args.limit:
                error_message = 'Unknown zip code "{}"; geographic limit not applied.'.format(zip)
            else:
                error_message = 'ZIP code not understood; unable to sort by distance.'

    recents = request.session.get('recents', [])
    stored_search = None
    if args.search_id:
        # look in recents
        if recents:
            for search in recents:
                if search['id'] == args.search_id:
                    stored_search = search
                    break
        # GEE TODO and in stored searches and canned searches

    search_desc = querybody = None
    if stored_search:  # then do it
        search_desc = stored_search['desc']
        querybody = stored_search['query']
    else:  # new search via the search form params
        search_desc, querybody = build_query(args)

    if search_desc == 'recently-listed cars':
        pass
    elif recents and recents[0]['desc'] == search_desc: # GEE TODO: match any recent in the list
        # same query as last one, or nearly; update any minor change
        recents[0]['query'] = querybody
    else:
        srchid = 'R' + str(datetime.date.today()) + '_' + str(int(round(time.time() * 1000)))
        item = {'id': srchid, 'desc': search_desc, 'query': querybody}
        recents.insert(0, item)
    while len(recents) > 10:
        recents.pop()

    request.session['recents'] = recents

    es = Elasticsearch()
    search_resp = es.search(index='carbyr-index',
                            doc_type='listing-type',
                            size=50,
                            body=querybody)
    listings = []
    for item in search_resp['hits']['hits']:
        es_listing = prettify_listing(Bunch(item['_source']))
        listings.append(es_listing)

    context = {}
    context['recents'] = []
    i = 0
    if recents:
        for search in recents:
            i += 1
            if i<3:
                context['recents'].append(search)
            else:
                if i == 3:
                    context['more_recents'] = []
                context['more_recents'].append(search)

    context['listings'] = listings
    context['search_desc'] = search_desc
    if recents:  # GEE TODO: ... and this isn't already a saved search
        context['search_id'] = recents[0]['id']
    if error_message:
        context['error_message'] = error_message
    if base_url:
        context['abs_url'] = '/' + base_url
    return render(request, template, context)


def test(request, base_url=None, search_id=None):
    return index(request, template=LISTINGSTEST, base_url=base_url, search_id=search_id, error_message='You are using the beta Carbyr interface.')


def oldtest(request):
    return render(request, 'listings/oldtest.html')


