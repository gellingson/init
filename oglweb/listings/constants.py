
# GLOBALS

# TEMPLATE NAMES

LISTINGSBASE = 'listings/listingsbase.html'
LISTINGSADMIN = 'listings/listingsadmin.html'
LISTINGSTEST = 'listings/listingstest.html'
ABOUTBASE = 'listings/about.html'

# GEE TODO -- should probably move these to the db
# for now, to add a filter (sub-site) add it here & in db section below
VALID_FILTERS = {'miatas': { "term": { "model": "miata"}},
                 'corvettes': { "term": { "model": "corvette"}},
                 'classics': { "range": { "model_year": { "to": "1975"}}}
}

SUGGESTED_SEARCH_LIST = {
    '_sotw_nb': {
        'id': '_sotw_nb',
        'desc': '99-05 miatas',
        'query': {'query': {'filtered': {'query': {'query_string': {'query': 'nb', 'default_operator': 'AND'}}}}, 'sort': [{'_geo_distance': {'unit': 'mi', 'order': 'asc', 'location': {'lon': -121.8818207, 'lat': 37.3415451}}}]}
    }
}
