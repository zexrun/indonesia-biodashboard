# Indonesia BioDashboard — Feature Review (branch: new-ui)
**Tanggal review:** 2026-06-12  
**Stack:** Plotly Dash (Python) · MapLibre GL JS · OpenAI GPT-4o-mini  
**Entry point:** `python run_v2.py` → `http://localhost:8050`

---

## A. Data Layer

Lima layer raster aktif, dimuat saat startup dari file GeoTIFF ke NumPy array → base64 PNG overlay:

| ID | Nama Layer | Tipe | Rentang | Sumber |
|----|-----------|------|---------|--------|
| `ranked` | Ranked Conservation Priority | Kontinu | 1–100 (1 = prioritas tertinggi) | Jung et al. 2021 |
| `mollweide` | Species Richness / Area Index | Kontinu | 0–1000 | Indonesia 10km Mollweide |
| `habitat` | IUCN Habitat Classification (Level 1) | Diskret | 11 kelas | Jung et al. 2020 + custom marine |
| `ias_ujungkulon` | Potensi Invasif *Arenga obtusifolia* (TNUK) | Diskret | 4 kelas (0–3) | Tri Atmaja |
| `ias_baluran` | Potensi Invasif *Vachellia nilotica* (TNB) | Diskret | 4 kelas (0–3) | Tri Atmaja |

---

## B. Fitur Utama yang Berjalan

### B1. Layout Full-Screen Map + Sidebar Overlay
- Peta memenuhi seluruh viewport (`position: fixed; inset: 0`)
- Sidebar mengambang di kiri atas sebagai overlay (tidak mendorong peta)
- Sidebar dapat ditutup (tombol `✕`) dan dibuka kembali (tombol `☰`)
- Referensi desain: Global Mangrove Watch (GMW)

---

### B2. Layer Data Panel (Sidebar)
Setiap layer memiliki widget card yang dapat di-collapse, berisi:
- **Toggle ON/OFF** — menampilkan/menyembunyikan layer dari peta
- **Deskripsi layer** — teks singkat dari metadata, ditampilkan di dalam card
- **Opacity slider** — 0–100%, diapply langsung ke MapLibre GL JS tanpa server round-trip
- **Range filter** (layer kontinu) — filter nilai minimum/maksimum dengan reset button
- **Filter kelas aktif** (layer diskret) — checklist per kelas warna dengan tombol "Semua"
- **Tombol Fokus** (layer IAS) — zoom otomatis ke bounding box Taman Nasional
- **Drag reorder** — urutan layer dapat diubah dengan drag-and-drop

---

### B3. Action Bar — 4 Tombol Modal
Tersedia di bagian header sidebar. Setiap tombol membuka modal panel yang **anchored di sebelah kanan sidebar** (tidak overlay peta, tidak overlay sidebar). Semua modal saling menutup saat salah satu dibuka (*mutual-close*).

#### Tombol Reset
- Mematikan semua layer toggle
- Reset opacity ke 100%, range ke default
- Reset basemap ke Carto Light
- Reset fokus provinsi ke "Semua"

#### Modal Fokus Provinsi (`◈ Provinsi`)
- Daftar 34 provinsi Indonesia dengan search bar
- Klik provinsi → peta zoom + mask raster ke wilayah provinsi tersebut
- Provinsi aktif ditandai visual (dot teal + background highlight)
- Mask raster dihitung dari data GADM Level 1

#### Modal Cari Lokasi (`⌖ Lokasi`)
- **536 lokasi preloaded** saat startup: 34 provinsi + 502 kabupaten/kota dari data GADM Level 1 & 2
- Search bar filter real-time (tanpa debounce, tanpa limit)
- Filter chip: **Semua / Provinsi / Kab·Kota**
- Filter "Semua": separator sticky antara grup Provinsi dan Kabupaten/Kota (beserta jumlah entri)
- Urutan kab/kota: alfabetis dua level (Provinsi A–Z, Nama A–Z)
- Klik lokasi → peta zoom ke koordinat lokasi, modal otomatis tutup

