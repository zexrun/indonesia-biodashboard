"""
Startup loading + spatial query helpers.

Memuat semua raster & shapefile GADM sekali saat startup dan menyimpan hasilnya
di cache modul-level agar dapat diakses cepat oleh callbacks.
"""

import os
import math
import warnings
from threading import Lock
import numpy as np
import geopandas as gpd
from shapely.geometry import Point

from .config import FILES, LAYER_META, GADM_DIR, GADM_LEVELS, SIMPLIFY_TOL
from .raster import load_as_wgs84, arr_to_rgba_png_b64
from .gadm import gadm_to_latlons
from .utils_mask import build_province_mask, apply_mask_to_arr
from .mask_cache import ProvinceMaskCache, _log as _cache_log
from .config_cache import CACHE_ENABLED, CACHE_DIR, CACHE_VALIDATION_ENABLED

LAYER_CACHE      = {}   # {key: {img_b64, arr, bounds, nodata}}
GADM_CACHE       = {}   # {level: {lats, lons, n_features}}
GADM_GDF         = {}   # {level: GeoDataFrame} untuk spatial query
GADM_GEOJSON     = {}   # {level: GeoJSON FeatureCollection dict} untuk map.layers
PROVINCE_OPTIONS = []   # opsi dropdown provinsi
PROVINCE_MASKS   = {}   # {(province_name, layer_key): bool ndarray}
MASKED_PNG_CACHE = {}   # {(province_name, layer_key): base64 PNG str}

# Preloaded location list for Find Location modal
# Each entry: {"name": str, "type": "provinsi"|"kabkota", "sub": str (provinsi parent)}
LOCATION_LIST    = []

_INIT_LOCK = Lock()

# Map old placeholder codes (100-1400) to IUCN standard codes (1-14)
CODE_MAPPING = {
    100: 1, 200: 2, 300: 3, 400: 4, 500: 5, 600: 6, 800: 8,
    900: 9, 1100: 10, 1200: 11, 1400: 14,
}


def initialize():
    """Jalankan sekali saat startup untuk populate semua cache."""
    with _INIT_LOCK:
        suppress_output = bool(os.getenv("_APP_CACHE_INITIALIZED"))
        _do_initialize(suppress_output=suppress_output)
        os.environ["_APP_CACHE_INITIALIZED"] = "1"


