#!/usr/bin/env python3
#
# 3taps inventory manipulation
#

# builtin modules used
from base64 import b64decode
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
import time
import urllib.request
import urllib.error
import urllib.parse

# third party modules used
from bunch import Bunch
from lxml import etree
from pyquery import PyQuery as pq

# OGL modules used
from inventory.settings import LOG, XL, _HDRS
from inventory.tagging import tagify
import inventory.utils as u
from orm.models import Listing, ListingSourceinfo, Zipcode

# extract_3taps_key_fields_and_status()
#
def extract_3taps_key_fields_and_status(listing, item, classified, counts):
    # local_id & stock_no
    # the source identifier to minimizes dupes (3taps ID changes each update)
    listing.local_id = item.external_id
    # keep the 3taps ID around too (at least the latest one)
    listing.stock_no = item.id
    if not listing.local_id:
        # some feeds (e.g. autod) *occasionally* lack the local_id;
        # fall back to stock_no
        counts['warn_no_external_id'] += 1
        LOG.debug('listing for a %s %s %s has no local ID; ' +
                  'using 3taps ID %s',
                  listing.model_year, listing.make, listing.model,
                  listing.stock_no)
        listing.local_id = listing.stock_no

    # status
    # per 3taps deleted=True is the primary thing to check now that they are
    # doing deletion updates, but let's also take status !='for_sale' -> !'F'
    if item.status == 'for_sale' and item.deleted is False:
        listing.status = 'F' # 'F' -> For Sale
            
    else:
        listing.status = 'R' # 'R' -> Removed
        counts['inactive'] += 1
        listing.status = 'R' # 'R' -> Removed, unknown reason

    return True  # Got these fields...
   

# extract_3taps_location()
#
# returns location
#
# NOTES:
# From annotations. Tries to handle partial information.
# Uses/standardizes against zipcode table (thus requiring session)
#
# one note on quality: sometimes the feeds have USA-05602 zip and
# lat/lon; other times (notably hmngs) they have "plain" 5-digit
# zips and no lat/lon or other breakouts (like state or metro). In
# any case, lets try to end up with zip/postal code, lat/lon, and
# city&state (this last just to avoid a lookup at display time).
# GEE TODO: more i18n!
def extract_3taps_location(listing, item, classified, counts, session):
    if 'location' in item:
        if 'lat' in item.location:
            listing.lat = u.regularize_latlon(item.location['lat'])
        if 'long' in item.location: # note 3taps uses long, we use lon
            listing.lon = u.regularize_latlon(item.location['long'])
        if 'zipcode' in item.location:
            listing.zip = item.location['zipcode'].strip()
            if listing.zip.startswith('USA-'):
                listing.zip = listing.zip[4:]
            z = session.query(Zipcode).get(listing.zip)
            if z:
                listing.location_text = '{}, {}'.format(z.city, z.state_code)
                if not (listing.lat and listing.lon):
                    listing.lat = z.lat
                    listing.lon = z.lon

    if not (listing.lat and listing.lon and listing.zip and listing.location_text):
        LOG.debug("location information bad: {} {} {} {}".format(
            listing.lat, listing.lon, listing.location_text, listing.zip))
        counts['badloc'] += 1
    return True


