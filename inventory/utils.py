#!/usr/bin/env python3
#
# inventory utility classes and methods
#
# yeah, each class & group of methods should probably be a separate module

# builtin modules used
from collections import defaultdict
import datetime
from decimal import Decimal
import errno
import logging
import os
import pytz
import re
import sys
import time

# third party modules used
from bunch import Bunch
from bs4 import BeautifulSoup
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
import iso8601
import sqlalchemy
from sqlalchemy.orm.exc import NoResultFound

# OGL modules used
from inventory.settings import LOG, XL, _HDRS
from inventory.settings import _BORING_MAKES, _INTERESTING_MODELS, _INTERESTING_WORDS
from inventory.settings import _MAKES, _MODELS, _TAGS, _TAG_RELS, load_refdata_cache
from orm.models import Listing


# GuessDate class:
#
# guesses a date from the object passed in & returns a datetime
#
# NOTES:
# inputs handled:
#     string with any of these date formats:
#     datetime
#     number (int or float) containing utime info
# to force a ValueException on failure to parse, call with default=False.
# datetime returned will be TZ-aware & in UTC unless instructed otherwise.
# optimization: string format most recently successful is retained and tried
# first if guess_date() is called again within the same process space.
# this is a class to cleanly encapsulate storing date format(s) across calls
#
# some practical info/common inputs:
# ebay uses iso8601 date & time strings with trailing Z indicating UTC
# 3taps uses unix timestamps in ints
#
# SEE ALSO: force_date() method in oglweb.listings.utils
#
class GuessDate(object):
    def __init__(self):
        self._successful_format = None
        self._formats = [
            'timestamp',  # mock format string, use datetime.fromtimestamp()
            'iso8601', # mock format string, use iso8601.parse_date()
            '%Y-%m-%dT%H:%M:%S', # used by eBay
        ]

    def _try(self, maybedate, format):
        d = None
        try:
            if format == 'timestamp':
                # specialcasing this as a mock format
                d = datetime.datetime.fromtimestamp(float(maybedate))  # UTC
            elif format == 'iso8601':
                d = iso8601.parse_date(maybedate)
            else:
                d = datetime.datetime.strptime(maybedate,
                                               format).replace(tzinfo=tzinfo)
        except (ValueError, TypeError):
            pass
        return d

    def __call__(self, maybedate, default=None, tzinfo=pytz.UTC):
        if isinstance(maybedate, datetime.datetime):
            if maybedate.tzinfo and maybedate.tzinfo.utcoffset(maybedate) != None:
                # any TZ-aware/localized datetime will be returned as-is, not
                # converted to the specified TZ
                d = maybedate
            else:
                # assume we are in UTC & the date was intended that way
                # UNSAFE TZ HANDLING, but in our usage better than failing
                d = pytz.utc.localize(maybedate)
        elif isinstance(maybedate, str):

            # try whatever worked last time
            fmt = self._successful_format
            d = self._try(maybedate, fmt)

            if not d:
                # try everything else
                for format in self._formats:
                    if format != fmt:  # tried that one already above...
                        d = self._try(maybedate, format)
                        if d:
                            self._successful_format = format  # try 1st next time
                            break

        elif isinstance(maybedate, float) or isinstance(maybedate, int):
            try:
                d = datetime.datetime.fromtimestamp(maybedate)
            except ValueError:
                pass
        else:
            pass # we're screwed -- fall through to the fail

        if not d:
            if default==False:  # caller wants exception on failure to parse
                raise ValueError
            else:
                d = default
        return d

# create a file global callable for the class
guessDate = GuessDate()

LOG = logging.getLogger(__name__)

class ImportReport(object):
    def __init__(self):
        self.counts = {}
        self.accepted_lsinfos = []
        self.rejected_lsinfos = []

    def add_accepted_lsinfo(self, lsinfo):
        self.accepted_lsinfos.append(lsinfo)

    def add_accepted_lsinfos(self, lsinfos):
        self.accepted_lsinfos += lsinfos

    def add_rejected_lsinfo(self, lsinfo):
        self.rejected_lsinfos.append(lsinfo)
        
    def add_rejected_lsinfos(self, lsinfos):
        self.rejected_lsinfos += lsinfos

    def text_report(self, classified, logger=None):
        return

    def db_report(self, classified, session):
        return

