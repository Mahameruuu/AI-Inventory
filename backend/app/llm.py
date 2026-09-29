# -*- coding: utf-8 -*-
"""
Sambungan ke LLM lewat Ollama (lokal maupun Ollama Cloud).

Router assistant sengaja tidak mengetahui detail runtime. Yang dipakainya
hanya empat hal dari berkas ini:

    health()                      -> status server dan ketersediaan model
    chat(messages, tools)         -> jawaban yang sudah dinormalkan
    pesan_asisten(...)            -> menyusun pesan balasan model
    pesan_tool(...)               -> menyusun pesan hasil tool

Dengan begitu, mengganti runtime cukup mengubah berkas ini saja. Bentuk
`tool_calls` Ollama berbeda dari OpenAI -- argumennya sudah berupa objek dan
tidak membawa id -- dan seluruh perbedaan itu diserap di sini.

Seluruh kegagalan diterjemahkan menjadi pesan yang aman dibaca pengguna.
Alamat server dan jejak galat tidak pernah bocor ke klien.
"""

import json
import logging
import re

import httpx

from .config import (OLLAMA_API_KEY, OLLAMA_BASE_URL, OLLAMA_MODEL,
                     OLLAMA_TEMPERATURE, OLLAMA_TIMEOUT)
from .errors import AppError

log = logging.getLogger("inventory.llm")

# Alamat yang bukan localhost dianggap layanan awan: hanya dipakai untuk
# menyusun pesan galat yang tepat, bukan untuk mengubah perilaku protokol.
AWAN = not any(h in OLLAMA_BASE_URL for h in ("127.0.0.1", "localhost", "0.0.0.0"))
RUNTIME = "Ollama Cloud" if AWAN else "Ollama"

# Pesan yang sampai ke pengguna sengaja TIDAK menyebut nama model, nama
# runtime, maupun nama variabel lingkungan. Dashboard ini dipakai pengguna
# bisnis: bagi mereka detail itu bukan tindakan yang bisa diambil, dan
# menampilkannya membuat antarmuka terlihat seperti alat internal. Seluruh
# keterangan teknis tetap lengkap di log server (lihat log.warning pada
# health() dan _model_aktif()), tempat administrator memang mencarinya.
PESAN_MATI = "Layanan asisten sedang tidak tersedia. Coba beberapa saat lagi."
PESAN_MODEL_HILANG = (
    "Layanan asisten belum siap melayani permintaan. "
    "Hubungi administrator sistem."
)
PESAN_KEY_KOSONG = (
    "Layanan asisten belum dikonfigurasi. Hubungi administrator sistem."
)
PESAN_KEY_SALAH = (
    "Layanan asisten tidak dapat diakses. Hubungi administrator sistem."
)
PESAN_LANGGANAN = (
    "Layanan asisten sedang tidak dapat digunakan. "
    "Hubungi administrator sistem."
)
PESAN_LAMBAT = (
    "Layanan asisten tidak merespons tepat waktu. "
    "Coba ulangi pertanyaan dengan lebih spesifik."
)

# Qwen3 menyisipkan blok penalaran <think>...</think>. Isinya proses berpikir
# model, bukan jawaban, jadi dibuang sebelum sampai ke pengguna.
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def bersihkan(teks: str | None) -> str:
    if not teks:
        return ""
    return _THINK.sub("", teks).strip()


class KeyDitolak(Exception):
    """Server menolak kredensial. Dipisah agar pesannya tidak tertukar."""


def _client() -> httpx.Client:
    # Header Authorization hanya dipasang bila API key benar-benar diisi,
    # sehingga konfigurasi Ollama lokal tanpa kunci tetap berfungsi.
    headers = {"Authorization": f"Bearer {OLLAMA_API_KEY}"} if OLLAMA_API_KEY else {}
    return httpx.Client(base_url=OLLAMA_BASE_URL, timeout=OLLAMA_TIMEOUT, headers=headers)


def _daftar_model() -> list[str]:
    with _client() as c:
        r = c.get("/api/tags", timeout=15)
        if r.status_code in (401, 403):
            raise KeyDitolak(r.status_code)
        r.raise_for_status()
        return [m.get("name", "") for m in (r.json().get("models") or []) if m.get("name")]


def pilih_model(tersedia: list[str]) -> str | None:
    """
    Mencocokkan model yang dikonfigurasi dengan yang benar-benar terpasang.

    Ollama menamai model dengan pola nama:tag, misalnya "qwen3:8b". Bila tag
    yang diminta tidak ada, dicari varian Qwen3 berukuran 8B yang paling
    mendekati -- sesuai permintaan agar sistem tetap jalan di mesin yang
    tagnya sedikit berbeda.
    """
    if not tersedia:
        return None

    target = OLLAMA_MODEL.lower()
    for m in tersedia:
        if m.lower() == target:
            return m

    # "qwen3:8b" cocok dengan "qwen3:8b-instruct-q4_K_M"
    for m in tersedia:
        if m.lower().startswith(target):
            return m

    # nama tanpa tag: "gpt-oss" cocok dengan "gpt-oss:120b"
    dasar = target.split(":")[0]
    sekeluarga = [m for m in tersedia if m.lower().split(":")[0] == dasar]
    if sekeluarga:
        return sorted(sekeluarga, key=len)[0]

    return None


