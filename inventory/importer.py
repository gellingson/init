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
from base64 import b64decode
import datetime
import errno
import json
import logging
import os
import re
import sys
import urllib.request
import urllib.error
import urllib.parse

# third party modules used
from bunch import Bunch
from bs4 import BeautifulSoup
from ebaysdk.finding import Connection as ebaysdk_finding
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import NotFoundError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.exc import NoResultFound

# OGL modules used
from orm.models import Classified, Dealership, Listing
from orm.models import ConceptTag, ConceptImplies
from orm.models import NonCanonicalMake, NonCanonicalModel, Zipcode


# ============================================================================
# CONSTANTS AND GLOBALS
# ============================================================================

# GEE TODO refine this: what headers do we want to send?
# some sites don't want to offer up inventory without any headers.
# Not sure why, but let's impersonate some real browser and such to get through
_HDRS = {
    'User-Agent': ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11'
                   '(KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11'),
    'Accept': ('text/html,application/xhtml+xml,application/xml;q=0.9,'
               '*/*;q=0.8'),
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive'
}

_BORING_MAKES = [
    'Dodge', 'Chrysler', 'Ram', 'RAM', 'Jeep',
    'Honda', 'Acura', 'Toyota', 'Lexus', 'Scion', 'Nissan', 'Infiniti',
    'Mazda', 'Subaru', 'Isuzu', 'Mitsubishi',
    'Chevrolet', 'Pontiac', 'Saturn', 'Cadillac', 'Buick', 'Oldsmobile',
    'GM', 'General', 'GMC',
    'Ford', 'Mercury', 'Lincoln',
    'BMW', 'Mini', 'MINI', 'Mercedes', 'Mercedes-Benz', 'MB',
    'Volkswagen', 'VW', 'Audi',
    'Fiat', 'Volvo', 'Land Rover', 'Range Rover', 'Saab',
    'Hyundai', 'Kia', 'Suzuki',
    'Smart'
]

_INTERESTING_MODELS = [
    'Viper',
    'NSX', 'MR2', 'MR-2', 'Supra', 'LFA', '300zx', 'Skyline', 'GTR',
    'MX5', 'MX-5', 'Miata', 'MX-5 Miata', 'rx7', 'STI', 'Evolution', 'Evo',
    'Corvette', 'Grand National',
    'Boss', 'Shelby', 'GT',
    'M3', 'M5', 'M6', 'SLS', 'AMG', 'R8'
]

# global hashes (caches) of refdata objects from the db, populated at startup
_MAKES = {}
_MODELS = {}
_TAGS = {}
_TAG_RELS = {}

# ============================================================================
# UTILITY METHODS
# ============================================================================


# load_refdata_cache
#
# cache some stable (read-only) db entries into globals for quicker access
# GEE TODO: these reference data may outgrow this approach eventually...
#
def load_refdata_cache(session):

    all_ncms = session.query(NonCanonicalMake).all()
    for ncm in all_ncms:
        _MAKES[ncm.non_canonical_name] = ncm

    all_ncms = session.query(NonCanonicalModel).all()
    for ncm in all_ncms:
        _MODELS[ncm.non_canonical_name] = ncm

    all_tags = session.query(ConceptTag).all()
    for tag in all_tags:
        _TAGS[tag.tag] = tag

    # hash of form tag -> list of implied tags
    all_rels = session.query(ConceptImplies).all()
    for rel in all_rels:
        # create or add to the given tag's list of implied tags
        if rel.has_tag_id in _TAG_RELS:
            _TAG_RELS[rel.has_tag_id].append(rel.implies_tag_id)
        else:
            _TAG_RELS[rel.has_tag_id] = [rel.implies_tag_id]
    return


# regularize methods will take a string input that may be "messy" or
# vary a bit from site to site and regularize/standardize it

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
        # strip out any letters that might remain...
        price_string = re.sub(r'[a-zA-Z]', '', price_string)
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
                        makemodel[0] in ncm.consume_list
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

        return (str(year), make, model)  # backconvert year to string


