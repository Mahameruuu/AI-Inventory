# -*- coding: utf-8 -*-
"""
Membuat penyewa demo beserta pengguna dan isinya.

    python -m app.jobs.buat_demo --username demo --sandi 'RahasiaDemo1'

Dijalankan SEKALI oleh operator. Sesudahnya, mengisi ulang dan menyimulasikan
penjualan dilakukan lewat tombol di layar, tidak perlu menyentuh baris perintah
lagi.

TIDAK MENUNTUT HAK ISTIMEWA. Perintah ini berjalan dengan DATABASE_URL yang
sama seperti aplikasi, yaitu sebagai role aplikasi biasa. Pembuatan perusahaan
lewat fungsi auth_buat_perusahaan (migrasi 037; tidak ada endpoint yang
memanggilnya) -- dan sisanya berjalan sebagai penyewa demo itu sendiri. Tidak ada
langkah yang perlu superuser, sehingga tidak ada alasan menjalankan perintah ini
dengan kredensial admin basis data.

AMAN DIJALANKAN ULANG. Bila username yang diberikan sudah terdaftar, perusahaannya
dipakai kembali dan isinya disegarkan -- bukan membuat perusahaan demo kedua
yang menumpuk tanpa ada yang menghapusnya.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .. import demo, tenant
from ..auth import hash_sandi, periksa_kekuatan_sandi
from ..db import close_pool, readonly, transaction

log = logging.getLogger("inventory.demo")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    ap = argparse.ArgumentParser(description="Membuat penyewa demo")
    ap.add_argument("--username", default="demo", help="username owner demo")
    ap.add_argument("--sandi", required=True, help="kata sandi pengguna owner demo")
    ap.add_argument("--nama", default="Demo Inventory AI",
                    help="nama perusahaan demo")
    ap.add_argument("--slug", default="demo", help="pengenal untuk URL")
    ap.add_argument("--nama-pengguna", default="Akun Demo",
                    help="nama lengkap pengguna owner")
    ap.add_argument("--hari", type=int, default=demo.HARI_RIWAYAT,
                    help="panjang riwayat yang dibangkitkan")
    a = ap.parse_args()

    periksa_kekuatan_sandi(a.sandi)
    username = a.username.strip().lower()

    try:
        # --- perusahaan sudah ada? ---
        with readonly() as cur:
            cur.execute("SELECT * FROM auth_cari_pengguna(%s)", (username,))
            ada = cur.fetchone()

        if ada:
            company_id = ada["company_id"]
            log.info("Username sudah terdaftar; memakai perusahaan id %s (%s)",
                     company_id, ada["company_name"])
            with tenant.jalankan_sebagai(company_id, ada["company_name"]):
                with readonly() as cur:
                    cur.execute("SELECT is_demo FROM companies")
                    if not cur.fetchone()["is_demo"]:
                        sys.exit(
                            f"Perusahaan milik {username} BUKAN perusahaan demo. "
                            f"Menolak mengisinya dengan data demo -- pakai username "
                            f"lain."
                        )
        else:
            with transaction() as cur:
                cur.execute(
                    "SELECT * FROM auth_buat_perusahaan(%s, %s, %s, %s, %s)",
                    (a.nama, a.slug, username, a.nama_pengguna, hash_sandi(a.sandi)),
                )
                company_id = cur.fetchone()["company_id"]

            # Penandaan demo terpisah dari pembuatannya: fungsi pembuat
            # perusahaan sengaja tidak tahu apa-apa tentang demo, supaya
            # perusahaan sungguhan tidak pernah bisa keliru bertanda demo --
            # dan karenanya boleh dikosongkan dari layar.
            with tenant.jalankan_sebagai(company_id, a.nama):
                with transaction() as cur:
                    cur.execute("UPDATE companies SET is_demo = TRUE WHERE id = %s",
                                (company_id,))
            log.info("Perusahaan demo dibuat: id %s", company_id)

        # --- isi ulang ---
        with tenant.jalankan_sebagai(company_id, a.nama):
            with transaction() as cur:
                terhapus = demo.kosongkan(cur)
                ringkas = demo.isi(cur, a.hari)

        print(json.dumps(
            {"company_id": company_id, "username": username,
             "terhapus": terhapus, "terisi": ringkas},
            ensure_ascii=False, indent=2))
    finally:
        close_pool()


if __name__ == "__main__":
    main()
