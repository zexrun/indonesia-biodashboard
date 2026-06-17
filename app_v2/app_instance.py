"""Shared Dash app instance to avoid circular imports between layout and callbacks."""

import os
import dash
import dash_bootstrap_components as dbc
from flask import request, jsonify
from .perf_timing import log_timing
import time

ASSETS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "assets",
)

app = dash.Dash(
    __name__,
    title="Indonesia BioDashboard",
    update_title=None,
    assets_folder=ASSETS_PATH,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP,
        "https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:ital,wght@0,300;0,400;0,500;1,300&display=swap",
    ],
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    suppress_callback_exceptions=True,
)


@app.server.route("/log-timing", methods=["POST"])
def _log_timing_endpoint():
    """Terima timing dari JS dan print ke terminal."""
    data = request.get_json(silent=True) or {}
    label = data.get("label", "js_event")
    elapsed_ms = float(data.get("elapsed_ms", 0))
    info = data.get("info", "")
    t1 = time.time()
    t0 = t1 - elapsed_ms / 1000
    log_timing(label, t0, t1, info)
    return jsonify({"ok": True})
