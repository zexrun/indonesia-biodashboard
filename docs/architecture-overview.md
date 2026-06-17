# Architecture Overview — Indonesia BioDashboard

## Backend Architecture

**Framework:** Plotly Dash (berjalan di atas Flask) — semua logic ada di **Dash callbacks** di `app_v2/callbacks.py`. Tidak ada separate API server (tidak ada FastAPI/Express/dll).

**Pola:** Single-process Python server. Semua callback berjalan di thread yang sama kecuali `background_callback` — aplikasi ini tidak menggunakan background callback untuk proses berat seperti AI query.

---

## Data Storage

Semua file disimpan **lokal** di mesin yang menjalankan app:

| File | Ukuran |
|------|--------|
| `indonesia_iucn_habitatclassification_composite_lvl1_ver004_masked.tif` | **1,857 MB** |
| `vachellia_nilotica_baluran.tif` | 14.50 MB |
| `arenga_obtusifolia_ujungkulon.tif` | 1.03 MB |
| `INDONESIA_minshort_...ranked_masked.tif` | 0.19 MB |
| `Indonesia_Mollweid_10km.tif` | 0.19 MB |
| `gadm41_IDN_2.shp` | 40.24 MB |
| `gadm41_IDN_1.shp` | 24.50 MB |
| `gadm41_IDN_0.shp` | 22.46 MB |

**Setelah startup**, semua raster di-load ke RAM sebagai numpy array + base64 PNG. Callbacks tidak pernah baca disk lagi.

---

## Current Bottlenecks

| Titik | Keterangan |
|-------|-----------|
| **Startup** | Loading habitat TIF 1.8 GB + province mask pre-computation untuk semua provinsi × 5 layer — bisa memakan waktu beberapa menit |
| **AI query** | `query_ai()` dipanggil secara **synchronous** di dalam callback — server Dash ter-block selama request ke OpenAI berlangsung (rata-rata 2–5 detik) |
| **Province filter** | Re-colorize array numpy saat range/habitat filter berubah dilakukan di-request-time, tidak di-cache |
| **Memory** | Habitat TIF 1.8 GB di-load penuh ke RAM |

**Observasi yang sudah diketahui:**
- Opacity slider sempat tidak responsif (sudah diperbaiki)
- Bubble chat user tidak langsung muncul saat enter (sudah diperbaiki)

---

## Deployment Target

Saat ini: **localhost** (`http://0.0.0.0:8050`, debug mode).

Belum ada konfigurasi untuk production deployment (tidak ada Gunicorn, Nginx, Docker, atau environment variable production).

---

## Expected Users

Belum ada konfigurasi multi-user. Dash default Flask dev server **tidak thread-safe untuk concurrent users** — cocok untuk **1 user sekaligus** (demo/penelitian). Jika perlu multi-user, perlu Gunicorn dengan multiple workers.

---

## Monitoring

**Belum ada.** Tidak ada:
- Structured logging (hanya `print()`)
- Profiling (tidak ada `cProfile` atau APM)
- Metrics (tidak ada Prometheus/Grafana)
- Error tracking (tidak ada Sentry)

Satu-satunya observability adalah output terminal dari `print()` di callbacks.
