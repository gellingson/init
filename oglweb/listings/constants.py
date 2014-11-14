
# GLOBALS

# TEMPLATE NAMES

HOMEPAGE = 'listings/homepage.html'
ABOUTPAGE = 'listings/about.html'
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

