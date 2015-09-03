from django.conf.urls import patterns, include, url
from django.views.generic import RedirectView
from django.contrib import admin

admin.autodiscover()

admin.site.site_header = "Deso (Data Layer) Administration"

urlpatterns = patterns('',
    url(r'^vector/', include('deso.layers.vector.urls')),
    url(r'^raster/', include('deso.layers.raster.urls')),
    url(r'^collections/', include('deso.layercollections.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^$', RedirectView.as_view(url="/static/index.html")),
)
