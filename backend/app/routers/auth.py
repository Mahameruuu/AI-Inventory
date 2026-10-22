# -*- coding: utf-8 -*-
"""
Masuk, lupa kata sandi, dan pengelolaan akun sendiri.

Ini satu-satunya router yang sebagian endpoint-nya berjalan TANPA penyewa.
Masuk dan meminta setel ulang kata sandi memang harus begitu: perusahaan yang
bersangkutan justru yang sedang dicari. Keduanya lewat fungsi SECURITY
DEFINER (migrasi 037) -- sempit dan disengaja, dan tidak ada jalur lain di
seluruh aplikasi yang boleh membaca lintas perusahaan.

Pendaftaran mandiri dicabut pada 22 Oktober 2026: perusahaan baru dibuat orang
dalam, pengguna baru dibuat admin dari halaman Pengguna.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from .. import i18n, tenant
from ..auth import (SANDI_MINIMAL, buat_token, hash_sandi,
                    pengguna_saat_ini, periksa_kekuatan_sandi, sandi_cocok)
from ..db import readonly, transaction
from ..errors import AppError
from ..limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Hash asli dari kata sandi acak. Dipakai saat username tidak ditemukan supaya
# jalur "username salah" tetap membayar waktu bcrypt yang sama dengan jalur "kata
# sandi salah". Tanpa ini, jawaban yang datang lebih cepat memberi tahu bahwa
# username tersebut tidak terdaftar -- pembedaan yang sudah susah payah
# dihilangkan dari kalimat galatnya.
_HASH_UMPAN = "$2b$12$C6UzMDM.H6dfI/f/IKcEe.9GpP.MMc0jVpEO/EiaG9wjhtLdRhAAK"


# ==========================================================================
# Bentuk permintaan dan jawaban
# ==========================================================================

class MasukIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class LupaSandiIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)


class GantiSandiIn(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=SANDI_MINIMAL)


class PenggunaOut(BaseModel):
    id: int
    username: str
    email: str | None = None
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


def _sesi(user: dict, company: dict) -> SesiOut:
    token, berakhir = buat_token(user["id"], company["id"], user["role"],
                                 user["token_version"])
    return SesiOut(
        access_token=token,
        expires_at=berakhir.isoformat(),
        user=PenggunaOut(id=user["id"], username=user["username"], email=user.get("email"),
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
    Menukar username dan kata sandi dengan token akses.

    Seluruh kegagalan -- username tidak ada, kata sandi salah -- dijawab
    kalimat yang sama. Membedakannya berarti halaman ini dapat dipakai
    memeriksa username mana yang terdaftar.
    """
    username = body.username.strip().lower()

    with readonly() as cur:
        cur.execute("SELECT * FROM auth_cari_pengguna(%s)", (username,))
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


@router.post("/forgot-password", status_code=202)
@limiter.limit("5/minute")
def lupa_sandi(request: Request, body: LupaSandiIn) -> dict:
    """
    Mencatat permintaan setel ulang kata sandi untuk admin perusahaannya.

    Jawabannya SELALU sama, ada atau tidaknya username itu: halaman ini tidak
    boleh menjadi alat menebak username yang terdaftar. Dibatasi lima kali per
    menit per alamat untuk alasan yang sama.
    """
    with transaction() as cur:
        cur.execute("SELECT auth_minta_reset_sandi(%s)", (body.username.strip().lower(),))
    return {"message": i18n.t("auth.reset_requested", i18n.bahasa_permintaan())}


@router.get("/me")
def saya(p: tenant.Penyewa = Depends(pengguna_saat_ini)) -> dict:
    """
    Siapa pemegang token ini. Dipakai antarmuka saat halaman dimuat ulang:
    token masih ada di peramban, tetapi nama, peran, dan perusahaannya tidak.
    """
    with readonly() as cur:
        cur.execute(
            """
            SELECT u.id, u.username, u.email, u.full_name, u.role, u.last_login_at,
                   c.id AS company_id, c.name AS company_name,
                   c.slug AS company_slug, c.is_demo
              FROM users u JOIN companies c ON c.id = u.company_id
             WHERE u.id = %s
            """,
            (p.user_id,),
        )
        b = cur.fetchone()

    return {
        "user": {"id": b["id"], "username": b["username"], "email": b["email"],
                 "full_name": b["full_name"],
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
            RETURNING id, username, email, full_name, role, token_version
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
