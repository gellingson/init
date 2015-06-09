from django.conf.urls import include, url
from django.contrib import admin

from listings import views as views
from listings.feeds import ListingsFeed, QueryFeed

#from oglweb import views as oglviews

# NOTE: was using include(listings.site.urls) but that borked calls to
# reverse() so I promoted all the listings urls directly into this file

urlpatterns = [
    # Examples:
    # url(r'^$', 'oglweb.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    # url(r'^$', oglviews.fubar, name='homepage'),
    url(r'^land/(?P<ref>[a-z0-9]+)/$', views.landing, name='landing'),
    url(r'^$', views.homepage, name='homepage'),
    url(r'^about/$', views.about, name='about'),
    url(r'^accounts/profile/$', views.profile, name='profile'),
    url(r'^ajax/flagcar$', views.flag_car_api),
    url(r'^ajax/savecar$', views.save_car_api),
    url(r'^ajax/unsavecar$', views.unsave_car_api),
    url(r'^ajax/addnote$', views.add_note_api),
    url(r'^ajax/viewcar$', views.view_car_api),
    url(r'^dashboard/$', views.dashboard, name='dashboard'),
    url(r'^blank/$', views.blank, name='blank'),
    url(r'^statictest/$', views.statictest, name='statictest'),
    url(r'^accounts/', include('allauth.urls')),
    # GEE TODO: /about and /cars/about -> the same place; clean that up
    url(r'^cars/about/$', views.about, name='about'),
    url(r'^carsapi/(?P<offset>[0-9]+)/(?P<number>[0-9]+)$', views.cars_api, name='cars_api'),
    url(r'^(?P<base_url>cars/)(?P<filter>[a-zA-Z]+)/about$', views.about, name='filter-about'),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^(?P<base_url>blank/)$', views.blank, name='blank'),
    url(r'^(?P<base_url>cars/)$', views.cars, name='allcars'),
    url(r'^(?P<base_url>test/)$', views.cars_test, name='test'),
    url(r'^(?P<base_url>test/)s/(?P<query_ref>[a-zA-Z0-9\-_]+)/$', views.cars_test, name='test-existing'),
    url(r'^oldtest/$', views.oldtest, name='oldtest'),
    url(r'^carsadmin/$', views.listingadmin, name='allcarsadmin'),
    url(r'^carsadmin/adminflag/(?P<id>[0-9]+)$', views.adminflag, name='adminflag'),
    url(r'^cars/rss/$', ListingsFeed(), name='rss'),
    url(r'^cars/(?P<filter>[a-z]+)/$', views.cars, name='filtered'),
    url(r'^cars/(?P<filter>[a-z]+)/rss/$', ListingsFeed(), name='filtered-rss'),
    url(r'^cars/(?P<user_id>[0-9]+)/(?P<query_id>[0-9]+)/rss/$', QueryFeed(), name='query-rss'),
    url(r'^viewcar/$', views.view_car),
    url(r'^goto/$', views.redirect_to_original_listing),
]