# ============================================================================
# UTILITY METHODS
# ============================================================================


# regularize methods will take a string input that may be "messy" or
# vary a bit from site to site and regularize/standardize it

# def regularize_latlon
#
# take in a string that should contain a lat or lon number
# and return the lat or lon as a Decimal, or None. Note that
# exactly 0.0 is considered invalid and will become None
#
# GEE TODO: handle notation in minutes & seconds
#
def regularize_latlon(num_string):
    if num_string:
        try:
            latlon = Decimal(num_string)
            if latlon != Decimal(0) and abs(latlon) <= Decimal(180):
                return latlon
        except ValueError:
            pass
    return None


# def regularize_price
#
# take a price string, strip out any dollar signs and commas, convert
# to an int
# GEE TODO: this is US-format-only right now and doesn't handle decimals
# or other garbage yet ... or currencies!

def regularize_price(price_string):
    if price_string is None:
        price = -1
    elif isinstance(price_string, str):
        # strip out 'Price:' or similar if included
        if ':' in price_string:  # then take the part after the colon
            (junk, junk, price_string) = price_string.rpartition(':') # noqa
        # strip out any letters & irrelevant punctuation that might remain...
        price_string = re.sub(r'[a-zA-Z\!]', '', price_string)
        try:
            price = int(re.sub(r'[$,]', '', price_string))
        except ValueError:
            try:
                price = int(float(re.sub(r'[$,]', '', price_string)))
            except ValueError:
                price = -1
    else:  # was passed something other than a string (int, float, ...?)
        # lets try force-converting it; if that fails then....
        try:
            price = int(price_string)  # which isn't a string
        except (ValueError, TypeError):
            price = -1
    return price


# regularize year_make_model_fields
#
# takes 3 fields containing year, make, model and regularizes them 
#
# NOTES:
# this actually just concats the fields and wraps the main
# regularize_year_make_model() method. Seems backward but actually
# gives me the most flexibility to work with, even if the source
# may have split things differently than I would.
#
# Year is handled whether str or int. Missing/bad elements are omitted
# from the string, so e.g. year = "1963", make = None, model="Corvette"
# would become "1963 Corvette".
#
def regularize_year_make_model_fields(year, make, model):
    ymm_list = [elt for elt in [year, make, model] if elt]
    return regularize_year_make_model(' '.join(ymm_list))

