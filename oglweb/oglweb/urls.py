from django.conf.urls import include, url
from django.contrib import admin

from listings import views
#from polls import views

urlpatterns = [
    # Examples:
    # url(r'^$', 'oglweb.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')), 
    url(r'^cars/', include('listings.urls', namespace='listings')), # GEE app listings @ URL cars/
#    url(r'^polls/', include('polls.urls', namespace='polls')),
    url(r'^admin/', include(admin.site.urls)),
]
