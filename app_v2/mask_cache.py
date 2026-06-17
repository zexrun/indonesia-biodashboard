"""
Province mask disk cache manager.

Saves/loads 170 boolean mask arrays (.npy) to avoid recomputing
GeoPandas unary_union rasterizations on every startup.

First run:  compute all masks, save to cache/masks/
Next runs:  load from disk in ~2s instead of ~63s
"""

import os
import time
import zlib
from datetime import datetime

import numpy as np


# ── Logging helpers ──────────────────────────────────────────────────────────

def _ts():
    now = datetime.now()
    return now.strftime("%H:%M:%S.") + f"{now.microsecond // 1000:03d}"


def _log(tag, msg):
    print(f"[{_ts()}] [{tag}] {msg}", flush=True)


# ── ProvinceMaskCache ────────────────────────────────────────────────────────

class ProvinceMaskCache:
    """Disk cache for province×layer boolean mask arrays."""

    def __init__(self, cache_dir="./cache/masks"):
        self.cache_dir = os.path.abspath(cache_dir)
        self.data_hash_file = os.path.join(self.cache_dir, "data_hash.txt")
        self._hits = 0
        self._misses = 0
        self.is_initialized = self._init_dir()

    # ── Setup ────────────────────────────────────────────────────────────────

    def _init_dir(self):
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            test = os.path.join(self.cache_dir, ".write_test")
            with open(test, "w") as f:
                f.write("ok")
            os.remove(test)
            return True
        except Exception as e:
            _log("CACHE_ERROR", f"Cannot initialize cache dir {self.cache_dir}: {e}")
            return False

    # ── Key / path ───────────────────────────────────────────────────────────

    def get_cache_key(self, province_name, layer_name):
        """Return full path to .npy file for (province, layer)."""
        key = f"{province_name}_{layer_name}".lower().replace(" ", "_")
        return os.path.join(self.cache_dir, f"{key}.npy")

    # ── Hash ─────────────────────────────────────────────────────────────────

    def compute_data_hash(self, provinces_gdf, raster_files: dict) -> str:
        """
        Stable hash of source data.
        Combines geometry CRC32 + raster mtime + layer names.
        Returns hex string.
        """
        parts = []

        # Geometry checksum — CRC32 over WKB bytes of all province geometries
        try:
            wkb_bytes = b"".join(
                geom.wkb for geom in provinces_gdf.geometry if geom is not None
            )
            parts.append(f"geom:{zlib.crc32(wkb_bytes) & 0xFFFFFFFF:08x}")
        except Exception as e:
            _log("CACHE_WARN", f"Geometry hash failed: {e}")
            parts.append("geom:error")

        # Raster mtime + layer names
        for key, path in sorted(raster_files.items()):
            try:
                mtime = int(os.path.getmtime(path) * 1000)
                parts.append(f"{key}:{mtime}")
            except Exception:
                parts.append(f"{key}:missing")

        combined = "|".join(parts)
        return f"{zlib.crc32(combined.encode()) & 0xFFFFFFFF:08x}"

    # ── Validation ───────────────────────────────────────────────────────────

    def is_cache_valid(self, current_hash: str) -> bool:
        """True if stored hash matches current_hash."""
        if not self.is_initialized:
            return False
        try:
            with open(self.data_hash_file, "r") as f:
                stored = f.read().strip()
            return stored == current_hash
        except FileNotFoundError:
            return False
        except Exception as e:
            _log("CACHE_WARN", f"Hash read error: {e}")
            return False

    def _save_hash(self, data_hash: str):
        try:
            with open(self.data_hash_file, "w") as f:
                f.write(data_hash)
        except Exception as e:
            _log("CACHE_WARN", f"Cannot save hash: {e}")

    # ── Save / Load single ───────────────────────────────────────────────────

    def save_mask(self, province_name, layer_name, mask_array) -> bool:
        """Save one mask to disk. Returns True on success."""
        if not self.is_initialized:
            return False
        path = self.get_cache_key(province_name, layer_name)
        try:
            np.save(path, mask_array)
            size_mb = os.path.getsize(path) / 1_048_576
            if os.environ.get("_CACHE_VERBOSE"):
                _log("CACHE", f"Saved: {province_name}/{layer_name} ({size_mb:.1f}MB)")
            return True
        except OSError as e:
            if e.errno == 28:  # ENOSPC
                _log("CACHE_ERROR", f"Disk full — cannot save {province_name}/{layer_name}")
            else:
                _log("CACHE_ERROR", f"Save failed {province_name}/{layer_name}: {e}")
            return False
        except Exception as e:
            _log("CACHE_ERROR", f"Save failed {province_name}/{layer_name}: {e}")
            return False

    def load_mask(self, province_name, layer_name):
        """Load one mask from disk. Returns array or None."""
        path = self.get_cache_key(province_name, layer_name)
        if not os.path.exists(path):
            self._misses += 1
            return None
        try:
            arr = np.load(path)
            self._hits += 1
            return arr
        except Exception as e:
            _log("CACHE_WARN", f"Corrupt cache file {path}: {e} — will recompute")
            self._misses += 1
            return None

    # ── Save / Load bulk ─────────────────────────────────────────────────────

    def save_all_masks(self, mask_dict: dict, data_hash: str):
        """
        Save all masks from {(province, layer): ndarray} dict.
        Saves data_hash afterwards to mark cache as valid.
        Returns (count_saved, total_mb).
        """
        if not self.is_initialized:
            _log("CACHE_WARN", "Cache not initialized — skipping save")
            return 0, 0.0

        _log("CACHE", f"Saving {len(mask_dict)} masks to {self.cache_dir} ...")
        t0 = time.time()
        saved = 0
        total_bytes = 0

        for (province, layer), arr in mask_dict.items():
            ok = self.save_mask(province, layer, arr)
            if ok:
                saved += 1
                total_bytes += os.path.getsize(self.get_cache_key(province, layer))

        # Save hash only after all masks written
        self._save_hash(data_hash)

        total_mb = total_bytes / 1_048_576
        elapsed = time.time() - t0
        _log("CACHE", f"Saved {saved}/{len(mask_dict)} masks ({total_mb:.1f}MB) in {elapsed:.2f}s")
        return saved, total_mb

    def load_all_masks(self, provinces_list: list, layers_list: list) -> dict:
        """
        Load all (province, layer) combinations.
        Returns dict where missing files map to None.
        """
        t0 = time.time()
        total = len(provinces_list) * len(layers_list)
        result = {}
        loaded = 0
        total_bytes = 0

        for province in provinces_list:
            for layer in layers_list:
                arr = self.load_mask(province, layer)
                result[(province, layer)] = arr
                if arr is not None:
                    loaded += 1
                    total_bytes += arr.nbytes

        elapsed = time.time() - t0
        total_mb = total_bytes / 1_048_576
        _log("CACHE", f"Loaded {loaded}/{total} masks ({total_mb:.1f}MB) in {elapsed*1000:.0f}ms")
        return result

    # ── Maintenance ──────────────────────────────────────────────────────────

    def clear_cache(self):
        """Delete all .npy files and hash. Logs what was removed."""
        if not os.path.isdir(self.cache_dir):
            return
        files = [f for f in os.listdir(self.cache_dir) if f.endswith(".npy")]
        total_bytes = sum(
            os.path.getsize(os.path.join(self.cache_dir, f)) for f in files
        )
        for f in files:
            os.remove(os.path.join(self.cache_dir, f))
        if os.path.exists(self.data_hash_file):
            os.remove(self.data_hash_file)
        _log("CACHE", f"Cleared {len(files)} files, freed {total_bytes/1_048_576:.1f}MB")

    def get_cache_size(self) -> float:
        """Total size in MB of all .npy files in cache_dir."""
        if not os.path.isdir(self.cache_dir):
            return 0.0
        total = sum(
            os.path.getsize(os.path.join(self.cache_dir, f))
            for f in os.listdir(self.cache_dir)
            if f.endswith(".npy")
        )
        return total / 1_048_576

    def get_cache_stats(self, current_hash: str = None) -> dict:
        """Return dict with cache diagnostics."""
        if not os.path.isdir(self.cache_dir):
            return {"total_files": 0, "total_size_mb": 0.0, "cache_valid": False,
                    "last_update": None, "hit_rate": 0.0}

        files = [f for f in os.listdir(self.cache_dir) if f.endswith(".npy")]
        total_bytes = sum(
            os.path.getsize(os.path.join(self.cache_dir, f)) for f in files
        )

        last_update = None
        if files:
            newest = max(
                os.path.getmtime(os.path.join(self.cache_dir, f)) for f in files
            )
            last_update = datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M:%S")

        total_ops = self._hits + self._misses
        hit_rate = (self._hits / total_ops * 100) if total_ops > 0 else 0.0

        return {
            "total_files":   len(files),
            "total_size_mb": round(total_bytes / 1_048_576, 1),
            "cache_valid":   self.is_cache_valid(current_hash) if current_hash else None,
            "last_update":   last_update,
            "hit_rate":      round(hit_rate, 1),
        }
