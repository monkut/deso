"""
Functions for generating a new RasterAggregatedLayer object by comparing existing RasterAggregatedLayer objects.
"""
import datetime
from functools import partial
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from ...models import RasterAggregatedLayer, NumericRasterAggregateData

WGS84_SRID = settings.WGS84_SRID

COMMIT_COUNT = 5000

class NoOverlapingData(Exception):
    pass

def diff(layer_one, layer_two, minimum_samples, fill_value=None, gte_value=None, lte_value=None, absolute=False):
    """
    Create a RasterAggregatedLayer object containing the difference of the layer's value field as defined in 'value_fieldname'.
    diff_layer = layer_one - layer_two
    :param layer_one: RasterAggregatedLayer object
    :param layer_two: RasterAggregatedLayer object
    :param minimum_samples: minimum samples filter (int)
    :return: RasterAggregatedLayer object, Resulting Bin Count
    """
    assert layer_one.pixel_size_meters == layer_two.pixel_size_meters
    diff_layer = RasterAggregatedLayer(data_model="NumericRasterAggregateData",
                                       name="Diff Layer ({} - {})".format(layer_one.id, layer_two.id),
                                       aggregation_method="difference",
                                       pixel_size_meters=layer_one.pixel_size_meters,
                                       minimum_samples=minimum_samples)
    diff_layer.save()
    # expect that x,y is unique in layer
    first_queryset = layer_one.pixels()
    second_queryset = layer_two.pixels()

    kwargs = {"samples__gte": minimum_samples}
    if gte_value is not None:
        kwargs["{}__gte".format(layer_one.value_fieldname)] = gte_value
    elif lte_value is not None:
        kwargs["{}__lte".format(layer_one.value_fieldname)] = lte_value

    # get locations that meet the criteria from both layers
    ewkt_locations = set(p.ewkt for p in first_queryset.filter(**kwargs).values_list("location", flat=True))
    ewkt_locations.update(set(p.ewkt for p in second_queryset.filter(**kwargs).values_list("location", flat=True)))

    # reinstantiate querysets after gathering locations
    first_queryset = layer_one.pixels()
    second_queryset = layer_two.pixels()

    # ignore extra kwargs in order to get locations that match both layers!
    first_values = {location.ewkt: value for location, value in first_queryset.filter(samples__gte=minimum_samples).values_list("location", layer_one.value_fieldname) if location.ewkt in ewkt_locations}
    diff_data_items = []
    count = 0
    filled_locations = []
    for location, second_samples, second_value in second_queryset.filter(samples__gte=minimum_samples).values_list("location", "samples", layer_one.value_fieldname):
        if location.ewkt in first_values:
            if absolute:
                diff_value = abs(first_values[location.ewkt] - second_value)
            else:
                diff_value = first_values[location.ewkt] - second_value
            diff_data = NumericRasterAggregateData(layer=diff_layer,
                                                   location=location,
                                                   samples=second_samples,
                                                   difference=diff_value)
            diff_data_items.append(diff_data)
            count += 1
            filled_locations.append(location.ewkt)

            if len(diff_data_items) > COMMIT_COUNT:
                NumericRasterAggregateData.objects.bulk_create(diff_data_items)
                diff_data_items = []

    if fill_value is not None:
        for unfilled_location_ewkt in set(first_values.keys()) - set(filled_locations):
            diff_value = fill_value
            data = NumericRasterAggregateData(layer=diff_layer,
                                              location=GEOSGeometry(unfilled_location_ewkt),
                                              samples=0,
                                              percentage=diff_value)
            diff_data_items.append(data)
            count += 1


    # commit remaining
    if diff_data_items:
        NumericRasterAggregateData.objects.bulk_create(diff_data_items)

    if not NumericRasterAggregateData.objects.filter(layer=diff_layer).exists():
        raise NoOverlapingData("Diff layer contains no Data! (check that both input layers can be displayed on map after removing browser cache)")

    # auto-create legend
    if absolute:
        legend = diff_layer.auto_create_legend(more_is_better=False,
                                               color_manager_class="ScaledDiffColorManager")
    else:
        legend = diff_layer.auto_create_legend(more_is_better=True,
                                               color_manager_class="ScaledDiffColorManager")
    diff_layer.legend = legend
    diff_layer.save()

    # create MapLayer (for viewing)
    diff_layer.create_map_layer()

    return diff_layer, count


