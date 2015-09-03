
"""
Create a RasterAggregatedLayer object and related NumericRasterAggregateData
from a given CSV.file.  Results will be aggregated.
"""
import os
import csv
import sys
import gzip
import datetime
from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import Point, GEOSGeometry
from django.conf import settings
from .....functions  import WelfordRunningVariance, WelfordRunningVariancedB
from ...models import RasterAggregatedLayer, NumericRasterAggregateData

WGS84_SRID = 4326
SPHERICAL_MERCATOR_SRID = 3857 # google maps projection

COMMIT_COUNT = 50000

def load_to_raster_layer(raster_data, options, kpi_name):
    """
    Load aggregated raster data to DB
    :param raster_data: { KEY: WelfordRunningVariance Object, ... }
    :return: RasterAggregatedLayer object
    """
    default_aggregation_method = "mean"
    if options["name"]:
        layer_name = options["name"]
    else:
        layer_name = "{} ({})".format(os.path.split(options["filepath"])[-1], kpi_name)
    layer = RasterAggregatedLayer(filepath=options["filepath"],
                                  data_model="NumericRasterAggregateData",
                                  name=layer_name,
                                  opacity=options["opacity"],
                                  aggregation_method=default_aggregation_method,
                                  pixel_size_meters=options["pixel_size"],
                                  minimum_samples=options["minimum_samples"],
                                  )
    layer.save()
    source_file_datetime = datetime.datetime.fromtimestamp(os.path.getmtime(options["filepath"]))
    count = 0
    numeric_data = []
    for pixel_key_ewkt, welford_object in raster_data.items():
        # skip if minimum samples condition is not met
        if options["minimum_samples"] and welford_object.count() < options["minimum_samples"]:
            continue
        pixel_location = GEOSGeometry(pixel_key_ewkt)
        data = NumericRasterAggregateData(layer=layer,
                                          location=pixel_location,
                                          dt=source_file_datetime,
                                          samples=welford_object.count(),
                                          mean=welford_object.mean(),
                                          variance=welford_object.var(),
                                          stddev=welford_object.stddev(),
                                          sum=welford_object.sum(),
                                          maximum=welford_object.max(),
                                          minimum=welford_object.min(),)
        numeric_data.append(data)
        count += 1
        if len(numeric_data) >= COMMIT_COUNT:
            NumericRasterAggregateData.objects.bulk_create(numeric_data)
            numeric_data = []
    # commit remaining
    if numeric_data:
        NumericRasterAggregateData.objects.bulk_create(numeric_data)
    return layer, count


def get_lonlat_point(line, lon_idx, lat_idx, line_srid=WGS84_SRID, line_number=None, show_warnings=False):
    p = None
    if len(line) -1 >= lon_idx and len(line) -1 >= lat_idx:
        raw_lon = line[lon_idx]
        raw_lat = line[lat_idx]

        # determine if value is a number
        if raw_lon and raw_lat and any(c.isdigit() for c in raw_lon) and any(c.isdigit() for c in raw_lat):
            p = Point(float(line[lon_idx]), float(line[lat_idx]), srid=line_srid)
        elif show_warnings:
            # only show warnings if a value exists
            if raw_lon or raw_lat:
                print("WARNING -- [{}] Lon/Lat fields invalid: {},{}".format(line_number, raw_lon, raw_lat),
                      file=sys.stderr)
    return p


