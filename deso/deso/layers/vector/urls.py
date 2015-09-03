from django.conf.urls import patterns, url
from django.contrib import admin

from .views import get_objects, get_vector_layers


admin.autodiscover()

urlpatterns = patterns('',
    url(r'^layers/$', get_vector_layers),
    url(r'^layer/(?P<layer_id>\d+)/$', get_objects),
)