def _do_initialize(suppress_output=False):
    import time
    start_time = time.time()

    if not suppress_output:
        print("\n" + "="*70)
        print("  >> INITIALIZING APPLICATION CACHE")
        print("="*70 + "\n")

    if not suppress_output:
        print("[1/3] RASTER LAYERS")
        print("-" * 70)
    for key, filepath in FILES.items():
        if not suppress_output:
            print(f"  Loading [{key}]...", end=" ", flush=True)
        arr, lon_min, lat_min, lon_max, lat_max, nodata = load_as_wgs84(filepath)
        img_b64 = arr_to_rgba_png_b64(arr, LAYER_META[key], nodata, layer_key=key)
        LAYER_CACHE[key] = {
            "img_b64": img_b64,
            "arr":     arr,
            "bounds":  (lon_min, lat_min, lon_max, lat_max),
            "nodata":  nodata,
        }
        if not suppress_output:
            print("OK")
            print(f"    Shape: {arr.shape} | Bounds: [{lon_min:.2f}, {lat_min:.2f}] to [{lon_max:.2f}, {lat_max:.2f}]")
    if not suppress_output:
        print()

    if not suppress_output:
        print("[2/3] GADM SHAPEFILES")
        print("-" * 70)
    for lvl, info in GADM_LEVELS.items():
        path = os.path.join(GADM_DIR, info["file"])
        if not suppress_output:
            print(f"  Loading Level {lvl}: {info['label']}...", end=" ", flush=True)
        gdf = gpd.read_file(path)
        lats, lons = gadm_to_latlons(gdf, simplify_tol=SIMPLIFY_TOL[lvl])
        GADM_CACHE[lvl] = {"lats": lats, "lons": lons, "n_features": len(gdf)}
        GADM_GDF[lvl]   = gdf
        GADM_GEOJSON[lvl] = gdf.__geo_interface__
        if not suppress_output:
            print("OK")
            print(f"    {len(gdf)} features | {len(lats)} coordinates")
    if not suppress_output:
        print()

    PROVINCE_OPTIONS.append({"label": "Semua Provinsi", "value": "__all__"})
    if 1 in GADM_GDF:
        names = sorted(GADM_GDF[1]["NAME_1"].dropna().unique().tolist())
        PROVINCE_OPTIONS.extend({"label": n, "value": n} for n in names)
        for n in names:
            LOCATION_LIST.append({"name": n, "type": "provinsi", "sub": ""})
    if 2 in GADM_GDF:
        gdf2 = GADM_GDF[2]
        for _, row in gdf2.sort_values(["NAME_1", "NAME_2"]).iterrows():
            name2  = row.get("NAME_2", "") or ""
            type2  = row.get("TYPE_2",  "") or ""
            prov   = row.get("NAME_1",  "") or ""
            if name2:
                LOCATION_LIST.append({
                    "name":  f"{type2} {name2}".strip() if type2 else name2,
                    "type":  "kabkota",
                    "sub":   prov,
                    "raw":   name2,
                })

    if not suppress_output:
        print("[3/3] PROVINCE MASKS")
        print("-" * 70)
    gdf1 = GADM_GDF.get(1)
    if gdf1 is not None:
        prov_names = [opt["value"] for opt in PROVINCE_OPTIONS if opt["value"] != "__all__"]
        layer_keys = list(LAYER_CACHE.keys())
        total_masks = len(prov_names) * len(layer_keys)

        _mask_milestone_start = time.time()
        if not suppress_output:
            print(f"[STARTUP_MILESTONE] START_MASK_COMPUTATION @ {_mask_milestone_start - start_time:.2f}s")

        cache_mgr = None
        loaded_masks = {}

        if CACHE_ENABLED:
            cache_mgr = ProvinceMaskCache(cache_dir=CACHE_DIR)
            if not suppress_output:
                _cache_log("CACHE", "Validating cache...")
            data_hash = cache_mgr.compute_data_hash(gdf1, FILES) if CACHE_VALIDATION_ENABLED else "no-validation"

            if CACHE_VALIDATION_ENABLED and cache_mgr.is_cache_valid(data_hash):
                if not suppress_output:
                    _cache_log("CACHE", "Cache status: VALID — loading from disk")
                loaded_masks = cache_mgr.load_all_masks(prov_names, layer_keys)
            else:
                if not suppress_output:
                    _cache_log("CACHE", "Cache status: INVALID — will recompute and cache")
                data_hash = cache_mgr.compute_data_hash(gdf1, FILES)

        # Compute missing masks (all on first run, zero on subsequent runs)
        computed_masks = {}
        missing = [(p, lk) for p in prov_names for lk in layer_keys
                   if loaded_masks.get((p, lk)) is None]

        if not suppress_output and missing:
            print(f"  Computing {len(missing)}/{total_masks} masks...", end=" ", flush=True)

        for i, (pname, layer_key) in enumerate(missing):
            lc = LAYER_CACHE[layer_key]
            h, w = lc["arr"].shape
            mask = build_province_mask(pname, gdf1, h, w, lc["bounds"])
            computed_masks[(pname, layer_key)] = mask
            if not suppress_output and (i + 1) % 30 == 0:
                print(f"\n    Progress: {i+1}/{len(missing)} masks computed...", end=" ", flush=True)

        if not suppress_output and missing:
            print("OK")

        # Merge loaded + computed into PROVINCE_MASKS, build MASKED_PNG_CACHE
        for pname in prov_names:
            for layer_key, lc in LAYER_CACHE.items():
                mask = loaded_masks.get((pname, layer_key))
                if mask is None:
                    mask = computed_masks.get((pname, layer_key))
                if mask is None:
                    mask = np.zeros(lc["arr"].shape, dtype=bool)
                PROVINCE_MASKS[(pname, layer_key)] = mask
                masked_arr = apply_mask_to_arr(lc["arr"], mask, lc["nodata"])
                MASKED_PNG_CACHE[(pname, layer_key)] = arr_to_rgba_png_b64(
                    masked_arr, LAYER_META[layer_key], lc["nodata"], layer_key=layer_key
                )

        # Persist newly computed masks to disk
        if CACHE_ENABLED and cache_mgr is not None and computed_masks:
            if not suppress_output:
                _cache_log("CACHE", f"Saving {len(computed_masks)} new masks to cache...")
            cache_mgr.save_all_masks(computed_masks, data_hash)

        if not suppress_output:
            n_loaded   = len(loaded_masks) - sum(1 for v in loaded_masks.values() if v is None)
            n_computed = len(computed_masks)
            print(f"    {len(PROVINCE_MASKS)} masks ready "
                  f"(loaded from cache: {n_loaded}, computed: {n_computed})")
            _mask_milestone_end = time.time()
            print(f"[STARTUP_MILESTONE] END_MASK_COMPUTATION @ {_mask_milestone_end - start_time:.2f}s "
                  f"(mask phase: {_mask_milestone_end - _mask_milestone_start:.2f}s)")
    else:
        if not suppress_output:
            print("  WARNING: GADM Level 1 not found - skipping province masks")
    if not suppress_output:
        print()

        elapsed = time.time() - start_time
        print("="*70)
        print(f"  INIT COMPLETE ({elapsed:.2f}s)")
        print("="*70 + "\n")


