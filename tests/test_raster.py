import numpy as np
import base64
import io
from PIL import Image


def _decode_rgba(b64_str):
    img_bytes = base64.b64decode(b64_str.split(",")[1])
    return np.array(Image.open(io.BytesIO(img_bytes)))


def test_value_range_masks_pixels_outside_range():
    """Pixels outside value_range must have alpha=0; pixels inside must have alpha>0."""
    from app_v2.raster import arr_to_rgba_png_b64

    arr = np.array([[10.0, 50.0, 90.0]])
    meta = {"discrete": False, "colormap": "viridis", "vmin": 0, "vmax": 100}

    b64 = arr_to_rgba_png_b64(arr, meta, value_range=(40, 60))
    rgba = _decode_rgba(b64)

    assert rgba[0, 0, 3] == 0,  "value=10 below range must be transparent"
    assert rgba[0, 2, 3] == 0,  "value=90 above range must be transparent"
    assert rgba[0, 1, 3] > 0,   "value=50 inside range must be opaque"


def test_no_value_range_shows_all_pixels():
    """Without value_range, all non-nodata pixels are opaque."""
    from app_v2.raster import arr_to_rgba_png_b64

    arr = np.array([[10.0, 50.0, 90.0]])
    meta = {"discrete": False, "colormap": "viridis", "vmin": 0, "vmax": 100}

    b64 = arr_to_rgba_png_b64(arr, meta)
    rgba = _decode_rgba(b64)

    assert rgba[0, 0, 3] > 0
    assert rgba[0, 1, 3] > 0
    assert rgba[0, 2, 3] > 0


def test_nodata_always_transparent():
    """Nodata pixels are transparent regardless of value_range."""
    from app_v2.raster import arr_to_rgba_png_b64

    NODATA = -9999.0
    arr = np.array([[NODATA, 50.0, 90.0]])
    meta = {"discrete": False, "colormap": "viridis", "vmin": 0, "vmax": 100}

    b64 = arr_to_rgba_png_b64(arr, meta, nodata=NODATA, value_range=(0, 100))
    rgba = _decode_rgba(b64)

    assert rgba[0, 0, 3] == 0, "nodata must be transparent even inside value_range"


def test_value_range_boundary_values_are_inclusive():
    """Boundary values (== lo, == hi) must be visible; only < lo or > hi is masked."""
    from app_v2.raster import arr_to_rgba_png_b64

    arr = np.array([[40.0, 60.0]])
    meta = {"discrete": False, "colormap": "viridis", "vmin": 0, "vmax": 100}
    b64 = arr_to_rgba_png_b64(arr, meta, value_range=(40, 60))
    rgba = _decode_rgba(b64)

    assert rgba[0, 0, 3] > 0, "value == lo must be visible (inclusive lower bound)"
    assert rgba[0, 1, 3] > 0, "value == hi must be visible (inclusive upper bound)"
