from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.utils.datastructures import MultiValueDictKeyError

# Create your views here.

def fubar(request):
    context = {'fubar': 'barfu'}
    return render(request, 'oglweb/index.html', context)