# extract_3taps_desc_fields()
#
# pulls "the rest" of the fields from item into listing
#
def extract_3taps_desc_fields(listing, item, classified, counts):
    anno = item.get('annotations') or {}
    ok = True
    # set removal date as requested, within limits...
    # e.g. most cl posts are set to expire in +6 weeks. That's too long.
    # listing time is capped relative to now (maybe update), not listing date
    listing.removal_date = (datetime.datetime.now() +
                            datetime.timedelta(days=classified.keep_days))
    if item.expires:
        listing.removal_date = min(listing.removal_date,
                                   u.guessDate(item.expires))

    if (item.deleted or item.flagged_status or
          item.state != 'available' or item.status != 'for_sale'):
        LOG.debug('maybe-not-active: d/e/f/s/s=%s/%s/%s/%s/%s',
                  str(item.deleted), str(item.expires),
                  str(item.flagged_status), str(item.state),
                  str(item.status))

    # drop all cars from outside the US (temporarily, we hope!)
    # (assuming missing country and/or currency are USA/USD for all feeds)
    country = None
    if item.location:
        country = item.location.get('country')
    if country and country != 'USA' and country != 'US':
        # yes, there is a mix of 'US' and 'USA' in the feeds... sigh.
        # from looking at a few examples it seems like the 'US' records
        # are cases where 3taps failed to get full location info, but
        # these listings do seem to be likely US cars, sometimes with
        # partial US addresses (maybe state, maybe zip)
        counts['outsideusa:' + country] += 1
        ok = False

    if item.currency and item.currency != 'USD':
        counts['nonusd'] += 1
        ok = False

    # mileage -- just check annotations; otherwise leave null
    if anno.get('mileage'):
        # GEE TODO: put this in a regularize() method & add complexity (e.g. dropping tenths)
        try:
            listing.mileage = int(re.sub(r',', '', anno['mileage']))
        except ValueError:
            pass

    # colors -- just check annotations; otherwise leave null
    # some sources (e.g. hmngs) have this pretty often; others (e.g. carsd) not
    if anno.get('exteriorColor'):
        listing.color = anno['exteriorColor'].strip()
    if anno.get('interiorColor'):
        listing.int_color = anno['interiorColor'].strip()

    # VIN -- isn't in any of the 3taps feeds (at least without
    # checking html) so always leave it null

    # listing_text
    listing.listing_text = item.heading
    if classified.textid == 'ccars' and listing.listing_text:
        # drop leading site ID in format '(CC-123456) '
        if listing.listing_text[:4] == '(CC-':
            try:
                listing.listing_text = ') '.join(listing.listing_text.split(') ')[1:])
            except IndexError:
                pass  # huh, there was no closing paren; ignore...
    # price - may be @ top level or in the annotations
    listing.price = u.regularize_price(item.price)
    if listing.price <= 1000 and 'price' in anno:
        listing.price = u.regularize_price(anno['price'])
    if listing.price <= 100:
        counts['badprice'] += 1
        # GEE TODO: check to see if we can salvage any of these via raw html?
    return ok


# extract_3taps_urls()
#
# extracts pic_href and listing_href
#
def extract_3taps_urls(listing, item, classified, counts):
    ok = True
    # pic_href
    try:
        # for all 3taps sites the listing pic _should_ be first in the list
        # many times we don't get the right pic at all, but so far if the
        # right pic is there, it is first in the list. So use that....
        listing.pic_href = item.images[0]['full']
        # now work around some 3taps issues where they pull scaled-down
        # thumbnails rather than full size images; we can fix the URLs
        if classified.textid == 'carsd':
            listing.pic_href = listing.pic_href.split('&width')[0]
        if classified.textid == 'autod':
            listing.pic_href = listing.pic_href.replace('/scaler/80/60/',
                                                        '/scaler/544/408/')
    except (KeyError, IndexError, TypeError):
        LOG.debug('Failed to find a picture for a posting')
        listing.pic_href = 'N/A'

    # listing_href
    listing.listing_href = item.external_url
    # workaround for 3taps issue with broken autod URLs:
    if classified.textid == 'autod':
        if not listing.listing_href or not 'listingId=' in listing.listing_href:
            LOG.debug('discarding record due to broken autod external_url')
            ok = False  # unfixable error, unfortunately
    return ok


# extract_3taps_year_make_model()
#
# pulls year/make/model from listing json and/or html
#
# This is complicated...
# there are three possible places to find year/make/model from 3taps:
# annotations, the listing heading, or the full listing html.
# grab the first 2, the 3rd contingently, and keep the best-looking.