#### Modal Pengaturan (`⚙ Setting`)
- Ganti **basemap**: OpenStreetMap / Carto Light / Carto Dark
- Section **Tentang Aplikasi**: info peneliti, institusi, pembimbing, dan sumber data (lihat bagian G)

---

### B4. Tombol Tanya AI (Sidebar)
- Tombol full-width teal di bawah action bar
- Membuka **modal AI Chat** (440px lebar, anchored di sebelah sidebar)
- Mutual-close dengan modal lain

---

### B5. AI Chat Panel
- **Asisten konservasi** berbasis OpenAI GPT-4o-mini
- Deteksi bahasa otomatis (Indonesia / Inggris)
- **Konteks peta otomatis:** AI menerima informasi layer yang sedang aktif + nilai pin terakhir tanpa user perlu menyebutkannya
- **Geocoding + pixel sampling:** AI mengekstrak nama lokasi dari query, mengambil data layer di koordinat tersebut, dan menyertakannya dalam analisis
- **Markdown rendering:** Respons AI dirender dengan `dcc.Markdown` — bold, italic, list, dan heading ditampilkan secara visual (bukan raw `**text**`)
- Chat history: 6 pesan terakhir dipertahankan per sesi
- Loading indicator (animasi dot) saat menunggu respons

---

### B6. Pin Lokasi (Widget Kanan Atas)
- Klik di mana saja pada peta → pin dijatuhkan (marker lingkaran magenta + halo glow)
- Widget **Pin Lokasi** menampilkan:
  - Koordinat (Lat/Lon 4 desimal)
  - Wilayah administratif: Provinsi + Kab/Kota (dari GADM Level 1 & 2)
  - Nilai pixel semua layer yang aktif pada titik tersebut
  - Layer diskret (habitat, IAS): **color dot + nama kelas + kode angka**
  - Layer kontinu (ranked, mollweide): nilai numerik
- Pin dapat dipindah (klik lokasi lain) atau dihapus (tombol `✕`)
- Deteksi otomatis jika klik di luar wilayah Indonesia → pesan peringatan

---

### B7. Legend (Widget Kanan Atas)
- Segmented pill selector untuk memilih layer legend jika beberapa layer aktif
- **Layer kontinu:** gradien bar warna + tick angka + tabel kelas interpretasi (nama zona, rentang, keterangan)
- **Layer diskret:** daftar kotak warna + nama kelas
- Deskripsi layer ditampilkan di bawah legend figure (teks italic)
- Auto-switch ke layer pertama yang visible jika layer terpilih dimatikan

---

### B8. Scale Bar (Kiri Bawah Peta)
- Skala peta visual berbentuk bar horizontal dengan label jarak (km atau m)
- Posisi: `fixed; bottom: 32px; left: calc(var(--sidebar-w) + 16px)` — otomatis bergeser saat sidebar di-collapse
- Nilai diperbarui real-time saat zoom/pan menggunakan event listener MapLibre (`move`, `zoom`, `moveend`)
- Formula Web Mercator: `(40075016.686 × cos(lat)) / (512 × 2^zoom)` meters-per-pixel (512px tile size untuk MapLibre GL JS)
- Snap ke nilai "nice": 10m, 20m, 50m, 100m, 200m, 500m, 1km, 2km, 5km, 10km, … 5000km — pilih nilai terbesar yang muat dalam 80px target
- Bar berbentuk ⊓ (border bawah + kiri + kanan, background transparan)

---

### B9. Zoom Controls (Kanan Bawah Peta)
- Tombol `+` dan `−` untuk zoom in/out
- Diimplementasikan via clientside callback → `map.easeTo({ zoom: ±1, duration: 250ms })` langsung ke MapLibre GL JS (tanpa server round-trip)

---

### B10. Interaksi Peta
- **Kursor crosshair** di seluruh area peta (CSS `cursor: crosshair`)
- Hover tooltip Plotly **dinonaktifkan** (`hovermode=False`) — tidak ada popup saat mouse bergerak
- Double-click zoom dinonaktifkan
- Scroll zoom aktif
- Drag pan aktif

