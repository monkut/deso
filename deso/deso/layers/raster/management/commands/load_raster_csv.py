"""
Load a CSV raster file to RasterAggregatedLayer object and related NumericRasterAggregateData.
NOTE: Input CSV expected to be AGGREGATED.
"""
import os
import csv
import gzip
import datetime
from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import Point
from django.utils import timezone
from ...models import RasterAggregatedLayer, NumericRasterAggregateData

WGS84_SRID = 4326
SPHERICAL_MERCATOR_SRID = 3857 # google maps projection

COMMIT_COUNT = 50000


def load_raster_csv(filepath, layer_name, csv_encoding, pixel_size, csv_srid, indexes, lon_idx, lat_idx, datetime_idx, datetime_format_str, opacity, no_datetime=False, no_headers=False, aggregation_method="mean"):
    open_func = open
    if filepath.lower().endswith(".gz"):
        open_func = gzip.open

    with open_func(filepath, "rt", encoding=csv_encoding) as in_f:
        reader = csv.reader(in_f)
        headers = None
        if not no_headers:
            headers = next(reader)  # remove headers

        # prepare KPI raster layers
        index_layers = {}
        for data_idx in indexes:
            if not headers:
                kpi_name = "Unknown (no-headers)"
            else:
                kpi_name = headers[data_idx]
            if not layer_name:
                layer_name = "{} ({})".format(os.path.split(filepath)[-1], kpi_name)
            layer = RasterAggregatedLayer(name=layer_name,
                                          filepath=filepath,
                                          data_model="NumericRasterAggregateData",
                                          opacity=opacity,
                                          aggregation_method=aggregation_method,
                                          pixel_size_meters=pixel_size,
                                          minimum_samples=1,  # sample number is not known for pre-aggregated items.
                                          )
            layer.save()
            index_layers[data_idx] = layer

        count = 0
        pixels = []
        expected_indexes = [lon_idx, lat_idx, datetime_idx]
        for row in reader:
            if row and all(row[idx] for idx in expected_indexes):
                if no_datetime:
                    datetime_value = timezone.now()
                else:
                    naive_datetime_value = datetime.datetime.strptime(row[datetime_idx], datetime_format_str)
                    current_timezone = timezone.get_default_timezone()
                    datetime_value = timezone.make_aware(naive_datetime_value, current_timezone)
                lon = float(row[lon_idx])
                lat = float(row[lat_idx])
                p = Point(lon, lat, srid=csv_srid)
                for value_idx in indexes:
                    if row[value_idx]:
                        # currently only supporting numeric values!
                        value = float(row[value_idx])
                        data = NumericRasterAggregateData(layer=index_layers[value_idx],
                                                          location=p,
                                                          dt = datetime_value,
                                                          mean=value,
                                                          samples=1)
                        pixels.append(data)
            if len(pixels) >= COMMIT_COUNT:
                NumericRasterAggregateData.objects.bulk_create(pixels)
                count += len(pixels)
                pixels = []
        if pixels:
            NumericRasterAggregateData.objects.bulk_create(pixels)
            count += len(pixels)
    return index_layers.values(), count


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("-f", "--filepath",
                            required=True,
                            default=None,
                            help="CSV Raster File to load")
        parser.add_argument("-e", "--encoding",
                            default="utf8",
                            help="Encoding of the CSV file [DEFAULT='utf8']")
        parser.add_argument("-p", "--pixel-size",
                            type=int,
                            default=5,
                            help="CSV Raster Pixel Size (meters)")
        parser.add_argument("-c", "--csv-srid",
                            dest="csv_srid",
                            type=int,
                            default=WGS84_SRID,
                            help="Input CSV Lon/Lat SRID. (DEFAULT=4326 [WGS84])")
        parser.add_argument("-i", "--indexes",
                            type=int,
                            default=[3,],
                            nargs="+",
                            help="Column indexes for the 'value(s)' to be loaded [DEFAULT=(3,)]")
        parser.add_argument("--lon-idx",
                            dest="lon_idx",
                            default=2,
                            type=int,
                            help="Column Index (0 start) of 'longitude' in decimal degrees [DEFAULT=1]")
        parser.add_argument("--lat-idx",
                            dest="lat_idx",
                            default=1,
                            type=int,
                            help="Column Index (0 start) of 'latitude' in decimal degrees [DEFAULT=2]")
        parser.add_argument("-n", "--name",
                            default=None,
                            type=str,
                            help="If given this name will be applied to resulting RasterAggregatedLayer [DEFAULT=None]")
        parser.add_argument("-o", "--opacity",
                            default=0.75,
                            type=float,
                            help="Layer Suggested Opacity [DEFAULT={}]".format(0.75))
        parser.add_argument("-d", "--datetime-idx",
                            default=0,
                            type=int,
                            help="Column index of datetime [DEFAULT=0]")
        parser.add_argument("--datetime-format-str",
                            default="%H:%M:%S.%f %d-%m-%Y",
                            help="Datetime format string to use [DEFAULT='%%H:%%M:%%S.%%f %%d-%%m-%%Y']")
        parser.add_argument("--no-datetime",
                            default=False,
                            action="store_true",
                            help="If given datetime column will not be necessary, and load time will be used.")
        parser.add_argument("--no-headers",
                            default=False,
                            action="store_true",
                            help="If given the first line will be *included* as data")

    def handle(self, *args, **options):

        result_layers, count = load_raster_csv(options["filepath"],
                                               options["name"],
                                                options["encoding"],
                                                options["pixel_size"],
                                                options["csv_srid"],
                                                options["indexes"],
                                                options["lon_idx"],
                                                options["lat_idx"],
                                                options["datetime_idx"],
                                                options["datetime_format_str"],
                                                options["opacity"],
                                                options["no_datetime"],
                                                options["no_headers"])
        self.stdout.write("Created ({}) pixels in the following RasterAggregatedLayer(s): ".format(count))
        for raster_layer in result_layers:
            # auto create legend
            legend = raster_layer.auto_create_legend(more_is_better=True)
            raster_layer.legend = legend
            raster_layer.save()

            # create map layer (for viewing)
            raster_layer.create_map_layer()
            self.stdout.write("[{}] {}".format(raster_layer.id, raster_layer.name))

