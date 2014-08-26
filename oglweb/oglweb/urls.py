from django.conf.urls import include, url
from django.contrib import admin

from listings import views
from oglweb import views as oglviews

urlpatterns = [
    # Examples:
    # url(r'^$', 'oglweb.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),
    # url(r'^$', oglviews.fubar, name='homepage'),
    url(r'^$', views.homepage, name='homepage'),
    url(r'^cars/', include('listings.urls', namespace='listings')), # GEE app listings @ URL cars/
    url(r'^admin/', include(admin.site.urls)),
]