# a few notes on feed quality:
# carsd seems to have consistent year/make/model in annotations
# autod usually has all three in annotations but not always
# hmngs usually has all three in annotations, and it is clearly a
#   straight parse of the heading, e.g.:
#   heading: "2006 Cadillac XLR-V 31k MILES Loaded! Supercharged!",
#   annotations.model: " XLR-V 31k MILES Loaded! Supercharged!",
#   (make/model category info appears to be unused)
#   (model field even retains a leading space, heh)
#   (hemmings seems to enforce/regularize year/make/model at the
#    beginning of the heading but then permit more verbiage)
# craig sometimes has year in annotations but usually not the others
#
def extract_3taps_year_make_model(listing, item,
                                  classified, counts,
                                  html, dblog):
    anno = item.get('annotations') or {}

    # from the annotations:
    (an_model_year,
     an_make,
     an_model) = u.regularize_year_make_model_fields(anno.get('year'),
                                                     anno.get('make'),
                                                     anno.get('model'))
    # from the heading
    (he_model_year,
     he_make,
     he_model) = u.regularize_year_make_model(item.get('heading'))

    # from the html
    # for cl, annotations are often WRONG, so always go to the html
    # (but fall back to the annotations if we have to). The html
    # contains one ore more <p class="attrgroup">... one of which
    # often contains a <span> with Y/M/M info.
    # GEE TODO: some of the other attrgroup spans are also interesting
    ht_model_year = ht_make = ht_model = None
    if classified.textid == 'craig' and html:
        # the encoded html gets chopped at 64k blob size, and there may
        # be other situations where something gets munged; if the length
        # is wrong pad chop off a few chars until it is a multiple of
        # 4 bytes so that b64decode will at least be able to pull out what
        # is there. Chopping rather than padding because it happens to deal
        # with an "incorrect" last character too (such as \n) in case that
        # has happened, at the cost of potentially chopping up the last tag
        html_decoded = None
        extrabytes = len(html) % 4
        if extrabytes:
            html = html[:-extrabytes]
        try:
            html_decoded = b64decode(html)
        except:  # GEE TODO: figure out how to catch 'binascii.Error'
            LOG.warning('Failed to decode item html for item %s',
                        item.external_id)
        if html_decoded:
            # pyquery is 10x FASTER than beautiful soup for this simple task
            # but it does throw an occasional exception on bad inputs (heh)
            try:
                d = pq(html_decoded)
                for span in d('.attrgroup').find('span').items():
                    if not listing.model_year or not listing.make:
                        (ht_model_year,
                         ht_make,
                         ht_model) = u.regularize_year_make_model(span.text())
                        listing.model_year = ht_model_year
                        listing.make = ht_make
                        listing.model = ht_model
            except:
                LOG.exception('exception encountered while getting ',
                              'year/make/model from html for element ',
                              str(listing.local_id))

            # and store the decoded version since we've bothered to make it
            if dblog and lsinfo.detail_enc == 'B':
                lsinfo.detail_enc = 'T'
                lsinfo.detail = html_decoded
    if not listing.model_year:  # from the html...
        if an_model_year and an_model_year > '1800' and an_model_year < '2020':
            listing.model_year = an_model_year
        else:
            listing.model_year = he_model_year
    if not listing.make or not listing.model:
        # GEE TODO: recheck in a few months (spring '15) and hopefully remove:
        # recent (dec-14) bug in hmngs is getting annotation 'make' wrong, as
        # 'Willys-Overland' when it is not. So at least temporarily a patch:
        if an_make and (classified.textid != 'hmngs' or
                        an_make != 'Willys' or he_make == an_make):
            listing.make = an_make
            if an_model:  # take any model found with the winning make
                listing.model = an_model
            else:
                listing.model = he_model
        else:
            listing.make = he_make
            if he_model:
                listing.model = he_model
            else:
                listing.model = an_model

    # logging what year/make/model we ended up with [and what we started from]
    # GEE TODO: cl 1996 1996 nissan pulsar -> model=1996 :(.
    # Can fix that one (header was right, annotations and html were wrong)
    if classified.textid == 'craig':
        LOG.debug('Final year/make/model: %s %s %s [an: %s %s %s, h: %s, html: %s %s %s]',
                  listing.model_year, listing.make, listing.model,
                  an_model_year, an_make, an_model, item.heading,
                  ht_model_year, ht_make, ht_model)
    else:
        LOG.debug('Final year/make/model: %s %s %s [an: %s %s %s, h: %s]',
                  listing.model_year, listing.make, listing.model,
                  an_model_year, an_make, an_model, item.heading)
    return True


