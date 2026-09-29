# -*- coding: utf-8 -*-
"""
Masuk, daftar, dan pengelolaan akun sendiri.

Ini satu-satunya router yang sebagian endpoint-nya berjalan TANPA penyewa.
Masuk dan mendaftar memang harus begitu: perusahaan yang bersangkutan justru
yang sedang dicari atau baru akan dibuat. Keduanya lewat fungsi SECURITY
DEFINER pada migrasi 028 -- dua-duanya sempit dan disengaja, dan tidak ada
jalur lain di seluruh aplikasi yang boleh membaca lintas perusahaan.
"""

from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, Depends
from psycopg import errors as pg_errors
from pydantic import BaseModel, EmailStr, Field

from .. import i18n, tenant
from ..auth import (SANDI_MINIMAL, buat_token, hash_sandi,
                    pengguna_saat_ini, periksa_kekuatan_sandi, sandi_cocok)
from ..config import ALLOW_SIGNUP
from ..db import readonly, transaction
from ..errors import AppError

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Hash asli dari kata sandi acak. Dipakai saat email tidak ditemukan supaya
# jalur "email salah" tetap membayar waktu bcrypt yang sama dengan jalur "kata
# sandi salah". Tanpa ini, jawaban yang datang lebih cepat memberi tahu bahwa
# email tersebut tidak terdaftar -- pembedaan yang sudah susah payah
# dihilangkan dari kalimat galatnya.
_HASH_UMPAN = "$2b$12$C6UzMDM.H6dfI/f/IKcEe.9GpP.MMc0jVpEO/EiaG9wjhtLdRhAAK"


# ==========================================================================
# Bentuk permintaan dan jawaban
# ==========================================================================

class MasukIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class DaftarIn(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255)
    # Boleh dikosongkan: diturunkan dari nama perusahaan bila tidak diisi.
    slug: str | None = Field(default=None, max_length=80)
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=SANDI_MINIMAL)


class GantiSandiIn(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=SANDI_MINIMAL)


class PenggunaOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str


class PerusahaanOut(BaseModel):
    id: int
    name: str
    slug: str
    is_demo: bool


class SesiOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: str
    user: PenggunaOut
    company: PerusahaanOut


# ==========================================================================
# Pembantu
# ==========================================================================

def _galat(kunci: str, status: int, kode: str, **params) -> AppError:
    return AppError(status, kode,
                    i18n.t(kunci, i18n.bahasa_permintaan(), **params))


def _slug_dari(nama: str) -> str:
    """
    Mengubah nama perusahaan menjadi pengenal yang aman dipakai di URL.

    Huruf beraksen diuraikan lebih dulu supaya "Café Nusantara" menjadi
    "cafe-nusantara", bukan kehilangan huruf e-nya. Hasil yang kosong -- nama
    yang seluruhnya berupa aksara non-latin -- diberi awalan tetap, karena
    slug kosong akan ditolak CHECK pada tabel companies.
    """
    dasar = unicodedata.normalize("NFKD", nama).encode("ascii", "ignore").decode()
    dasar = re.sub(r"[^a-zA-Z0-9]+", "-", dasar).strip("-").lower()
    dasar = re.sub(r"-{2,}", "-", dasar)[:70]
    return dasar or "perusahaan"


def _sesi(user: dict, company: dict) -> SesiOut:
    token, berakhir = buat_token(user["id"], company["id"], user["role"],
                                 user["token_version"])
    return SesiOut(
        access_token=token,
        expires_at=berakhir.isoformat(),
        user=PenggunaOut(id=user["id"], email=user["email"],
                         full_name=user["full_name"], role=user["role"]),
        company=PerusahaanOut(id=company["id"], name=company["name"],
                              slug=company["slug"],
                              is_demo=company.get("is_demo", False)),
    )


# ==========================================================================
# Endpoint
# ==========================================================================

