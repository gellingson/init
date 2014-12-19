# query_utils.py
#
# utilities for handling saved queries
#
# NOTES:
#
# there are three lists of saved queries: favorites, recents, and suggested:
# - recents live only in the session
# - favorites live in the session for unauthenticated users, then are stored
#   in the db for authenticated users (with the session holding a cache)
# - suggested queries are defined and accessed from constants.py for now
#
# early code used different formats for session & db storage, including the
# fieldname of 'id' in the session corresponding to 'ref' in the db. This has
# been cleared up as of Nov 2014. Now all of these types of saved queries use
# the same model object (even though not all are stored in the db). Some of
# the model fields are unused for some types of queries (e.g. only favorites
# can have a mark_date set).
#
# note that there is some ugliness about JSON serializing and unserializing
# these objects, notably due to datetime objects in favorites. The code below
# and in models.py handles this as best we can.

# builtin modules used
import copy
import datetime
import inspect
import logging
import pytz
import time

# third party modules used
import iso8601
from bunch import Bunch

# OGL modules used
from listings.constants import *
from listings.models import SavedQuery
from listings.utils import *

LOG = logging.getLogger(__name__)

QUERYTYPE_NONE = None
QUERYTYPE_DEFAULT = 'D'
QUERYTYPE_FAVORITE = 'F'
QUERYTYPE_RECENT = 'R'
QUERYTYPE_SUGGESTED = '_'

# Query class
#
# Used to store queries in the session; can be easily converted to/from a
# SavedQuery, which is used to store queries in the db.
#
# This Query class is expressly designed to be JSON-storable (no datetime,
# decimal, complex objects, etc).
#
class Query(object):
    # if passed, mark_date is expected to be a datetime object
    def __init__(self):
        self.id = None
        self.ref = None
        self.orig_ref = None
        self.descr = None
        self.query = None
        self.type = QUERYTYPE_NONE
        self.mark_date = None

    def to_dict(self):
        qd = Bunch()
        for name in dir(self):
            value = getattr(self, name)
            if not name.startswith('__') and not name == 'user' and not inspect.ismethod(value):
                qd[name] = value
        return qd

    def from_dict(self, querydict, type=None):
        qd = Bunch(querydict)
        self.id = qd.get('id', None)
        self.ref = qd.ref
        self.orig_ref = qd.get('orig_ref', None)
        self.descr = qd.descr
        self.query = qd.query
        self.type = qd.get('type', qd.ref[0])
        self.mark_date = qd.get('mark_date', None)
        return self

    # this method is for use during the switchover period only;
    # it takes a hash in the old/original format we used to store
    # in the session and makes a Query object from it....
    def from_old_storage_dict(self, querydict, type=None):
        qd = Bunch(querydict)
        self.id = None
        self.ref = qd.id
        self.orig_ref = None
        self.descr = qd.desc
        self.query = qd.query
        self.type = qd.get('querytype', qd.id[0])
        self.mark_date = None
        return self

    def from_saved_query(self, sq):
        self.id = sq.id
        self.ref = sq.ref
        self.orig_ref = None
        self.descr = sq.descr
        self.query = sq.query
        self.type = sq.querytype
        if sq.mark_date:
            self.mark_date = sq.mark_date.isoformat()
        else:
            self.mark_date = None
        # don't try to store user; will recombine with session as needed
        return self

    def to_saved_query(self, user=None):
        sq = SavedQuery()
        sq.id = self.id
        sq.ref = self.ref
        sq.descr = self.descr
        sq.query = self.query
        sq.querytype = self.type
        if self.mark_date:
            sq.mark_date = iso8601.parse_date(self.mark_date)
        else:
            sq.mark_date = None
        sq.user = user
        return sq

    def __str__(self):
        return str(self.to_dict())
        return "{}/{}/{}/{}".format(self.id, self.ref, self.descr, self.query)


