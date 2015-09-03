import logging
import os
from colorsys import rgb_to_hls, hls_to_rgb

from django.contrib.gis.geos import Point
from django.contrib.gis.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.apps import apps
from django.core.cache import caches
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.db.models import Avg, Max, Min, StdDev
from deso.functions import WelfordRunningVariance

# Get an instance of a logger
logger = logging.getLogger(__name__)

WGS84_SRID = settings.WGS84_SRID
METERS_SRID = settings.SPHERICAL_MERCATOR_SRID

# Linked to NumericRasterAggregateData fieldnames,
# and used to pull out the value of interest in combination with 'value_fieldname' in the RasterAggregatedLayer
# NOTE: If fields are added to NumericRasterAggregateData, AGGREGATION_METHOD_CHOICES needs to be updated with that fieldname
AGGREGATION_METHOD_CHOICES = (
    # NOTE: db values are expected to match NumericRasterAggregateData fieldnames
    ("percentile_50", _("50th Percentile")),
    ("percentile_67", _("67th Percentile")),
    ("percentile_90", _("90th Percentile")),
    ("mean", _("Mean (average)")),
    ("median", _("Median")),
    ("variance", _("Variance")),
    ("stddev", _("Standard Deviation")),
    ("sum", _("Sum")),
    ("maximum", _("Maximum")),
    ("minimum", _("Minimum")),
    ("difference", _("Compare-Difference")),
    ("percentage", _("Compare-Percentage")),
)

BIN_SIZE_CHOICES = (
    (10, 10),
    (25, 25),
    (50, 50),
    (100, 100),
    (250, 250),
)

SPERICAL_MERCATOR_SRID = 3857 # Google maps projection

VALID_COLOR_MANAGERS = (
    ("ScaledFloatColorManager", "ScaledFloatColorManager"),
    ("ScaledDiffColorManager", "ScaledDiffColorManager"),
)

class ScaledColorLegend(models.Model):
    """
    Provides color scaling between minimum & maximum values
    """
    created_by = models.ForeignKey(User, null=True, editable=False)
    created_datetime = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=256,
                            unique=True,
                            help_text=_("kpi name that the legend represents"))
    hex_min_color = models.CharField(max_length=6,
                                     default="66b219", # 66b219=GREEN_RGB
                                     help_text=_("Color in HEX RGB (e.g. AABBCC) for the color to apply to the min value"))
    hex_max_color = models.CharField(max_length=6,
                                     default="cc0000", # cc0000=RED RGB
                                     help_text=_("Color in HEX RGB (e.g. AABBCC) for the color to apply to the max value"))
    display_band_count = models.SmallIntegerField(default=6,
                                                  help_text=_("Number of color bands to display in HTML legend"))
    minimum_value = models.FloatField()
    maximum_value = models.FloatField()
    color_manager_class = models.CharField(max_length=25,
                                           default="ScaledFloatColorManager",
                                           choices=VALID_COLOR_MANAGERS)

    def clean(self):
        if len(self.hex_max_color) != 6 or len(self.hex_min_color) != 6:
            raise ValidationError("'hex_max_color' or 'hex_min_color' are not the expected 6-digits long!")

    def save(self, *args, **kwargs):
        if self.id:
            # check if legend changed
            previous = ScaledColorLegend.objects.get(id=self.id)
            for fieldname in ("hex_min_color", "hex_max_color", "minimum_value", "maximum_value",):
                if getattr(self, fieldname) != getattr(previous, fieldname):
                    # clear cache if legend was changed, so raster is recreated.
                    cache = caches["tilecache"]
                    cache.clear()
                    break
        super(ScaledColorLegend, self).save(*args, **kwargs) # Call the "real" save() method.

    def __str__(self):
        return "[{}] {} ({} to {})".format(self.id,
                                            self.name,
                                            self.minimum_value,
                                            self.maximum_value)

    def get_absolute_url(self):
        return "http://{}:{}/raster/legend/{}/".format(settings.HOST,
                                                        settings.PORT,
                                                        self.id)

    def get_color_manager(self):
        if self.color_manager_class == "ScaledFloatColorManager":
            ColorManagerClass = ScaledFloatColorManager
        elif self.color_manager_class == "ScaledDiffColorManager":
            ColorManagerClass = ScaledDiffColorManager
        else:
            raise Exception("Unknown 'color_manager_class': {}".format(self.color_manager_class))

        if not hasattr(self, "color_manager"):
            color_manager = ColorManagerClass(self.name,
                                              self.minimum_value,
                                              self.maximum_value,
                                              self.hex_min_color,
                                              self.hex_max_color,
                                              self.display_band_count)
            self.color_manager = color_manager

        return self.color_manager

    def get_color_str(self, model_instance, model_value_fieldname="value"):
        """
        Method for supporting tmstiler Django view
        :param model_instance: Model containting a value to 'colorize'
        :param model_value_fieldname: fieldname in the model that holds the target 'value"
        :return: Color as 'hsl()' string.
        """
        if not hasattr(self, "color_manager"):
            self.get_color_manager()  # populates self.color_manager

        value = getattr(model_instance, model_value_fieldname)
        return self.color_manager.value_to_hsl(value, as_str=True)