@router.post("/login", response_model=SesiOut)
def masuk(body: MasukIn) -> SesiOut:
    """
    Menukar email dan kata sandi dengan token akses.

    Seluruh kegagalan -- email tidak ada, kata sandi salah, akun nonaktif --
    dijawab kalimat yang sama. Membedakannya berarti halaman ini dapat dipakai
    memeriksa email mana yang terdaftar.
    """
    email = body.email.strip().lower()

    with readonly() as cur:
        cur.execute("SELECT * FROM auth_cari_pengguna(%s)", (email,))
        baris = cur.fetchone()

    if baris is None:
        sandi_cocok(body.password, _HASH_UMPAN)  # bayar waktu yang sama
        raise _galat("err.auth.credentials_invalid", 401, "UNAUTHENTICATED")

    if not sandi_cocok(body.password, baris["password_hash"]):
        raise _galat("err.auth.credentials_invalid", 401, "UNAUTHENTICATED")

    if not baris["is_active"]:
        raise _galat("err.auth.user_inactive", 403, "FORBIDDEN")
    if not baris["company_aktif"]:
        raise _galat("err.auth.company_inactive", 403, "FORBIDDEN")

    # Mulai titik ini penyewa sudah diketahui, sehingga penulisan di bawah
    # lolos RLS.
    with tenant.jalankan_sebagai(baris["company_id"], baris["company_name"]):
        with transaction() as cur:
            cur.execute(
                "UPDATE users SET last_login_at = now() WHERE id = %s",
                (baris["id"],),
            )
            cur.execute(
                "SELECT id, name, slug, is_demo FROM companies WHERE id = %s",
                (baris["company_id"],),
            )
            perusahaan = cur.fetchone()

    return _sesi(baris, perusahaan)


@router.post("/signup", response_model=SesiOut, status_code=201)
def daftar(body: DaftarIn) -> SesiOut:
    """
    Membuat perusahaan baru beserta pengguna owner-nya, lalu langsung
    memasukkannya. Pendaftar yang harus masuk sendiri setelah mendaftar hanya
    menambah satu langkah yang tidak memberi apa-apa.
    """
    if not ALLOW_SIGNUP:
        raise _galat("err.auth.signup_disabled", 403, "FORBIDDEN")

    periksa_kekuatan_sandi(body.password)

    email = body.email.strip().lower()
    slug_diminta = (body.slug or "").strip().lower() or _slug_dari(body.company_name)
    sandi = hash_sandi(body.password)

    # Slug yang bentrok dicoba ulang dengan akhiran angka -- nama perusahaan
    # yang mirip itu lumrah, dan menolak pendaftaran hanya karena itu berarti
    # kehilangan calon pelanggan di layar pertama. Slug yang DIISI SENDIRI oleh
    # pendaftar tidak diutak-atik: ia meminta alamat tertentu, dan memberinya
    # alamat lain diam-diam lebih buruk daripada mengatakan alamat itu sudah
    # dipakai.
    kandidat = [slug_diminta] if body.slug else [
        slug_diminta, *(f"{slug_diminta}-{n}" for n in range(2, 7))
    ]

    for slug in kandidat:
        try:
            with transaction() as cur:
                cur.execute(
                    "SELECT * FROM auth_daftar_perusahaan(%s, %s, %s, %s, %s)",
                    (body.company_name.strip(), slug, email,
                     body.full_name.strip(), sandi),
                )
                hasil = cur.fetchone()
            break
        except pg_errors.UniqueViolation as e:
            nama_constraint = (e.diag.constraint_name or "")
            if nama_constraint == "users_email_unique":
                raise _galat("err.auth.email_taken", 409, "CONFLICT",
                             email=email) from None
            if nama_constraint == "companies_slug_unique":
                continue
            raise
    else:
        raise _galat("err.auth.slug_taken", 409, "CONFLICT", slug=slug_diminta)

    with tenant.jalankan_sebagai(hasil["company_id"], body.company_name.strip()):
        with readonly() as cur:
            cur.execute(
                """
                SELECT u.id, u.email, u.full_name, u.role, u.token_version,
                       c.id AS c_id, c.name AS c_name, c.slug AS c_slug,
                       c.is_demo AS c_demo
                  FROM users u JOIN companies c ON c.id = u.company_id
                 WHERE u.id = %s
                """,
                (hasil["user_id"],),
            )
            b = cur.fetchone()

    return _sesi(b, {"id": b["c_id"], "name": b["c_name"], "slug": b["c_slug"],
                     "is_demo": b["c_demo"]})


