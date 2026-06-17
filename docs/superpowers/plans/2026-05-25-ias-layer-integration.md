# IAS Layer Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menambahkan 2 layer raster IAS (Invasive Alien Species) — Arenga obtusifolia (TNUK) dan Vachellia nilotica (TNB) — ke dalam aplikasi Dash peta raster Indonesia yang sudah ada.

**Architecture:** Kedua layer IAS bersifat diskret (nilai 0–3) dengan colormap custom. Integrasi mengikuti pola layer yang sudah ada: tambah entri di `config.py` → otomatis ter-load di `cache.py` → tambah UI di `layout.py` + `layer_widgets.py` → update semua callback yang saat ini hard-code 3 layer menjadi generik atau ditambahkan entri baru.

**Tech Stack:** Python, Plotly Dash, Rasterio, NumPy, dash-bootstrap-components

---

## File Map

| File | Aksi | Tanggung Jawab |
|------|------|----------------|
| `app_v2/config.py` | Modify | Tambah `FILES` + `LAYER_META` untuk 2 layer IAS |
| `app_v2/layer_widgets.py` | Modify | Tambah icon, warna, dan IAS category checklist widget |
| `app_v2/layout.py` | Modify | Tambah slot layer card + update `layer-order` store default |
| `app_v2/callbacks.py` | Modify | Update semua callback yang hard-code layer keys |

> `cache.py`, `raster.py`, `legend.py` tidak perlu diubah — sudah generik terhadap semua layer di `FILES` dan `LAYER_META`.

---

## Task 1: Tambah Layer Meta di config.py

**Files:**
- Modify: `app_v2/config.py`

- [ ] **Step 1: Tambah FILES entries**

Di `app_v2/config.py`, pada dict `FILES` (setelah entry `"habitat"`), tambahkan:

```python
FILES = {
    "ranked":         os.path.join(DATA_DIR, "INDONESIA_minshort_speciestargets_biome.id_withPA_esh10km_repruns10_ranked_masked.tif"),
    "mollweide":      os.path.join(DATA_DIR, "Indonesia_Mollweid_10km.tif"),
    "habitat":        os.path.join(DATA_DIR, "indonesia_iucn_habitatclassification_composite_lvl1_ver004_masked.tif"),
    "ias_ujungkulon": os.path.join(DATA_DIR, "arenga_obtusifolia_ujungkulon.tif"),
    "ias_baluran":    os.path.join(DATA_DIR, "vachellia_nilotica_baluran.tif"),
}
```

- [ ] **Step 2: Tambah LAYER_META entries**

Di `app_v2/config.py`, pada dict `LAYER_META` (setelah entry `"habitat"`), tambahkan:

```python
    "ias_ujungkulon": {
        "label":       "Potensi Invasif Arenga obtusifolia (TNUK)",
        "description": "Pemetaan potensi invasibilitas Langkap (Arenga obtusifolia) di Taman Nasional Ujung Kulon menggunakan metode Multi-Index Thresholding Sentinel-2",
        "colormap":    None,
        "vmin":        None,
        "vmax":        None,
        "discrete":    True,
        "source":      "Tri Atmaja – Sentinel-2 Based Habitat Potential Mapping",
        "species":     "Arenga obtusifolia",
        "location":    "Taman Nasional Ujung Kulon",
        "categories": {
            0: ("Tidak Ada Potensi", "rgba(0,0,0,0)"),
            1: ("Potensi Rendah",    "#00CC00"),
            2: ("Potensi Sedang",    "#CCFF00"),
            3: ("Potensi Tinggi",    "#FF0000"),
        },
    },
    "ias_baluran": {
        "label":       "Potensi Invasif Vachellia nilotica (TNB)",
        "description": "Pemetaan potensi invasibilitas Akasia Duri (Vachellia nilotica) di Taman Nasional Baluran menggunakan analisis multi-temporal Sentinel-2 dan PlanetScope (2020–2025)",
        "colormap":    None,
        "vmin":        None,
        "vmax":        None,
        "discrete":    True,
        "source":      "Tri Atmaja – Multi-Temporal Sentinel-2 Data Analysis",
        "species":     "Vachellia nilotica",
        "location":    "Taman Nasional Baluran",
        "categories": {
            0: ("Tidak Ada Potensi", "rgba(0,0,0,0)"),
            1: ("Potensi Rendah",    "#00CC00"),
            2: ("Potensi Sedang",    "#CCFF00"),
            3: ("Potensi Tinggi",    "#FF0000"),
        },
    },
```

