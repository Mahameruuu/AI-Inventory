# -*- coding: utf-8 -*-
"""
Penyiapan bersama untuk seluruh uji.

BERKAS INI DIIMPOR SEBELUM MODUL UJI MANA PUN, dan itulah sebabnya penyetelan
lingkungan tinggal di sini. app/config.py membaca seluruh variabel lingkungan
sekali saat diimpor, lalu app/db.py menyalin DATABASE_URL ke namespace-nya
sendiri. Menyetelnya dari dalam modul uji sudah terlambat -- nilai yang dipakai
sudah terlanjur dibaca.

DAN INI JUGA YANG MENJAGA BASIS DATA SUNGGUHAN. Selama DATABASE_URL diarahkan
ke basis data uji di sini, tidak ada uji yang bisa menyentuh data produksi
walau ia salah tulis: alamatnya memang tidak menunjuk ke sana.
"""

import os
import re
import subprocess
from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
NAMA_DB_UJI = "inventory_uji_penyewa"

# ROLE TERSENDIRI UNTUK PENGUJIAN, DAN INI PENTING.
#
# Basis data boleh dibuang dan dibuat ulang sesuka hati, tetapi ROLE di
# PostgreSQL berlaku untuk SATU KLUSTER -- bukan per basis data. Menyetel kata
# sandi inventory_app dari sini akan mengganti kata sandi role yang sedang
# dipakai aplikasi yang berjalan, dan backend produksi berhenti dapat menyambung
# begitu seseorang menjalankan pytest. Kegagalan itu tidak akan terlihat di sini
# sama sekali: seluruh uji tetap lulus.
#
# Karena itu pengujian memakai role sendiri, dan haknya diberikan LANGSUNG di
# dalam basis data uji -- bukan lewat keanggotaan pada inventory_app.
# Keanggotaan role juga berlaku satu kluster: menjadikannya anggota
# inventory_app berarti ia ikut memegang seluruh hak di basis data PRODUKSI,
# dan kata sandinya tertulis terbuka pada berkas ini. Hak yang diberikan per
# basis data berhenti di basis data uji.
#
# Hak yang diberikan sengaja sama persis dengan yang diterima inventory_app
# pada migrasi 028, supaya yang diuji benar-benar sama dengan yang dijalankan.
# Ia bukan pemilik tabel dan bukan superuser, jadi seluruh policy RLS berlaku
# atasnya persis seperti pada aplikasi sungguhan.
ROLE_UJI = "inventory_app_uji"
SANDI_UJI = "uji-lokal-sementara"


def _url_dari_env() -> str:
    """
    Alamat basis data BERHAK ADMIN, untuk membangun basis data uji.

    ADMIN_DATABASE_URL didahulukan karena DATABASE_URL kini menunjuk role
    aplikasi -- role non-superuser yang memang TIDAK boleh membuat basis data.
    Memakainya di sini akan membuat seluruh uji yang menyentuh basis data
    dilewati dengan alasan "tidak dapat menghubungi PostgreSQL", yang menyesatkan:
    servernya baik-baik saja, hanya rolenya yang tidak berhak.
    """
    berkas = AKAR / ".env"
    if not berkas.exists():
        return ""
    nilai: dict[str, str] = {}
    for baris in berkas.read_text(encoding="utf-8-sig").splitlines():
        for kunci in ("ADMIN_DATABASE_URL=", "DATABASE_URL="):
            if baris.strip().startswith(kunci):
                nilai[kunci.rstrip("=")] = baris.split("=", 1)[1].strip().strip('"').strip("'")
    return nilai.get("ADMIN_DATABASE_URL") or nilai.get("DATABASE_URL", "")


URL_ADMIN = _url_dari_env()
INDUK = URL_ADMIN.rsplit("/", 1)[0] if URL_ADMIN else ""
HOST = re.sub(r"^postgresql://[^@]*@", "", INDUK) if INDUK else ""

if HOST:
    os.environ.setdefault(
        "DATABASE_URL",
        f"postgresql://{ROLE_UJI}:{SANDI_UJI}@{HOST}/{NAMA_DB_UJI}")

os.environ.setdefault("JWT_SECRET", "kunci-uji-jangan-dipakai-di-produksi")
# Berkas modelnya ratusan MB dan tidak ada uji di sini yang memerlukannya.
os.environ.setdefault("FORECAST_MODEL_PRELOAD", "false")
os.environ.setdefault("FORECAST_USE_MODEL", "false")
os.environ.setdefault("ALLOW_SIGNUP", "true")


def bangun_basis_uji() -> str | None:
    """
    Membangun ulang basis data uji dari nol lewat database/migrate.sql.

    Mengembalikan alasan kegagalan sebagai teks bila tidak bisa -- server tidak
    terjangkau, psql tidak terpasang -- supaya uji yang membutuhkannya dapat
    dilewati dengan keterangan, bukan gagal seolah-olah kodenya yang salah.
    """
    if not URL_ADMIN:
        return "DATABASE_URL tidak ada pada .env"

    def psql(target: str, *arg: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["psql", target, "-q", "-v", "ON_ERROR_STOP=1", *arg],
            capture_output=True, text=True, cwd=AKAR, timeout=180)

    coba = psql(f"{INDUK}/postgres", "-c", "SELECT 1")
    if coba.returncode != 0:
        return f"tidak dapat menghubungi PostgreSQL: {coba.stderr.strip()[:200]}"

    for perintah in (f'DROP DATABASE IF EXISTS "{NAMA_DB_UJI}"',
                     f'CREATE DATABASE "{NAMA_DB_UJI}"'):
        h = psql(f"{INDUK}/postgres", "-c", perintah)
        if h.returncode != 0:
            return f"gagal menyiapkan basis data uji: {h.stderr.strip()[:200]}"

    h = psql(f"{INDUK}/{NAMA_DB_UJI}", "-f", "database/migrate.sql")
    if h.returncode != 0:
        return f"migrasi gagal: {h.stderr.strip()[:400]}"

    h = psql(f"{INDUK}/{NAMA_DB_UJI}", "-c", f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{ROLE_UJI}') THEN
                CREATE ROLE {ROLE_UJI} LOGIN PASSWORD '{SANDI_UJI}';
            ELSE
                ALTER ROLE {ROLE_UJI} LOGIN PASSWORD '{SANDI_UJI}';
            END IF;
        END $$;

        GRANT USAGE ON SCHEMA public TO {ROLE_UJI};
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {ROLE_UJI};
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {ROLE_UJI};
        GRANT EXECUTE ON FUNCTION auth_cari_pengguna(TEXT) TO {ROLE_UJI};
        GRANT EXECUTE ON FUNCTION
            auth_daftar_perusahaan(TEXT, TEXT, TEXT, TEXT, TEXT) TO {ROLE_UJI};
    """)
    if h.returncode != 0:
        return f"gagal menyiapkan role uji: {h.stderr.strip()[:300]}"

    return None
