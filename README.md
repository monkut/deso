
# deso README

:language: python
:interpreter: 3.4


## About

This document describes the basic functionality of the 'deso' web map layer server project.

The 'deso' project is a server based application that allows creation and  display of web map (TMS) layer and GeoJSON layer information in map layer 'collections'.
The project supports multiple map layer 'collections', allowing for the prepartion and sharing of different sets of map layers for reporting and analysis.

This project has the following functionality:

- Display TMS Tiles
- Generate TMS Tiles (RASTER) from CSV input
- Display GeoJSON Layers

## Structure & Configuration


Configuration is performed through the 'deso' administration interface, available at http://(server):(port)/admin/

The administration interface provides the following categories:

    - Layercollections
        - For managing 'collections' of layers (local or remote)

    - Raster
        - For managing Raster Layers provided by the local 'deso' installation


    - Vector
        - For managing Vector Layers provided by the local 'deso' installation


### Layercollections

The Layercollections appliation provides the main interface for defining web map layers.
A 'MapLayerCollection' is a collection of basemap, and/or Overlay (raster, or vector) map layers.

A 'MapLayer' defines the initial proprties of the layer, and where and how the layer can be retrieved.

> *NOTE*
>
>    The 'MapLayer' mainted separately from internal raster, and vector applications in order to allow layers to be on a separate server.

> *WARNING*
>
>    While a 'MapLayer' does define a legend URL, the defined legend is for display purposes only, and changing this URL does not
>    affect how the related layer is displayed.


### Raster

Raster layers are spatially aggrgated layers and require a legend in order to apply colors to binned values.
A legend is automatically created and applied when a raster layer is created through the *management commands* listed below.

> *NOTE*
>
>    At the moment, when a raster layer's legend is changed, the tile-cache is invalidated, and deleted, forcing tiles to be regenerated.
>
>    The tile cache is located by default at:
>     /var/www/deso/deso/.tilecache


### Vector

Vector layers provide display of GeoJSON objects.


## Management Commands


The following django management commands are used to perform various loading and map layer creation functions for thier respective layers.
Commands are run from the 'deso' installation directory (Default: /var/www/deso/src/deso) where the django 'manage.py' file is located.

> *NOTE*
>
>    These commands must be run from the server where the 'deso' project is installed!



### Raster Layer Commands


[raster]
* compare_raster_layers
* create_raster_layer
* list_raster_layers

#### `list_raster_layers`


List the loaded Raster Layers
(Raster Layer ID is listed as the first number on the left, this number is used to identify layers when using the 'compare_raster_layers' command)

Example:

```console
$ python3 manage.py list_raster_layers
```


#### `compare_raster_layers`


Example:

```console
$ python3 manage.py compare_raster_layers -f 2 -s 25 -m 1 -c percentage
```


> *NOTE*
>
>    Layer IDs can be obtained using the `list_raster_layers` command.

Functions for generating a new RasterAggregatedLayer object by comparing
existing RasterAggregatedLayer objects.

```
optional arguments:
  -h, --help            show this help message and exit
  -f FIRST_LAYER_ID, --first-layer-id FIRST_LAYER_ID
                        RasterAggregatedLayer.id of first layer
  -s SECOND_LAYER_ID, --second-layer-id SECOND_LAYER_ID
                        RasterAggregatedLayer.id of second layer
  -m MINIMUM_SAMPLES, --minimum-samples MINIMUM_SAMPLES
                        Minimum number of samples in pixel for it to be
                        considered for DIFF [DEFAULT=250]
  -c COMPARE_METHOD, --compare-method COMPARE_METHOD
                        Compare Method to use (percentage,diff)
                        [DEFAULT='diff']
  --fill-value FILL_VALUE
                        If given, this value will be used to create BINs where
                        the second-layer does not overlap the first-
                        layer.[DEFAULT=None]
```


### Vector Layer Commands

[vector]
* list_vector_layers
* load_geojson_layer

> *WARNING*
>
> All GeoJSON features are expected to have an 'id' value defined in the feature's 'properties' attributes.
> The 'id' value is used for deduping purposes, if an 'id' is not given, some features may fail to display.
>

#### `load_geojson_layer`


```
Load GEOJSON text file to vector.GeoJsonLayer model

optional arguments:
  -h, --help            show this help message and exit
  -f FILEPATH, --filepath FILEPATH
                        Filepath to GEOJSON text file to load to
                        vector.GeoJsonLayer object.
  -o OPACITY, --opacity OPACITY
                        Layer Suggested Opacity ( 0 to 1) [DEFAULT=0.75]
```

#### `list_vector_layers`


List loaded vector.GeoJsonLayer items.

Example Usage::

```console
$ python3 manage.py list_vector_layers
```
