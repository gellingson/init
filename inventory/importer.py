#!/usr/bin/env python3
#
# importer.py
#
# this is the main import script for grabbing inventory from various sources
#
# NOTES:
# GEE TODO currency handling

# builtin modules used
import argparse
from collections import defaultdict
import datetime
from decimal import Decimal
import errno
import simplejson as json  # handles Decimal fields; regular json does not
import logging
import os
import pytz
import re
import socket
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

# third party modules used
from bunch import Bunch
from bs4 import BeautifulSoup, NavigableString, Comment
from ebaysdk.finding import Connection as ebaysdk_finding
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
import iso8601
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# OGL modules used
from inventory.settings import XL, _HDRS
from inventory.settings import _BORING_MAKES, _INTERESTING_MODELS, _INTERESTING_WORDS
from inventory.settings import _MAKES, _MODELS, _TAGS, _TAG_RELS, load_refdata_cache
import inventory.utils as u
from inventory.tagging import tagify
from inventory.threetaps import pull_3taps_inventory
from orm.models import Classified, Dealership
from orm.models import Listing, ListingSourceinfo
from orm.models import ConceptTag, ConceptImplies
from orm.models import NonCanonicalMake, NonCanonicalModel, Zipcode


# always use module name as LOG, never __main__
LOG = logging.getLogger('inventory.importer')


# ============================================================================
# PARSING METHODS
# ============================================================================

# placeholder method to copy-and-paste to form a new dealership-specific parse
#
def new_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing.model_year,
     listing.make,
     listing.model) = u.regularize_year_make_model('')

    listing.listing_text = ''

    # pull the rest of the fields from the detail page

    listing.price = u.regularize_price('')

    return True


# autorevo_parse_listing
#
# developed to load VIP motors, and hopefully also works with other dealers
# who use autorevo for their inventory listings.
#
def autorevo_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing.model_year,
     listing.make,
     listing.model) = u.regularize_year_make_model(entry.find('h1').text)

    try:
        listing.price = u.regularize_price(
            entry.find(class_='vehicleMainPriceRow').text)
    except AttributeError:
        listing.price = -1

    # doesn't have listing text on inventory page
    try:
        listing.listing_text = detail.find(
            class_='innerDescriptionText').find('p').text.strip()
    except AttributeError:
        listing.listing_text = ''

    # inv page thumbs are tiny; try to find an image from the detail page
    pic = detail.find('img', id='detailMainPhoto')
    if pic:
        listing.pic_href = pic.attrs['src']

    return True

# bat_parse_listing
#
# parses Bring A Trailer Auctions listings
#
# implementing this as a dealership for now because we don't have
# generic classified handling yet
#
def bat_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    title = entry.find(class_="current-listing-details-title-link")
    if title:
        (listing.model_year,
         listing.make,
         listing.model) = u.regularize_year_make_model(title.text)

    text = entry.find(class_="current-listing-details-excerpt")
    if text:
        if text.find('p'):
            listing.listing_text = text.find('p').text.strip()

    price_button_div = entry.find(class_="current-listing-details-button")
    if price_button_div:
        if price_button_div.find('a'):
            price_string = price_button_div.find('a').text
            try:
                price_string = price_string.split(':')[1]
            except:
                pass
            listing.price = u.regularize_price(price_string)

    # pull the rest of the fields from the detail page

    # so far, this is my only "dealership" where location varies by car.
    # we can pull location text but let's not try to infer zip yet

    listing.location_text = 'contact for location'
    location_li = detail.find('li',
                              class_='listing-essential-item',
                              text=re.compile('Location:'))
    if location_li:
        try:
            listing.location_text = location_li.text.split(':')[1].strip()
        except:
            pass
    

    return True


# carbuffs_parse_listing
#
#
def carbuffs_parse_listing(listing, entry, detail):

    # get the short listing text from the inventory page
    listing.listing_text = entry.find(class_="car-excerpt").text.strip()

    # pull the rest of the fields from the detail page
    (listing.model_year,
     listing.make,
     listing.model) = u.regularize_year_make_model(
         detail.find(class_='car-name').text)

    # common name/value patterns in details page:
    # <li><strong>Car model year:</strong> 1963</li>
    # <p class="car-asking-price"><strong>Asking Price:</strong> $89,950</p>
    pe = detail.find('strong', text='Asking Price:')
    if pe is not None:
        pe = pe.next_sibling
    listing.price = u.regularize_price(pe)

    return True


def ccw_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing.model_year,
     listing.make,
     listing.model) = u.regularize_year_make_model(entry.find('strong').text)

    # no short text available, only longer text from detail page
    listing.listing_text = ''

    # pull the rest of the fields from the detail page

    return True


# cfc_parse_listing
#
def cfc_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing.model_year,
     listing.make,
     listing.model) = u.regularize_year_make_model(entry.find('a').text)

    listing.listing_text = '' # no crisp text, just long text

    return True


# cvc_parse_listing
#
def cvc_parse_listing(listing, entry, detail):

    # this site is super-sparse, with no useful tagging...
    # we just have to make the best of it

    # get year/make/model and short listing text from the inventory page

    strings = entry.find_all(text=True)

    (listing.model_year,
     listing.make,
     listing.model) = u.regularize_year_make_model(strings[0])

    listing.listing_text = strings[1].strip()

    # no real patterns to mine on the details page.
    # but hey, at least it has the price! (unlike the inventory page)
    pe = detail.find(text=re.compile(r'Asking Price:'))
    if pe is not None:
        pe = pe.split(':')[-1]
    listing.price = u.regularize_price(pe)

    # inv page thumbs are small but the detail page uses dynamically-created
    # pic hrefs that are not worth sorting out

    return True


