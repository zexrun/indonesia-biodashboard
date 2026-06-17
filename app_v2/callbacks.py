"""Dash callbacks for map, legend, pixel info, and pin interactions."""

import time
import numpy as np
import plotly.graph_objects as go
import dash
from dash import html, dcc, Input, Output, State, ctx, ClientsideFunction, MATCH, ALL
from dash.exceptions import PreventUpdate

from .app_instance import app
from .config import LAYER_META, GADM_LEVELS
from .cache import (
    LAYER_CACHE, GADM_CACHE, GADM_GDF, GADM_GEOJSON,
    sample_pixel_text, point_to_admin, get_province_view,
    get_masked_png, get_province_mask, CODE_MAPPING, search_location,
    LOCATION_LIST,
)
from .utils_mask import get_province_geojson, apply_mask_to_arr
from .raster import arr_to_rgba_png_b64
from .legend import make_legend_figure, make_empty_legend
from .ai_search import query_ai
from .perf_timing import log_timing


# Clientside: zoom in/out buttons
app.clientside_callback(
    """
    function(nIn, nOut) {
        var triggered = dash_clientside.callback_context.triggered;
        if (!triggered || !triggered.length) return window.dash_clientside.no_update;
        var id = triggered[0].prop_id.split(".")[0];
        var delta = (id === "zoom-in-btn") ? 1 : -1;

        var gd = document.getElementById("map-graph");
        if (!gd) return window.dash_clientside.no_update;
        if (!gd._fullLayout) gd = gd.querySelector(".js-plotly-plot");
        if (!gd || !gd._fullLayout) return window.dash_clientside.no_update;

        var layout = gd._fullLayout;
        var paths = ["map._subplot.map", "map._subplot.mapbox", "mapbox._subplot.map", "mapbox._subplot.mapbox"];
        var map = null;
        for (var i = 0; i < paths.length; i++) {
            try {
                var parts = paths[i].split(".");
                var obj = layout;
                for (var j = 0; j < parts.length; j++) obj = obj[parts[j]];
                if (obj && typeof obj.getZoom === "function") { map = obj; break; }
            } catch(_) {}
        }
        if (!map) return window.dash_clientside.no_update;
        map.easeTo({ zoom: map.getZoom() + delta, duration: 250 });
        return window.dash_clientside.no_update;
    }
    """,
    Output("zoom-dummy", "children"),
    Input("zoom-in-btn",  "n_clicks"),
    Input("zoom-out-btn", "n_clicks"),
    prevent_initial_call=True,
)

# Clientside: polling MapLibre click → dcc.Store
app.clientside_callback(
    ClientsideFunction(namespace="mapClick", function_name="pollClick"),
    Output("map-click-coords", "data"),
    Input("click-poll", "n_intervals"),
)

# Clientside: sidebar toggle (close btn) + open btn — overlay sidebar
app.clientside_callback(
    """
    function(nClose, nOpen, isOpen) {
        var triggered = dash_clientside.callback_context.triggered;
        if (!triggered || !triggered.length) return window.dash_clientside.no_update;
        var id = triggered[0].prop_id.split(".")[0];
        var next = (id === "sidebar-open-btn") ? true : !isOpen;
        var el = document.getElementById("app-sidebar");
        if (el) el.classList.toggle("collapsed", !next);
        var openBtn = document.getElementById("sidebar-open-btn");
        if (openBtn) openBtn.style.display = next ? "none" : "flex";
        return next;
    }
    """,
    Output("sidebar-state", "data"),
    Input("sidebar-toggle-btn", "n_clicks"),
    Input("sidebar-open-btn",   "n_clicks"),
    State("sidebar-state",      "data"),
    prevent_initial_call=True,
)

# Clientside: poll window._layerDragOrder set by drag JS → layer-order store
app.clientside_callback(
    """
    function(n) {
        var order = window._layerDragOrder;
        if (!order) return window.dash_clientside.no_update;
        window._layerDragOrder = null;
        return order;
    }
    """,
    Output("layer-order", "data"),
    Input("drag-order-poll", "n_intervals"),
    prevent_initial_call=True,
)



