from django.conf.urls import include, url
from django.contrib import admin

from listings import views as views
from listings.feeds import ListingsFeed
#from oglweb import views as oglviews

# NOTE: was using include(listings.site.urls) but that borked calls to
# reverse() so I promoted all the listings urls directly into this file

urlpatterns = [
    # Examples:
    # url(r'^$', 'oglweb.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    # url(r'^$', oglviews.fubar, name='homepage'),
    #url(r'^cars/search/$', views.index, name='search'),
    url(r'^$', views.homepage, name='homepage'),
    url(r'^about$', views.about, name='about'),
    # GEE TODO: /about and /cars/about -> the same place; clean that up
    url(r'^cars/about$', views.about, name='about'),
    url(r'^(?P<base_url>cars/)(?P<filter>[a-zA-Z]+)/about$', views.about, name='filter-about'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^(?P<base_url>cars/)$', views.index, name='allcars'),
    url(r'^(?P<base_url>test/)$', views.test, name='test'),
    url(r'^(?P<base_url>test/)s/(?P<search_id>[a-zA-Z0-9\-_]+)/$', views.test, name='test-existing'),
    url(r'^oldtest/$', views.oldtest, name='oldtest'),
    url(r'^carsadmin/$', views.listingadmin, name='allcarsadmin'),
    url(r'^carsadmin/adminflag/(?P<id>[0-9]+)$', views.adminflag, name='adminflag'),
    url(r'^cars/rss/$', ListingsFeed(), name='rss'),
    url(r'^cars/(?P<filter>[a-z]+)/$', views.index, name='filtered'),
    url(r'^cars/(?P<filter>[a-z]+)/rss/$', ListingsFeed(), name='filtered-rss'),
]