# dawydiak_parse_listing
#
# used for both porsche and non-porsche inventory from Cars Dawydiak
#
def dawydiak_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page

    # if dawydiak has any listing text, it's in the introlist
    listing.listing_text = entry.find(class_='introlist').text.strip()

    if entry.find(class_='dscprice'):
        listing.price = u.regularize_price(entry.find(class_='dscprice').text)

    # pull the rest of the fields from the detail page
    listing.model_year = detail.find(
        'dt', text=re.compile(r'Year:')).parent.dd.text
    listing.make = detail.find(
        'dt', text=re.compile(r'Make:')).parent.dd.text
    listing.model = detail.find(
        'dt', text=re.compile(r'Model:')).parent.dd.text

    listing.local_id = detail.find(
        'dt', text=re.compile(r'Stock')).parent.dd.text
    listing.stock_no = listing.local_id # no separate stock#

    return True


# fj_parse_listing
#
def fj_parse_listing(listing, entry, detail):

    # get the year/make/model from listing or detail page
    # note: it is also in the detail header, but we've chucked that :(
    s = None
    if entry.find('h1'):
        s = entry.find('h1').text
    elif detail.find('h1', class_='entry-header'):
        s = detail.find('h1', class_='entry-header').text
    s = s.split(', ')[0]  # take of trailing content, e.g. ', s/n 1234'
    LOG.debug('FJ: title is: %s', s)
    (listing.model_year,
     listing.make,
     listing.model) = u.regularize_year_make_model(s)

    # and short listing text from the inventory page
    listing.listing_text = entry.find(class_="entry-subheader blue").get_text().strip()

    # now hack the pic href to get a larger one (also have /large/ available)
    listing.pic_href = listing.pic_href.replace('/small/',
                                                '/medium/')

    # pull the rest of the fields from the detail page

    foo = detail.find(id="ContactCarId")
    if foo:
        listing.local_id = foo['value']
    listing.stock_no = listing.local_id # no separate stock#

    # many interesting items are in an "alpha-inner-bottom' div,
    # but for now just grab price
    # tabular format with labels & values in two td elements, e.g.:
    # <tr>
    # <td class="car-detail-name">Price</td>
    # <td class="car-detail-value"> $42,500</td>
    # </tr>
    elt = detail.find(id='alpha-inner-bottom')
    price_string = elt.find(
        "td", text="Price").parent.find('td', class_="car-detail-value").text
    listing.price = u.regularize_price(price_string)

    return True


# lc_parse_listing
#
# this method handles both left coast classics (lcc) and
# left coast exotics (lce)
#
def lc_parse_listing(listing, entry, detail):

    LOG.debug(entry)
    LOG.debug(detail)
    # first of all, since the inventory page has so little useful tagging
    # we may get some entries that are not really car listings. Detect
    # them here and return False...
    if entry.name != 'tr':
        LOG.debug('skipping putative entry because it is not in '
                  'a <tr> (was a {})'.format(entry.name))
        return False

    # as with cvc, there is no useful tagging....
    # we just have to make the best of it

    # get the short listing text from the inventory page
    listing.listing_text = entry.find('h3').text.strip()

    # price is only on the inventory page, not on the detail page (!)
    # and it's often missing (text will just be CALL, SOLD, etc)
    price_string = entry.find('h2', align='center')
    if price_string is not None:
        price_string = price_string.text
    listing.price = u.regularize_price(price_string)

    # pull the rest of the fields from the detail page, IF we loaded one
    # (sometimes there isn't one! Just "COMING SOON" and a phone number)

    # GEE TODO: better splitter that understands alfa romeo AND
    # is robust enough to handle unexpected inputs (like missing model year)
    # without puking...
    # Note: the <h1> appears to be handmade and in at least one case omitted
    # model year, so I'm going to pull year/make/model from the detail URL
    # (ugh!) if I can't find it in the <h1>... and if there is no detail URL
    # then I will just return False. Heh, and sometimes the detail HAS no h1!
    try:
        if detail and detail.find('h1'):
            s = detail.find('h1').text
        else:
            s = entry.find('h2').text

        (listing.model_year,
         listing.make,
         listing.model) = u.regularize_year_make_model(s)

        # removed a hacky bit here since I don't think it chains correctly
        # off the revised code above, and I hope I don't need it!

    except ValueError: # should happen only if there is no h1 and then no h2
        return False

    # no real patterns to mine on the details page...

    return True


# def mhc_parse_listing
#
# GEE TODO: this page only loads the first 50 cars and then uses js to pull
# more and do "infinite scrolling". Needt o find a way to get the rest!
#
def mhc_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing.model_year,
     listing.make,
     listing.model) = u.regularize_year_make_model(entry.find('h2').text)

    # GEE TODO: some don't have any description, but others do
    # (on the detail page)
    listing.listing_text = ''

    # pull the rest of the fields from the detail page
    listing.price = u.regularize_price(entry.find('span').text)

    return True


# sfs_parse_listing
#
def sfs_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing.model_year,
     listing.make,
     listing.model) = u.regularize_year_make_model(entry.find('h2').text)

    listing.listing_text = entry.find('h3').text.strip()

    if entry.find('h6'):
        listing.price = u.regularize_price(entry.find('h6').text)
    else:
        listing.price = -1

    # pull the rest of the fields from the detail page

    return True


# specialty_parse_listing
#
# GEE TODO: handle the various showroom locations
# (currently assuming everything is in the pleasanton location)
#
def specialty_parse_listing(listing, entry, detail):

    # get the short listing text from the inventory page; we want the
    # text from the top-level of the entry only, not the details inside
    # various spans or other sub-elements:
    listing.listing_text = ''.join([t for t in entry.contents if isinstance(t, NavigableString) and not isinstance(t, Comment)]).strip()

    # grab price from the main listings page entry
    if entry.find(class_='vehicle-price-label'):
        price_string = entry.find(class_='vehicle-price-label').text
    else:
        price_string = ''
    listing.price = u.regularize_price(price_string)

    # grab year/make/model
    if entry.find(class_='vehicle-heading'):
        s = entry.find(class_='vehicle-heading').text
    else:
        s = ''
    (listing.model_year,
     listing.make,
     listing.model) = u.regularize_year_make_model(s)

    s = ''
    if entry.find(class_='vehicle-stock'):
        s = entry.find(class_='vehicle-stock').text
        if '#' in s:
            junk, s = s.split('#')
    listing.local_id = s
    listing.stock_no = listing.local_id # no separate stock#

    # NOTE: we got everything from the inventory page;
    # not currently using the detail page at all
    # specialty used to have nice elements like the below on the detail
    # page but doesn't any more:
    # <tr>
    #   <td><h3>Stock: </h3></td>
    #   <td>F13011</td>
    # </tr>
    # the first td has an h3 with the fieldname, initcaps with colon and
    # a trailing space
    # the second td has the value (raw, not in an h3)
    # the h3 in there seems to toast next_sibling/next_element, but
    # find_next_sibling('td') works
    return True