def percentage(layer_one, layer_two, minimum_samples, fill_value=None, gte_value=None, lte_value=None):
    """
    Create a RasterAggregatedLayer containing the percentage of layer_two to layer_one
    Uses 'samples' field of NumericRasterAggregateData to calculate percentage
    :param layer_one: RasterAggregatedLayer object
    :param layer_two: RasterAggregatedLayer object
    :param minimum_samples: minimum samples filter (int)
    :return: RasterAggregatedLayer object, resulting bin count
    """
    assert layer_one.pixel_size_meters == layer_two.pixel_size_meters
    compare_layer = RasterAggregatedLayer(data_model="NumericRasterAggregateData",
                                       name="Percentage Layer ({} - {})".format(layer_one.id, layer_two.id),
                                       aggregation_method="percentage",
                                       pixel_size_meters=layer_one.pixel_size_meters,
                                       minimum_samples=minimum_samples)
    compare_layer.save()
    # expect that x,y is unique in layer
    first_queryset = layer_one.pixels()
    second_queryset = layer_two.pixels()

    kwargs = {"samples__gte": minimum_samples}
    if gte_value is not None:
        kwargs["{}__gte".format(layer_one.value_fieldname)] = gte_value
    elif lte_value is not None:
        kwargs["{}__lte".format(layer_one.value_fieldname)] = lte_value

    # get locations that meet the criteria from both layers
    ewkt_locations = set(p.ewkt for p in first_queryset.filter(**kwargs).values_list("location", flat=True))
    ewkt_locations.update(set(p.ewkt for p in second_queryset.filter(**kwargs).values_list("location", flat=True)))

    # reinstantiate querysets
    first_queryset = layer_one.pixels()
    second_queryset = layer_two.pixels()

    # ignore extra kwargs in order to get locations that match both layers!
    first_values = {location.ewkt: sample_count for location, sample_count in first_queryset.filter(samples__gte=minimum_samples).values_list("location", "samples") if location.ewkt in ewkt_locations}
    data_items = []
    count = 0
    filled_locations = []
    for location, second_samples in second_queryset.filter(samples__gte=minimum_samples).values_list("location", "samples"):
        if location.ewkt in first_values:
            if first_values[location.ewkt] > 0:
                percentage_value = round((second_samples/first_values[location.ewkt]) * 100, 2)
                data = NumericRasterAggregateData(layer=compare_layer,
                                                       location=location,
                                                       samples=second_samples,
                                                       percentage=percentage_value)
                data_items.append(data)
                count += 1
                filled_locations.append(location.ewkt)

                if len(data_items) > COMMIT_COUNT:
                    NumericRasterAggregateData.objects.bulk_create(data_items)
                    data_items = []

    if fill_value is not None:
        for unfilled_location_ewkt in set(first_values.keys()) - set(filled_locations):
            percentage_value = fill_value
            data = NumericRasterAggregateData(layer=compare_layer,
                                              location=GEOSGeometry(unfilled_location_ewkt),
                                              samples=0,
                                              percentage=percentage_value)
            data_items.append(data)
            count += 1

    # commit remaining
    if data_items:
        NumericRasterAggregateData.objects.bulk_create(data_items)

    # auto-create legend
    legend = compare_layer.auto_create_legend(more_is_better=False,
                                              color_manager_class="ScaledFloatColorManager")
    compare_layer.legend = legend
    compare_layer.save()

    # create MapLayer (for viewing)
    compare_layer.create_map_layer()

    return compare_layer, count

# mapping of method name to method function
# --> used to validate user input from commandline
VALID_METHODS = {"diff": diff,
                 "absdiff": partial(diff, absolute=True),
                 "percentage": percentage}

class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument("-f", "--first-layer-id",
                            type=int,
                            required=True,
                            default=None,
                            help="RasterAggregatedLayer.id of first layer")
        parser.add_argument("-s", "--second-layer-id",
                            type=int,
                            default=None,
                            required=True,
                            help="RasterAggregatedLayer.id of second layer")
        parser.add_argument("-m", "--minimum-samples",
                            type=int,
                            default=250,
                            help="Minimum number of samples in pixel for it to be considered for DIFF [DEFAULT=250]")
        parser.add_argument("-c", "--compare-method",
                            default="diff",
                            help="Compare Method to use ({}) [DEFAULT='diff']".format("|".join(VALID_METHODS.keys())))
        parser.add_argument("--fill-value",
                            type=float,
                            default=None,
                            help="If given, this value will be used to create BINs where the second-layer does not overlap the first-layer.[DEFAULT=None]")
        parser.add_argument("--value-gte",
                            default=None,
                            type=float,
                            help="If given, this value will be used to filter values of the FIRST, '-f' layer so that it will only include values >= the given value.")
        parser.add_argument("--value-lte",
                            default=None,
                            type=float,
                            help="If given, this value will be used to filter values of the FIRST, '-f' layer so that it will only include values <= the given value.")


    def handle(self, *args, **options):
        start = datetime.datetime.now()
        if options["compare_method"] not in VALID_METHODS:
            raise CommandError("Given '--compare-method' ({}) not in VALID METHODS({})".format(options["compare_method"],
                                                                                                ",".join(VALID_METHODS.keys())))

        if options["value_lte"] is not None and options["value_gte"] is not None:
            raise CommandError("Both '--value-gte' and '--value-lte' options were given, only one may be used at at time!")

        self.stdout.write("Start: {}".format(start))
        layer_one = RasterAggregatedLayer.objects.get(id=options["first_layer_id"])
        layer_two = RasterAggregatedLayer.objects.get(id=options["second_layer_id"])
        self.stdout.write("First Layer-id: {}".format(options["first_layer_id"]))
        self.stdout.write("Second Layer-id: {}".format(options["second_layer_id"]))
        self.stdout.write("Minimum Samples: {}".format(options["minimum_samples"]))
        self.stdout.write("Performing [{}] comparison using: {}, {}...".format(options["compare_method"],
                                                                               str(layer_one),
                                                                               str(layer_two)))
        compare_function = VALID_METHODS[options["compare_method"]]
        if options["value_gte"]:
            self.stdout.write("(FIRST LAYER VALUE) >= {0} OR (SECOND LAYER VALUE) >= {0} ".format(options["value_gte"]))
        if options["value_lte"]:
            self.stdout.write("(FIRST LAYER VALUE) <= {0} OR (SECOND LAYER VALUE) <= {0} ".format(options["value_lte"]))

        layer, count = compare_function(layer_one, layer_two, options["minimum_samples"], options["fill_value"], gte_value=options["value_gte"], lte_value=options["value_lte"])
        self.stdout.write("--> NumericRasterAggregateData({}) entries created!".format(count))
        end = datetime.datetime.now()
        self.stdout.write("End: {}".format(end))
        elapsed = end - start
        self.stdout.write("Elapsed: {}".format(elapsed))

