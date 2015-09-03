import json

from django.http import HttpResponse, HttpResponseBadRequest
from django.contrib.gis.geos import Polygon
from django.conf import settings

from .models import GeoJsonLayer


WGS84_SRID = settings.WGS84_SRID
METERS_SRID = settings.METERS_SRID

def get_vector_layers(request):
    available_layers =[]
    for layer in GeoJsonLayer.objects.all():
        available_layers.append(layer.info())
    return HttpResponse(json.dumps(available_layers), content_type='application/json; charset=utf-8')


def get_objects(request, layer_id=None):
    """
    Return the objects within the given bbox (bounding box) in the format:

    [
     {
        "id": <unique layer id>,
        "type": "Point",
        "coordinates": [ 139.66305555555556, 35.706666666666663 ],
        "properties": [
                        {
                          'site_id': self.site_id,
                          'unique_id': self.unique_id,
                          'lon': wgs84_location.x,
                          'lat': wgs84_location.y,
                          'number': self.number,
                          'azimuth': self.azimuth,
                          'beam_width': self.beam_width,
                          'down_tilt': self.down_tilt,
                          'band': self.band,
                          'antenna_height': self.antenna_height,
                          'antenna_pattern': self.antenna_pattern
                          },
                          ...
                        ]
     },
     ...
    ]
    """
    bbox_raw = request.GET.get("bbox", None)
    if bbox_raw and bbox_raw.count(",") == 3:
        bbox = [float(v) for v in bbox_raw.split(",")]
    else:
        geojson_layer = GeoJsonLayer.objects.get(pk=1)
        example_poly = geojson_layer.bounds_polygon
        example_poly.transform(WGS84_SRID)
        max_lon, max_lat = max(example_poly.coords[0])
        min_lon, min_lat = min(example_poly.coords[0])
        msg = "Improperly formed or not given 'bbox' querystring option, should be in the format '?bbox={},{},{},{}'".format(min_lon,
                                                                                                                             min_lat,
                                                                                                                             max_lon,
                                                                                                                             max_lat)

        return HttpResponseBadRequest(msg)

    bbox_poly = Polygon.from_bbox(bbox)
    bbox_poly.srid = WGS84_SRID
    bbox_poly.transform(METERS_SRID)

    try:
        layer = GeoJsonLayer.objects.get(id=layer_id,
                                         bounds_polygon__intersects=bbox_poly)
        return HttpResponse(layer.data, content_type='application/json')
    except GeoJsonLayer.DoesNotExist as e:
        # layer may exist, but query does not intersect.
        return HttpResponse(json.dumps([]), content_type='application/json; charset=utf-8')

