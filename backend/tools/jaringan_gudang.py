# -*- coding: utf-8 -*-
"""
Jaringan empat gudang, sepuluh barang habis pakai di dalamnya, dan riwayat
transfer setahun -- bahan bagi rekomendasi rute berbasis riwayat.

    cd backend && ../.venv/bin/python -m tools.jaringan_gudang --perusahaan utama [--terapkan]

Tanpa --terapkan hanya menampilkan rencana; basis data tidak disentuh.

APA YANG DIKERJAKAN (untuk satu perusahaan):

  1. Dua gudang baru: Semarang (di Pulau Jawa) dan Makassar (di luar Jawa,
     hanya terjangkau laut/udara), berikut matriks jarak 12 arah.
  2. Sepuluh barang habis pakai dibangun ulang di empat gudang dengan riwayat
     365 hari. Posisi stok akhir tiap gudang DITETAPKAN sebagai kelipatan titik
     pesan (SEBAR), sehingga halaman Transfer punya skenario yang sama tiap kali
     dijalankan: ada gudang yang kekurangan, ada beberapa sumber yang
     bersaing, dan ada tujuan yang hanya bisa dicapai lewat laut atau udara.
  3. Riwayat transfer setahun: ratusan dokumen SELESAI dengan moda, biaya,
     lama di jalan, dan jumlah yang benar-benar diterima. Inilah bahan latih
     model rute (app/rute_ml.py).
  4. Dokumen transfer yang sudah ada (skenario komponen) dilengkapi moda dan
     biayanya.

INI DATA BANGKITAN. Riwayat transfer disimulasikan dari model dunia
app/logistik.py ditambah ragam yang bisa dipelajari model -- musim mudik dan
cuaca, keterlambatan khas pasangan gudang, harga BBM, dan insiden kerusakan
sesekali. Skripnya menyebut itu terang-terangan supaya tidak ada yang
menyangka tarif di layar adalah kutipan pelayaran sungguhan.

INTEGRITAS BUKU BESAR. Tiap transfer selesai menulis transfer_out di gudang
asal dan transfer_in di gudang tujuan (sebesar yang DITERIMA; selisihnya rusak
di jalan). Supaya saldo akhir tiap pasangan tetap persis seperti yang
ditetapkan SEBAR, gudang asal "memesan pengganti" (penerimaan) beberapa hari
sesudah barangnya berangkat dan gudang tujuan "memakai" kiriman itu
(pengeluaran) beberapa hari sesudah tiba. Keduanya transaksi biasa, dan saldo
berjalan tiap pasangan dijaga tidak pernah minus.
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import logistik, tenant                              # noqa: E402
from app.common import (LOCK_ISSUE, LOCK_RECEIPT, LOCK_TRANSFER,  # noqa: E402
                        next_document_number)
from app.db import close_pool, transaction                    # noqa: E402

BENIH = 20260929
HARI_RIWAYAT = 365
# Transfer historis berhenti sekian hari sebelum hari ini: dokumen skenario hari
# ini (diajukan/disetujui/dijalan) tidak boleh berbenturan dengan arsip.
HARI_JEDA_ARSIP = 25

# --- gudang -------------------------------------------------------------
# kunci abstrak -> kode gudang per penyewa
PETA = {
    "utama": {"SBY": "WH-CEN-01", "JKT": "WH-CEN-02", "SMG": "WH-CEN-03", "MKS": "WH-CEN-04"},
    "demo": {"SBY": "WH-SBY", "JKT": "WH-JKT", "SMG": "WH-SMG", "MKS": "WH-MKS"},
}
PERUSAHAAN = {"utama": (1, "Perusahaan Utama"), "demo": (2, "Demo Inventory AI")}

# (kunci, nama utama, nama demo, lokasi, lintang, bujur, waktu tempuh ke gudang ini)
GUDANG_BARU = [
    ("SMG", "Central Warehouse Semarang", "Gudang Semarang",
     "Kaligawe, Semarang", -6.9500, 110.4700, 2),
    ("MKS", "Central Warehouse Makassar", "Gudang Makassar",
     "Tamalanrea, Makassar", -5.1400, 119.4800, 8),
]

# Jarak yang ditetapkan tangan (km) dan waktu tempuh bawaan (hari). Pasangan
# Jawa: jalan tol Trans-Jawa. Pasangan ke Makassar: pelayaran (tidak ada jalan).
# (asal, tujuan, km, hari, catatan)
JARAK = [
    ("SBY", "JKT", 780.0, 2, "Tol Trans-Jawa, langsung"),
    ("JKT", "SBY", 795.0, 3, "Tol Trans-Jawa, muat balik lewat Semarang"),
    ("SBY", "SMG", 355.0, 1, "Tol Trans-Jawa"),
    ("SMG", "SBY", 350.0, 1, "Tol Trans-Jawa"),
    ("JKT", "SMG", 445.0, 1, "Tol Trans-Jawa"),
    ("SMG", "JKT", 450.0, 1, "Tol Trans-Jawa, padat di Cikampek"),
    ("SBY", "MKS", 980.0, 7, "Kapal kargo Tanjung Perak - Soekarno-Hatta, jadwal mingguan"),
    ("MKS", "SBY", 980.0, 7, "Kapal kargo Soekarno-Hatta - Tanjung Perak, jadwal mingguan"),
    ("JKT", "MKS", 1780.0, 9, "Kapal kargo Tanjung Priok - Makassar"),
    ("MKS", "JKT", 1780.0, 9, "Kapal kargo Makassar - Tanjung Priok"),
    ("SMG", "MKS", 1150.0, 8, "Kapal kargo Tanjung Emas - Makassar"),
    ("MKS", "SMG", 1150.0, 8, "Kapal kargo Makassar - Tanjung Emas"),
]

# --- barang habis pakai -------------------------------------------------
# sku -> {gudang: posisi stok akhir sebagai kelipatan titik pesan}. Arti angkanya
# sama dengan app/demo.SEBARAN: 0,55-0,90 di bawah titik pesan (kekurangan);
# 1,70 surplus sebagian; 3,40 surplus yang menutup seluruh kebutuhan; 2,0-2,4
# aman. Waktu tunggu dipatok tujuh hari karena aritmetikanya berdiri di atasnya.
SEBAR = {
    "SP-1001": {"SBY": 3.40, "JKT": 0.55, "SMG": 2.00, "MKS": 0.50},  # Makassar & Jakarta kurang
    "CP-6001": {"JKT": 3.40, "SBY": 0.55, "SMG": 1.90, "MKS": 0.60},
    "PL-2001": {"SBY": 1.70, "JKT": 0.80, "MKS": 0.70},               # sumber terbatas -> sebagian
    "EL-3001": {"SBY": 2.20, "SMG": 2.10, "JKT": 2.00, "MKS": 2.00},
    "PD-4001": {"SBY": 2.20, "JKT": 2.10, "SMG": 2.00, "MKS": 2.20},
    "CP-6004": {"SBY": 2.30, "JKT": 2.20, "SMG": 2.00},
    "SP-1003": {"JKT": 2.40, "SMG": 2.10, "SBY": 2.00, "MKS": 0.65},  # Makassar kurang
    "SP-1004": {"JKT": 2.30, "SBY": 2.10, "MKS": 2.00, "SMG": 0.60},  # Semarang kurang (darat)
    "PL-2003": {"JKT": 2.20, "SBY": 2.00, "SMG": 2.10},
    "PD-4002": {"JKT": 2.20, "SMG": 2.00, "MKS": 2.10, "SBY": 2.00},
}
TUNGGU = 7
# kode satuan demo -> kandidat kode pada perusahaan
_SATUAN_ALT = {"LTR": ("LTR", "LITER"), "MTR": ("MTR", "METER")}


def rencana_barang(peta: dict[str, str], hari_ini: date) -> list[dict]:
    """Baris rencana barang habis pakai (satu per barang x gudang)."""
    from app import demo
    katalog = {b[0]: b for b in demo.BARANG}
    hasil = []
    for n, (sku, tempat) in enumerate(SEBAR.items(), start=101):
        _, nama, kat, sat, harga, laju, kritis, _ = katalog[sku]
        kode_satuan = demo.SATUAN[sat][1]
        for kunci in sorted(tempat):
            hasil.append({
                "nomor": n, "sku": sku, "nama": nama, "harian": True,
                "kategori": demo.KATEGORI[kat],
                "satuan_calon": _SATUAN_ALT.get(kode_satuan, (kode_satuan,)),
                "harga": harga, "kritis": kritis, "laju": laju,
                "tunggu_awal": TUNGGU,
                "kode_gudang": peta[kunci], "kunci_gudang": kunci,
                "sasaran": None, "rumah": False,
                "lantai": tempat[kunci],
                "pesanan_hari": demo.HARI_STOK_PESANAN,
                "mulai": hari_ini - timedelta(days=HARI_RIWAYAT),
            })
    return hasil


# --- master -------------------------------------------------------------

def tambah_cabang(cur, jenis: str) -> dict[str, int]:
    """Gudang Semarang dan Makassar (idempoten) serta matriks jarak 12 arah."""
    peta = PETA[jenis]
    ids: dict[str, int] = {}
    cur.execute("SELECT id, code, latitude, longitude FROM warehouses")
    ada = {r["code"]: r for r in cur.fetchall()}
    for kunci, nama_utama, nama_demo, lokasi, lat, lon, tempuh in GUDANG_BARU:
        kode = peta[kunci]
        if kode in ada:
            ids[kunci] = ada[kode]["id"]
            continue
        cur.execute(
            "INSERT INTO warehouses (code, name, location, latitude, longitude, "
            "transfer_lead_time_days) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (kode, nama_utama if jenis == "utama" else nama_demo, lokasi, lat, lon, tempuh))
        ids[kunci] = cur.fetchone()["id"]
    for kunci in ("SBY", "JKT"):
        kode = peta[kunci]
        if kode not in ada:
            raise SystemExit(f"Gudang {kode} tidak ada; dihentikan.")
        ids[kunci] = ada[kode]["id"]
    # Koordinat gudang lama dipastikan terisi: moda dan jarak dihitung darinya.
    koordinat = {"SBY": (-7.2575, 112.7521), "JKT": (-6.2088, 106.8456)}
    for kunci, (lat, lon) in koordinat.items():
        if ada[peta[kunci]]["latitude"] is None or ada[peta[kunci]]["longitude"] is None:
            cur.execute("UPDATE warehouses SET latitude = %s, longitude = %s WHERE id = %s",
                        (lat, lon, ids[kunci]))
    cur.execute("DELETE FROM warehouse_distances")
    for asal, tujuan, km, hari, cat in JARAK:
        cur.execute(
            "INSERT INTO warehouse_distances (from_warehouse_id, to_warehouse_id, "
            "distance_km, lead_time_days, notes) VALUES (%s, %s, %s, %s, %s)",
            (ids[asal], ids[tujuan], km, hari, cat))
    return ids


def siapkan_barang(cur, baris: list[dict]) -> int:
    """Membuat kategori dan barang habis pakai yang belum ada; mengembalikan jumlah baru."""
    cur.execute("SELECT name FROM items")
    ada = {r["name"] for r in cur.fetchall()}
    dibuat = 0
    for r in baris:
        if r["nama"] in ada:
            continue
        ada.add(r["nama"])
        cur.execute("SELECT id FROM categories WHERE name = %s", (r["kategori"],))
        k = cur.fetchone()
        if k is None:
            cur.execute("INSERT INTO categories (name) VALUES (%s) RETURNING id",
                        (r["kategori"],))
            k = cur.fetchone()
        cur.execute("SELECT id FROM units WHERE code = ANY(%s)", (list(r["satuan_calon"]),))
        u = cur.fetchone()
        if u is None:
            raise SystemExit(f"Satuan tidak ada: {r['satuan_calon']}")
        cur.execute(
            """
            INSERT INTO items (sku, name, category_id, unit_id, unit_price,
                               criticality, lead_time_days, usage_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'habis_pakai')
            """,
            (r["sku"], r["nama"], k["id"], u["id"], r["harga"], r["kritis"], r["tunggu_awal"]))
        dibuat += 1
    return dibuat


# --- model dunia: hasil NYATA sebuah kiriman ----------------------------

# Keterlambatan khas pasangan gudang (hari): sesuatu yang dapat dipelajari model.
_TUNDA_PASANGAN = {
    ("SMG", "JKT", "darat"): 0.35,      # tol Cikampek padat
    ("JKT", "SMG", "darat"): 0.25,
    ("SBY", "MKS", "laut"): 0.6,        # antrean pelabuhan Makassar
    ("JKT", "MKS", "laut"): 0.9,
    ("SMG", "MKS", "laut"): 0.7,
    ("MKS", "SBY", "laut"): 0.4,
    ("MKS", "JKT", "laut"): 0.6,
    ("MKS", "SMG", "laut"): 0.5,
}


def hasil_nyata(acak: random.Random, moda: str, jarak: float, jumlah: int,
                nilai: float, tgl: date, dari: str, ke: str) -> dict:
    """Lama tempuh, biaya, dan jumlah diterima SESUNGGUHNYA satu kiriman."""
    dasar = logistik.tarif_standar(moda, jarak, jumlah, nilai)
    bulan = tgl.month
    musim = 1.0
    if moda == "darat":
        musim = 1.35 if bulan in (3, 4) else (1.12 if bulan in (12, 1) else 1.0)   # mudik, hujan
    elif moda == "laut":
        musim = 1.30 if bulan in (12, 1, 2) else 1.0                               # cuaca buruk
    elif moda == "udara":
        musim = 1.10 if bulan in (3, 4, 12) else 1.0                               # kargo padat
    hari = (dasar["hari"] * musim + _TUNDA_PASANGAN.get((dari, ke, moda), 0.0)) \
        * acak.lognormvariate(0, 0.12)
    hari = max(0.3, hari)
    bbm = 1.0 + 0.10 * math.sin(2 * math.pi * tgl.timetuple().tm_yday / 365.0)
    biaya = dasar["biaya"] * bbm * acak.lognormvariate(0, 0.08)
    if jumlah > 200:
        biaya *= 0.92                                                  # tarif volume
    rugi = (1.0 - dasar["terima"]) * acak.lognormvariate(0, 0.5)
    if acak.random() < 0.025:                                          # insiden
        rugi += acak.uniform(0.08, 0.25)
    rusak = min(jumlah, int(round(jumlah * rugi)))
    return {"hari": hari, "biaya": biaya, "diterima": jumlah - rusak}


def _pilih_moda(acak: random.Random, tersedia: dict[str, float]) -> str:
    """Kebijakan operasional yang berderau: tiap moda tetap muncul di riwayat."""
    bobot = {"darat": 0.68, "laut": 0.20, "udara": 0.12} if "darat" in tersedia \
        else {"laut": 0.62, "udara": 0.38}
    moda = [m for m in bobot if m in tersedia]
    return acak.choices(moda, weights=[bobot[m] for m in moda])[0]


# --- penulisan dokumen --------------------------------------------------

def _tulis_penerimaan(cur, tgl, gid, sup, item_id, qty, harga, ref):
    stempel = datetime.combine(tgl, datetime.min.time())
    nomor = next_document_number(cur, table="stock_receipts", column="receipt_number",
                                 prefix="GR", tanggal=tgl, lock_namespace=LOCK_RECEIPT)
    cur.execute(
        "INSERT INTO stock_receipts (receipt_number, supplier_id, warehouse_id, receipt_date, "
        "reference_number, status, notes) VALUES (%s, %s, %s, %s, %s, 'completed', %s) RETURNING id",
        (nomor, sup, gid, stempel, ref, "Pengganti stok yang dikirim ke gudang lain"))
    rid = cur.fetchone()["id"]
    cur.execute("INSERT INTO stock_receipt_items (stock_receipt_id, item_id, quantity, unit_price, "
                "received_date) VALUES (%s, %s, %s, %s, %s)", (rid, item_id, qty, harga, tgl))
    cur.execute("INSERT INTO stock_movements (item_id, warehouse_id, movement_type, reference_id, "
                "movement_date, quantity, unit_price) VALUES (%s, %s, 'stock_in', %s, %s, %s, %s)",
                (item_id, gid, rid, stempel, qty, harga))


def _tulis_pengeluaran(cur, tgl, gid, item_id, qty, ref):
    stempel = datetime.combine(tgl, datetime.min.time())
    nomor = next_document_number(cur, table="stock_issues", column="issue_number",
                                 prefix="ISS", tanggal=tgl, lock_namespace=LOCK_ISSUE)
    cur.execute(
        "INSERT INTO stock_issues (issue_number, warehouse_id, issue_date, purpose, "
        "reference_number, status, notes) VALUES (%s, %s, %s, %s, %s, 'completed', %s) RETURNING id",
        (nomor, gid, stempel, "Pemakaian", ref, "Pemakaian kiriman dari gudang lain"))
    did = cur.fetchone()["id"]
    cur.execute("INSERT INTO stock_issue_items (stock_issue_id, item_id, quantity) "
                "VALUES (%s, %s, %s)", (did, item_id, qty))
    cur.execute("INSERT INTO stock_movements (item_id, warehouse_id, movement_type, reference_id, "
                "movement_date, quantity) VALUES (%s, %s, 'stock_out', %s, %s, %s)",
                (item_id, gid, did, stempel, -qty))


def riwayat_transfer(cur, jenis: str, ids: dict[str, int], acak: random.Random,
                     hari_ini: date, sku_barang: list[str]) -> dict:
    """Ratusan transfer selesai, dengan buku besar yang tetap utuh."""
    import numpy as np

    kunci_dari_id = {v: k for k, v in ids.items()}
    cur.execute("SELECT id, code, latitude, longitude FROM warehouses")
    gudang = {r["id"]: dict(r) for r in cur.fetchall()}
    cur.execute("SELECT from_warehouse_id a, to_warehouse_id b, distance_km FROM warehouse_distances")
    matriks = {(r["a"], r["b"]): float(r["distance_km"]) for r in cur.fetchall()}
    cur.execute("SELECT id FROM suppliers ORDER BY id")
    supplier = [r["id"] for r in cur.fetchall()]
    cur.execute("SELECT id, sku, unit_price FROM items WHERE sku = ANY(%s)", (sku_barang,))
    barang = {r["id"]: r for r in cur.fetchall()}

    mulai = hari_ini - timedelta(days=HARI_RIWAYAT)   # sama dengan awal riwayat barang
    akhir = hari_ini - timedelta(days=HARI_JEDA_ARSIP)
    n_hari = (hari_ini - mulai).days + 1

    # saldo akhir hari per pasangan, dari pergerakan yang sudah ada
    cur.execute(
        "SELECT item_id, warehouse_id, movement_date::date AS d, SUM(quantity) AS q "
        "FROM stock_movements WHERE item_id = ANY(%s) GROUP BY 1, 2, 3", (list(barang),))
    delta: dict[tuple[int, int], np.ndarray] = defaultdict(lambda: np.zeros(n_hari))
    for r in cur.fetchall():
        i = (r["d"] - mulai).days
        if 0 <= i < n_hari:
            delta[(r["item_id"], r["warehouse_id"])][i] += float(r["q"])
    saldo = {k: np.cumsum(v) for k, v in delta.items()}
    adj = {k: np.zeros(n_hari) for k in saldo}
    rata = {k: max(1.0, float(np.mean(v[v > 0])) if (v > 0).any() else 1.0) for k, v in saldo.items()}

    per_item: dict[int, list[int]] = defaultdict(list)
    for (iid, gid) in saldo:
        per_item[iid].append(gid)

    dibuat = tersimpan = batal = 0
    stat_moda: dict[str, int] = defaultdict(int)
    hari = mulai + timedelta(days=8)
    while hari <= akhir:
        i = (hari - mulai).days
        for _ in range(_poisson(acak, 0.85)):
            iid = acak.choice(list(per_item))
            gudang_item = [g for g in per_item[iid] if saldo[(iid, g)][i] > 0]
            if len(gudang_item) < 2:
                continue
            jendela = slice(i, min(n_hari, i + 10))

            def longgar(g):
                sd = saldo[(iid, g)][jendela] + adj[(iid, g)][jendela]
                return float(sd.min()), float(sd.min()) / rata[(iid, g)]

            urut = sorted(gudang_item, key=lambda g: longgar(g)[1])
            tujuan, sumber = urut[0], urut[-1]
            if tujuan == sumber:
                continue
            bebas = longgar(sumber)[0]
            if bebas < 12:
                continue
            qty = int(min(300, max(5, bebas * acak.uniform(0.12, 0.35))))
            k_asal, k_tuju = kunci_dari_id[sumber], kunci_dari_id[tujuan]
            tersedia = logistik.moda_tersedia(gudang[sumber], gudang[tujuan],
                                              matriks.get((sumber, tujuan)))
            moda = _pilih_moda(acak, tersedia)
            harga = float(barang[iid]["unit_price"])
            nyata = hasil_nyata(acak, moda, tersedia[moda], qty, qty * harga,
                                hari, k_asal, k_tuju)
            ka, kb = acak.randint(1, 3), acak.randint(1, 4)
            berangkat = datetime.combine(hari, datetime.min.time()) + timedelta(
                hours=acak.randint(7, 17), minutes=acak.randint(0, 59))
            tiba = berangkat + timedelta(days=nyata["hari"])
            j = (tiba.date() - mulai).days
            if j + kb + 1 >= n_hari or tiba.date() > akhir + timedelta(days=12):
                continue
            r_qty = nyata["diterima"]

            nomor = next_document_number(cur, table="stock_transfers", column="transfer_number",
                                         prefix="TRF", tanggal=hari, lock_namespace=LOCK_TRANSFER)
            dibatalkan = acak.random() < 0.03
            janji = logistik.janji_hari(moda, tersedia[moda])
            manual = acak.random() < 0.3
            alasan = (f"Ditutup dari {gudang[sumber]['code']}: surplus di atas titik pesan; "
                      f"moda {moda}, {tersedia[moda]:.0f} km.") if not manual else None
            cur.execute(
                """
                INSERT INTO stock_transfers
                    (transfer_number, from_warehouse_id, to_warehouse_id, transfer_date,
                     status, notes, source, score, reason, distance_km,
                     approved_at, shipped_at, received_at, cancelled_at,
                     transport_mode, shipping_cost, planned_days)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (nomor, sumber, tujuan, datetime.combine(hari, datetime.min.time()),
                 "cancelled" if dibatalkan else "completed",
                 "Arsip transfer", "manual" if manual else "transfer_engine",
                 None if manual else acak.randint(62, 96), alasan, tersedia[moda],
                 berangkat - timedelta(hours=acak.randint(2, 20)),
                 None if dibatalkan else berangkat,
                 None if dibatalkan else tiba,
                 berangkat if dibatalkan else None,
                 moda, None if dibatalkan else round(nyata["biaya"], 2), janji))
            tid = cur.fetchone()["id"]
            cur.execute(
                "INSERT INTO stock_transfer_items (stock_transfer_id, item_id, quantity, "
                "for_item_id, match_type, received_quantity) VALUES (%s, %s, %s, %s, 'sku', %s)",
                (tid, iid, qty, iid, None if dibatalkan else r_qty))
            if dibatalkan:
                batal += 1
                continue
            cur.execute("INSERT INTO stock_movements (item_id, warehouse_id, movement_type, "
                        "reference_id, movement_date, quantity) VALUES (%s, %s, 'transfer_out', %s, %s, %s)",
                        (iid, sumber, tid, berangkat, -qty))
            cur.execute("INSERT INTO stock_movements (item_id, warehouse_id, movement_type, "
                        "reference_id, movement_date, quantity) VALUES (%s, %s, 'transfer_in', %s, %s, %s)",
                        (iid, tujuan, tid, tiba, r_qty))
            # pengganti di asal, pemakaian di tujuan
            ref = f"{nomor}"
            _tulis_penerimaan(cur, hari + timedelta(days=ka), sumber, acak.choice(supplier),
                              iid, qty, harga, ref)
            if r_qty:
                _tulis_pengeluaran(cur, tiba.date() + timedelta(days=kb), tujuan, iid, r_qty, ref)
            adj[(iid, sumber)][i:i + ka] -= qty
            adj[(iid, tujuan)][j:j + kb] += r_qty
            dibuat += 1
            stat_moda[moda] += 1
        hari += timedelta(days=1)

    _periksa_buku_besar(cur, list(barang))
    return {"transfer_selesai": dibuat, "dibatalkan": batal, "menurut_moda": dict(stat_moda)}