@app.callback(
    Output("layer-slot-ranked",         "style"),
    Output("layer-slot-mollweide",      "style"),
    Output("layer-slot-habitat",        "style"),
    Output("layer-slot-ias_ujungkulon", "style"),
    Output("layer-slot-ias_baluran",    "style"),
    Input("layer-order", "data"),
)
def render_layer_cards(order):
    """Update CSS order of layer slots to reflect drag order."""
    if not order:
        order = ["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]
    positions = {k: i for i, k in enumerate(order)}
    return (
        {"order": positions.get("ranked",         0)},
        {"order": positions.get("mollweide",      1)},
        {"order": positions.get("habitat",        2)},
        {"order": positions.get("ias_ujungkulon", 3)},
        {"order": positions.get("ias_baluran",    4)},
    )


@app.callback(
    Output("layer-card-ranked",         "className"),
    Output("layer-card-mollweide",      "className"),
    Output("layer-card-habitat",        "className"),
    Output("layer-card-ias_ujungkulon", "className"),
    Output("layer-card-ias_baluran",    "className"),
    Input("layer-toggle-ranked",         "value"),
    Input("layer-toggle-mollweide",      "value"),
    Input("layer-toggle-habitat",        "value"),
    Input("layer-toggle-ias_ujungkulon", "value"),
    Input("layer-toggle-ias_baluran",    "value"),
)
def update_layer_card_states(toggle_ranked, toggle_mollweide, toggle_habitat,
                              toggle_ias_ujungkulon, toggle_ias_baluran):
    def card_cls(v):
        return "widget-card" if (v and "show" in v) else "widget-card layer-is-off"
    return (
        card_cls(toggle_ranked),
        card_cls(toggle_mollweide),
        card_cls(toggle_habitat),
        card_cls(toggle_ias_ujungkulon),
        card_cls(toggle_ias_baluran),
    )


@app.callback(
    Output({"type": "widget-collapse", "index": MATCH}, "is_open"),
    Output({"type": "widget-header-btn", "index": MATCH}, "className"),
    Input({"type": "widget-header-btn", "index": MATCH}, "n_clicks"),
    State({"type": "widget-collapse",   "index": MATCH}, "is_open"),
    prevent_initial_call=True,
)
def toggle_widget_card(header_clicks, is_open):
    """Toggle widget card open/closed on header click."""
    new_open = not is_open
    header_cls = "widget-card-header" if new_open else "widget-card-header is-closed"
    return new_open, header_cls


# Abbreviated labels for the segmented pill selector (space-constrained)
_LAYER_SHORT = {
    "ranked":         "Ranked",
    "mollweide":      "Rich",
    "habitat":        "Hab.",
    "ias_ujungkulon": "TNUK",
    "ias_baluran":    "TNB",
}


@app.callback(
    Output("legend-selector", "children"),
    Input("layer-toggle-ranked",         "value"),
    Input("layer-toggle-mollweide",      "value"),
    Input("layer-toggle-habitat",        "value"),
    Input("layer-toggle-ias_ujungkulon", "value"),
    Input("layer-toggle-ias_baluran",    "value"),
    Input("layer-order",                 "data"),
    Input("selected-legend-layer",       "data"),
)
def update_legend_selector(toggle_ranked, toggle_mollweide, toggle_habitat,
                            toggle_ias_ujungkulon, toggle_ias_baluran, layer_order, selected):
    order = layer_order if layer_order else ["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]
    toggles = {
        "ranked":         toggle_ranked,
        "mollweide":      toggle_mollweide,
        "habitat":        toggle_habitat,
        "ias_ujungkulon": toggle_ias_ujungkulon,
        "ias_baluran":    toggle_ias_baluran,
    }
    visible_keys = [
        k for k in order
        if toggles.get(k) and "show" in (toggles.get(k) or [])
    ]

    if not visible_keys:
        return []

    # Auto-select first visible if selected is no longer visible
    active = selected if selected in visible_keys else visible_keys[0]

    pills = []
    for key in visible_keys:
        cls = "seg-pill active" if key == active else "seg-pill"
        pills.append(
            html.Span(
                _LAYER_SHORT[key],
                id={"type": "legend-pill", "key": key},
                className=cls,
                n_clicks=0,
            )
        )
    return pills


@app.callback(
    Output("selected-legend-layer", "data", allow_duplicate=True),
    Input({"type": "legend-pill", "key": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def handle_legend_pill_click(n_clicks_list):
    triggered = ctx.triggered_id
    # triggered is None on spurious fires (e.g. dynamic component injection)
    if not triggered or not isinstance(triggered, dict):
        return dash.no_update
    return triggered["key"]


@app.callback(
    Output("habitat-active-classes", "value"),
    Input("habitat-classes-all-btn", "n_clicks"),
    prevent_initial_call=True,
)
def habitat_select_all(_):
    return list(LAYER_META["habitat"]["categories"].keys())


@app.callback(
    Output("search-result", "data"),
    Output("search-status", "children"),
    Input("location-search-input", "value"),
    prevent_initial_call=True,
)
def handle_location_search(query):
    """Search location in local GADM or remote Nominatim API."""
    if not query or len(query.strip()) < 2:
        return None, ""
    result = search_location(query)
    if result:
        return result, f"-> {result['label']}"
    return None, "Lokasi tidak ditemukan"


@app.callback(
    Output("map-graph",             "figure"),
    Output("legend-content",        "children"),
    Output("selected-legend-layer", "data"),
    # Per-layer toggles
    Input("layer-toggle-ranked",         "value"),
    Input("layer-toggle-mollweide",      "value"),
    Input("layer-toggle-habitat",        "value"),
    Input("layer-toggle-ias_ujungkulon", "value"),
    Input("layer-toggle-ias_baluran",    "value"),
    # Per-layer opacities
    Input("layer-opacity-ranked",         "value"),
    Input("layer-opacity-mollweide",      "value"),
    Input("layer-opacity-habitat",        "value"),
    Input("layer-opacity-ias_ujungkulon", "value"),
    Input("layer-opacity-ias_baluran",    "value"),
    # Per-layer range filters (continuous layers only)
    Input("layer-range-ranked",    "value"),
    Input("layer-range-mollweide", "value"),
    # Map controls
    Input("basemap-select",  "value"),
    Input("layer-toggle",    "value"),
    Input("province-select", "value"),
    Input("search-result",   "data"),
    Input("selected-legend-layer",  "data"),
    Input("layer-order",            "data"),
    Input("habitat-active-classes",           "value"),
    Input("ias-active-classes-ias_ujungkulon","value"),
    Input("ias-active-classes-ias_baluran",   "value"),
    Input("ias-focus-btn-ias_ujungkulon",     "n_clicks"),
    Input("ias-focus-btn-ias_baluran",        "n_clicks"),
    State("pinned-data",                      "data"),
    State("map-graph",                        "figure"),
    prevent_initial_call=True,
)
def update_map(
    toggle_ranked, toggle_mollweide, toggle_habitat,
    toggle_ias_ujungkulon, toggle_ias_baluran,
    opacity_ranked, opacity_mollweide, opacity_habitat,
    opacity_ias_ujungkulon, opacity_ias_baluran,
    range_ranked, range_mollweide,
    basemap, layer_toggle_global,
    province, search_result, selected_legend_layer, layer_order,
    habitat_active_classes,
    ias_active_classes_ujungkulon, ias_active_classes_baluran,
    focus_ujungkulon, focus_baluran,
    pinned, current_figure,
):
    """Rebuild map figure with all visible layers as stacked image overlays."""
    _t0 = time.time()
    _no = dash.no_update

    # Opacity ditangani sepenuhnya oleh clientside callback via MapLibre — skip full rebuild
    _opacity_ids = {
        "layer-opacity-ranked", "layer-opacity-mollweide", "layer-opacity-habitat",
        "layer-opacity-ias_ujungkulon", "layer-opacity-ias_baluran",
    }
    if ctx.triggered_id in _opacity_ids:
        return _no, _no, _no

    global_visible = bool(layer_toggle_global and "show" in layer_toggle_global)

    toggles = {
        "ranked":         toggle_ranked,
        "mollweide":      toggle_mollweide,
        "habitat":        toggle_habitat,
        "ias_ujungkulon": toggle_ias_ujungkulon,
        "ias_baluran":    toggle_ias_baluran,
    }
    opacities = {
        "ranked":         opacity_ranked         if opacity_ranked         is not None else 1.0,
        "mollweide":      opacity_mollweide       if opacity_mollweide      is not None else 1.0,
        "habitat":        opacity_habitat         if opacity_habitat        is not None else 1.0,
        "ias_ujungkulon": opacity_ias_ujungkulon  if opacity_ias_ujungkulon is not None else 1.0,
        "ias_baluran":    opacity_ias_baluran     if opacity_ias_baluran    is not None else 1.0,
    }
    ranges = {
        "ranked":    range_ranked,
        "mollweide": range_mollweide,
    }
    ias_active_classes = {
        "ias_ujungkulon": ias_active_classes_ujungkulon,
        "ias_baluran":    ias_active_classes_baluran,
    }

    _order = layer_order if layer_order else ["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]
    visible_keys = [
        k for k in _order
        if global_visible and toggles.get(k) and "show" in (toggles.get(k) or [])
    ]


    province_active = bool(province and province != "__all__")

    # Use first visible layer as primary for hover + legend + center
    primary_key   = visible_keys[0] if visible_keys else "ranked"
    primary_meta  = LAYER_META[primary_key]
    primary_cache = LAYER_CACHE[primary_key]
    lon_min, lat_min, lon_max, lat_max = primary_cache["bounds"]

    # ── Deteksi trigger ───────────────────────────────────────────
    _triggered = ctx.triggered_id
    _basemap_changed = (_triggered == "basemap-select")

    # ── Deteksi trigger IAS (toggle ON atau tombol Fokus) ─────────
    _ias_focus_key = None
    if _triggered == "ias-focus-btn-ias_ujungkulon":
        _ias_focus_key = "ias_ujungkulon"
    elif _triggered == "ias-focus-btn-ias_baluran":
        _ias_focus_key = "ias_baluran"
    elif _triggered == "layer-toggle-ias_ujungkulon" and toggle_ias_ujungkulon and "show" in toggle_ias_ujungkulon:
        _ias_focus_key = "ias_ujungkulon"
    elif _triggered == "layer-toggle-ias_baluran" and toggle_ias_baluran and "show" in toggle_ias_baluran:
        _ias_focus_key = "ias_baluran"

    # ── Center / zoom ──────────────────────────────────────────────
    # Helper: baca posisi peta saat ini dari figure state (saat basemap berubah)
    def _current_map_pos():
        try:
            m = (current_figure or {}).get("layout", {}).get("map", {})
            c = m.get("center", {})
            return c.get("lat"), c.get("lon"), m.get("zoom")
        except Exception:
            return None, None, None

    if _ias_focus_key and _ias_focus_key in LAYER_CACHE:
        _fc = LAYER_CACHE[_ias_focus_key]
        _flon_min, _flat_min, _flon_max, _flat_max = _fc["bounds"]
        center_lat = (_flat_min + _flat_max) / 2
        center_lon = (_flon_min + _flon_max) / 2
        _span = max(_flon_max - _flon_min, _flat_max - _flat_min)
        import math as _math
        map_zoom = max(6.0, min(_math.log2(360 / _span) + 0.3, 13.0))
    elif _basemap_changed:
        # Pertahankan posisi peta saat basemap berubah atau opacity diubah
        _cur_lat, _cur_lon, _cur_zoom = _current_map_pos()
        center_lat = _cur_lat if _cur_lat is not None else (lat_min + lat_max) / 2
        center_lon = _cur_lon if _cur_lon is not None else (lon_min + lon_max) / 2
        map_zoom   = _cur_zoom if _cur_zoom is not None else 3.8
    elif search_result and search_result.get("lat") is not None:
        center_lat = search_result["lat"]
        center_lon = search_result["lon"]
        map_zoom   = search_result["zoom"]
    elif province_active:
        p_lat, p_lon, p_zoom = get_province_view(province)
        center_lat = p_lat if p_lat is not None else (lat_min + lat_max) / 2
        center_lon = p_lon if p_lon is not None else (lon_min + lon_max) / 2
        map_zoom   = p_zoom if p_zoom is not None else 3.8
    else:
        center_lon = (lon_min + lon_max) / 2
        center_lat = (lat_min + lat_max) / 2
        map_zoom   = 3.8

    # ── Hover scatter (primary layer) ─────────────────────────────
    arr  = primary_cache["arr"]
    h, w = arr.shape
    sr   = max(1, h // 20)
    sc   = max(1, w // 40)
    rows = np.arange(0, h, sr)
    cols = np.arange(0, w, sc)
    lats_pts = lat_max - (rows + 0.5) / h * (lat_max - lat_min)
    lons_pts = lon_min + (cols + 0.5) / w * (lon_max - lon_min)
    lon_mesh, lat_mesh = np.meshgrid(lons_pts, lats_pts)
    val_mesh = arr[np.ix_(rows, cols)]

    if primary_meta["discrete"]:
        cats = primary_meta["categories"]
        def val_label(v):
            int_v    = int(v)
            mapped_v = CODE_MAPPING.get(int_v, int_v) if primary_key == "habitat" else int_v
            return cats.get(mapped_v, ("Unknown",))[0]
        hover_z = [[f"Nilai: {int(v)}<br>Kelas: {val_label(v)}" for v in row]
                   for row in val_mesh]
    else:
        hover_z = [[f"Nilai: {v:.1f}" for v in row] for row in val_mesh]

    # ── Pin data ───────────────────────────────────────────────────
    has_pin  = bool(pinned and not pinned.get("outside") and pinned.get("lat") is not None)
    p_lats   = [pinned["lat"]] if has_pin else []
    p_lons   = [pinned["lon"]] if has_pin else []
    provinsi = pinned.get("provinsi", "") if has_pin else ""
    pin_text = [f"  {provinsi}" if provinsi else "  Pin"] if has_pin else []
    pin_hover = (
        "<b>📍 Pin Aktif</b><br>"
        f"Lat: {pinned['lat']:.4f}°<br>Lon: {pinned['lon']:.4f}°<br>"
        "<i>Klik lokasi lain untuk memindahkan</i><extra></extra>"
    ) if has_pin else "<extra></extra>"

    # ── Build figure ───────────────────────────────────────────────
    fig = go.Figure()

    fig.add_trace(go.Scattermap(
        lon=lon_mesh.flatten().tolist(),
        lat=lat_mesh.flatten().tolist(),
        mode="markers",
        marker=dict(size=1, opacity=0, color="rgba(0,0,0,0)"),
        text=[t for row in hover_z for t in row],
        hovertemplate="%{text}<br>Lat: %{lat:.4f}°<br>Lon: %{lon:.4f}°<extra></extra>",
        name="",
    ))

    # Pin marker: halo (glow) + border (putih) + inti (magenta) + label provinsi
    fig.add_trace(go.Scattermap(
        lat=p_lats, lon=p_lons, mode="markers",
        marker=dict(size=52, color="rgba(233,30,140,0.18)"),
        hoverinfo="skip", showlegend=False, uid="pin-halo",
    ))
    fig.add_trace(go.Scattermap(
        lat=p_lats, lon=p_lons, mode="markers",
        marker=dict(size=34, color="white"),
        hoverinfo="skip", showlegend=False, uid="pin-border",
    ))
    fig.add_trace(go.Scattermap(
        lat=p_lats, lon=p_lons,
        mode="markers+text",
        marker=dict(size=22, color="#e91e8c", symbol="circle"),
        text=pin_text, textposition="middle right",
        textfont=dict(size=13, color="#ffffff",
                      family="'Segoe UI', Arial, sans-serif"),
        hovertemplate=pin_hover, name="Pin",
        showlegend=False, uid="pin-main",
    ))

    # ── Image overlays (one per visible layer, bottom→top order) ──
    map_layers = []
    for k in reversed(visible_keys):
        meta  = LAYER_META[k]
        cache = LAYER_CACHE[k]

        if province_active:
            masked_png = get_masked_png(province, k)
            base_img   = masked_png if masked_png else cache["img_b64"]
            # Re-render with class filter if habitat or IAS
            if k == "habitat" and habitat_active_classes is not None:
                all_keys = list(LAYER_META["habitat"]["categories"].keys())
                if set(habitat_active_classes) != set(all_keys):
                    arr_src = cache["arr"]
                    if masked_png:
                        pmask = get_province_mask(province, k)
                        arr_src = apply_mask_to_arr(arr_src, pmask, cache["nodata"]) if pmask is not None else arr_src
                    img_b64 = arr_to_rgba_png_b64(
                        arr_src, meta, cache["nodata"],
                        layer_key=k, active_classes=habitat_active_classes,
                    )
                else:
                    img_b64 = base_img
            elif k in ias_active_classes and ias_active_classes[k] is not None:
                all_keys = list(meta["categories"].keys())
                if set(ias_active_classes[k]) != set(all_keys):
                    img_b64 = arr_to_rgba_png_b64(
                        cache["arr"], meta, cache["nodata"],
                        layer_key=k, active_classes=ias_active_classes[k],
                    )
                else:
                    img_b64 = base_img
            else:
                img_b64 = base_img
        elif not meta["discrete"] and ranges.get(k):
            rng     = ranges[k]
            meta_r  = dict(meta, vmin=rng[0], vmax=rng[1])
            img_b64 = arr_to_rgba_png_b64(
                cache["arr"], meta_r, cache["nodata"],
                layer_key=k, value_range=rng,
            )
        elif k == "habitat" and habitat_active_classes is not None:
            all_keys = list(LAYER_META["habitat"]["categories"].keys())
            if set(habitat_active_classes) != set(all_keys):
                img_b64 = arr_to_rgba_png_b64(
                    cache["arr"], meta, cache["nodata"],
                    layer_key=k, active_classes=habitat_active_classes,
                )
            else:
                img_b64 = cache["img_b64"]
        elif k in ias_active_classes and ias_active_classes[k] is not None:
            all_keys = list(meta["categories"].keys())
            if set(ias_active_classes[k]) != set(all_keys):
                img_b64 = arr_to_rgba_png_b64(
                    cache["arr"], meta, cache["nodata"],
                    layer_key=k, active_classes=ias_active_classes[k],
                )
            else:
                img_b64 = cache["img_b64"]
        else:
            img_b64 = cache["img_b64"]

        c_lon_min, c_lat_min, c_lon_max, c_lat_max = cache["bounds"]
        map_layers.append(dict(
            sourcetype="image",
            source=img_b64,
            coordinates=[
                [c_lon_min, c_lat_max],
                [c_lon_max, c_lat_max],
                [c_lon_max, c_lat_min],
                [c_lon_min, c_lat_min],
            ],
            opacity=opacities[k],
        ))

    # Province GeoJSON highlight
    if province_active and 1 in GADM_GDF:
        prov_geojson = get_province_geojson(province, GADM_GDF[1])
        if prov_geojson:
            map_layers.append(dict(
                sourcetype="geojson",
                source=prov_geojson,
                type="line",
                color="#FF6B35",
                opacity=0.9,
                line={"width": 2.5},
            ))

    _hab_cls_key = "-".join(str(c) for c in sorted(habitat_active_classes or []))
    _ias_uk_key  = "-".join(str(c) for c in sorted(ias_active_classes.get("ias_ujungkulon") or []))
    _ias_bal_key = "-".join(str(c) for c in sorted(ias_active_classes.get("ias_baluran") or []))
    _uirev_base = (
        f"{','.join(visible_keys)}-{basemap}"
        f"-{province}"
        f"-focus{focus_ujungkulon or 0}-{focus_baluran or 0}"
        f"-hab{_hab_cls_key}-uk{_ias_uk_key}-bal{_ias_bal_key}"
    )
    if _ias_focus_key:
        _uirevision = f"focus-{_ias_focus_key}-{focus_ujungkulon or 0}-{focus_baluran or 0}"
    elif _basemap_changed:
        _uirevision = f"basemap-{basemap}-{time.time()}"
    else:
        _uirevision = _uirev_base

    fig.update_layout(
        map=dict(
            style=basemap,
            center=dict(lat=center_lat, lon=center_lon),
            zoom=map_zoom,
            layers=map_layers,
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        hovermode=False,
        uirevision=_uirevision,
    )

    # ── Legend + description (auto-select if selected layer is not visible) ──
    if visible_keys:
        # Check if selected layer is still visible; if not, use first visible
        if selected_legend_layer not in visible_keys:
            primary_key = visible_keys[0]
            updated_selected = visible_keys[0]
        else:
            primary_key = selected_legend_layer
            updated_selected = selected_legend_layer
    else:
        primary_key = "ranked"
        updated_selected = "ranked"

    primary_meta = LAYER_META[primary_key]

    # Generate legend
    if visible_keys:
        legend_fig, legend_h = make_legend_figure(primary_meta)
        layer_desc = primary_meta["description"]
    else:
        legend_fig, legend_h = make_empty_legend()
        layer_desc = ""

    # Build legend content (figure + description)
    legend_content = html.Div(
        className="legend-content-inner",
        children=[
            dcc.Graph(
                figure=legend_fig,
                config={"displayModeBar": False, "staticPlot": True},
                className="legend-graph",
                style={"height": legend_h},
            ) if visible_keys else html.Div(),
            html.Div(
                layer_desc,
                id="layer-desc",
                style={
                    "fontSize": "11px",
                    "color": "#939393",
                    "fontStyle": "italic",
                    "marginTop": "6px",
                    "fontFamily": "Inter, sans-serif",
                    "lineHeight": "1.5",
                },
            ),
        ],
    )

    _triggered = ctx.triggered_id
    _label = {
        "layer-toggle-ranked":          "toggle_layer_ranked",
        "layer-toggle-mollweide":       "toggle_layer_mollweide",
        "layer-toggle-habitat":         "toggle_layer_habitat",
        "layer-toggle-ias_ujungkulon":  "toggle_layer_ias_tnuk",
        "layer-toggle-ias_baluran":     "toggle_layer_ias_tnb",
        "layer-range-ranked":           "filter_range_ranked",
        "layer-range-mollweide":        "filter_range_mollweide",
        "province-select":              "filter_by_province",
        "habitat-active-classes":       "filter_iucn_classes",
        "ias-active-classes-ias_ujungkulon": "filter_ias_classes_tnuk",
        "ias-active-classes-ias_baluran":    "filter_ias_classes_tnb",
    }.get(str(_triggered), f"update_map_{_triggered}")
    log_timing(_label, _t0, time.time(), {"triggered": str(_triggered), "visible": visible_keys})

    return fig, legend_content, updated_selected


# Clientside: update posisi pin via Plotly.restyle langsung di browser.
# Bypass Dash Patch pipeline (yang race dengan Store mount) dan hindari full figure rebuild.
app.clientside_callback(
    ClientsideFunction(namespace="mapClick", function_name="updatePin"),
    Output("pin-dummy", "children"),
    Input("pinned-data", "data"),
    prevent_initial_call=True,
)

# Clientside: update opacity layer langsung ke MapLibre — bypass Plotly figure rebuild.
app.clientside_callback(
    ClientsideFunction(namespace="mapClick", function_name="updateLayerOpacity"),
    Output("opacity-dummy", "children"),
    Input("layer-opacity-store", "data"),
    prevent_initial_call=True,
)


@app.callback(
    Output("layer-opacity-store", "data"),
    Input("layer-opacity-ranked",         "value"),
    Input("layer-opacity-mollweide",      "value"),
    Input("layer-opacity-habitat",        "value"),
    Input("layer-opacity-ias_ujungkulon", "value"),
    Input("layer-opacity-ias_baluran",    "value"),
    Input("layer-toggle-ranked",         "value"),
    Input("layer-toggle-mollweide",      "value"),
    Input("layer-toggle-habitat",        "value"),
    Input("layer-toggle-ias_ujungkulon", "value"),
    Input("layer-toggle-ias_baluran",    "value"),
    Input("layer-toggle",    "value"),
    Input("layer-order",     "data"),
    prevent_initial_call=True,
)
def update_opacity_store(
    op_ranked, op_mollweide, op_habitat, op_ias_uk, op_ias_bal,
    tog_ranked, tog_mollweide, tog_habitat, tog_ias_uk, tog_ias_bal,
    global_toggle, layer_order,
):
    """Simpan urutan opacity visible layers ke store untuk diapply JS ke MapLibre."""
    global_visible = bool(global_toggle and "show" in global_toggle)
    toggles = {
        "ranked":         tog_ranked,
        "mollweide":      tog_mollweide,
        "habitat":        tog_habitat,
        "ias_ujungkulon": tog_ias_uk,
        "ias_baluran":    tog_ias_bal,
    }
    opacities_all = {
        "ranked":         op_ranked         if op_ranked         is not None else 1.0,
        "mollweide":      op_mollweide       if op_mollweide      is not None else 1.0,
        "habitat":        op_habitat         if op_habitat        is not None else 1.0,
        "ias_ujungkulon": op_ias_uk          if op_ias_uk         is not None else 1.0,
        "ias_baluran":    op_ias_bal         if op_ias_bal        is not None else 1.0,
    }
    order = layer_order or ["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]
    visible_keys = [
        k for k in order
        if global_visible and toggles.get(k) and "show" in (toggles.get(k) or [])
    ]
    # Urutan opacity harus sesuai urutan raster layer di MapLibre (reversed visible_keys)
    opacities = [opacities_all[k] for k in reversed(visible_keys)]
    return {"opacities": opacities}


@app.callback(
    Output("pixel-info", "children"),
    Input("map-graph",   "hoverData"),
)
def update_pixel_info(hover_data):
    """Display pixel value and admin info on hover."""
    _t0 = time.time()
    if not hover_data:
        return "Arahkan kursor ke area data pada peta untuk melihat nilai pixel."

    point = hover_data["points"][0]
    lat   = point.get("lat", "?")
    lon   = point.get("lon", "?")
    text  = point.get("text", "")

    admin = point_to_admin(lat, lon) if isinstance(lat, float) and isinstance(lon, float) else {}
    provinsi      = admin.get("provinsi",     "Tidak diketahui")
    wilayah       = admin.get("wilayah",      "Tidak diketahui")
    tipe_wilayah  = admin.get("tipe_wilayah", "")
    wilayah_label = f"{tipe_wilayah} {wilayah}".strip() if tipe_wilayah else wilayah

    lines = [
        html.B("Koordinat"), html.Br(),
        f"Lat: {lat:.4f}°" if isinstance(lat, float) else f"Lat: {lat}", html.Br(),
        f"Lon: {lon:.4f}°" if isinstance(lon, float) else f"Lon: {lon}",
        html.Br(), html.Br(),
        html.B("Wilayah Administratif"), html.Br(),
        html.Span("Provinsi: ", style={"fontWeight": "600"}),
        html.Span(provinsi, style={"color": "#00857F"}), html.Br(),
        html.Span("Kab/Kota: ", style={"fontWeight": "600"}),
        html.Span(wilayah_label, style={"color": "#00857F"}),
        html.Br(), html.Br(),
        html.B("Nilai Piksel"), html.Br(),
    ]
    for part in text.split("<br>"):
        lines += [part, html.Br()]
    log_timing("update_hover_info", _t0, time.time(),
               {"lat": round(lat, 4) if isinstance(lat, float) else lat,
                "lon": round(lon, 4) if isinstance(lon, float) else lon})
    return lines


@app.callback(
    Output("pinned-data", "data"),
    Input("map-click-coords",            "data"),
    Input("clear-pin-btn",               "n_clicks"),
    State("layer-toggle-ranked",         "value"),
    State("layer-toggle-mollweide",      "value"),
    State("layer-toggle-habitat",        "value"),
    State("layer-toggle-ias_ujungkulon", "value"),
    State("layer-toggle-ias_baluran",    "value"),
    State("layer-toggle",                "value"),
    State("pinned-data",                 "data"),
    prevent_initial_call=True,
)
def update_pinned_store(click_coords, clear_clicks,
                        toggle_ranked, toggle_mollweide, toggle_habitat,
                        toggle_ias_ujungkulon, toggle_ias_baluran,
                        layer_toggle_global, current_pin):
    """Save or clear pin; sample pixel values for all visible layers."""
    _t0 = time.time()
    triggered = ctx.triggered_id
    if triggered == "clear-pin-btn":
        return None
    if not click_coords:
        return current_pin

    lat = click_coords.get("lat")
    lon = click_coords.get("lon")
    if lat is None or lon is None:
        return current_pin

    global_visible = bool(layer_toggle_global and "show" in layer_toggle_global)
    toggles = {
        "ranked":         toggle_ranked,
        "mollweide":      toggle_mollweide,
        "habitat":        toggle_habitat,
        "ias_ujungkulon": toggle_ias_ujungkulon,
        "ias_baluran":    toggle_ias_baluran,
    }
    visible_keys = [
        k for k in ["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]
        if global_visible and toggles[k] and "show" in (toggles[k] or [])
    ]

    admin    = point_to_admin(lat, lon)
    provinsi = admin.get("provinsi", "Tidak diketahui")

    layer_samples = {k: sample_pixel_text(lat, lon, k) for k in visible_keys}

    result = {
        "lat":           lat,
        "lon":           lon,
        "layer_samples": layer_samples,
        "primary_key":   visible_keys[0] if visible_keys else None,
        "provinsi":      provinsi,
        "wilayah":       admin.get("wilayah",      "Tidak diketahui"),
        "tipe_wilayah":  admin.get("tipe_wilayah", ""),
        "outside":       provinsi == "Tidak diketahui",
    }
    log_timing("pin_location", _t0, time.time(),
               {"lat": round(lat, 4), "lon": round(lon, 4), "layers_sampled": len(layer_samples)})
    return result


@app.callback(
    Output("pinned-info", "children"),
    Input("pinned-data",  "data"),
)
def render_pinned_info(pin):
    """Display pinned pixel info with coordinates, admin data, and all visible layer values."""
    if not pin:
        return "Klik pada peta untuk menjatuhkan pin. Klik lokasi lain untuk memindahkannya."

    lat = pin.get("lat")
    lon = pin.get("lon")

    if pin.get("outside"):
        return [
            html.Div(
                style={"textAlign": "center", "padding": "12px 6px"},
                children=[
                    html.Div("⚠️", style={"fontSize": "24px", "marginBottom": "6px"}),
                    html.B("Titik berada di luar Indonesia",
                           style={"color": "#b94a00", "fontSize": "12px"}),
                    html.Br(), html.Br(),
                    html.Span(
                        f"Lat: {lat:.4f}°, Lon: {lon:.4f}°" if isinstance(lat, float) else "",
                        style={"color": "#939393", "fontSize": "11px"},
                    ),
                ],
            )
        ]

    layer_samples = pin.get("layer_samples", {})
    provinsi      = pin.get("provinsi",     "Tidak diketahui")
    wilayah       = pin.get("wilayah",      "Tidak diketahui")
    tipe_wilayah  = pin.get("tipe_wilayah", "")
    wilayah_label = f"{tipe_wilayah} {wilayah}".strip() if tipe_wilayah else wilayah

    def _section(label):
        return html.Div(label, style={
            "fontSize": "10px", "fontWeight": "600", "letterSpacing": "0.06em",
            "textTransform": "uppercase", "color": "#939393",
            "marginTop": "10px", "marginBottom": "3px",
        })

    lines = [
        _section("Koordinat"),
        html.Span(f"Lat: {lat:.4f}°" if isinstance(lat, float) else f"Lat: {lat}"), html.Br(),
        html.Span(f"Lon: {lon:.4f}°" if isinstance(lon, float) else f"Lon: {lon}"),
        _section("Wilayah Administratif"),
        html.Span("Provinsi: ", style={"fontWeight": "600"}),
        html.Span(provinsi, style={"color": "#00857F"}), html.Br(),
        html.Span("Kab/Kota: ", style={"fontWeight": "600"}),
        html.Span(wilayah_label, style={"color": "#00857F"}),
    ]

    _LAYER_SHORT_LABEL = {
        "ranked":         "Ranked Priority",
        "mollweide":      "Species Richness",
        "habitat":        "IUCN Habitat",
        "ias_ujungkulon": "IAS – TNUK",
        "ias_baluran":    "IAS – TNB",
    }

    for k, text in layer_samples.items():
        meta_k = LAYER_META[k]
        lines.append(_section(_LAYER_SHORT_LABEL.get(k, meta_k["label"])))

        if meta_k["discrete"]:
            # Parse "Nilai: X<br>Kelas: Y" → show color dot + label
            parts = {p.split(":")[0].strip(): p.split(":", 1)[1].strip()
                     for p in text.split("<br>") if ":" in p}
            raw_val = parts.get("Nilai", "")
            kelas   = parts.get("Kelas", "")
            try:
                int_val = int(raw_val)
                mapped  = CODE_MAPPING.get(int_val, int_val) if k == "habitat" else int_val
                color   = meta_k["categories"].get(mapped, ("", "#cccccc"))[1]
            except (ValueError, KeyError):
                color = "#cccccc"
            lines.append(html.Div(
                style={"display": "flex", "alignItems": "center", "gap": "7px", "marginTop": "2px"},
                children=[
                    html.Span(style={
                        "display": "inline-block", "width": "11px", "height": "11px",
                        "borderRadius": "3px", "background": color,
                        "border": "1px solid rgba(0,0,0,0.12)", "flexShrink": "0",
                    }),
                    html.Span(kelas or raw_val, style={"fontWeight": "600", "fontSize": "12px"}),
                    html.Span(f"(kode {raw_val})", style={"color": "#939393", "fontSize": "10px"}),
                ],
            ))
        else:
            for part in text.split("<br>"):
                if part.strip():
                    lines += [part, html.Br()]

    return lines


@app.callback(
    Output("layer-range-ranked", "value"),
    Input("layer-range-reset-ranked", "n_clicks"),
    prevent_initial_call=True,
)
def reset_range_ranked(_):
    return [LAYER_META["ranked"]["vmin"], LAYER_META["ranked"]["vmax"]]


@app.callback(
    Output("layer-range-mollweide", "value"),
    Input("layer-range-reset-mollweide", "n_clicks"),
    prevent_initial_call=True,
)
def reset_range_mollweide(_):
    return [LAYER_META["mollweide"]["vmin"], LAYER_META["mollweide"]["vmax"]]


@app.callback(
    # Layer toggles
    Output("layer-toggle-ranked",         "value"),
    Output("layer-toggle-mollweide",      "value"),
    Output("layer-toggle-habitat",        "value"),
    Output("layer-toggle-ias_ujungkulon", "value"),
    Output("layer-toggle-ias_baluran",    "value"),
    # Opacities
    Output("layer-opacity-ranked",         "value"),
    Output("layer-opacity-mollweide",      "value"),
    Output("layer-opacity-habitat",        "value"),
    Output("layer-opacity-ias_ujungkulon", "value"),
    Output("layer-opacity-ias_baluran",    "value"),
    # Range filters
    Output("layer-range-ranked",    "value", allow_duplicate=True),
    Output("layer-range-mollweide", "value", allow_duplicate=True),
    # Map controls
    Output("basemap-select",        "value"),
    Output("province-select",       "value"),
    Output("search-result",         "data",  allow_duplicate=True),
    Output("location-search-input", "value", allow_duplicate=True),
    Input("reset-all-btn", "n_clicks"),
    prevent_initial_call=True,
)
def reset_all(_):
    return (
        [], [], [], [], [],          # layer toggles → semua OFF
        1.0, 1.0, 1.0, 1.0, 1.0,   # opacities → 100%
        [LAYER_META["ranked"]["vmin"],    LAYER_META["ranked"]["vmax"]],
        [LAYER_META["mollweide"]["vmin"], LAYER_META["mollweide"]["vmax"]],
        "carto-positron",            # basemap default
        "__all__",                   # province → semua provinsi
        None,                        # search-result → clear
        "",                          # search input → clear
    )


# ── AI CHAT PANEL callbacks ────────────────────────────────────────────────────

@app.callback(
    Output("chat-panel",          "style"),
    Output("province-modal",      "style", allow_duplicate=True),
    Output("find-location-modal", "style", allow_duplicate=True),
    Output("settings-modal",      "style", allow_duplicate=True),
    Input("chat-toggle-btn", "n_clicks"),
    Input("chat-close-btn",  "n_clicks"),
    State("chat-panel",      "style"),
    prevent_initial_call=True,
)
def toggle_chat_panel(open_clicks, close_clicks, current_style):
    trigger = ctx.triggered_id
    if trigger == "chat-close-btn":
        return {"display": "none"}, dash.no_update, dash.no_update, dash.no_update
    if current_style and current_style.get("display") == "flex":
        return {"display": "none"}, dash.no_update, dash.no_update, dash.no_update
    return {"display": "flex"}, {"display": "none"}, {"display": "none"}, {"display": "none"}


@app.callback(
    Output("chat-messages", "children"),
    Output("chat-input",    "value"),
    Output("chat-pending",  "data"),
    Input("chat-send-btn",  "n_clicks"),
    Input("chat-input",     "n_submit"),
    State("chat-input",     "value"),
    State("chat-messages",  "children"),
    prevent_initial_call=True,
)
def chat_show_user_bubble(n_clicks, n_submit, user_message, current_messages):
    """Tampilkan bubble user segera saat pesan dikirim, lalu set pending untuk trigger AI."""
    if not user_message or not user_message.strip():
        raise PreventUpdate

    current_messages = current_messages or []
    user_bubble = html.Div(className="chat-bubble user", children=user_message.strip())
    updated_messages = list(current_messages) + [user_bubble]

    return updated_messages, "", user_message.strip()


@app.callback(
    Output("chat-messages", "children", allow_duplicate=True),
    Output("chat-history",  "data"),
    Output("chat-pending",  "data", allow_duplicate=True),
    Input("chat-pending",   "data"),
    State("chat-history",   "data"),
    State("chat-messages",  "children"),
    State("pinned-data",    "data"),
    State("layer-toggle-ranked",         "value"),
    State("layer-toggle-mollweide",      "value"),
    State("layer-toggle-habitat",        "value"),
    State("layer-toggle-ias_ujungkulon", "value"),
    State("layer-toggle-ias_baluran",    "value"),
    State("layer-toggle",   "value"),
    prevent_initial_call=True,
    running=[
        (Output("chat-send-btn", "disabled"), True, False),
        (Output("chat-input",    "disabled"), True, False),
        (Output("chat-loading",  "style"), {"display": "flex"}, {"display": "none"}),
    ],
)
def chat_call_ai(pending_message, history, current_messages,
                 pinned, tog_ranked, tog_mollweide, tog_habitat,
                 tog_ias_uk, tog_ias_bal, global_toggle):
    """Panggil AI setelah bubble user muncul, lalu tambahkan bubble AI."""
    if not pending_message:
        raise PreventUpdate

    history = history or []
    current_messages = current_messages or []

    # Build pin + active layer context untuk AI
    pin_context = _build_pin_context(
        pinned, global_toggle,
        tog_ranked, tog_mollweide, tog_habitat, tog_ias_uk, tog_ias_bal,
    )

    ai_response = query_ai(pending_message, history, pin_context=pin_context)

    ai_bubble = html.Div(className="chat-bubble ai", children=dcc.Markdown(
        ai_response,
        className="chat-markdown",
        dangerously_allow_html=False,
    ))
    updated_messages = list(current_messages) + [ai_bubble]

    history = list(history) + [
        {"role": "user",      "content": pending_message},
        {"role": "assistant", "content": ai_response},
    ]
    history = history[-6:]

    return updated_messages, history, None


def _build_pin_context(pinned, global_toggle,
                       tog_ranked, tog_mollweide, tog_habitat,
                       tog_ias_uk, tog_ias_bal):
    """Build context string dari pin aktif dan layer yang sedang ditampilkan."""
    global_visible = bool(global_toggle and "show" in global_toggle)
    toggles = {
        "ranked":         tog_ranked,
        "mollweide":      tog_mollweide,
        "habitat":        tog_habitat,
        "ias_ujungkulon": tog_ias_uk,
        "ias_baluran":    tog_ias_bal,
    }
    active_keys = [
        k for k in ["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]
        if global_visible and toggles.get(k) and "show" in (toggles.get(k) or [])
    ]

    lines = []

    if active_keys:
        layer_labels = [LAYER_META[k]["label"] for k in active_keys]
        lines.append(f"Layer aktif di peta: {', '.join(layer_labels)}")

    if pinned and not pinned.get("outside") and pinned.get("lat") is not None:
        lat = pinned["lat"]
        lon = pinned["lon"]
        provinsi = pinned.get("provinsi", "")
        wilayah  = pinned.get("wilayah", "")
        tipe     = pinned.get("tipe_wilayah", "")
        admin_str = ""
        if provinsi and provinsi != "Tidak diketahui":
            wil_label = f"{tipe} {wilayah}".strip() if tipe else wilayah
            admin_str = f"{wil_label}, {provinsi}" if wil_label and wil_label != "Tidak diketahui" else provinsi

        lines.append(f"\nPin aktif: {lat:.4f}°, {lon:.4f}°" + (f" ({admin_str})" if admin_str else ""))

        layer_samples = pinned.get("layer_samples", {})
        if layer_samples:
            lines.append("Nilai layer pada pin:")
            for k, text in layer_samples.items():
                meta_k = LAYER_META.get(k, {})
                label  = meta_k.get("label", k)
                clean  = text.replace("<br>", " | ").replace("<b>", "").replace("</b>", "")
                lines.append(f"  - {label}: {clean}")

    return "\n".join(lines) if lines else ""


# ── Settings Modal ────────────────────────────────────────────────

_SETTINGS_MODAL_OUTPUTS = [
    "settings-modal",
    "province-modal",
    "find-location-modal",
]

@app.callback(
    Output("settings-modal",      "style"),
    Output("province-modal",      "style",  allow_duplicate=True),
    Output("find-location-modal", "style",  allow_duplicate=True),
    Output("chat-panel",          "style",  allow_duplicate=True),
    Input("settings-modal-btn",   "n_clicks"),
    Input("stm-close-btn",        "n_clicks"),
    prevent_initial_call=True,
)
def toggle_settings_modal(_open, _close):
    if ctx.triggered_id == "settings-modal-btn":
        return {"display": "flex"}, {"display": "none"}, {"display": "none"}, {"display": "none"}
    return {"display": "none"}, dash.no_update, dash.no_update, dash.no_update


# ── Province Modal ────────────────────────────────────────────────

_PROVINCE_NAMES = None  # lazily populated from LOCATION_LIST

def _get_province_names():
    global _PROVINCE_NAMES
    if _PROVINCE_NAMES is None:
        _PROVINCE_NAMES = [e["name"] for e in LOCATION_LIST if e["type"] == "provinsi"]
    return _PROVINCE_NAMES


def _build_pvm_items(query, active_value):
    q = (query or "").strip().lower()
    items = []
    for name in _get_province_names():
        if q and q not in name.lower():
            continue
        is_active = (name == active_value)
        cls = "pvm-result-item active" if is_active else "pvm-result-item"
        items.append(html.Div(
            name,
            className=cls,
            id={"type": "pvm-item", "value": name},
            n_clicks=0,
        ))
    return items or [html.Div("Tidak ada hasil.", className="pvm-empty")]


@app.callback(
    Output("province-modal",      "style"),
    Output("pvm-search-input",    "value"),
    Output("find-location-modal", "style",  allow_duplicate=True),
    Output("settings-modal",      "style",  allow_duplicate=True),
    Output("chat-panel",          "style",  allow_duplicate=True),
    Input("province-modal-btn",   "n_clicks"),
    Input("pvm-close-btn",        "n_clicks"),
    prevent_initial_call=True,
)
def toggle_province_modal(_open, _close):
    if ctx.triggered_id == "province-modal-btn":
        return {"display": "flex"}, "", {"display": "none"}, {"display": "none"}, {"display": "none"}
    return {"display": "none"}, dash.no_update, dash.no_update, dash.no_update, dash.no_update


@app.callback(
    Output("pvm-results", "children"),
    Input("pvm-search-input", "value"),
    State("province-select",  "value"),
)
def update_pvm_results(query, active_prov):
    return _build_pvm_items(query, active_prov)


@app.callback(
    Output("province-select",  "value",            allow_duplicate=True),
    Output("province-modal",   "style",            allow_duplicate=True),
    Input({"type": "pvm-item", "value": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def pvm_item_clicked(n_clicks_list):
    if not any(n_clicks_list):
        raise PreventUpdate
    triggered = ctx.triggered_id
    if not triggered:
        raise PreventUpdate
    prov_name = triggered.get("value", "")
    if not prov_name:
        raise PreventUpdate
    return prov_name, {"display": "none"}


# ── Find Location Modal ────────────────────────────────────────────

@app.callback(
    Output("find-location-modal", "style"),
    Output("flm-search-input",    "value"),
    Output("province-modal",      "style",  allow_duplicate=True),
    Output("settings-modal",      "style",  allow_duplicate=True),
    Output("chat-panel",          "style",  allow_duplicate=True),
    Input("find-location-btn",    "n_clicks"),
    Input("flm-close-btn",        "n_clicks"),
    State("find-location-modal",  "style"),
    prevent_initial_call=True,
)
def toggle_find_location_modal(n_open, n_close, current_style):
    triggered = ctx.triggered_id
    if triggered == "find-location-btn":
        return {"display": "flex"}, "", {"display": "none"}, {"display": "none"}, {"display": "none"}
    return {"display": "none"}, dash.no_update, dash.no_update, dash.no_update, dash.no_update


def _flm_separator(label):
    return html.Div(label, className="flm-separator")


def _build_flm_items(type_filter, query):
    """Filter LOCATION_LIST by type chip and search query, return Dash children."""
    q = (query or "").strip().lower()

    if type_filter == "semua":
        # Build two separate buckets then join with separator
        prov_items, kab_items = [], []
        for entry in LOCATION_LIST:
            name = entry["name"]
            if q and q not in name.lower():
                continue
            raw_val = entry.get("raw", name)
            sub = entry.get("sub", "")
            type_label = "Provinsi" if entry["type"] == "provinsi" else sub
            item = html.Div(
                [html.Span(name, className="flm-result-name"),
                 html.Span(type_label, className="flm-result-type")],
                className="flm-result-item",
                id={"type": "flm-item", "value": raw_val},
                n_clicks=0,
            )
            if entry["type"] == "provinsi":
                prov_items.append(item)
            else:
                kab_items.append(item)

        result = []
        if prov_items:
            result.append(_flm_separator(f"Provinsi ({len(prov_items)})"))
            result.extend(prov_items)
        if kab_items:
            result.append(_flm_separator(f"Kabupaten / Kota ({len(kab_items)})"))
            result.extend(kab_items)
        return result or [html.Div("Tidak ada hasil.", className="flm-empty")]

    items = []
    for entry in LOCATION_LIST:
        if type_filter == "provinsi" and entry["type"] != "provinsi":
            continue
        if type_filter == "kabkota" and entry["type"] != "kabkota":
            continue
        name = entry["name"]
        if q and q not in name.lower():
            continue
        sub = entry.get("sub", "")
        type_label = "Provinsi" if entry["type"] == "provinsi" else sub
        raw_val = entry.get("raw", name)
        items.append(html.Div(
            [html.Span(name, className="flm-result-name"),
             html.Span(type_label, className="flm-result-type")],
            className="flm-result-item",
            id={"type": "flm-item", "value": raw_val},
            n_clicks=0,
        ))
    return items or [html.Div("Tidak ada hasil.", className="flm-empty")]


@app.callback(
    Output("flm-type-filter",    "data"),
    Output("flm-chip-semua",    "className"),
    Output("flm-chip-provinsi", "className"),
    Output("flm-chip-kabkota",  "className"),
    Input("flm-chip-semua",    "n_clicks"),
    Input("flm-chip-provinsi", "n_clicks"),
    Input("flm-chip-kabkota",  "n_clicks"),
    prevent_initial_call=True,
)
def update_flm_type_filter(_s, _p, _k):
    mapping = {
        "flm-chip-semua":    "semua",
        "flm-chip-provinsi": "provinsi",
        "flm-chip-kabkota":  "kabkota",
    }
    active = mapping.get(ctx.triggered_id, "semua")
    cls = {k: "flm-chip active" if mapping[k] == active else "flm-chip" for k in mapping}
    return active, cls["flm-chip-semua"], cls["flm-chip-provinsi"], cls["flm-chip-kabkota"]


@app.callback(
    Output("flm-results", "children"),
    Input("flm-search-input", "value"),
    Input("flm-type-filter",  "data"),
)
def update_flm_results(query, type_filter):
    return _build_flm_items(type_filter or "semua", query)


@app.callback(
    Output("search-result",        "data", allow_duplicate=True),
    Output("find-location-modal",  "style", allow_duplicate=True),
    Input({"type": "flm-item", "value": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def flm_item_clicked(n_clicks_list):
    if not any(n_clicks_list):
        raise PreventUpdate
    triggered = ctx.triggered_id
    if not triggered:
        raise PreventUpdate
    location_name = triggered.get("value", "")
    if not location_name:
        raise PreventUpdate
    result = search_location(location_name)
    return result, {"display": "none"}