FIRST_SUGGESTED_SEARCH_LIST = {
    '_sotw_vette':
    {
        'ref': '_sotw_vette',
        'descr': 'C2 Corvettes',
        'type': QUERYTYPE_SUGGESTED,
        'query': {'query': {'filtered': {'query': {'query_string': {'default_operator': 'AND', 'query': 'model_year:[1963 TO 1967] make: chevrolet model:corvette'}}}}}
    },
    '_sotw_tesla':
    {
        'ref': '_sotw_tesla',
        'descr': 'Tesla Roadsters',
        'type': QUERYTYPE_SUGGESTED,
        'query': {'query': {'filtered': {'query': {'query_string': {'default_operator': 'AND', 'query': 'tesla roadster'}}}}}
    },
    '_sotw_nb':
    {
        'ref': '_sotw_nb',
        'descr': '99-05 MX-5 Miatas',
        'type': QUERYTYPE_SUGGESTED,
        'query': {'query': {'filtered': {'query': {'query_string': {'query': 'nb', 'default_operator': 'AND'}}}}, 'sort': [{'_geo_distance': {'unit': 'mi', 'order': 'asc', 'location': {'lon': -121.8818207, 'lat': 37.3415451}}}]}
    }
}
SUGGESTED_SEARCH_LIST = {
    '_sotw_c5z06':
    {
        'ref': '_sotw_c5z06',
        'descr': 'C5 Z06s',
        'type': QUERYTYPE_SUGGESTED,
        'query': {'query': {'filtered': {'query': {'query_string': {'default_operator': 'AND', 'query': 'C5 Z06 make:chevrolet model:corvette'}}}}}
    },
    '_sotw_morgan':
    {
        'ref': '_sotw_morgan',
        'descr': 'Morgans',
        'type': QUERYTYPE_SUGGESTED,
        'query': {'query': {'filtered': {'query': {'query_string': {'default_operator': 'AND', 'query': 'make:morgan'}}}}}
    },
    '_sotw_308':
    {
        'ref': '_sotw_308',
        'descr': 'Ferrari 308s',
        'type': QUERYTYPE_SUGGESTED,
        'query': {'query': {'filtered': {'query': {'query_string': {'default_operator': 'AND', 'query': '308 make:ferrari'}}}}}
    }
}

# querylist_from_session()
#
# pulls named list of json-ed saved queries from the session &
# returns them reinstantiated as SavedQuery objects
#
# this is only required because of the limits of JSON serialization
# and the desire to avoid using pickling for session serialization
#
def querylist_from_session(session, query_type):
    querylist = []
    dictlist = session.get(query_type + 'QL', [])
    if dictlist:
        for querydict in dictlist:
            q = Query().from_dict(querydict)
            querylist.append(q)
    if not querylist:
        # check the old storage (different name, different format)
        if query_type == QUERYTYPE_RECENT:
            old_ql = session.get('recents', [])
        elif query_type == QUERYTYPE_FAVORITE:
            old_ql = session.get('favorites', [])
        else:
            old_ql = []
        for query in old_ql:
            try:
                querylist.append(Query().from_old_storage_dict(query, type=query_type))
            except AttributeError:
                pass  # must have been some oddity in the old query list -- ignore
    return querylist
    #return [ SavedQuery().from_jsonable(query) for query in session.get(querytype, []) ]


# querylist_to_session()
#
# takes list of SavedQuery objects and puts them in the session
#
# this is only required because of the limits of JSON serialization
# and the desire to avoid using pickling for session serialization
#
def querylist_to_session(session, query_type, querylist):
    #jsonable_querylist = [ query.to_jsonable() for query in querylist ]
    dictlist = []
    for query in querylist:
        dictlist.append(query.to_dict())
    session[query_type + 'QL'] = dictlist