def _periksa_buku_besar(cur, item_ids: list[int]) -> None:
    """Saldo tabel stok = jumlah pergerakan, dan tidak pernah minus di tengah jalan."""
    cur.execute(
        "SELECT item_id, warehouse_id, movement_date::date AS d, SUM(quantity) AS q "
        "FROM stock_movements WHERE item_id = ANY(%s) GROUP BY 1, 2, 3 ORDER BY 1, 2, 3",
        (item_ids,))
    lari: dict[tuple[int, int], float] = defaultdict(float)
    minus = 0
    for r in cur.fetchall():
        lari[(r["item_id"], r["warehouse_id"])] += float(r["q"])
        if lari[(r["item_id"], r["warehouse_id"])] < -1e-9:
            minus += 1
    cur.execute("SELECT item_id, warehouse_id FROM inventory WHERE item_id = ANY(%s)", (item_ids,))
    beda = [k for k in ((r["item_id"], r["warehouse_id"]) for r in cur.fetchall())
            if abs(lari[k] - float(_stok(cur, k))) > 1e-6]
    if minus or beda:
        raise SystemExit(f"Buku besar tidak utuh: {minus} saldo minus, {len(beda)} selisih "
                         f"terhadap inventory. Dibatalkan.")


def _stok(cur, k):
    cur.execute("SELECT quantity FROM inventory WHERE item_id = %s AND warehouse_id = %s", k)
    return cur.fetchone()["quantity"]


