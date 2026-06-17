"""Konstanta aplikasi: path file, metadata layer, konfigurasi GADM."""

import os
import glob
from rasterio.crs import CRS

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARENT_DIR = os.path.dirname(PROJECT_ROOT)

WGS84 = CRS.from_epsg(4326)
MAX_PIXELS = 700

DATA_DIR = os.path.join(PROJECT_ROOT, "data")

FILES = {
    "ranked":         os.path.join(DATA_DIR, "INDONESIA_minshort_speciestargets_biome.id_withPA_esh10km_repruns10_ranked_masked.tif"),
    "mollweide":      os.path.join(DATA_DIR, "Indonesia_Mollweid_10km.tif"),
    "habitat":        os.path.join(DATA_DIR, "indonesia_iucn_habitatclassification_composite_lvl1_ver004_masked.tif"),
    "ias_ujungkulon": os.path.join(DATA_DIR, "arenga_obtusifolia_ujungkulon.tif"),
    "ias_baluran":    os.path.join(DATA_DIR, "vachellia_nilotica_baluran.tif"),
}

for _key, _path in FILES.items():
    if not os.path.exists(_path):
        raise FileNotFoundError(f"Raster file not found for layer '{_key}': {_path}")

def _find_gadm_dir(root):
    """Find the extracted GADM folder by looking for gadm41_IDN_0.shp."""
    matches = glob.glob(os.path.join(root, "**/gadm41_IDN_0.shp"), recursive=True)
    if not matches:
        raise FileNotFoundError(
            f"GADM shapefiles not found under {root}. "
            "Extract the GADM zip so that gadm41_IDN_0.shp is reachable."
        )
    return os.path.dirname(matches[0])

GADM_DIR = _find_gadm_dir(PROJECT_ROOT)
GADM_LEVELS = {
    0: {"file": "gadm41_IDN_0.shp", "label": "Nasional (Negara)", "color": "#1a1a1a", "width": 2.0},
    1: {"file": "gadm41_IDN_1.shp", "label": "Provinsi",          "color": "#1a6b35", "width": 1.4},
    2: {"file": "gadm41_IDN_2.shp", "label": "Kabupaten / Kota",  "color": "#4a90d9", "width": 0.8},
}
SIMPLIFY_TOL = {0: None, 1: None, 2: 0.01}

LAYER_META = {
    "ranked": {
        "label":       "Ranked Conservation Priority (1–100)",
        "description": "Species targets biome-based conservation priority ranking (1 = highest priority)",
        "colormap":    "YlOrRd_r",
        "vmin": 1, "vmax": 100,
        "discrete":    False,
        "zones": [
            (1,   20,  "Sangat Tinggi", "Prioritas konservasi kritis"),
            (21,  40,  "Tinggi",        "Perlu tindakan segera"),
            (41,  60,  "Sedang",        "Perlu pemantauan aktif"),
            (61,  80,  "Rendah",        "Potensi konservasi terbatas"),
            (81, 100,  "Sangat Rendah", "Prioritas paling rendah"),
        ],
        "source": "Jung et al. 2021 - Spatial conservation prioritization",
        "methodology": "Multicriteria optimization (biodiversity + carbon + water)",
    },
    "mollweide": {
        "label":       "Species Richness / Area Index (0–1000)",
        "description": "Indonesia 10km Mollweide raster – continuous index values",
        "colormap":    "viridis",
        "vmin": 0, "vmax": 1000,
        "discrete":    False,
        "zones": [
            (0,   200, "Sangat Rendah", "Keanekaragaman sangat rendah"),
            (201, 400, "Rendah",        "Keanekaragaman terbatas"),
            (401, 600, "Sedang",        "Keanekaragaman moderat"),
            (601, 800, "Tinggi",        "Keanekaragaman tinggi"),
            (801,1000, "Sangat Tinggi", "Hotspot keanekaragaman"),
        ],
        "source": "Indonesia 10km species richness index",
        "validation_accuracy": 0.76,
    },
    "habitat": {
        "label":       "IUCN Habitat Classification (Level 1)",
        "description": "IUCN habitat types mapped globally, extended with Indonesian marine habitats",
        "colormap":    None,
        "vmin": None, "vmax": None,
        "discrete":    True,
        "source": {
            "terrestrial": "Jung et al. 2020 - A global map of terrestrial habitat types",
            "marine": "Custom extension for Indonesian territorial waters (EEZ)"
        },
        "doi": "10.1038/s41597-020-00599-8",
        "iucn_standard": "IUCN Habitat Classification Scheme Version 3.1",
        "validation": {
            "terrestrial": {
                "method": "Species occurrence data + IBA + PREDICTS + Visual assessment",
                "balanced_accuracy_level1": 0.76,
                "std_dev": 0.12,
                "sample_size": {
                    "habitat_specialist_species": 828,
                    "occurrence_points": 35152,
                    "iba_polygons": 8181,
                    "predicts_sites": 3797,
                    "visual_samples": 2229
                },
                "validation_sources": ["GBIF", "eBird", "IBA", "PREDICTS", "LACO-Wiki"]
            },
            "marine": {
                "status": "Not validated - custom mapping for Indonesia",
                "note": "Future validation recommended against species occurrence/habitat data"
            }
        },

                "categories": {
            1:    ("Hutan",                     "#1B5E20"),
            2:    ("Savana",                    "#BFA86E"),
            3:    ("Semak",                     "#8A7847"),
            4:    ("Rumput",                    "#A8C66C"),
            5:    ("Rawa",                      "#4DC4D9"),
            6:    ("Berbatu",                   "#8E9B8E"),
            8:    ("Gurun & Xeric",             "#8E9B8E"),
            14:   ("Antropogenik",              "#C84B3F"),
            9:    ("Laut Dangkal",              "#3F95D9"),
            10:   ("Laut Terbuka",              "#1C5C99"),
            11:   ("Pasut",                     "#8FDCE5"),
        },
        "level2_available": True,
        "level2_count": 119,
        "level2_note": "Level 2 classes available in Jung et al. 2020 for future detailed mapping",
    },
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
}