- [ ] **Step 3: Verifikasi config load tanpa error**

```bash
cd "c:/Users/asus/Documents/Kuliah/TA2/PROJECT/GIS_MAP_V2"
python -c "from app_v2.config import FILES, LAYER_META; print('FILES:', list(FILES.keys())); print('LAYER_META:', list(LAYER_META.keys()))"
```

Expected output:
```
FILES: ['ranked', 'mollweide', 'habitat', 'ias_ujungkulon', 'ias_baluran']
LAYER_META: ['ranked', 'mollweide', 'habitat', 'ias_ujungkulon', 'ias_baluran']
```

- [ ] **Step 4: Commit**

```bash
git add app_v2/config.py
git commit -m "feat: add IAS layer metadata for TNUK and TNB to config"
```

---

## Task 2: Tambah Icon, Warna, dan Widget di layer_widgets.py

**Files:**
- Modify: `app_v2/layer_widgets.py`

- [ ] **Step 1: Tambah icon dan warna IAS**

Di `app_v2/layer_widgets.py`, update dict `_LAYER_ICONS` dan `_LAYER_COLORS`:

```python
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
```

- [ ] **Step 2: Update fungsi `_layer_widget` untuk handle IAS layers**

Layer IAS juga diskret tetapi memiliki pola category checklist sendiri (nilai 0–3). Tambahkan branch `elif key in ("ias_ujungkulon", "ias_baluran"):` setelah branch `elif key == "habitat":` di dalam fungsi `_layer_widget`:

```python
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
            if k != 0  # Nilai 0 selalu transparan, tidak perlu toggle
        ]
        body.append(
            html.Div(className="ctrl-row habitat-classes-row", children=[
                html.Span("Kelas Potensi", className="ctrl-label"),
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
```

- [ ] **Step 3: Verifikasi import layer_widgets tanpa error**

```bash
cd "c:/Users/asus/Documents/Kuliah/TA2/PROJECT/GIS_MAP_V2"
python -c "from app_v2.layer_widgets import _layer_widget, _LAYER_ICONS, _LAYER_COLORS; print('Icons:', list(_LAYER_ICONS.keys())); w = _layer_widget('ias_ujungkulon'); print('Widget OK')"
```

Expected output:
```
Icons: ['ranked', 'mollweide', 'habitat', 'ias_ujungkulon', 'ias_baluran']
Widget OK
```

- [ ] **Step 4: Commit**

```bash
git add app_v2/layer_widgets.py
git commit -m "feat: add IAS layer icons, colors, and class filter widgets"
```

---

## Task 3: Update Layout — Tambah Layer Slots dan Store Default

**Files:**
- Modify: `app_v2/layout.py`

- [ ] **Step 1: Update `layer-order` store default value**

Di `app_v2/layout.py`, cari:
```python
dcc.Store(id="layer-order", data=["ranked", "mollweide", "habitat"]),
```

Ganti dengan:
```python
dcc.Store(id="layer-order", data=["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]),
```

- [ ] **Step 2: Tambah import `_layer_widget` (sudah ada) dan tambah slot layer card**

Di `app_v2/layout.py`, cari blok `layer-cards-list`:
```python
html.Div(
    id="layer-cards-list",
    className="layer-cards-list",
    children=[
        html.Div(id="layer-slot-ranked",    style={"order": 0}, children=[_layer_widget("ranked")]),
        html.Div(id="layer-slot-mollweide", style={"order": 1}, children=[_layer_widget("mollweide")]),
        html.Div(id="layer-slot-habitat",   style={"order": 2}, children=[_layer_widget("habitat")]),
    ],
),
```

Ganti dengan:
```python
html.Div(
    id="layer-cards-list",
    className="layer-cards-list",
    children=[
        html.Div(id="layer-slot-ranked",         style={"order": 0}, children=[_layer_widget("ranked")]),
        html.Div(id="layer-slot-mollweide",      style={"order": 1}, children=[_layer_widget("mollweide")]),
        html.Div(id="layer-slot-habitat",        style={"order": 2}, children=[_layer_widget("habitat")]),
        html.Div(id="layer-slot-ias_ujungkulon", style={"order": 3}, children=[_layer_widget("ias_ujungkulon")]),
        html.Div(id="layer-slot-ias_baluran",    style={"order": 4}, children=[_layer_widget("ias_baluran")]),
    ],
),
```