# Kunci yang hanya dipakai di dalam proses ini dan TIDAK ikut dikirim ke
# klien. Nama model dan katalog model yang terpasang bukan urusan pengguna
# dashboard, dan sekali masuk ke jawaban API ia terbaca siapa pun yang membuka
# panel jaringan peramban. Nilainya tetap dipakai health() untuk menyusun
# status, lalu dibuang tepat sebelum dikirim.
_INTERNAL = ("resolved_model", "available_models")


def _status(**tambahan) -> dict:
    dasar = {
        "cloud": AWAN,
        # Hanya penanda ADA atau TIDAK. Nilai kuncinya tidak pernah dikirim.
        "api_key_configured": bool(OLLAMA_API_KEY),
        "connected": False,
        "model_loaded": False,
        "resolved_model": None,
        "available_models": [],
        "message": "",
    }
    dasar.update(tambahan)
    return dasar


def _tanpa_detail_internal(status: dict) -> dict:
    return {k: v for k, v in status.items() if k not in _INTERNAL}


def health(deep: bool = False) -> dict:
    """
    Memeriksa runtime tanpa melempar galat -- UI memakainya untuk membedakan:
    kunci belum diisi, kunci ditolak, layanan tak terjangkau, model tidak ada,
    dan semuanya siap.

    `deep` menambah satu panggilan sangat kecil ke model. Diperlukan karena
    katalog model Ollama Cloud dapat dibaca tanpa kredensial, sehingga
    pemeriksaan ringan saja tidak mampu membedakan kunci yang benar dari yang
    salah. Dimatikan secara bawaan supaya membuka halaman tidak memakan kuota.
    """
    if AWAN and not OLLAMA_API_KEY:
        return _tanpa_detail_internal(_status(message=PESAN_KEY_KOSONG))

    try:
        tersedia = _daftar_model()
    except KeyDitolak:
        log.warning("Kredensial %s ditolak", RUNTIME)
        return _tanpa_detail_internal(
            _status(connected=True, message=PESAN_KEY_SALAH))
    except Exception as e:  # noqa: BLE001 -- sengaja menangkap semua
        log.warning("%s tidak terjangkau: %s", RUNTIME, e)
        return _tanpa_detail_internal(_status(message=PESAN_MATI))

    cocok = pilih_model(tersedia)
    if not cocok:
        log.warning("Model %s tidak ada di %s; tersedia: %s",
                    OLLAMA_MODEL, RUNTIME, ", ".join(tersedia) or "(kosong)")
    hasil = _status(
        connected=True,
        model_loaded=cocok is not None,
        resolved_model=cocok,
        available_models=tersedia,
        message="Terhubung." if cocok else PESAN_MODEL_HILANG,
    )
    hasil["verified"] = False

    if deep and cocok:
        try:
            with _client() as c:
                r = c.post(
                    "/api/chat",
                    json={
                        "model": cocok,
                        "messages": [{"role": "user", "content": "ping"}],
                        "stream": False,
                        "options": {"num_predict": 1, "temperature": 0},
                    },
                    timeout=45,
                )
            if r.status_code == 401:
                log.warning("Kredensial %s ditolak saat pemeriksaan mendalam", RUNTIME)
                hasil.update(model_loaded=False, message=PESAN_KEY_SALAH)
            elif r.status_code == 403 or "subscription" in r.text[:200].lower():
                log.warning("Model %s ditolak %s (langganan): %s",
                            cocok, RUNTIME, r.text[:200])
                hasil.update(model_loaded=False, message=PESAN_LANGGANAN)
            elif r.status_code >= 400:
                log.warning("Model %s gagal dipanggil di %s: HTTP %s %s",
                            cocok, RUNTIME, r.status_code, r.text[:200])
                hasil.update(model_loaded=False, message=PESAN_MODEL_HILANG)
            else:
                hasil["verified"] = True
        except Exception as e:  # noqa: BLE001
            log.warning("Pemeriksaan mendalam %s gagal: %s", RUNTIME, e)
            hasil.update(message=PESAN_MATI)

    return _tanpa_detail_internal(hasil)


def _model_aktif() -> str:
    """
    Nama model yang benar-benar dipakai untuk memanggil Ollama.

    Bila tag persis tidak ada, dipakai varian Qwen3 8B yang tersedia. Kalau
    tidak ada sama sekali, permintaan dihentikan dengan pesan yang jelas
    alih-alih membiarkan Ollama menjawab 404 mentah.
    """
    if AWAN and not OLLAMA_API_KEY:
        raise AppError(503, "AI_KEY_MISSING", PESAN_KEY_KOSONG)

    try:
        tersedia = _daftar_model()
    except KeyDitolak as e:
        raise AppError(503, "AI_KEY_REJECTED", PESAN_KEY_SALAH) from e
    except httpx.TimeoutException as e:
        raise AppError(504, "AI_TIMEOUT", PESAN_LAMBAT) from e
    except httpx.HTTPError as e:
        log.warning("%s tidak terjangkau: %s", RUNTIME, e)
        raise AppError(503, "AI_UNAVAILABLE", PESAN_MATI) from e

    cocok = pilih_model(tersedia)
    if cocok is None:
        log.warning("Model %s tidak ada di daftar %s model", OLLAMA_MODEL, len(tersedia))
        raise AppError(503, "AI_MODEL_NOT_FOUND", PESAN_MODEL_HILANG)
    return cocok


