# -*- coding: utf-8 -*-
"""
Titik masuk API Inventory Management.

Tahap ini hanya melayani satu alur: penerimaan barang.
"""

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .auth import pengguna_saat_ini
from .config import (CORS_ORIGIN_REGEX, DB_TOLAK_SUPERUSER,
                     FORECAST_MODEL_PRELOAD, FORECAST_USE_MODEL, JWT_SECRET,
                     LOG_LEVEL)
from .db import close_pool, pool, readonly
from . import i18n
from .errors import AppError
from .limiter import limiter
from .ml import predict
from .routers import (assistant, auth, catalog, dashboard, demo,
                      forecast_api, forecasting, inventory, lifetime, master,
                      purchase_orders, reorder, reports, stock_issues,
                      stock_receipts, transfer, users)

# Tanpa ini seluruh log.info di app/ hilang tanpa jejak: uvicorn hanya memasang
# handler untuk logger miliknya sendiri, dan logger akar bawaannya berada di
# level WARNING. Handler dipasang langsung pada namespace "inventory" -- bukan
# lewat basicConfig pada akar -- supaya tidak bergantung pada urutan uvicorn
# menyiapkan logging, dan supaya menaikkan level aplikasi tidak membuat
# pustaka pihak ketiga ikut cerewet.
_handler = logging.StreamHandler()
_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s",
                      "%Y-%m-%d %H:%M:%S")
)
log = logging.getLogger("inventory")
log.setLevel(LOG_LEVEL)
log.handlers = [_handler]
log.propagate = False


def _periksa_konfigurasi_keamanan() -> None:
    """
    Dua kesalahan konfigurasi yang tidak akan pernah terlihat dengan menguji
    aplikasi, dan keduanya membatalkan seluruh pemisahan penyewa.

    KUNCI TOKEN KOSONG berarti tanda tangan token dibuat dengan string kosong:
    siapa pun dapat menerbitkan token atas nama pengguna mana pun.

    TERSAMBUNG SEBAGAI SUPERUSER berarti PostgreSQL membebaskan aplikasi dari
    SELURUH Row Level Security. Setiap halaman tetap tampil normal, setiap
    query tetap berhasil, dan tidak ada satu pun galat yang terbit -- yang
    berubah hanyalah bahwa penyewa mana pun melihat data seluruh penyewa.
    Justru karena tidak menimbulkan gejala apa pun, ia diperiksa di sini.
    """
    if not JWT_SECRET:
        raise RuntimeError(
            "JWT_SECRET belum diisi pada .env. Buat kunci baru dengan:\n"
            "    python -c \"import secrets; print(secrets.token_urlsafe(48))\""
        )

    with readonly() as cur:
        cur.execute("SELECT current_setting('is_superuser') AS super, "
                    "current_user AS pengguna")
        b = cur.fetchone()

    if b["super"] == "on":
        pesan = (
            f"Aplikasi tersambung ke PostgreSQL sebagai superuser "
            f"({b['pengguna']}). Superuser dibebaskan dari seluruh Row Level "
            f"Security, sehingga pemisahan antar perusahaan TIDAK AKTIF dan "
            f"setiap penyewa dapat melihat data penyewa lain.\n"
            f"Perbaiki dengan menyambung sebagai role aplikasi:\n"
            f"    ALTER ROLE inventory_app LOGIN PASSWORD '<kata sandi>';\n"
            f"lalu arahkan DATABASE_URL pada .env ke role tersebut."
        )
        if DB_TOLAK_SUPERUSER:
            raise RuntimeError(pesan)
        log.warning("PEMISAHAN PENYEWA TIDAK AKTIF. %s", pesan)