- [ ] **Step 3: Update header chip jumlah layer**

Di `app_v2/layout.py`, chip `{len(FILES)} Layers` sudah dinamis — tidak perlu diubah.

- [ ] **Step 4: Verifikasi layout import tanpa error**

```bash
cd "c:/Users/asus/Documents/Kuliah/TA2/PROJECT/GIS_MAP_V2"
python -c "from app_v2 import layout; print('Layout OK')"
```

Expected output:
```
Layout OK
```

- [ ] **Step 5: Commit**

```bash
git add app_v2/layout.py
git commit -m "feat: add IAS layer card slots to sidebar layout"
```

---

## Task 4: Update Callbacks — Generalisasi untuk 5 Layer

**Files:**
- Modify: `app_v2/callbacks.py`

Saat ini banyak callback di `callbacks.py` yang hard-code untuk 3 layer (`ranked`, `mollweide`, `habitat`). Semua perlu diupdate untuk 5 layer.

- [ ] **Step 1: Update `render_layer_cards` callback**

Cari:
```python
@app.callback(
    Output("layer-slot-ranked",    "style"),
    Output("layer-slot-mollweide", "style"),
    Output("layer-slot-habitat",   "style"),
    Input("layer-order", "data"),
)
def render_layer_cards(order):
    """Update CSS order of layer slots to reflect drag order."""
    if not order:
        order = ["ranked", "mollweide", "habitat"]
    positions = {k: i for i, k in enumerate(order)}
    return (
        {"order": positions.get("ranked",    0)},
        {"order": positions.get("mollweide", 1)},
        {"order": positions.get("habitat",   2)},
    )
```

Ganti dengan:
```python
@app.callback(
    Output("layer-slot-ranked",         "style"),
    Output("layer-slot-mollweide",      "style"),
    Output("layer-slot-habitat",        "style"),
    Output("layer-slot-ias_ujungkulon", "style"),
    Output("layer-slot-ias_baluran",    "style"),
    Input("layer-order", "data"),
)
def render_layer_cards(order):
    """Update CSS order of layer slots to reflect drag order."""
    if not order:
        order = ["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]
    positions = {k: i for i, k in enumerate(order)}
    return (
        {"order": positions.get("ranked",         0)},
        {"order": positions.get("mollweide",      1)},
        {"order": positions.get("habitat",        2)},
        {"order": positions.get("ias_ujungkulon", 3)},
        {"order": positions.get("ias_baluran",    4)},
    )
```

- [ ] **Step 2: Update `update_layer_card_states` callback**

Cari:
```python
@app.callback(
    Output("layer-card-ranked",    "className"),
    Output("layer-card-mollweide", "className"),
    Output("layer-card-habitat",   "className"),
    Input("layer-toggle-ranked",    "value"),
    Input("layer-toggle-mollweide", "value"),
    Input("layer-toggle-habitat",   "value"),
)
def update_layer_card_states(toggle_ranked, toggle_mollweide, toggle_habitat):
    def card_cls(v):
        return "widget-card" if (v and "show" in v) else "widget-card layer-is-off"
    return card_cls(toggle_ranked), card_cls(toggle_mollweide), card_cls(toggle_habitat)
```

Ganti dengan:
```python
@app.callback(
    Output("layer-card-ranked",         "className"),
    Output("layer-card-mollweide",      "className"),
    Output("layer-card-habitat",        "className"),
    Output("layer-card-ias_ujungkulon", "className"),
    Output("layer-card-ias_baluran",    "className"),
    Input("layer-toggle-ranked",         "value"),
    Input("layer-toggle-mollweide",      "value"),
    Input("layer-toggle-habitat",        "value"),
    Input("layer-toggle-ias_ujungkulon", "value"),
    Input("layer-toggle-ias_baluran",    "value"),
)
def update_layer_card_states(toggle_ranked, toggle_mollweide, toggle_habitat,
                              toggle_ias_ujungkulon, toggle_ias_baluran):
    def card_cls(v):
        return "widget-card" if (v and "show" in v) else "widget-card layer-is-off"
    return (
        card_cls(toggle_ranked),
        card_cls(toggle_mollweide),
        card_cls(toggle_habitat),
        card_cls(toggle_ias_ujungkulon),
        card_cls(toggle_ias_baluran),
    )
```

