"""
Make requests for tiles at given zoom levels to fill the tilecache.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from ...models import RasterAggregatedLayer

WGS84_SRID = settings.WGS84_SRID

def request_layer_tiles(layer_url, layer, zoom):
    """
    Request tiles for given layer
    :param layer_url: Abosulute URL with layer_id (for example: http://HOST:PORT/pathtolayer/{layer_id}/)
    :param layer: RasterAggregatedLayer object
    :param zoom: Zoom level
    :return: tile count
    """
    count = 0
    pass

class Command(BaseCommand):
    help = __doc__


    def add_arguments(self, parser):
        parser.add_argument("-l", "--layers",
                            type=int,
                            nargs="+",
                            required=True,
                            default=None,
                            help="RasterAggregatedLayer Id(s) of layers to cache")
        parser.add_argument("-z", "--zooms",
                            type=int,
                            nargs="+",
                            default=[14,],
                            help="Zoom Level(s) to cache [DEFAULT=14]")
        DEFAULT_RASTER_LAYERS_URL = "http://{}:{}/raster/layer/{{layer_id}}/".format(settings.HOST,
                                                                             settings.PORT)
        parser.add_argument("-u", "--url",
                            default=DEFAULT_RASTER_LAYERS_URL,
                            help="Raster Layers URL to send requests to [DEFAULT='{}']".format(DEFAULT_RASTER_LAYERS_URL))

    def handle(self, *args, **options):
        layer_ids = sorted(options["layers"])
        for layer_id in layer_ids:
            try:
                layer = RasterAggregatedLayer.objects.get(id=layer_id)
            except RasterAggregatedLayer.DoesNotExist:
                self.stderr.write("Given RasterAggregatedLayer({}) Does Not Exist -- SKIPPING!".format(layer_id))
            center = layer.get_center()



