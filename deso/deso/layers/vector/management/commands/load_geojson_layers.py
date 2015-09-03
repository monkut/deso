"""
Load GEOJSON text files from a given directory to individua vector.GeoJsonLayer models
"""
import os

from django.core.management.base import BaseCommand, CommandError

from ...models import GeoJsonLayer


WGS84_SRID = 4326

def load_geojson_layer(geojson_filepath):
    with open(geojson_filepath, "rt", encoding="utf8") as in_f:
        geojson_text = in_f.read()
    geojson_layer = GeoJsonLayer(name=geojson_filepath,
                                 data=geojson_text)
    bounds_polygon = geojson_layer.get_data_bounds_polygon()
    geojson_layer.bounds_polygon = bounds_polygon
    geojson_layer.clean()
    geojson_layer.save()
    geojson_layer.create_map_layer()
    return geojson_layer

class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("-d", "--directory",
                            default=None,
                            required=True,
                            help="Direcotry containing GEOJSON text files to load to individual vector.GeoJsonLayer object.")

    def handle(self, *args, **options):
        directory = options["directory"]
        found_geojson_filepaths = []
        for f in os.listdir(directory):
            if f.endswith(".geojson"):
                filepath = os.path.join(directory, f)
                found_geojson_filepaths.append(filepath)
        if not found_geojson_filepaths:
            raise CommandError("No '.geojson' files found in given directory: {}".format(directory))

        for filepath in found_geojson_filepaths:
            self.stdout.write("Loading ({})...".format(filepath))
            load_geojson_layer(filepath)
            self.stdout.write("Done!")