class ScaledFloatColorManager:
    """
    Intended to provide a scaled legend for pciopt and kpi bin maps
    """

    def __init__(self, name, minimum_value, maximum_value, hex_color_min="66b219", hex_color_max="cc0000", display_band_count=6):
        self.name = name
        self.minimum_value = minimum_value
        self.maximum_value = maximum_value
        self.hex_min_color = hex_color_min
        self.hex_max_color = hex_color_max
        self.display_band_count = display_band_count


    def get_rgb_tuple(self, color):
        """
        :param color: hex string of RGB color, ex: 'FFFFFF'
        :returns: tuple of RGB color as integers between 0-255, ex: (255, 255, 255)

        Convert hex string value to tuple of ints
        'FFFFFF' --> (255, 255, 255)
        """
        assert len(self.hex_min_color) == 6
        assert len(self.hex_max_color) == 6
        color_tuple = []
        for idx in range(0, 6, 2):
            #color_tuple.append(self.hex_min_color[idx: idx+2])
            color_tuple.append(int(color[idx: idx+2], 16))
        return tuple(color_tuple)


    def value_to_hsl(self, value, as_str=False):
        """
        :param value: float value to convert to HSL color
        :param as_str: Toggle to force resulting HSL color as a string in the form  'hsl({}, {}%, {}%)'
        :type as_str: bool
        :returns: HSL color as tuple or string

        Convert the given value to the appropriate color
        resulting color is represented in HSL (not rgb)
        """
        if value < self.minimum_value:
            value = self.minimum_value
        elif value > self.maximum_value:
            value = self.maximum_value

        if self.minimum_value < 0:
            offset = abs(self.minimum_value)
            minimum_value = self.minimum_value + offset
            maximum_value = self.maximum_value + offset
            value = value + offset

        else:
            minimum_value = self.minimum_value
            maximum_value = self.maximum_value
        if all(i == 0 for i in (value, minimum_value, maximum_value)):
            scale = 1.0
        else:
            scale = float(value - minimum_value) / float(maximum_value - minimum_value)


        # scale all channels linearly between START_COLOR and END_COLOR
        start_rgb = self.get_rgb_tuple(self.hex_min_color)
        end_rgb = self.get_rgb_tuple(self.hex_max_color)

        # convert rgb to hsl
        # --> put rgb values on scale between 0, and 1 for usage with colorsys conversion functions
        # results in values 0-1 for all (h,l,s)
        start_hls = rgb_to_hls(*[v/255.0 for v in start_rgb])
        end_hls = rgb_to_hls(*[v/255.0 for v in end_rgb])

        h, l, s = [float(scale * (end-start) + start) for start, end in zip(start_hls, end_hls)]

        # adjust to expected scales 0-360, 0-100, 0-100
        h *= 360
        l *= 100
        s *= 100

        assert 0 <= h <= 360
        assert 0 <= l <= 100
        assert 0 <= s <= 100
        hsl_color = (int(h), int(s), int(l))
        if as_str:
            hsl_color = "hsl({}, {}%, {}%)".format(*hsl_color)
        return hsl_color


    def value_to_rgb(self, value, htmlhex=False, max_rgb_value=255):
        """
        :param value: float value to convert to RGB color
        :param htmlhex: toggle to return value as html formatted hex, ex: '#FFFFFF'
        :returns: RGB color as tuple or string

        convert the given float value to rgb color
        """
        # flooring value to the limits of the legend
        if value < self.minimum_value:
            value = self.minimum_value
        elif value > self.maximum_value:
            value = self.maximum_value

        # hsl is used because it is easier to 'rotate' evenly to another color on the spectrum
        h, s, l = self.value_to_hsl(value)
        # adjust range to be from 0 to 1 change to hls for use with hls_to_rgb()
        hls = (h/360.0, l/100.0, s/100.0)

        # covert to rgb
        if max_rgb_value == 255:
            # --> adjust values from 0 to 1, to 0 to 255
            rgb = [int(i * 255) for i in hls_to_rgb(*hls)]
        else:
            rgb= hls_to_rgb(*hls)

        if htmlhex:
            rgb = "#" + "".join("{:02x}".format(i) for i in rgb)
        return rgb

    def get_color_str(self, model_instance, model_value_fieldname="value"):
        """
        Method for supporting tmstiler Django view
        :param model_instance: Model containting a value to 'colorize'
        :param model_value_fieldname: fieldname in the model that holds the target 'value"
        :return: Color as 'hsl()' string.
        """
        value = getattr(model_instance, model_value_fieldname)
        return self.value_to_hsl(value, as_str=True)

    def html(self, invert=True):
        """
        :param invert: toggle to invert, so that larger values are on top
        :type invert: bool
        :returns: html legend snippet for leaflet map display

        Create the html needed for leaflet.js legend display
        reference:
        http://leafletjs.com/examples/choropleth.html
        """
        div_innerHTML = []
        band_count = self.display_band_count - 1# adjust to n-1 (last MAX value added automatically

        full_range = self.maximum_value - self.minimum_value
        step = full_range / band_count
        for i in range(int(band_count)):
            current_value = self.minimum_value + (i * step)
            next_value = current_value + step
            color_str = self.value_to_rgb(current_value, htmlhex=True)
            # dash, "-": &ndash;
            # tilde, "~": &#126;
            grade_html = '''<i style="background:{rgb}"></i>{value} &#126; {next}<br>'''.format(rgb=color_str,
                                                                                                value=round(current_value, 2),
                                                                                                next=round(next_value, 2))

            div_innerHTML.append(grade_html)
        # add the last maximum value
        color_str = self.value_to_rgb(self.maximum_value, htmlhex=True)
        grade_html = '''<i style="background:{rgb}"></i>{value} +<br>'''.format(rgb=color_str,
                                                                                value=round(self.maximum_value, 2))
        div_innerHTML.append(grade_html)
        if invert:
            div_innerHTML = list(reversed(div_innerHTML))
        return "".join(div_innerHTML)


