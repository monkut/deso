from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from .models import MapLayerCollection, MapLayer

class MapLayerCollectionAdmin(admin.ModelAdmin):
    list_per_page = 5000
    list_display = ("id", "name", "description")
    list_display_links = ("id", "name")
    search_fields = ('name','description')

    def save_model(self, request, obj, form, change):
        if obj and obj.created_by is None:
            obj.created_by = request.user
        obj.save()

class MapLayerAdmin(admin.ModelAdmin):
    list_per_page = 5000
    list_display = ("name", 'created_datetime', "type", "url", "description")
    search_fields = ('name', 'description')

    def save_model(self, request, obj, form, change):
        if obj and obj.created_by is None:
            obj.created_by = request.user
        obj.save()


admin.site.register(MapLayerCollection, MapLayerCollectionAdmin)
admin.site.register(MapLayer, MapLayerAdmin)
admin.site.unregister(User)  # so not displayed in admin
admin.site.unregister(Group)  # so not displayed in admin