# Indonesia Biodiversity GIS Map

Interactive web dashboard for visualizing Indonesia's conservation priority, species richness, and habitat classification data on an interactive map.

## Features

- **5 Raster Layers** — Conservation Priority Ranking, Species Richness Index, IUCN Habitat Classification, IAS TNUK, IAS TNB
- **Layer Controls** — toggle, opacity slider, value range filter, drag-to-reorder
- **Habitat Filter** — select/deselect specific IUCN habitat classes
- **IAS Layer Focus** — auto-zoom ke area TNUK/TNB saat layer diaktifkan, dengan tombol Fokus
- **Province Focus** — zoom to any province, mask raster to province boundary, view statistics
- **Location Search** — search by province/city name (local GADM + Nominatim fallback)
- **AI Assistant (Asisten Konservasi)** — natural language chatbot powered by OpenAI GPT-4o-mini; tanya tentang data konservasi, habitat, dan biodiversitas Indonesia
- **Admin Boundaries** — GADM Level 0 (national), 1 (province), 2 (district)
- **Basemap** — switch between OpenStreetMap, Carto Light, Carto Dark
- **Hover Pixel Info** — coordinates, province/district name, pixel value on hover
- **Pin Location** — click to pin a point; see all layer values + admin info for that point
- **Province Statistics** — mean, distribution stats for selected province
- **Dynamic Legend** — auto-updates per active layer with pill selector
- **Reset All** — reset semua pengaturan ke kondisi awal dengan satu klik

## Data Sources