@router.get("/me")
def saya(p: tenant.Penyewa = Depends(pengguna_saat_ini)) -> dict:
    """
    Siapa pemegang token ini. Dipakai antarmuka saat halaman dimuat ulang:
    token masih ada di peramban, tetapi nama, peran, dan perusahaannya tidak.
    """
    with readonly() as cur:
        cur.execute(
            """
            SELECT u.id, u.email, u.full_name, u.role, u.last_login_at,
                   c.id AS company_id, c.name AS company_name,
                   c.slug AS company_slug, c.is_demo
              FROM users u JOIN companies c ON c.id = u.company_id
             WHERE u.id = %s
            """,
            (p.user_id,),
        )
        b = cur.fetchone()

    return {
        "user": {"id": b["id"], "email": b["email"], "full_name": b["full_name"],
                 "role": b["role"], "last_login_at": b["last_login_at"]},
        "company": {"id": b["company_id"], "name": b["company_name"],
                    "slug": b["company_slug"], "is_demo": b["is_demo"]},
    }


@router.post("/change-password", response_model=SesiOut)
def ganti_sandi(body: GantiSandiIn,
                p: tenant.Penyewa = Depends(pengguna_saat_ini)) -> SesiOut:
    """
    Mengganti kata sandi sendiri.

    token_version ikut dinaikkan, sehingga seluruh token lama -- termasuk yang
    tertinggal di perangkat lain -- langsung tidak berlaku. Itu memang inti
    penggantian kata sandi: kalau sesi lama tetap hidup, mengganti kata sandi
    setelah menduga akun dibobol tidak mengusir siapa pun. Token baru untuk
    perangkat yang sedang dipakai dikembalikan di jawaban ini supaya pengguna
    tidak terlempar keluar dari layar yang sedang ia buka.
    """
    periksa_kekuatan_sandi(body.new_password)

    with transaction() as cur:
        cur.execute("SELECT password_hash FROM users WHERE id = %s", (p.user_id,))
        baris = cur.fetchone()
        if baris is None or not sandi_cocok(body.current_password,
                                            baris["password_hash"]):
            raise _galat("err.auth.password_wrong", 422, "VALIDATION_ERROR")

        cur.execute(
            """
            UPDATE users
               SET password_hash = %s,
                   token_version = token_version + 1,
                   updated_at    = now()
             WHERE id = %s
            RETURNING id, email, full_name, role, token_version
            """,
            (hash_sandi(body.new_password), p.user_id),
        )
        pengguna = cur.fetchone()

        cur.execute("SELECT id, name, slug, is_demo FROM companies WHERE id = %s",
                    (p.company_id,))
        perusahaan = cur.fetchone()

    return _sesi(pengguna, perusahaan)


@router.post("/logout-all", status_code=204)
def keluar_semua(p: tenant.Penyewa = Depends(pengguna_saat_ini)) -> None:
    """
    Mencabut seluruh token milik pengguna ini, termasuk yang sedang dipakai
    memanggil endpoint ini.

    Keluar dari SATU perangkat tidak perlu memanggil server -- token cukup
    dibuang dari peramban. Yang tidak bisa dikerjakan sendiri oleh peramban
    adalah mengusir perangkat lain, dan itulah yang dilayani di sini.
    """
    with transaction() as cur:
        cur.execute(
            "UPDATE users SET token_version = token_version + 1 WHERE id = %s",
            (p.user_id,),
        )