# regularize_year_make_model
#
# take a string containing year, make, and model (e.g. '1970 ford thunderbird')
# and split (intelligently) into year, make, and model
#
# NOTES:
# for now this is stupid; will be enhanced to use make/model dict info
# will return None for any elements we can't figure out (e.g. if passed '')
#
def regularize_year_make_model(year_make_model_string):
    # GEE TODOs:
    # make a better splitter that understands multiword makes (e.g. Alfa Romeo)
    # use the year/make/model database to reality check / standardize
    year = None
    makemodel = None
    make = None
    model = None
    if year_make_model_string:  # is not None or ''
        words = year_make_model_string.split(" ")
        for word in range(0, len(words) - 1):
            try:
                s = words[word].strip("'`\"")  # strip likely junk (e.g. '67)
                s = s.split('.')[0]  # chop any trailing decimal (e.g. 1973.5)
                num = int(s)
                if num > 1900 and num < 2020:
                    year = num
                if num >= 20 and num <= 99:
                    year = 1900 + num
                if num < 20:
                    year = 2000 + num
                if year:  # only look for makemodel in the remaining words
                    if len(words) > word:
                        makemodel = words[(word+1):]
                break
            except ValueError:
                pass  # that wasn't it... no harm, no foul

        if not year:  # then we see no year in the offered string
            # this means we're not doing well and will probably trash this
            # anyway, but let's see what we get when we look for a make
            for word in range(0, len(words)-1):
                try:
                    s = words[0].strip("'` *~_\"\t")  # strip likely junk
                    ncm = _MAKES[s.upper()]
                    make = ncm.canonical_name
                    # apply the ncm's deltas, then take the rest as model
                    modellist = []
                    if word == len(words)-1:  # this is the end of the string
                        modellist = []
                    else:
                        modellist = words[(word+1):]
                    # GEE TODO handle multiple words here;
                    # for now just the first
                    if (
                            ncm.consume_list and modellist and
                            modellist[0] in ncm.consume_list
                    ):
                        modellist.pop(0)  # throw it away
                    if ncm.push_list:
                        modellist = ncm.push_list + modellist
                    # GEE TODO: check if the push word(s) are already there
                    # (e.g. 'vette corvette stingray')
                    model = ' '.join(modellist).strip("'` *~_\"\t")
                    break
                except KeyError:
                    pass  # that wasn't it... no harm, no foul
            # if the for loop finishes without finding a make, then screw it...
            # leave stuff blank

            makemodel = words  # use the whole list-of-words from the string

        elif year and makemodel:  # we did find both year and remaining string
            # jackpot!
            # GEE TODO: apply the real make/model regularization here
            make = makemodel[0].strip("'` *~_\"\t")
            try:
                model_list = []
                modelstem = []
                ncm = _MAKES[make.upper()]
                make = ncm.canonical_name
                makemodel.pop(0)  # throw away the noncanonical
                # GEE TODO handle multiple words here; for now just the first
                if (
                        ncm.consume_list and makemodel and
                        makemodel[0].upper() in ncm.consume_list
                ):
                    makemodel.pop(0)  # throw it away
                if ncm.push_list:
                    modelstem = ncm.push_list
                    # GEE TODO: check if the push word(s) are already there
                    # (e.g. 'vette corvette stingray')
                else:
                    modelstem = []
                model_list = modelstem + makemodel
            except KeyError:
                # didn't find it; assume we're OK with make as given
                make = make.title().strip("'` *~_\"\t") # initcap it
                if len(makemodel) > 1:
                    model_list = makemodel[1:]
            model = ' '.join(model_list).strip("'` *~_\"\t")
        else:  # found a potential year string but no make/model after it
            # this is likely a false positive; let's chuck even the year
            # and tell the caller we found nothing
            year = None
            make = None
            model = None

    return str(year), make, model  # backconvert year to string


# regularize_url()
#
# Regularizes a url
#
# parameters
# url: the url to be regularized (a string)
# base_url: if given, is used to convert relative URLs to absolute URLs
# absolute_only: if true and we can't form an absolute URL, return None
#
# Note: only returns http URLs (e.g. rejects tel: URLs)
#
def regularize_url(href_in, base_url=None,
                    absolute_only=True):

    href_out = None
    if href_in:
        # oops -- apparent bug. urlsplit doesn't recognize
        # tel:8005551212. It handles some variants but basically
        # expects at least one '/' somewhere.
        # Without that, it returns None as the scheme. We usually
        # don't want the tel scheme anyway, but we don't want to
        # mistake it for a relative http URL. So patch for it:
        if (href_in[:4] == 'tel:'):
            pass
        else:
            try:
                p = urllib.parse.urlsplit(href_in.strip())
                if p.scheme and p.netloc:
                    href_out = href_in  # complete & it works great
                elif base_url:
                    # was probably a relative URL; try to combine w/ base_url
                    href_candidate = urllib.parse.urljoin(base_url, href_in)
                    if not absolute_only:
                        href_out = href_candidate  # good enough
                    else:
                        p = urllib.parse.urlsplit(href_in.strip())
                        if p.scheme and p.netloc:
                            href_out = href_candidate
                else:  # incomplete URL and no base_url to combo with
                    if not absolute_only:
                        href_out = href_candidate  # good enough, hopefully
            except:
                pass  # well, that didn't work
    LOG.debug('regularized href=%s from input href=%s', href_out, href_in)
    return href_out