def _periksa_berkas_model() -> None:
    """
    Menolak menyala bila model prakiraan diminta tetapi berkasnya tidak ada.

    KENAPA INI HARUS FATAL. Tanpa pemeriksaan ini, berkas model yang hilang
    hanya menghasilkan satu baris peringatan di log, dan sistem melanjutkan
    dengan rata-rata bergerak berbobot. Setiap halaman tetap terisi, setiap
    angka tetap masuk akal, dan tidak ada satu pun yang terlihat rusak -- yang
    berubah hanyalah bahwa seluruh prakiraan menjadi lebih buruk, diam-diam,
    sampai ada yang kebetulan membaca log.

    Sejak berkas model dipindahkan ke direktori yang dipasang dari luar (lihat
    FORECAST_MODEL_DIR), kemungkinan itu menjadi nyata: satu tanda -v yang
    salah ketik, satu direktori yang dipindahkan di host, dan model 757 MB itu
    hilang tanpa jejak. Yang membedakan "sengaja tidak memakai model" dari
    "modelnya hilang" adalah FORECAST_USE_MODEL; selama ia menyala, berkasnya
    wajib ada.
    """
    if not FORECAST_USE_MODEL:
        return

    kurang = [b for b in (predict.BERKAS_MODEL, predict.BERKAS_META)
              if not b.exists()]
    if not kurang:
        return

    raise RuntimeError(
        "Model prakiraan diminta (FORECAST_USE_MODEL=true) tetapi berkasnya "
        "tidak ditemukan:\n"
        + "".join(f"    {b}\n" for b in kurang)
        + f"Direktori model yang dipakai: {predict.MODEL_DIR}\n"
        "Bila berjalan di kontainer, pastikan direktori model dipasang, mis.:\n"
        "    docker run -v /home/sml/meru/ai_inventory/backend/models:/models:ro "
        "-e FORECAST_MODEL_DIR=/models ...\n"
        "Untuk sengaja berjalan TANPA model -- prakiraan memakai rata-rata "
        "bergerak berbobot -- setel FORECAST_USE_MODEL=false."
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    pool()  # gagal cepat saat start bila kredensial salah
    _periksa_konfigurasi_keamanan()
    _periksa_berkas_model()
    if FORECAST_MODEL_PRELOAD:
        # Di utas terpisah dan tidak menghalangi: berkas modelnya ratusan MB.
        # Server tetap melayani selama pemuatan; permintaan prakiraan yang
        # datang lebih dulu memakai rata-rata bergerak berbobot, bukan
        # menunggu. Utasnya tetap satu -- proses uvicorn juga satu -- sehingga
        # model hanya pernah ada satu salinan di memori.
        threading.Thread(target=predict.muat_awal, name="muat-model",
                         daemon=True).start()
    yield
    close_pool()


app = FastAPI(title="Inventory Management API", version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def bahasa_permintaan(request: Request, call_next):
    """
    Menyetel bahasa satu permintaan, sekali, dari query string.

    Endpoint yang memang menyusun kalimat tetap menerima `lang` sebagai
    parameter biasa -- itu eksplisit dan terbaca pada tanda tangannya. Yang
    dilayani middleware ini adalah PESAN GALAT: ia lahir jauh di dalam lapisan
    data (pemeriksa stok, pencari baris) yang tidak punya urusan dengan
    tampilan, dan melewatkan `lang` sampai ke sana berarti menambah satu
    parameter pada belasan fungsi hanya demi satu kalimat kegagalan.
    """
    i18n.set_bahasa_permintaan(request.query_params.get("lang"))
    return await call_next(request)

# Masuk dan mendaftar harus dapat dicapai tanpa token -- itu justru yang
# sedang diminta. Penjagaan per endpoint ada di dalam routernya sendiri.
app.include_router(auth.router)
app.include_router(users.router)

# SELURUH router data di bawah menuntut token yang sah. Dependency-nya dipasang
# di sini, satu tempat, bukan di setiap endpoint: endpoint yang lupa memasangnya
# tidak akan menolak siapa pun dan tidak akan menimbulkan gejala apa pun sampai
# seseorang menemukannya. Di sini, menambah router baru tanpa penjaga terlihat
# sebagai baris yang berbeda sendiri.
#
# Dependency ini juga yang MENYETEL penyewa untuk permintaan tersebut. Tanpa
# ia berjalan lebih dulu, app/db.py tidak punya apa pun untuk disalin ke
# setelan sesi dan seluruh query mengembalikan nol baris.
WAJIB_MASUK = [Depends(pengguna_saat_ini)]

app.include_router(dashboard.router, dependencies=WAJIB_MASUK)
app.include_router(catalog.router, dependencies=WAJIB_MASUK)
app.include_router(inventory.router, dependencies=WAJIB_MASUK)
app.include_router(stock_receipts.router, dependencies=WAJIB_MASUK)
app.include_router(stock_issues.router, dependencies=WAJIB_MASUK)
app.include_router(purchase_orders.router, dependencies=WAJIB_MASUK)
app.include_router(reports.router, dependencies=WAJIB_MASUK)
app.include_router(forecasting.router, dependencies=WAJIB_MASUK)
app.include_router(forecast_api.router, dependencies=WAJIB_MASUK)
app.include_router(reorder.router, dependencies=WAJIB_MASUK)
# Transfer Antar Gudang berdiri SESUDAH Pemesanan Ulang, dan urutan itu adalah
# urutan pertanyaannya: berapa yang kurang dijawab lebih dulu, dari mana
# ditutup dijawab sesudahnya. Modul ini meminjam angka kekurangan dari mesin
# reorder tanpa menghitung ulang satu pun rumusnya -- lihat catatan di
# app/transfer.py.
app.include_router(transfer.router, dependencies=WAJIB_MASUK)
app.include_router(lifetime.router, dependencies=WAJIB_MASUK)
app.include_router(assistant.router, dependencies=WAJIB_MASUK)
app.include_router(demo.router, dependencies=WAJIB_MASUK)
app.include_router(master.router, dependencies=WAJIB_MASUK)
# Impor massal, penyesuaian stok, dan transfer antar gudang dihapus pada
# 31 Agustus 2026 bersama halamannya: ketiganya berdiri di luar alur
# "data dasar -> input manual -> kecerdasan AI" yang kini menjadi bentuk
# aplikasi ini. Arsip kodenya ada di backups/.
#
# Deteksi Anomali dihapus seluruhnya pada 2 September 2026 -- mesin deteksi,
# tabel temuan, pemindai batch, dan halamannya -- dan tempatnya pada alur AI
# diisi Analisis Umur Pakai. Yang dijawab modul lama adalah "apakah pola
# jumlah stok berubah"; yang dijawab penggantinya adalah "apakah komponen
# bertahan sesuai umur pakainya", sebuah pertanyaan yang punya jawaban
# referensi di master barang (items.service_life_value, migrasi 029) alih-alih
# hanya punya ambang statistik yang harus dikalibrasi terus-menerus.


@app.exception_handler(AppError)
async def handle_app_error(_: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content=exc.body())


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError):
    """
    Menyederhanakan galat pydantic menjadi satu pesan yang bisa dibaca, lengkap
    dengan nama field-nya. Bentuk bawaan FastAPI terlalu teknis untuk pengguna.
    """
    pertama = exc.errors()[0]
    lokasi = ".".join(str(p) for p in pertama.get("loc", []) if p != "body")
    pesan = pertama.get("msg", "Permintaan tidak valid.")
    pesan = pesan.replace("Value error, ", "")
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": pesan,
                "field": lokasi or None,
            }
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected(_: Request, exc: Exception):
    """
    Jaring terakhir. Galat asli dicatat di log server; klien hanya menerima
    pesan umum supaya struktur basis data tidak bocor keluar.
    """
    log.exception("Kesalahan tak terduga", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Terjadi kesalahan pada server. Tidak ada data yang tersimpan.",
            }
        },
    )


@app.get("/api/health", tags=["meta"])
def health() -> dict:
    with readonly() as cur:
        cur.execute("SELECT 1 AS ok")
        cur.fetchone()
    return {"status": "ok", "database": "terhubung",
            "forecast_model": predict.info()}
