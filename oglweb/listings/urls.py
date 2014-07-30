from django.conf.urls import url

from listings import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^$', views.index, name='search'),
    ]
