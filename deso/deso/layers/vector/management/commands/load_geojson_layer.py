"""
Load GEOJSON text file to vector.GeoJsonLayer model
"""
from django.core.management.base import BaseCommand, CommandError

from ...models import GeoJsonLayer


WGS84_SRID = 4326

def load_geojson_layer(geojson_filepath, opacity):
    with open(geojson_filepath, "rt", encoding="utf8") as in_f:
        geojson_text = in_f.read()
    geojson_layer = GeoJsonLayer(name=geojson_filepath,
                                 data=geojson_text,
                                 opacity=opacity)
    bounds_polygon = geojson_layer.get_data_bounds_polygon()
    geojson_layer.bounds_polygon = bounds_polygon
    geojson_layer.clean()
    geojson_layer.save()
    geojson_layer.create_map_layer()


    return geojson_layer

class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("-f", "--filepath",
                            default=None,
                            required=True,
                            help="Filepath to GEOJSON text file to load to vector.GeoJsonLayer object.")
        parser.add_argument("-o", "--opacity",
                            default=0.75,
                            type=float,
                            help="Layer Suggested Opacity ( 0 to 1) [DEFAULT=0.75]")

    def handle(self, *args, **options):
        if not (0 < options["opacity"] <= 1.0):
            raise CommandError("Invalid '--opacity' not (0<{}<=1.0)".format(options["opacity"]))

        filepath = options["filepath"]
        self.stdout.write("Loading ({})...".format(filepath))
        load_geojson_layer(filepath, options["opacity"])
        self.stdout.write("Done!")