# ============================================================================
# PRIMARY INVENTORY PULLING METHODS
# ============================================================================

# pull_dealer_inventory()
#
# pulls inventory from common dealer sites as directed
#
# parameters:
# dealer (textid of the dealer to be imported)
#
# returns a list of listings dicts
#
# NOTES:
#
# this is a generic puller which accepts (and to perform decently, requires)
# site-specific helper functions to extract all the listing details.
#
# see sample inventory and detail pages:
# samples/<dealer>_inventory_page.html
# samples/<dealer>_detail_page.html
#
# this was first developed on/for specialty & fantasy junction sites
#
def pull_dealer_inventory(dealer, session=None):

    LOG.info('Beginning inventory pull for {}'.format(dealer.textid))

    # implicit param from environment:
    # [currently unused in dealer pulls, but for consistency & future use...]
    # inv_settings = os.environ.get('OGL_INV_SETTINGS', '')

    list_of_listings = []
    last_local_id = None

    # get a page of listings; we have pagination logic to loop over addl pages

    try:
        full_inv_url = urllib.parse.urljoin(dealer.base_url,
                                            dealer.inventory_url)
        LOG.info('Pulling ' + dealer.textid + ' inventory from ' +
                 full_inv_url + '....')
        req = urllib.request.Request(full_inv_url, headers=_HDRS)
        page = urllib.request.urlopen(req)
    except urllib.error.HTTPError as error:
        LOG.error('Unable to load inventory page ' + full_inv_url +
                  ': HTTP ' + str(error.code) + ' ' + error.reason)
        return list_of_listings

    # GEE TODO: handle URLError that might have been raised...
    if page.getcode() != 200:
        LOG.warning('Failed to pull an inventory page for ' + full_inv_url +
                    ' with HTTP response code ' + str(page.getcode()))
        return list_of_listings

    while True:
        # soupify it
        soup = BeautifulSoup(page)

        # extract all the listings
        myfunc = eval(dealer.extract_car_list_func)

        listings = myfunc(soup)
        LOG.info('Number of car listings found: {}'.format(len(listings)))
        for item in listings:
            ok = True
            listing = Listing()
            listing.source_type = 'D'
            listing.source_id = dealer.id
            listing.source_textid = dealer.textid
            listing.source = dealer.full_name
            listing.static_quality = dealer.score_adjustment or 0
            listing.lat = dealer.lat
            listing.lon = dealer.lon
            listing.location_text = '{}, {}'.format(dealer.city, dealer.state)
            listing.zip = dealer.zip
            # for some sites the full entry is actually a parent or sibling
            # or similar permutation of the list item we just grabbed
            myfunc = eval(dealer.listing_from_list_item_func)
            entry = myfunc(item)

            # try standard grabs; then call the dealer-specific method for
            # overrides & improvements

            # try to find the URL of the detail listing page
            detail = None # if we don't find one, we can pass down this None
            if entry.get('href'):
                # the found item may itself be an <a>
                # with an href to the detail page
                detail_url = entry.get('href')
            elif entry.find('a'):
                detail_url_elt = entry.find('a')
                # or the first (likely only) href in the block
                # is the detail page
                detail_url = detail_url_elt.get('href')
            else:
                # or alternately, there may be an onclick property we can grab?
                # the onclick property could be on entry or a subentity
                detail_url_attr = None
                try:
                    detail_url_attr = entry.attrs['onclick']
                except KeyError:
                    pass
                if detail_url_attr is None:
                    detail_url_elt = entry.find(onclick=True)
                    if detail_url_elt is not None:
                        detail_url_attr = detail_url_elt.attrs['onclick']
                if detail_url_attr is not None:
                    detail_url = detail_url_attr.split(
                        'href=')[1].replace("'", "")
            # if we found a detail page URL, store & load it
            if detail_url:
                detail_url = detail_url.lstrip()
                # is it an http reference? Sometimes there is a phone URL...
                scheme = urllib.parse.urlsplit(detail_url).scheme
                # oops -- apparent bug, or at least difference in effect
                # between safari and urlsplit. urlsplit doesn't recognize
                # tel:8005551212
                # it recognizes some variants -- basically it expects at
                # least one '/' somewhere.
                # Without that, it returns None as the scheme. So:
                if detail_url[:4] == 'tel:':
                    scheme = 'tel'
                if scheme and scheme != 'http' and scheme != 'https':
                    # uh... let's skip this one if we can't link to it as http
                    LOG.warning('found non-http detail URL: %s',
                                detail_url)
                    listing.listing_href = detail_url # just to prevent barfs
                    ok = False
                else:
                    try:
                        # GEE TODO: occasionally detail_url is NOT escaped
                        # properly (e.g. contains spaces), but calling
                        # urllib.parse.quote() on it quotes chars that
                        # shouldn't be quoted. What to do?
                        listing.listing_href = urllib.parse.urljoin(
                            full_inv_url, detail_url)
                        LOG.debug('detail page: ' + listing.listing_href)
                        req = urllib.request.Request(
                            listing.listing_href, headers=_HDRS)
                        detail_page = urllib.request.urlopen(req)
                        detail = BeautifulSoup(detail_page)
                        # if the detail page is well-formed (has a body)
                        # then throw out the rest & keep just the body
                        body = detail.find('body')
                        if body:
                            detail = body

                    except urllib.error.HTTPError as error:
                        LOG.warning('Unable to load detail page ' +
                                    listing.listing_href + ': HTTP ' +
                                    str(error.code) + ' ' + error.reason)
                        ok = False

            # look for an image in the entry
            if entry.find('img'):
                listing.pic_href = urllib.parse.urljoin(
                    full_inv_url, str(entry.find('img').attrs['src']))
            elif detail and detail.find('img'): # failover to 1st detail img
                listing.pic_href = urllib.parse.urljoin(
                    full_inv_url, str(detail.find('img').attrs['src']))
            else:
                listing.pic_href = None

            # look for a string to use as listing text:
            # pick the longest string in a likely tag within the entry
            listing.listing_text = ''
            for tag in entry.descendants:
                if tag.name in ['p', 'div', 'li', 'span', 'td']:
                    if (
                            len(tag.text) > 50 and
                            len(tag.text) > len(listing.listing_text)
                    ):
                        listing.listing_text = tag.text.strip()
            # if that failed, try to find something on the detail page
            if detail and not listing.listing_text:
                for tag in detail.descendants:
                    if tag.name in ['p', 'div', 'li', 'span', 'td']:
                        if (
                                len(tag.text) > 50 and
                                len(tag.text) > len(listing.listing_text)
                        ):
                            listing.listing_text = tag.text.strip()

            # many sites have no stock#/inventory ID; default to the unique
            # URL element. note that this will be wonky for item(s) that are
            # 'coming soon' (no detail page exists yet)
            listing.local_id = (
                listing.listing_href.rstrip('/').
                split('/')[-1].replace('.html', ''))
            listing.stock_no = listing.local_id # no separate stock_no

            # see if the listing is marked as sold?
            # GEE TODO improve this; using uppercase intentionally as a cheat
            if entry.find(text=re.compile(r'SOLD')):
                # used to also check detail but that was getting too many false
                # positives due to 'VIEW CARS SOLD' link or similar on the page
                listing.status = 'S' # 'S' -> Sold
            elif (
                    entry.find(text=re.compile(r'SALE PENDING')) or
                    (detail and detail.find(text=re.compile(r'SALE PENDING')))
            ):
                listing.status = 'P' # 'P' -> Sale Pending
            else:
                listing.status = 'F' # 'F' -> For Sale

            # $ followed by a number is likely to be a price :-)
            # look first in the entry on the inventory page
            listing.price = u.regularize_price(
                entry.find(text=re.compile(r'\$[0-9]')))
            # try detail page if we didn't get one from the inventory page
            if listing.price == -1 and detail:
                listing.price = u.regularize_price(
                    detail.find(text=re.compile(r'\$[0-9]')))

            # call the dealer-specific method
            # GEE TODO need to define some sort of error-handling protocol...
            ok = (ok and
                  globals()[dealer.parse_listing_func](listing, entry, detail))
            if ok:
                # check for common errors / signs of trouble:
                # need a listing_id
                if listing.local_id == last_local_id:
                    # not getting clean, unique local_ids from the page
                    LOG.warning('Duplicate local_ids '
                                '[{}] from {} inventory'.format(
                                    last_local_id, dealer.textid))
                    ok = False
                last_local_id = listing.local_id
                # model_year must be a string containing an integer
                # (not None or a string that doesn't become an int, etc)
                if not listing.model_year:
                    listing.model_year = '1'
                elif isinstance(listing.model_year, int):
                    listing.model_year = str(listing.model_year)
                else:
                    try:
                        int(listing.model_year) # convert it
                    except ValueError:
                        listing.model_year = '1' #oops

            if ok:
                tagify(listing)
                list_of_listings.append(listing)
                LOG.debug('pulled listing: {}'.format(listing))
            else:
                LOG.warning('skipped listing: {}'.format(listing.local_id))
                LOG.debug('skipped listing details: {}'.format(listing))

            # END LOOP over listings on the page

        # Is there another page of listings? Look for a link with "next" text.
        # Note: there may be multiple such links (e.g. @ top & bottom of list).
        # They should be identical so just grab the first
        next_ref = soup.find('a', text=re.compile(r"[Nn]ext"))
        if next_ref:
            # build the full URL (it may be relative to current URL)
            full_inv_url = urllib.parse.urljoin(
                full_inv_url, next_ref.get('href'))
            LOG.debug('Loading next page of inventory via URL: %s',
                      full_inv_url)
            req = urllib.request.Request(full_inv_url, headers=_HDRS)
            page = urllib.request.urlopen(req)
            # GEE TODO - check that this is really a listings page and has
            # different listings, ie detect and avoid infinite loops
            # GEE TODO - catch the ugly exceptions I get for a bogus URL
            # (errno 8 & a big splat) and also errno 54 / connection reset by
            # peer -> ConnectionResetError, etc (here & in all other URL gets)
        else:
            break
        # END LOOP over all inventory pages

    LOG.info('Loaded ' + str(len(list_of_listings)) + ' cars from ' +
             dealer.textid)
    return list_of_listings


