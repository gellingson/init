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
from listings.constants import *
from listings.forms import UserForm
from listings.models import Zipcode, Listing
from listings.display_utils import prettify_listing
from listings.search_utils import handle_search_args, build_query, save_query, unsave_query, get_listings, save_car, save_car_to_db, unsave_car, favdict_for_user

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
    #for fav in fav_list:
    #    listings.append(prettify_listing(Bunch(fav.listing), favorites=fav_dict))
    listings = [ prettify_listing(Bunch(fav.listing.__dict__), favorites=fav_dict) for fav in list(fav_dict.values())]

    # code that gets the favorites from the session (not the db)
    #for listing_id in savedcars:
    #    listings.append(prettify_listing(Bunch(Listing.objects.get(pk=listing_id)),
    #                                     all_favorites=True))    

    context = {}
    context['listings'] = listings
    return render(request, 'listings/dashboard.html', context)


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
def cars_api(request, search_id=None, number=50, offset=0):
    number = int(number)
    offset = int(offset)
    if not search_id:
        recents = request.session.get('recents', [])
        querybody = recents[0]['query']
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
def cars(request, filter=None, base_url=None, search_id=None, template=LISTINGSBASE, error_message=None):
    search_type = None
    request.session['ogl_alpha_user'] = True  # been here, seen this = IN

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

    # handle save-query modal
    if args.save_id and args.save_desc:
        args.search_id = save_query(args.save_id, args.save_desc, request)
    elif args.unsave_id:
        unsave_query(args.unsave_id, request)

    recents = request.session.get('recents', [])
    favorites = request.session.get('favorites', [])
    # GEE TODO: put these in a db...
    # ... and be intelligent about which ones to pull for display
    suggested_lib = SUGGESTED_SEARCH_LIST  # all suggested searches
    suggestions = SUGGESTED_SEARCH_LIST  # the ones selected to show now
    stored_search = None
    if args.search_id:
        # look in recents
        if recents and args.search_id.startswith('R'):
            for search in recents:
                if search['id'] == args.search_id:
                    stored_search = search
                    search_type = 'R'
                    break
        if favorites and args.search_id.startswith('F'):
            for search in favorites:
                if search['id'] == args.search_id:
                    stored_search = search
                    search_type = 'F'
                    break
        if suggested_lib and args.search_id.startswith('_'):
            for search in suggested_lib:
                if search == args.search_id:
                    stored_search = suggested_lib[search]
                    search_type = 'S'
                    break

    search_desc = querybody = None
    if stored_search:  # then do it
        search_id = stored_search['id']
        search_desc = stored_search['desc']
        querybody = stored_search['query']
        print('<{}>'.format(querybody))
    else:  # new search via the search form params
        querybody, search_desc, search_type = build_query(args)

    #print(querybody)
    if search_type == 'D':
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

    total_hits, listings = get_listings(querybody, user=request.user)
    context = {}
    # this func is always doing the first page; will there be more?
    if total_hits > len(listings):
        context['next_page_offset'] = len(listings)
    context['recents'] = []
    context['favorites'] = []
    context['suggestions'] = []
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
    if favorites:
        for search in favorites:
            context['favorites'].append(search)
    if suggestions:
        for search in suggestions:
            context['suggestions'].append(suggestions[search])

    context['listings'] = listings
    context['search_desc'] = search_desc
    # if showing a stored or suggested search use that id, not from recents
    # (the search will also be entered in the recents array with an Rid)
    if stored_search:
        context['search_id'] = stored_search['id']
    elif recents:
        context['search_id'] = recents[0]['id']

    context['search_type'] = search_type

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
def cars_test(request, base_url=None, search_id=None):
    return cars(request, template=LISTINGSTEST, base_url=base_url, search_id=search_id)


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
        return {'result': True}
    return {'result': None}


@ajax
@login_required
def unsave_car_api(request):
    if request.method == 'POST':
        listing_id = request.POST['listing_id']
        result = unsave_car(request.session, listing_id)
        return {'result': result}
    return {'result': None}
