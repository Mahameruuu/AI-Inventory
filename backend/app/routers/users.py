# -*- coding: utf-8 -*-
"""
Pengelolaan pengguna di dalam satu perusahaan.

Seluruh endpoint di sini hanya untuk admin dan owner. Penyaringan antar
perusahaan TIDAK ditulis di berkas ini: policy users_penyewa pada migrasi 028
sudah membuat setiap query di bawah hanya melihat pengguna perusahaan sendiri.
Menuliskannya lagi di sini hanya akan menjadi salinan kedua dari aturan yang
sama, yang bisa ikut salah tanpa ketahuan bila salah satunya diubah.

Yang MEMANG harus ditulis di sini adalah aturan yang tidak diketahui basis
data: seseorang tidak boleh menurunkan perannya sendiri, dan owner tidak boleh
dinonaktifkan. Keduanya bukan soal kepemilikan baris, melainkan soal jangan
sampai ada perusahaan yang kehilangan seluruh pemegang kuncinya.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from psycopg import errors as pg_errors
from pydantic import BaseModel, EmailStr, Field

from .. import i18n, tenant
from ..auth import (SANDI_MINIMAL, hash_sandi, pengguna_saat_ini,
                    periksa_kekuatan_sandi, wajib_admin)
from ..common import PAGE_SIZE_DEFAULT, clamp_page, page_envelope
from ..db import readonly, transaction
from ..errors import AppError, not_found

router = APIRouter(prefix="/api/users", tags=["users"])

PERAN_DAPAT_DIBERIKAN = ("admin", "staff", "viewer")


class PenggunaBaru(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=SANDI_MINIMAL)
    role: str = Field(default="staff")


class PenggunaUbah(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: str | None = None
    is_active: bool | None = None


class SandiBaru(BaseModel):
    new_password: str = Field(..., min_length=SANDI_MINIMAL)


def _galat(kunci: str, status: int, kode: str, **params) -> AppError:
    return AppError(status, kode,
                    i18n.t(kunci, i18n.bahasa_permintaan(), **params))


def _periksa_peran(peran: str) -> str:
    """
    owner sengaja TIDAK ada di daftar yang boleh diberikan. Owner lahir sekali
    saat perusahaan didaftarkan, dan indeks users_owner_tunggal pada migrasi
    025 hanya mengizinkan satu per perusahaan -- memberikannya lewat endpoint
    ini akan ditolak basis data dengan pesan yang tidak berarti apa-apa bagi
    pengguna. Pemindahan kepemilikan adalah tindakan tersendiri yang belum ada,
    dan menyamarkannya sebagai "ubah peran" akan membuatnya tampak lebih ringan
    daripada yang sebenarnya.
    """
    if peran not in PERAN_DAPAT_DIBERIKAN:
        raise AppError(
            422, "VALIDATION_ERROR",
            f"Peran harus salah satu dari: {', '.join(PERAN_DAPAT_DIBERIKAN)}.",
            field="role",
        )
    return peran


@router.get("", dependencies=[Depends(wajib_admin)])
def daftar_pengguna(
    q: str | None = Query(None, description="Cari nama atau email"),
    only_active: bool = Query(False),
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if q:
        where += " AND (u.full_name ILIKE %s OR u.email ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if only_active:
        where += " AND u.is_active"

    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM users u {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT u.id, u.email, u.full_name, u.role, u.is_active,
                   u.last_login_at, u.created_at
              FROM users u
            {where}
             ORDER BY (u.role = 'owner') DESC, u.full_name
             LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        return page_envelope(cur.fetchall(), total, page, page_size)


@router.post("", status_code=201, dependencies=[Depends(wajib_admin)])
def buat_pengguna(body: PenggunaBaru) -> dict:
    periksa_kekuatan_sandi(body.password)
    peran = _periksa_peran(body.role)
    email = body.email.strip().lower()

    # company_id tidak disebut: DEFAULT kolomnya membacanya dari setelan sesi,
    # sama seperti seluruh tabel lain sejak migrasi 026.
    try:
        with transaction() as cur:
            cur.execute(
                """
                INSERT INTO users (email, full_name, password_hash, role)
                VALUES (%s, %s, %s, %s)
                RETURNING id, email, full_name, role, is_active, created_at
                """,
                (email, body.full_name.strip(), hash_sandi(body.password), peran),
            )
            return cur.fetchone()
    except pg_errors.UniqueViolation:
        # Email unik sedunia (lihat migrasi 025), jadi bentrokan bisa datang
        # dari perusahaan lain yang tidak boleh diketahui keberadaannya.
        # Kalimatnya karena itu tidak menyebut di mana email itu sudah dipakai.
        raise _galat("err.auth.email_taken", 409, "CONFLICT", email=email) from None


@router.patch("/{user_id}")
def ubah_pengguna(user_id: int, body: PenggunaUbah,
                  saya: tenant.Penyewa = Depends(wajib_admin)) -> dict:
    with transaction() as cur:
        cur.execute(
            "SELECT id, role, is_active FROM users WHERE id = %s", (user_id,))
        sasaran = cur.fetchone()
        if sasaran is None:
            raise not_found("user", user_id)

        menyentuh_hak = body.role is not None or body.is_active is not None

        # Mengubah hak diri sendiri: satu-satunya cara admin mengunci dirinya
        # sendiri keluar dari halaman ini. Namanya sendiri tetap boleh diubah.
        if menyentuh_hak and sasaran["id"] == saya.user_id:
            raise _galat("err.auth.diri_sendiri", 422, "VALIDATION_ERROR")

        # Owner adalah pemegang kunci terakhir perusahaan. Menurunkan atau
        # menonaktifkannya berarti perusahaan itu kehilangan siapa pun yang
        # berhak mengangkat admin baru.
        if menyentuh_hak and sasaran["role"] == "owner":
            raise _galat("err.auth.owner_terakhir", 422, "VALIDATION_ERROR")

        set_bagian, params = [], []
        if body.full_name is not None:
            set_bagian.append("full_name = %s")
            params.append(body.full_name.strip())
        if body.role is not None:
            set_bagian.append("role = %s")
            params.append(_periksa_peran(body.role))
        if body.is_active is not None:
            set_bagian.append("is_active = %s")
            params.append(body.is_active)
            # Menonaktifkan akun harus berlaku SEKARANG. Tanpa menaikkan
            # token_version, orang yang baru saja dinonaktifkan tetap bisa
            # bekerja sampai tokennya kedaluwarsa sendiri -- berjam-jam
            # setelah keputusan diambil.
            if not body.is_active:
                set_bagian.append("token_version = token_version + 1")

        if not set_bagian:
            raise AppError(422, "VALIDATION_ERROR",
                           "Tidak ada perubahan yang dikirim.")

        set_bagian.append("updated_at = now()")
        params.append(user_id)
        cur.execute(
            f"UPDATE users SET {', '.join(set_bagian)} WHERE id = %s "
            "RETURNING id, email, full_name, role, is_active",
            params,
        )
        return cur.fetchone()


@router.post("/{user_id}/reset-password", status_code=204,
             dependencies=[Depends(wajib_admin)])
def setel_ulang_sandi(user_id: int, body: SandiBaru) -> None:
    """
    Menyetel kata sandi pengguna lain -- jalur "saya lupa kata sandi" yang
    ditempuh lewat admin, bukan lewat email. Pemulihan lewat email menuntut
    pengiriman surat yang belum ada di sistem ini; menyediakan tombolnya
    sekarang tanpa itu hanya akan menjadi tombol yang tidak melakukan apa-apa.

    Seluruh sesi pengguna yang bersangkutan ikut dicabut: kata sandi diganti
    justru saat kendali atas akun itu diragukan.
    """
    periksa_kekuatan_sandi(body.new_password)
    with transaction() as cur:
        cur.execute(
            """
            UPDATE users
               SET password_hash = %s,
                   token_version = token_version + 1,
                   updated_at    = now()
             WHERE id = %s
            RETURNING id
            """,
            (hash_sandi(body.new_password), user_id),
        )
        if cur.fetchone() is None:
            raise not_found("user", user_id)
