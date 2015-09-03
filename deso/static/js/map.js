/* Map UI Features */
/*
QueryString options:
    - bbox (RESERVED)
    - siteid (integer) [DEFAULT=None]
        - If given center will be set to the average of all siteids given.
    - display-labels (boolean) [DEFAULT=True]
        - Toggle lables display
    - display-legend (boolean) [DEFAULT=True]
        - Toggle legend display (if available)
*/
var map;
var baseMaps = {};
var overlayMaps = {};
var geojsonLayerLoadedFeatureIds = {};
var geojsonFeatureStyles = {};
var tileLayerOpacity = 1.0;//0.45;
var overlayTileLayerOpacity = 0.80;//0.45;
var collectionName = null;
var initialRefresh = true;
var vectorLayerCenterLatLng = undefined;

var urlQSParams;
(window.onpopstate = function () {
    var match,
        pl     = /\+/g,  // Regex for replacing addition symbol with a space
        search = /([^&=]+)=?([^&]*)/g,
        decode = function (s) { return decodeURIComponent(s.replace(pl, " ")); },
        query  = window.location.search.substring(1);

    urlQSParams = {};
    while (match = search.exec(query))
       urlQSParams[decode(match[1])] = decode(match[2]);
})();

function style(feature) {
    if (feature.properties !== undefined && feature.properties.style !== undefined){
        return feature.properties.style;
    }
    else if (feature.properties.type !== undefined && feature.properties.type === "cell"){
        var default_color = "#FB8072";
        if (feature.properties.pci !== null){ // temporary for initial pci debug
            default_color = "#00FFFF";
        }
        return {
            fillColor: default_color,
            weight: 1,
            opacity: 1,
            color: 'gray',
            fillOpacity: 0.7
        };
    }
    else{
        return {};

    }
}

function onEachFeature(feature, layer) {
    // does this feature have a property named popupContent?
    if (feature.properties !== undefined) {
        var popupContent = "";
        for (var key in feature.properties){

            if (key !== "style"){
                 popupContent += '<div class="popup-content">' + key + ": " + feature.properties[key] + "</div>";
            }
        }
        layer.bindPopup(popupContent);
    }
}

function getParameterByName(name) {
    name = name.replace(/[\[]/, "\\[").replace(/[\]]/, "\\]");
    var regex = new RegExp("[\\?&]" + name + "=([^&#]*)"),
        results = regex.exec(location.search);
    return results === null ? "" : decodeURIComponent(results[1].replace(/\+/g, " "));
}

function createMarker(feature, latlng){
    var marker = null;

    // marker should be a data point, show as a dot/circle
    if (feature.properties && feature.properties.type && feature.properties.type == "actual"){
        // To show act
        marker = new L.Circle(latlng, 5, {color: "#000000", // gray
                                          fillOpacity: 0.5,
                                          stroke: false});
    }
    else{
        var feature_color = feature.properties.style.color;
        marker = new L.Circle(latlng, 10, {color: feature_color,
                                           fillOpacity: 0.5,
                                           stroke: false}); // stroke defines if border of circle is displayed
    }

    // does this feature have a property named popupContent?
    if (feature.properties && feature.properties.popupContent) {
        marker.bindPopup(feature.properties.popupContent);
    }

    return marker;
}


function onOverlayAdd(layer){
    if (!map.hasLayer(overlayMaps[layer.name])){
        overlayMaps[layer.name].addTo(map);
    }
    if (overlayMaps[layer.name].legendControl !== undefined){
        overlayMaps[layer.name].legendControl.addTo(this);
    }

    overlayMaps[layer.name].togglestate = true;
    refreshGeoJSONLayers();
}

function onOverlayRemove(layer){
    overlayMaps[layer.name].togglestate = false;
    if (overlayMaps[layer.name].legendControl !== undefined){
        this.removeControl(overlayMaps[layer.name].legendControl);
    }
}