# pull_classified_inventory()
#
# pulls inventory from common classified sites as directed
#
# NOTES: NOT WRITTEN YET; need to understand if this really != dealer method
#
def pull_classified_inventory(classified, session,
                              inventory_marker=None, dblog=False):
    return [], [], [], inventory_marker

def ebay_attr_get(item, attr_name):
    attr_value = None
    try:
        for attr in item['attribute']:
            if attr['name'] == attr_name:
                attr_value = attr['value']
    except (KeyError, TypeError):
        # note: got an odd TypeError once because on one record eBay
        # returned a string rather than a hash for an attr (!). The
        # inconsistency makes no sense, but I guess it is just another
        # way for the record to be messed up & missing model_year
        pass
    return attr_value


# process_ebay_listing()
#
# handles one ebay listing, as returned from the ebay API
#
# broken out just for readability
#
# returns an ok flag, a Listing object, and a ListingSourceinfo object
# ... and also modifies the running totals in counts
#
def process_ebay_listing(session, item, classified, counts, dblog=False, batch_year=None, color=None):
    ok = True
    item = Bunch(item) # for convenience
    LOG.debug('eBay ITEM: {}'.format(item['itemId']))
    listing = Listing()
    listing.source_type = 'C'
    listing.source_id = classified.id
    listing.source_textid = classified.textid
    listing.source = classified.full_name
    listing.static_quality = classified.score_adjustment or 0

    lsinfo = None
    if dblog:
        lsinfo = ListingSourceinfo()
        lsinfo.source_type = 'C'
        lsinfo.source_id = classified.id
        lsinfo.entry = json.dumps(item)
        lsinfo.detail_enc = 'X'
        lsinfo.detail = None
    if XL.dump:
        LOG.debug(json.dumps(item, indent=4, sort_keys=True))
    # local_id & stock_no
    listing.local_id = item.itemId
    listing.stock_no = listing.local_id

    # status
    listing.status = 'F' # 'F' -> For Sale (that's all ebay sends us)

    # year/make/model
    year = make = model = None
    year = ebay_attr_get(item, 'Year')
    if year and len(year) > 4:
        year = year[:4] # ebayism: may have 4 addl trailing 0s, e.g. 20140000
    if not year:
        counts['ebay_bad_year'] += 1
        year = str(batch_year)
    else:
        counts['ebay_good_year'] += 1

    make = item['title'].split(':')[0].strip()
    model = item['primaryCategory']['categoryName']
    (listing.model_year,
     listing.make,
     listing.model) = u.regularize_year_make_model_fields(year, make, model)
    # GEE TODO ^^ alternatively could often get more info from title

    # pic_href -- get the biggest one we can for now
    # GEE TODO: probably should be storing mult sizes on our side
    listing.pic_href = u.regularize_url(item.get('pictureURLSuperSize', '') or
                                        item.get('pictureURLLarge', '') or
                                        item.get('galleryPlusPictureURL'),
                                        absolute_only=True)

    if not listing.pic_href:
        listing.pic_href = u.regularize_url(item.get('galleryURL'),
                                            absolute_only=True)
        if listing.pic_href: # got at least a small pic
            listing.static_quality -= 25
        else:  # no pic at all
            listing.static_quality -= 100

    # listing_href
    listing.listing_href = u.regularize_url(item.get('viewItemURL'),
                                            absolute_only=True)

    if not listing.listing_href:  # broken href = failed; discard
        counts['badhref'] += 1
        ok = False
    
    # location
    # ebay offers a "city,state,country" string and postalCode
    # let's use postalCode and the other string as fallback only
    if item.get('postalCode'):
        listing.zip = item.postalCode
        z = session.query(Zipcode).get(listing.zip)
        if z:
            listing.lat = z.lat
            listing.lon = z.lon
            listing.location_text = '{}, {}'.format(z.city, z.state_code)
    if not listing.lat:  # postalCode lookup didn't work
        city = state = country = z = None
        try:
            city, state, country = item.location.split(',')
        except ValueError:
            pass
        if city and state:
            z = session.query(Zipcode).filter_by(state_code=state.upper(),
                                                 city_upper=city.upper()).first()
        if z:
            listing.zip = z.zip
            listing.lat = z.lat
            listing.lon = z.lon
            listing.location_text = '{}, {}'.format(z.city, z.state_code)
        else:  # ah... well... we have some text in city & state, at least :)
            listing.location_text = '{}, {}'.format(city, state)
            # leave lat/lon/zip empty
    if not (listing.lat and listing.lon and listing.zip and listing.location_text):
        LOG.debug("location information bad: {} {} {} {}".format(
            listing.lat, listing.lon, listing.location_text, listing.zip))
        counts['badloc'] += 1

    # mileage
    miles = ebay_attr_get(item, 'Miles')
    if miles:
        try:
            listing.mileage = int(re.sub(r',', '', miles))
        except ValueError:
            pass

    # colors -- eBay has the info but it's not in the pull. Seems to be
    # another victim of eBay's inconsistent attribute handling. However,
    # since we're sometimes batching by exterior color to work around
    # other eBay issues, the color may be known by the caller that
    # pulled this particular batch... so let's just apply that color
    # to each listing in the batch. Hacky & only applies to years that
    # we batch, but better than nothing:
    listing.color = color
    # still no way to get interior color, or ext color for nonbatched years

    # VIN -- not present by default at least

    # listing_text
    listing.listing_text = item['title'].strip()

    # price
    # GEE TODO: this is ignoring ebay price weirdness and currency
    try:
        listing.price = u.regularize_price(
            item['sellingStatus']['buyItNowPrice']['value'])
    except (KeyError, AttributeError, TypeError, ValueError):
        listing.price = u.regularize_price(
            item['sellingStatus']['currentPrice']['value'])

    # auction end date will also serve as our removal date
    listing.removal_date = u.guessDate(item.listingInfo.get('endTime'))

    # GEE TODO: get other listingInfo, e.g. buy-it-now price

    # validate model_year
    try:
        int(listing.model_year)
    except (ValueError, TypeError):
        counts['badyear'] += 1
        LOG.debug('bad year [%s] for item %s',
                  listing.model_year, listing.local_id)
        listing.model_year = '1'

    return ok, listing, lsinfo


