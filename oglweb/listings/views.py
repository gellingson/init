# views.py

# builtin modules used
import datetime
import time

# third party modules used
#import simplejson as json
from bunch import Bunch
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.template import RequestContext
from django_ajax.decorators import ajax
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from django.core.mail import send_mail

# OGL modules used
from listings.constants import *
from listings.forms import UserForm
from listings.models import Zipcode, Listing
from listings.display_utils import prettify_listing
from listings.search_utils import *
from listings.query_utils import *
from listings.favlist_utils import *

# Create your views here.

def homepage(request):
    context = {}
    return render(request, HOMEPAGE, context)


def about(request, filter=None):
    context = {}
    return render(request, ABOUTPAGE, context)

@login_required
def profile(request):
    context = {}
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            print("valid form")
            user = request.user
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.username = form.cleaned_data['username']
            user.save()
            # now continue as per get: display the profile incl hidden form
        else:
            context['show_form'] = True  # redisplay (with errors)
            print("invalid form?!" + form.errors.as_json())
    else:  # GET, ie not form submission; populate blank form
        form = UserForm(initial={
            'id':request.user.id,
            'first_name':request.user.first_name,
            'last_name':request.user.last_name,
            'username':request.user.username,
        })
    context['form'] = form
    return render(request, 'account/profile.html', context)


@login_required
def dashboard(request):

    # get the favorites as a dict
    fav_dict = favdict_for_user(request.user)

    # and build a list of the listing records
    fav_list = list(fav_dict.items())
    listings = []

    listings = [ prettify_listing(Bunch(fav.listing.__dict__),
                                  favorites=fav_dict) for fav in list(fav_dict.values())]

    context = {}
    context['listings'] = listings
    return render(request, 'listings/dashboard.html', context)

# flag()
#
# flags a car as inappropriate; one flag from an admin kills a listing,
# but we should be a bit more cautious about other users. But it should
# block the ad for the particular user, as much as possible.
#
@login_required
@ajax
def flag_car_api(request):
    if request.method == 'POST':
        listing_id = request.POST['listing_id']
        reason = request.POST.get('reason', None)
        other_reason = request.POST.get('other_reason', None)

        result = flag_listing(request.user, listing_id, reason, other_reason)
        return {'result': result}
    return {'result': None}


# adminflag()
#
# GEE TODO: kill this because the ajax one (above) is better
#
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


# cars_api()
#
# pulls just the listings section (the listing items themselves and
# a next-page link) as a mini-page
#
# NOTES:
# for now this is used as an ajax endpoint for additional pages of listings
#
def cars_api(request, query_ref=None, number=50, offset=0):
    number = int(number)
    offset = int(offset)
    if not query_ref:
        recents = querylist_from_session(request.session, QUERYTYPE_RECENT)
        querybody = recents[0].query
    # GEE TODO: handle cases other than addl pages of the most recent search!
    total_hits, listings = get_listings(querybody, number=number, offset=offset,
                                        user=request.user)
    context = {}
    # this api may be pulling any page of the results; are there even more?
    if total_hits > (offset + number):
        context['next_page_offset'] = offset + number
    context['listings'] = listings
    return render(request, LISTINGSAPI, context)


# cars()
#
# this is the primary view for car search/results viewing
#
def cars(request, filter=None, base_url=None, query_ref=None, template=LISTINGSBASE, error_message=None):
    request.session['ogl_alpha_user'] = True  # been here, seen this = IN
    args = handle_search_args(request, filter, base_url, query_ref)
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

    print('DEBUG: ' + args.action + args.query_ref)
    # handle actions that may have been requested (e.g. save-query modal)
    if args.action == 'save_query':
        args.query_ref = save_query(args.query_ref, args.query_descr, request.session, request.user)
    elif args.action == 'unsave_query':
        unsave_query(args.query_ref, request.session, request.user)
    elif args.action == 'mark_read':
        mark_as_read(request.session, args.query_ref, args.query_date)

    # GEE TODO: put these in a db... and the session!
    # ... and be intelligent about which ones to pull for display

    query = None
    if args.query_ref:
        query = get_query_by_ref(request.session, args.query_ref)
    else:
        query = build_new_query(args)

    print("QUERY IS: " + str(query))
    # update recent searches list
    update_recents(request.session, query)

    total_hits, listings = get_listings(query.query, user=request.user, mark_since=query.mark_date)
    context = {}
    context['timestamp'] = time.time()  # may be used to set mark_date
    # this func returns the first page; will there be more?
    if total_hits > len(listings):
        context['next_page_offset'] = len(listings)
    # put saved queries into the context
    context['recents'] = []
    context['favorites'] = []
    context['suggestions'] = []
    i = 0
    recents = querylist_from_session(request.session, QUERYTYPE_RECENT)
    if recents:
        for search in recents:
            i += 1
            if i<3:
                context['recents'].append(search)
            else:
                if i == 3:
                    context['more_recents'] = []
                context['more_recents'].append(search)
    favorites = querylist_from_session(request.session, QUERYTYPE_FAVORITE)
    if favorites:
        context['favorites'] = favorites
    suggestions = SUGGESTED_SEARCH_LIST  # the ones selected to show now
    if suggestions:
        context['suggestions'] = list(suggestions.values())

    # GEE TODO: rename querytype field to type for consistency
    context['listings'] = listings
    context['query_descr'] = query.descr
    context['query_ref'] = query.ref
    context['query_type'] = query.type

    # GEE TODO: these next two seem like garbage I should clean up
    if error_message:
        context['error_message'] = error_message
    if base_url:
        context['abs_url'] = '/' + base_url

    return render(request, template, context)


# cars_test()
#
# this wraps cars() and adds/modifies the interface to be
# whatever is being worked on & isn't ready to share yet
#
def cars_test(request, base_url=None, query_ref=None):
    return cars(request, template=LISTINGSTEST, base_url=base_url, query_ref=query_ref)


# blank()
#
# should not be visited; convenience method for showing the blank base template
#
def blank(request):
    context = {}
    return render(request, 'listings/carbyrbase.html', context)


# statictest()
#
# should not be visited; convenience method for showing the static test page
# ... but this page can be a reasonable place to throw something exploratory
#
def statictest(request):
    context = {}
    return render(request, 'listings/carbyrtest.html', context)


# GEE TODO: remove this; it's temporary way to display a fixed html
def oldtest(request):
    return render(request, 'listings/oldtest.html')


# GEE TODO: kill this and incorporate admin into the primary template?
def listingadmin(request, error_message=None):
    return index(request, template=LISTINGSADMIN)


@ajax
@login_required
def save_car_api(request):
    if request.method == 'POST':
        listing_id = request.POST['listing_id']
        result = save_car_to_db(request.user, listing_id)
        return {'result': result}
    return {'result': None}


@ajax
@login_required
def unsave_car_api(request):
    if request.method == 'POST':
        listing_id = request.POST['listing_id']
        result = unsave_car_from_db(request.user, listing_id)
        return {'result': result}
    return {'result': None}
