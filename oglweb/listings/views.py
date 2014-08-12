from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.datastructures import MultiValueDictKeyError

from elasticsearch import Elasticsearch

# Create your views here.

from listings.models import Listing


# Create your views here.

def index(request):
    search_string = None
    listings = []
    try:
        search_string = request.GET['search_string']
    except MultiValueDictKeyError:
        pass
    if search_string:
        es = Elasticsearch()
        search_resp = es.search(index='carbyr-index', doc_type='listing-type', size=50, q=search_string)
        for item in search_resp['hits']['hits']:
            listings.append(item['_source'])
    else:
        listings = Listing.objects.all()
    context = {'listings': listings}
    return render(request, 'listings/index.html', context)