# tagify()
#
# examines a listing and adds tags
#
# ok if the listing already has tags; this will be additive, not replace
# (but conflicting tags may be removed; e.g. if we determine this is a
# sportscar we might remove an suv tag if one exists on the listing)
#
# NOTE: THIS MAY ALSO MODIFY OTHER ASPECTS OF THE LISTING!
#
def tagify(listing):
    new_tags = []
    remove_tags = []  # not sure if we want to do this...
    make = None

    # GEE TODO: maybe we should be doing some of this tagging in the
    # relevant regularize() methods?

    if (
            listing.make and listing.make.upper() in _MAKES and
            _MAKES[listing.make.upper()].canonical_name == listing.make
    ):
        make = _MAKES[listing.make.upper()]
        new_tags.append('known_make')
    else:
        new_tags.append('unknown_make')

    # models may be 1 or 2 words long, and it is OK if the listing has
    # extra words on the end of the model string; ignore them
    if make and listing.model:
        model = None
        modelwordlist = listing.model.split(' ')
        if (
                modelwordlist[0].upper() in _MODELS and
                _MODELS[modelwordlist[0].upper()].non_canonical_make_id == make.id
        ):
            model = _MODELS[modelwordlist[0].upper()]
        elif len(modelwordlist) >= 2:
            twowordmodel = ' '.join(modelwordlist[:2]).upper()
            if (
                    twowordmodel in _MODELS and
                    _MODELS[twowordmodel].non_canonical_make_id == make.id
            ):
                model = _MODELS[twowordmodel]
        if model:

            logging.debug('found model: %s', model.canonical_name)
            new_tags.append('known_model')
            if model.canonical_name == 'Miata':
                if listing.model_year <= '1994':
                    new_tags.append('NA6')
                    new_tags.append('NA')
                elif listing.model_year <= '1997':
                    new_tags.append('NA8')
                    new_tags.append('NA')
                elif listing.model_year <= '2005':
                    new_tags.append('NB')
                elif listing.model_year <= '2014':
                    new_tags.append('NC')
                else:
                    new_tags.append('ND')
            if model.canonical_name == 'Corvette':
                if listing.model_year <= '1962':
                    new_tags.append('C1')
                elif listing.model_year <= '1967':
                    new_tags.append('C2')
                elif listing.model_year <= '1983':
                    new_tags.append('C3')
                elif listing.model_year <= '1996':
                    new_tags.append('C4')
                elif listing.model_year <= '2004':
                    new_tags.append('C5')
                elif listing.model_year <= '2013':
                    new_tags.append('C6')
                else:
                    new_tags.append('C7')
        else:
            new_tags.append('unknown_model')

        # GEE TODO: method not yet implemented; also, resolve handling of
        # text and ConceptTag objects!
        #implied_tag_set = set()
        #for tag in new_tags:
        #    implied_tag_set.add(_TAGS[tag].implied_tags())
        #new_tags.append(implied_tag_set)

    if new_tags:
        logging.debug('adding tags: %s for %s %s %s',
                      new_tags, listing.model_year,
                      listing.make, listing.model)
    else:
        logging.debug('no new tags')
    listing.add_tags(new_tags)

    # GEE TODO: if I'm really going to use this mechanism (much) then
    # I should make a remove_tags() method
    for tag in remove_tags:
        listing.remove_tag(tag)


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
    if not unknown_make_is_interesting:
        if listing.make not in _MAKES:
            return False
    # GEE TODO: case of comparisons & substrings make this.... interesting.
    # we need to split model to model/submodel, then us db rels/orm model
    # objects to make all this easier to handle without all the string stuff
    if listing.make not in _BORING_MAKES:
        # wow is this inefficient - need make/model db stuff
        return True
    # pull particular models back in
    if listing.model and listing.model.split(' ')[0] in _INTERESTING_MODELS:
        return True
    if int(listing.price) > 100000: # Prima facia evidence of interesting? :)
        return True
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
        logging.error('Unable to load inventory page ' + url + ': HTTP ' +
                      str(error.code) + ' ' + error.reason)
        return None

    if page.getcode() != 200:
        logging.error('Failed to pull an inventory page for ' + url +
                      ' with HTTP response code ' + str(page.getcode()))
        return None

    return BeautifulSoup(page)


# ============================================================================
# PARSING METHODS
# ============================================================================

# placeholder method to copy-and-paste to form a new dealership-specific parse
#
def new_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing.model_year,
     listing.make,
     listing.model) = regularize_year_make_model('')

    listing.listing_text = ''

    # pull the rest of the fields from the detail page

    listing.price = regularize_price('')

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
     listing.model) = regularize_year_make_model(entry.find('h1').text)

    try:
        listing.price = regularize_price(
            entry.find(class_='vehicleMainPriceRow').text)
    except AttributeError:
        listing.price = -1

    # doesn't have listing text on inventory page
    try:
        listing.listing_text = detail.find(
            class_='innerDescriptionText').find('p').text
    except AttributeError:
        listing.listing_text = ''

    return True


# carbuffs_parse_listing
#
#
def carbuffs_parse_listing(listing, entry, detail):

    # get the short listing text from the inventory page
    listing.listing_text = entry.find(class_="car-excerpt").text

    # pull the rest of the fields from the detail page
    (listing.model_year,
     listing.make,
     listing.model) = regularize_year_make_model(
         detail.find(class_='car-name').text)

    # common name/value patterns in details page:
    # <li><strong>Car model year:</strong> 1963</li>
    # <p class="car-asking-price"><strong>Asking Price:</strong> $89,950</p>
    pe = detail.find('strong', text='Asking Price:')
    if pe is not None:
        pe = pe.next_sibling
    listing.price = regularize_price(pe)

    return True


