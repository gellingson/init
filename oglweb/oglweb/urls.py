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
    url(r'^admin/$', include(admin.site.urls)),
    url(r'^cars/$', views.index, name='allcars'),
    url(r'^cars/rss/$', ListingsFeed(), name='rss'),
    url(r'^cars/(?P<filter>[a-z]+)/$', views.index, name='filtered'),
    url(r'^cars/(?P<filter>[a-z]+)/rss/$', ListingsFeed(), name='filtered-rss'),
]