# pull_ebay_inventory()
#
# Pulls ebay listings via the ebay python sdk over the ebay finding api
#
# Accepts some input about what to pull & what not to
# (at least temporarily, we don't want everything ebay lists)
#
# parameters:
# classified: the classified site we are to pull (ebay motors in this case)
# inventory_marker: a marker used to chunk the work; opaque to caller
#
# implicit parameter from unix environment: if OGL_INV_SETTINGS=limited then:
# 	limits pulls to local area (see notes)
# 	limits pulls to "interesting" cars (see notes)
# 	allows larger chunking of the pulls (see notes)
#
# returns:
# accepted_listings: a list of listings (could be partial or entire set)
# inventory_marker: pagination/subset marker (will be None if done)
# import_report: an ImportReport object that can report on what happened
#
# NOTES:
#
# Must chunk queries into 10K items (100 items each x 100 pages) or ebay
# will give an error on page 101. eBay queries on the website are a messed
# up pile o' crap, so hopefully these APIs will give better results
#
# For now, 'limited' pull is interpreted as:
# * 'interesting' filters as described in the named method
# and 'local' pull is interpreted as:
# * 'local' = 150 miles of 95112, and
#
def pull_ebay_inventory(classified, session,
                        inventory_marker=None, dblog=False):

    # implicit param from environment:
    inv_settings = os.environ.get('OGL_INV_SETTINGS', '')

    accepted_listings = []
    accepted_lsinfos = []  # to keep in sync with accepted_listings
    rejected_lsinfos = []
    counts = defaultdict(int)  # track some data/import quality measures
    import_report = u.ImportReport()

    # wonky workaround for ebay's 10K limit. Mostly we can split by model years
    # but for years with lots of inventory (basically the current model year)
    # we have to further subdivide or we run past 10K when not restricting to
    # local cars only

    # we use a magic value for the second year in a batch being 1, indicating
    # that the batch is one year only and must be further subdivided by color

    
    # GEE PATCH
    #ebay_year_batches = [
    #        (1900, 1960), (1961, 1970), (1971, 1980),
    #        (1981, 1990), (1991, 1995), (1996, 1999),
    #        (2000, 2003), (2004, 2005), (2006, 2006),
    #        (2007, 2007), (2008, 2008), (2009, 2009),
    #        (2010, 2010), (2011, 2011),
    ebay_large_batches = [ (2012, 1),
                           (2013, 1), (2014, 1), (2015, 1)
                       ]
    ebay_year_batches=[]
    for year in range(1900,2011):
        ebay_year_batches.append((year, year))
    ebay_year_batches.extend(ebay_large_batches)

    # for any years that are too big we further segment by color (!)
    # (hey, it splits the inventory into reasonably-suitable chunks)
    # note: this color list is eBay-specific; other imports use
    # different list of color words & extract color info differently
    colors = [
        'NotSubBatching', 'Black', 'Blue', 'Brown', 'Burgundy', 'Gold',
        'Gray', 'Green', 'Orange', 'Purple', 'Red', 'Silver', 'Tan',
        'Teal', 'White', 'Yellow', 'Not Specified'
    ]

    if not inventory_marker:
        # start with the first batch, no sub-batch
        inventory_marker = {'batch': 0, 'sub': None}

    # look for ebay yaml (config) in $STAGE/conf, or ../conf if stage not set
    ebay_yaml = os.path.join(os.environ.get('OGL_STAGE', '..'),
                             'conf/ebay.yaml')
    api = ebaysdk_finding(debug=False, appid=None,
                          config_file=ebay_yaml, warnings=True)
    api_request = {
        'categoryId': 6001,
        'GLOBAL-ID': 100,
        'buyerPostalCode': 95112,
        'itemFilter': [
            ],
        'aspectFilter': [],
        'affiliate': {'trackingId': 1},
        'sortOrder': 'CountryDescending',
        'paginationInput': {
            'entriesPerPage': 100, # max allowed; higher would be ignored
            'pageNumber': 1},
        'outputSelector': ['PictureURLLarge', 'PictureURLSuperSize'],
    }

    if 'local' in inv_settings:
        LOG.debug('limiting to local cars')
        api_request['itemFilter'].append({'name': 'MaxDistance',
                                          'value': 150})
    else:
        LOG.debug('NOT limiting to local cars')

    LOG.info('batch starting with year {}, sub {}'.format(
        ebay_year_batches[inventory_marker['batch']][0],
        inventory_marker['sub']))
    # batching by year-groupings; if the 2nd "year" in the batch tuple is not a
    # year but a small #, then this is a single-year batch with sub-batches
    for year in range(ebay_year_batches[inventory_marker['batch']][0],
                      max(ebay_year_batches[inventory_marker['batch']][1],
                          ebay_year_batches[inventory_marker['batch']][0])+1):
        api_request['aspectFilter'].append({'aspectName': 'Model Year',
                                            'aspectValueName': year})
    if inventory_marker['sub']:
        # then we're doing sub-batches, so select the indicated color batch
        api_request['aspectFilter'].append({'aspectName': 'Exterior Color',
                                            'aspectValueName':
                                            colors[inventory_marker['sub']]})

    # log the API request for page 1 (not again each page inside the next loop)
    LOG.debug('eBay API request: {}'.format(api_request))

    while True:

        # NOTE: in case of various issues we can break out of this loop, but
        # we must be careful not to break out of the enclosing (batch) loop
        # to avoid potentially mangling inventory_marker handling

        # pull a page
        response = api.execute('findItemsAdvanced', api_request)
        r = response.dict()
        if r['ack'] != 'Success':
            LOG.error('eBay reports failure: {}'.format(response))
            break # note: breaks out of loop over pages
        # _count may be empty, or '0', or 0, or... who knows, but skip it
        if (
                not r['searchResult']['_count']
                or int(r['searchResult']['_count']) == 0
        ):
            LOG.warning('eBay returned a set of zero records')
            break # note: breaks out of loop over pages

        # note: _count may not be present if we got a bad fetch from eBay;
        # hopefully we've done all our checks above and called a break...
        LOG.info('Number of car listings found: %s',
                 r['searchResult']['_count'])
        # GEE PATCH: delete the next line when ebay fixes the missing year attr
        pull_year = ebay_year_batches[inventory_marker['batch']][0]
        for item in r['searchResult']['item']:
            if inventory_marker['sub']:
                ok, listing, lsinfo = process_ebay_listing(session, item,
                                                           classified, counts,
                                                           dblog=dblog,
                                                           batch_year=pull_year,  # GEE PATCH
                                                           color=colors[inventory_marker['sub']])
            else:
                ok, listing, lsinfo = process_ebay_listing(session, item,
                                                           classified, counts,
                                                           dblog=dblog,
                                                           batch_year=pull_year)  # GEE PATCH
            # ok to date means we got something potentially useful
            if ok:
                tagify(listing, strict=False, counts=counts)
                # more checks after tagification (checks that leverage tagging)
                ok = u.apply_post_tagging_filters(listing, inv_settings, counts, protect=False)

            if ok:
                # it's a keeper!
                accepted_listings.append(listing)
                if dblog:
                    accepted_lsinfos.append(lsinfo)
                LOG.debug('pulled listing: {}'.format(listing))
            else:
                # debug not warn b/c we're throwing out lots of stuff
                LOG.debug('skipped listing: {}'.format(listing))
                if dblog:
                    rejected_lsinfos.append(lsinfo)

            # END LOOP over listings on the page

        # is there another page of listings?
        # IMPORTANT NOTE: eBay page counts are *approximate*, meaning you might
        # get back page 48 of 50, then the next page will be empty and that is
        # the end of the list. Also, the "of 50" might say "of 49" on one page
        # and "of 53" on another page of the same pull
        current_page = int(r['paginationOutput']['pageNumber'])
        total_pages = int(r['paginationOutput']['totalPages'])
        LOG.info('Loaded page {} of {}'.format(current_page, total_pages))
        if current_page < total_pages:
            api_request['paginationInput']['pageNumber'] = current_page + 1
            response = api.execute('findItemsAdvanced', api_request)
        else:
            break
        # END LOOP over all inventory pages

    if accepted_listings:
        LOG.info('Loaded %s cars from ebay',
                 str(len(accepted_listings)))

    # do we increment sub-batch (color) or move to the next batch?
    if inventory_marker['sub']:
        # then the current batch has sub-batches;
        # move to the next sub-batch of the current batch
        inventory_marker['sub'] = inventory_marker['sub'] + 1
        #  unless we have done all the sub-batches, that is?
        if inventory_marker['sub'] == len(colors):
            # we are done with all the sub-batches so go to the next batch
            inventory_marker['batch'] = inventory_marker['batch'] + 1
            inventory_marker['sub'] = None # will check below...
    else: # no sub-batches right now, always increment to next batch
        inventory_marker['batch'] = inventory_marker['batch'] + 1

    # have we walked through all the batches?
    # do we have sub-batches in this batch?
    if inventory_marker['batch'] == len(ebay_year_batches):
        inventory_marker = None # done!
    elif (ebay_year_batches[inventory_marker['batch']][1] == 1
          and not inventory_marker['sub']):
        # need to sub-batch this new batch; start with sub-batch index=1
        inventory_marker['sub'] = 1 # 1st color is @ ind 1, not 0, in list

    import_report.add_accepted_lsinfos(accepted_lsinfos)
    import_report.add_accepted_lsinfos(rejected_lsinfos)
    return accepted_listings, inventory_marker, import_report


