/**
 * Scale bar — uses identical MapLibre access pattern as the working zoom callback.
 * Also tracks sidebar collapsed state to reposition itself.
 */
(function () {
    var TARGET_PX = 80;
    var NICE_KM   = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000];
    var _map      = null;

    function getMap() {
        var gd = document.getElementById("map-graph");
        if (!gd) return null;
        if (!gd._fullLayout) {
            var inner = gd.querySelector(".js-plotly-plot");
            if (!inner || !inner._fullLayout) return null;
            gd = inner;
        }
        var layout = gd._fullLayout;
        var paths  = ["map._subplot.map", "map._subplot.mapbox", "mapbox._subplot.map", "mapbox._subplot.mapbox"];
        for (var i = 0; i < paths.length; i++) {
            try {
                var parts = paths[i].split(".");
                var obj   = layout;
                for (var j = 0; j < parts.length; j++) obj = obj[parts[j]];
                if (obj && typeof obj.getZoom === "function") return obj;
            } catch (_) {}
        }
        return null;
    }

    function updatePosition() {
        var bar     = document.getElementById("map-scale-bar");
        var sidebar = document.getElementById("app-sidebar");
        if (!bar || !sidebar) return;
        var collapsed = sidebar.classList.contains("collapsed");
        bar.style.left = collapsed ? "16px" : "";   // CSS var handles non-collapsed
    }

    function updateScaleBar() {
        var line  = document.getElementById("scale-bar-line");
        var label = document.getElementById("scale-bar-label");
        if (!line || !label) return;

        var map = getMap();
        if (!map) return;

        var zoom   = map.getZoom();
        var center = map.getCenter();
        var lat    = center ? center.lat : 0;

        // MapLibre GL JS uses 512px tiles, not 256
        var metersPerPx = (40075016.686 * Math.cos(lat * Math.PI / 180)) / (512 * Math.pow(2, zoom));
        var kmPerPx     = metersPerPx / 1000;
        var rawKm       = kmPerPx * TARGET_PX;

        // Pick the largest nice value that fits within TARGET_PX
        var niceKm = NICE_KM[0];
        for (var i = 0; i < NICE_KM.length; i++) {
            var candidate = NICE_KM[i];
            if (candidate / kmPerPx <= TARGET_PX) niceKm = candidate;
        }

        var barPx = Math.round(niceKm / kmPerPx);
        var text  = niceKm >= 1
            ? (niceKm % 1 === 0 ? niceKm + " km" : niceKm.toFixed(1) + " km")
            : (niceKm * 1000) + " m";

        line.style.width  = barPx + "px";
        label.textContent = text;
    }

    function attachToMap(map) {
        if (map === _map) return;
        _map = map;
        map.on("move",    updateScaleBar);
        map.on("zoom",    updateScaleBar);
        map.on("moveend", updateScaleBar);
        updateScaleBar();
    }

    // Poll for MapLibre instance + sidebar position
    setInterval(function () {
        var map = getMap();
        if (map) attachToMap(map);
        updatePosition();
    }, 800);
})();
