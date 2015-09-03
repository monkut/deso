import logging

from django.utils.translation import ugettext as _
from django.conf import settings
from django.contrib.gis.db import models
from django.contrib.auth.models import User

WGS84_SRID = settings.WGS84_SRID
METERS_SRID = settings.METERS_SRID

# Get an instance of a logger
logger = logging.getLogger(__name__)


class MapLayerCollection(models.Model):
    created_by = models.ForeignKey(User, null=True, editable=False)
    created_datetime = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)

    def __str__(self):
        return "MapLayerCollection({}-{})".format(self.name, self.id)

    def get_absolute_url(self):
        return "/collections/{}/".format(self.id)

VALID_LAYER_TYPES = (
    ("TileLayer-base", "Base TMS Tiles (RasterLayer)"),  # Uses TMS url request scheme
    ("TileLayer-overlay", "Overlay TMS Tiles (RasterLayer)"),  # Uses TMS url request scheme
    ("GeoJSON", "GEOJSON (VectorLayer|SitesLayer)"),  # Uses "?bbox=<minx>,<miny>,<maxx>,<maxy>" request scheme
)


class MapLayer(models.Model):
    created_by = models.ForeignKey(User, null=True, editable=False)
    created_datetime = models.DateTimeField(auto_now_add=True)
    collections = models.ManyToManyField(MapLayerCollection,
                                         blank=True)
    name = models.CharField(max_length=255)
    attribution = models.CharField(max_length=255)
    max_zoom = models.PositiveSmallIntegerField(default=18)
    min_zoom = models.PositiveSmallIntegerField(default=8)
    opacity = models.FloatField(default=1.0, help_text="Suggested Layer Opacity")
    center = models.PointField(default=None,
                               null=True,
                               blank=True,
                               srid=METERS_SRID,
                               help_text="Location of MapLayer center")
    description = models.TextField(blank=True)
    type = models.CharField(max_length=25, choices=VALID_LAYER_TYPES)
    # note this could be a layer within this django project,
    # or one defined elsewhere.
    url = models.URLField(help_text=_("Layer URL from which layer is served. (For TileLayers this should be in the form: 'http://HOST:PORT/{z}/{x}/{y}.png')"))
    legend_url = models.URLField(null=True,
                                 blank=True,
                                 help_text="(Optional) URL to legend html")

    def info(self):
        layer_definition = {
            "collections": [i.id for i in self.collections.all()],
            "name": self.name,
            "type": self.type,
            "layerUrl": self.url,
            "minZoom": self.min_zoom,
            "maxZoom": self.max_zoom,
            "attribution": self.attribution,
            "opacity": self.opacity,
        }
        if self.legend_url:
            layer_definition["legendUrl"] = self.legend_url

        if self.center:
            wgs84_point = self.center.transform(WGS84_SRID, clone=True)
            layer_definition["centerlon"] = round(wgs84_point.x, 6)
            layer_definition["centerlat"] = round(wgs84_point.y, 6)

        return layer_definition

    def __str__(self):
        return "MapLayer({}-{})".format(self.name, self.id)