# import_from_dealer
#
# Imports inventory from a dealership, overwriting (adding/updating) as needed
#
# parameters:
# con: db connection (None if no db access is possible/requested)
# es: indexing connection (None if no indexing is possible/requested)
#
# returns:
# True if the import succeeded, False if something broke
#
# Notes:
#
# This is basically a wrapper around pull_dealer_inventory() that handles the
# persistence details of the pulled inventory. Assumes that a dealership's
# inventory is small enough to pull & update within a single db commit
# (and then this method commits)
#
def import_from_dealer(dealer, session, es):

    # clear out existing sourceinfo records (this table grows FAST)
    u.clear_listing_sourceinfo(session, 'D', dealer.id)
    session.commit()

    # paint current records so we can mark-as-removed any that no longer exist
    u.mark_listings_pending_delete('D', dealer.id, session)
    session.commit()

    # get the current listings on the dealer's website inventory
    listings = []
    try:
        listings = pull_dealer_inventory(dealer, session)
    except (ValueError, AttributeError, IndexError):
        # if we were stopped by one of these data-related errors, log it and
        # return to the caller rather than halting execution because there
        # may be other actions to take (e.g. other sites to import)
        LOG.exception('Importing inventory from dealer %s halted by exception',
                      dealer.textid)
        return False

    # now put the located records in the db & es index
    # GEE TODO: switch this over to use record_listings()
    if listings:
        # with sqlalchemy, we get new objects back so build a list of those
        db_listings = []
        for listing in listings:
            db_listings.append(u.add_or_update_found_listing(session, listing))

        # commit the block of listings (which generates ids on new records)
        session.commit()
        LOG.debug('committed a block of listings for %s',
                  dealer.textid)

        if es:
            # put the listings in the text index
            for listing in db_listings:
                u.index_listing(es, listing)
    else:
        LOG.warning('no inventory found for dealer %s', dealer.textid)

    # we want to remove the marked listings even if there are no new
    # listings -- there might be no inventory.
    u.remove_marked_listings('D', dealer.id, session, es=es)

    # and commit (marked-as-removed inventory)
    session.commit()

    return True