# process_3taps_posting()
#
# Extracts info from a 3taps polling API posting structure
#
# Broken out just to make code more readable & maintainable
#
# returns an ok flag, a Listing object, and a ListingSourceinfo object
# ... and also modifies the running totals in counts
#
def process_3taps_posting(session, item, classified, counts, dblog=False):
    ok = True
    item = Bunch(item) # for convenience
    anno = item.get('annotations') or {}
    # copy out html so we can put it ONLY in the detail field of the lsinfo
    html = item.get('html')
    item.html = None

    LOG.debug('3taps ITEM: {}'.format(item.id))
    listing = Listing()
    listing.source_type = 'C'
    listing.source_id = classified.id
    listing.source_textid = classified.textid
    listing.source = classified.full_name

    lsinfo = None
    if dblog:
        lsinfo = ListingSourceinfo()
        lsinfo.source_type = 'C'
        lsinfo.source_id = classified.id
        lsinfo.entry = json.dumps(item)
        lsinfo.detail_enc = 'B'
        lsinfo.detail = html
    if XL.dump:
        LOG.debug(json.dumps(item, indent=4, sort_keys=True))

    # pull local_id, stock_no, and status
    ok = extract_3taps_key_fields_and_status(listing, item, classified, counts)

    if ok:
        if listing.status == 'F':
            ok = ok and extract_3taps_year_make_model(listing, item,
                                                      classified, counts,
                                                      html, dblog)
            ok = ok and u.validate_year_make_model(listing, counts)
            ok = ok and extract_3taps_urls(listing, item, classified, counts)
            ok = ok and extract_3taps_location(listing, item, classified,
                                               counts, session)
            ok = ok and extract_3taps_desc_fields(listing, item, classified,
                                                  counts)
            # now run final validations of the listing
            ok = ok and u.validate_listing(listing, counts)
        else:  # item/listing is NOT for sale
            listing.removal_date = datetime.datetime.now()
            # don't bother to look for other data fields...
            # This seems odd but 3taps injects some removal records
            # representing records no longer present in source site
            # inventory. These records will lack all detail other than
            # source id/3taps id. It is counterproductive to even look
            # for these details and potentially overwrite complete db
            # records that may already exist for these ids with empty
            # fields; instead we will just be updating the status.

    return ok, listing, lsinfo


# pull_3taps_inventory()
#
# Pulls listings (for some source/classified) via the 3taps api
#
# This method is for all 3taps sources; the classified param tells which one
#
# Accepts some input about what to pull & what not to
#(at least temporarily, we don't want everything 3taps lists)
#
# parameters:
# classified: the classified site we are to pull
# inventory_marker: a marker used to chunk the work; opaque to caller
# session: db session
#
# returns:
# accepted_listings: a list of listings (could be partial or entire set)
# inventory_marker: pagination/subset marker (will be None if done)
# import_report: an ImportReport object that can report on what happened
#
# NOTES:
#
# 3taps provides polling with an anchor, so unlike with other sites we don't
# have to reload all the active listings each time. Yay! Much simpler this way.
#
# We also get data already broken into useful json. Unfortunately we sometimes
# get less richness (e.g. very small thumbs or only partial text).

