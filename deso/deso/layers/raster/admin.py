from django.contrib import admin

from .models import ScaledColorLegend, RasterAggregatedLayer


class ScaledLegendAdmin(admin.ModelAdmin):
    list_display = ("id",
                    "name",
                    "created_datetime",
                    "created_by",
                    "hex_min_color",
                    "hex_max_color",
                    "display_band_count",
                    "minimum_value",
                    "maximum_value",
                    "color_manager_class",
    )
    list_display_links = ("id", "name", )

    def save_model(self, request, obj, form, change):
        if not obj.id:  # check if this is the first creation.
            obj.created_by = request.user
        obj.save()


class RasterAggregatedLayerAdmin(admin.ModelAdmin):

    list_display = ("id",
                    "name",
                    "legend",
                    "filepath",
                    "created_datetime",
                    "data_model",
                    "aggregation_method",
                    "srid",
                    "pixel_size_meters",
                    "minimum_samples",)
    list_display_links = ("id", "name", "filepath", )
    ordering = ('-created_datetime',)

    def has_add_permission(self, request, obj=None):
        # layers are *not* added via the admin interface.
        # --> data must be loaded via the appropriate management command
        permission = False
        return permission

admin.site.register(ScaledColorLegend, ScaledLegendAdmin)
admin.site.register(RasterAggregatedLayer, RasterAggregatedLayerAdmin)