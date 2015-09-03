import logging
import json
from collections import OrderedDict
from io import BytesIO
from colorsys import hls_to_rgb

from django.http import HttpResponse, HttpResponseBadRequest
from django.views.generic import View

from tmstiler.django import DjangoRasterTileLayerManager, LayerNotConfigured

from .models import RasterAggregatedLayer, ScaledColorLegend


# Get an instance of a logger
logger = logging.getLogger(__name__)


class Legend:

    def __init__(self, maximum_value, minimum_value, maximum_hue=61, minimum_hue=246, maximum_depth=6):
        self.maximum_value = maximum_value
        self.minimum_value = minimum_value
        self.maximum_hue = maximum_hue
        self.minimum_hue = minimum_hue
        self.maximum_depth = maximum_depth


    def get_color_str(self, model_instance, value=None, htmlhex=False):
        """
        :param value:
        :return:  rgb or hsl color string in the format:

        rgb(255,0,0)
        rgb(100%,0%,0%)

        hsl(hue, saturation%, lightness%)
        where:
            hue is the color given as an angle between 0 and 360 (red=0, green=120, blue=240)
            saturation is a value between 0% and 100% (gray=0%, full color=100%)
            lightness is a value between 0% and 100% (black=0%, normal=50%, white=100%).

        For example, hsl(0,100%,50%) is pure red.
        """
        if not value:
            value = model_instance.value
        full_range = self.maximum_value - self.minimum_value
        if self.minimum_hue > self.maximum_hue:
            color_range = self.minimum_hue - self.maximum_hue
        else:
            color_range = self.maximum_hue - self.minimum_hue

        if value > self.maximum_value:
            value = self.maximum_value
        elif value < self.minimum_value:
            value = self.minimum_value

        saturation = 1.0
        if model_instance:
            # adjust saturation based on months_to_actual
            # moves color to grey
            saturation = 1.0 - (model_instance.months_to_actual / self.maximum_depth)
            if saturation < 0.0:
                saturation = 0.0

        saturation_percentage = int(100 * saturation)

        value_percentage = (value - self.minimum_value)/full_range
        if self.minimum_hue > self.maximum_hue:
            # invert
            h = int(color_range - (value_percentage * color_range))
        else:
            h = int(value_percentage * color_range)

        result_str = "hsl({}, {}%, 50%)".format(h, saturation_percentage)

        if htmlhex:
            # convert hsl string to rgb hex
            hls = (h/360, .5, saturation)
            rgb = [int(i * 255) for i in hls_to_rgb(*hls)]
            result_str = "#" + "".join("{:02x}".format(i) for i in rgb)

        return result_str

    def html(self, display_band_count=6, invert=True):
        """
        :param invert: toggle to invert, so that larger values are on top
        :type invert: bool
        :returns: html legend snippet for leaflet map display

        Create the html needed for leaflet.js legend display
        reference:
        http://leafletjs.com/examples/choropleth.html
        """
        div_innerHTML = []
        band_count = display_band_count - 1  # adjust to n-1 (last MAX value added automatically

        full_range = self.maximum_value - self.minimum_value
        step = full_range / band_count
        for i in range(int(band_count)):
            current_value = self.minimum_value + (i * step)
            next_value = current_value + step
            color_str = self.get_color_str(None, value=current_value, htmlhex=True)
            # dash, "-": &ndash;
            # tilde, "~": &#126;
            grade_html = '''<i style="background:{rgb}"></i>{value} &#126; {next}<br>'''.format(rgb=color_str,
                                                                                                value=round(current_value, 2),
                                                                                                next=round(next_value, 2))
            div_innerHTML.append(grade_html)
        # add the last maximum value
        color_str = self.get_color_str(None, self.maximum_value, htmlhex=True)
        grade_html = '''<i style="background:{rgb}"></i>{value} +<br>'''.format(rgb=color_str,
                                                                                value=round(self.maximum_value, 2))
        div_innerHTML.append(grade_html)
        if invert:
            div_innerHTML = list(reversed(div_innerHTML))
        return "".join(div_innerHTML)


def get_layers(request):
    """
    determine and return a list of available bandclass site layers for *all* databases
     Layers are in the format:
    {
       "name": "<name>",
       "id": <id>,
       "url": "<url>",
       "centerlon": "<centerlon>",
       "centerlat": "<centerlat>",
       "type": "TileLayer-Overlay",
    }
    """
    available_layers =[]
    for layer in RasterAggregatedLayer.objects.order_by("id"):
        available_layers.append(layer.info())
    return HttpResponse(json.dumps(available_layers), content_type='application/json')


class LegendNotDefined(Exception):
    pass

class RasterLayersTileView(View):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layers = OrderedDict()
        for raster_layer in RasterAggregatedLayer.objects.order_by("id"):
            if raster_layer.legend is not None:
                # Only add layers with defined legends
                #  --> raster tiles cannot be created without a color scheme, a legend is necessary for tile generation!
                DataModel = raster_layer.get_data_model()
                qs = DataModel.objects.filter(layer=raster_layer)
                layers[str(raster_layer.id)] = {
                            "pixel_size": raster_layer.pixel_size_meters,  # currently hard-coded in measurements.management.commands.load_safecast_csv
                            "point_position": "upperleft",
                            "model_queryset": qs,
                            "model_point_fieldname": "location",
                            "model_value_fieldname": raster_layer.value_fieldname,
                            "round_pixels": False,
                            "legend_instance": raster_layer.legend,  # object with '.get_color_str()' method that returns an rgb() or hsl() color string.
                            }
            else:
                logger.warn("RasterAggregatedLayer:  {} has no legend defined!".format(str(raster_layer)))

        self.tilemgr = DjangoRasterTileLayerManager(layers)

    def get(self, request):
        layername, zoom, x, y, image_format = self.tilemgr.parse_url(request.path)
        logger.info("layername({}) zoom({}) x({}) y({}) image_format({})".format(layername, zoom, x, y, image_format))
        try:
            mimetype, tile_pil_img_object = self.tilemgr.get_tile(layername, zoom, x, y)
        except LayerNotConfigured:
            return HttpResponseBadRequest("Requested RasterLayer({}) Does Not Exist!".format(layername))
        image_encoding = image_format.replace(".", "")

        # pillow tile_pil_img_object.tobytes() doesn't seem to work, workaround to serve raw bytes via BytesIO()
        image_fileio = BytesIO()
        tile_pil_img_object.save(image_fileio, image_encoding)
        image_fileio.seek(0)
        return HttpResponse(image_fileio, content_type=mimetype)


def get_legend(request, legend_id=None):
    """
    Get HTML legend for display in leaflet
    :param request:
    :param legend_id:
    :return:
    """
    legend = ScaledColorLegend.objects.get(id=legend_id)
    color_manager = legend.get_color_manager()
    return HttpResponse(color_manager.html(), content_type="text/html")