# validate_listing()
#
# takes in a completely-imported listing and determines whether to store it
# or throw it away as useless
#
# note that this is a VALIDITY test ie is-this-OK, not is-this-interesting
#
def validate_listing(listing, counts):
    ok = True
    if not listing.listing_href:
        ok = False
        counts['badurl'] += 1
    try:
        model_year_int = int(listing.model_year)
        if model_year_int < 1800 or model_year_int > 2020:
            ok = False
            counts['badyear'] += 1
    except:
        ok = False
        counts['badyear'] += 1
    return ok


# apply_post_tagging_filters()
#
# applies last set of validity & relevance checks before applying a listing
def apply_post_tagging_filters(listing, inv_settings, counts):
    if listing.status != 'F':
        return True # always willing to remove inventory

    if 'limited' in inv_settings and not listing.has_tag('interesting'):
        counts['rejected:uninteresting'] += 1
        return False # throw it away for limited inventory stages
    if listing.has_tag('rv'):
        counts['rejected:rv'] += 1
        return False
    return True

# make_sure_path_exists()
#
# utility method that will create any missing components of the given path
#
def make_sure_path_exists(path):
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    return True


# is_car_interesting()
#
# crummy kludge to filter to cars we want for now vs ones we don't
#
# parameters:
# listing: the listing to examine
# unknown_make_is_interesting: if True then an unknown make is interesting
# (defaults to True because this catches good oddities; set to False for
# particularly dirty sources where you have lots of junky records)
#
def is_car_interesting(listing, unknown_make_is_interesting=True):
    if int(listing.model_year) > 1800 and int(listing.model_year) <= 1975:
        return True # automatically interesting
    if int(listing.price) > 100000: # Prima facia evidence of interesting? :)
        return True
    if not unknown_make_is_interesting:
        # any known make should already be regularized so we don't need
        # to worry about fuzzy matching here:
        if listing.make and listing.make.upper() in _MAKES:
            pass  # known make; continue
        else:
            return False  # unknown make is, in this case, uninteresting

    # GEE TODO: case of comparisons & substrings make this.... interesting.
    # we need to split model to model/submodel, then us db rels/orm model
    # objects to make all this easier to handle without all the string stuff

    # keep everything that isn't from a boring make
    # listing.make is regularized (ie spelled & capitalized consistently),
    # at least for any boring make (ie for the cases that matter here):
    if listing.make not in _BORING_MAKES:
        # wow is this inefficient - need make/model db stuff
        return True

    # keep particular models even from boring makes
    # model is NOT reliably regularized so we have to do some extra work
    # first check primary model designation (first word)
    if listing.model and listing.model.split(' ')[0].upper() in _INTERESTING_MODELS:
        return True
    # and keep specific sub-models/trim & cars with other "interesting" signals
    # some sources will have lots of words in the "model" field for trim;
    # other sources (notably ebay) do not & we really need to use listing_text
    #
    # GEE TODO: improve this for consistency (some sites are getting minimal
    # listing text from subject while others are importing more lengthy text)
    # & to not reward sellers stuffing keywords in listing titles
    # (e.g. "1992 mercury capri like miata")
    if listing.model:
        for word in listing.model.upper().split(' '):
            if word in _INTERESTING_WORDS:
                return True
    if listing.listing_text:
        for word in listing.listing_text.upper().split(' '):
            if word in _INTERESTING_WORDS:
                return True
    # heh, can't think of any reason to keep this record, so...
    return False



# soup_from_file()
#
# intended for interactive use only; quickly soupify a file for testing.
#
def soup_from_file(path):
    with open(path) as file:
        return BeautifulSoup(file)


# soup_from_url()
#
# intended for interactive use only; quickly soupify a file for testing.
#
def soup_from_url(url):
    try:
        req = urllib.request.Request(url, headers=_HDRS)
        page = urllib.request.urlopen(req)
    except urllib.error.HTTPError as error:
        LOG.error('Unable to load inventory page ' + url + ': HTTP ' +
                  str(error.code) + ' ' + error.reason)
        return None

    if page.getcode() != 200:
        LOG.error('Failed to pull an inventory page for ' + url +
                  ' with HTTP response code ' + str(page.getcode()))
        return None

    return BeautifulSoup(page)