function initmap() {
    // set up the map
    map = new L.Map('map');

	// get collection
	var collection_id = getParameterByName("collection");
	if (collection_id){
        // TODO: Update to be more dynamic (don't use static IP here!)
        var layerCollectionUrl = 'http://10.143.165.241:8086/collections/collection/' + collection_id + '/';
	}
	else{
	    // default collection
	    // TODO: Update to be more dynamic (don't use static IP here!)
	    var layerCollectionUrl = 'http://10.143.165.241:8086/collections/collection/1/';
	}

	// retrieve layers from collection
    var xhrequest = new XMLHttpRequest();
    xhrequest.onreadystatechange =  function(){
        if (xhrequest.readyState == 4){
            if (xhrequest.status == 200){
                var collection =  JSON.parse(xhrequest.responseText);
                console.log(collection);
                baseMaps = {}; // clear existing layers
                overlayMaps = {};
                var vectorCenter = {};
                collectionName = collection.properties.name;
                for (var i=0;i<collection.layers.length;i++){
                    // Process the layer defined as below to the appropriate Leaflet Layer object
                    var layer = collection.layers[i];
                    var processedLayer = null;
                    if (layer.type == "TileLayer-base"){
                        var layerOpacity = tileLayerOpacity;
                        if (layer.opacity !== undefined && layer.opacity >= 0 && layer.opacity <= 1.0){
                            layerOpacity = layer.opacity;
                        }
                        var tileLayer = new L.TileLayer(layer.layerUrl, {tms: true,
                                                                         minZoom:layer.minZoom,
                                                                         maxZoom:layer.maxZoom,
                                                                         attribution:layer.attribution,
                                                                         opacity: layerOpacity});
                        baseMaps[layer.name] = tileLayer;
                        baseMaps[layer.name].addTo(map);
                        console.log("Adding basemap!");
                        console.log(layer.name);
                    }
                    else{
                        if(layer.type == "TileLayer-overlay"){
                            var layerOpacity = overlayTileLayerOpacity;
                            if (layer.opacity !== undefined && layer.opacity >= 0 && layer.opacity <= 1.0){
                                layerOpacity = layer.opacity;
                            }
                            var tileLayer = new L.TileLayer(layer.layerUrl, {tms: true,
                                                                             minZoom:layer.minZoom,
                                                                             maxZoom:layer.maxZoom,
                                                                             attribution:layer.attribution,
                                                                             opacity: overlayTileLayerOpacity});

                            overlayMaps[layer.name] = tileLayer;
                            console.log(layer.name);
                        }
                        else if(layer.type == "GeoJSON"){
                            var geojsonLayer = new L.GeoJSON(null, {pointToLayer: createMarker,
                                                                     style: style,
                                                                     onEachFeature: onEachFeature});
                            overlayMaps[layer.name] = geojsonLayer;
                            geojsonLayerLoadedFeatureIds[layer.name] = [];
                            console.log(layer.name);
                            if (vectorLayerCenterLatLng === undefined && layer.hasOwnProperty("centerlat") && layer.hasOwnProperty("centerlon")){
                                vectorLayerCenterLatLng = new L.LatLng(layer.centerlat, layer.centerlon);
                            }
                        }
                        // attempt to attach source json layer info to object
                        overlayMaps[layer.name].layerinfo = layer;
                        overlayMaps[layer.name].togglestate = true;
                        if (layer.legendUrl !== undefined){
                            updateLayerLegendControl(layer.name);
                        }
                        overlayMaps[layer.name].addTo(map);
                        console.log("Adding " + layer.type);
                    }
                }
                // Add Collection Name to map
                if (collectionName !== null){
                    // add info label
                    var info = L.control();
                    info.onAdd = function (map) {
                        this._div = L.DomUtil.create('div', 'info'); // create a div with a class "info"
                        this.update();
                        return this._div;
                    };
                    // method that we will use to update the control based on feature properties passed
                    info.update = function (props) {
                        this._div.innerHTML = '<h1>'+ collectionName + '</h1>';
                    };
                    info.addTo(map);
                }
                L.control.layers(baseMaps, overlayMaps).addTo(map);
                L.control.scale({imperial: false}).addTo(map); // should be imperial -> documentaion is "imerial"
                if (initialRefresh && vectorLayerCenterLatLng !== undefined){
                    map.setView(vectorLayerCenterLatLng, 14);
                    initialRefresh = false;
                } else {
                    // shinjuku (tokyo)
                    map.setView(new L.LatLng(35.691389, 139.69944), 14);
                }
                map.on('moveend', onMapMove); // refreshGeoJSONLayers on mapMove
                map.on('overlayadd', onOverlayAdd);
                map.on('overlayremove', onOverlayRemove);
                refreshGeoJSONLayers();
            }
        }
    };
    xhrequest.open('GET', layerCollectionUrl, true);
    xhrequest.send(null);
}

