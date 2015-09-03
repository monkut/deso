from django.contrib import admin

from .models import GeoJsonLayer


class GeoJsonLayerAdmin(admin.ModelAdmin):
    list_per_page = 5000

admin.site.register(GeoJsonLayer, GeoJsonLayerAdmin)