# -*- coding: utf-8 -*-
"""
Identitas: siapa yang sedang memakai sistem, dan atas nama perusahaan mana.

BATAS TANGGUNG JAWAB. Berkas ini MEMBUKTIKAN identitas dan menaruhnya di
app/tenant.py. Ia tidak menyaring satu baris data pun -- penyaringannya
dikerjakan Row Level Security di basis data (migrasi 028). Pembagian ini
disengaja: kalau berkas ini keliru, akibatnya permintaan ditolak atau halaman
kosong. Kalau penyaringan ikut tinggal di sini, satu kekeliruan yang sama
berarti data satu klien tampil di layar klien lain.

KATA SANDI. Disimpan sebagai hash bcrypt. bcrypt hanya membaca 72 bita
pertama dan menolak yang lebih panjang, jadi batas itu ditegakkan di sini
secara terang-terangan -- memotong diam-diam berarti dua kata sandi berbeda
yang 72 bita pertamanya sama akan sama-sama diterima.

TOKEN. JWT bertanda tangan, tanpa penyimpanan sesi di server. Konsekuensinya
jujur: token yang sudah terbit tidak bisa dihapus. Yang membatasinya dua hal --
umurnya (JWT_TTL_HOURS) dan kolom users.token_version, yang ikut ditandatangani
dan diperiksa ulang pada setiap permintaan. Menaikkan angka itu membuat seluruh
token lama milik satu pengguna langsung ditolak.

SATU QUERY TAMBAHAN PER PERMINTAAN. Memeriksa token_version berarti membaca
baris pengguna setiap kali. Itu memang harga yang dibayar, dan dibayar dengan
sadar: tanpa pembacaan itu, menonaktifkan karyawan yang keluar hari ini baru
berlaku setelah tokennya kedaluwarsa sendiri. Pembacaannya satu baris lewat
kunci primer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Request
from starlette.concurrency import run_in_threadpool

from . import i18n, tenant
from .config import JWT_ALGORITHM, JWT_SECRET, JWT_TTL_HOURS
from .db import readonly
from .errors import AppError

# Panjang minimal kata sandi. Sepuluh, bukan delapan: delapan sudah menjadi
# angka bawaan di mana-mana sehingga daftar kata sandi bocoran pun disusun
# untuk panjang itu.
SANDI_MINIMAL = 10
# Batas keras bcrypt. Bukan pilihan kami.
SANDI_MAKSIMAL_BITA = 72


# ==========================================================================
# Kata sandi
# ==========================================================================

def periksa_kekuatan_sandi(sandi: str) -> None:
    """Menolak kata sandi yang tidak memenuhi syarat. Diam bila lolos."""
    if len(sandi) < SANDI_MINIMAL:
        raise AppError(
            422, "VALIDATION_ERROR",
            i18n.t("err.auth.password_weak", i18n.bahasa_permintaan(),
                   minimal=SANDI_MINIMAL),
            field="password",
        )
    if len(sandi.encode("utf-8")) > SANDI_MAKSIMAL_BITA:
        raise AppError(
            422, "VALIDATION_ERROR",
            f"Kata sandi terlalu panjang (maksimal {SANDI_MAKSIMAL_BITA} bita).",
            field="password",
        )


def hash_sandi(sandi: str) -> str:
    return bcrypt.hashpw(sandi.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def sandi_cocok(sandi: str, hash_tersimpan: str) -> bool:
    """
    Membandingkan kata sandi dengan hash. bcrypt.checkpw membandingkan dalam
    waktu tetap, sehingga lamanya jawaban tidak membocorkan seberapa jauh
    tebakan mendekati.

    Hash yang rusak atau berformat asing dijawab False, bukan pengecualian:
    satu baris cacat di basis data tidak boleh membuat halaman masuk balas
    dengan galat 500 yang membedakannya dari kata sandi salah biasa.
    """
    try:
        return bcrypt.checkpw(sandi.encode("utf-8"),
                              hash_tersimpan.encode("ascii"))
    except (ValueError, TypeError):
        return False


# ==========================================================================
# Token
# ==========================================================================

def buat_token(user_id: int, company_id: int, role: str,
               token_version: int) -> tuple[str, datetime]:
    """Menerbitkan token akses. Mengembalikan token beserta waktu berakhirnya
    supaya antarmuka dapat menampilkan atau menjadwalkan perpanjangan."""
    sekarang = datetime.now(timezone.utc)
    berakhir = sekarang + timedelta(hours=JWT_TTL_HOURS)
    muatan = {
        "sub": str(user_id),
        "cid": company_id,
        "role": role,
        "tv": token_version,
        "iat": int(sekarang.timestamp()),
        "exp": int(berakhir.timestamp()),
    }
    return jwt.encode(muatan, JWT_SECRET, algorithm=JWT_ALGORITHM), berakhir


def _galat_auth(kunci: str, status: int = 401, **params) -> AppError:
    return AppError(status, "UNAUTHENTICATED" if status == 401 else "FORBIDDEN",
                    i18n.t(kunci, i18n.bahasa_permintaan(), **params))


def baca_token(token: str) -> dict:
    """
    Membuka token dan memastikan tanda tangannya sah.

    Algoritmanya disebut secara tertutup pada daftar `algorithms`. Tanpa itu,
    token bisa datang dengan header alg yang dipilih penyerang -- termasuk
    "none" -- dan pustaka akan menurutinya.
    """
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise _galat_auth("err.auth.token_expired") from None
    except jwt.InvalidTokenError:
        raise _galat_auth("err.auth.token_invalid") from None


def _token_dari_permintaan(request: Request) -> str:
    header = request.headers.get("authorization") or ""
    bagian = header.split(None, 1)
    if len(bagian) != 2 or bagian[0].lower() != "bearer" or not bagian[1].strip():
        raise _galat_auth("err.auth.token_missing")
    return bagian[1].strip()


# ==========================================================================
# Dependency
# ==========================================================================

def _baca_pengguna(company_id: int, user_id: int) -> dict | None:
    """
    Membaca satu baris pengguna. Dipanggil di utas terpisah -- lihat catatan
    pada pengguna_saat_ini -- sehingga penyewa harus disetel di dalam utas itu
    sendiri, bukan diwarisi dari pemanggilnya.
    """
    tenant.set_penyewa(tenant.Penyewa(company_id=company_id))
    with readonly() as cur:
        cur.execute(
            """
            SELECT u.id, u.company_id, u.username, u.email, u.full_name, u.role,
                   u.is_active, u.token_version,
                   c.name AS company_name, c.is_active AS company_aktif
              FROM users u
              JOIN companies c ON c.id = u.company_id
             WHERE u.id = %s
            """,
            (user_id,),
        )
        return cur.fetchone()


async def pengguna_saat_ini(request: Request) -> tenant.Penyewa:
    """
    Penjaga setiap endpoint yang menyentuh data, sekaligus yang MENYETEL
    penyewa untuk permintaan tersebut.

    KENAPA async PADAHAL ISINYA MEMBACA BASIS DATA. Ini bukan pilihan gaya,
    melainkan syarat supaya fungsi ini bekerja sama sekali. FastAPI menjalankan
    dependency yang sync di utas pekerja lewat run_in_threadpool, dan utas itu
    menerima SALINAN context -- ContextVar yang disetel di dalamnya tidak
    kembali ke pemanggil. Akibatnya penyewa hilang begitu dependency selesai,
    endpoint berjalan tanpa penyewa, app/db.py tidak menyetel app.company_id,
    dan setiap policy RLS menolak seluruh baris. Yang terlihat: pengguna
    berhasil masuk, setiap permintaan dijawab 200, dan setiap halaman kosong --
    tanpa satu pun galat yang menunjuk ke sini.

    Sebagai coroutine, fungsi ini berjalan di context permintaan itu sendiri,
    sehingga nilai yang disetel di baris terakhir ikut terbawa saat FastAPI
    menyalin context untuk menjalankan endpoint. Pembacaan basis datanya
    dipindahkan ke utas pekerja secara terang-terangan supaya event loop tidak
    terhalang.
    """
    muatan = baca_token(_token_dari_permintaan(request))
    try:
        company_id = int(muatan["cid"])
        user_id = int(muatan["sub"])
        token_version = int(muatan["tv"])
    except (KeyError, TypeError, ValueError):
        raise _galat_auth("err.auth.token_invalid") from None

    baris = await run_in_threadpool(_baca_pengguna, company_id, user_id)

    # Pengguna yang sudah dihapus, dan token yang menyebut perusahaan lain --
    # keduanya tampak sama dari sini, dan keduanya memang tidak sah.
    if baris is None or baris["token_version"] != token_version:
        raise _galat_auth("err.auth.token_invalid")
    if not baris["is_active"]:
        raise _galat_auth("err.auth.user_inactive", 403)
    if not baris["company_aktif"]:
        raise _galat_auth("err.auth.company_inactive", 403)

    # Peran diambil dari basis data, BUKAN dari token: peran yang diturunkan
    # lima menit lalu harus berlaku sekarang, bukan setelah token kedaluwarsa.
    penyewa = tenant.Penyewa(
        company_id=baris["company_id"],
        company_name=baris["company_name"],
        user_id=baris["id"],
        email=baris["email"] or "",
        username=baris["username"],
        role=baris["role"],
    )
    tenant.set_penyewa(penyewa)
    return penyewa


def wajib_peran(*peran_diizinkan: str):
    """
    Dependency yang membatasi endpoint pada peran tertentu.

        @router.post("", dependencies=[Depends(wajib_peran("owner", "admin"))])

    owner selalu lolos tanpa perlu disebut: pemilik perusahaan tidak boleh bisa
    mengunci dirinya sendiri keluar dari pengaturan perusahaannya sendiri.
    """
    izin = set(peran_diizinkan) | {"owner"}

    def penjaga(p: tenant.Penyewa = Depends(pengguna_saat_ini)) -> tenant.Penyewa:
        if p.role not in izin:
            raise _galat_auth("err.auth.forbidden", 403, peran=p.role)
        return p

    return penjaga


# Peran yang boleh mengubah data transaksi, dan yang boleh mengurus perusahaan.
# Diberi nama supaya router tidak menyalin-nyalin daftar peran, dan menambah
# peran baru kelak cukup mengubah satu baris.
wajib_penulis = wajib_peran("admin", "staff")
wajib_admin = wajib_peran("admin")