class ScaledDiffColorManager(ScaledFloatColorManager):

    def value_to_hsl(self, value, as_str=False):
        """
        :param value: float value to convert to HSL color
        :param as_str: Toggle to force resulting HSL color as a string in the form  'hsl({}, {}%, {}%)'
        :type as_str: bool
        :returns: HSL color as tuple or string

        Convert the given value to the appropriate color
        resulting color is represented in HSL (not rgb)
        """
        full_color_luminosity = 50
        full_white_luminosity = 100

        # define which color to use
        if value >= 0:
            rgb_color = self.hex_max_color
        else:
            rgb_color = self.hex_min_color

        # once +/- color is defined use abs(value)
        value = abs(value)

        rgb = self.get_rgb_tuple(rgb_color)
        h, l, s = rgb_to_hls(*[v/255.0 for v in rgb])

        # adjust to expected scales 0-360, 0-100, 0-100
        h *= 360
        l *= 100
        s *= 100

        assert 0 <= h <= 360
        assert 0 <= l <= 100
        assert 0 <= s <= 100

        assert abs(self.minimum_value) == self.maximum_value # expected to be equal values above/below 0
        if value < 0:
            value = 0
        elif value > self.maximum_value:
            value = self.maximum_value

        # scale is garunteed zero base!
        scale = float(value)/float(self.maximum_value)

        # scale lumonosity between white and full color 100 (white) full (50)
        lumonosity = int(scale * (full_color_luminosity - full_white_luminosity) + full_white_luminosity)

        hsl_color = (int(h), int(s), int(lumonosity))
        if as_str:
            hsl_color = "hsl({}, {}%, {}%)".format(*hsl_color)
        return hsl_color


    def value_to_rgb(self, value, htmlhex=False):
        """
        :param value: float value to convert to RGB color
        :param htmlhex: toggle to return value as html formatted hex, ex: '#FFFFFF'
        :returns: RGB color as tuple or string

        convert the given float value to rgb color
        """
        # hsl is used because it is easier to 'rotate' evenly to another color on the spectrum
        h, s, l = self.value_to_hsl(value)
        # adjust range to be from 0 to 1 change to hls for use with hls_to_rgb()
        hls = (h/360.0, l/100.0, s/100.0)

        # covert to rgb
        # --> adjust values from 0 to 1, to 0 to 255
        rgb = [int(i * 255) for i in hls_to_rgb(*hls)]

        if htmlhex:
            rgb = "#" + "".join("{:02x}".format(i) for i in rgb)
        return rgb

    def html(self, invert=True):
        """
        :param invert: toggle to invert, so that larger values are on top
        :type invert: bool
        :returns: html legend snippet for leaflet map display

        Create the html needed for leaflet.js legend display
        reference:
        http://leafletjs.com/examples/choropleth.html
        """
        # diff legend expects equal values above and below "0"
        div_innerHTML = []
        bands = self.display_band_count

        step = int(self.maximum_value / (bands/2))

        for i in (1, -1):
            for current_value in range(step, int(self.maximum_value), step):
                next_value = current_value + step
                next_value *= i
                current_value *= i
                color_str = self.value_to_rgb(current_value, htmlhex=True)
                if abs(current_value) == self.maximum_value:
                    grade_html = '''<i style="background:{rgb}"></i>{value}<br>'''.format(rgb=color_str,
                                                                                          value=round(current_value, 2),
                                                                                          next=round(next_value, 2))
                else:
                    grade_html = '''<i style="background:{rgb}"></i>{value} &#126; {next}<br>'''.format(rgb=color_str,
                                                                                                        value=round(current_value, 2),
                                                                                                        next=round(next_value, 2))
                div_innerHTML.append(grade_html)
            if i == 1:
                # add max value
                max_color_rgb = self.value_to_rgb(self.maximum_value, htmlhex=True)
                grade_html = '''<i style="background:{rgb}"></i>{value} +<br>'''.format(rgb=max_color_rgb,
                                                                                        value=self.maximum_value)
                div_innerHTML.append(grade_html)
                div_innerHTML.reverse()
                grade_html = '''<i style="background:#ffffff"></i>0<br>'''
                div_innerHTML.append(grade_html)
        # add min legend value
        min_color_rgb = self.value_to_rgb(self.minimum_value, htmlhex=True)
        grade_html = '''<i style="background:{rgb}"></i>{value}<br>'''.format(rgb=min_color_rgb,
                                                                                value=self.minimum_value)
        div_innerHTML.append(grade_html)


        return "".join(div_innerHTML)