# save_query()
#
# saves the referenced query as a favorite
#
# writes to cached favorites list in the session as well as the db;
# normal usage is to save the current (most recent) query but can
# save any query that is somewhere in the recents array
#
# also updates the recents list, marking the now-favorite query as a fav
#
def save_query(ref, descr, session, user):
    LOG.info('user {} saving the query {}:{}'.format(user, ref, descr))
    recents = querylist_from_session(session, QUERYTYPE_RECENT)
    from_search = None
    # ref'd query is normally recents[0] but let's be flexible in case
    if recents and ref.startswith(QUERYTYPE_RECENT):
        for search in recents:
            if search.ref == ref:
                from_search = search
                break
    if from_search:
        fav_search = copy.copy(from_search)
        fav_search.id = None  # force new/distinct object
        fav_search.type = QUERYTYPE_FAVORITE
        fav_search.ref = QUERYTYPE_FAVORITE + fav_search.ref[1:]
        fav_search.descr = descr
        # keep other fields (e.g. query)

        if user and user.is_authenticated():
            # store in db
            sq = fav_search.to_saved_query(user=user)
            sq.save()
            fav_search.id = sq.id # put id back into session obj
        # now also store it in the session list
        favorites = querylist_from_session(session, QUERYTYPE_FAVORITE)
        favorites.append(fav_search)
        querylist_to_session(session, QUERYTYPE_FAVORITE, favorites)

        # and now update all matching entries in the recents list
        for search in recents:
            if search.ref == ref:
                search.orig_ref = search.ref
                search.ref = fav_search.ref
                search.type = QUERYTYPE_FAVORITE
                search.descr = fav_search.descr
        querylist_to_session(session, QUERYTYPE_RECENT, recents)

        return fav_search.ref  # so we can show it now...

    # else fail silently
    return None


# unsave_query()
#
# removes the referenced query from the user's favorites list
#
# updates both cached query list and db
# also downgrades any matching queries in the recents list
#
def unsave_query(ref, session, user):
    LOG.info('user {} unsaving the query {}'.format(user, ref))
    f = None
    favorites = querylist_from_session(session, QUERYTYPE_FAVORITE)
    if favorites:
        i = 0
        while i < len(favorites):
            if favorites[i].ref == ref:
                f = favorites.pop(i)
                if user and user.is_authenticated():
                    sq = f.to_saved_query(user=user)
                    sq.delete()
                querylist_to_session(session, QUERYTYPE_FAVORITE, favorites)
                break
            i += 1
    if f:  # downgrade any refs to the no-longer-fav in the recents list
        recents = querylist_from_session(session, QUERYTYPE_RECENT)
        for search in recents:
            if search.ref == ref:
                if search.orig_ref:
                    search.ref = search.orig_ref
                else:
                    search.ref = QUERYTYPE_RECENT + str(datetime.date.today()) + '_' + str(int(round(time.time() * 1000)))
                search.type = QUERYTYPE_RECENT
                search.orig_ref = None
        querylist_to_session(session, QUERYTYPE_RECENT, recents)
    return None


# mark_as_read()
#
# sets the mark_date on a saved (favorite) query
#
def mark_as_read(ref, session, user, mark_date):
    LOG.info('user {} marking query {} as read'.format(user, ref))
    mark_date = force_date(mark_date)
    mark_date_str = mark_date.isoformat()
    q = get_query_by_ref(session, ref)
    if q:
        q.mark_date = mark_date_str
        return put_query_by_ref(session, user, q)
    return False

# update_recents()
#
# given a session and a new query, put the latter into the former
#
# current_query should be a Query object, not SavedQuery or Bunch or whatnot
#
def update_recents(session, current_query):
    if current_query.type == QUERYTYPE_DEFAULT:  # ie just recent cars
        return
    new_query = copy.copy(current_query)
    recents = querylist_from_session(session, QUERYTYPE_RECENT)
    if recents and recents[0].ref == new_query.ref:
        # same query; do nothing
        pass
    elif (recents and recents[0].descr == new_query.descr and
          recents[0].type == QUERYTYPE_RECENT and new_query.type == QUERYTYPE_RECENT):
        # ad-hoc query that looks the same query as last one, or nearly enough;
        # keep ref & replace to update any minor change (e.g. a query clause)
        new_query.ref = recents[0].ref
        new_query.orig_ref = recents[0].orig_ref
        recents[0] = new_query
    else:  # new enough to be counted as a new recents entry
        # generate new query ref if needed, and a new orig_query_ref if the
        # new query isn't just a recent query (e.g. a favorite); then
        # insert into recents
        if new_query.type == QUERYTYPE_FAVORITE or new_query.type == QUERYTYPE_SUGGESTED:
            # orig_ref will be used if this query ceases to be a favorite (or whatever)
            # later on and becomes a "plain" recent query
            new_query.orig_ref = QUERYTYPE_RECENT + str(datetime.date.today()) + '_' + str(int(round(time.time() * 1000)))
            if not new_query.ref:  # shouldn't happen, but just in case
                new_query.ref = new_query.orig_ref
        else:  # recent (or missing type info)
            new_query.ref = QUERYTYPE_RECENT + str(datetime.date.today()) + '_' + str(int(round(time.time() * 1000)))
            new_query.type = QUERYTYPE_RECENT
        recents.insert(0, new_query)

    # if the current query was just being formed & didn't have ref/type,
    # then modify the current query with that new info
    if not current_query.ref:
        current_query.ref = new_query.ref
    if not current_query.type:
        current_query.ref = new_query.type

    # limit recents query list size
    while len(recents) > 10:
        recents.pop()

    querylist_to_session(session, QUERYTYPE_RECENT, recents)
    return


