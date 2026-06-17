"""
AI-powered natural language search using OpenAI GPT-4o-mini.
Answers questions about conservation data for Indonesian locations.
"""

import os
import json
import time
import logging
from dotenv import load_dotenv
from .perf_timing import log_timing

load_dotenv()

logger = logging.getLogger(__name__)

# ── Lazy OpenAI client ────────────────────────────────────────────────────────

_client = None

def _get_client():
    """Lazily initialize OpenAI client."""
    global _client
    if _client is None:
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not found in environment")
            _client = OpenAI(api_key=api_key)
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")
    return _client

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Kamu adalah asisten analisis konservasi dan biodiversitas Indonesia yang terintegrasi dalam aplikasi GIS peta interaktif.

Aplikasi ini memiliki 5 layer data raster untuk wilayah Indonesia:
1. **Ranked Conservation Priority (1–100)**: Prioritas konservasi multi-kriteria (biodiversitas + karbon + air). Skor 1 = prioritas tertinggi (sangat penting dilindungi), 100 = prioritas terendah.
   - Zona: 1-20 Sangat Tinggi, 21-40 Tinggi, 41-60 Sedang, 61-80 Rendah, 81-100 Sangat Rendah
2. **Species Richness Index (0–1000)**: Indeks kekayaan spesies (tumbuhan vaskular + vertebrata terestrial). Skor tinggi = lebih banyak spesies.
   - Zona: 0-200 Sangat Rendah, 201-400 Rendah, 401-600 Sedang, 601-800 Tinggi, 801-1000 Sangat Tinggi
3. **IUCN Habitat Classification**: Klasifikasi tipe habitat (Hutan, Savana, Semak, Padang Rumput, Lahan Basah, Area Berbatu, Gurun, Habitat Buatan, Laut Neritik, Laut Oseanik, Zona Intertidal)
4. **Potensi Invasif Arenga obtusifolia - TNUK**: Peta potensi invasibilitas Langkap di Taman Nasional Ujung Kulon (0=Tidak Ada, 1=Rendah, 2=Sedang, 3=Tinggi)
5. **Potensi Invasif Vachellia nilotica - TNB**: Peta potensi invasibilitas Akasia Duri di Taman Nasional Baluran (0=Tidak Ada, 1=Rendah, 2=Sedang, 3=Tinggi)

Response language rule (HIGHEST PRIORITY):
- ALWAYS detect the language of the user's message and reply in EXACTLY that language
- If user writes in English → respond entirely in English
- If user writes in Indonesian → respond entirely in Indonesian
- Never mix languages in a single response