def _poisson(acak: random.Random, lam: float) -> int:
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= acak.random()
        if p <= limit:
            return k
        k += 1


# --- dokumen aktif untuk Semarang dan Makassar --------------------------
#
# Tanpa ini kedua cabang baru KOSONG pada peta dan daftar Dokumen: arsip
# setahun sudah selesai semua, dan dokumen skenario komponen hanya menyangkut
# Surabaya-Jakarta. Enam dokumen di bawah menyentuh Semarang dan Makassar pada
# tiap tahap dan tiap moda: kapal dan pesawat ke Makassar, truk di Jawa.
#
# (sku, asal, tujuan, jumlah, tahap akhir, moda, hari lalu berangkat,
#  catatan). "Hari lalu berangkat" = kapan dikirim; untuk yang selesai, tibanya
# menyusul menurut lama tempuh sesungguhnya. Barangnya sengaja yang stok
# sumbernya "aman" pada SEBAR, supaya angka skenario rekomendasi tidak bergeser.
DOKUMEN_CABANG = [
    ("EL-3001", "SBY", "MKS", 60, "in_transit", "laut", 4,
     "Kapal kargo Tanjung Perak - Makassar; jadwal mingguan, perkiraan tiba 4 hari lagi."),
    ("PD-4001", "JKT", "MKS", 40, "in_transit", "udara", 1,
     "Kargo udara: Makassar kehabisan sarung tangan; dikirim dengan penerbangan malam."),
    ("CP-6004", "SMG", "JKT", 30, "in_transit", "darat", 1,
     "Truk dari Semarang lewat tol Trans-Jawa."),
    ("PL-2003", "SBY", "SMG", 25, "approved", "darat", 0,
     "Surplus Surabaya mencukupi; stok dicadangkan menunggu jadwal truk."),
    ("PD-4001", "SMG", "MKS", 15, "approved", "udara", 0,
     "Kebutuhan mendesak Makassar; menunggu slot kargo udara."),
    ("PD-4002", "MKS", "SBY", 20, "draft", "laut", 0,
     "Makassar berlebih kacamata safety; diajukan ke Surabaya lewat kapal."),
    ("EL-3001", "MKS", "SMG", 30, "completed", "laut", 10,
     "Kapal kargo Makassar - Tanjung Emas; sudah diterima."),
]
_PENANDA_CABANG = "Skenario cabang"


