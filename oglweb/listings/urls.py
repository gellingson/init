from django.conf.urls import url

from listings import views
from listings.feeds import ListingsFeed

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^search/$', views.index, name='search'), # currently unused
    url(r'^rss/$', ListingsFeed(), name='rss'),
    ]
