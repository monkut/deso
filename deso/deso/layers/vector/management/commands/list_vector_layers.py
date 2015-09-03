"""
List the loaded site layers
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from ...models import GeoJsonLayer

WGS84_SRID = settings.WGS84_SRID

class Command(BaseCommand):
    help = __doc__

    def handle(self, *args, **options):
        for layer in GeoJsonLayer.objects.order_by("id"):
            center = layer.get_center()
            p = center.transform(WGS84_SRID, clone=True)
            self.stdout.write("[{}] {} ({}, {}): {}".format(layer.id,
                                                 str(layer),
                                                 round(p.x, 5),
                                                 round(p.y, 5),
                                                 layer.get_layer_url()))