def ccw_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing.model_year,
     listing.make,
     listing.model) = regularize_year_make_model(entry.find('strong').text)

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
     listing.model) = regularize_year_make_model(entry.find('a').text)

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
     listing.model) = regularize_year_make_model(strings[0])

    listing.listing_text = strings[1]

    # no real patterns to mine on the details page.
    # but hey, at least it has the price! (unlike the inventory page)
    pe = detail.find(text=re.compile(r'Asking Price:'))
    if pe is not None:
        pe = pe.split(':')[-1]
    listing.price = regularize_price(pe)

    return True


# dawydiak_parse_listing
#
# used for both porsche and non-porsche inventory from Cars Dawydiak
#
def dawydiak_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page

    # if dawydiak has any listing text, it's in the introlist
    listing.listing_text = entry.find(class_='introlist').text

    if entry.find(class_='dscprice'):
        listing.price = regularize_price(entry.find(class_='dscprice').text)

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

    # get the short listing text from the inventory page
    listing.listing_text = entry.find(class_="entry-subheader blue").get_text()

    # pull the rest of the fields from the detail page

    if detail.find('title'):
        s = detail.find('title').text
        (listing.model_year,
         listing.make,
         listing.model) = regularize_year_make_model(s)

    listing.local_id = detail.find(id="ContactCarId")['value']
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
    listing.price = regularize_price(price_string)

    return True


# lc_parse_listing
#
# this method handles both left coast classics (lcc) and
# left coast exotics (lce)
#
def lc_parse_listing(listing, entry, detail):

    logging.debug(entry)
    logging.debug(detail)
    # first of all, since the inventory page has so little useful tagging
    # we may get some entries that are not really car listings. Detect
    # them here and return False...
    if entry.name != 'tr':
        logging.debug('skipping putative entry because it is not in '
                      'a <tr> (was a {})'.format(entry.name))
        return False

    # as with cvc, there is no useful tagging....
    # we just have to make the best of it

    # get the short listing text from the inventory page
    listing.listing_text = entry.find('h3').text

    # price is only on the inventory page, not on the detail page (!)
    # and it's often missing (text will just be CALL, SOLD, etc)
    price_string = entry.find('h2', align='center')
    if price_string is not None:
        price_string = price_string.text
    listing.price = regularize_price(price_string)

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
         listing.model) = regularize_year_make_model(s)

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
     listing.model) = regularize_year_make_model(entry.find('h2').text)

    # GEE TODO: some don't have any description, but others do
    # (on the detail page)
    listing.listing_text = ''

    # pull the rest of the fields from the detail page
    listing.price = regularize_price(entry.find('span').text)

    return True