# clear_listing_sourceinfo()
#
# Nukes listing_sourceinfo records
#
# parameters:
#   source_type, source_id: if only type is provided, will clear
#     everything for the given type
#
def clear_listing_sourceinfo(session, source_type, source_id=None):
    stmt = "delete from listing_sourceinfo where source_type = :source_type"
    parms = {'source_type': source_type}
    if source_id:
        stmt += " and source_id = :source_id"
        parms['source_id'] = source_id
    result = session.execute(stmt, parms)
    if source_id:
        LOG.debug('Deleted listing_sourceinfo for all %s', source_type)
    else:
        LOG.debug('Deleted listing_sourceinfo for %s %s',
                  source_type, source_id)
    return result.rowcount


# mark_listings_pending_delete()
#
# Normally used in preparation for a pull, to help id records that we will need
# to delete if they are not found in the current pull
#
def mark_listings_pending_delete(source_type, source_id, session):
    # mark the active listings stored in the db for this classified
    result = session.execute(
        "update listing set markers = concat(ifnull(markers, ''), 'P') "
        "where source_type = :source_type and source_id = :source_id "
        "and status = 'F'",
        {'source_type': source_type, 'source_id': source_id})
    LOG.debug('Painted %s existing records for %s site %s',
              result.rowcount, source_type, source_id)
    return result.rowcount


# remove_marked_listings()
#
# set status to 'R' on all the listings marked pending-delete
# (which is normally those existing before a pull and not found in the pull)
#
# returns the number of listings removed
#
def remove_marked_listings(source_type, source_id, session, es=None):

    # we have to load each one in order to remove it from the es index
    # GEE TODO: can I improve this to use an es delete-by-query somehow?
    # I think I would have to do an es-mark-all query like I do with the db;
    # any other solution would involve generating the set to pass to es
    # so for now, let's just iterate
    if es:
        LOG.info('Removing listings that have been taken down '
                 'since the last pull')
        result = session.execute(
            "select id from listing "
            "where source_type = :source_type and source_id = :source_id "
            "and instr(ifnull(markers, ''), 'P') != 0",
            {'source_type': source_type, 'source_id': source_id})
        if es:
            for row in result:
                listing_id = row[0]
                try:
                    es.delete(index="carbyr-index",
                              doc_type="listing-type",
                              id=listing_id)
                except NotFoundError as err:
                    LOG.debug('record with id=%s not found during ' +
                              'attempted deletion: %s',
                              listing_id, err)

    # mark them all in the db in one query to avoid per-record round-trips
    # NOTE: we didn't pull the full rows into Listing objects, so we can't
    # update that way
    result = session.execute(
        """update listing
              set status = 'R',
                  markers = replace(markers, 'P', ''),
                  removal_date = ifnull(removal_date, CURRENT_TIMESTAMP),
                  last_update = CURRENT_TIMESTAMP
            where source_type = :source_type and source_id = :source_id
              and instr(ifnull(markers, ''), 'P') != 0""",
        {'source_type': source_type, 'source_id': source_id})
    LOG.debug('Marked %s rows as no longer active on %s site #%s',
              result.rowcount, source_type, source_id)
    return result.rowcount


