"""
List the loaded RasterAggregatedLayer objects.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from ...models import RasterAggregatedLayer

WGS84_SRID = settings.WGS84_SRID

class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        for layer in RasterAggregatedLayer.objects.order_by("id"):
            center = layer.get_center()
            x = None
            y = None
            if center:
                p = center.transform(WGS84_SRID, clone=True)
                x = round(p.x, 5)
                y = round(p.y, 5)
            self.stdout.write("[{}] {} ({}, {}): {}".format(layer.id,
                                                 str(layer),
                                                 x,
                                                 y,
                                                 layer.get_layer_url()))

