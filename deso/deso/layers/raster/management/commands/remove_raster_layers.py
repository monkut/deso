"""
Remove RasterAggregatedLayer and Related objects given RasterAggregatedLayer ids.
Note: Use the 'list_raster_layers' command to obtain the RasterAggregatedLayer ids.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from ...models import RasterAggregatedLayer

WGS84_SRID = settings.WGS84_SRID

class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("-i", "--ids",
                            type=int,
                            default=None,
                            required=True,
                            nargs="+",
                            help="RasterAggregatedLayer ids to delete.")

    def handle(self, *args, **options):
        for layer in RasterAggregatedLayer.objects.order_by("id"):
            self.stdout.write("Removing RasterAggregatedLayer: [{}] {}...".format(layer.id, layer.name))
            # Delete related DataModel Objects
            layer.pixels().delete()

            # delete Layer
            layer.delete()

            self.stdout.write("Done!")