# add_or_update_found_listing
#
# used to add a listing found from a source to the db, or update the existing
# record for that listing if there is one. Has some special-case logic.
#
# parameters:
# session: db session
# current_listing: the listing as most recently pulled from a source
#
# returns a new listing object that is embedded in the current session
#
# NOTES:
#
# The input listing is NOT modified, and thus becomes out-of-date!
# Throw it away, e.g.:
#
# my_listing = add_or_update_found_listing(session, my_listing)
#
# this method searches the db for potential matches and ensures matched records
# are updated in the db (including removing any pending-delete marker, if the
# passed-in listing is not so marked)
#
# matching is always/only by local_id
#
# Markers (other than pending-delete) and tags will carry forward (union)
# between existing and new listing records
#
# also: if there is a matching record, the new record overrides most fields
# but will NOT override or otherwise affect a record that has a status of
# 'X' (removed, not-a-valid-listing).
#
# new listings will NOT have an id in them, but will receive one when next the
# session is flushed
#
def add_or_update_found_listing(session, current_listing):

    LOG.debug('checking on existence of listing %s',
              current_listing.local_id)
    try:
        existing_listing = session.query(Listing).filter_by(
            local_id=current_listing.local_id,
            source_type=current_listing.source_type,
            source_id=current_listing.source_id).one()

        LOG.debug('found: {}'.format(existing_listing))

        # remove pending-delete marker, if present
        if existing_listing.markers:
            s = set(existing_listing.markers)
            if 'P' in s:
                s.remove('P')
                existing_listing.markers = ''.join(s)

        if existing_listing.status == 'X':
            # record has been excluded, do not reactivate it
            # make no other changes (besides pending-delete flag above)
            return existing_listing # already in session; discard new listing
        # note that other records CAN be returned to 'F' status by
        # an active update record... which can lead to removal_date wonkiness

        # sometimes updates will be deletion requests that are placeholder
        # posting records without full/proper details on them. In this case
        # keep the existing listing (for history) and just mark it removed...
        if current_listing.status == 'R' and current_listing.model_year == '1':
            # deletion presumed to lack details/be less accurate than original
            existing_listing.status = current_listing.status
            # GEE TODO: this should be server/db time, not python time: how?!
            existing_listing.removal_date = datetime.datetime.now()
            return existing_listing # already in session; discard new listing

        # ... otherwise  mark the current record with the id of the
        # existing record and carry forward (merge) tags and markers, etc
        current_listing.id = existing_listing.id
        current_listing.add_tags(existing_listing.tagset)
        current_listing.add_markers(existing_listing.markers)
        current_listing.listing_date = existing_listing.listing_date
        # set removal date to record actual deletion date if we are deleting
        if current_listing.status == 'F':
            if current_listing.removal_date and existing_listing.removal_date:
                # set removal_date to the shortest of original & update;
                # while this is an issue for sources where updates can be
                # used to extend the life of the listing, most normal
                # updates (e.g. price drops) do NOT extend posting lifetime
                current_listing.removal_date = \
                        min(current_listing.removal_date,
                            existing_listing.removal_date)
            elif existing_listing.removal_date:
                # had a removal_date set already so preserve it
                current_listing.removal_date = existing_listing.removal_date
            else:
                # leave current_listing.removal_date alone even if it is null
                # (certain active records -- from dealers -- don't expire)
                pass
        else:
            # not/no longer active: set removal_date to actual deletion date
            if existing_listing.status != 'F' and existing_listing.removal_date:
                # already removed & date already set -- do not overwrite it
                current_listing.removal_date = existing_listing.removal_date
            else:
                # well, it is deleted/inactive now...
                current_listing.removal_date = datetime.datetime.now()
        # all other fields will be taken from the current listing record

    except NoResultFound:
        LOG.debug('no match for local_id=%s',
                  current_listing.local_id)
        pass # current_listing will not get an id until merge & flush

    # GEE TODO: this setting of last_update should not be required, but...
    current_listing.last_update = datetime.datetime.now()
    return session.merge(current_listing) # behavior dependent upon id


# record_listings()
#
# records the results of processing some listings in mysql & es
#
# this method commits (it has to commit midway, in fact, in order to
# generate ids that allow us to link listings and lsinfos and pass ids
# to es
#
# GEE TODO: check if I could be using a flush() rather than a commit()?
#
# returns nothing
#
def record_listings(listings, accepted_lsinfos, rejected_lsinfos,
                    source_textid, session, es):

    # now put the located records in the db & es index
    # with sqlalchemy, we get new objects back so build a list of those
    db_listings = []

    # this if, and the others outside for loops, are because empty lists []
    # are sometimes being turned into Nones, so absent the if test we will
    # explode trying to iterate on the NoneType to set up the for loop (sigh)
    if listings:
        for listing in listings:
            db_listings.append(add_or_update_found_listing(session, listing))

        # commit the block of listings (which generates ids on new records)
        # also commits everything else, e.g. updated classified.anchors, etc
        session.commit()
        LOG.debug('committed a block of listings for %s',
                  source_textid)

    # now using those db_listings with ids we can continue...

    if es:
        # put the listings in the text index
        for listing in db_listings:
            index_listing(es, listing)

    # store lsinfos for future debugging/reference
    if (db_listings and accepted_lsinfos):
        accepted_lsinfos_with_listings = zip(accepted_lsinfos, db_listings)
        for lsinfo, ls in accepted_lsinfos_with_listings:
            if lsinfo and ls:
                lsinfo.listing_id = ls.id
                session.add(lsinfo)
            elif ls:
                LOG.warning('db_listing without ls_info')
            elif lsinfo: 
                LOG.warning('ls_info without db_listing')
    if (rejected_lsinfos):
        for lsinfo in rejected_lsinfos:
            session.add(lsinfo)
    session.commit()  # commit again for the lsinfos
    return