# ─── Cache-dependent query helpers ───────────────────────────────────────────

def sample_pixel_text(lat, lon, layer_key):
    """Sample raster pixel at (lat, lon); return formatted text or empty string."""
    cache = LAYER_CACHE[layer_key]
    meta  = LAYER_META[layer_key]
    arr   = cache["arr"]
    lon_min, lat_min, lon_max, lat_max = cache["bounds"]
    nodata = cache["nodata"]
    h, w   = arr.shape

    col = int((lon - lon_min) / (lon_max - lon_min) * w)
    row = int((lat_max - lat) / (lat_max - lat_min) * h)

    if not (0 <= row < h and 0 <= col < w):
        return ""

    val = arr[row, col]
    if nodata is not None and val == nodata:
        return ""

    if meta["discrete"]:
        int_val = int(val)
        # Apply code mapping for habitat layer (handle old placeholder codes)
        if layer_key == "habitat":
            mapped_val = CODE_MAPPING.get(int_val, int_val)
        else:
            mapped_val = int_val

        label = meta["categories"].get(mapped_val, ("Unknown",))[0]
        return f"Nilai: {mapped_val}<br>Kelas: {label}"
    return f"Nilai: {val:.1f}"


def point_to_admin(lat, lon):
    """
    Koordinat (lat, lon) → {provinsi, wilayah, tipe_wilayah} via spatial index GADM.

    Return "Tidak diketahui" jika titik di luar Indonesia.
    """
    result = {"provinsi": "Tidak diketahui", "wilayah": "Tidak diketahui", "tipe_wilayah": ""}
    pt = Point(lon, lat)

    def _query_contains(gdf, point, fallback_deg=1.0):
        """bbox candidates → exact contains; fallback ke poligon terdekat (handle titik di laut dekat pantai)."""
        idx = list(gdf.sindex.query(point))
        if idx:
            subset = gdf.iloc[idx]
            exact  = subset[subset.contains(point)]
            if not exact.empty:
                return exact
        buf_idx = list(gdf.sindex.query(point.buffer(fallback_deg)))
        if not buf_idx:
            return gdf.iloc[:0]
        subset  = gdf.iloc[buf_idx]
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")
            nearest = subset.distance(point).idxmin()
        return subset.loc[[nearest]]

    if 1 in GADM_GDF:
        hits = _query_contains(GADM_GDF[1], pt)
        if not hits.empty:
            result["provinsi"] = hits.iloc[0].get("NAME_1", "?")

    if 2 in GADM_GDF:
        hits = _query_contains(GADM_GDF[2], pt)
        if not hits.empty:
            result["wilayah"]      = hits.iloc[0].get("NAME_2", "?")
            result["tipe_wilayah"] = hits.iloc[0].get("TYPE_2", "")

    return result


