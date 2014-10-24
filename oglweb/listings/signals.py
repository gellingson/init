
from allauth.account.signals import user_signed_up, user_logged_in
from django.contrib.sessions.models import Session
from django.dispatch import receiver
from listings.models import SavedQuery

@receiver(user_logged_in)
def get_and_set_queries(request, user, **kwargs):

    # if there are any saved queries in the anonymous session, save them
    # note that login happens right after signin so if this is the user's
    # first login we will have just done this... no problem, except to be
    # careful about potential duplication
    
    favorites = request.session.get('favorites', [])
    if favorites:
        db_qs = SavedQuery.objects.filter(user=request.user, querytype='F')
        for search in favorites:
            # ref is pretty unique; ignore the case where a user somehow
            # created a new (different) saved query with the same ref as
            # one of their existing saved queries while not logged in...
            exists = False
            for query in db_qs:
                if query.ref == search['id']:
                    exists = True  # so we don't need to add it
            if not exists:
                # newly created in the anonymous session, add it
                sq = SavedQuery()
                sq.user = request.user
                sq.querytype = 'F'
                sq.ref = search['id']
                sq.descr = search['desc']
                sq.query = search['query']
                sq.save()

    # now populate the session with all the user's saved queries
    db_favorites = SavedQuery.objects.filter(user=user, querytype='F')
    favorites = []
    for fav in db_favorites:
        favdict = {
            'id': fav.ref,
            'desc': fav.descr,
            'query': fav.query
        }
        favorites.append(favdict)
    request.session['favorites'] = favorites
    return


@receiver(user_signed_up)
def get_names_and_queries(request, user, sociallogin=None, **kwargs):
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

    # promote any saved queries from the anonymous session to user storage
    favorites = request.session.get('favorites', [])
    if favorites:
        for search in favorites:
            sq = SavedQuery()
            sq.user = user
            sq.querytype = 'F'
            sq.ref = search['id']
            sq.descr = search['desc']
            sq.query = search['query']
            sq.save()
    
    return
