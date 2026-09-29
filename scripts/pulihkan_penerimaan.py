# -*- coding: utf-8 -*-
"""
Memulihkan stock_receipts, stock_receipt_items, dan stock_movements dari
data/parquet/.

Diperlukan karena satu perintah pembersihan data uji memakai penyaring
`reference_number LIKE 'PO-%'`, dan ternyata SELURUH penerimaan bawaan memakai
pola nomor referensi yang sama -- bukan hanya satu baris uji yang dimaksud.

Aman dijalankan berulang: hanya baris yang id-nya BELUM ada di basis data yang
disisipkan, jadi menjalankannya dua kali tidak menggandakan apa pun.

    .venv/bin/python scripts/pulihkan_penerimaan.py [id_perusahaan]

PERUSAHAAN PEMILIK. Sejak sistem menjadi banyak-penyewa, setiap baris data
punya pemilik. Skrip ini menyisipkan baris tanpa menyebut company_id, sehingga
kolom itu terisi dari setelan sesi -- persis seperti yang dilakukan aplikasi.
Setelannya dipasang di bawah dari argumen baris perintah; bawaannya 1, yaitu
perusahaan yang memiliki seluruh data lama. Tanpa langkah itu, setiap INSERT
ditolak NOT NULL.
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg

AKAR = Path(__file__).resolve().parents[1]


def dsn() -> str:
    """
    Alamat basis data, dibaca dari .env.

    Sebelumnya alamat ini beserta kata sandinya tertulis langsung di berkas ini.
    Kata sandi yang tinggal di dalam kode ikut ke mana pun kode itu disalin --
    ke laptop, ke riwayat git, ke tangkapan layar saat menjelaskan skrip ini --
    dan tidak ada cara menariknya kembali selain menggantinya.

    Dijalankan sebagai inventory_admin (pemilik tabel), bukan role aplikasi:
    skrip ini menyisipkan baris dengan id aslinya lewat OVERRIDING SYSTEM VALUE,
    yang memang di luar kewenangan role aplikasi.
    """
    for baris in (AKAR / ".env").read_text(encoding="utf-8-sig").splitlines():
        if baris.strip().startswith("DATABASE_URL="):
            return baris.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("DATABASE_URL tidak ditemukan pada .env")

TABEL = {
    "stock_receipts": [
        "id", "receipt_number", "supplier_id", "warehouse_id", "receipt_date",
        "reference_number", "status", "notes", "created_at", "updated_at",
    ],
    "stock_receipt_items": [
        "id", "stock_receipt_id", "item_id", "quantity", "unit_price",
        "batch_number", "serial_number", "received_date", "expiry_date",
        "created_at", "updated_at",
    ],
    "stock_movements": [
        "id", "item_id", "warehouse_id", "movement_type", "reference_id",
        "movement_date", "quantity", "unit_price", "batch_number", "created_at",
    ],
}


def bersih(v):
    """NaN/NaT dari pandas menjadi NULL; tipe numpy menjadi tipe Python."""
    if v is None or v is pd.NaT:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    return v


def main() -> None:
    company_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            # Berlaku sepanjang sesi (argumen ketiga false), bukan per
            # transaksi: skrip ini melakukan commit di antara setiap tabel, dan
            # setelan per transaksi akan hilang pada commit yang pertama.
            cur.execute("SELECT set_config('app.company_id', %s, false)",
                        (str(company_id),))
        print(f"Memulihkan atas nama perusahaan id = {company_id}")

        for nama, kolom in TABEL.items():
            d = pd.read_parquet(f"data/parquet/{nama}.parquet")
            with conn.cursor() as cur:
                cur.execute(f"SELECT id FROM {nama}")
                ada = {r[0] for r in cur}

            hilang = d[~d["id"].isin(ada)][kolom]
            if hilang.empty:
                print(f"{nama}: sudah lengkap ({len(ada)} baris)")
                continue

            stg = f"pulih_{nama}"
            with conn.cursor() as cur:
                # Staging tanpa identity supaya id asli dapat dipertahankan.
                cur.execute(f"DROP TABLE IF EXISTS {stg}")
                cur.execute(f"CREATE UNLOGGED TABLE {stg} (LIKE {nama})")
                cur.execute(f"ALTER TABLE {stg} ALTER COLUMN id DROP IDENTITY IF EXISTS")
                with cur.copy(f"COPY {stg} ({','.join(kolom)}) FROM STDIN") as cp:
                    for baris in hilang.itertuples(index=False, name=None):
                        cp.write_row([bersih(v) for v in baris])

                cur.execute(
                    f"""
                    INSERT INTO {nama} ({','.join(kolom)})
                    OVERRIDING SYSTEM VALUE
                    SELECT {','.join(kolom)} FROM {stg} s
                    WHERE NOT EXISTS (SELECT 1 FROM {nama} t WHERE t.id = s.id)
                    """
                )
                dipulihkan = cur.rowcount
                cur.execute(f"DROP TABLE {stg}")

                # Identity harus melompati id yang baru disisipkan, kalau tidak
                # baris berikutnya akan bentrok pada primary key.
                cur.execute(
                    f"SELECT setval(pg_get_serial_sequence('{nama}', 'id'), "
                    f"(SELECT max(id) FROM {nama}))"
                )
                cur.execute(f"SELECT count(*) FROM {nama}")
                print(f"{nama}: +{dipulihkan} baris, total {cur.fetchone()[0]}")
            conn.commit()


if __name__ == "__main__":
    main()
