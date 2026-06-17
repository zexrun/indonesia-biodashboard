"""Province spatial masking utilities."""

import json
import numpy as np
from dash import html
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from shapely.ops import unary_union


def build_province_mask(province_name, gdf_wgs84, h, w, bounds):
    """
    Build a boolean mask (True = inside province) for a WGS84 raster grid.

    bounds: (lon_min, lat_min, lon_max, lat_max)
    Returns: np.ndarray shape (h, w), dtype bool
    """
    lon_min, lat_min, lon_max, lat_max = bounds
    rows = gdf_wgs84[gdf_wgs84["NAME_1"] == province_name]
    if rows.empty:
        return np.zeros((h, w), dtype=bool)

    geom = unary_union(rows.geometry)
    transform = from_bounds(lon_min, lat_min, lon_max, lat_max, w, h)
    burned = rasterize(
        [(geom, 1)],
        out_shape=(h, w),
        transform=transform,
        fill=0,
        dtype="uint8",
    )
    return burned.astype(bool)


def apply_mask_to_arr(arr, bool_mask, nodata):
    """Set pixels outside province (False in mask) to nodata."""
    masked = arr.copy()
    fill = nodata if nodata is not None else 0
    masked[~bool_mask] = fill
    return masked


def get_province_geojson(province_name, gdf_wgs84):
    """Return GeoJSON __geo_interface__ dict for a single province, or None."""
    rows = gdf_wgs84[gdf_wgs84["NAME_1"] == province_name]
    if rows.empty:
        return None
    geom = unary_union(rows.geometry)
    return json.loads(json.dumps(geom.__geo_interface__))


def build_stats_children(province_name, arr, bool_mask, meta, nodata):
    """Dash children list for the province statistics panel."""
    in_prov = arr[bool_mask]
    if nodata is not None:
        in_prov = in_prov[in_prov != nodata]

    if in_prov.size == 0:
        return [html.Span("Tidak ada data piksel dalam provinsi ini.",
                           style={"color": "#8fac98"})]

    pixel_count = int(in_prov.size)

    if meta["discrete"]:
        cats = meta["categories"]
        unique, counts = np.unique(in_prov, return_counts=True)
        lines = [
            html.B(f"Distribusi Kelas"), html.Br(),
            html.Span(province_name, style={"color": "#00e676", "fontWeight": "700"}),
            html.Br(), html.Br(),
            html.Span(f"Total piksel: {pixel_count:,}", style={"color": "#8fac98"}),
            html.Br(), html.Br(),
        ]
        for v, c in zip(unique, counts):
            label = cats.get(int(v), ("Unknown",))[0]
            pct = c / pixel_count * 100
            lines += [
                html.Span(f"{label}: ", style={"fontWeight": "600"}),
                html.Span(f"{c:,} ({pct:.1f}%)"),
                html.Br(),
            ]
        return lines

    mn  = float(np.min(in_prov))
    mx  = float(np.max(in_prov))
    med = float(np.median(in_prov))
    avg = float(np.mean(in_prov))

    lines = [
        html.B("Statistik Provinsi"), html.Br(),
        html.Span(province_name, style={"color": "#00e676", "fontWeight": "700"}),
        html.Br(), html.Br(),
        html.Span("Min: ",       style={"fontWeight": "600"}), html.Span(f"{mn:.1f}"),  html.Br(),
        html.Span("Max: ",       style={"fontWeight": "600"}), html.Span(f"{mx:.1f}"),  html.Br(),
        html.Span("Median: ",    style={"fontWeight": "600"}), html.Span(f"{med:.1f}"), html.Br(),
        html.Span("Rata-rata: ", style={"fontWeight": "600"}), html.Span(f"{avg:.1f}"), html.Br(),
        html.Span(f"Piksel: {pixel_count:,}", style={"color": "#8fac98"}),
        html.Br(), html.Br(),
    ]

    zones = meta.get("zones", [])
    if zones:
        lines += [html.B("Distribusi Zona"), html.Br()]
        for zmin, zmax, zlabel, _ in zones:
            cnt = int(np.sum((in_prov >= zmin) & (in_prov <= zmax)))
            pct = cnt / pixel_count * 100
            lines += [
                html.Span(f"{zlabel}: ", style={"fontWeight": "600"}),
                html.Span(f"{cnt:,} ({pct:.1f}%)"),
                html.Br(),
            ]

    return lines