function updateLayerLegendControl(overlayLayerName){
    var xhrequest = new XMLHttpRequest();
    xhrequest.onreadystatechange = function(){
        if (xhrequest.readyState == 4){
            if (xhrequest.status == 200){
                var data =  xhrequest.responseText;
                var legendControl = L.control({position: 'bottomright'});
                legendControl.onAdd = function(map){
                    var div = L.DomUtil.create('div', 'info legend');
                    div.innerHTML += data;
                    return div;
                }
                overlayMaps[overlayLayerName].legendControl = legendControl;
            }
        }
    }
    console.log("fetching legendHtml for: " + overlayLayerName);
    var url = overlayMaps[overlayLayerName].layerinfo.legendUrl;
    xhrequest.open('GET', url, true);
    xhrequest.send(null);

}

function refreshGeoJSONLayer(name){
    var loadedFeatureIds =  geojsonLayerLoadedFeatureIds[name];
    if (overlayMaps[name].togglestate === true && overlayMaps[name].layerinfo.type == "GeoJSON"){
        console.log("refreshGeoJSONLayer() processing 'overlayMaps[" + name + "]'");
        var xhrequest = new XMLHttpRequest();
        xhrequest._layername = name;
        xhrequest.onreadystatechange = function(){
            if (xhrequest.readyState == 4){
                if (xhrequest.status == 200){
                    var responseLayer = overlayMaps[xhrequest._layername];
                    var layerFeatures =  JSON.parse(xhrequest.responseText);
                    if (layerFeatures.type !== undefined && layerFeatures.type == "FeatureCollection"){
                        layerFeatures = layerFeatures.features;
                        console.log("len" + layerFeatures.length);
                    }
                    else if (layerFeatures.length == undefined){
                        layerFeatures = [layerFeatures];
                    }
                    var featuresAdded = false;
                    for(var j=0;j<layerFeatures.length;j++){
                        // check that feature isn't already loaded to map
                        if (layerFeatures[j]){
                            // for de-dupping
                            var featureId = layerFeatures[j].properties.id || layerFeatures[j].properties.ID;
                            if (loadedFeatureIds.indexOf(featureId) == -1){
                                featuresAdded = true;
                                responseLayer.addData(layerFeatures[j]);
                                loadedFeatureIds.push(featureId);
                                // attempt to add siteid/nodeid label
                                if (layerFeatures[j].properties.label_lon !== undefined && layerFeatures[j].properties.label_lat !== undefined &&  layerFeatures[j].properties.label_text !== undefined){
                                    console.log("Attempt to create Label for " + layerFeatures[j].properties.label_text);
                                    L.marker([layerFeatures[j].properties.label_lat, layerFeatures[j].properties.label_lon], {
                                                                                        icon: L.divIcon({
                                                                                                           iconSize: [30, 0],
                                                                                                           html: layerFeatures[j].properties.label_text
                                                                                                          })
                                                                                        }).addTo(responseLayer);
                                }
                            }
                        }
                    }
                    console.log("New Data added (" + xhrequest._layername + "): " + featuresAdded);
                }
            }
        };
        var url = overlayMaps[name].layerinfo.layerUrl + '?bbox=' + map.getBounds().toBBoxString();
        console.log("fetching data from: " + overlayMaps[name].layerinfo.layerUrl);
        xhrequest.open('GET', url, true);
        xhrequest.send(null);
    }
}

function refreshGeoJSONLayers(){
    for (var name in overlayMaps){
        // due to the async nature of the XMLHTTPRequest requests are isolated in a separate function
        refreshGeoJSONLayer(name);
    }
}

function onMapMove(e) {
    refreshGeoJSONLayers();
}
