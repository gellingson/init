# favlist_utils.py
#
# utility methods for handling a user's favorite-car list

# builtin modules used
import logging

# third party modules used
from bunch import Bunch
from django.db import IntegrityError

# OGL modules used
from listings.actions import log_and_adj_quality
from listings.constants import *
from listings.models import SavedListing, Listing

LOG = logging.getLogger(__name__)

# unsave_car_from_db()
#
# removes a car from the user's list of saved listings
#
# returns:
# True if car was removed
# False if there was an issue of any type
#
def unsave_car_from_db(user, listing_id):
    LOG.info('User {} unsaving car {}'.format(user, listing_id))
    l = Listing()
    l.id = listing_id
    records = list(SavedListing.objects.filter(listing=l, user=user))
    if len(records) == 1:
        sl_to_delete = records[0]
        sl_to_delete.delete()
        log_and_adj_quality(user, ACTION_UNFAV, listing_id=listing_id)
    else:
        LOG.error('OOPS!retrieved {} records to delete'.format(len(records)))
        return False
    return True


# save_car_to_db()
#
# saves a car to the user's list of saved listings
#
# True if saved
# False if there was an issue
# None if the car was already saved
#
def save_car_to_db(user, listing_id):
    LOG.info('User {} saving car {}'.format(user, listing_id))
    l = Listing()
    l.id = listing_id
    fav = SavedListing()
    fav.listing = l
    fav.user = user
    fav.status = 'A'
    try:
        fav.save()
        log_and_adj_quality(user, ACTION_FAV, listing_id=listing_id)
    except IntegrityError:  # already a favorite....
        return None
    return True


# add_note()
#
# adds a note to a SavedListing record
#
# note: cleaning/escaping input is the caller's responsibility
#
def add_note(note, user_id, listing_id):
    sl = SavedListing.objects.get(user=user_id,
                                  listing_id=listing_id)
    sl.note = note
    sl.save()
    return True


# favdict_for_user()
#
# returns a dict of the user's favorite listings
#
# keys are ids
# values are SavedListing model records
#
def favdict_for_user(user):
    fav_dict = {}
    if user:
        favs = SavedListing.objects.filter(user=user)
        for fav in favs:
            fav_dict[fav.listing_id] = fav
    return fav_dict
