# views.py

# builtin modules used
import datetime
import logging
import time
import urllib.parse

# third party modules used
#import simplejson as json
from bunch import Bunch
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.urlresolvers import reverse
from django.forms.models import model_to_dict
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.template import RequestContext
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt
from django_ajax.decorators import ajax
from elasticsearch import Elasticsearch
import humanize

# OGL modules used
from listings.actions import log_and_adj_quality
from listings.constants import *
from listings.display_utils import prettify_listing
from listings.favlist_utils import *
from listings.forms import UserForm
from listings.models import Zipcode, Listing
from listings.query_utils import *
from listings.search_utils import *
from listings.utils import *

LOG = logging.getLogger(__name__)

# Create your views here.


# landing()
#
# landing page to receive customers coming from promotional campaigns
#
# for now always goes to the homepage, but could do otherwise; logs
# and tracks the landing action, however...
#
def landing(request, page='home', ref=None):
    LOG.info('landing ({})'.format(ref))
    request.session['refer'] = ref  # store for later analysis (sign up?)
    if not ref and request.method == 'GET':
        # r ('r'eferer, or list 'r'eference) selects queries to feature
        ref = request.GET.get('r', 'home')
    context = {}
    queries = get_queries(ref)
    context['querylist'] = queries
    return render(request, LANDINGPAGE, context)


def homepage(request, ref=None):
    if not ref and request.method == 'GET':
        # r ('r'eferer, or list 'r'eference) selects queries to feature
        ref = request.GET.get('r', 'home')
    context = {}
    queries = get_queries(ref)
    context['querylist'] = queries
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
            user = request.user
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.username = form.cleaned_data['username']
            if form.cleaned_data['newsletter'] != (user.profile.newsletter == 'Y'):
                # GEE TODO: manage subscription change in mailchimp
                if form.cleaned_data['newsletter']:
                    LOG.info("user {} has subscribed to the newsletter".format(user.username))
                else:
                    LOG.info("user {} has unsubscribed from the newsletter".format(user.username))
            if form.cleaned_data['newsletter']:
                user.profile.newsletter = 'Y'
            else:
                user.profile.newsletter = 'N'
            user.save()
            user.profile.save()
            # now continue as per get: display the profile incl hidden form
        else:
            context['show_form'] = True  # redisplay (with errors)
    else:  # GET, ie not form submission; populate blank form
        form = UserForm(initial={
            'id':request.user.id,
            'first_name':request.user.first_name,
            'last_name':request.user.last_name,
            'username':request.user.username,
            'newsletter':(request.user.profile.newsletter == 'Y')
        })
    context['form'] = form
    if force_date(request.user.date_joined) > (now_utc() - datetime.timedelta(days=1)):
        context['new_user'] = True
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

# flag_car_api()
#
# ajax api: flags a car as inappropriate
#
@ajax
def flag_car_api(request):
    if request.method == 'POST':
        listing_id = request.POST['listing_id']
        reason = request.POST.get('reason', None)
        other_reason = request.POST.get('other_reason', None)

        result = flag_listing(request.user, listing_id, reason, other_reason)
        return {'result': result}
    return {'result': None}


# add_note_api()
#
# ajax api: adds a note to a favorite car
@ajax
def add_note_api(request):
    if request.method == 'POST':
        listing_id = request.POST['listing_id']
        note_contents = request.POST['listing_note']
        add_note(note_contents, request.user.id, listing_id)
        return {
            'result': True,
            'newcontents': note_contents
        }
    return {'result': None}


# adminflag() UNUSED
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
# this is used only as an ajax endpoint for additional pages of listings.
# this returns fully formated listing row HTML via a template, not raw JSON.
# this does NOT use the django-ajax framework. GEE TODO: switch it over.
#
def cars_api(request, query_ref=None, number=50, offset=0):

    if request.method == 'GET':
        number = int(number)
        offset = int(offset)
        if not query_ref:  # then look in the GET params
            query_ref = request.GET.get('q', None)
        q = None
        total_hits = 0
        listings = []

        if query_ref:
            q = get_query_by_ref(request.session, query_ref)
        # else we're toast; q will remain unset & will error out below

        context = {}
        if q:
            LOG.info('%s: api search: %s [%s]',
                     request.user.username or 'anon',
                     q.ref or '', q.descr)
            show = get_show_cars_option(request.session, q)

            total_hits, listings, tossed = get_listings(q,
                                                        number=number,
                                                        offset=offset,
                                                        user=request.user,
                                                        show=show)
            context['listings'] = listings
            # this api may be pulling any page of the results; are there even more?
            if total_hits > (offset + number):
                context['next_page_offset'] = offset + number
                context['query_ref'] = query_ref
            return render(request, LISTINGSAPI, context)

        else: # no query found to execute
            context['listings'] = []
            context['message'] = 'Unable to access query reference: {}'.format(
                query_ref)
            raise Http404  # GEE TODO: make a 404 response template


