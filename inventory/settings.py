#!/usr/bin/env python3
#
# settings.py
#
# this contains settings, constants, and globals for inventory managment
#
# NOTES:
# load_refdata_cache() loads up a bunch of these globals... call it!

# builtin modules used
from bunch import Bunch
import logging
import sys
import traceback

# third party modules used

# OGL modules used
from orm.models import ConceptTag, ConceptImplies
from orm.models import NonCanonicalMake, NonCanonicalModel


### logging

LOG = logging.getLogger('importer')  # will configure further in main()

# extra logging settings (beyond even the DEBUG log setting); to be used
# only in one-off situations because these are very resource-intensive
XL = Bunch({
    'dblog': False,
    'dump': False
})
    
# log_unhandled_exception()
#
# attached to sys.excepthook, logs unhandled exceptions to LOG not stderr
#
def log_unhandled_exception(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    LOG.error("Uncaught exception {}: {}".format(exc_type, exc_value))
    if exc_tb:
        LOG.error("Traceback:")
        LOG.error(''.join(traceback.format_tb(exc_tb)))

sys.excepthook = log_unhandled_exception


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
    'VIPER',
    'NSX', 'MR2', 'MR-2', 'SUPRA', 'LFA', '300ZX', 'SKYLINE', 'GTR', 'LEAF',
    'MX5', 'MX-5', 'MIATA', 'MX-5 MIATA', 'RX7',
    'EVOLUTION', 'EVO', 'I-MIEV', 'I',
    'CORVETTE', 'VOLT', 'GRAND NATIONAL', 'ELR', 'CTS-V',
    'BOSS', 'SHELBY', 'GT', 'MUSTANG', 'C-MAX',
    '1M', 'Z3M', 'M3', 'M5', 'M6', 'I3', 'I8',
    '330', '330CI', '330I', '335', '335D', '335I', 'SLS',
    'E-GOLF', 'E-UP', 'XL1', 'R8',
    '500', '500E',
]

_INTERESTING_WORDS = [
    'ENERGI', 'ELECTRIC', 'AMG', 'PHEV', 'CLARITY', 'EV',
    'STI', 'WRX', 'GTI', 'R32', 'SI', 'GLH', 'GLHS'
    'SWAP', 'SWAPPED', 'MODS', 'MODDED', 'JDM', 'DRAG', 'RACE', 'RACECAR',
    'AUTOCROSS', 'SCCA', 'CRAPCAN', 'LEMONS',
    'CUSTOM', 'RESTORED', 'PROJECT',
    'LS1', 'LS2', 'LS7',
    'TURBO', 'TURBOCHARGED', 'SUPERCHARGED', 'SUPERCHARGER',
    'V10', 'V12', 'ROTARY', '12A', '13B', '20B',
]

# GEE TODO: specific submodels that can only be recognized by multiple words,
# e.g. Focus ST/RS, Integra Type R.

# global hashes (caches) of refdata objects from the db, populated at startup
_MAKES = {}
_MODELS = {}
_TAGS = {}
_TAG_RELS = {}


# load_refdata_cache()
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