- [ ] **Step 3: Update `toggle_widget_card` callback — tambah IAS toggle inputs**

Cari:
```python
@app.callback(
    Output({"type": "widget-collapse", "index": MATCH}, "is_open"),
    Output({"type": "widget-header-btn", "index": MATCH}, "className"),
    Input({"type": "widget-header-btn", "index": MATCH}, "n_clicks"),
    Input("layer-toggle-ranked",    "value"),
    Input("layer-toggle-mollweide", "value"),
    Input("layer-toggle-habitat",   "value"),
    State({"type": "widget-collapse",   "index": MATCH}, "is_open"),
    State({"type": "widget-header-btn", "index": MATCH}, "id"),
    prevent_initial_call=True,
)
def toggle_widget_card(header_clicks, toggle_ranked, toggle_mollweide, toggle_habitat, is_open, header_id):
```

Ganti dengan:
```python
@app.callback(
    Output({"type": "widget-collapse", "index": MATCH}, "is_open"),
    Output({"type": "widget-header-btn", "index": MATCH}, "className"),
    Input({"type": "widget-header-btn", "index": MATCH}, "n_clicks"),
    Input("layer-toggle-ranked",         "value"),
    Input("layer-toggle-mollweide",      "value"),
    Input("layer-toggle-habitat",        "value"),
    Input("layer-toggle-ias_ujungkulon", "value"),
    Input("layer-toggle-ias_baluran",    "value"),
    State({"type": "widget-collapse",   "index": MATCH}, "is_open"),
    State({"type": "widget-header-btn", "index": MATCH}, "id"),
    prevent_initial_call=True,
)
def toggle_widget_card(header_clicks, toggle_ranked, toggle_mollweide, toggle_habitat,
                        toggle_ias_ujungkulon, toggle_ias_baluran, is_open, header_id):
```

Di dalam body fungsi `toggle_widget_card`, tambahkan branch IAS setelah `elif section_index == "layer-habitat":`:

```python
        elif section_index == "layer-ias_ujungkulon":
            new_open = bool(toggle_ias_ujungkulon and "show" in toggle_ias_ujungkulon)
            if triggered_id == header_id:
                new_open = not is_open
        elif section_index == "layer-ias_baluran":
            new_open = bool(toggle_ias_baluran and "show" in toggle_ias_baluran)
            if triggered_id == header_id:
                new_open = not is_open
```

- [ ] **Step 4: Update `_LAYER_SHORT` dict dan `update_legend_selector` callback**

Cari:
```python
_LAYER_SHORT = {
    "ranked":    "Ranked",
    "mollweide": "Rich",
    "habitat":   "Hab.",
}
```

Ganti dengan:
```python
_LAYER_SHORT = {
    "ranked":         "Ranked",
    "mollweide":      "Rich",
    "habitat":        "Hab.",
    "ias_ujungkulon": "TNUK",
    "ias_baluran":    "TNB",
}
```

Cari callback `update_legend_selector`:
```python
@app.callback(
    Output("legend-selector", "children"),
    Input("layer-toggle-ranked",    "value"),
    Input("layer-toggle-mollweide", "value"),
    Input("layer-toggle-habitat",   "value"),
    Input("layer-order",            "data"),
    Input("selected-legend-layer",  "data"),
)
def update_legend_selector(toggle_ranked, toggle_mollweide, toggle_habitat, layer_order, selected):
    order = layer_order if layer_order else ["ranked", "mollweide", "habitat"]
    toggles = {
        "ranked":    toggle_ranked,
        "mollweide": toggle_mollweide,
        "habitat":   toggle_habitat,
    }
```