def dokumen_cabang(cur, jenis: str, ids: dict[str, int], acak: random.Random,
                   hari_ini: date) -> int:
    """Enam-tujuh dokumen aktif untuk Semarang/Makassar; idempoten (dilewati bila sudah ada)."""
    from decimal import Decimal

    from app.routers.transfer import terapkan_status

    cur.execute("SELECT count(*) AS n FROM stock_transfers WHERE notes = %s", (_PENANDA_CABANG,))
    if cur.fetchone()["n"]:
        return 0
    cur.execute("SELECT id, code, name, latitude, longitude FROM warehouses")
    gudang = {r["id"]: dict(r) for r in cur.fetchall()}
    cur.execute("SELECT from_warehouse_id a, to_warehouse_id b, distance_km FROM warehouse_distances")
    matriks = {(r["a"], r["b"]): float(r["distance_km"]) for r in cur.fetchall()}
    cur.execute("SELECT id, sku, unit_price FROM items WHERE sku = ANY(%s)", (list(SEBAR),))
    barang = {r["sku"]: r for r in cur.fetchall()}
    kunci_id = {v: k for k, v in ids.items()}
    rantai = ("draft", "approved", "in_transit", "completed")
    n = 0
    for sku, asal, tujuan, qty, akhir, moda, lalu, cat in DOKUMEN_CABANG:
        gid_a, gid_t = ids[asal], ids[tujuan]
        b = barang[sku]
        tersedia = logistik.moda_tersedia(gudang[gid_a], gudang[gid_t], matriks.get((gid_a, gid_t)))
        jarak = tersedia[moda]
        nyata = hasil_nyata(acak, moda, jarak, qty, qty * float(b["unit_price"]),
                            hari_ini - timedelta(days=lalu), asal, tujuan)
        berangkat = datetime.combine(hari_ini - timedelta(days=lalu), datetime.min.time()) \
            + timedelta(hours=acak.randint(8, 16))
        tiba = berangkat + timedelta(days=nyata["hari"])
        diajukan = berangkat - timedelta(days=1 if akhir != "draft" else 0)
        tgl = diajukan.date()
        nomor = next_document_number(cur, table="stock_transfers", column="transfer_number",
                                     prefix="TRF", tanggal=tgl, lock_namespace=LOCK_TRANSFER)
        cur.execute(
            """
            INSERT INTO stock_transfers
                (transfer_number, from_warehouse_id, to_warehouse_id, transfer_date, status,
                 notes, source, score, reason, distance_km, transport_mode, planned_days)
            VALUES (%s, %s, %s, %s, 'draft', %s, 'transfer_engine', %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (nomor, gid_a, gid_t, datetime.combine(tgl, datetime.min.time()), _PENANDA_CABANG,
             acak.randint(70, 92), cat, jarak, moda, logistik.janji_hari(moda, jarak)))
        tid = cur.fetchone()["id"]
        cur.execute(
            "INSERT INTO stock_transfer_items (stock_transfer_id, item_id, quantity, for_item_id, "
            "match_type) VALUES (%s, %s, %s, %s, 'sku')", (tid, b["id"], qty, b["id"]))
        header = {"from_warehouse_id": gid_a, "to_warehouse_id": gid_t,
                  "from_warehouse_name": gudang[gid_a]["name"]}
        baris = [{"item_id": b["id"], "quantity": Decimal(qty), "sku": sku}]
        waktu = {"approved": diajukan + timedelta(hours=6), "in_transit": berangkat, "completed": tiba}
        dari = "draft"
        for ke in rantai[1:rantai.index(akhir) + 1]:
            terapkan_status(cur, transfer_id=tid, dari=dari, ke=ke, header=header,
                            baris=baris, stempel=waktu[ke])
            dari = ke
        if akhir == "completed":
            cur.execute("UPDATE stock_transfers SET shipping_cost = %s WHERE id = %s",
                        (round(nyata["biaya"], 2), tid))
            cur.execute("UPDATE stock_transfer_items SET received_quantity = quantity "
                        "WHERE stock_transfer_id = %s", (tid,))
        n += 1
    _periksa_buku_besar(cur, [r["id"] for r in barang.values()])
    return n


def lengkapi_dokumen_lama(cur, ids: dict[str, int]) -> int:
    """Moda, biaya, dan janji hari untuk dokumen yang belum punya (skenario komponen)."""
    cur.execute("SELECT id, code, latitude, longitude FROM warehouses")
    gudang = {r["id"]: dict(r) for r in cur.fetchall()}
    cur.execute("SELECT from_warehouse_id a, to_warehouse_id b, distance_km FROM warehouse_distances")
    matriks = {(r["a"], r["b"]): float(r["distance_km"]) for r in cur.fetchall()}
    cur.execute(
        """
        SELECT t.id, t.from_warehouse_id a, t.to_warehouse_id b, t.status,
               SUM(ti.quantity) q, SUM(ti.quantity * it.unit_price) nilai
          FROM stock_transfers t
          JOIN stock_transfer_items ti ON ti.stock_transfer_id = t.id
          JOIN items it ON it.id = ti.item_id
         WHERE t.transport_mode IS NULL
         GROUP BY t.id
        """)
    n = 0
    for r in cur.fetchall():
        tersedia = logistik.moda_tersedia(gudang[r["a"]], gudang[r["b"]], matriks.get((r["a"], r["b"])))
        moda = "darat" if "darat" in tersedia else "laut"
        biaya = logistik.tarif_standar(moda, tersedia[moda], float(r["q"]), float(r["nilai"] or 0))["biaya"]
        cur.execute("UPDATE stock_transfers SET transport_mode = %s, planned_days = %s, "
                    "shipping_cost = %s WHERE id = %s",
                    (moda, logistik.janji_hari(moda, tersedia[moda]),
                     round(biaya, 2) if r["status"] == "completed" else None, r["id"]))
        if r["status"] == "completed":
            cur.execute("UPDATE stock_transfer_items SET received_quantity = quantity "
                        "WHERE stock_transfer_id = %s AND received_quantity IS NULL", (r["id"],))
        n += 1
    return n


# --- orkestrasi ---------------------------------------------------------

def bangun_jaringan(cur, jenis: str, hari_ini: date | None = None) -> dict:
    """Seluruh langkah untuk satu perusahaan, di dalam satu transaksi."""
    from tools import histori_umur_pakai as umur

    hari_ini = hari_ini or date.today()
    peta = PETA[jenis]
    acak = random.Random(BENIH)

    ids = tambah_cabang(cur, jenis)
    baris = rencana_barang(peta, hari_ini)

    # Bangun ulang barang habis pakai: hapus versi lama menurut SKU.
    cur.execute("SELECT id FROM items WHERE sku = ANY(%s)", (list(SEBAR),))
    umur._hapus_barang(cur, [r["id"] for r in cur.fetchall()])
    siapkan_barang(cur, baris)
    hasil = umur.bangun(cur, acak, 0, list(peta.values()), semua_baris=True,
                        hapus=False, jarak=False, dokumen=False, baris=baris)
    riwayat = riwayat_transfer(cur, jenis, ids, acak, hari_ini, list(SEBAR))
    n_cabang = dokumen_cabang(cur, jenis, ids, acak, hari_ini)
    dilengkapi = lengkapi_dokumen_lama(cur, ids)
    return {"gudang": len(ids), "barang_habis_pakai": len(SEBAR),
            "baris_stok_baru": hasil["baris_stok"], **riwayat,
            "dokumen_cabang": n_cabang, "dokumen_lama_dilengkapi": dilengkapi}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--perusahaan", choices=sorted(PERUSAHAAN), required=True)
    ap.add_argument("--terapkan", action="store_true")
    ap.add_argument("--hanya-dokumen", action="store_true",
                    help="hanya menambah dokumen aktif Semarang/Makassar pada data yang sudah "
                         "dibangun (idempoten); tidak menghapus apa pun")
    a = ap.parse_args()
    cid, nama = PERUSAHAAN[a.perusahaan]
    peta = PETA[a.perusahaan]
    print(f"Perusahaan     : {nama}")
    print(f"Gudang         : {', '.join(f'{k}={v}' for k, v in peta.items())}")
    print(f"Barang         : {len(SEBAR)} habis pakai x {sum(len(v) for v in SEBAR.values())} penempatan")
    print(f"Riwayat        : {HARI_RIWAYAT} hari, transfer berhenti {HARI_JEDA_ARSIP} hari sebelum hari ini")
    if not a.terapkan:
        print("\n(rencana saja -- tambahkan --terapkan untuk menulis)")
        return
    try:
        with tenant.jalankan_sebagai(cid, nama):
            with transaction() as cur:
                if a.perusahaan == "demo":
                    cur.execute("SELECT is_demo FROM companies")
                    b = cur.fetchone()
                    if b is None or not b["is_demo"]:
                        raise SystemExit("Bukan penyewa demo; dihentikan.")
                if a.hanya_dokumen:
                    cur.execute("SELECT id, code FROM warehouses")
                    kode = {r["code"]: r["id"] for r in cur.fetchall()}
                    ids = {k: kode[v] for k, v in peta.items()}
                    n = dokumen_cabang(cur, a.perusahaan, ids, random.Random(BENIH + 7), date.today())
                    print(f"\n== selesai == dokumen_cabang: {n}")
                    return
                hasil = bangun_jaringan(cur, a.perusahaan)
    finally:
        close_pool()
    print("\n== selesai ==")
    for k, v in hasil.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
