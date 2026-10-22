# -*- coding: utf-8 -*-
"""
Penyewa yang sedang dilayani, per permintaan.

KENAPA CONTEXTVAR, BUKAN PARAMETER. Penyaringan penyewa harus terjadi pada
SETIAP query, dan seluruh query di aplikasi ini lahir di dalam `transaction()`
atau `readonly()` di app/db.py. Melewatkan company_id sebagai parameter berarti
menyentuh dua ratus pemanggilan di dua belas router -- dan yang lebih buruk,
membuat "lupa melewatkannya" menjadi kesalahan yang mungkin terjadi. Disimpan
di sini, kedua pintu basis data itu mengambilnya sendiri, dan tidak ada satu
pun router yang perlu tahu bahwa sistem ini banyak-penyewa.

Pola yang sama sudah dipakai app/i18n.py untuk bahasa permintaan; berkas ini
mengikutinya supaya hanya ada satu cara membaca "keadaan permintaan yang
sedang berjalan" di seluruh kode.

YANG MENJAGA KEBENARANNYA BUKAN BERKAS INI. Nilai di sini hanya disalin ke
setelan sesi PostgreSQL; yang benar-benar menolak baris milik penyewa lain
adalah policy Row Level Security pada migrasi 028. Bila berkas ini keliru dan
tidak menyetel apa pun, akibatnya adalah halaman kosong -- bukan data orang
lain.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class Penyewa:
    """Siapa yang sedang dilayani. Dibekukan supaya tidak ada yang mengubahnya
    di tengah permintaan."""

    company_id: int
    company_name: str = ""
    # Kosong untuk pekerjaan latar (skrip pemeliharaan, pembangun riwayat)
    # yang berjalan atas nama perusahaan, bukan atas nama orang.
    user_id: int | None = None
    email: str = ""
    username: str = ""
    role: str = ""


_penyewa: ContextVar[Penyewa | None] = ContextVar("penyewa", default=None)


def set_penyewa(p: Penyewa | None) -> None:
    _penyewa.set(p)


def penyewa() -> Penyewa | None:
    return _penyewa.get()


def company_id() -> int | None:
    """
    Perusahaan yang sedang aktif, atau None bila permintaan ini memang berjalan
    tanpa penyewa -- pemeriksaan kesehatan dan jalur masuk termasuk di
    dalamnya.
    """
    p = _penyewa.get()
    return p.company_id if p else None


@contextmanager
def jalankan_sebagai(id_perusahaan: int, nama: str = ""):
    """
    Menjalankan satu blok atas nama satu perusahaan, di luar permintaan HTTP.

    Dipakai pekerjaan latar dan skrip pemeliharaan: keduanya tidak punya token,
    tetapi tetap harus menyebut untuk siapa mereka bekerja. Tanpa ini, keduanya
    akan membaca nol baris begitu RLS aktif -- dan diamnya itulah yang membuat
    kegagalan seperti ini sulit ditemukan.

    Nilai sebelumnya dikembalikan saat blok selesai, sehingga pemanggilan
    bersarang tidak saling menimpa.
    """
    token = _penyewa.set(Penyewa(company_id=id_perusahaan, company_name=nama))
    try:
        yield
    finally:
        _penyewa.reset(token)