| Layer | Key | Source |
|-------|-----|--------|
| Conservation Priority | `ranked` | Jung et al. 2021 — [DOI:10.1038/s41559-021-01528-7](https://doi.org/10.1038/s41559-021-01528-7) |
| Species Richness | `mollweide` | Indonesia 10km Mollweide species richness index |
| Habitat Classification | `habitat` | Jung et al. 2020 — [DOI:10.1038/s41597-020-00599-8](https://doi.org/10.1038/s41597-020-00599-8) |
| IAS TNUK | `ias_tnuk` | Invasive Alien Species — Arenga obtusifolia, Taman Nasional Ujung Kulon |
| IAS TNB | `ias_tnb` | Invasive Alien Species — Vachellia nilotica, Taman Nasional Baluran |
| Admin Boundaries | GADM | [GADM v4.1](https://gadm.org) — Indonesia (IDN) levels 0–2 |

## Requirements

- Python 3.9+
- dash >= 4.1.0
- plotly >= 6.6.0
- rasterio >= 1.5.0
- geopandas >= 1.1.3
- dash-bootstrap-components >= 2.0.4
- openai >= 1.0.0
- numpy, requests, python-dotenv

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Setup

Copy `.env.example` ke `.env` dan isi API key:

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-proj-your-key-here
OPENAI_MODEL=gpt-4o-mini   # optional, default: gpt-4o-mini
```

## Data Setup

Place the following files inside the `data/` folder at the project root:

```
data/
├── INDONESIA_minshort_speciestargets_biome.id_withPA_esh10km_repruns10_ranked_masked.tif
├── Indonesia_Mollweid_10km_masked.tif
└── indonesia_iucn_habitatclassification_composite_lvl1_ver004_masked.tif
```

Place the GADM shapefiles anywhere under the project root (the app auto-discovers `gadm41_IDN_0.shp` recursively):

```
<project_root>/
└── drive-download-20260401T132944Z-1-001/
    ├── gadm41_IDN_0.shp
    ├── gadm41_IDN_1.shp
    └── gadm41_IDN_2.shp
```

## Running the App

```bash
python run_v2.py
```

App will be available at `http://localhost:8050`. Startup takes a moment — all rasters and shapefiles are pre-loaded into memory on first run.

## Project Structure

```
app_v2/
├── app_instance.py   # Dash app instance
├── ai_search.py      # AI chatbot — OpenAI GPT-4o-mini integration
├── callbacks.py      # All server-side and clientside callbacks
├── cache.py          # Startup data loading, pixel sampling, geocoding helpers
├── config.py         # File paths, LAYER_META, GADM_LEVELS constants
├── gadm.py           # Shapefile → lat/lon boundary traces
├── layout.py         # App layout definition
├── legend.py         # Legend figure builder
├── layer_widgets.py  # IAS layer widget card builder
├── raster.py         # Raster I/O and PNG overlay generation
assets/
├── map_click.js      # MapLibre click → dcc.Store polling
├── chat_drag.js      # AI chat panel drag-to-reposition
├── disable_dblclick.js
└── style.css
data/                 # Raster TIF files (not tracked in git)
.env.example          # Template environment variables
requirements.txt      # Python dependencies
run_v2.py             # Entry point
```

## Architecture Notes

- Rasters are reprojected to WGS84 at startup and cached as base64 PNG overlays
- Map is rendered via Plotly `go.Figure` with `layout.mapbox` image overlays (MapLibre GL JS)
- Admin boundaries are rendered as `go.Scattermap` line traces
- Map clicks are captured by a clientside JS polling loop (workaround for Dash's lack of native MapLibre click events)
- Province masking uses GeoPandas spatial intersection at request time
- AI assistant extracts location names from user query, samples pixel data at those coordinates, and passes context to OpenAI GPT-4o-mini

---

## How the App Works

### 1. Startup — Cache Initialization (`cache.py → initialize()`)

When the app first starts, before accepting any request, it runs a one-time initialization in three stages:

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

[3/3] Province Masks
  For each province × each layer:
    spatial intersection of province polygon with raster grid
    → boolean mask array
    → apply mask → re-encode as base64 PNG
    → store in PROVINCE_MASKS and MASKED_PNG_CACHE
```

After this, all rasters and boundaries are in memory — callbacks never touch disk again.

---

### 2. User Opens the App — Initial Layout Render (`layout.py`)

Dash serves the HTML layout defined in `layout.py`. The layout includes:

- **Sidebar** — tab nav (Layers / Settings), province dropdown, location search, layer widget cards
- **Map** — `dcc.Graph` (empty on first load, filled by the first callback trigger)
- **Floating panels** — Legend, Pixel Info, Pin Lokasi (all collapsed by default)
- **AI Chat Panel** — draggable floating panel (collapsed by default)
- **Hidden stores** — `dcc.Store` nodes for state: `pinned-data`, `map-click-coords`, `layer-order`, etc.
- **Intervals** — two `dcc.Interval` timers (200ms each) that drive polling loops

---

### 3. Map Render — `update_map` Callback (`callbacks.py`)

The main callback fires whenever any control changes (layer toggle, opacity, basemap, province, etc.):

```
Inputs change
  → determine visible layers (toggle state + global toggle)
  → determine map center/zoom:
       search result?  → use search lat/lon/zoom
       province active? → get_province_view() → bbox centroid + log2 zoom
       default         → raster bounds centroid, zoom 3.8
  → for each visible layer (bottom → top order):
       province active?  → use MASKED_PNG_CACHE (pre-computed)
       range filter set? → re-colorize arr with new vmin/vmax
       habitat filter?   → re-colorize arr with only selected classes
       default           → use LAYER_CACHE[key]["img_b64"]
       → append as image overlay to map_layers[]
  → if province active → append GeoJSON province border as line layer
  → if boundary active → add GADM Scattermap trace (lat/lon lines)
  → build hover scatter grid (subsampled ~20×40 points) as invisible markers
  → build Plotly figure → go.Figure with map= layout
  → build legend figure (make_legend_figure)
  → build province stats (build_stats_children)
  → return figure, legend_content, stats_style, stats_children
```

---

### 4. User Hovers on Map — `update_pixel_info` Callback

```
hoverData from dcc.Graph
  → extract lat, lon, text (pre-formatted pixel value from hover scatter)
  → point_to_admin(lat, lon):
       GADM_GDF[1].sindex.query(point) → province name
       GADM_GDF[2].sindex.query(point) → district name + type
  → render: Koordinat | Wilayah Administratif | Nilai Piksel
  → update "pixel-info" div in floating panel
```

---

### 5. User Clicks on Map — Pin Flow

Map clicks go through a two-step chain because Dash has no native MapLibre click event:

```
Step A — Client side (map_click.js):
  dcc.Interval fires every 200ms
  → polls window._mapClickCoords (set by MapLibre's 'click' event listener)
  → if new coords found → write to dcc.Store("map-click-coords")
                        → clear window._mapClickCoords

Step B — Server side (update_pinned_store callback):
  dcc.Store("map-click-coords") changes
  → extract lat, lon
  → point_to_admin(lat, lon) → province + district
  → sample_pixel_text(lat, lon, key) for each visible layer
  → write all data to dcc.Store("pinned-data")

Step C — Client side (updatePin in map_click.js):
  dcc.Store("pinned-data") changes
  → Plotly.restyle() directly updates pin marker position in the browser
    (bypasses full figure rebuild for instant visual response)

Step D — Server side (render_pinned_info callback):
  dcc.Store("pinned-data") changes
  → render pin info panel: koordinat, provinsi, kab/kota, nilai tiap layer
```

---

### 6. Location Search — `handle_location_search` Callback

```
User types in search box (debounced)
  → search_location(query):
       Layer 1: GADM_GDF[1] NAME_1 contains query → province view
       Layer 2: GADM_GDF[2] NAME_2 contains query → district centroid
       Layer 3: Nominatim API (countrycodes=id, timeout=3s) → fallback
  → write result {lat, lon, zoom, label} to dcc.Store("search-result")
  → update_map reads search-result → repositions map center/zoom
```

---

### 7. AI Assistant — `handle_ai_chat` Callback (`ai_search.py`)

```
User sends message in chat panel
  → query_ai(user_message, chat_history):
       Step 1: extract_locations(query) via GPT-4o-mini → list of location names
       Step 2: for each location → search_location() + sample_pixel_text() → layer data
       Step 3: _build_context(locations_data) → structured context string
       Step 4: call OpenAI GPT-4o-mini with system prompt + history + context
  → return AI response string → append to chat history in dcc.Store
```

---

### 8. Data Flow Summary

```
Disk (TIF + SHP)
    │
    ▼ startup only
  cache.py initialize()
    ├── LAYER_CACHE      ← numpy arrays + base64 PNGs (whole-Indonesia)
    ├── GADM_CACHE       ← lat/lon coordinate arrays for boundary traces
    ├── GADM_GDF         ← GeoDataFrames for spatial queries
    ├── PROVINCE_MASKS   ← boolean mask per (province, layer)
    └── MASKED_PNG_CACHE ← base64 PNGs per (province, layer)
          │
          ▼ per user interaction
        Dash Callbacks
          ├── update_map              → reads cache → builds go.Figure
          ├── update_pixel_info       → reads GADM_GDF → renders hover info
          ├── update_pinned_store     → reads GADM_GDF + LAYER_CACHE → saves pin
          ├── render_pinned_info      → reads pinned-data store → renders pin panel
          ├── handle_location_search  → reads GADM_GDF + Nominatim → repositions map
          └── handle_ai_chat          → calls OpenAI GPT-4o-mini → returns AI response
```

---

## License

Data licenses apply per source. See individual dataset DOIs for terms of use.
