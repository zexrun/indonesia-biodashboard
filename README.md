# Indonesia Biodiversity GIS Map

Interactive web dashboard for visualizing Indonesia's conservation priority, species richness, IUCN habitat classification, and invasive alien species (IAS) data on an interactive map.

## Features

- **5 Raster Layers** — Conservation Priority Ranking, Species Richness Index, IUCN Habitat Classification, IAS TNUK (*Arenga obtusifolia*), IAS TNB (*Vachellia nilotica*)
- **Layer Controls** — toggle on/off, opacity slider, value range filter, drag-to-reorder
- **Habitat Filter** — select/deselect specific IUCN habitat classes per layer
- **IAS Layer Focus** — dedicated focus button to auto-zoom to TNUK or TNB bounding box
- **Province Focus** — zoom to any of 34 provinces, mask raster to province boundary
- **Location Search** — search from 536 preloaded locations (34 provinces + 502 districts) with real-time filter; Nominatim API fallback
- **AI Assistant (Asisten Konservasi)** — conservation chatbot powered by OpenAI GPT-4o-mini; automatically receives active layer context and pinned location data; responds in the user's language (Indonesian or English); renders markdown (bold, italic, lists)
- **Basemap** — switch between OpenStreetMap, Carto Light, Carto Dark
- **Pin Location** — click anywhere on the map to drop a pin; displays coordinates, province/district, and pixel values for all active layers (discrete layers show color dot + class name)
- **Scale Bar** — real-time map scale indicator (bottom-left), snaps to nice km/m values, repositions when sidebar collapses
- **Dynamic Legend** — pill selector when multiple layers active; continuous layers show gradient + interpretation table; discrete layers show color swatches
- **Zoom Controls** — in/out buttons (clientside, no server round-trip)
- **Reset All** — resets all layer toggles, opacity, range filters, basemap, and province focus in one click
- **Settings Modal** — basemap selector + About section with researcher info and data sources

## Data Sources