# cars()
#
# this is the primary view for car search/results viewing
#
# making this csrf_exempt to simplify actions/reloading after login/signup
#
@csrf_exempt
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
                error_message = 'Unknown zip code "{}"; geographic limit not applied.'.format(args.zip)
            else:
                error_message = 'ZIP code not understood; unable to sort by distance.'

    # handle actions that may have been requested (e.g. save-query modal)
    # these are all actions which post to the main cars URL so that they can
    # redisplay a (modified) listings page upon completion; these could have
    # been done as ajax calls too, but it was easier to implement these as
    # full posts that redraw the page rather than doing a bunch of post-ajax
    # javascript to "fix" the page to reflect the changes
    if args.action == 'save_query':
        args.query_ref = save_query(args.query_ref, args.query_descr, request.session, request.user)
    elif args.action == 'unsave_query':
        unsave_query(args.query_ref, request.session, request.user)
    elif args.action == 'mark_read':
        mark_as_read(args.query_ref, request.session, request.user, args.query_date)
        set_show_cars_option(request.session, 'new_only', args.query_ref)
    elif args.action == 'new_only' or args.action == 'all_cars':
        set_show_cars_option(request.session, args.action, args.query_ref)

    # GEE TODO: put suggested queries in a db... and the session!
    # ... and be intelligent about which ones to pull for display

    query = None
    if args.query_ref:
        query = get_query_by_ref(request.session, args.query_ref)
        if not query:
            LOG.error('oops! failed to find referenced query: ' + args.query_ref)
    if not query:  # was an else, but better to fall through/try to build query
        query = build_new_query(args)

    if not query:
        LOG.error('oops! no query!')
        # GEE TODO: some real handling that informs the user, is sane, etc
        return HttpResponseRedirect(reverse('about'))

    show = get_show_cars_option(request.session, query)

    # update recent searches list (also updates the query param)
    update_recents(request.session, query)

    LOG.info('%s: search: %s [%s]',
             request.user.username or 'anon',
             query.ref or '', query.descr)

    total_hits, listings, tossed = get_listings(query,
                                                user=request.user,
                                                show=show)
    context = {}
    # this func returns the first page; will there be more?
    if total_hits > len(listings) + tossed:
        context['next_page_offset'] = len(listings) + tossed
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
    recents = querylist_from_session(request.session, QUERYTYPE_RECENT)
    if query.mark_date:
        d = utc_to_naive_local_tz(force_date(query.mark_date))
        context['query_mark_date'] = humanize.naturaltime(d)
    context['show'] = show
    # record timestamp at which query was issued; used e.g. to set mark_date
    context['query_timestamp'] = now_utc().isoformat()

    # repop search form with the values of the current ad-hoc or saved query
    populate_search_context(context, args, query)
    
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
# making this csrf_exempt to simplify actions/reloading after login/signup
#
@csrf_exempt
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
def save_car_api(request):
    #LOG.info(request.user)
    if request.method == 'POST':
        listing_id = request.POST['listing_id']
        result = save_car_to_db(request.user, listing_id)
        return {'result': result}
    return {'result': None}


@ajax
def unsave_car_api(request):
    if request.method == 'POST':
        listing_id = request.POST['listing_id']
        result = unsave_car_from_db(request.user, listing_id)
        return {'result': result}
    return {'result': None}


# view_car_api
#
# return 
@ajax
def view_car_api(request):
    if request.method == 'POST':
        listing_id = request.POST['listing_id']
        LOG.debug('view_car_api request for listing ID ' + str(listing_id))
        listing = Listing.objects.get(pk=listing_id)
        # do nothing but register the action for now
        log_and_adj_quality(request.user, ACTION_VIEW, listing=listing)
        fav_dict = {}
        if request.user.is_authenticated():
            fav_dict = favdict_for_user(request.user)
        pretty_listing = prettify_listing(Bunch(model_to_dict(listing)),
                                          fav_dict)
        # GEE TODO: understand where the fucking "_state" db thing comes from
        # and deal with all the datetime and decimals that don't do json :(
        #pretty_listing.pop("_state", None)
        pretty_listing.pop("lat", None)
        pretty_listing.pop("lon", None)
        pretty_listing.pop("last_update", None)
        pretty_listing.pop("listing_date", None)
        pretty_listing.pop("removal_date", None)
        LOG.debug(json.dumps(pretty_listing, indent=4, sort_keys=True))
        return {'listing': pretty_listing}
    return {'result': None}

# view_car
#
# views a single car (by listing_id)
#
def view_car(request):
    listing_id = request.GET['listing_id']
    LOG.info('view listing ID is ' + str(listing_id))
    listing = Listing.objects.get(pk=listing_id)
    fav_dict = {}
    if request.user.is_authenticated():
        fav_dict = favdict_for_user(request.user)
    pretty_listing = prettify_listing(Bunch(model_to_dict(listing)),
                                      fav_dict)
    context = {}
    context['listing'] = pretty_listing
    context['testdata'] = 'somedata'
    context['item'] = pretty_listing
    return render(request, 'listings/viewcar.html', context)

# redirect_to_original_listing
#
# tracks the fact that the user is clicking through, then sends them off...
#
def redirect_to_original_listing(request):
    listing_id = request.GET['listing_id']
    listing = Listing.objects.get(pk=listing_id)
    log_and_adj_quality(request.user, ACTION_CLICKTHROUGH, listing=listing)
    return HttpResponseRedirect(listing.listing_href)
    
