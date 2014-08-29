from urllib.parse import urlparse

from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.datastructures import MultiValueDictKeyError

from bunch import Bunch
from money import Money
#import babel
from elasticsearch import Elasticsearch

from listings.models import Listing

# Create your views here.

def homepage(request):
    context = {'fubar': 'barfu'}
    return render(request, 'listings/homepage.html', context)
    
def index(request):
    def prettify_listing(listing):
        if listing.price == -1:
            listing.price = 'Contact for price'
        else:
            m = Money(listing.price, 'USD')
            listing.price = m.format('en_US')
        return listing
        p = urlparse(listing.pic_href)
        if not p.netloc:
            # relative URL means we have a problem
            listing.pic_href = ''
    
    search_string = None
    listings = []
    search_criteria = 'latest interesting cars'
    try:
        search_string = request.GET['search_string']
    except MultiValueDictKeyError:
        pass
    if search_string:
        es = Elasticsearch()
        search_resp = es.search(index='carbyr-index', doc_type='listing-type', size=50, q=search_string)
        for item in search_resp['hits']['hits']:
            es_listing = prettify_listing(Bunch(item['_source']))
            listings.append(es_listing)
        search_criteria = search_string
    else:
        listings = Listing.objects.all().order_by('-last_update')
        # GEE TODO: these are Listings, whereas other case are es hashes. Reconcile!!

    context = {'listings': listings,
               'search_criteria': search_criteria}
    return render(request, 'listings/index.html', context)