# index_listing
#
# adds a listing to the carbyr elasticsearch index
# (or removes the listing from the index if the status != 'F')
#
# NOTES:
#
# es seems to automatically handle duplicates by id, so relying on that for now
#
# only indexing the fields, NOT sucking in the full listing detail pages
# (but we could, if we added the page text to the listing dict)
#
def index_listing(es, listing):
    if listing.status == 'F':
        # elasticsearch uses the builtin JSON serialization module, which does
        # not understand arbitrary objects nor does it understand certain types
        # (DateTime, Numeric->Decimal). Fortunately our model types know how to
        # convert themselves to "JSON-safe" dicts....
        if isinstance(listing, Listing):
            listing_d = Bunch(dict(listing))
        else:
            # if we got some other flavor of listing then hope it is safe
            listing_d = listing

        # create a virtual location field that es understands from the lat/lon
        # I don't like this hackery here but otherwise I have to combine the
        # lat/lon into a single varchar field on the db record (ick) or do a
        # MySQL geopoint thing & make es understand that (yikes)....

        if listing_d.lat and listing_d.lon:
            listing_d.location = {
                'lat': listing_d.lat, 'lon': listing_d.lon}

        es.index(index="carbyr-index", doc_type="listing-type",
                 id=listing_d['id'], body=listing_d)
    else:
        try:
            es.delete(index="carbyr-index", doc_type="listing-type",
                      id=listing.id)
        except NotFoundError as err:
            LOG.debug('record with id=%s not found during attempted ' +
                      'deletion: %s',
                      listing.id, err)
            # NOTE: this can easily happen if we find a record of a SOLD car
            # but did not already have the car listing open
    return True


# text_store_listing
#
# stores a text file (suitable for text indexing) of the given listing
# in the given directory
#
def text_store_listing(list_dir, listing):
    # store car listing file in subdir by source (not the best, heh --
    # temporary, should really be some more reliable sharding mechanism)
    # and with the id (our internal id) as the filename root
    make_sure_path_exists(list_dir + '/' + listing.source_textid)
    pathname = str(list_dir + '/' + listing.source_textid + '/' +
                   str(listing.id) + '.html')
    list_file = open(pathname, "w")
    list_file.write(listing)
    list_file.close()

    LOG.debug("wrote listing id {} ({} {} {}) to file {}".format(
        listing.id, listing.model_year, listing.make, listing.model, pathname))
    return True


# validate_year_make_model()
#
# validates year/make/model (well, the first 2 are sufficient)
#
# returns: True iff year/make/model is sufficient to proceed
#
# WARNING: can modify model_year field!
#
# GEE TODO: split out validation and overwriting of model_year
# and move validation to separate method
#
def validate_year_make_model(listing, counts):
    ok = True
    if not listing.model_year and not listing.model:
        ok = False
        LOG.warning('skipping item with no year/make/model info: %s',
                    listing.local_id)
        counts['badmakemodel'] += 1
    else:
        try:
            int(listing.model_year)
        except (ValueError, TypeError):
            ok = False
            listing.model_year = '1'
            LOG.debug('bad year [%s] for item %s',
                      listing.model_year, listing.local_id)
            counts['badyear'] += 1
    return ok