def chat(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """
    Satu panggilan ke model.

    Mengembalikan bentuk yang sudah dinormalkan:

        {
          "content": str,
          "tool_calls": [{"id": ..., "name": ..., "arguments": {...}, "raw": {...}}],
          "metrics": {"total_ms": int, "eval_count": int}
        }
    """
    model = _model_aktif()
    payload: dict = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": OLLAMA_TEMPERATURE},
    }
    if tools:
        payload["tools"] = tools

    try:
        with _client() as c:
            r = c.post("/api/chat", json=payload)
    except httpx.TimeoutException as e:
        log.warning("%s kehabisan waktu: %s", RUNTIME, e)
        raise AppError(504, "AI_TIMEOUT", PESAN_LAMBAT) from e
    except httpx.HTTPError as e:
        log.warning("%s tidak terjangkau: %s", RUNTIME, e)
        raise AppError(503, "AI_UNAVAILABLE", PESAN_MATI) from e

    if r.status_code >= 400:
        cuplikan = r.text[:300]
        log.warning("%s menolak permintaan (%s): %s", RUNTIME, r.status_code, cuplikan)
        rendah = cuplikan.lower()
        if r.status_code == 401:
            raise AppError(503, "AI_KEY_REJECTED", PESAN_KEY_SALAH)
        if r.status_code == 403 or "subscription" in rendah or "upgrade" in rendah:
            raise AppError(503, "AI_SUBSCRIPTION_REQUIRED", PESAN_LANGGANAN)
        if r.status_code == 429 or "rate limit" in rendah:
            raise AppError(
                429,
                "AI_RATE_LIMITED",
                "Kuota permintaan ke Ollama Cloud sedang penuh. Coba lagi sebentar.",
            )
        if r.status_code == 404 or "not found" in rendah or "try pulling" in rendah:
            raise AppError(503, "AI_MODEL_NOT_FOUND", PESAN_MODEL_HILANG)
        if "does not support tools" in rendah or ("tools" in rendah and "support" in rendah):
            raise AppError(
                503,
                "AI_TOOLS_UNSUPPORTED",
                f"Model {model} tidak mendukung pemanggilan tool. "
                "Pilih model lain lewat OLLAMA_MODEL.",
            )
        raise AppError(503, "AI_UNAVAILABLE", PESAN_MATI)

    try:
        data = r.json()
        pesan = data.get("message") or {}
    except ValueError as e:
        log.warning("Jawaban %s tidak dikenali: %s", RUNTIME, r.text[:300])
        raise AppError(503, "AI_UNAVAILABLE", PESAN_MATI) from e

    panggilan = []
    for i, p in enumerate(pesan.get("tool_calls") or []):
        fungsi = p.get("function") or {}
        panggilan.append(
            {
                # Ollama tidak memberi id; dibuat sendiri supaya jejak tool
                # tetap dapat dirujuk pada log dan jawaban API.
                "id": p.get("id") or f"call_{i}_{fungsi.get('name', 'tool')}",
                "name": fungsi.get("name", ""),
                "arguments": _argumen(fungsi.get("arguments")),
                "raw": p,
            }
        )

    return {
        "content": pesan.get("content"),
        "tool_calls": panggilan,
        "model": data.get("model", model),
        "metrics": {
            "total_ms": int((data.get("total_duration") or 0) / 1_000_000),
            "eval_count": data.get("eval_count") or 0,
        },
    }


def _argumen(raw) -> dict:
    """
    Ollama mengirim argumen sebagai objek, tetapi sebagian model tetap
    membungkusnya sebagai teks JSON. Keduanya diterima.
    """
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        hasil = json.loads(raw)
        return hasil if isinstance(hasil, dict) else {}
    except (json.JSONDecodeError, TypeError):
        log.warning("Argumen tool bukan JSON yang sah: %s", str(raw)[:200])
        return {}


def pesan_asisten(content: str | None, panggilan: list[dict]) -> dict:
    """Balasan model yang memuat permintaan tool, dalam bentuk yang Ollama pahami."""
    return {
        "role": "assistant",
        "content": content or "",
        "tool_calls": [p["raw"] for p in panggilan],
    }


def pesan_tool(panggilan: dict, hasil: dict) -> dict:
    """
    Hasil satu tool.

    Ollama mencocokkan hasil dengan permintaannya berdasarkan urutan, bukan id.
    `tool_name` disertakan karena versi Ollama yang lebih baru memakainya, dan
    versi lama mengabaikan field yang tidak dikenal.
    """
    return {
        "role": "tool",
        "tool_name": panggilan["name"],
        "content": json.dumps(hasil, ensure_ascii=False),
    }
