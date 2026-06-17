/**
 * Tangkap klik MapLibre GL → simpan ke window._mapClickData.
 * Polling dilakukan oleh clientside callback Dash (namespace mapClick.pollClick).
 */
(function () {
    window._mapClickData = null;

    function findPlotDiv() {
        var wrapper = document.getElementById("map-graph");
        if (!wrapper) return null;
        if (wrapper._fullLayout) return wrapper;
        return wrapper.querySelector(".js-plotly-plot");
    }

    function getMapInstance() {
        var gd = findPlotDiv();
        if (!gd || !gd._fullLayout) return null;
        var layout = gd._fullLayout;

        var paths = [
            "map._subplot.map",
            "map._subplot.mapbox",
            "mapbox._subplot.map",
            "mapbox._subplot.mapbox",
            "map._subplot",
            "mapbox._subplot",
        ];
        for (var i = 0; i < paths.length; i++) {
            try {
                var parts = paths[i].split(".");
                var obj = layout;
                for (var j = 0; j < parts.length; j++) obj = obj[parts[j]];
                if (obj && typeof obj.on === "function") return obj;
            } catch (_) {}
        }
        return null;
    }

    function attachClickHandler(map) {
        if (map._dashClickAttached) return;
        map.on("click", function (e) {
            window._mapClickData = {
                lat: e.lngLat.lat,
                lon: e.lngLat.lng,
                _ts: Date.now(),
            };
        });
        map._dashClickAttached = true;
    }

    var lastMap = null;
    window._mapClickPollInterval = setInterval(function () {
        var map = getMapInstance();
        if (map && map !== lastMap) {
            lastMap = map;
            map._dashClickAttached = false;
            attachClickHandler(map);
        }
    }, 1000);

    /* Urutan layer key sesuai config — dipakai untuk mapping index ke MapLibre layer */
    var LAYER_KEYS = ["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"];

    /* Register namespace untuk clientside_callback Dash */
    if (!window.dash_clientside) window.dash_clientside = {};
    window.dash_clientside.mapClick = {
        pollClick: function (_n) {
            var data = window._mapClickData;
            if (data) {
                window._mapClickData = null;
                return data;
            }
            return window.dash_clientside.no_update;
        },

        /* Update posisi marker pin via Plotly.restyle — hindari full figure rebuild. */
        updatePin: function (pinned) {
            var gd = findPlotDiv();
            if (!gd || !gd._fullLayout || !gd.data) return window.dash_clientside.no_update;

            function traceIdx(uid) {
                return gd.data.findIndex(function (t) { return t.uid === uid; });
            }
            var haloIdx   = traceIdx("pin-halo");
            var borderIdx = traceIdx("pin-border");
            var mainIdx   = traceIdx("pin-main");
            if (haloIdx < 0 || borderIdx < 0 || mainIdx < 0) return window.dash_clientside.no_update;

            var hasPin = !!(pinned && !pinned.outside && pinned.lat != null);
            var lats = hasPin ? [pinned.lat] : [];
            var lons = hasPin ? [pinned.lon] : [];
            var provinsi = (pinned && pinned.provinsi) || "";
            var pinText = hasPin ? [provinsi ? "  " + provinsi : "  Pin"] : [];
            var pinHover = hasPin
                ? "<b>📍 Pin Aktif</b><br>Lat: " + pinned.lat.toFixed(4)
                  + "°<br>Lon: " + pinned.lon.toFixed(4)
                  + (provinsi ? "<br>" + provinsi : "")
                  + "<br><i>Klik lokasi lain untuk memindahkan</i><extra></extra>"
                : "<extra></extra>";

            try {
                Plotly.restyle(gd, { lat: [lats], lon: [lons] }, [haloIdx]);
                Plotly.restyle(gd, { lat: [lats], lon: [lons] }, [borderIdx]);
                Plotly.restyle(gd, {
                    lat: [lats], lon: [lons],
                    text: [pinText], hovertemplate: pinHover,
                }, [mainIdx]);
            } catch (e) {
                console.warn("[pin] restyle failed:", e);
            }
            return window.dash_clientside.no_update;
        },

        /* Update opacity layer image overlay langsung via MapLibre setPaintProperty.
         * Menerima array opacities dari store, apply ke raster layers sesuai urutan Plotly. */
        updateLayerOpacity: function(opacityStore) {
            if (!opacityStore) return window.dash_clientside.no_update;

            function applyOpacities() {
                var map = getMapInstance();
                if (!map) return false;

                var style = map.getStyle();
                if (!style || !style.layers) return false;

                var rasterLayers = style.layers.filter(function(l) {
                    return l.type === "raster";
                });
                if (rasterLayers.length === 0) return false;

                var opacities = opacityStore.opacities || [];
                var t0 = performance.now();
                for (var i = 0; i < rasterLayers.length && i < opacities.length; i++) {
                    try {
                        map.setPaintProperty(rasterLayers[i].id, "raster-opacity", opacities[i]);
                    } catch(e) {
                        console.warn("[opacity] setPaintProperty failed:", e);
                    }
                }
                var elapsed = parseFloat((performance.now() - t0).toFixed(1));
                fetch("/log-timing", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        label: "opacity_render",
                        elapsed_ms: elapsed,
                        info: "layers=" + rasterLayers.length + " | opacities=" + JSON.stringify(opacities)
                    })
                }).catch(function() {});
                return true;
            }

            if (!applyOpacities()) {
                setTimeout(applyOpacities, 150);
            }
            return window.dash_clientside.no_update;
        },
    };
})();
