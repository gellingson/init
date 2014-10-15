
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

SUGGESTED_SEARCH_LIST = {
    '_sotw_vette': {
        'id': '_sotw_vette',
        'desc': 'C2 Corvettes',
        'query': {'query': {'filtered': {'query': {'query_string': {'default_operator': 'AND', 'query': 'model_year:[1963 TO 1967] make: chevrolet model:corvette'}}}}}
    },
    '_sotw_tesla': {
        'id': '_sotw_tesla',
        'desc': 'Tesla Roadsters',
        'query': {'query': {'filtered': {'query': {'query_string': {'default_operator': 'AND', 'query': 'tesla roadster'}}}}}
    },
    '_sotw_nb': {
        'id': '_sotw_nb',
        'desc': '99-05 MX-5 Miatas',
        'query': {'query': {'filtered': {'query': {'query_string': {'query': 'nb', 'default_operator': 'AND'}}}}, 'sort': [{'_geo_distance': {'unit': 'mi', 'order': 'asc', 'location': {'lon': -121.8818207, 'lat': 37.3415451}}}]}
    }
}
