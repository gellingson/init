from django.conf.urls import url

from listings import views
from listings.feeds import ListingsFeed

# this is UNUSED since reverse() doesn't seem to follow includes
# so I have put all the urls in the oglweb urls.py file

urlpatterns = [
    url(r'^$', views.index, name='allcars'),
    url(r'^search/$', views.index, name='search'), # currently unused
    url(r'^rss/$', ListingsFeed(), name='rss'),
    url(r'^(?P<filter>[a-z]+)/$', views.index, name='filtered'),
    url(r'^(?P<filter>[a-z]+)/rss/$', ListingsFeed(), name='filtered-rss'),
    ]