# We also have to decide (on a site-by-site basis) whether to load the detail
# pages or just use the 3taps data and avoid hitting the originating site.
#
# 3taps doesn't seem to offer control over the chunking of the polling results;
# it returns chunks of 1000 listings. We'll chunk that way too for simplicity.
#
# implicit parameter from unix environment: if OGL_INV_SETTINGS=limited then:
# 	limits pulls to local area (see notes)
# 	limits pulls to "interesting" cars (see notes)
#
def pull_3taps_inventory(classified, session,
                         inventory_marker=None, dblog=False):

    # GEE TODO: clean this up!
    dblog = XL.dblog

    # implicit param from environment:
    inv_settings = os.environ.get('OGL_INV_SETTINGS', '')

    accepted_listings = []
    accepted_lsinfos = []  # to keep in sync with accepted_listings
    rejected_lsinfos = []
    counts = defaultdict(int)  # track some data/import quality measures
    import_report = u.ImportReport()

    # for 3taps we want to keep the anchor in the classified record (which
    # ultimately means in the db) but we will also feed it through the
    # inventory_marker param as a mechanism for flow control only. Since
    # this routine only pulls records and doesn't touch the db, we will
    # update the classified record but trust the caller to update the db

    if inventory_marker:
        pass # run from the passed-in point
    else:
        # caller doesn't specify; start from the anchor in classified
        inventory_marker = classified.anchor

    LOG.info('Pulling inventory from 3taps for %s starting with marker %s',
             classified.textid, inventory_marker)

    # no dedicated python sdk, but simple enough JSON APIs to call directly
    url = ('http://polling.3taps.com/poll?'
           'auth_token=a7e282009ed50537b7f3271b753c803a'
           '&category=VAUT&retvals=id,account_id,source,'
           'category,location,external_id,external_url,'
           'heading,body,timestamp,timestamp_deleted,expires'
           ',language,price,currency,images,annotations,'
           'deleted,flagged_status,state,status')
    # html is LARGE -- especially for some sites. Only pull it for craig...
    if classified.textid == 'craig':
        url += ',html'
    url_params = ['&source={}'.format(classified.textid.upper())]
    url_params.append('&anchor={}'.format(inventory_marker))
    if 'local' in inv_settings:
        LOG.debug('limiting to local cars')
        # GEE TODO: note that inventory will get really screwed up if we switch
        # back and forth between local and not
        url_params.append('&location.state=USA-CA')
    else:
        LOG.debug('NOT limiting to local cars')

    url = url + ''.join(url_params)
    LOG.info('inventory URL is: {}'.format(url))

    try:
        # set a longer socket timeout. 3taps can be slow, esp for craig
        # however, we;re being blocked by a timeout at an intermediate
        # server somewhere (http 504) so this isn't effective :(
        socket.setdefaulttimeout(180)
        req = urllib.request.Request(url, headers=_HDRS)
        t1 = int(time.time())
        page = urllib.request.urlopen(req)
        t2 = int(time.time())
        bytestream = page.read()
        t3 = int(time.time())
        LOG.info('open time (sec): {}, read time (sec): {}'.format(t2-t1, t3-t2))
        r = json.loads(bytestream.decode())
    except urllib.error.HTTPError as error:
        LOG.error('Unable to poll 3taps at ' + url + ': HTTP ' +
                  str(error.code) + ' ' + error.reason)
        return [], None, import_report

    if page.getcode() != 200:
        LOG.error('Failed to poll 3taps at ' + url +
                  ' with HTTP response code ' + str(page.getcode()))
        LOG.error('Full error page:'.format(bytestream.decode()))
        return [], None, import_report

    if not r['success']:
        ret = json.dumps(r, indent=4, sort_keys=True)
        LOG.error('3taps reports failure: {}'.format(ret))
        return [], None, import_report
    if len(r['postings']) == 0:
        LOG.warning('3taps returned a set of zero records')
        return [], None, import_report

    LOG.info('Number of car listings found: {}'.format(len(r['postings'])))

    for item in r['postings']:
        ok, listing, lsinfo = process_3taps_posting(session, item,
                                                    classified, counts,
                                                    dblog=dblog)

        # ok to date means we got something potentially useful
        if ok and listing.status == 'F':
            # strictness: be tougher on CL posts b/c, well, junk
            tagify(listing, strict=(classified.textid == 'craig'), counts=counts)

            # more checks after tagification (checks that leverage tagging)
            ok = u.apply_post_tagging_filters(listing, inv_settings, counts)

            # GEE TODO: fix these & incorp into post_tagging filters (above)
            # a few more CL junk-data tests: drop records that fail
            if ok and classified.textid == 'craig' and not listing.has_tag('interesting'):
                if not listing.model_year or listing.model_year < '1800':
                    LOG.warning('skipping item with no useful year: %s',
                                item)                
                    ok = False
                elif not listing.model or listing.model == 'None':
                    LOG.warning('skipping item with no useful model: %s',
                                item)
                    ok = False
                elif listing.price < 100:
                    LOG.warning('skipping item with no useful price: %s',
                                item)
                    ok = False

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

    # report on outcomes
    if accepted_listings:
        LOG.info('Loaded %s cars from 3taps for %s',
                 str(len(accepted_listings)), classified.textid)
    for key in counts:
        LOG.info(' - %s: %s', key, str(counts[key]))

    # update the classified record with the new 3taps anchor AND
    # send the same value back as the inventory marker.
    classified.anchor = r['anchor']
    inventory_marker = r['anchor']

    # note: 3taps doesn't tell us when/if we are caught up -- we just won't see
    # a full set of new records. We could have a few that came in while we're
    # running but lets NOT endlessly cycle on that....
    if len(r['postings']) < 500: # arbitrary number
        inventory_marker = None # signal that we are done!

    import_report = u.ImportReport()
    import_report.add_accepted_lsinfos(accepted_lsinfos)
    import_report.add_accepted_lsinfos(rejected_lsinfos)
    return accepted_listings, inventory_marker, import_report