| Layer | Key | Source |
|-------|-----|--------|
| Conservation Priority | `ranked` | Jung et al. 2021 — [DOI:10.1038/s41559-021-01528-7](https://doi.org/10.1038/s41559-021-01528-7) |
| Species Richness | `mollweide` | Indonesia 10km Mollweide species richness index |
| Habitat Classification | `habitat` | Jung et al. 2020 — [DOI:10.1038/s41597-020-00599-8](https://doi.org/10.1038/s41597-020-00599-8) |
| IAS TNUK | `ias_ujungkulon` | Angga Yudaputra, Ph.D. (BRIN) — *Arenga obtusifolia*, Taman Nasional Ujung Kulon |
| IAS TNB | `ias_baluran` | Angga Yudaputra, Ph.D. (BRIN) — *Vachellia nilotica*, Taman Nasional Baluran |
| Admin Boundaries | GADM | [GADM v4.1](https://gadm.org) — Indonesia (IDN) levels 0–2 |

## Requirements

- Python 3.9+
- dash >= 4.1.0
- plotly >= 6.6.0
- rasterio >= 1.5.0
- geopandas >= 1.1.3
- openai >= 1.0.0
- numpy, requests, python-dotenv

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Setup

Copy `.env.example` to `.env` and fill in your API key:

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-proj-your-key-here
OPENAI_MODEL=gpt-4o-mini   # optional, default: gpt-4o-mini
```

## Data Setup

Place the following raster files inside the `data/` folder:

```
data/
├── INDONESIA_minshort_speciestargets_biome.id_withPA_esh10km_repruns10_ranked_masked.tif
├── Indonesia_Mollweid_10km_masked.tif
├── indonesia_iucn_habitatclassification_composite_lvl1_ver004_masked.tif
├── arenga_obtusifolia_ujungkulon.tif
└── vachellia_nilotica_baluran.tif
```

Place GADM shapefiles under the project root (app auto-discovers `gadm41_IDN_*.shp` recursively):

```
<project_root>/
└── map/
    ├── gadm41_IDN_0.shp
    ├── gadm41_IDN_1.shp
    └── gadm41_IDN_2.shp
```

## Running the App

```bash
python run_v2.py
```

App will be available at `http://localhost:8050`. First startup pre-loads all rasters and shapefiles into memory (~17 seconds with province mask cache).

> **Note:** On the very first run, province masks are computed and saved to `cache/masks/` (~63 seconds). Subsequent runs load from disk (~46ms).

## Project Structure

```
app_v2/
├── app_instance.py   # Dash app instance
├── ai_search.py      # AI chatbot — OpenAI GPT-4o-mini integration
├── callbacks.py      # All server-side and clientside callbacks
├── cache.py          # Startup data loading, pixel sampling, geocoding helpers
├── config.py         # File paths, LAYER_META, color scales, category definitions
├── config_cache.py   # Cache settings (CACHE_ENABLED, CACHE_DIR)
├── gadm.py           # Shapefile → lat/lon boundary traces
├── layout.py         # App layout definition
├── legend.py         # Legend figure builder
├── layer_widgets.py  # Layer widget card builder (per-layer controls)
├── mask_cache.py     # Province mask disk cache (170 masks × .npy)
├── perf_timing.py    # Performance timing logger → perf_log.jsonl
└── raster.py         # Raster I/O, colorization, PNG overlay generation
assets/
├── map_click.js        # MapLibre click → dcc.Store; pin marker update via Plotly.restyle
├── drag_reorder.js     # Drag-to-reorder layer slots → window._layerDragOrder
├── scale_bar.js        # Real-time scale bar using Web Mercator formula
├── chat_drag.js        # AI chat panel drag-to-reposition
├── disable_dblclick.js # Disable Plotly double-click zoom
├── responsive.css      # Responsive layout adjustments
└── style.css           # Main stylesheet (GMW Design System tokens)
data/                   # Raster TIF files (not tracked in git)
map/                    # GADM shapefiles (not tracked in git)
cache/                  # Province mask cache — auto-generated (not tracked in git)
.env.example            # Template environment variables
requirements.txt        # Python dependencies
run_v2.py               # Entry point
```

## Architecture Notes

- Rasters are reprojected to WGS84 at startup and cached as base64 PNG overlays
- Map is rendered via Plotly `go.Figure` with `layout.map` image overlays (MapLibre GL JS)
- Opacity updates are applied directly to MapLibre via clientside callback — no Plotly figure rebuild
- Map clicks are captured by a JS polling loop (workaround for Dash's lack of native MapLibre click events)
- Province mask cache stores 170 precomputed binary masks (34 provinces × 5 layers) as `.npy` files
- Scale bar uses the Web Mercator formula: `(40075016.686 × cos(lat)) / (512 × 2^zoom)` meters-per-pixel
- AI assistant injects active layer state and pinned location data into every query as structured context

---

## How the App Works

### 1. Startup — Cache Initialization (`cache.py → initialize()`)

```
[1/3] Raster Layers
  For each TIF file:
    rasterio.open() → reproject to WGS84 → downsample to max 700px
    → numpy array → colorize to RGBA → encode as base64 PNG
    → store in LAYER_CACHE[key] = {img_b64, arr, bounds, nodata}

[2/3] GADM Shapefiles
  For each admin level (0, 1, 2):
    geopandas.read_file() → extract lat/lon coordinate arrays
    → store in GADM_CACHE[level] = {lats, lons}
    → store GeoDataFrame in GADM_GDF[level] (for spatial queries)

[3/3] Province Masks (disk cache)
  Check cache/masks/ for valid .npy files (CRC32 hash validation)
  → HIT:  load 170 masks from disk (~46ms)
  → MISS: compute 170 masks via spatial intersection (~63s) → save to disk
```

### 2. Map Render — `update_map` Callback

```
Any control changes (toggle, range, province, basemap, layer order...)
  → if triggered by opacity slider → return no_update (handled clientside)
  → determine visible layers from toggle state + global toggle + layer order
  → determine map center/zoom:
       search result?   → use search lat/lon/zoom
       province active? → bbox centroid + log2 zoom
       default          → Indonesia centroid, zoom 3.8
  → for each visible layer:
       province active?  → use MASKED_PNG_CACHE[province][layer]
       range filter?     → re-colorize arr with new vmin/vmax
       habitat filter?   → re-colorize arr with selected classes only
       default           → use LAYER_CACHE[key]["img_b64"]
  → build Plotly figure → return figure + legend_content + selected_legend_layer
```

### 3. Pin Location Flow

```
Step A — JS (map_click.js):
  MapLibre 'click' event → window._mapClickCoords
  dcc.Interval (200ms) polls → writes to dcc.Store("map-click-coords")

Step B — Server (update_pinned_store):
  → point_to_admin(lat, lon) → province + district via GADM_GDF spatial query
  → sample_pixel_text(lat, lon, key) for each active layer
  → discrete layers: color dot + class name + numeric code
  → write to dcc.Store("pinned-data")

Step C — JS (map_click.js → updatePin):
  → Plotly.restyle() updates pin marker position directly in browser

Step D — Server (render_pinned_info):
  → render pin panel: coordinates, admin info, per-layer values
```

### 4. AI Assistant Flow (`ai_search.py`)

```
User sends message
  → detect language (English/Indonesian) → prepend explicit lang instruction
  → extract_locations(query) via GPT-4o-mini → list of location names
  → for each location: geocode + sample all layer pixel values
  → inject: active layer state (from Dash State) + pin context + location data
  → call GPT-4o-mini with system prompt + last 6 chat history messages
  → response rendered as dcc.Markdown (bold, italic, lists displayed correctly)
```

### 5. Data Flow Summary

```
Disk (TIF + SHP)
    │
    ▼ startup only (~17s with cache)
  cache.py initialize()
    ├── LAYER_CACHE       ← numpy arrays + base64 PNGs
    ├── GADM_CACHE        ← lat/lon arrays for boundary traces
    ├── GADM_GDF          ← GeoDataFrames for spatial queries
    └── MASKED_PNG_CACHE  ← base64 PNGs per (province × layer)
          │
          ▼ per interaction
        Callbacks
          ├── update_map            → figure + legend
          ├── update_pinned_store   → pin data (coords, admin, layer values)
          ├── render_pinned_info    → pin panel UI
          ├── update_opacity_store  → opacity list → clientside MapLibre update
          ├── handle_location_search → geocode → reposition map
          └── chat_call_ai          → GPT-4o-mini → markdown response
```

---

## Acknowledgement

This project was developed as part of an undergraduate thesis (Tugas Akhir) at Universitas Telkom, Fakultas Informatika, Program Studi Sarjana Informatika.

| | |
|--|--|
| **Researcher** | Muhammad Rifqy Khuzaini (1301223473) |
| **Supervisors** | Rio Nurtantyana · Tri Atmaja |
| **Institution** | Universitas Telkom, Bandung, Indonesia |
| **Year** | 2026 |

The IAS spatial data layers were developed by **Angga Yudaputra, Ph.D.**, a researcher at the National Research and Innovation Agency (BRIN). This study was supported by the Asia-Pacific Network for Global Change Research (APN) No. CRRP2025-04MY-Setiawan.

---

## License

Data licenses apply per source. See individual dataset DOIs for terms of use.
