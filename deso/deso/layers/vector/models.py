import os
import json
import logging

#from django.utils.translation import ugettext as _
from django.core.exceptions import ValidationError
from django.contrib.gis.db import models
from django.contrib.gis.geos import GEOSGeometry, Polygon, MultiPolygon, Point
from django.contrib.auth.models import User
from django.apps import apps
from django.conf import settings


WGS84_SRID = settings.WGS84_SRID
METERS_SRID = settings.SPHERICAL_MERCATOR_SRID

# Get an instance of a logger
logger = logging.getLogger(__name__)


class GeoJsonLayer(models.Model):
    name = models.CharField(max_length=255)
    srid = models.PositiveIntegerField(default=WGS84_SRID)
    created_by = models.ForeignKey(User, null=True, editable=False)
    created_datetime = models.DateTimeField(auto_now_add=True,
                                            help_text="Datetime of when the data was loaded from file")
    opacity = models.FloatField(default=0.75, help_text="Suggested Layer Opacity")
    center = models.PointField(null=True, srid=METERS_SRID)
    description = models.TextField(blank=True)
    bounds_polygon = models.PolygonField(
                                         editable=False,
                                         srid=METERS_SRID)
    data = models.TextField(help_text="GeoJSON Text")

    objects = models.GeoManager()

    def clean(self):
        # try to load as json, if fails raise ValidationError
        try:
            loaded_geojson = json.loads(self.data)
            unique_ids = set()
            if "features" in loaded_geojson:
                # check features for 'id' attribute
                for f in loaded_geojson["features"]:
                    if "id" not in f["properties"]:
                        raise ValidationError("Features do not contain an 'id' attribute!  (use 'geojson_increment_id.py' tool to add/increment feature ids)")
                    else:
                        id_value = f["properties"]["id"]
                        if id_value in unique_ids:
                            raise ValidationError("Features do not contain a UNIQUE 'id' properties attribute!  (use 'geojson_increment_id.py' tool to add/increment feature ids)")
                        else:
                            unique_ids.add(id_value)

        except ValueError as e:
            raise ValidationError("INVALID GeoJSON: {}".format(str(e.args)))

    def get_data_bounds_polygon(self):
        parsed_geojson = json.loads(self.data)
        def get_polygons(obj):
            polys = []
            if "type" in obj:
                if obj["type"] == "FeatureCollection":
                    for feature in obj["features"]:
                        extent_polys = get_polygons(feature)
                        polys.extend(extent_polys)
                elif obj["type"] == "Feature":
                    # process "geometry"
                    geom = GEOSGeometry(json.dumps(obj["geometry"]))
                    # get extent_poly of geom
                    extent_poly = Polygon.from_bbox(geom.extent)
                    polys.append(extent_poly)

                elif obj["type"] in ("Polygon", "LineString", "Point"):
                    # process "geometry"
                    geom = GEOSGeometry(json.dumps(obj))
                    # get extent_poly of geom
                    extent_poly = Polygon.from_bbox(geom.extent)
                    polys.append(extent_poly)
            return polys

        geojson_extent_polygons = []
        if isinstance(parsed_geojson, list):
            for obj in parsed_geojson:
                polygons = get_polygons(obj)
                geojson_extent_polygons.extend(polygons)
        elif "type" in parsed_geojson and parsed_geojson["type"] in ("FeatureCollection", "Feature", "Polygon", "LineString", "Point"):
            polygons = get_polygons(parsed_geojson)
            geojson_extent_polygons.extend(polygons)


        # process polygons into polyons extent
        mploy = MultiPolygon(geojson_extent_polygons)
        mploy.srid = WGS84_SRID  # Expected...
        mploy.transform(METERS_SRID)
        poly = Polygon.from_bbox(mploy.extent)
        poly.srid  = METERS_SRID
        return poly

    def get_center(self):
        if not self.center:
            self.center = self.bounds_polygon.centroid
            self.save()
        return self.center

    def extent(self, as_wgs84=True):
        result = self.bounds_polygon.extent
        if as_wgs84:
            min_p = Point(*result[:2], srid=settings.METERS_SRID).transform(settings.WGS84_SRID, clone=True)
            max_p = Point(*result[2:], srid=settings.METERS_SRID).transform(settings.WGS84_SRID, clone=True)
            result = (min_p.x, min_p.y, max_p.x, max_p.y)
        return result

    def info(self):
        """
        layer information dictionary to be converted to json
        """
        layer_center_point = self.bounds_polygon.centroid
        if layer_center_point:
            layer_center_point.transform(WGS84_SRID)

        layer_unique_id = "{}:vector:{}".format(self._state.db,
                                                self.id)
        layer_info = {
                 "name": self.name,
                 "created_datetime": self.created_datetime.isoformat(),
                 "id": layer_unique_id,
                 "url": self.get_absolute_url(),
                 "type": "GeoJSON",
                 "extent": self.extent(),
                 "opacity": self.opacity,
                 }
        if layer_center_point:
            layer_info["centerlon"] = round(layer_center_point.x, 6)
            layer_info["centerlat"] = round(layer_center_point.y, 6)
        return layer_info

    def get_absolute_url(self):
        return "/vector/layer/{}/".format(self.id)

    def get_layer_url(self):
        return "http://{}:{}/vector/layer/{}/".format(settings.HOST,
                                                       settings.PORT,
                                                       self.id)

    def save(self, *args, **kwargs):
        if not self.bounds_polygon:
            poly = self.get_data_bounds_polygon()
            self.bounds_polygon = poly
        super(GeoJsonLayer, self).save(*args, **kwargs) # Call the "real" save() method.

    def create_map_layer(self):
        """
        Create a layercollections.model.MapLayer for leaflet map display.
        :return: saved layercollections.model.MapLayer object
        """
        app_label = "layercollections"
        MapLayer = apps.get_model(app_label, "MapLayer")
        m = MapLayer(name=str(self),
                     attribution="Nokia",
                     type="GeoJSON",
                     opacity=self.opacity,
                     center=self.get_data_bounds_polygon().centroid,
                     url=self.get_layer_url())
        m.save()
        return m

    def __str__(self):
        name = self.name
        if "/" in name or os.sep in name:
            name = os.path.split(name)[-1]
        return "GeoJsonLayer({}-{})".format(name, self.id)


# NOT USED yet...
class PreparedGeometry(models.Model):
    layer = models.ForeignKey(GeoJsonLayer)
    multipolygon = models.MultiPolygonField()

    objects = models.GeoManager()

    @property
    def geojson(self):
        pass

