# tagging.py
#
# manages concept tags on a listing
#
# should be it's own expert system yada yada
# ...but for now is a man behind a curtain hackfest implementation
#

# OGL modules used
from inventory.settings import LOG, XL, _HDRS
from inventory.settings import _BORING_MAKES, _INTERESTING_MODELS, _INTERESTING_WORDS
from inventory.settings import _MAKES, _MODELS, _TAGS, _TAG_RELS, load_refdata_cache
import inventory.utils as u
from orm.models import Listing
from orm.models import ConceptTag, ConceptImplies
from orm.models import NonCanonicalMake, NonCanonicalModel, Zipcode

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
def tagify(listing, strict=False, counts=None):
    new_tags = []
    remove_tags = []  # not sure if we want to do this...
    make = None

    if u.is_car_interesting(listing, strict):
        new_tags.append('interesting')

    # GEE TODO: maybe we should be doing some of this tagging in the
    # relevant regularize() methods?
    if (listing.make and listing.make.upper() in _MAKES):
        make = _MAKES[listing.make.upper()]
        new_tags.append('known_make')
        remove_tags.append('unknown_make')
    else:
        new_tags.append('unknown_make')
        remove_tags.append('known_make')

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

            LOG.debug('found model: %s', model.canonical_name)
            new_tags.append('known_model')
            remove_tags.append('unknown_model')
            if model.canonical_name == 'Miata':
                if listing.model_year <= '1994':
                    new_tags.append('NA6')
                    new_tags.append('NA')
                elif listing.model_year <= '1997':
                    new_tags.append('NA8')
                    new_tags.append('NA')
                elif listing.model_year <= '2005':
                    new_tags.append('NB')
                elif listing.model_year <= '2015':
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
            if listing.make == 'Nissan' and model.canonical_name == 'Leaf':
                new_tags.append('electric')
            if listing.make == 'Chevrolet' and model.canonical_name == 'Volt':
                new_tags.append('electric')
        else:
            new_tags.append('unknown_model')
        if listing.make == 'Subaru' and 'WRX' in listing.model.upper():
            new_tags.append('rally')
        if listing.make == 'Mitsubishi' and 'EVO' in listing.model.upper():
            new_tags.append('rally')
        if listing.make == 'Mazda' and '323 GTX' in listing.model.upper():
            new_tags.append('rally')
        if listing.make == 'Audi' and '323 GTX' in listing.model.upper():
            new_tags.append('rally')
        if listing.make == 'Ford' and 'ESCORT' in listing.model.upper() and 'MK' in listing.model.upper():
            new_tags.append('rally')
        if  'RALLY' in listing.model.upper():
            new_tags.append('rally')
        if  'WRC' in listing.model.upper():
            new_tags.append('rally')
        
        if listing.make == 'Tesla':
            new_tags.append('electric')
        if listing.make == 'Fisker':
            new_tags.append('electric')
        if listing.make == 'BMW' and listing.model[0].upper() == 'I':
            new_tags.append('electric')
        if listing.make == 'Volkswagen' and listing.model.upper().startswith('E-'):
            new_tags.append('electric')
        if listing.make == 'Volkswagen' and listing.model.upper().startswith('XL1'):
            new_tags.append('electric')
        if listing.make == 'Ford' and 'ENERGI' in listing.model.upper():
            new_tags.append('electric')
        if listing.make == 'Mitsubishi' and 'MIEV' in listing.model.upper():
            new_tags.append('electric')
        if listing.make == 'Chevrolet' and listing.model.upper().startswith('SPARK EV'):
            new_tags.append('electric')
        if listing.make == 'Fiat' and listing.model.split(' ')[0].upper() == '500E':
            new_tags.append('electric')
        if 'ELECTRIC' in listing.model.upper():
            new_tags.append('electric')

        # GEE TODO: method not yet implemented; also, resolve handling of
        # text and ConceptTag objects!
        #implied_tag_set = set()
        #for tag in new_tags:
        #    implied_tag_set.add(_TAGS[tag].implied_tags())
        #new_tags.append(implied_tag_set)

    # tag trailers/RVs
    if listing.source_textid == 'craig':
        if '/rvs/' in listing.listing_href:
            new_tags.append('rv')
        if '/rvd/' in listing.listing_href:
            new_tags.append('rv')
    if new_tags:
        LOG.debug('adding tags: %s for %s %s %s',
                  new_tags, listing.model_year,
                  listing.make, listing.model)
    else:
        LOG.debug('no new tags')

    listing.add_tags(new_tags)

    # GEE TODO: if I'm really going to use this mechanism (much) then
    # I should make a remove_tags() method
    #
    # IMPORTANT NOTE: if the listing already exists, the tagset from any
    # update record will be UNIONED with existing tagset, meaning that
    # an updated record has no mechanism for removing tags already on the
    # db listing. Until that changes, this is of very limited utility....
    for tag in remove_tags:
        listing.remove_tag(tag)

    if counts:
        # store tag counts for import reporting
        for tag in listing.tags.split(' '):
            counts[tag] += 1