# get_query_by_ref()
#
# retrieve the referenced query from the suggestion list or session
#
def get_query_by_ref(session, query_ref):
    if query_ref.startswith(QUERYTYPE_SUGGESTED):
        return Query().from_dict(SUGGESTED_SEARCH_LIST[query_ref])
    # otherwise, look in the session
    querylist = []
    querylist = querylist_from_session(session, query_ref[0])
    for query in querylist:
        if query.ref == query_ref:
            return query
    return None  # oops - not found


# put_query_by_ref()
#
# updates (overwrites) query by ref/orig_ref
#
# puts the given query into the appropriate saved query list(s), overwriting
# any existing query with the same ref/orig_ref
# writes to both recents and saved query lists if this query is in both (ie
# has suitable ref and orig_ref)
#
# returns True iff we were able to update
#
def put_query_by_ref(session, user, query):
    if query.type == QUERYTYPE_DEFAULT or query.type == QUERYTYPE_NONE:
        return False

    if query.type == QUERYTYPE_FAVORITE:
        # search for at most 1 match in the favorite list
        flist = querylist_from_session(session, QUERYTYPE_FAVORITE)
        i = 0
        match = -1
        while i < len(flist):
            if flist[i].ref == query.ref:
                match = i
                break
            i += 1
        if match > -1:
            flist[match] = copy.copy(query)
        else:
            flist.append(copy.copy(query))
        if user and user.is_authenticated():
            sq = query.to_saved_query(user=user)
            sq.save()
        querylist_to_session(session, QUERYTYPE_FAVORITE, flist)

    # now update copies in recents, regardless of query type
    rlist = querylist_from_session(session, QUERYTYPE_RECENT)
    i = 0
    match = -1
    while i < len(rlist):
        if rlist[i].ref == query.ref:
            match = i
            break
        i += 1
    if match > -1:
        rlist[i] = copy.copy(query)
    else:
        recents.insert(0, copy.copy(query))
    querylist_to_session(session, QUERYTYPE_RECENT, rlist)
    return True


# set_show_cars_option()
#
# sets the 'show' option to the specified value
#
# NOTES:    
# by default when viewing a favorite that has a mark date we should show
# only new listings since that mark_date, *but* the user can override
# to show all listings regardless of date; if they so set, the pref
# should be retained until the user switches to another query or switches
# the pref explicitly. If the user switches to another query and then
# comes back to the favorite query, the new-only behavior should reset.
# to accomplish this we can store a "show" param in the session which
# will default to "new_only", and will only change when the user explicitly
# changes it
#
def set_show_cars_option(session, action, query_ref):
    if query_ref:
        session['show'] = action
        session['show_for_query_ref'] = query_ref
    else:  # uh, invalid; reset to default
        session['show'] = 'new_only'
        session['show_for_query_ref'] = None


# get_show_cars_option()
#
# returns the option IF STILL VALID; else resets & returns the default
#
def get_show_cars_option(session, query):
    if query.ref == session.get('show_for_query_ref', None):
        # has been set for this query; return the value
        return session.get('show', 'new_only')
    else:
        # mismatch; reset to, and return, default value
        session['show'] = 'new_only'
        session['show_for_query_ref'] = query.ref
        return 'new_only'