# import_from_classified
#
# Imports inventory from a classified site,
# overwriting (adding/updating) as needed
#
# parameters:
# con: db connection (None if no db access is possible/requested)
# es: indexing connection (None if no indexing is possible/requested)
#
# Notes:
#
# This is basically a wrapper around a generic or site-specific method
# [pull_<foo>_inventory()] that handles the persistence details of the
# pulled inventory. Handles chunking up the classified site's inventory
# into reasonable-size commit blocks (which this method commits)
#
# NOTE: no longer supporting writing files or skipping db or indexing
#
def import_from_classified(classified, session, es, dblog=False):

    LOG.info('Beginning inventory pull for {}'.format(classified.textid))

    # clear out existing sourceinfo records (this table grows FAST)
    u.clear_listing_sourceinfo(session, 'C', classified.id)
    session.commit()

    # 3taps provides polling w/ only new/updated records in the stream, so
    # we explicitly get deletes/expirations/etc. All other sites we need
    # to treat disappearance of the listing as cause for cancellation

    if classified.custom_pull_func != 'pull_3taps_inventory':
        u.mark_listings_pending_delete('C', classified.id, session)
        session.commit()

    inventory_marker = None
    done = False
    import_report = None
    while not done:

        listings = []

        # get the current active inventory of website listings
        # or, in the case of 3taps, the deltas since the last polling
        # note that some sites have a custom pull method

        if classified.custom_pull_func:
            f = globals()[classified.custom_pull_func]
        else:
            f = pull_classified_inventory

        try:
            (listings,
             inventory_marker,
             import_report) = f(classified, session,
                                inventory_marker=inventory_marker, dblog=dblog)
        except (ValueError, AttributeError, IndexError):
            # if we were stopped by one of these data-related errors, log it and
            # return to the caller rather than halting execution because there
            # may be other actions to take (e.g. other sites to import)

            # note that this may leave existing records marked for pending
            # deletion and some previous blocks of inventory committed
            # that is harmless; both 3taps and non-3taps cases will handle
            # that fine when the import is next attempted

            LOG.exception('Importing inventory from classified %s halted by exception',
                          classified.textid)
            return False            

        # record listings and lsinfos in the db (this method commits!)
        u.record_listings(listings,
                          # GEE TODO: move this lsinfo stuff into import_report
                          import_report.accepted_lsinfos,
                          import_report.rejected_lsinfos,
                          classified.textid, session, es)
        import_report.text_report(classified, logger=LOG)
        import_report.db_report(classified, session)

        # check if we're done?
        if not inventory_marker:
            done = True
        # END LOOP over blocks of inventory (while not done)

    if classified.custom_pull_func == 'pull_3taps_inventory':
        # do nothing: sqlalchemy will already have updated the anchor
        pass
    else:
        u.remove_marked_listings('C', classified.id, session, es=es)

    session.commit() # aaaaaand commit (catches the marked listing handling)
    LOG.info('Completed inventory pull for {}'.format(classified.textid))

    return True