Ganti dengan:
```python
@app.callback(
    Output("legend-selector", "children"),
    Input("layer-toggle-ranked",         "value"),
    Input("layer-toggle-mollweide",      "value"),
    Input("layer-toggle-habitat",        "value"),
    Input("layer-toggle-ias_ujungkulon", "value"),
    Input("layer-toggle-ias_baluran",    "value"),
    Input("layer-order",                 "data"),
    Input("selected-legend-layer",       "data"),
)
def update_legend_selector(toggle_ranked, toggle_mollweide, toggle_habitat,
                            toggle_ias_ujungkulon, toggle_ias_baluran, layer_order, selected):
    order = layer_order if layer_order else ["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]
    toggles = {
        "ranked":         toggle_ranked,
        "mollweide":      toggle_mollweide,
        "habitat":        toggle_habitat,
        "ias_ujungkulon": toggle_ias_ujungkulon,
        "ias_baluran":    toggle_ias_baluran,
    }
```

- [ ] **Step 5: Update `update_map` callback — inputs, opacities, ranges, visible_keys**

Cari blok Output/Input `update_map`:
```python
    # Per-layer toggles
    Input("layer-toggle-ranked",    "value"),
    Input("layer-toggle-mollweide", "value"),
    Input("layer-toggle-habitat",   "value"),
    # Per-layer opacities
    Input("layer-opacity-ranked",    "value"),
    Input("layer-opacity-mollweide", "value"),
    Input("layer-opacity-habitat",   "value"),
    # Per-layer range filters (continuous layers only)
    Input("layer-range-ranked",    "value"),
    Input("layer-range-mollweide", "value"),
```

Ganti dengan:
```python
    # Per-layer toggles
    Input("layer-toggle-ranked",         "value"),
    Input("layer-toggle-mollweide",      "value"),
    Input("layer-toggle-habitat",        "value"),
    Input("layer-toggle-ias_ujungkulon", "value"),
    Input("layer-toggle-ias_baluran",    "value"),
    # Per-layer opacities
    Input("layer-opacity-ranked",         "value"),
    Input("layer-opacity-mollweide",      "value"),
    Input("layer-opacity-habitat",        "value"),
    Input("layer-opacity-ias_ujungkulon", "value"),
    Input("layer-opacity-ias_baluran",    "value"),
    # Per-layer range filters (continuous layers only)
    Input("layer-range-ranked",    "value"),
    Input("layer-range-mollweide", "value"),
```

Cari signature fungsi `update_map`:
```python
def update_map(
    toggle_ranked, toggle_mollweide, toggle_habitat,
    opacity_ranked, opacity_mollweide, opacity_habitat,
    range_ranked, range_mollweide,
    ...
```

Ganti dengan:
```python
def update_map(
    toggle_ranked, toggle_mollweide, toggle_habitat,
    toggle_ias_ujungkulon, toggle_ias_baluran,
    opacity_ranked, opacity_mollweide, opacity_habitat,
    opacity_ias_ujungkulon, opacity_ias_baluran,
    range_ranked, range_mollweide,
    ...
```

Di dalam body `update_map`, update dict `toggles` dan `opacities`:
```python
    toggles = {
        "ranked":         toggle_ranked,
        "mollweide":      toggle_mollweide,
        "habitat":        toggle_habitat,
        "ias_ujungkulon": toggle_ias_ujungkulon,
        "ias_baluran":    toggle_ias_baluran,
    }
    opacities = {
        "ranked":         opacity_ranked         if opacity_ranked         is not None else 1.0,
        "mollweide":      opacity_mollweide       if opacity_mollweide      is not None else 1.0,
        "habitat":        opacity_habitat         if opacity_habitat        is not None else 1.0,
        "ias_ujungkulon": opacity_ias_ujungkulon  if opacity_ias_ujungkulon is not None else 1.0,
        "ias_baluran":    opacity_ias_baluran     if opacity_ias_baluran    is not None else 1.0,
    }
    ranges = {
        "ranked":    range_ranked,
        "mollweide": range_mollweide,
    }
```

Update `_order` default:
```python
    _order = layer_order if layer_order else ["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]
```

Update `uirevision` string untuk include opacity IAS:
```python
        uirevision=(
            f"{','.join(visible_keys)}-{basemap}"
            f"-{'on' if boundary_active else 'off'}-{boundary_level}"
            f"-{province}-{center_lat:.4f}-{center_lon:.4f}-{map_zoom:.2f}"
            f"-{opacity_ranked}-{opacity_mollweide}-{opacity_habitat}"
            f"-{opacity_ias_ujungkulon}-{opacity_ias_baluran}"
        ),
```