def get_masked_png(province_name, layer_key):
    """Return pre-computed masked base64 PNG, or None if not cached."""
    return MASKED_PNG_CACHE.get((province_name, layer_key))


def get_province_mask(province_name, layer_key):
    """Return pre-computed bool mask ndarray, or None."""
    return PROVINCE_MASKS.get((province_name, layer_key))


def get_province_view(province_name):
    """
    Hitung (center_lat, center_lon, zoom) dari bounding box provinsi.

    Return (None, None, None) jika provinsi tidak ditemukan.
    """
    if 1 not in GADM_GDF:
        return None, None, None
    gdf1 = GADM_GDF[1]
    rows = gdf1[gdf1["NAME_1"] == province_name]
    if rows.empty:
        return None, None, None
    lon_min, lat_min, lon_max, lat_max = rows.total_bounds
    center_lat = (lat_min + lat_max) / 2
    center_lon = (lon_min + lon_max) / 2
    max_span   = max(lon_max - lon_min, lat_max - lat_min)
    zoom       = math.log2(360 / max_span) + 0.3
    zoom       = max(2.0, min(zoom, 10.0))
    return center_lat, center_lon, zoom


def search_location(query):
    """
    Search lokasi: coba GADM lokal dulu, fallback ke Nominatim API.
    Return: {"lat": float, "lon": float, "zoom": float, "label": str} atau None.
    """
    q = query.strip() if query else ""
    if not q or len(q) < 2:
        return None

    # Layer 1: search provinsi (NAME_1) — exact match first, then substring
    if 1 in GADM_GDF:
        gdf1 = GADM_GDF[1]
        exact = gdf1[gdf1["NAME_1"].str.lower() == q.lower()]
        hits  = exact if not exact.empty else gdf1[gdf1["NAME_1"].str.contains(q, case=False, na=False)]
        if not hits.empty:
            lat, lon, zoom = get_province_view(hits.iloc[0]["NAME_1"])
            return {"lat": lat, "lon": lon, "zoom": zoom, "label": hits.iloc[0]["NAME_1"]}

    # Layer 2: search kabupaten/kota (NAME_2) — exact match first, then substring
    if 2 in GADM_GDF:
        gdf2  = GADM_GDF[2]
        exact = gdf2[gdf2["NAME_2"].str.lower() == q.lower()]
        hits  = exact if not exact.empty else gdf2[gdf2["NAME_2"].str.contains(q, case=False, na=False)]
        if not hits.empty:
            row = hits.iloc[0]
            bounds = hits.iloc[[0]].total_bounds
            lon_min, lat_min, lon_max, lat_max = bounds
            center_lat = (lat_min + lat_max) / 2
            center_lon = (lon_min + lon_max) / 2
            max_span = max(lon_max - lon_min, lat_max - lat_min)
            zoom = max(6.0, min(math.log2(360 / max_span) + 0.3, 12.0))
            return {"lat": center_lat, "lon": center_lon, "zoom": zoom,
                    "label": f"{row['TYPE_2']} {row['NAME_2']}, {row['NAME_1']}"}

    # Layer 3: Nominatim fallback
    try:
        import requests
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "countrycodes": "id", "format": "json", "limit": 1},
            headers={"User-Agent": "IndonesiaRasterMap/1.0"},
            timeout=3,
        )
        results = resp.json()
        if results:
            r = results[0]
            return {"lat": float(r["lat"]), "lon": float(r["lon"]),
                    "zoom": 10.0, "label": r.get("display_name", q)}
    except Exception:
        pass

    return None
