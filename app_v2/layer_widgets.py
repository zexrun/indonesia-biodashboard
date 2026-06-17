"""Reusable widget components for layer cards."""

from dash import html, dcc
import dash_bootstrap_components as dbc

from .config import LAYER_META


# ── Layer display config ───────────────────────────────────────────
_LAYER_ICONS = {
    "ranked":         "◈",
    "mollweide":      "◉",
    "habitat":        "◬",
    "ias_ujungkulon": "⚠",
    "ias_baluran":    "⚠",
}
_LAYER_COLORS = {
    "ranked":         "#d62728",
    "mollweide":      "#440154",
    "habitat":        "#2d6a2d",
    "ias_ujungkulon": "#cc3300",
    "ias_baluran":    "#cc3300",
}


def _widget_card(section_id, icon, title, body_children,
                 header_extras=None, start_open=True, card_id=None, card_class="widget-card"):
    """Collapsible GMW-style widget card."""
    header_kids = [
        html.Span(icon, className="widget-icon"),
        html.Span(title, className="widget-title"),
        *(header_extras or []),
        html.Span("▾", className="widget-chevron"),
    ]
    card_props = {"className": card_class}
    if card_id:
        card_props["id"] = card_id

    return dbc.Card(
        **card_props,
        children=[
            html.Div(
                header_kids,
                className="widget-card-header",
                id={"type": "widget-header-btn", "index": section_id},
                n_clicks=0,
            ),
            dbc.Collapse(
                id={"type": "widget-collapse", "index": section_id},
                is_open=start_open,
                children=html.Div(
                    className="widget-card-body",
                    children=body_children,
                ),
            ),
        ],
    )


def _layer_widget(key):
    """Widget card for a single raster layer with toggle, opacity, and optional range."""
    meta = LAYER_META[key]

    toggle = dcc.Checklist(
        id=f"layer-toggle-{key}",
        className="toggle-pill layer-toggle-inline",
        options=[{"label": " ", "value": "show"}],
        value=[],
        inline=True,
    )

    desc = meta.get("description", "")
    body = [
        *(
            [html.P(desc, className="layer-description")]
            if desc else []
        ),
        html.Div(className="ctrl-row", children=[
            html.Span("Opacity", className="ctrl-label"),
            dcc.Slider(
                id=f"layer-opacity-{key}",
                min=0, max=1, step=0.05, value=1.0,
                marks={0: "0%", 0.5: "50%", 1: "100%"},
                tooltip={"placement": "top", "always_visible": False},
                updatemode="drag",
            ),
        ]),
    ]

    if not meta["discrete"]:
        body.append(
            html.Div(className="ctrl-row", children=[
                html.Div(className="ctrl-row-inline", children=[
                    html.Span("Range", className="ctrl-label"),
                    html.Button(
                        "↺ Reset",
                        id=f"layer-range-reset-{key}",
                        className="btn-range-reset",
                        n_clicks=0,
                    ),
                ]),
                dcc.RangeSlider(
                    id=f"layer-range-{key}",
                    min=meta["vmin"],
                    max=meta["vmax"],
                    step=max(1, int((meta["vmax"] - meta["vmin"]) / 100)),
                    value=[meta["vmin"], meta["vmax"]],
                    marks={},
                    tooltip={"placement": "top", "always_visible": True},
                    allowCross=False,
                ),
            ])
        )
    elif key == "habitat":
        all_class_keys = list(meta["categories"].keys())
        class_options = [
            {
                "label": html.Span(
                    [
                        html.Span(className="class-dot",
                                  style={"background": meta["categories"][k][1]}),
                        meta["categories"][k][0],
                    ],
                    className="class-option-label",
                ),
                "value": k,
            }
            for k in all_class_keys
        ]
        body.append(
            html.Div(className="ctrl-row habitat-classes-row", children=[
                html.Div(className="ctrl-row-inline", children=[
                    html.Span("Kelas Aktif", className="ctrl-label"),
                    html.Button(
                        "✓ Semua",
                        id="habitat-classes-all-btn",
                        className="btn-range-reset",
                        n_clicks=0,
                    ),
                ]),
                dcc.Checklist(
                    id="habitat-active-classes",
                    options=class_options,
                    value=all_class_keys,
                    className="habitat-class-checklist",
                    labelClassName="habitat-class-label",
                    inputClassName="habitat-class-input",
                ),
            ])
        )
    elif key in ("ias_ujungkulon", "ias_baluran"):
        all_class_keys = list(meta["categories"].keys())
        class_options = [
            {
                "label": html.Span(
                    [
                        html.Span(className="class-dot",
                                  style={"background": meta["categories"][k][1]}),
                        meta["categories"][k][0],
                    ],
                    className="class-option-label",
                ),
                "value": k,
            }
            for k in all_class_keys
            if k != 0
        ]
        body.append(
            html.Div(className="ctrl-row habitat-classes-row", children=[
                html.Div(className="ctrl-row-inline", children=[
                    html.Span("Kelas Potensi", className="ctrl-label"),
                    html.Button(
                        "⊕ Fokus",
                        id=f"ias-focus-btn-{key}",
                        className="btn-range-reset btn-focus",
                        n_clicks=0,
                        title=f"Zoom ke area {meta['location']}",
                    ),
                ]),
                dcc.Checklist(
                    id=f"ias-active-classes-{key}",
                    options=class_options,
                    value=[k for k in all_class_keys if k != 0],
                    className="habitat-class-checklist",
                    labelClassName="habitat-class-label",
                    inputClassName="habitat-class-input",
                ),
            ])
        )

    return _widget_card(
        section_id=f"layer-{key}",
        icon=_LAYER_ICONS[key],
        title=meta["label"],
        body_children=body,
        header_extras=[
            html.Span("⠿", className="layer-drag-handle"),
            html.Span(
                className="layer-color-dot",
                style={"background": _LAYER_COLORS[key]},
            ),
            toggle,
        ],
        start_open=True,
        card_id=f"layer-card-{key}",
        card_class="widget-card layer-is-off",
    )
