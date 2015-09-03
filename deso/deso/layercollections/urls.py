from django.conf.urls import patterns, url
from django.contrib import admin
from .views import get_collection, get_collection_map, get_available_collections, get_available_maplayers

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^collection/(?P<collection_id>\d+)/map/$', get_collection_map),
    url(r'^collection/(?P<collection_id>\d+)/$', get_collection),
    url(r'^maplayers/$', get_available_maplayers),
    url(r'^$', get_available_collections),
)