VALID_DATA_MODELS = (
    ("NumericRasterAggregateData", "NumericRasterAggregateData"),
    ("TextRasterAggregateData", "TextRasterAggregateData"),
)


class RasterAggregatedLayer(models.Model):
    created_by = models.ForeignKey(User, null=True, editable=False)
    created_datetime = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=256,
                            help_text=_("Source Data Column/KPI name"))
    opacity = models.FloatField(default=0.75, help_text="Suggested Layer Opacity")
    center = models.PointField(null=True, srid=METERS_SRID,
                               help_text=_("Center location of Layer"))
    filepath = models.FilePathField(max_length=256,
                                    editable=False,
                                    null=True)
    legend = models.ForeignKey(ScaledColorLegend, null=True)
    data_model = models.CharField(max_length=35,
                                  choices=VALID_DATA_MODELS,
                                  help_text=_("RasterAggregateData Django model where related data is stored"))
    aggregation_method = models.CharField(max_length=16,
                                          default="sum",
                                          choices=AGGREGATION_METHOD_CHOICES)
    srid = models.PositiveIntegerField(default=SPERICAL_MERCATOR_SRID)
    pixel_size_meters = models.IntegerField(choices=BIN_SIZE_CHOICES)
    minimum_samples = models.PositiveIntegerField(null=True,
                                                  help_text=_("Minimum sample size for bin"))

    objects = models.GeoManager()

    @property
    def value_fieldname(self):
        return self.aggregation_method

    def save(self, *args, **kwargs):
        if self.id:
            # check if legend changed
            previous = RasterAggregatedLayer.objects.get(id=self.id)
            if self.legend != previous.legend:
                cache = caches["tilecache"]
                cache.clear()
        super(RasterAggregatedLayer, self).save(*args, **kwargs) # Call the "real" save() method.


    def extent(self, as_wgs84=True):
        result = NumericRasterAggregateData.objects.filter(layer=self).extent()
        if as_wgs84:
            min_p = Point(*result[:2], srid=settings.METERS_SRID).transform(settings.WGS84_SRID, clone=True)
            max_p = Point(*result[2:], srid=settings.METERS_SRID).transform(settings.WGS84_SRID, clone=True)
            result = (min_p.x, min_p.y, max_p.x, max_p.y)
        return result


    def auto_create_legend(self, more_is_better=True, color_manager_class="ScaledFloatColorManager"):
        """
        Create a legend from the range of values in the layer
        :param more_is_better: Flag that defines which 'direction' is better (Default=True) [Better is green]
        :return: Legend Model Object (saved)
        """
        legend_name = "{} Legend".format(str(self))

        related_legends = ScaledColorLegend.objects.filter(name=legend_name)
        if related_legends:
            assert len(related_legends) == 1
            legend = related_legends[0]
        else:
            # calculate distribution
            RelatedModel = self.get_data_model()
            fieldname = self.value_fieldname
            results = RelatedModel.objects.filter(layer=self).aggregate(Avg(fieldname), Max(fieldname), Min(fieldname), StdDev(fieldname))
            # get rounded average
            avg_key = "{}__avg".format(fieldname)
            rounded_average = round(results[avg_key])
            # calculate modifier to get 'clean' values
            if rounded_average > 1000:
                modifier = 25
            else:
                modifier = 5

            mid_point = rounded_average - (rounded_average % modifier)
            stddev_key = "{}__stddev".format(fieldname)
            legend_max = mid_point + (results[stddev_key] * 1.5)
            # adjust to actual max if higher
            max_key = "{}__max".format(fieldname)
            if legend_max > results[max_key]:
                legend_max = results[max_key]
            legend_max -= legend_max % modifier

            legend_min = mid_point - (results[stddev_key] * 1.5)
            # adjust to actual min if lower
            min_key = "{}__min".format(fieldname)
            if legend_min < results[min_key]:
                legend_min = results[min_key]
            legend_min -= legend_min % modifier  # get clean value.

            if more_is_better:
                default_min_color = "cc0000"  # red
                default_max_color = "66b219"  # green
            else:
                default_min_color = "66b219"  # green
                default_max_color = "cc0000"  # red

            # adjust for Diff legend
            if color_manager_class == "ScaledDiffColorManager":
                # expect that max min are equal lengths
                # --> Use smallest
                if abs(legend_min) < legend_max:
                    legend_max = abs(legend_min)
                else:
                    legend_min = -legend_max

            legend = ScaledColorLegend(name=legend_name,
                                       hex_min_color=default_min_color,
                                       hex_max_color=default_max_color,
                                       minimum_value=legend_min,
                                       maximum_value=legend_max,
                                       color_manager_class=color_manager_class)
            legend.save()
        return legend

    def __str__(self):
        return "{}[{}-{}m]".format(self.name,
                                    self.aggregation_method,
                                    self.pixel_size_meters)

    def get_center(self, recalculate=False):
        p = None
        if not self.center or recalculate:
            welfords_x = WelfordRunningVariance()
            welfords_y = WelfordRunningVariance()
            numeric_raster_data = NumericRasterAggregateData.objects.filter(layer=self)
            for n in numeric_raster_data:
                welfords_x.send(n.location.x)
                welfords_y.send(n.location.y)

            text_raster_data = TextRasterAggregateData.objects.filter(layer=self)
            for t in text_raster_data:
                welfords_x.send(t.location.x)
                welfords_y.send(t.location.y)
            mean_x = welfords_x.mean()
            mean_y = welfords_y.mean()
            if mean_x and mean_y:
                p = Point(mean_x, mean_y, srid=self.srid)
                p.transform(METERS_SRID)
                self.center = p
                self.save()
        else:
            p = self.center
        return p

    def get_data_model(self):
        if self.data_model == "NumericRasterAggregateData":
            return NumericRasterAggregateData
        elif self.data_model == "TextRasterAggregateData":
            return TextRasterAggregateData
        else:
            raise Exception("Unknown data_model: {}".format(self.data_model))

    def info(self):
        """
        layer information dictionary to be converted to json
        """
        layer_center_point = self.get_center()
        if layer_center_point:
            layer_center_point.transform(WGS84_SRID)

        layer_unique_id = "{}:raster:{}".format(self._state.db,
                                                self.id)
        source_value = os.path.split(self.filepath)[-1] if self.filepath else None
        layer_info = {
                 "source": source_value,
                 "created_datetime": self.created_datetime.isoformat(),
                 "id": layer_unique_id,
                 "url": self.get_layer_url(),
                 "type": "TileLayer-overlay",
                 "extent": self.extent(),
                 "opacity": self.opacity,
                 }
        if self.legend:
            layer_info["legendUrl"] = self.legend.get_absolute_url()
        if layer_center_point:
            layer_info["centerlon"] = round(layer_center_point.x, 6)
            layer_info["centerlat"] = round(layer_center_point.y, 6)
        return layer_info

    def create_map_layer(self):
        """
        Create a layercollections.model.MapLayer for leaflet map display.
        :return: saved layercollections.model.MapLayer object
        """
        app_label = "layercollections"
        MapLayer = apps.get_model(app_label, "MapLayer")
        map_layer_name = "{} ({})".format(self.name,
                                          self.id)
        m = MapLayer(name=map_layer_name,
                     attribution="Nokia",
                     type="TileLayer-overlay",
                     center=self.get_center(),
                     opacity=self.opacity,
                     url=self.get_layer_url())
        if self.legend:
            m.legend_url = self.legend.get_absolute_url()
        m.save()
        return m

    def get_layer_url(self):
        """
        :return: URL from which layer is served
        """
        return "http://{}:{}/raster/layer/{}/{{z}}/{{x}}/{{y}}.png".format(settings.HOST,
                                                                            settings.PORT,
                                                                            self.id)

    def pixels(self):
        DataModel = self.get_data_model()
        return DataModel.objects.filter(layer=self)


