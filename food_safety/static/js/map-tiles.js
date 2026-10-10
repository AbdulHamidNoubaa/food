/**
 * Shared Leaflet basemap config — no API keys.
 * Primary: Esri World Street Map
 * Fallbacks: Esri Topo / Imagery, OSM Germany mirror
 */
(function (global) {
  var STREET = {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    options: {
      attribution: "Tiles &copy; Esri",
      maxZoom: 19,
    },
  };

  var SATELLITE = {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    options: {
      attribution: "Tiles &copy; Esri — Maxar, Earthstar Geographics",
      maxZoom: 19,
    },
  };

  var TOPO = {
    url: "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
    options: {
      attribution: "Tiles &copy; Esri — USGS, NOAA",
      maxZoom: 19,
    },
  };

  // Light-use OSM mirror (not the blocked tile.openstreetmap.org)
  var OSM_DE = {
    url: "https://tile.openstreetmap.de/{z}/{x}/{y}.png",
    options: {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    },
  };

  function streetLayer() {
    return L.tileLayer(STREET.url, STREET.options);
  }

  function satelliteLayer() {
    return L.tileLayer(SATELLITE.url, SATELLITE.options);
  }

  function topoLayer() {
    return L.tileLayer(TOPO.url, TOPO.options);
  }

  function osmDeLayer() {
    return L.tileLayer(OSM_DE.url, OSM_DE.options);
  }

  function addDefault(map) {
    var layer = streetLayer().addTo(map);
    setTimeout(function () {
      map.invalidateSize();
    }, 100);
    return layer;
  }

  function addWithSwitcher(map) {
    var street = streetLayer();
    var topo = topoLayer();
    var sat = satelliteLayer();
    var osm = osmDeLayer();
    street.addTo(map);
    L.control
      .layers(
        {
          "خريطة شوارع": street,
          "خريطة طبوغرافية": topo,
          "صور فضائية": sat,
          "OpenStreetMap": osm,
        },
        null,
        { position: "topright" }
      )
      .addTo(map);
    setTimeout(function () {
      map.invalidateSize();
    }, 100);
    return street;
  }

  global.FSMapTiles = {
    streetLayer: streetLayer,
    satelliteLayer: satelliteLayer,
    topoLayer: topoLayer,
    osmDeLayer: osmDeLayer,
    addDefault: addDefault,
    addWithSwitcher: addWithSwitcher,
  };
})(window);
