"""
Load GEOJSON text file to vector.GeoJsonLayer model
"""
import datetime

from django.apps import apps
from django.core.management.base import BaseCommand

from ...models import MapLayerCollection, MapLayer

app_name = "deso.layers.vector"
app_label = "vector"
assert apps.is_installed(app_name)
GeoJsonLayer = apps.get_model(app_label, "GeoJsonLayer")

WGS84_SRID = 4326

def create_collection(geojson_layer, base_maplayer_id=None, host=None, port=8086):
    if base_maplayer_id is not None:
        base_maplayer = MapLayer.objects.get(id=base_maplayer_id)
    else:
        # get the first entry
        base_maplayer = MapLayer.objects.filter(type="TileLayer-base")[0]

    # see if datetime is in geojson_layer.name
    collection_name = geojson_layer.name
    if all(t in geojson_layer.name for t in ("voronoi", "RRC")):
        datetime_portion = geojson_layer.name.split("voronoi.")[-1]
        datetime_portion = datetime_portion.split(".RRC")[0]
        d = datetime.datetime.strptime(datetime_portion, "%Y%m%d_%H%M")
        collection_name = d.strftime("%Y-%m-%d %H:%M")
    new_collection = MapLayerCollection(name=collection_name)
    new_collection.save()

    full_url = "http://{}:{}{}".format(host, port, geojson_layer.get_absolute_url())
    geojson_maplayer = MapLayer(collection=new_collection,
                                name=geojson_layer.name,
                                attribution="Nokia",
                                type="GeoJSON",
                                url=full_url)
    geojson_maplayer.save()
    new_base_maplayer = MapLayer(collection=new_collection,
                                name=base_maplayer.name,
                                attribution=base_maplayer.attribution,
                                type="TileLayer-base",
                                url=base_maplayer.url)
    new_base_maplayer.save()
    return new_collection

    # create geojson MapLayer object
class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("-p", "--prefix",
                            default=None,
                            help="GeoJsonLayer Prefix Filter")
        parser.add_argument("-b", "--baselayer-id",
                            dest="baselayer_id",
                            default=None,
                            help="Baselayer ID to use in collection [DEFAULT=None]")
        parser.add_argument("--host",
                            default=None,
                            required=True,
                            help="IP or HOST for target collection URL.[DEFAULT=None]")
        parser.add_argument("--port",
                            default=8086,
                            help="host PORT for target collection URL.[DEFAULT=8086]")
    def handle(self, *args, **options):
        prefix_filter = options["prefix"]
        baselayer_id = options["baselayer_id"]

        if prefix_filter:
            geojson_layers = GeoJsonLayer.objects.filter(name__startswith=prefix_filter).order_by("name")
        else:
            geojson_layers = GeoJsonLayer.objects.order_by("name")
        for geojson_layer in geojson_layers:
            collection = create_collection(geojson_layer,
                                           baselayer_id,
                                           options["host"],
                                           options["port"])

            self.stdout.write("Created New Collection({}) for: {}".format(collection.id, geojson_layer.name))