def rasterize_csv(csv_file, pixel_size_meters=5, csv_srid=WGS84_SRID, raster_srid=SPHERICAL_MERCATOR_SRID, value_idx=3, lon_idx=1, lat_idx=2, include_only_values=None, null_fill_value=None, decibels=False, no_headers=False):
    csv_filepath = os.path.abspath(csv_file)
    WelfordRunningAggregator = WelfordRunningVariance
    if decibels:
        WelfordRunningAggregator = WelfordRunningVariancedB
    read_open = open
    read_mode = "rt"
    if csv_filepath.endswith(".gz"):
        read_open = gzip.open
        read_mode = "rt"

    raster_data = {}
    with read_open(csv_filepath, read_mode) as in_f:
        reader = csv.reader(in_f)
        if not no_headers:
            headers = next(reader)
            assert headers[value_idx]
            value_fieldname = headers[value_idx]
        else:
            value_fieldname = "Unknown (no-headers)"

        for line in reader:
            point = get_lonlat_point(line, lon_idx, lat_idx, csv_srid)
            # convert to meters srid
            point.transform(raster_srid)
            snapped_x = point.x - (point.x % pixel_size_meters)
            snapped_y = point.y - (point.y % pixel_size_meters)
            snapped_point = Point(snapped_x, snapped_y, srid=raster_srid)

            if point:
                value_raw = line[value_idx]
                if value_raw:
                    value = float(value_raw)
                    bin_key = snapped_point.ewkt
                    if bin_key not in raster_data:
                        raster_data[bin_key] = WelfordRunningAggregator()
                    raster_data[bin_key].send(value)
    return value_fieldname, raster_data


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("-f", "--filepath",
                            required=True,
                            default=None,
                            help="CSV to Bin/Rasterize")
        parser.add_argument("-p", "--pixel-size",
                            type=int,
                            default=5,
                            help="Desired Pixel Size (meters) [DEFAULT=5]")
        parser.add_argument("-c", "--csv_srid",
                            type=int,
                            default=WGS84_SRID,
                            help="Input CSV Lon/Lat SRID. (DEFAULT=4326 [WGS84])")
        parser.add_argument("-i", "--index",
                            type=int,
                            default=3,
                            help="Column index for the 'value' to be bin aggregated")
        parser.add_argument("--lon_idx",
                            default=1,
                            type=int,
                            help="Column Index (0 start) of 'longitude' in decimal degrees.")
        parser.add_argument("--lat_idx",
                            default=2,
                            type=int,
                            help="Column Index (0 start) of 'latitude' in decimal degrees.")
        parser.add_argument("--ifequals",
                            nargs="+",
                            default=None,
                            type=str,
                            help="Include only these 'values' (only works for int() values).")
        parser.add_argument("-m", "--minimum-samples",
                            default=None,
                            type=int,
                            help="Minimum Samples count in pixel to be considered for DB storage [DEFAULT=None]")
        parser.add_argument("-o", "--opacity",
                            default=0.75,
                            type=float,
                            help="Layer Suggested Opacity [DEFAULT={}]".format(0.75))
        parser.add_argument("-n", "--name",
                            default=None,
                            type=str,
                            help="If given this name will be applied to resulting RasterAggregatedLayer [DEFAULT=None]")
        parser.add_argument("--decibels",
                            default=False,
                            action="store_true",
                            help="If given value will be aggregated using decibels (dB) aggregation [DEFAULT=False]")
        parser.add_argument("--no-headers",
                            default=False,
                            action="store_true",
                            help="If given the first line will be *included* as data")


    def handle(self, *args, **options):

        if not os.path.exists(options["filepath"]):
            raise CommandError("Given File not found: {}".format(options["filepath"]))

        start = datetime.datetime.now()
        self.stdout.write("Start: {}".format(start))
        self.stdout.write("CSV File: {}".format(options["filepath"]))
        self.stdout.write("Pixel Size: {}m".format(options["pixel_size"]))
        self.stdout.write("CSV SRID: {}".format(options["csv_srid"]))
        self.stdout.write("Column Index To Aggregate: {}".format(options["index"]))
        self.stdout.write("Opacity: {}".format(options["opacity"]))
        if options["ifequals"]:
            self.stdout.write("Only using values: {}".format(options["ifequals"]))
        value_fieldname, raster_data = rasterize_csv(options["filepath"],
                                    options["pixel_size"],
                                    options["csv_srid"],
                                    settings.METERS_SRID,
                                    options["index"],
                                    options["lon_idx"],
                                    options["lat_idx"],
                                    options["ifequals"],
                                    options["decibels"],
                                    options["no_headers"],
                                    )
        self.stdout.write("Loading aggregated data to database...")
        layer, pixel_count = load_to_raster_layer(raster_data, options, value_fieldname)

        # create legend
        self.stdout.write("Creating Related Legend...")
        legend = layer.auto_create_legend()
        layer.legend = legend
        layer.save()

        # create map layer
        self.stdout.write("Creating MapLayer() object for viewing...")
        layer.create_map_layer()

        end = datetime.datetime.now()
        self.stdout.write("End: {}".format(end))
        elapsed = end - start
        self.stdout.write("Elapsed: {}".format(elapsed))




