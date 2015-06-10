
# GLOBALS

# Actions (that a user might take, and we might log...)
ACTION_FLAG = 'X'
ACTION_FAV = 'F'
ACTION_UNFAV = 'U'
ACTION_VIEW = 'V'
ACTION_CLICKTHROUGH = 'C'
ACTION_SEARCH = 'S'

# Reasons that a user might flag a listing
FLAG_REASON_UNINTERESTING = 'U'
FLAG_REASON_NONCAR = 'N'
FLAG_REASON_INCORRECT = 'I'
FLAG_REASON_FRAUD = 'F'
FLAG_REASON_SOLD = 'S'
FLAG_REASON_OTHER = 'O'
FLAG_REASON_UNSPECIFIED = 'X'

# TEMPLATE NAMES

HOMEPAGE = 'listings/homepage.html'
ABOUTPAGE = 'listings/about.html'
LANDINGPAGE = 'listings/landing.html'
LISTINGSBASE = 'listings/listingsbase.html'
LISTINGSADMIN = 'listings/listingsadmin.html'
LISTINGSTEST = 'listings/listingstest.html'
LISTINGSAPI = 'listings/listingsapi.html'

# GEE TODO -- should probably move these to the db
# for now, to add a filter (sub-site) add it here & in db section below
VALID_FILTERS = {'miatas': { "term": { "model": "miata"}},
                 'corvettes': { "term": { "model": "corvette"}},
                 'classics': { "range": { "model_year": { "to": "1975"}}}
}

