
from bunch import Bunch
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.datastructures import MultiValueDictKeyError

from elasticsearch import Elasticsearch

from listings.models import Listing
from listings.display_utils import prettify_listing

# GLOBALS

# GEE TODO -- should probably move these to the db
# for now, to add a filter (sub-site) add it here & in db section below
_VALID_FILTERS = {'miatas': 'model:miata',
                  'corvettes': 'model:corvette',
                  'classics': 'model_year<1975'
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

    search_filter = ''

    # put current page into the context so we post back to the same URL
    context['post_url'] = request.path_info

    if filter:
        print('filter detected: {}'.format(filter));
        if filter in _VALID_FILTERS:
            #error_message = 'Limiting as per filter {}: {}'.format(filter, _VALID_FILTERS[filter])
            search_filter = _VALID_FILTERS[filter]
        else:
            #error_message = 'Invalid filter {}'.format(filter)
            # go to the main page sans filter
            print("REDIRECTING")
            return HttpResponseRedirect(reverse('allcars'))
#    else:
        #print('filter NOT detected');

    # get listings to display
    search_string = ''
    listings = []
    search_criteria = 'most recently-listed cars'

    try:
        search_string = request.GET['search_string']
    except MultiValueDictKeyError:
        pass  # no criteria specified; get recent listings
    print('filter string is {}'.format(search_filter))
    print('search string is {}'.format(search_string))
    if search_string:
        es = Elasticsearch()
        if search_filter:
            final_string = '(' + search_filter + ')&&(' + search_string + ')'
        else:
            final_string = search_string
        search_resp = es.search(index='carbyr-index',
                                doc_type='listing-type',
                                size=50,
                                q=(final_string))
        search_criteria = search_string  # for display; filter is implied
        for item in search_resp['hits']['hits']:
            es_listing = prettify_listing(Bunch(item['_source']))
            listings.append(es_listing)
    else:
        # GEE TODO: this is a db pull so these are Listings, whereas
        # other case is es search thus es hashes. Reconcile!!

        # GEE TODO: if we keep doing db-based searches then we need to
        # pickle a filtered queryset object & attach it to the valid
        # filters list, and do similar for user-owned queries (if supptd).
        # But we can do this 1-off for now and hope to retire db-based
        # searches before we need to generalize them....
        if search_filter == 'model:corvette':
            queryset = Listing.objects.filter(model__startswith='Corvette')
        elif search_filter == 'model:miata':
            queryset = Listing.objects.filter(model__startswith='Miata')
        elif search_filter == 'model_year<1975':
            queryset = Listing.objects.filter(model_year__lt='1975')
        else:  # no filter
            queryset = Listing.objects.all()

        latest_listings = queryset.order_by('-last_update')[:50]

        for item in latest_listings:
            listings.append(prettify_listing(item))

    context['listings'] = listings
    context['search_criteria'] = search_criteria
    if error_message:
        context['error_message'] = error_message

    return render(request, 'listings/index.html', context)

