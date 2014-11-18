# favlist_utils.py
#
# utility methods for handling a user's favorite-car list

# builtin modules used

# third party modules used
from bunch import Bunch
from django.db import IntegrityError

# OGL modules used
from listings.models import SavedListing, Listing


# unsave_car() ** UNUSED
#
# removes a car from the user's list of saved listings
# (both in the db and the cached data in the session)
#
# returns:
# True if car was removed
# False if there was an issue of any type
#
def unsave_car(session, listing_id):
    # GEE TODO: this just works on the session; redo for db
    sl_cache = [value for value in session.get('savedcars', []) if value != listing_id]
    session['savedcars'] = sl_cache
    return True


# save_car() ** UNUSED
#
# saves a car to the user's list of saved listings
# (both in the db and the cached data in the session)
#
# True if saved
# False if there was an issue
# None if the car was already saved
#
def save_car(session, listing_id=0, listing=None):
    # GEE TODO: this just works on the session; redo for db
    if not listing:
        if not listing_id:
            return False  # heh, need a target
        try:
            listing = Listing.objects.get(pk=listing_id)
        except (DoesNotExist, MultipleObjectsReturned) as e:
            print("attempted to find listing id " +
                  "{} failed with error {}".format(listing_id, e))
            return False

    # now we definitely have a listing, so get the cached list & insert
    sl_cache = session.get('savedcars', [])
    if listing.id in sl_cache:
        return None
    sl_cache.append(listing.id)
    session['savedcars'] = sl_cache
    return True


# unsave_car_from_db()
#
# removes a car from the user's list of saved listings
#
# returns:
# True if car was removed
# False if there was an issue of any type
#
def unsave_car_from_db(user, listing_id):
    l = Listing()
    l.id = listing_id
    records = list(SavedListing.objects.filter(listing=l, user=user))
    if len(records) == 1:
        sl_to_delete = records[0]
        sl_to_delete.delete()
    else:
        print('OOPS!retrieved {} records to delete'.format(len(records)))
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
    l = Listing()
    l.id = listing_id
    fav = SavedListing()
    fav.listing = l
    fav.user = user
    fav.status = 'A'
    try:
        fav.save()
    except IntegrityError:  # already a favorite....
        return None
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
