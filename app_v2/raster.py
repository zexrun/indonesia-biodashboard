"""Utilitas raster: load TIF ke WGS84 + konversi array → PNG base64."""

import io
import base64
import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.transform import array_bounds
from PIL import Image
import matplotlib.cm as cm
import matplotlib.colors as mcolors

from .config import WGS84, MAX_PIXELS


def load_as_wgs84(filepath, max_px=MAX_PIXELS):
    """Load and reproject raster to WGS84; return array, bounds, and nodata value."""
    with rasterio.open(filepath) as src:
        nodata = src.nodata
        already_wgs84 = src.crs and src.crs.to_epsg() == 4326

        if already_wgs84:
            scale  = max(1, max(src.width, src.height) / max_px)
            new_w  = max(1, int(src.width  / scale))
            new_h  = max(1, int(src.height / scale))
            arr    = src.read(1, out_shape=(new_h, new_w),
                              resampling=Resampling.nearest)
            new_tf = src.transform * src.transform.scale(scale, scale)
        else:
            tf, w, h = calculate_default_transform(
                src.crs, WGS84, src.width, src.height, *src.bounds
            )
            scale  = max(1, max(w, h) / max_px)
            new_w  = max(1, int(w / scale))
            new_h  = max(1, int(h / scale))
            new_tf = tf * tf.scale(scale, scale)
            arr    = np.empty((new_h, new_w), dtype=src.dtypes[0])
            reproject(
                source=rasterio.band(src, 1),
                destination=arr,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=new_tf,
                dst_crs=WGS84,
                resampling=Resampling.nearest,
            )

    lon_min, lat_min, lon_max, lat_max = array_bounds(new_h, new_w, new_tf)
    return arr, lon_min, lat_min, lon_max, lat_max, nodata


def arr_to_rgba_png_b64(arr, meta, nodata=None, layer_key=None, value_range=None,
                        active_classes=None):
    """Convert raster array to PNG base64 with discrete/continuous coloring.
    For continuous layers, value_range=(lo, hi) masks pixels outside [lo, hi] transparent.
    For discrete layers, active_classes (set/list of int class keys) hides unselected classes.
    Nodata pixels are always transparent."""
    h, w = arr.shape
    mask = (arr == nodata) if nodata is not None else np.zeros((h, w), dtype=bool)

    if meta["discrete"]:
        rgba = np.zeros((h, w, 4), dtype=np.uint8)

        # Code mapping for habitat layer (raster old codes → IUCN standard)
        code_mapping = {
            100: 1, 200: 2, 300: 3, 400: 4, 500: 5, 600: 6, 800: 8,
            900: 9, 1100: 10, 1200: 11, 1400: 14
        } if layer_key == "habitat" else {}

        active_set = set(active_classes) if active_classes is not None else None

        for val, (_, hex_c) in meta["categories"].items():
            if not (isinstance(hex_c, str) and len(hex_c) == 7 and hex_c[0] == "#"):
                continue
            # Skip classes not in active_set
            if active_set is not None and val not in active_set:
                continue
            r = int(hex_c[1:3], 16)
            g = int(hex_c[3:5], 16)
            b = int(hex_c[5:7], 16)

            pixel_mask = arr == val
            if code_mapping:
                for old_code, new_code in code_mapping.items():
                    if new_code == val:
                        pixel_mask |= (arr == old_code)

            rgba[pixel_mask] = [r, g, b, 210]
        rgba[mask] = [0, 0, 0, 0]
    else:
        cmap = cm.get_cmap(meta["colormap"])
        vmin, vmax = meta["vmin"], meta["vmax"]
        if vmin == vmax:
            vmax = vmin + 1
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
        rgba = (cmap(norm(arr.astype(float))) * 255).astype(np.uint8)
        rgba[..., 3] = 200
        rgba[mask, 3] = 0
        if value_range is not None:
            lo, hi = value_range
            rgba[(arr < lo) | (arr > hi), 3] = 0

    img = Image.fromarray(rgba, "RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