# ============================================================================
# MAIN
# ============================================================================

def process_command_line():

    parser = argparse.ArgumentParser(description='Imports car listings')
    parser.add_argument('--noindex', dest='index', action='store_const',
                        const=False, default=True,
                        help='skip indexing the listings')
    parser.add_argument('--files', dest='file', action='store_const',
                        const=True, default=False,
                        help='writes listings to files in /tmp')
    parser.add_argument('--log_level', default='INFO',
                        choices=('DEBUG', 'INFO', 'WARNING',
                                 'ERROR', 'CRITICAL'),
                        help='set the logging level')
    parser.add_argument('--extra_logging', default='NONE',
                        choices=('NONE', 'DBLOG', 'STDOUT'),
                        help='do extra logging (expensive, be careful)')
    parser.add_argument('action',
                        choices=('list', 'import'),
                        help=('action: list sources which can be imported and'
                              'exit, or import from those sources'))
    parser.add_argument('sources', nargs='*',
                        help='the source(s) to pull from if action=import')

    return parser.parse_args()


def main():
    args = process_command_line()

    # start logging:
    # set up the root logger as desired for the process; the local
    # __name__ logger (and all other loggers) will pass things up to root
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)s] %(message)s',
        datefmt="%d/%b/%Y %H:%M:%S")
    fh = None
    try:
        fh = logging.FileHandler(os.path.join(os.environ.get('OGL_LOGDIR',
                                                             '/tmp'),
                                              'importlog'))
    except:
        fh = logging.StreamHandler()  # fall back to stderr
    fh.setFormatter(formatter)

    # set this fh & log level on the root logger so that the local LOG and
    # loggers defined in whatever other modules (e.g. elasticsearch) will
    # all output there, at the defined level (unless they augment/supercede)
    tmp = logging.getLogger('')
    tmp.setLevel(args.log_level.upper())
    tmp.addHandler(fh)

    if args.extra_logging == 'DBLOG':
        XL.dblog = True
    if args.extra_logging == 'STDOUT':
        XL.dump = True

    # uncomment this to log the SQL generated by SQLalchemy (and lots more)
    #logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

    # and suppress elasticsearch's annoying INFO and WARNING messages
    logging.getLogger('elasticsearch').setLevel(logging.ERROR)

    # establish connections to required services (db & es)
    session = None # the SQLAlchemy session
    es = None # and the indexing connection

    try:
        # recommended connection string adds &use_unicode=0 "because
        # python is faster at unicode than mysql" (per sqlalchemy docs), but
        # fuck faster if it doesn't work at all: that generates this error:
        # TypeError: conversion from bytes to Decimal is not supported
        # ... which is a dead end. Maybe that is a python 2.x-only advice?
        connect_str = 'mysql+pymysql://{}:{}@{}/{}?charset=utf8'
        sqla_db_string = connect_str.format(
            os.environ['OGL_DB_USERACCOUNT'],
            os.environ['OGL_DB_USERACCOUNT_PASSWORD'],
            os.environ['OGL_DB_HOST'],
            os.environ['OGL_DB']
        )
        engine = create_engine(sqla_db_string)
        Session = sessionmaker(bind=engine)
        session = Session()
    except KeyError:
        print("Please set environment variables for OGL DB connectivity"
              "and rerun.")
        sys.exit(1)

    # GEE TODO: test session success here

    # ... and go ahead and fetch the sources from the db here for simplicity
    # GEE TODO: when # of sources gets large we can refactor
    dealerships = session.query(Dealership).all()
    classifieds = session.query(Classified).all()

    # populate our cache of db reference data into global hashes
    load_refdata_cache(session)

    if args.index:
        # set es; other code will use es == None as implying to skip indexing
        es = Elasticsearch()

    # now do what the user requested (the action)
    if args.action == 'list':
        for dealer in dealerships:
            print('{} [dealer {}]'.format(dealer.textid, dealer.full_name))
        for classified in classifieds:
            print('{} [classified site {}]'.format(classified.textid,
                                                   classified.full_name))

        print('norcal [special aggregation of norcal dealerships]')
        print('db_dealers [all dealers in the database]')

    elif args.action == 'import':
        for source in args.sources:
            if source == 'norcal':
                for dealer in dealerships:
                    import_from_dealer(dealer, session, es)
            else:
                found = False
                for dealer in dealerships:
                    if dealer.textid == source:
                        found = True
                        import_from_dealer(dealer, session, es)
                for classified in classifieds:
                    if classified.textid == source:
                        import_from_classified(classified, session, es)
                        found = True
                if not found:
                    LOG.error('request of import from unknown source: %s',
                              source)
    else: # uh, shouldn't be possible?
        LOG.error('oops -- action {} not recognized'.format(args.action))

    return True

if __name__ == "__main__":
    status = main()
    sys.exit(status)
