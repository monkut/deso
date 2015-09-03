import json
from django.conf import settings
from django.shortcuts import redirect
from django.views.decorators.cache import cache_page
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from .models import MapLayerCollection, MapLayer

@cache_page(60 * 5)
def get_available_collections(request):
    available_collections =[]
    for collection in MapLayerCollection.objects.all():
        collection_info = {"properties": {"name": collection.name,
                                          "description": collection.description,
                                          "collection-url": collection.get_absolute_url(),
                                          "id": collection.id,
                                          },
                              "layers": [],
                              }
        for ml in collection.maplayer_set.all():
            collection_info["layers"].append(ml.info())
        available_collections.append(collection_info)
    return HttpResponse(json.dumps(available_collections), content_type='application/json')


@cache_page(60 * 5)
def get_available_maplayers(request):
    available_maplayers = []
    for maplayer in MapLayer.objects.order_by("created_datetime"):
        available_maplayers.append(maplayer.info())
    return HttpResponse(json.dumps(available_maplayers), content_type='application/json')


def get_collection(request, collection_id=None):
    try:
        collection = MapLayerCollection.objects.get(id=collection_id)
    except MapLayerCollection.DoesNotExist:
        return HttpResponseNotFound("Requested Collection({}) Not Found!".format(collection_id))
    collection_info = {"properties": {"name": collection.name,
                                      "description": collection.description,
                                      "collection-url": collection.get_absolute_url(),
                                      "id": collection.id,
                                      },
                      "layers": [],
                      }

    for ml in collection.maplayer_set.all():
        collection_info["layers"].append(ml.info())

    return HttpResponse(json.dumps(collection_info), content_type='application/json')


def get_collection_map(request, collection_id=None):
    """Return url loaded with collection"""
    if not collection_id:
        raise HttpResponseBadRequest("Collection ID not given!")

    url = "http://{host}:{port}/static/index.html?collection={collection_id}".format(host=settings.HOST,
                                                                                     port=settings.PORT,
                                                                                     collection_id=collection_id)
    return redirect(url)