Panduan menjawab:
- Buat jawaban yang deskriptif, informatif, dan mudah dipahami (2-4 paragraf)
- Jika ada data lokasi yang disediakan, gunakan data tersebut sebagai dasar analisis
- Jika data tidak tersedia untuk suatu lokasi (nilai kosong/nodata), jelaskan dengan sopan
- Untuk pertanyaan komparasi, bandingkan secara sistematis per aspek/layer
- Sertakan konteks ekologis yang relevan untuk membuat jawaban lebih bermakna
- Jangan mengada-ada data — hanya gunakan data yang diberikan dalam konteks"""

# ── Location extraction ───────────────────────────────────────────────────────

def extract_locations(query: str) -> list[str]:
    """
    Use OpenAI to extract location names from a natural language query.
    Returns a list of location name strings.
    Falls back to empty list on failure.
    """
    if not query or not query.strip():
        return []
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ekstrak semua nama lokasi geografis dari query berikut. "
                        "Kembalikan HANYA JSON array of strings, tanpa teks lain. "
                        "Contoh: [\"Kota Bandung\"] atau [\"Kalimantan\", \"Sumatera\"]. "
                        "Jika tidak ada lokasi, kembalikan []."
                    ),
                },
                {"role": "user", "content": query},
            ],
            response_format={"type": "json_object"},
            max_tokens=200,
            temperature=0,
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        # Accept {"locations": [...]} or direct array wrapped in any key
        if isinstance(parsed, list):
            return [str(loc) for loc in parsed if loc]
        for val in parsed.values():
            if isinstance(val, list):
                return [str(loc) for loc in val if loc]
        return []
    except Exception as exc:
        logger.warning("extract_locations failed: %s", exc)
        return []

# ── Location data sampler ─────────────────────────────────────────────────────

def get_location_data(location_name: str) -> dict | None:
    """
    Geocode a location name and sample all layer values at that coordinate.
    Returns a dict with location info and layer data, or None if not found.
    """
    from .cache import search_location, sample_pixel_text, point_to_admin
    from .config import FILES

    result = search_location(location_name)
    if not result:
        return None

    lat, lon = result["lat"], result["lon"]
    admin = point_to_admin(lat, lon)

    layer_data = {}
    for layer_key in FILES:
        text = sample_pixel_text(lat, lon, layer_key)
        if text:
            layer_data[layer_key] = text

    return {
        "query": location_name,
        "label": result["label"],
        "lat": lat,
        "lon": lon,
        "admin": admin,
        "layers": layer_data,
    }

# ── Context builder ───────────────────────────────────────────────────────────

def _build_context(locations_data: list[dict]) -> str:
    """Build a context string from location data for the AI prompt."""
    from .config import LAYER_META

    if not locations_data:
        return ""

    lines = ["=== DATA LOKASI DARI APLIKASI ==="]
    for loc in locations_data:
        lines.append(f"\n📍 Lokasi: {loc['label']}")
        lines.append(f"   Koordinat: {loc['lat']:.4f}°, {loc['lon']:.4f}°")
        admin = loc.get("admin", {})
        if admin.get("provinsi") and admin["provinsi"] != "Tidak diketahui":
            lines.append(f"   Administrasi: {admin.get('tipe_wilayah','')} {admin.get('wilayah','')}, {admin.get('provinsi','')}")
        if loc["layers"]:
            lines.append("   Data layer:")
            for layer_key, text in loc["layers"].items():
                meta = LAYER_META.get(layer_key, {})
                label = meta.get("label", layer_key)
                # Clean HTML tags from text
                clean_text = text.replace("<br>", " | ").replace("<b>", "").replace("</b>", "")
                lines.append(f"     - {label}: {clean_text}")
        else:
            lines.append("   Data layer: Tidak ada data tersedia untuk koordinat ini")
    lines.append("\n=== AKHIR DATA ===")
    return "\n".join(lines)

# ── Main AI query function ────────────────────────────────────────────────────

def query_ai(user_message: str, chat_history: list | None = None,
             pin_context: str | None = None) -> str:
    """
    Main entry point. Takes user message + conversation history,
    extracts locations, fetches data, calls OpenAI, returns response string.

    chat_history format: [{"role": "user"|"assistant", "content": str}, ...]
    pin_context: optional string with active layers + pinned location data from the map.
    Max 6 messages from history are used.
    """
    if not user_message or not user_message.strip():
        return "Mohon masukkan pertanyaan Anda."

    _t_total = time.time()

    # Step 1: Extract locations from query
    _t0 = time.time()
    location_names = extract_locations(user_message)
    log_timing("AI_location_extraction", _t0, time.time(),
               {"query_len": len(user_message), "locations_found": location_names})

    # Step 2: Fetch data for each location
    _t0 = time.time()
    locations_data = []
    not_found = []
    for name in location_names:
        data = get_location_data(name)
        if data:
            locations_data.append(data)
        else:
            not_found.append(name)
    log_timing("AI_pixel_retrieval", _t0, time.time(),
               {"locations_found": len(locations_data), "not_found": not_found})

    # Step 3: Build context
    context = _build_context(locations_data)

    # Step 4: Build message for OpenAI
    # Detect language by checking common English words; inject explicit instruction
    # to override any language bias from prior chat history
    _en_words = {"the", "is", "are", "what", "how", "why", "where", "which",
                 "compare", "show", "explain", "tell", "between", "and", "in",
                 "of", "for", "with", "a", "an", "does", "do", "can", "will"}
    _words = set(user_message.lower().split())
    _is_english = len(_words & _en_words) >= 2
    lang_instruction = (
        "[IMPORTANT: The user wrote in English. Reply ENTIRELY in English.]"
        if _is_english else
        "[PENTING: User menulis dalam Bahasa Indonesia. Balas SELURUHNYA dalam Bahasa Indonesia.]"
    )
    user_content = f"{lang_instruction}\n\n{user_message}"
    if pin_context:
        user_content += f"\n\n=== KONTEKS PETA SAAT INI ===\n{pin_context}\n=== AKHIR KONTEKS ==="
    if context:
        user_content = f"{user_content}\n\n{context}"
    if not_found:
        not_found_str = ", ".join(not_found)
        user_content += f"\n\n[Catatan: Lokasi tidak ditemukan dalam database: {not_found_str}]"

    # Step 5: Build messages array (system + history + current)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if chat_history:
        # Use last 6 messages from history
        recent_history = chat_history[-6:]
        messages.extend(recent_history)
    messages.append({"role": "user", "content": user_content})

    # Step 6: Call OpenAI
    _t0 = time.time()
    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=800,
            temperature=0.7,
        )
        result = response.choices[0].message.content.strip()
        log_timing("AI_openai_api_call", _t0, time.time(), {"model": MODEL})
        log_timing("AI_total_query_latency", _t_total, time.time(),
                   {"query": user_message[:60] + "..." if len(user_message) > 60 else user_message})
        return result
    except Exception as exc:
        log_timing("AI_openai_api_call_FAILED", _t0, time.time(), {"error": str(exc)[:80]})
        logger.error("OpenAI API call failed: %s", exc)
        error_str = str(exc)
        if "api_key" in error_str.lower() or "authentication" in error_str.lower():
            return "⚠️ API key tidak valid. Pastikan OPENAI_API_KEY sudah diisi dengan benar di file .env"
        if "rate_limit" in error_str.lower():
            return "⚠️ Terlalu banyak permintaan. Coba lagi dalam beberapa detik."
        return f"⚠️ Terjadi kesalahan saat menghubungi AI. Silakan coba lagi.\n\nDetail: {error_str[:200]}"
