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
import datetime
import inspect
import pytz
import time

# third party modules used
import iso8601
from bunch import Bunch

# OGL modules used
from listings.constants import *
from listings.models import SavedQuery

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
        self.descr = qd.descr
        self.query = qd.query
        self.type = qd.get('type', QUERYTYPE_NONE)
        self.mark_date = qd.get('mark_date', None)    
        return self

    # this method is for use during the switchover period only;
    # it takes a hash in the old/original format we used to store
    # in the session and makes a Query object from it....
    def from_old_storage_dict(self, querydict, type=None):
        qd = Bunch(querydict)
        self.id = None
        self.ref = qd.id
        self.descr = qd.desc
        self.query = qd.query
        self.type = qd.get('querytype', QUERYTYPE_NONE)
        self.mark_date = None
        return self

    def from_saved_query(self, sq):
        self.id = sq.id
        self.ref = sq.ref
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
            sq.mark_date = iso8601.parse(self.mark_date)
        else:
            sq.mark_date = None
        sq.user = user
        return sq

    def __str__(self):
        return "{}/{}/{}/{}".format(self.id, self.ref, self.descr, self.query)


SUGGESTED_SEARCH_LIST = {
    '_sotw_vette':
    {
        'ref': '_sotw_vette',
        'descr': 'C2 Corvettes',
        'type': 'S',
        'query': {'query': {'filtered': {'query': {'query_string': {'default_operator': 'AND', 'query': 'model_year:[1963 TO 1967] make: chevrolet model:corvette'}}}}}
    },
    '_sotw_tesla':
    {
        'ref': '_sotw_tesla',
        'descr': 'Tesla Roadsters',
        'type': 'S',
        'query': {'query': {'filtered': {'query': {'query_string': {'default_operator': 'AND', 'query': 'tesla roadster'}}}}}
    },
    '_sotw_nb':
    {
        'ref': '_sotw_nb',
        'descr': '99-05 MX-5 Miatas',
        'type': 'S',
        'query': {'query': {'filtered': {'query': {'query_string': {'query': 'nb', 'default_operator': 'AND'}}}}, 'sort': [{'_geo_distance': {'unit': 'mi', 'order': 'asc', 'location': {'lon': -121.8818207, 'lat': 37.3415451}}}]}
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
                querylist.append(Query().from_old_storage_dict(query), type=query_type)
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
def save_query(ref, descr, session, user):
    recents = querylist_from_session(session, QUERYTYPE_RECENT)
    from_search = None
    # ref'd query is normally recents[0] but let's be flexible in case
    if recents and ref.startswith(QUERYTYPE_RECENT):
        for search in recents:
            if search.ref == ref:
                from_search = search
                break
    if from_search:
        from_search.id = None  # force new/distinct object
        from_search.type = QUERYTYPE_FAVORITE
        from_search.ref = QUERYTYPE_FAVORITE + from_search.ref[1:]
        from_search.descr = descr
        # keep other fields (e.g. query)

        if user and user.is_authenticated():
            # store in db
            sq = from_search.to_saved_query(user=user)
            sq.create()
            from_search.id = sq.id # put id back into session obj
        # now also store it in the session list
        favorites = querylist_from_session(session, QUERYTYPE_FAVORITE)
        favorites.append(from_search)
        querylist_to_session(session, QUERYTYPE_FAVORITE, favorites)
        return from_search.ref  # so we can show it now...

    # else fail silently
    return None


# unsave_query()
#
# removes the referenced query from the user's favorites list
#
# updates both cached query list and db
#
def unsave_query(ref, session, user):
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
    return None


# mark_as_read()
#
# sets the mark_date on a saved (favorite) query
#
def mark_as_read(session, ref, mark_date_dt=None, mark_date_str=None):
    if not mark_date_str:
        if not mark_date_dt:
            return False
        mark_date_str = mark_date_dt.isoformat()

    favorites = querylist_from_session(session, QUERYTYPE_FAVORITE)
    if favorites:
        i = 0
        while i < len(favorites):
            if favorites[i].id == id:
                favorites[i].mark_date = mark_date_str
                sq = favorites[i].to_saved_query(user=session.user)
                sq.save()
                querylist_to_session(session, QUERYTYPE_FAVORITE, favorites)
                break
            i += 1
    return True


# update_recents()
#
# given a session and a new query, put the latter into the former
#
# current_query should be a Query object, not SavedQuery or Bunch or whatnot
#
def update_recents(session, current_query):
    if current_query.type == QUERYTYPE_DEFAULT:  # ie just recent cars
        return
    recents = querylist_from_session(session, QUERYTYPE_RECENT)
    if recents and recents[0].descr == current_query.descr: # GEE TODO: match any recent in the list
        # same query as last one, or nearly so...
        # keep ref & replace to update any minor change
        current_query.ref = recents[0].ref
        recents[0] = current_query
    else:
        # generate new query ref and insert into recents
        current_query.ref = QUERYTYPE_RECENT + str(datetime.date.today()) + '_' + str(int(round(time.time() * 1000)))
        current_query.querytype = QUERYTYPE_RECENT
        recents.insert(0, current_query)

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
    if query_ref.startswith('_'):
        return Query().from_dict(SUGGESTED_SEARCH_LIST[query_ref])
    # otherwise, look in the session
    querylist = []
    querylist = querylist_from_session(session, query_ref[0])
    for query in querylist:
        if query.ref == query_ref:
            return query
    return None  # oops - not found
