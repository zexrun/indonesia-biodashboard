"""
GMW-style overlay layout: Map full-screen, sidebar floats on top left.
"""

from dash import html, dcc
import dash_bootstrap_components as dbc

from .app_instance import app
from .config import FILES, LAYER_META
from .cache import PROVINCE_OPTIONS
from .layer_widgets import _LAYER_ICONS, _LAYER_COLORS, _widget_card, _layer_widget


app.layout = html.Div(
    id="app-root",
    className="app-root",
    children=[

        # ── Stores & Intervals ─────────────────────────────────────
        dcc.Store(id="pinned-data",            data=None),
        dcc.Store(id="map-click-coords",       data=None),
        dcc.Store(id="sidebar-state",          data=True),
        dcc.Store(id="search-result",          data=None),
        dcc.Store(id="selected-legend-layer",  data="ranked"),
        dcc.Store(id="sidebar-active-tab",     data="layers"),
        dcc.Store(id="layer-order",            data=["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]),
        dcc.Interval(id="drag-order-poll",     interval=200, n_intervals=0),
        dcc.Interval(id="click-poll",          interval=200, n_intervals=0),
        html.Div(id="pin-dummy",               style={"display": "none"}),
        html.Div(id="opacity-dummy",           style={"display": "none"}),
        html.Div(id="zoom-dummy",              style={"display": "none"}),
        dcc.Store(id="layer-opacity-store",    data={}),
        dcc.Store(id="chat-history",           data=[]),
        dcc.Store(id="chat-pending",           data=None),

        # ── MAP (full screen base layer) ───────────────────────────
        html.Div(
            className="app-map-container",
            children=[
                dcc.Graph(
                    id="map-graph",
                    className="map-graph-fill",
                    config={
                        "scrollZoom":             True,
                        "displayModeBar":         True,
                        "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                        "doubleClick":            False,
                        "displaylogo":            False,
                    },
                ),

                # ── ZOOM CONTROLS (Bottom Right) ──────────────────
                html.Div(
                    className="zoom-controls",
                    children=[
                        html.Button("+", id="zoom-in-btn",  className="zoom-btn", n_clicks=0, title="Zoom in"),
                        html.Button("−", id="zoom-out-btn", className="zoom-btn", n_clicks=0, title="Zoom out"),
                    ],
                ),

                # ── FLOATING PANELS (Top Right) ────────────────────
                html.Div(
                    className="floating-panels",
                    children=[
                        # Legend
                        dbc.Card(
                            className="floating-widget",
                            children=[
                                html.Div(
                                    ["◈ ", html.Span("Legend", className="widget-title"),
                                     html.Span("▾", className="widget-chevron")],
                                    className="widget-card-header",
                                    id={"type": "widget-header-btn", "index": "floating-legend"},
                                    n_clicks=0,
                                ),
                                dbc.Collapse(
                                    id={"type": "widget-collapse", "index": "floating-legend"},
                                    is_open=False,
                                    children=html.Div(
                                        className="widget-card-body",
                                        children=[
                                            html.Div(
                                                id="legend-tabs-container",
                                                className="legend-tabs-container",
                                                children=[
                                                    html.Div(id="legend-selector", className="legend-seg-selector", children=[]),
                                                    html.Div(id="legend-content",  className="legend-content",      children=[]),
                                                ],
                                            ),
                                        ],
                                    ),
                                ),
                            ],
                        ),

                        # Pixel Info (hidden)
                        html.Div(id="pixel-info", style={"display": "none"}),

                        # Pin Lokasi
                        dbc.Card(
                            className="floating-widget",
                            children=[
                                html.Div(
                                    ["⊗ ", html.Span("Pin Lokasi", className="widget-title"),
                                     html.Button("✕", id="clear-pin-btn", className="pin-clear-btn", n_clicks=0),
                                     html.Span("▾", className="widget-chevron")],
                                    className="widget-card-header",
                                    id={"type": "widget-header-btn", "index": "floating-pin"},
                                    n_clicks=0,
                                ),
                                dbc.Collapse(
                                    id={"type": "widget-collapse", "index": "floating-pin"},
                                    is_open=False,
                                    children=html.Div(
                                        className="widget-card-body",
                                        children=[
                                            html.Div(
                                                id="pinned-info",
                                                className="info-content",
                                                children=["Klik lokasi pada peta untuk menjatuhkan pin."],
                                            ),
                                        ],
                                    ),
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),

        # ── SIDEBAR OVERLAY ────────────────────────────────────────
        html.Div(
            id="app-sidebar",
            className="app-sidebar",
            children=[

                # ── Sidebar Header (wave teal) ─────────────────────
                html.Div(
                    className="sidebar-header",
                    children=[
                        html.Div(
                            className="sidebar-header-top",
                            children=[
                                html.Div(
                                    className="sidebar-brand",
                                    children=[
html.Div(
                                            className="sidebar-brand-text",
                                            children=[
                                                html.Span("Indonesia BioDashboard", className="sidebar-brand-title"),
                                                html.Span("Biodiversity · Conservation · Habitat", className="sidebar-brand-sub"),
                                            ],
                                        ),
                                    ],
                                ),
                                html.Button(
                                    "✕",
                                    id="sidebar-toggle-btn",
                                    className="sidebar-close-btn",
                                    n_clicks=0,
                                    title="Tutup sidebar",
                                ),
                            ],
                        ),
                        # Action bar
                        html.Div(
                            className="sidebar-action-bar",
                            children=[
                                html.Button(
                                    [html.Span("↺", className="action-icon"), html.Span("Reset", className="action-label")],
                                    id="reset-all-btn",
                                    className="action-btn",
                                    n_clicks=0,
                                    title="Reset semua pengaturan",
                                ),
                                html.Button(
                                    [html.Span("◈", className="action-icon"), html.Span("Provinsi", className="action-label")],
                                    id="province-modal-btn",
                                    className="action-btn",
                                    n_clicks=0,
                                    title="Fokus ke provinsi",
                                ),
                                html.Button(
                                    [html.Span("⌖", className="action-icon"), html.Span("Lokasi", className="action-label")],
                                    id="find-location-btn",
                                    className="action-btn",
                                    n_clicks=0,
                                    title="Cari lokasi di peta",
                                ),
                                html.Button(
                                    [html.Span("⚙", className="action-icon"), html.Span("Setting", className="action-label")],
                                    id="settings-modal-btn",
                                    className="action-btn",
                                    n_clicks=0,
                                    title="Pengaturan peta",
                                ),
                            ],
                        ),
                    ],
                ),

                # ── Tanya AI button (full-width row) ──────────────
                html.Button(
                    [html.Span("💬", className="action-icon"), html.Span("Tanya AI", className="action-label")],
                    id="chat-toggle-btn",
                    className="ai-btn",
                    n_clicks=0,
                    title="Buka asisten konservasi AI",
                ),

                # ── Layers content (no tab nav) ────────────────────
                html.Div(
                    id="sidebar-tab-layers",
                    className="sidebar-tab-content",
                    children=[
                        # Province select — now a hidden store, driven by province modal
                        dcc.Dropdown(
                            id="province-select",
                            options=PROVINCE_OPTIONS,
                            value="__all__",
                            clearable=False,
                            style={"display": "none"},
                        ),

                        # Hidden search input (still used by existing callback)
                        dcc.Input(
                            id="location-search-input",
                            type="text",
                            placeholder="Cari provinsi / kota...",
                            debounce=True,
                            style={"display": "none"},
                            n_submit=0,
                        ),
                        html.Div(id="search-status", className="search-status"),

                        html.Div(className="layer-list-header", children=[
                            html.Span("Layer Data", className="ctrl-label"),
                        ]),

                        html.Div(
                            id="layer-cards-list",
                            className="layer-cards-list",
                            children=[
                                html.Div(id="layer-slot-ranked",         style={"order": 0}, children=[_layer_widget("ranked")]),
                                html.Div(id="layer-slot-mollweide",      style={"order": 1}, children=[_layer_widget("mollweide")]),
                                html.Div(id="layer-slot-habitat",        style={"order": 2}, children=[_layer_widget("habitat")]),
                                html.Div(id="layer-slot-ias_ujungkulon", style={"order": 3}, children=[_layer_widget("ias_ujungkulon")]),
                                html.Div(id="layer-slot-ias_baluran",    style={"order": 4}, children=[_layer_widget("ias_baluran")]),
                            ],
                        ),
                    ],
                ),

                # hidden stub — keeps sidebar-tab-btn-settings id alive for any callback
                html.Div(id="sidebar-tab-settings", style={"display": "none"}),
            ],
        ),

        # ── Sidebar open button (shown when sidebar closed) ────────
        html.Button(
            "☰",
            id="sidebar-open-btn",
            className="sidebar-open-btn",
            n_clicks=0,
            title="Buka sidebar",
            style={"display": "none"},
        ),

        # ── Scale Bar (Bottom Left, respects sidebar width) ────────
        html.Div(
            id="map-scale-bar",
            className="map-scale-bar",
            children=[
                html.Div(id="scale-bar-line", className="scale-bar-line"),
                html.Span(id="scale-bar-label", className="scale-bar-label", children=""),
            ],
        ),

        # ── Settings Modal ─────────────────────────────────────────
        html.Div(
            id="settings-modal",
            className="settings-modal",
            style={"display": "none"},
            children=[
                html.Div(
                    className="stm-inner",
                    children=[
                        html.Div(
                            className="stm-header-row",
                            children=[
                                html.Span("Pengaturan", className="stm-title"),
                                html.Button("✕", id="stm-close-btn", className="stm-close-btn", n_clicks=0),
                            ],
                        ),
                        html.Div(
                            className="stm-body",
                            children=[
                                html.Div(className="stm-section-label", children="Peta Dasar"),
                                dcc.Dropdown(
                                    id="basemap-select",
                                    options=[
                                        {"label": "OpenStreetMap", "value": "open-street-map"},
                                        {"label": "Carto Light",   "value": "carto-positron"},
                                        {"label": "Carto Dark",    "value": "carto-darkmatter"},
                                    ],
                                    value="carto-positron",
                                    clearable=False,
                                    className="gmw-dropdown",
                                ),
                                # hidden layer-toggle stub
                                dcc.Checklist(
                                    id="layer-toggle",
                                    options=[{"label": "", "value": "show"}],
                                    value=["show"],
                                    style={"display": "none"},
                                ),

                                # ── About / Acknowledgement ──────────
                                html.Div(className="stm-divider"),
                                html.Div(className="stm-section-label", children="Tentang Aplikasi"),
                                html.Div(
                                    className="stm-about",
                                    children=[
                                        html.Div("Indonesia BioDashboard", className="stm-about-title"),
                                        html.Div("Sistem Informasi Geospasial Keanekaragaman Hayati dan Konservasi Indonesia", className="stm-about-subtitle"),
                                        html.Div(className="stm-about-divider"),
                                        html.Div([
                                            html.Span("Peneliti", className="stm-about-key"),
                                            html.Span("Muhammad Rifqy Khuzaini", className="stm-about-val"),
                                        ], className="stm-about-row"),
                                        html.Div([
                                            html.Span("NIM", className="stm-about-key"),
                                            html.Span("1301223473", className="stm-about-val"),
                                        ], className="stm-about-row"),
                                        html.Div([
                                            html.Span("Institusi", className="stm-about-key"),
                                            html.Span("Universitas Telkom", className="stm-about-val"),
                                        ], className="stm-about-row"),
                                        html.Div([
                                            html.Span("Program Studi", className="stm-about-key"),
                                            html.Span("Sarjana Informatika", className="stm-about-val"),
                                        ], className="stm-about-row"),
                                        html.Div([
                                            html.Span("Departemen", className="stm-about-key"),
                                            html.Span("Fakultas Informatika", className="stm-about-val"),
                                        ], className="stm-about-row"),
                                        html.Div([
                                            html.Span("Pembimbing", className="stm-about-key"),
                                            html.Span("Rio Nurtantyana, Tri Atmaja", className="stm-about-val"),
                                        ], className="stm-about-row"),
                                        html.Div([
                                            html.Span("Tahun", className="stm-about-key"),
                                            html.Span("2026", className="stm-about-val"),
                                        ], className="stm-about-row"),
                                        html.Div(className="stm-about-divider"),
                                        html.Div("Sumber Data", className="stm-about-sources-label"),
                                        html.Div([
                                            html.Span("Jung et al. (2021)", className="stm-about-source"),
                                            html.Span("Ranked Conservation Priority", className="stm-about-source-desc"),
                                        ], className="stm-about-source-row"),
                                        html.Div([
                                            html.Span("Jung et al. (2020)", className="stm-about-source"),
                                            html.Span("IUCN Habitat Classification", className="stm-about-source-desc"),
                                        ], className="stm-about-source-row"),
                                        html.Div([
                                            html.Span("GADM v4.1", className="stm-about-source"),
                                            html.Span("Batas Administratif Indonesia", className="stm-about-source-desc"),
                                        ], className="stm-about-source-row"),
                                        html.Div([
                                            html.Span("Angga Yudaputra, Ph.D.", className="stm-about-source"),
                                            html.Span("Pemetaan IAS TNUK & TNB", className="stm-about-source-desc"),
                                        ], className="stm-about-source-row"),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),

        # ── Province Modal ─────────────────────────────────────────
        html.Div(
            id="province-modal",
            className="province-modal",
            style={"display": "none"},
            children=[
                html.Div(
                    className="pvm-inner",
                    children=[
                        html.Div(
                            className="pvm-header-row",
                            children=[
                                html.Span("Fokus Provinsi", className="pvm-title"),
                                html.Button("✕", id="pvm-close-btn", className="pvm-close-btn", n_clicks=0),
                            ],
                        ),
                        html.Div(
                            className="pvm-search-row",
                            children=[
                                html.Span("🔍", className="pvm-search-icon"),
                                dcc.Input(
                                    id="pvm-search-input",
                                    type="text",
                                    placeholder="Cari nama provinsi...",
                                    debounce=False,
                                    n_submit=0,
                                    className="pvm-input",
                                    autoComplete="off",
                                ),
                            ],
                        ),
                        html.Div(
                            id="pvm-results",
                            className="pvm-results",
                            children=[],
                        ),
                    ],
                ),
            ],
        ),

        # ── Find Location Modal ────────────────────────────────────
        dcc.Store(id="flm-type-filter", data="semua"),
        html.Div(
            id="find-location-modal",
            className="find-location-modal",
            style={"display": "none"},
            children=[
                html.Div(
                    className="find-location-modal-inner",
                    children=[
                        # Header row: title + close
                        html.Div(
                            className="flm-header-row",
                            children=[
                                html.Span("Cari Lokasi", className="flm-title"),
                                html.Button("✕", id="flm-close-btn", className="flm-close-btn", n_clicks=0),
                            ],
                        ),
                        # Search input
                        html.Div(
                            className="flm-search-row",
                            children=[
                                html.Span("🔍", className="flm-search-icon"),
                                dcc.Input(
                                    id="flm-search-input",
                                    type="text",
                                    placeholder="Ketik nama provinsi atau kabupaten/kota...",
                                    debounce=False,
                                    n_submit=0,
                                    className="flm-input",
                                    autoComplete="off",
                                ),
                            ],
                        ),
                        # Filter chips
                        html.Div(
                            className="flm-chips-row",
                            children=[
                                html.Button("Semua",    id="flm-chip-semua",    className="flm-chip active", n_clicks=0),
                                html.Button("Provinsi", id="flm-chip-provinsi", className="flm-chip",        n_clicks=0),
                                html.Button("Kab/Kota", id="flm-chip-kabkota",  className="flm-chip",        n_clicks=0),
                            ],
                        ),
                        # Results list
                        html.Div(
                            id="flm-results",
                            className="flm-results",
                            children=[],
                        ),
                    ],
                ),
            ],
        ),

        # ── AI Chat Modal ──────────────────────────────────────────
        html.Div(
            id="chat-panel",
            className="chat-modal",
            style={"display": "none"},
            children=[
                html.Div(
                    className="chat-modal-inner",
                    children=[
                        html.Div(
                            className="chat-header",
                            children=[
                                html.Span("💬", className="chat-header-icon"),
                                html.Span("Asisten Konservasi AI", className="chat-header-title"),
                                html.Button("✕", id="chat-close-btn", className="chat-close-btn", n_clicks=0),
                            ],
                        ),
                        html.Div(
                            id="chat-messages",
                            className="chat-messages",
                            children=[
                                html.Div(
                                    className="chat-bubble ai",
                                    children="Halo! Saya asisten analisis konservasi Indonesia. Tanya saya tentang nilai konservasi, kekayaan spesies, atau habitat di lokasi mana pun di Indonesia.",
                                )
                            ],
                        ),
                        html.Div(
                            id="chat-loading",
                            className="chat-loading",
                            children=[html.Span(className="chat-loading-dot")] * 3,
                            style={"display": "none"},
                        ),
                        html.Div(
                            className="chat-input-row",
                            children=[
                                dcc.Input(id="chat-input", type="text",
                                          placeholder="Contoh: Nilai konservasi di Kota Bandung?",
                                          debounce=False, n_submit=0,
                                          className="chat-input", autoComplete="off"),
                                html.Button("➤", id="chat-send-btn", className="chat-send-btn", n_clicks=0),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
)
