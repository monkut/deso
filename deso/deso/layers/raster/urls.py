from django.conf.urls import patterns, url
from django.views.decorators.cache import cache_page
from .views import RasterLayersTileView, get_legend, get_layers

FIVE_DAYS = (60 * 60 * 24 * 5)  # seconds * minutes * hours * days
urlpatterns = patterns('',
    url(r'^layers/$', get_layers),
    url(r'^layer/', cache_page(FIVE_DAYS, cache="tilecache")(RasterLayersTileView.as_view())),
    url(r'^legend/(?P<legend_id>\d+)/$', get_legend),  # for display on leaflet map
)