---

## C. Performa & Optimasi

### Startup Cache
- Semua TIF di-load, diproyeksikan ulang ke WGS84, dan dikonversi ke base64 PNG saat startup
- **Province mask disk cache** (`.npy` + CRC32 hash validation):
  - Run pertama: komputasi mask per provinsi (~63 detik) → simpan ke `cache/masks/`
  - Run berikutnya: load dari disk (~46ms untuk 170 mask)
  - Startup time: ~17 detik (dengan cache valid)

### Clientside Callbacks
Tiga operasi dijalankan langsung di browser tanpa server round-trip:
1. **Opacity update** — `setPaintProperty` MapLibre GL JS
2. **Pin marker update** — `Plotly.restyle` langsung
3. **Zoom in/out** — `map.easeTo()`

### Timing Instrumentation
Semua operasi penting dicatat ke `/log-timing` endpoint Flask dengan `performance.now()` (JS-side) atau `time.time()` (Python-side), tersimpan di `perf_log.jsonl`.

---

## D. Data & Referensi Ilmiah

| Layer | Sumber | DOI / Referensi |
|-------|--------|-----------------|
| Ranked Priority | Jung et al. 2021 | DOI: 10.1038/s41559-021-01528-7 |
| Species Richness | Indonesia 10km Mollweide | — |
| IUCN Habitat (terrestrial) | Jung et al. 2020 | DOI: 10.1038/s41597-020-00599-8 |
| IUCN Habitat (marine) | Custom mapping EEZ Indonesia | Tidak divalidasi |
| IAS TNUK | Tri Atmaja | — |
| IAS TNB | Tri Atmaja | — |
| Admin boundaries | GADM v4.1 (Level 1 & 2) | gadm.org |

---

## E. Fitur yang Sengaja Dihapus (Simplifikasi)

| Fitur | Alasan |
|-------|--------|
| Batas wilayah administratif (GADM overlay) | Tidak digunakan dalam analisis utama |
| Dropdown level administratif | Dependen pada fitur di atas |
| Statistik Provinsi (min/max/median per layer) | Tidak relevan dengan tujuan aplikasi |
| Hover tooltip peta | Digantikan Pin Lokasi yang lebih informatif |

---

## F. Future Improvements (Tidak Diimplementasikan)

### F1. AI-Controlled Map Actions
User dapat memberi instruksi natural language seperti *"Tampilkan data konservasi di Kota Medan"* dan sistem secara otomatis:
- Menyalakan layer yang relevan
- Zoom ke lokasi yang disebutkan
- Memberikan analisis tekstual

**Arsitektur yang dibutuhkan:** OpenAI function calling / structured output + callback Dash baru yang membaca `actions` dari respons AI dan mengubah state peta.

---

## G. Acknowledgement

| | |
|--|--|
| **Peneliti** | Muhammad Rifqy Khuzaini |
| **NIM** | 1301223473 |
| **Institusi** | Universitas Telkom |
| **Program Studi** | Sarjana Informatika |
| **Departemen** | Fakultas Informatika |
| **Pembimbing** | Rio Nurtantyana, Tri Atmaja |
| **Tahun** | 2026 |

---

## H. Stack Teknis

| Komponen | Teknologi |
|----------|-----------|
| Framework web | Plotly Dash 2.x (Python) |
| Peta interaktif | MapLibre GL JS (via `go.Scattermap`) |
| AI / NLP | OpenAI GPT-4o-mini (via API) |
| Data raster | GeoTIFF → NumPy → base64 PNG overlay |
| Data administratif | GADM v4.1 (GeoDataFrame via GeoPandas) |
| Disk cache | NumPy `.npy` + CRC32 hash validation |
| Styling | CSS custom (GMW Design System tokens) |
| Geocoding | Nominatim (OpenStreetMap) via `geopy` |
| Profiling | `perf_log.jsonl` + Flask `/log-timing` endpoint |