class NumericRasterAggregateData(models.Model):
    layer = models.ForeignKey(RasterAggregatedLayer)
    location = models.PointField(srid=METERS_SRID)
    dt = models.DateTimeField(null=True)
    samples = models.PositiveIntegerField(help_text="Number of samples for pixel")

    percentile_50 = models.FloatField(null=True)
    percentile_67 = models.FloatField(null=True)
    percentile_90 = models.FloatField(null=True)
    mean = models.FloatField(null=True)
    median = models.FloatField(null=True)
    variance = models.FloatField(null=True)
    stddev = models.FloatField(null=True)
    sum = models.FloatField(null=True)
    maximum = models.FloatField(null=True)
    minimum = models.FloatField(null=True)
    difference = models.FloatField(null=True,
                                   help_text="For holding the result of 'compare_raster_layers' 'diff' method")
    percentage = models.FloatField(null=True,
                                   help_text="For holding the result of 'compare_raster_layers' 'percentage' method")
    objects = models.GeoManager()


class TextRasterAggregateData(models.Model):
    layer = models.ForeignKey(RasterAggregatedLayer)
    location = models.PointField(srid=METERS_SRID)
    dt = models.DateTimeField(null=True)
    value = models.CharField(max_length=255)
    mode = models.CharField(max_length=255,
                            null=True)


    objects = models.GeoManager()