# sfs_parse_listing
#
def sfs_parse_listing(listing, entry, detail):

    # get some stuff from the inventory page
    (listing.model_year,
     listing.make,
     listing.model) = regularize_year_make_model(entry.find('h2').text)

    listing.listing_text = entry.find('h3').text

    if entry.find('h6'):
        listing.price = regularize_price(entry.find('h6').text)
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

    # get the short listing text from the inventory page
    listing.listing_text = entry.get_text()

    # grab price from the main listings page entry
    if entry.find(class_='vehicle-price-label'):
        price_string = entry.find(class_='vehicle-price-label').text
    else:
        price_string = ''
    listing.price = regularize_price(price_string)

    # grab year/make/model
    if entry.find(class_='vehicle-heading'):
        s = entry.find(class_='vehicle-heading').text
    else:
        s = ''
    (listing.model_year,
     listing.make,
     listing.model) = regularize_year_make_model(s)

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

    # implicit param from environment:
    # [currently unused in dealer pulls, but for consistency & future use...]
    # inv_settings = os.environ.get('OGL_INV_SETTINGS', '')

    list_of_listings = []
    last_local_id = None

    # get a page of listings; we have pagination logic to loop over addl pages

    try:
        full_inv_url = urllib.parse.urljoin(dealer.base_url,
                                            dealer.inventory_url)
        logging.info('Pulling ' + dealer.textid + ' inventory from ' +
                     full_inv_url + '....')
        req = urllib.request.Request(full_inv_url, headers=_HDRS)
        page = urllib.request.urlopen(req)
    except urllib.error.HTTPError as error:
        logging.error('Unable to load inventory page ' + full_inv_url +
                      ': HTTP ' + str(error.code) + ' ' + error.reason)
        return list_of_listings

    # GEE TODO: handle URLError that might have been raised...
    if page.getcode() != 200:
        logging.error('Failed to pull an inventory page for ' + full_inv_url +
                      ' with HTTP response code ' + str(page.getcode()))
        return list_of_listings

    while True:
        # soupify it
        soup = BeautifulSoup(page)

        # extract all the listings
        myfunc = eval(dealer.extract_car_list_func)

        listings = myfunc(soup)
        logging.info('Number of car listings found: {}'.format(len(listings)))
        for item in listings:
            ok = True
            listing = Listing()
            listing.source_type = 'D'
            listing.source_id = dealer.id
            listing.source_textid = dealer.textid

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
                    logging.warning('found non-http detail URL: %s',
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
                        logging.debug('detail page: ' + listing.listing_href)
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
                        logging.error('Unable to load detail page ' +
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
                        listing.listing_text = tag.text
            # if that failed, try to find something on the detail page
            if detail and not listing.listing_text:
                for tag in detail.descendants:
                    if tag.name in ['p', 'div', 'li', 'span', 'td']:
                        if (
                                len(tag.text) > 50 and
                                len(tag.text) > len(listing.listing_text)
                        ):
                            listing.listing_text = tag.text

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
            listing.price = regularize_price(
                entry.find(text=re.compile(r'\$[0-9]')))
            # try detail page if we didn't get one from the inventory page
            if listing.price == -1 and detail:
                listing.price = regularize_price(
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
                    logging.warning('Duplicate local_ids '
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
                if is_car_interesting(listing):
                    listing.add_tag('interesting')
                tagify(listing)
                list_of_listings.append(listing)
                logging.debug('pulled listing: {}'.format(listing))
            else:
                logging.warning('skipped listing: {}'.format(listing))

            # END LOOP over listings on the page

        # Is there another page of listings? Look for a link with "next" text.
        # Note: there may be multiple such links (e.g. @ top & bottom of list).
        # They should be identical so just grab the first
        next_ref = soup.find('a', text=re.compile(r"[Nn]ext"))
        if next_ref:
            # build the full URL (it may be relative to current URL)
            full_inv_url = urllib.parse.urljoin(
                full_inv_url, next_ref.get('href'))
            logging.debug('Loading next page of inventory via URL: %s',
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

    logging.info('Loaded ' + str(len(list_of_listings)) + ' cars from ' +
                 dealer.textid)
    return list_of_listings


# pull_classified_inventory()
#
# pulls inventory from common classified sites as directed
#
# NOTES: NOT WRITTEN YET; need to understand if this really != dealer method
#
def pull_classified_inventory(classified, inventory_marker=None, session=None):
    return [], inventory_marker


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
# list_of_listings: a set of listings (could be partial or entire set)
# inventory_marker: pagination/subset marker (will be None if done)
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
# GEE TODO: chunking by years may not be entirely sufficient to avoid the 10K
# limit (and gives us some pretty big work bundles). Should get more granular.
#
def pull_ebay_inventory(classified, inventory_marker=None, session=None):

    # implicit param from environment:
    inv_settings = os.environ.get('OGL_INV_SETTINGS', '')

    list_of_listings = []

    # wonky workaround for ebay's 10K limit. Mostly we can split by model years
    # but for years with lots of inventory (basically the current model year)
    # we have to further subdivide or we run past 10K when not restricting to
    # local cars only

    # we use a magic value for the second year in a batch being 1, indicating
    # that the batch is one year only and must be further subdivided by color

    ebay_year_batches = [
        (1900, 1960), (1961, 1970), (1971, 1980),
        (1981, 1990), (1991, 1995), (1996, 1999),
        (2000, 2003), (2004, 2005), (2006, 2006),
        (2007, 2007), (2008, 2008), (2009, 2009),
        (2010, 2010), (2011, 2011), (2012, 2012),
        (2013, 2013), (2014, 1), (2015, 2015)
    ]

    # for any years that are too big we further segment by color (!)
    # (hey, it splits the inventory into reasonably-suitable chunks)
    colors = [
        'NotSubBatching', 'Black', 'Blue', 'Brown', 'Burgundy', 'Gold',
        'Gray', 'Green', 'Orange', 'Purple', 'Red', 'Silver', 'Tan',
        'Teal', 'White', 'Yellow', 'Not Specified'
    ]

#    if inv_settings == 'limited':
#        # overwrite with a simpler set of buckers, with no sub-buckets
#        ebay_year_batches = [ (1900, 2010), (2011, 2012), (2013, 2013),
#             (2014, 2014), (2015, 2020) ]

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
            'pageNumber': 1}
        }

    if 'local' in inv_settings:
        logging.debug('limiting to local cars')
        api_request['itemFilter'].append({'name': 'MaxDistance',
                                          'value': 150})
    else:
        logging.debug('NOT limiting to local cars')

    logging.info('batch {} sub {}'.format(inventory_marker['batch'],
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
    logging.debug('eBay API request: {}'.format(api_request))

    while True:

        # NOTE: in case of various issues we can break out of this loop, but
        # we must be careful not to break out of the enclosing (batch) loop
        # to avoid potentially mangling inventory_marker handling

        # pull a page
        response = api.execute('findItemsAdvanced', api_request)
        r = response.dict()
        if r['ack'] != 'Success':
            # Hmm, when I get an error back from eBay the response can't be
            # JSON dumped for some reason. This command barfs saying it isn't
            # JSON serializable:
            # print(response.json().dump())
            print(response.json())
            logging.error('eBay reports failure: {}'.format(response))
            break # note: breaks out of loop over pages
        # _count may be empty, or '0', or 0, or... who knows, but skip it
        if (
                not r['searchResult']['_count']
                or int(r['searchResult']['_count']) == 0
        ):
            logging.warning('eBay returned a set of zero records')
            break # note: breaks out of loop over pages

        # note: _count may not be present if we got a bad fetch from eBay;
        # hopefully we've done all our checks above and called a break...
        logging.info('Number of car listings found: %s',
                     r['searchResult']['_count'])
        for item in r['searchResult']['item']:
            ok = True
            logging.debug('eBay ITEM: {}'.format(item['itemId']))
            listing = Listing()
            listing.source_type = 'C'
            listing.source_id = classified.id
            listing.source_textid = classified.textid
            try:
                for attr in item['attribute']:
                    if attr['name'] == 'Year':
                        # only take the 1st 4 chars because of an eBayism
                        # of sometimes having trailing 0s (e.g. 20140000)
                        listing.model_year = attr['value'][:4]
            except (KeyError, TypeError):
                # note: got an odd TypeError once because on one record eBay
                # returned a string rather than a hash for an attr (!). The
                # inconsistency makes no sense, but I guess it is just another
                # way for the record to be messed up & missing model_year
                listing.model_year = None
            listing.make = item['title'].split(':')[0].strip()
            listing.model = item['primaryCategory']['categoryName']
            # ^^ alternatively could often get more info from title
            try:
                listing.pic_href = item['galleryURL']
            except KeyError:
                listing.pic_href = 'N/A'
            listing.listing_href = item['viewItemURL']
            listing.local_id = item['itemId']
            listing.stock_no = item['itemId']
            listing.status = 'F' # 'F' -> For Sale
            listing.listing_text = item['title']

            # GEE TODO: this is ignoring ebay price weirdness and currency
            try:
                listing.price = regularize_price(
                    item['sellingStatus']['buyItNowPrice']['value'])
            except (KeyError, AttributeError, TypeError, ValueError):
                listing.price = regularize_price(
                    item['sellingStatus']['currentPrice']['value'])

            if 'postalCode' in item and session:
                z = session.query(Zipcode).filter_by(
                    zip=item['postalCode']).first()
                if z:
                    listing.lat = z.lat
                    listing.lon = z.lon

            # validate model_year
            try:
                int(listing.model_year)
            except (ValueError, TypeError):
                logging.warning('bad year [%s] for item %s',
                                listing.model_year, listing.local_id)
                listing.model_year = '1'

            if is_car_interesting(listing):
                listing.add_tag('interesting')
            else:
                if 'limited' in inv_settings:
                    ok = False # throw it away for limited inventory stages

            if ok:
                tagify(listing)
                list_of_listings.append(listing)
                logging.debug('pulled listing: {}'.format(listing))
            else:
                # debug not warn b/c we're throwing out lots of stuff
                logging.debug('skipped listing: {}'.format(listing))

            # END LOOP over listings on the page

        # is there another page of listings?
        # IMPORTANT NOTE: eBay page counts are *approximate*, meaning you might
        # get back page 48 of 50, then the next page will be empty and that is
        # the end of the list. Also, the "of 50" might say "of 49" on one page
        # and "of 53" on another page of the same pull
        current_page = int(r['paginationOutput']['pageNumber'])
        total_pages = int(r['paginationOutput']['totalPages'])
        logging.info('Loaded page {} of {}'.format(current_page, total_pages))
        if current_page < total_pages:
            api_request['paginationInput']['pageNumber'] = current_page + 1
            response = api.execute('findItemsAdvanced', api_request)
        else:
            break
        # END LOOP over all inventory pages

    logging.info('Loaded ' + str(len(list_of_listings)) + ' cars from ebay')

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

    return list_of_listings, inventory_marker


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
# list_of_listings: a set of listings (could be partial or entire set)
# inventory_marker: pagination/subset marker (will be None if done)
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
# GEE TODO clean up the classified (and dealer) db entries/table structures
# for now, this method goes in custom_pull_method and the anchor goes in
# the extract_car_list_func field
#
def pull_3taps_inventory(classified, inventory_marker=None, session=None):

    # implicit param from environment:
    inv_settings = os.environ.get('OGL_INV_SETTINGS', '')

    list_of_listings = []

    # for 3taps we want to keep the anchor in the classified record (which
    # ultimately means in the db) but we will also feed it through the
    # inventory_marker param as a mechanism for flow control only. Since
    # this routine only pulls records and doesn't touch the db, we will
    # update the classified record but trust the caller to update the db

    if inventory_marker:
        pass # run from the passed-in point
    else:
        # caller doesn't specify; start from the anchor in classified
        # see TODO - anchor is in temporary storage location
        inventory_marker = classified.extract_car_list_func

    logging.info('Pulling inventory from 3taps for %s starting with marker %s',
                 classified.textid, inventory_marker)

    # no dedicated python sdk, but simple enough JSON APIs to call directly
    url = ('http://polling.3taps.com/poll?'
           'auth_token=a7e282009ed50537b7f3271b753c803a'
           '&category=VAUT&retvals=id,account_id,source,'
           'category,location,external_id,external_url,'
           'heading,body,timestamp,timestamp_deleted,expires'
           ',language,price,currency,images,annotations,'
           'deleted,flagged_status,state,status,html')
    url_params = ['&source={}'.format(classified.textid.upper())]
    url_params.append('&anchor={}'.format(inventory_marker))
    if 'local' in inv_settings:
        logging.debug('limiting to local cars')
        # GEE TODO: note that the anchor will be invalidated if we switch
        # back and forth between local and not
        url_params.append('&location.state=USA-CA')
    else:
        logging.debug('NOT limiting to local cars')

    url = url + ''.join(url_params)
    logging.debug('inventory URL is: {}'.format(url))

    try:
        req = urllib.request.Request(url, headers=_HDRS)
        page = urllib.request.urlopen(req)
        bytestream = page.read()
        r = json.loads(bytestream.decode())
    except urllib.error.HTTPError as error:
        logging.error('Unable to poll 3taps at ' + url + ': HTTP ' +
                      str(error.code) + ' ' + error.reason)
        return None, None

    if page.getcode() != 200:
        logging.error('Failed to poll 3taps at ' + url +
                      ' with HTTP response code ' + str(page.getcode()))
        logging.error('Full error page:'.format(bytestream.decode()))
        return None, None

    if not r['success']:
        logging.error('3taps reports failure: {}'.format(json.dumps(r)))
        return None, None

    if len(r['postings']) == 0:
        logging.warning('3taps returned a set of zero records')
        return None, None

    logging.info('Number of car listings found: {}'.format(len(r['postings'])))
    for item in r['postings']:
        ok = True
        item = Bunch(item) # for convenience
        logging.debug('3taps ITEM: {}'.format(item.id))
        listing = Listing()
        listing.source_type = 'C'
        listing.source_id = classified.id
        listing.source_textid = classified.textid

        # there are three possible places to find year/make/model from 3taps:
        # annotations, the listing heading, or the full listing html.
        # grab the first 2, the 3rd contingently, and keep the best-looking.

        # a few notes on feed quality:
        # carsd seems to have consistent year/make/model in annotations
        # autod usually has all three but not always
        # craig sometimes has year, but usually not the other two

        an_model_year = he_model_year = ht_model_year = None
        an_make = he_make = ht_make = None
        an_model = he_model = ht_model = None

        # from the annotations:
        if 'year' in item.annotations:
            an_model_year = item.annotations['year']
        if 'make' in item.annotations:
            an_make = item.annotations['make']
        if 'model' in item.annotations:
            an_model = item.annotations['model']
        # now regularize them (if we found all three annotations)
        if an_model_year and an_make and an_model:
            (an_model_year,
             an_make,
             an_model) = regularize_year_make_model(
                 ' '.join([an_model_year, an_make, an_model]))

        # from the heading
        if 'heading' in item and item.heading: # present and non-empty
            (he_model_year,
             he_make,
             he_model) = regularize_year_make_model(item.heading)

        # now, are we OK with what we got so far?
        if an_model_year and an_model_year > '1800' and an_model_year < '2020':
            listing.model_year = an_model_year
        else:
            listing.model_year = he_model_year
        if (
                (an_make and an_make in _MAKES) or
                not he_make or he_make not in _MAKES
        ):
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

        # OK, how did we do?
        # we may not have gotten year/make/model from either of the above.
        # for craigslist we can look one more place: the full html
        # ... which contains one ore more <p class="attrgroup">
        # ... one of which which often contains a <span> with Y/M/M info.
        # GEE TODO: some of the other attrgroup spans are also interesting
        if (
                (not listing.model_year or not listing.make) and
                classified.textid == 'craig' and 'html' in item
        ):
            html = None
            try:
                html = b64decode(item.html)
            except binascii.Error:
                logging.error('Failed to decode item html for item %s',
                              item.external_id)
            if html:
                soup = BeautifulSoup(html)
                for p in soup.find_all(class_='attrgroup'):
                    for span in p.find_all('span'):
                        if not listing.model_year or not listing.make:
                            (listing.model_year,
                             listing.make,
                             listing.model) = regularize_year_make_model(span.text)
        # year/make/model we ended up with [and what we started from]
        logging.debug('Final year/make/model: %s %s %s [an: %s %s %s, h: %s]',
                      listing.model_year, listing.make, listing.model,
                      an_model_year, an_make, an_model, item.heading)

        try:
            listing.pic_href = item.images[0]['full']
        except (KeyError, IndexError):
            listing.pic_href = 'N/A'
        listing.listing_href = item.external_url
        # use the source identifier to minimize dupes
        listing.local_id = item.external_id
        # keep the 3taps ID around too (at least the latest one)
        listing.stock_no = item.id
        if not listing.local_id:
            # some feeds (e.g. autod) *occasionally* lack the local_id;
            # fall back to stock_no
            logging.warning('listing for a %s %s %s has no local ID; ' +
                            'using 3taps ID %s',
                            listing.model_year, listing.make, listing.model,
                            listing.stock_no)
            listing.local_id = listing.stock_no

        if 'location' in item:
            if 'lat' in item.location:
                listing.lat = item.location['lat']
            if 'long' in item.location: # note 3taps uses long, we use lon
                listing.lon = item.location['long']
            # add fall back to other location info if lat/long is unreliable?

        # GEE TODO: examine & use flagging info
        if item.status == 'for_sale' and item.deleted is False:
            listing.status = 'F' # 'F' -> For Sale
        else:
            listing.status = 'R' # 'R' -> Removed, unknown reason

        listing.listing_text = item.heading

        #try:
        #    listing.price = regularize_price(item.annotations['price'])
        #except ValueError:
        listing.price = regularize_price(item.price)

        # validate year/make/model (well, the first 2 are sufficient)
        if not listing.model_year and not listing.model:
            ok = False
            logging.warning('skipping item with no year/make/model info: %s',
                            listing.local_id)
        else:
            try:
                int(listing.model_year)
            except (ValueError, TypeError):
                logging.warning('bad year [%s] for item %s',
                                listing.model_year, listing.local_id)
                listing.model_year = '1'

        # be tougher on cl listings for now because there is so much junk
        if ok and is_car_interesting(listing,
                                     unknown_make_is_interesting=(
                                         classified.textid != 'craig')):
            listing.add_tag('interesting')
        else:
            if 'limited' in inv_settings:
                ok = False # throw it away for limited inventory stages

        # a few more CL junk-data tests: drop records that fail
        if ok and classified.textid == 'craig' and not listing.has_tag('interesting'):
            if not listing.model_year or listing.model_year < '1800':
                logging.warning('skipping item with no useful year: %s',
                                item)                
                ok = False
            if not listing.model or listing.model == 'None':
                logging.warning('skipping item with no useful model: %s',
                                item)
                ok = False

        # GEE TODO remove this hack around some problem in my CL logic
        if classified.textid = 'craig' and (listing.model.beginswith('Miata') or
                                            listing.model.beginswith('MX') or
                                            listing.model.beginswith('MIATA')):
            listing.add_tag('interesting')
            ok = True
            

        if ok:
            tagify(listing)
            list_of_listings.append(listing)
            logging.debug('pulled listing: {}'.format(listing))
        else:
            # debug not warn b/c we're throwing out lots of stuff
            logging.debug('skipped listing: {}'.format(listing))

        # END LOOP over listings in the feed pull

    logging.info('Loaded %s cars from 3taps for %s',
                 str(len(list_of_listings)), classified.textid)

    # update the classified record with the new 3taps anchor AND
    # send the same value back as the inventory marker.
    classified.extract_car_list_func = r['anchor']
    inventory_marker = r['anchor']

    # note: 3taps doesn't tell us when/if we are caught up -- we just won't see
    # a full set of new records. We could have a few that came in while we're
    # running but lets NOT endlessly cycle on that....
    if len(r['postings']) < 500: # arbitrary number
        inventory_marker = None # signal that we are done!

    return list_of_listings, inventory_marker


# import_from_dealer
#
# Imports inventory from a dealership, overwriting (adding/updating) as needed
#
# parameters:
# con: db connection (None if no db access is possible/requested)
# es: indexing connection (None if no indexing is possible/requested)
#
# Notes:
#
# This is basically a wrapper around pull_dealer_inventory() that handles the
# persistence details of the pulled inventory. Assumes that a dealership's
# inventory is small enough to pull & update within a single db commit
# (and then this method commits)
#
def import_from_dealer(dealer, session, es):

    # paint current records so we can mark-as-removed any that no longer exist
    mark_listings_pending_delete('D', dealer.id, session)
    session.commit()

    # get the current listings on the dealer's website inventory
    listings = pull_dealer_inventory(dealer, session=session)

    # now put the located records in the db & es index
    if listings:
        # with sqlalchemy, we get new objects back so build a list of those
        db_listings = []
        for listing in listings:
            db_listings.append(add_or_update_found_listing(session, listing))

        # commit the block of listings (which generates ids on new records)
        session.commit()
        logging.debug('committed a block of listings for %s',
                      dealer.textid)

        for listing in db_listings:
            index_listing(es, listing)

    remove_marked_listings('D', dealer.id, session, es=es)

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
def import_from_classified(classified, session, es):

    # 3taps provides polling w/ only new/updated records in the stream, so
    # we explicitly get deletes/expirations/etc. All other sites we need
    # to treat disappearance of the listing as cause for cancellation

    if classified.custom_pull_func != 'pull_3taps_inventory':
        mark_listings_pending_delete('C', classified.id, session)
        session.commit()

    inventory_marker = None
    done = False
    while not done:

        listings = []

        # get the current active inventory of website listings
        # or, in the case of 3taps, the deltas since the last polling
        # note the special-casing for some sites that have their own method

        if classified.custom_pull_func:
            f = globals()[classified.custom_pull_func]
            listings, inventory_marker = f(classified,
                                           inventory_marker=inventory_marker,
                                           session=session)
        else:
            listings, inventory_marker = pull_classified_inventory(
                classified,
                inventory_marker=inventory_marker,
                session=session)

        # now put the located records in the db & es index
        if listings:
            # with sqlalchemy, we get new objects back so build a list of those
            db_listings = []
            for listing in listings:
                db_listings.append(add_or_update_found_listing(session,
                                                               listing))

            # commit the block of listings (which generates ids on new records)
            session.commit()
            logging.debug('committed a block of listings for %s',
                          classified.textid)

            for listing in db_listings:
                index_listing(es, listing)

        # check if we're done?
        if not inventory_marker:
            done = True
        # END LOOP over blocks of inventory (while not done)

    if classified.custom_pull_func == 'pull_3taps_inventory':
        # in the 3taps case we just need to update the anchor that tells what
        # records we have pulled and thus where to start from next time;
        # the pull method will already have updated the field in classified
        logging.debug('Saving the 3taps anchor')
        # NO LONGER REQUIRED - sqlalchemy will automatically flush the update
        # when we commit
    else:
        remove_marked_listings('C', classified.id, session, es=es)

    session.commit() # aaaaaand commit!
    logging.info('Completed inventory pull for {}'.format(classified.textid))

    return True


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
    logging.debug('Painted %s existing records for %s site %s',
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
        logging.info('Removing listings that have been taken down '
                     'since the last pull')
        result = session.execute(
            "select id from listing "
            "where source_type = :source_type and source_id = :source_id "
            "and instr(ifnull(markers, ''), 'P') != 0",
            {'source_type': source_type, 'source_id': source_id})
        for row in result:
            listing_id = row[0]
            try:
                es.delete(index="carbyr-index",
                          doc_type="listing-type",
                          id=listing_id)
            except NotFoundError as err:
                logging.warning('record with id=%s not found during ' +
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
    logging.debug('Marked %s rows as no longer active on %s site #%s',
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

    logging.debug('checking on existence of listing %s',
                  current_listing.local_id)
    try:
        existing_listing = session.query(Listing).filter_by(
            local_id=current_listing.local_id,
            source_type=current_listing.source_type,
            source_id=current_listing.source_id).one()

        logging.debug('found: {}'.format(existing_listing))
        if existing_listing.markers:
            s = set(existing_listing.markers)
            if 'P' in s:
                s.remove('P')
                existing_listing.markers = ''.join(s)

        if existing_listing.status == 'X':
            # remove the pending-delete marker but make no other changes
            return existing_listing # already in session; discard new listing

        # mark the current record with the id of the existing record
        # and carry forward (merge) tags and markers, etc
        current_listing.id = existing_listing.id
        current_listing.add_tags(existing_listing.tagset)
        current_listing.add_markers(existing_listing.markers)
        current_listing.listing_date = existing_listing.listing_date
        if current_listing.status != 'F' and not existing_listing.removal_date:
            # GEE TODO: this should be server/db time, not python time: how?!
            current_listing.removal_date = datetime.datetime.now()
        # all other fields will be taken from the current listing record

    except NoResultFound:
        logging.debug('no match for local_id=%s',
                      current_listing.local_id)
        pass # current_listing will not get an id until merge & flush

    # GEE TODO: this setting of last_update should not be required, but...
    current_listing.last_update = datetime.datetime.now()
    return session.merge(current_listing) # behavior dependent upon id


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
            listing_d = dict(listing)
        else:
            # if we got some other flavor of listing then hope it is safe
            listing_d = listing
        es.index(index="carbyr-index", doc_type="listing-type",
                 id=listing_d['id'], body=listing_d)
    else:
        try:
            es.delete(index="carbyr-index", doc_type="listing-type",
                      id=listing.id)
        except NotFoundError as err:
            logging.warning('record with id=%s not found during attempted ' +
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

    logging.debug("wrote listing id {} ({} {} {}) to file {}".format(
        listing.id, listing.model_year, listing.make, listing.model, pathname))
    return True


# ============================================================================
# MAIN
# ============================================================================

def process_command_line():
    # initialize the parser object:
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
    parser.add_argument('action',
                        choices=('list', 'import'),
                        help=('action: list sources which can be imported and'
                              'exit, or import from those sources'))
    parser.add_argument('sources', nargs='*',
                        help='the source(s) to pull from if action=import')

    return parser.parse_args()


def main():
    args = process_command_line()

    # start logging
    logging.basicConfig(level=args.log_level.upper(),format='%(asctime)s %(message)s')

    # establish connections to required services (db & es)
    session = None # the SQLAlchemy session
    es = None # and the indexing connection

    try:
        # GEE TODO: recommended connection string adds &use_unicode=0 "because
        # python is faster at unicode than mysql" (per sqlalchemy docs), but
        # fuck faster if it doesn't work at all: that generates this error:
        # TypeError: conversion from bytes to Decimal is not supported
        # ... which is a dead end.
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
                    logging.error('request of import from unknown source: %s',
                                  source)
    else: # uh, shouldn't be possible?
        logging.error('oops -- action {} not recognized'.format(args.action))

    return True

if __name__ == "__main__":
    status = main()
    sys.exit(status)