- [ ] **Step 6: Update `update_pinned_store` callback**

Cari:
```python
    State("layer-toggle-ranked",    "value"),
    State("layer-toggle-mollweide", "value"),
    State("layer-toggle-habitat",   "value"),
```

Ganti dengan:
```python
    State("layer-toggle-ranked",         "value"),
    State("layer-toggle-mollweide",      "value"),
    State("layer-toggle-habitat",        "value"),
    State("layer-toggle-ias_ujungkulon", "value"),
    State("layer-toggle-ias_baluran",    "value"),
```

Cari signature:
```python
def update_pinned_store(click_coords, clear_clicks,
                        toggle_ranked, toggle_mollweide, toggle_habitat,
                        layer_toggle_global, current_pin):
```

Ganti dengan:
```python
def update_pinned_store(click_coords, clear_clicks,
                        toggle_ranked, toggle_mollweide, toggle_habitat,
                        toggle_ias_ujungkulon, toggle_ias_baluran,
                        layer_toggle_global, current_pin):
```

Update dict `toggles` di dalam body fungsi:
```python
    toggles = {
        "ranked":         toggle_ranked,
        "mollweide":      toggle_mollweide,
        "habitat":        toggle_habitat,
        "ias_ujungkulon": toggle_ias_ujungkulon,
        "ias_baluran":    toggle_ias_baluran,
    }
    visible_keys = [
        k for k in ["ranked", "mollweide", "habitat", "ias_ujungkulon", "ias_baluran"]
        if global_visible and toggles[k] and "show" in (toggles[k] or [])
    ]
```

- [ ] **Step 7: Verifikasi app dapat diimport tanpa error**

```bash
cd "c:/Users/asus/Documents/Kuliah/TA2/PROJECT/GIS_MAP_V2"
python -c "from app_v2 import callbacks; print('Callbacks OK')"
```

Expected output:
```
Callbacks OK
```

- [ ] **Step 8: Commit**

```bash
git add app_v2/callbacks.py
git commit -m "feat: generalize callbacks to support 5 layers including IAS TNUK and TNB"
```

---

## Task 5: Smoke Test — Jalankan Aplikasi

**Files:** (tidak ada perubahan file, hanya verifikasi)

- [ ] **Step 1: Jalankan app dan verifikasi startup**

```bash
cd "c:/Users/asus/Documents/Kuliah/TA2/PROJECT/GIS_MAP_V2"
python run_v2.py
```

Expected output startup log (antara lain):
```
  Loading [ias_ujungkulon]... OK
  Loading [ias_baluran]... OK
```
Dan tidak ada `FileNotFoundError` atau `KeyError`.

- [ ] **Step 2: Verifikasi di browser**

Buka `http://localhost:8050`:
- [ ] Sidebar menampilkan 5 layer card (termasuk "Potensi Invasif Arenga obtusifolia (TNUK)" dan "Potensi Invasif Vachellia nilotica (TNB)")
- [ ] Toggle layer IAS menyalakan/mematikan layer di peta
- [ ] Opacity slider IAS berfungsi
- [ ] Legend menampilkan 4 kelas warna (Tidak Ada Potensi / Rendah / Sedang / Tinggi) saat layer IAS aktif
- [ ] Hover pixel info menampilkan kelas potensi invasif yang benar
- [ ] Layer lama (ranked, mollweide, habitat) masih berfungsi normal

---

## Catatan Penting

- **Nilai 0 transparan:** `arr_to_rgba_png_b64` di `raster.py` sudah mem-mask nilai nodata. Untuk layer IAS, nilai `0` perlu dipastikan juga transparan. Jika nilai `0` tidak ter-mask otomatis, tambahkan `0` sebagai nilai nodata saat loading atau handle di `raster.py` dengan pengecekan khusus layer diskret IAS. Ini akan terlihat saat smoke test — jika area "tidak ada potensi" berwarna putih (bukan transparan), perlu ditambahkan handling di `raster.py` atau `arr_to_rgba_png_b64`.
- **CRS:** `load_as_wgs84()` di `raster.py` sudah generik — otomatis reproyeksi ke WGS84.
- **Layer IAS bersifat lokal** (hanya TNUK/TNB), jadi sebagian besar peta akan kosong/transparan — ini perilaku yang benar.
