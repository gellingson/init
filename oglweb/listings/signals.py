
from allauth.account.signals import user_signed_up, user_logged_in
from django.contrib import messages
from django.contrib.sessions.models import Session
from django.dispatch import receiver

# OGL modules used
from listings.models import SavedQuery
from listings.query_utils import *


# GEE TODO: this should fire even on first login after signup, right?
# but I'm not sure where in the sequence the session gets nuked & reset,
# so I'm catching both signals for safety right now.
@receiver(user_signed_up)
@receiver(user_logged_in)
def get_and_set_queries(request, user, **kwargs):
    # if there are any saved queries in the anonymous session, save them
    # note that login happens right after signin so if this is the user's
    # first login we will have just done this... no problem, except to be
    # careful about potential duplication

    session_favs = querylist_from_session(request.session, QUERYTYPE_FAVORITE)
    if session_favs:
        # note: if the user is newly-signed-up this should be empty
        db_favs = SavedQuery.objects.filter(user=user, querytype='F')
        for search in session_favs:
            # ref is pretty unique; ignore the case where a user somehow
            # created a new (different) saved query with the same ref as
            # one of their existing saved queries while not logged in...
            exists = False
            for dbquery in db_favs:
                if dbquery.ref == search.ref:
                    exists = True  # so we don't need to add it
            if not exists:
                # newly created in the anonymous session, add it
                sq = search.to_saved_query(user)
                sq.id = None
                sq.user = user
                sq.save()

    # re-query the combined list fresh from the db & repop the session
    db_favs = SavedQuery.objects.filter(user=user, querytype='F')
    favs = [Query().from_saved_query(sq) for sq in db_favs]
    querylist_to_session(request.session, QUERYTYPE_FAVORITE, favs)
    return


@receiver(user_signed_up)
def get_names(request, user, sociallogin=None, **kwargs):
    if sociallogin:
        # Extract first / last names from social nets and store on User record
        if sociallogin.account.provider == 'twitter':
            name = sociallogin.account.extra_data['name']
            user.first_name = name.split()[0]
            user.last_name = name.split()[1]
 
        if sociallogin.account.provider == 'facebook':
            user.first_name = sociallogin.account.extra_data['first_name']
            user.last_name = sociallogin.account.extra_data['last_name']
            #verified = sociallogin.account.extra_data['verified']
 
        if sociallogin.account.provider == 'google':
            user.first_name = sociallogin.account.extra_data['given_name']
            user.last_name = sociallogin.account.extra_data['family_name']
            #verified = sociallogin.account.extra_data['verified_email']
            picture_url = sociallogin.account.extra_data['picture']
 
    user.save()
    return


@receiver(user_signed_up)
def queue_welcome_message(request, user, sociallogin=None, **kwargs):
    messages.add_message(request, messages.INFO, 'postSignupModal', extra_tags='hidden modal_launcher')
    return


# note that this will be called right after signup... will queue a second
# modal request in that circumstance, which will be ignored (hopefully)
@receiver(user_logged_in)
def queue_welcome_back_message(request, user, sociallogin=None, **kwargs):
    messages.add_message(request, messages.INFO, 'postLoginModal', extra_tags='hidden modal_launcher')
    return
