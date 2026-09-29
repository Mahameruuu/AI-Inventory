# -*- coding: utf-8 -*-
"""
Membangun ulang riwayat Perusahaan Utama dari LAMA PEMAKAIAN tiap komponen.

    cd backend && ../.venv/bin/python -m tools.histori_umur_pakai [--terapkan]

Tanpa --terapkan skrip hanya menghitung dan menampilkan hasilnya; basis data
tidak disentuh sama sekali. Itu bawaan yang disengaja: perintah ini menghapus
seluruh transaksi satu perusahaan, dan kesalahan mengetik nama modul tidak boleh
berakhir dengan data yang hilang.

APA YANG DIKERJAKAN. Dua puluh komponen pada TABEL di bawah mendapat kolom
lama pemakaian sesuai daftar yang diberikan pengguna, lalu SELURUH transaksi
perusahaan dihapus dan riwayat tiga tahun dibangkitkan ulang -- kali ini
diturunkan dari lama pemakaian itu, bukan dari angka acak. Komponen yang
bertahan 1.250 jam keluar jauh lebih sering daripada yang bertahan 40.000 jam,
dan perbandingan itulah yang membuat halaman prakiraan masuk akal bila
seseorang membandingkannya dengan kolom lama pemakaian di layar.

DUA ASUMSI YANG TIDAK DIMILIKI BASIS DATA, dan karena itu ditulis di sini
sebagai konstanta, bukan disembunyikan di tengah kode:

  JAM_OPERASI_PER_HARI  Migrasi 029 sengaja menyimpan satuan apa adanya --
                        sebagian komponen dinyatakan dalam jam operasi,
                        sebagian dalam tahun kalender -- justru karena
                        mengubah yang satu menjadi yang lain menuntut angka
                        ini, dan selisih antara satu shift dan operasi
                        terus-menerus lebih dari empat kali lipat. Pengguna
                        memilih dua shift pada 1 September 2026.

  ARMADA                Berapa titik pemasangan tiap jenis komponen. Lama
                        pemakaian sendiri hanya menentukan PERBANDINGAN
                        frekuensi antar komponen; yang menentukan seberapa
                        ramai pengeluaran adalah berapa unit terpasang.
                        Tanpa angka ini, satu pompa berumur 20 tahun akan
                        keluar nol kali dalam riwayat tiga tahun.

Dijalankan sebagai role aplikasi (DATABASE_URL), bukan admin: seluruh
perintahnya menyentuh satu perusahaan saja, dan yang menjaganya adalah RLS --
bukan kehati-hatian penulis skrip ini. Sebuah percobaan sebelumnya yang
dijalankan sebagai inventory_admin diam-diam ikut menghapus data penyewa lain,
karena superuser dibebaskan dari seluruh kebijakan RLS.
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import tenant                                    # noqa: E402
from app.common import LOCK_ISSUE, LOCK_RECEIPT, next_document_number  # noqa: E402
from app.config import OPERATING_HOURS_PER_DAY            # noqa: E402
from app.db import close_pool, transaction                # noqa: E402

PERUSAHAAN = 1
BENIH = 20260901
# Dua puluh tahun, dipilih pengguna 1 September 2026 supaya seluruh komponen
# diukur pada jendela yang sama -- termasuk pompa sentrifugal yang umur pakainya
# memang dua puluh tahun. Jendela tiga tahun yang dipakai data sebelumnya
# membuat empat belas dari dua puluh komponen tidak bergerak sama sekali.
#
# Dua puluh tahun pun belum cukup untuk membuat semuanya terprakirakan: pompa
# 20 tahun dan bearing 40.000 jam masih bergerak kurang dari tiga kali. Itu
# bukan kekurangan skrip ini melainkan sifat komponennya, dan skrip menyebut
# barang mana saja setiap kali dijalankan.
TAHUN_RIWAYAT = 20

# Dua shift kerja. Lihat catatan pada docstring.
#
# DIIMPOR, tidak ditulis ulang di sini. Halaman Analisis Umur Pakai memakai
# angka yang sama untuk MEMBACA riwayat yang dibangun berkas ini; dua salinan
# yang berselisih membuat setiap komponen bersatuan jam terlihat menyimpang
# dari umur pakainya tanpa satu pun galat yang menunjuk sebabnya.
JAM_OPERASI_PER_HARI = OPERATING_HOURS_PER_DAY

# Satu unit terpasang per komponen, dan pemakaiannya persis seperti yang
# tertulis pada daftar: dipakai selama umur pakainya, lalu diganti. Bukan
# armada berisi puluhan titik pemasangan -- rancangan pertama skrip ini memakai
# 20-60 unit per komponen supaya setiap barang punya riwayat yang ramai, dan
# pengguna menolaknya pada 1 September 2026: yang diminta adalah pemakaian yang
# sepadan dengan daftar, bukan yang enak dilihat di halaman prakiraan.
#
# AKIBATNYA HARUS DISADARI. Dengan satu unit, komponen berumur 40.000 jam
# diganti sekali tiap 2.500 hari dan pompa berumur 20 tahun sekali tiap 7.300
# hari. Pada jendela riwayat tiga tahun, sebagian besar komponen hanya bergerak
# sekali atau tidak sama sekali -- dan barang yang tidak bergerak tidak dapat
# diprakirakan. Panjang riwayat dapat diperpanjang lewat --tahun bila yang
# diinginkan adalah melihat beberapa daur penggantian penuh.
UNIT_TERPASANG = 1

# Besar satu pesanan. Untuk komponen yang diganti sekali dalam beberapa tahun,
# yang wajar disimpan adalah satu unit cadangan di rak, bukan stok beberapa
# bulan kebutuhan.
PESANAN_HARI = 120
PESANAN_MINIMAL = 1

# (nomor, nama komponen, lama pemakaian, satuan, kode gudang)
#
# Nomor 1-10 dipakai gudang Surabaya, 11-20 gudang Jakarta -- pembagian yang
# sudah berlaku di basis data dan ditegaskan kembali oleh pengguna. Skrip ini
# MEMERIKSA pembagian itu, bukan memindahkan barang: bila satu baris tidak
# cocok dengan isi basis data, seluruh perintah dibatalkan sebelum ada yang
# terhapus.
TABEL = [
    ( 1, "Gear Pump ABB 29805",              12_000, "jam",   "WH-CEN-01"),
    ( 2, "Roller Bearing ABB 70416",         40_000, "jam",   "WH-CEN-01"),
    ( 3, "Oli Hidrolik Kobelco 11972",        3_000, "jam",   "WH-CEN-01"),
    ( 4, "Centrifugal Pump Festo 31859",         20, "tahun", "WH-CEN-01"),
    ( 5, "Ball Bearing Pertamina 81413",     35_000, "jam",   "WH-CEN-01"),
    ( 6, "Oli Hidrolik Shell 36011",          3_000, "jam",   "WH-CEN-01"),
    ( 7, "Centrifugal Pump Yokogawa 8703",       20, "tahun", "WH-CEN-01"),
    ( 8, "Roller Bearing Pertamina 53651",   40_000, "jam",   "WH-CEN-01"),
    ( 9, "Oli Hidrolik Parker 65767",         3_000, "jam",   "WH-CEN-01"),
    (10, "Gear Pump Donaldson 24745",        12_000, "jam",   "WH-CEN-01"),

    (11, "Gear Pump Parker 45907",           12_000, "jam",   "WH-CEN-02"),
    (12, "Roller Bearing Siemens 23915",     40_000, "jam",   "WH-CEN-02"),
    (13, "Filter Oli Timken 58773",           1_250, "jam",   "WH-CEN-02"),
    (14, "Centrifugal Pump Donaldson 77607",     20, "tahun", "WH-CEN-02"),
    (15, "Roller Bearing Timken 19505",      40_000, "jam",   "WH-CEN-02"),
    (16, "Filter Oli ABB 37613",              1_250, "jam",   "WH-CEN-02"),
    (17, "Gear Pump Grundfos 68749",         12_000, "jam",   "WH-CEN-02"),
    (18, "Ball Bearing Schneider 2377",      35_000, "jam",   "WH-CEN-02"),
    (19, "Oli Hidrolik Schneider 25705",      3_000, "jam",   "WH-CEN-02"),
    (20, "Gear Pump Bosch 93252",            12_000, "jam",   "WH-CEN-02"),
]

# ==========================================================================
# Komponen yang terpasang di DUA pabrik
# ==========================================================================
#
# KENAPA ADA. Sampai 3 September 2026 tiap komponen hanya terpasang di satu
# gudang, dan akibatnya halaman Transfer Antar Gudang menjawab "beli baru" pada
# setiap barisnya: modul itu mencari gudang lain yang SUDAH menyimpan barangnya,
# dan gudang seperti itu tidak pernah ada. Pengguna meminta sebarannya diadakan
# pada hari yang sama, sesudah hal yang sama dikerjakan pada penyewa demo.
#
# INI BUKAN "ARMADA" YANG DITOLAK 1 SEPTEMBER 2026. Yang ditolak waktu itu
# adalah 20-60 titik pemasangan per komponen supaya riwayatnya terlihat ramai.
# Yang ada di sini adalah satu unit terpasang di Surabaya dan satu lagi di
# Jakarta untuk komponen yang memang dipakai kedua pabrik -- lima dari dua
# puluh, dan tetap satu unit per pabrik. Frekuensi penggantiannya tidak berubah
# sama sekali; yang bertambah hanya tempatnya.
#
# CADANGAN AKHIRNYA DITETAPKAN DI SINI, dan itu yang membuat halaman Transfer
# punya sesuatu untuk dijawab. Angkanya jumlah unit cadangan di rak pada hari
# terakhir riwayat, dan dapat diperiksa terhadap titik pesan tiap komponen
# (laju x waktu tunggu + 1, jadi selalu di antara 1,0 dan 1,3 unit):
#
#   0 cadangan  -> di bawah titik pesan; kebutuhannya 2 unit
#   1 cadangan  -> masih di bawah titik pesan: gudang ini TIDAK boleh menjadi
#                  sumber, dan halaman menyebutkan alasannya
#   2 cadangan  -> surplus 1 unit: menutup sebagian kebutuhan
#   3-4 cadangan -> surplus 2 unit: menutup seluruhnya
#
# SURPLUSNYA DIHITUNG DARI ANGKA BULAT, dan pada skala satu-dua unit itu
# menentukan hasilnya. app/transfer.surplus_gudang() menerima stok tersedia dan
# titik pesan efektif yang SUDAH dibulatkan (available_stock_int,
# effective_reorder_point_int), sehingga titik pesan 1,128 masuk sebagai 1 dan
# tiga cadangan berarti surplus 2 -- bukan 1. Karena itu skenario "transfer
# sebagian" memakai dua cadangan, bukan tiga; percobaan pertama dengan tiga
# menghasilkan transfer penuh.
#
# Skenario "tetap pembelian" (sumber ikut di bawah titik pesan, 1 cadangan) DIHAPUS
# 28 September 2026 atas permintaan pengguna: contoh pada penyewa ini cukup satu
# rute per arah. Aturannya tetap terkunci oleh tes mesin (test_transfer.py) dan
# tetap tampil pada penyewa demo (PD-4005).
#
# (nomor komponen, {kode gudang: cadangan tersisa}, apa yang hendak ditunjukkan)
PEMASANGAN = [
    (16, {"WH-CEN-02": 4, "WH-CEN-01": 0},
     "transfer penuh Jakarta -> Surabaya"),
    (13, {"WH-CEN-02": 2, "WH-CEN-01": 0},
     "transfer sebagian: surplus Jakarta 1 unit, kebutuhan Surabaya 2"),
    ( 6, {"WH-CEN-01": 4, "WH-CEN-02": 0},
     "transfer penuh arah sebaliknya: Surabaya -> Jakarta"),
    (11, {"WH-CEN-02": 4, "WH-CEN-01": 3},
     "dua gudang aman; dipakai dokumen yang sedang dalam perjalanan"),
    ( 1, {"WH-CEN-01": 4, "WH-CEN-02": 2},
     "dua gudang aman; dipakai dokumen yang sudah diterima dan yang disetujui"),
]

# Jarak jalan darat Surabaya <-> Jakarta, bukan garis lurus. Haversine antara
# kedua koordinat 665 km; yang ditempuh truk lewat tol Trans-Jawa hampir 800 km,
# dan arah baliknya tidak persis sama.
#
# (kode gudang asal, kode gudang tujuan, km, hari, catatan)
JARAK_GUDANG = [
    ("WH-CEN-01", "WH-CEN-02", 780.0, 2, "Tol Trans-Jawa, langsung"),
    ("WH-CEN-02", "WH-CEN-01", 795.0, 3, "Tol Trans-Jawa, muat balik lewat Semarang"),
]

# --- dokumen transfer yang sudah berjalan ---------------------------------
#
# Rekomendasi menjawab "apa yang sebaiknya dipindahkan"; ia tidak pernah
# menunjukkan barang yang MEMANG sedang berpindah. Tanpa dokumen, tab Dokumen
# kosong dan keempat tahap yang membedakan modul ini -- diajukan, disetujui,
# dikirim, diterima -- tidak terlihat satu pun.
#
# BARANGNYA SENGAJA KOMPONEN YANG KEDUA GUDANGNYA AMAN, kecuali yang terakhir:
# dokumen yang disetujui mencadangkan stok gudang asal dan yang dikirim
# benar-benar menguranginya, sehingga menaruhnya pada komponen skenario akan
# membuat angka yang dijelaskan di atas tidak lagi cocok dengan layar. Yang
# berstatus "diajukan" tidak menyentuh stok sama sekali, jadi ia justru
# seharusnya berdiri di atas rekomendasi hari ini.
#
# (nomor komponen, gudang asal, gudang tujuan, unit, status akhir, hari lalu,
#  skor, alasan yang dibekukan)
DOKUMEN_TRANSFER = [
    ( 1, "WH-CEN-01", "WH-CEN-02", 1, "completed", 8, 81,
     "Surabaya menyimpan 4 cadangan, Jakarta 2; satu unit dipindahkan sebelum "
     "penggantian terjadwal."),
    (11, "WH-CEN-02", "WH-CEN-01", 1, "in_transit", 3, 76,
     "Jakarta surplus 3 unit; jarak 795 km, waktu tempuh 3 hari."),
    ( 1, "WH-CEN-01", "WH-CEN-02", 1, "approved", 1, 79,
     "Cadangan Surabaya mencukupi; stok dicadangkan menunggu jadwal kirim."),
    (16, "WH-CEN-02", "WH-CEN-01", 2, "draft", 0, 90,
     "Surabaya kehabisan cadangan Filter Oli; Jakarta berlebih 2 unit dan "
     "menutup seluruh kebutuhannya tanpa pembelian."),
]

# Urutan tahap yang dilewati sebuah dokumen; sama dengan app/transfer.PERPINDAHAN
# dibaca dari draft ke completed.
RANTAI_STATUS = ("draft", "approved", "in_transit", "completed")


# Transaksi yang dihapus, menurut arah kunci asing. Master data -- barang,
# gudang, kategori, satuan, pemasok, pengguna -- sengaja TIDAK ikut: yang
# diminta adalah riwayatnya yang dibangun ulang, bukan perusahaannya yang
# dibuat ulang dari nol.
URUTAN_HAPUS = [
    "serial_numbers", "stock_batches", "stock_movements",
    "inventory", "purchase_order_items", "purchase_orders",
    "stock_receipt_items", "stock_receipts", "stock_issue_items",
    "stock_issues", "stock_transfer_items", "stock_transfers",
    "stock_adjustment_items", "stock_adjustments",
    # Bukan transaksi, tetapi ikut dibangkitkan skrip ini dan barisnya unik per
    # pasangan gudang: tanpa dihapus lebih dulu, menjalankan ulang perintah ini
    # berhenti pada galat kunci ganda setelah separuh pekerjaan selesai.
    "warehouse_distances",
]


JENIS = ("Filter Oli", "Oli Hidrolik", "Gear Pump", "Ball Bearing",
         "Roller Bearing", "Centrifugal Pump")


def jenis_dari(nama: str) -> str:
    """Jenis komponen, dibaca dari awal namanya. Hanya untuk pelaporan."""
    for j in JENIS:
        if nama.startswith(j):
            return j
    raise SystemExit(f"Jenis komponen tidak dikenali: {nama!r}")


def umur_hari(nilai: float, satuan: str) -> float:
    """
    Lama pemakaian dalam hari kalender.

    'tahun' TIDAK ikut dikalikan jam operasi: dua puluh tahun pada spesifikasi
    pompa berarti dua puluh tahun kalender, bukan dua puluh tahun jam jalan.
    Menyamakan keduanya adalah kesalahan yang paling mudah terjadi di sini dan
    paling sulit terlihat pada hasilnya.
    """
    if satuan == "jam":
        return nilai / JAM_OPERASI_PER_HARI
    if satuan == "tahun":
        return nilai * 365.0
    raise SystemExit(f"Satuan tidak dikenali: {satuan!r}")


def rencana() -> list[dict]:
    """
    Menghitung laju pemakaian tiap TITIK PEMASANGAN, tanpa menyentuh basis data.

    Satu baris per (komponen, gudang), bukan per komponen: lima komponen pada
    PEMASANGAN berdiri di dua pabrik sekaligus, dan tiap unit terpasang punya
    daur penggantiannya sendiri. Yang berlipat hanya tempatnya -- lajunya tetap
    satu unit per umur pakai, persis seperti sebelumnya.
    """
    sebaran = {nomor: isi for nomor, isi, _ in PEMASANGAN}
    hasil = []
    for nomor, nama, nilai, satuan, kode in TABEL:
        j = jenis_dari(nama)
        hari = umur_hari(nilai, satuan)
        armada = UNIT_TERPASANG
        laju = armada / hari                      # unit per hari

        isi = sebaran.get(nomor)
        if isi is not None and kode not in isi:
            raise SystemExit(
                f"PEMASANGAN komponen {nomor} tidak menyebut gudang asalnya "
                f"({kode}); barangnya akan pindah rumah diam-diam.")
        titik = sorted(isi) if isi else [kode]

        for k in titik:
            hasil.append({
                "nomor": nomor, "nama": nama, "jenis": j,
                "umur_nilai": nilai, "umur_satuan": satuan, "umur_hari": hari,
                "armada": armada, "laju": laju, "kode_gudang": k,
                # Cadangan yang harus tersisa di rak pada hari terakhir; None
                # berarti "seadanya menurut siklus pemesanan".
                "sasaran": (isi[k] if isi else None),
                "rumah": k == kode,
            })
    return hasil


def _pengeluaran(acak: random.Random, r: dict, mulai: date, akhir: date
                 ) -> dict[date, int]:
    """
    Kapan saja komponen ini diganti, satu unit terpasang pada satu waktu.

    BUKAN sekadar angka acak sebesar laju rata-rata. Tiap unit terpasang
    membawa sisa umurnya sendiri, dan sisa itu disebar merata pada hari
    pertama: armada sungguhan tidak dipasang serentak, sehingga penggantiannya
    juga tidak menumpuk di satu hari lalu senyap berbulan-bulan. Umur
    penggantinya diberi ragam +-15% supaya polanya tidak menjadi denyut yang
    berulang persis -- yang justru akan membuat prakiraan tampak terlalu pandai.
    """
    if r.get("harian"):
        # Barang habis pakai: permintaan harian menurut pola pembangkit demo,
        # bukan penggantian satu unit per umur pakai.
        from app import demo
        harian: dict[date, int] = {}
        d = mulai
        while d <= akhir:
            n = demo._permintaan(acak, r["laju"], d)
            if n:
                harian[d] = n
            d += timedelta(days=1)
        return harian
    sisa = [acak.random() * r["umur_hari"] for _ in range(r["armada"])]
    keluar: dict[date, int] = defaultdict(int)
    hari = mulai
    while hari <= akhir:
        for i, s in enumerate(sisa):
            s -= 1.0
            if s <= 0:
                keluar[hari] += 1
                s = r["umur_hari"] * acak.uniform(0.85, 1.15)
            sisa[i] = s
        hari += timedelta(days=1)
    return dict(keluar)


def _hapus_lingkup(cur, ids: list[int]) -> dict[str, int]:
    """
    Menghapus transaksi HANYA milik gudang `ids`, gudang lain tidak disentuh.

    Dokumen transfer yang menyentuh gudang itu ikut dihapus berikut jejak
    ledgernya di gudang lawan; saldo gudang lawan lalu dihitung ulang dari
    pergerakan yang tersisa, sebab transfer-lah yang tadinya menggeser saldo itu
    (dan dokumennya dibangun ulang sesudahnya). Cadangan (reserved) pada baris
    yang tersentuh dikembalikan ke nol: hanya dokumen yang dihapus yang
    mencadangkannya.
    """
    terhapus: dict[str, int] = {}

    def hapus(nama: str, sql: str, *param) -> None:
        cur.execute(sql, param)
        if cur.rowcount:
            terhapus[nama] = terhapus.get(nama, 0) + cur.rowcount

    trf = ("SELECT id FROM stock_transfers WHERE from_warehouse_id = ANY(%s) "
           "OR to_warehouse_id = ANY(%s)")
    cur.execute(
        f"""
        SELECT DISTINCT item_id, warehouse_id FROM stock_movements
         WHERE movement_type IN ('transfer_in', 'transfer_out')
           AND reference_id IN ({trf})
        """, (ids, ids))
    lawan = [(b["item_id"], b["warehouse_id"]) for b in cur.fetchall()
             if b["warehouse_id"] not in ids]

    hapus("serial_numbers", "DELETE FROM serial_numbers WHERE warehouse_id = ANY(%s)", ids)
    hapus("stock_movements(transfer)",
          f"DELETE FROM stock_movements WHERE movement_type IN "
          f"('transfer_in', 'transfer_out') AND reference_id IN ({trf})", ids, ids)
    hapus("stock_movements", "DELETE FROM stock_movements WHERE warehouse_id = ANY(%s)", ids)
    hapus("inventory", "DELETE FROM inventory WHERE warehouse_id = ANY(%s)", ids)
    hapus("purchase_order_items",
          "DELETE FROM purchase_order_items WHERE purchase_order_id IN "
          "(SELECT id FROM purchase_orders WHERE warehouse_id = ANY(%s))", ids)
    hapus("purchase_orders", "DELETE FROM purchase_orders WHERE warehouse_id = ANY(%s)", ids)
    hapus("stock_receipt_items",
          "DELETE FROM stock_receipt_items WHERE stock_receipt_id IN "
          "(SELECT id FROM stock_receipts WHERE warehouse_id = ANY(%s))", ids)
    hapus("stock_receipts", "DELETE FROM stock_receipts WHERE warehouse_id = ANY(%s)", ids)
    hapus("stock_issue_items",
          "DELETE FROM stock_issue_items WHERE stock_issue_id IN "
          "(SELECT id FROM stock_issues WHERE warehouse_id = ANY(%s))", ids)
    hapus("stock_issues", "DELETE FROM stock_issues WHERE warehouse_id = ANY(%s)", ids)
    hapus("stock_transfer_items",
          f"DELETE FROM stock_transfer_items WHERE stock_transfer_id IN ({trf})", ids, ids)
    hapus("stock_transfers",
          "DELETE FROM stock_transfers WHERE from_warehouse_id = ANY(%s) "
          "OR to_warehouse_id = ANY(%s)", ids, ids)
    hapus("stock_adjustment_items",
          "DELETE FROM stock_adjustment_items WHERE stock_adjustment_id IN "
          "(SELECT id FROM stock_adjustments WHERE warehouse_id = ANY(%s))", ids)
    hapus("stock_adjustments", "DELETE FROM stock_adjustments WHERE warehouse_id = ANY(%s)", ids)
    hapus("warehouse_distances",
          "DELETE FROM warehouse_distances WHERE from_warehouse_id = ANY(%s) "
          "OR to_warehouse_id = ANY(%s)", ids, ids)

    for item_id, gid in lawan:
        cur.execute(
            """
            UPDATE inventory
               SET quantity = s.q, reserved_quantity = 0, available_quantity = s.q,
                   updated_at = now()
              FROM (SELECT COALESCE(SUM(quantity), 0) AS q FROM stock_movements
                     WHERE item_id = %s AND warehouse_id = %s) s
             WHERE item_id = %s AND warehouse_id = %s
            """, (item_id, gid, item_id, gid))
    return terhapus


def _simulasi_terjadwal(acak: random.Random, r: dict, permintaan: dict,
                        mulai: date, akhir: date, masuk: dict, keluar: dict,
                        supplier: list[int]) -> None:
    """
    Satu pasangan barang habis pakai yang dipasok menurut JADWAL, bukan menurut
    pemesanan otomatis. Sama dengan pasangan SEBARAN pada app/demo.py:
    kiriman tiap 21 hari, yang terakhir 14 hari sebelum hari ini, masing-masing
    setinggi lantai + perkiraan pemakaian sampai kiriman berikutnya. Saldo hari
    terakhir karenanya mendarat di `lantai` x titik pesan, hari apa pun skrip
    dijalankan -- yang dituntut skenario transfer. Seluruh koreksinya berupa
    penerimaan; pengeluaran tidak pernah ditambah, supaya laju pemakaian tidak
    ikut terdorong.
    """
    from app import demo
    gid = r["warehouse_id"]
    rencana_kirim = demo._jadwal_sebaran(mulai, akhir, r["laju"],
                                         r["lantai"] * r["titik_pesan"])
    awal = max(1, int(rencana_kirim.pop(mulai)))
    saldo = awal
    masuk[(mulai, gid, acak.choice(supplier))].append((r["item_id"], awal))
    hari = mulai + timedelta(days=1)
    while hari <= akhir:
        tinggi = rencana_kirim.get(hari)
        if tinggi is not None:
            tambah = int(tinggi - saldo + 0.999)
            if tambah > 0:
                saldo += tambah
                masuk[(hari, gid, acak.choice(supplier))].append(
                    (r["item_id"], tambah))
        dilayani = min(permintaan.get(hari, 0), int(saldo))
        if dilayani > 0:
            saldo -= dilayani
            keluar[(hari, gid)].append((r["item_id"], dilayani))
        hari += timedelta(days=1)


def bangun(cur, acak: random.Random, tahun: int,
           lingkup: list[str] | None = None, semua_baris: bool = False,
           hapus: bool = True, jarak: bool = True, dokumen: bool = True,
           baris: list[dict] | None = None) -> dict:
    """
    Menghapus transaksi lama lalu menuliskan riwayat yang baru.

    `lingkup` (kode gudang) membatasi PENGHAPUSAN pada gudang itu; kosong berarti
    seluruh perusahaan seperti sediakala. `semua_baris` membuat baris rencana di
    gudang lain (mis. penempatan kedua barang baru) ikut dibangun, bukan hanya
    yang berada di gudang lingkup -- dipakai penyewa demo, yang barang barunya
    belum punya riwayat di gudang mana pun. `hapus=False` melewatkan penghapusan
    (data lain di gudang itu harus tetap ada) dan `jarak=False` melewatkan
    penerbitan jarak antar gudang yang sudah ada -- keduanya dipakai penyewa
    demo, yang berisi juga barang harian. `dokumen=False` tidak menerbitkan
    dokumen transfer, dan `baris` menggantikan rencana() dengan baris buatan
    pemanggil (barang harian, lihat rencana_harian).
    """
    hari_ini = date.today()
    mulai = hari_ini - timedelta(days=365 * tahun)

    # --- cocokkan daftar dengan isi basis data ---------------------------
    cur.execute("SELECT id, code FROM warehouses")
    gudang = {b["code"]: b["id"] for b in cur.fetchall()}
    cur.execute("SELECT id, name, lead_time_days FROM items")
    barang = {b["name"]: b for b in cur.fetchall()}

    rencana_ = baris if baris is not None else rencana()
    # Dibandingkan terhadap jumlah KOMPONEN, bukan jumlah titik pemasangan:
    # sejak PEMASANGAN ada, satu komponen dapat menempati dua baris rencana.
    komponen = {r["nomor"] for r in rencana_}
    if not lingkup and len(barang) != len(komponen):
        raise SystemExit(
            f"Basis data berisi {len(barang)} barang, daftar berisi "
            f"{len(komponen)}. Dihentikan sebelum menghapus apa pun.")

    for r in rencana_:
        b = barang.get(r["nama"])
        if b is None:
            raise SystemExit(f"Barang tidak ada di basis data: {r['nama']!r}")
        if r["kode_gudang"] not in gudang:
            raise SystemExit(f"Gudang tidak ada: {r['kode_gudang']!r}")
        r["item_id"] = b["id"]
        r["warehouse_id"] = gudang[r["kode_gudang"]]
        r["tunggu"] = b["lead_time_days"] or 14

    ids_lingkup: list[int] | None = None
    if lingkup:
        salah = [k for k in lingkup if k not in gudang]
        if salah:
            raise SystemExit(f"Gudang tidak ada: {salah}")
        ids_lingkup = [gudang[k] for k in lingkup]
        if not semua_baris:
            rencana_ = [r for r in rencana_ if r["kode_gudang"] in lingkup]

    cur.execute("SELECT id FROM suppliers ORDER BY id")
    supplier = [b["id"] for b in cur.fetchall()]
    if not supplier:
        raise SystemExit("Tidak ada pemasok; penerimaan tidak dapat dibuat.")

    # --- hapus transaksi lama --------------------------------------------
    terhapus: dict[str, int] = {}
    if ids_lingkup and not hapus:
        pass
    elif ids_lingkup:
        terhapus = _hapus_lingkup(cur, ids_lingkup)
    else:
        for tabel in URUTAN_HAPUS:
            cur.execute(f"DELETE FROM {tabel}")
            if cur.rowcount:
                terhapus[tabel] = cur.rowcount

    # --- master barang mengikuti laju yang baru --------------------------
    # Titik pesan lama diturunkan dari data dummy yang baru saja dihapus;
    # membiarkannya berarti halaman Pemesanan Ulang menghitung dengan laju satu
    # dunia dan menampilkan riwayat dari dunia yang lain.
    sudah_master: set[int] = set()
    for r in rencana_:
        cadangan = max(1.0, round(r["laju"] * 3, 3))
        titik = round(r["laju"] * r["tunggu"] + cadangan, 3)
        pesanan = max(PESANAN_MINIMAL,
                      round(r["laju"] * r.get("pesanan_hari", PESANAN_HARI)))
        r["titik_pesan"] = titik
        r["pesanan"] = pesanan
        # Titik pesan dan cadangan melekat pada BARANG, bukan pada gudang, dan
        # keduanya sama untuk dua titik pemasangan komponen yang sama -- lajunya
        # memang sama. Menulisnya dua kali tidak salah, hanya sia-sia.
        if r["nomor"] in sudah_master:
            continue
        sudah_master.add(r["nomor"])
        if r.get("harian"):
            # Barang habis pakai: tanpa umur pakai, dan jenisnya tetap habis_pakai.
            cur.execute(
                """
                UPDATE items
                   SET safety_stock = %s, minimum_stock = %s, reorder_point = %s,
                       maximum_stock = %s, usage_type = 'habis_pakai',
                       updated_at = now()
                 WHERE id = %s
                """,
                (cadangan, cadangan, titik, round(titik + pesanan, 3), r["item_id"]),
            )
            continue
        cur.execute(
            """
            UPDATE items
               SET service_life_value = %s, service_life_unit = %s,
                   usage_type = 'berumur_pakai',
                   safety_stock = %s, minimum_stock = %s, reorder_point = %s,
                   maximum_stock = %s, updated_at = now()
             WHERE id = %s
            """,
            (r["umur_nilai"], r["umur_satuan"], cadangan, cadangan, titik,
             round(titik + pesanan, 3), r["item_id"]),
        )

    # --- simulasi hari demi hari -----------------------------------------
    # (tanggal, gudang) -> [(item_id, jumlah)]
    keluar: dict[tuple[date, int], list[tuple[int, int]]] = defaultdict(list)
    # (tanggal, gudang, supplier) -> [(item_id, jumlah, harga)]
    masuk: dict[tuple[date, int, int], list[tuple[int, int]]] = defaultdict(list)
    kurang = 0

    for r in rencana_:
        mulai_r = r.get("mulai", mulai)
        jadwal = _pengeluaran(acak, r, mulai_r, hari_ini)
        gid = r["warehouse_id"]
        if r.get("lantai") is not None:
            _simulasi_terjadwal(acak, r, jadwal, mulai_r, hari_ini, masuk,
                                keluar, supplier)
            continue

        # Titik awal disebar antara titik pesan dan satu pesanan penuh supaya
        # kedua puluh barang tidak memulai siklusnya serentak.
        saldo = r["titik_pesan"] + acak.random() * r["pesanan"]
        tiba: dict[date, int] = {}
        menunggu = False
        masuk[(mulai_r, gid, acak.choice(supplier))].append((r["item_id"], int(saldo) + 1))
        saldo = int(saldo) + 1
        terakhir = mulai_r

        hari = mulai_r + timedelta(days=1)
        while hari <= hari_ini:
            if hari in tiba:
                saldo += tiba.pop(hari)
                menunggu = False
                terakhir = hari

            diminta = jadwal.get(hari, 0)
            if diminta:
                dilayani = min(diminta, saldo)
                kurang += diminta - dilayani
                if dilayani:
                    saldo -= dilayani
                    keluar[(hari, gid)].append((r["item_id"], dilayani))
                    terakhir = hari

            if saldo <= r["titik_pesan"] and not menunggu:
                menunggu = True
                sampai = hari + timedelta(days=r["tunggu"])
                if sampai <= hari_ini:
                    tiba[sampai] = tiba.get(sampai, 0) + r["pesanan"]
                    masuk[(sampai, gid, acak.choice(supplier))].append(
                        (r["item_id"], r["pesanan"]))
            hari += timedelta(days=1)

        # --- cadangan akhir yang ditetapkan PEMASANGAN --------------------
        #
        # Siklus pemesanan di atas berhenti di mana pun fasenya kebetulan
        # berakhir, dan fase itu bergeser tiap kali skrip dijalankan pada
        # tanggal yang berbeda. Skenario transfer menuntut yang sebaliknya:
        # gudang yang kehabisan harus BENAR-BENAR kehabisan dan yang berlebih
        # benar-benar berlebih, hari apa pun perintah ini dijalankan.
        #
        # Koreksinya berupa transaksi biasa, bukan angka yang ditulis langsung
        # ke tabel stok: satu penggantian lagi bila cadangannya harus berkurang,
        # satu pembelian cadangan bila harus bertambah. Keduanya kejadian yang
        # memang terjadi pada komponen seperti ini, dan keduanya tetap tercatat
        # di riwayat -- laporan stok dan riwayat pergerakan tidak pernah
        # berselisih.
        if r["sasaran"] is not None and r["sasaran"] != saldo:
            # Sesudah pergerakan terakhir pasangan ini, supaya saldo berjalan
            # tidak pernah tampak minus; dan tidak lebih tua dari sepekan,
            # supaya koreksinya terbaca sebagai kejadian terbaru.
            tgl = min(hari_ini, max(terakhir + timedelta(days=1),
                                    hari_ini - timedelta(days=7)))
            selisih = r["sasaran"] - saldo
            if selisih > 0:
                masuk[(tgl, gid, acak.choice(supplier))].append(
                    (r["item_id"], selisih))
            else:
                keluar[(tgl, gid)].append((r["item_id"], -selisih))
            saldo = r["sasaran"]

    # --- tulis penerimaan -------------------------------------------------
    harga = {}
    cur.execute("SELECT id, unit_price FROM items")
    for b in cur.fetchall():
        harga[b["id"]] = b["unit_price"]

    jumlah_gr = 0
    for (tgl, gid, sup), baris in sorted(masuk.items()):
        stempel = datetime.combine(tgl, datetime.min.time())
        nomor = next_document_number(
            cur, table="stock_receipts", column="receipt_number", prefix="GR",
            tanggal=tgl, lock_namespace=LOCK_RECEIPT)
        cur.execute(
            """
            INSERT INTO stock_receipts
                (receipt_number, supplier_id, warehouse_id, receipt_date,
                 reference_number, status, notes)
            VALUES (%s, %s, %s, %s, %s, 'completed', %s)
            RETURNING id
            """,
            (nomor, sup, gid, stempel, f"UMUR-{tgl:%Y%m%d}",
             "Penggantian terjadwal menurut umur pakai"),
        )
        rid = cur.fetchone()["id"]
        jumlah_gr += 1
        cur.executemany(
            """
            INSERT INTO stock_receipt_items
                (stock_receipt_id, item_id, quantity, unit_price, received_date)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [(rid, iid, qty, harga[iid], tgl) for iid, qty in baris])
        cur.executemany(
            """
            INSERT INTO stock_movements
                (item_id, warehouse_id, movement_type, reference_id,
                 movement_date, quantity, unit_price)
            VALUES (%s, %s, 'stock_in', %s, %s, %s, %s)
            """,
            [(iid, gid, rid, stempel, qty, harga[iid]) for iid, qty in baris])

    # --- tulis pengeluaran ------------------------------------------------
    jumlah_iss = 0
    for (tgl, gid), baris in sorted(keluar.items()):
        stempel = datetime.combine(tgl, datetime.min.time())
        nomor = next_document_number(
            cur, table="stock_issues", column="issue_number", prefix="ISS",
            tanggal=tgl, lock_namespace=LOCK_ISSUE)
        cur.execute(
            """
            INSERT INTO stock_issues
                (issue_number, warehouse_id, issue_date, purpose,
                 reference_number, status, notes)
            VALUES (%s, %s, %s, %s, %s, 'completed', %s)
            RETURNING id
            """,
            (nomor, gid, stempel, "Penggantian komponen",
             f"UMUR-{tgl:%Y%m%d}", "Penggantian menurut umur pakai"),
        )
        did = cur.fetchone()["id"]
        jumlah_iss += 1
        cur.executemany(
            "INSERT INTO stock_issue_items (stock_issue_id, item_id, quantity) "
            "VALUES (%s, %s, %s)",
            [(did, iid, qty) for iid, qty in baris])
        cur.executemany(
            """
            INSERT INTO stock_movements
                (item_id, warehouse_id, movement_type, reference_id,
                 movement_date, quantity)
            VALUES (%s, %s, 'stock_out', %s, %s, %s)
            """,
            [(iid, gid, did, stempel, -qty) for iid, qty in baris])

    # --- saldo akhir, dihitung DARI pergerakan ----------------------------
    # Pada mode gudang hanya pasangan yang baru dibangun yang dihitung ulang;
    # baris gudang lain tidak disentuh.
    pasangan_i = pasangan_g = None
    if ids_lingkup:
        ps = sorted({(r["item_id"], r["warehouse_id"]) for r in rencana_})
        pasangan_i, pasangan_g = [p[0] for p in ps], [p[1] for p in ps]
    cur.execute(
        """
        INSERT INTO inventory (item_id, warehouse_id, quantity,
                               reserved_quantity, available_quantity)
        SELECT item_id, warehouse_id, SUM(quantity), 0, SUM(quantity)
          FROM stock_movements
         WHERE (%s::bigint[] IS NULL
                OR (item_id, warehouse_id) IN
                   (SELECT * FROM unnest(%s::bigint[], %s::bigint[])))
         GROUP BY item_id, warehouse_id
        """, (pasangan_i, pasangan_i, pasangan_g)
    )
    cur.execute("SELECT count(*) AS n, min(quantity) AS terkecil FROM inventory")
    stok = cur.fetchone()

    # --- transfer antar gudang -------------------------------------------
    # Sesudah persediaan berdiri, bukan sebelumnya: dokumen yang disetujui
    # mencadangkan stok dan yang dikirim menguranginya, dan keduanya menyentuh
    # baris inventory yang baru saja dihitung dari pergerakan di atas.
    if jarak:
        _jarak_gudang(cur, gudang)
    dokumen = (_dokumen_transfer(cur, rencana_=rencana_, gudang=gudang,
                                 hari_ini=hari_ini) if dokumen else [])

    return {
        "terhapus": terhapus,
        "mulai": str(mulai), "akhir": str(hari_ini),
        "penerimaan": jumlah_gr, "pengeluaran": jumlah_iss,
        "baris_stok": stok["n"], "stok_terkecil": float(stok["terkecil"]),
        "permintaan_tak_terlayani": kurang,
        "komponen_dua_gudang": len(PEMASANGAN),
        "transfer": len(dokumen),
    }


# ==========================================================================
# Transfer antar gudang
# ==========================================================================

def _jarak_gudang(cur, gudang: dict[str, int]) -> None:
    """Jarak jalan darat antar gudang, yang mengalahkan haversine."""
    for asal, tujuan, km, tempuh, catatan in JARAK_GUDANG:
        cur.execute(
            """
            INSERT INTO warehouse_distances
                (from_warehouse_id, to_warehouse_id, distance_km,
                 lead_time_days, notes)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (gudang[asal], gudang[tujuan], km, tempuh, catatan),
        )


def _dokumen_transfer(cur, *, rencana_: list[dict], gudang: dict[str, int],
                      hari_ini: date) -> list[str]:
    """
    Dokumen transfer yang sudah berjalan, satu untuk tiap tahap.

    TAHAPNYA DILEWATI SATU PER SATU, tidak ditulis langsung sebagai "sudah
    diterima". Yang menggerakkan stok adalah perpindahan status, bukan status
    itu sendiri (app/routers/transfer.terapkan_status), jadi dokumen yang
    disisipkan langsung dalam keadaan akhir akan menyatakan barang sudah sampai
    sementara gudang asalnya tidak pernah kehilangan satu unit pun -- selisih
    yang tidak pernah terbit sebagai galat, hanya sebagai stok yang tidak cocok
    saat opname. Melewati tahapnya juga yang mengisi cap waktu tiap tahap, dan
    itulah yang dibaca layar.
    """
    from decimal import Decimal

    from app.common import LOCK_TRANSFER
    from app.routers.transfer import terapkan_status

    id_barang = {r["nomor"]: r["item_id"] for r in rencana_}
    sku = {r["nomor"]: r["nama"] for r in rencana_}
    jarak = {(a, t): km for a, t, km, _, _ in JARAK_GUDANG}

    cur.execute("SELECT id, name FROM warehouses")
    nama_gudang = {b["id"]: b["name"] for b in cur.fetchall()}

    nomor_terbit: list[str] = []
    for nomor, asal, tujuan, qty, akhir, lalu, skor, alasan in DOKUMEN_TRANSFER:
        gid_asal, gid_tujuan = gudang[asal], gudang[tujuan]
        item_id = id_barang[nomor]
        tanggal = hari_ini - timedelta(days=lalu)
        stempel = datetime.combine(tanggal, datetime.min.time())

        no_trf = next_document_number(
            cur, table="stock_transfers", column="transfer_number",
            prefix="TRF", tanggal=tanggal, lock_namespace=LOCK_TRANSFER)
        cur.execute(
            """
            INSERT INTO stock_transfers
                (transfer_number, from_warehouse_id, to_warehouse_id,
                 transfer_date, status, notes, source, score, reason,
                 distance_km)
            VALUES (%s, %s, %s, %s, 'draft', %s, 'transfer_engine', %s, %s, %s)
            RETURNING id
            """,
            (no_trf, gid_asal, gid_tujuan, stempel,
             "Penggantian terjadwal menurut umur pakai", skor, alasan,
             jarak.get((asal, tujuan))),
        )
        transfer_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO stock_transfer_items
                (stock_transfer_id, item_id, quantity, for_item_id, match_type)
            VALUES (%s, %s, %s, %s, 'sku')
            """,
            (transfer_id, item_id, qty, item_id),
        )

        header = {"from_warehouse_id": gid_asal, "to_warehouse_id": gid_tujuan,
                  "from_warehouse_name": nama_gudang.get(gid_asal, "")}
        baris = [{"item_id": item_id, "quantity": Decimal(qty),
                  "sku": sku[nomor]}]

        dari = RANTAI_STATUS[0]
        for langkah, ke in enumerate(
                RANTAI_STATUS[1:RANTAI_STATUS.index(akhir) + 1]):
            # Tiap tahap sehari sesudah tahap sebelumnya, dan tidak pernah
            # melewati hari ini: dokumen yang cap kirimnya besok tidak dapat
            # dijelaskan kepada siapa pun.
            waktu = datetime.combine(
                min(hari_ini, tanggal + timedelta(days=langkah)),
                datetime.min.time())
            terapkan_status(cur, transfer_id=transfer_id, dari=dari, ke=ke,
                            header=header, baris=baris, stempel=waktu)
            dari = ke

        nomor_terbit.append(no_trf)

    return nomor_terbit


# ==========================================================================
# Penyewa Demo Inventory AI
# ==========================================================================
#
# Kedua gudang demo diisi dua puluh komponen yang sama dengan Perusahaan Utama
# (10 di WH-SBY, 10 di WH-JKT), dengan riwayat yang diturunkan dari lama
# pemakaian. Seluruh katalog bawaan demo.py dihapus.

# (sku, nama, kategori, harga satuan, kekritisan, waktu tunggu)
KATALOG_DEMO = [
    ("GP-7001", "Gear Pump ABB 29805",            "Sparepart Mesin", 21_000_000, "medium", 14),
    ("RB-7002", "Roller Bearing ABB 70416",       "Sparepart Mesin",    850_000, "high",    7),
    ("OH-7003", "Oli Hidrolik Kobelco 11972",     "Pelumas & Kimia",  8_900_000, "medium", 21),
    ("CP-7004", "Centrifugal Pump Festo 31859",   "Sparepart Mesin", 28_500_000, "medium",  7),
    ("BB-7005", "Ball Bearing Pertamina 81413",   "Sparepart Mesin",    640_000, "low",     7),
    ("OH-7006", "Oli Hidrolik Shell 36011",       "Pelumas & Kimia",  7_600_000, "medium", 21),
    ("CP-7007", "Centrifugal Pump Yokogawa 8703", "Sparepart Mesin", 31_000_000, "medium", 10),
    ("RB-7008", "Roller Bearing Pertamina 53651", "Sparepart Mesin",    780_000, "medium", 30),
    ("OH-7009", "Oli Hidrolik Parker 65767",      "Pelumas & Kimia",  8_200_000, "high",   45),
    ("GP-7010", "Gear Pump Donaldson 24745",      "Sparepart Mesin", 18_500_000, "low",     7),
    # --- WH-JKT (daftar kedua pengguna, 28 September 2026) ---
    ("GP-7011", "Gear Pump Parker 45907",         "Sparepart Mesin", 19_800_000, "high",   30),
    ("RB-7012", "Roller Bearing Siemens 23915",   "Sparepart Mesin",    920_000, "high",   45),
    ("FO-7013", "Filter Oli Timken 58773",        "Pelumas & Kimia",    450_000, "high",   10),
    ("CP-7014", "Centrifugal Pump Donaldson 77607", "Sparepart Mesin", 29_500_000, "high", 10),
    ("RB-7015", "Roller Bearing Timken 19505",    "Sparepart Mesin",    890_000, "critical", 21),
    ("FO-7016", "Filter Oli ABB 37613",           "Pelumas & Kimia",    520_000, "medium", 14),
    ("GP-7017", "Gear Pump Grundfos 68749",       "Sparepart Mesin", 17_200_000, "low",     7),
    ("BB-7018", "Ball Bearing Schneider 2377",    "Sparepart Mesin",    710_000, "low",    14),
    ("OH-7019", "Oli Hidrolik Schneider 25705",   "Pelumas & Kimia",  8_400_000, "medium", 45),
    ("GP-7020", "Gear Pump Bosch 93252",          "Sparepart Mesin", 20_500_000, "low",    21),
]


def pakai_profil_demo() -> None:
    """
    Mengganti tabel data modul ini dengan yang berlaku bagi penyewa demo.

    Demo meniru Perusahaan Utama apa adanya -- dua puluh komponen, 1-10 di
    Surabaya dan 11-20 di Jakarta, sebaran dua gudang dan dokumen transfer yang
    sama -- hanya kode gudangnya yang berbeda.
    """
    global PERUSAHAAN, TABEL, PEMASANGAN, DOKUMEN_TRANSFER, JARAK_GUDANG
    peta = {"WH-CEN-01": "WH-SBY", "WH-CEN-02": "WH-JKT"}
    PERUSAHAAN = 2
    TABEL = [(n, nama, nilai, satuan, peta[k]) for n, nama, nilai, satuan, k in TABEL]
    PEMASANGAN = [(n, {peta[k]: c for k, c in isi.items()}, ket)
                  for n, isi, ket in PEMASANGAN]
    # Permintaan pengguna 28 September 2026: cadangan Oli Hidrolik Parker di
    # Surabaya demo habis (0), dan ia tidak disimpan di gudang lain -- jadi
    # halaman Transfer menjawab "beli" untuknya.
    PEMASANGAN.append((9, {"WH-SBY": 0}, "habis di Surabaya, tanpa sumber transfer"))
    JARAK_GUDANG = [(peta[a], peta[t], *sisa) for a, t, *sisa in JARAK_GUDANG]
    DOKUMEN_TRANSFER = [(n, peta[a], peta[t], *sisa)
                        for n, a, t, *sisa in DOKUMEN_TRANSFER]


def terapkan_pada_demo(cur, tahun: int = TAHUN_RIWAYAT) -> dict:
    """
    Titik masuk bagi app.demo.isi(): mengganti isi WH-SBY penyewa demo dengan
    komponen dan riwayat dari lama pemakaian, sesudah katalog bawaan terisi.

    Tabel data modul ini ditukar sebentar lalu DIKEMBALIKAN, karena pemanggilnya
    proses server yang hidup lama dan skrip perusahaan utama memakai tabel yang
    sama pada proses yang sama.
    """
    global PERUSAHAAN, TABEL, PEMASANGAN, DOKUMEN_TRANSFER, JARAK_GUDANG
    simpan = (PERUSAHAAN, TABEL, PEMASANGAN, DOKUMEN_TRANSFER, JARAK_GUDANG)
    try:
        pakai_profil_demo()
        siapkan_master_demo(cur)
        hasil = bangun(cur, random.Random(BENIH), tahun,
                       ["WH-SBY", "WH-JKT"], semua_baris=True,
                       hapus=False, jarak=False)
        hasil["barang_lama_dihapus"] = bersihkan_barang_lama_demo(cur)
    finally:
        PERUSAHAAN, TABEL, PEMASANGAN, DOKUMEN_TRANSFER, JARAK_GUDANG = simpan
    # Dua gudang tambahan (Semarang, Makassar), sepuluh barang habis pakai di
    # empat gudang, dan riwayat transfer setahun: lihat tools/jaringan_gudang.
    # Dijalankan SESUDAH profil komponen dikembalikan; modul itu memakai
    # tabelnya sendiri.
    from tools import jaringan_gudang
    hasil["jaringan"] = jaringan_gudang.bangun_jaringan(cur, "demo")
    return hasil


def siapkan_master_demo(cur) -> None:
    """Membuat barang baru pada penyewa demo (idempoten menurut nama)."""
    cur.execute("SELECT is_demo FROM companies")
    b = cur.fetchone()
    if b is None or not b["is_demo"]:
        raise SystemExit("Perusahaan ini bukan penyewa demo; dihentikan.")
    cur.execute("SELECT id FROM units WHERE code = 'PCS'")
    satuan = cur.fetchone()["id"]
    cur.execute("SELECT id, name FROM categories")
    kategori = {r["name"]: r["id"] for r in cur.fetchall()}
    cur.execute("SELECT name FROM items")
    ada = {r["name"] for r in cur.fetchall()}
    for sku, nama, kat, harga, kritis, tunggu in KATALOG_DEMO:
        if nama in ada:
            continue
        cur.execute(
            """
            INSERT INTO items (sku, name, category_id, unit_id, unit_price,
                               criticality, lead_time_days, usage_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'berumur_pakai')
            """, (sku, nama, kategori[kat], satuan, harga, kritis, tunggu))


def bersihkan_barang_lama_demo(cur) -> int:
    """
    Menghapus SELURUH barang katalog bawaan demo (demo.BARANG), di gudang mana
    pun, berikut riwayatnya. Barang habis pakai penggantinya dibangun
    tools/jaringan_gudang.py; yang tersisa hanya komponen berumur pakai.
    """
    from app import demo
    cur.execute("SELECT id FROM items WHERE sku = ANY(%s)",
                ([b[0] for b in demo.BARANG],))
    return _hapus_barang(cur, [r["id"] for r in cur.fetchall()])


def _hapus_barang(cur, ids: list[int]) -> int:
    """Menghapus barang beserta seluruh riwayatnya; dokumen yang barisnya habis ikut."""
    if not ids:
        return 0
    for tabel in ("serial_numbers", "stock_movements", "inventory",
                  "purchase_order_items", "stock_receipt_items",
                  "stock_issue_items", "stock_transfer_items",
                  "stock_adjustment_items"):
        cur.execute(f"DELETE FROM {tabel} WHERE item_id = ANY(%s)", (ids,))
    for kepala, baris, kolom in (
            ("stock_receipts", "stock_receipt_items", "stock_receipt_id"),
            ("stock_issues", "stock_issue_items", "stock_issue_id"),
            ("stock_adjustments", "stock_adjustment_items", "stock_adjustment_id")):
        cur.execute(f"DELETE FROM {kepala} h WHERE NOT EXISTS "
                    f"(SELECT 1 FROM {baris} b WHERE b.{kolom} = h.id)")
    # Dokumen transfer yang barisnya habis, berikut jejak ledger yang tersisa.
    cur.execute("SELECT id FROM stock_transfers t WHERE NOT EXISTS "
                "(SELECT 1 FROM stock_transfer_items b WHERE b.stock_transfer_id = t.id)")
    kosong = [r["id"] for r in cur.fetchall()]
    if kosong:
        cur.execute("DELETE FROM stock_movements WHERE movement_type IN "
                    "('transfer_in', 'transfer_out') AND reference_id = ANY(%s)", (kosong,))
        cur.execute("DELETE FROM stock_transfers WHERE id = ANY(%s)", (kosong,))
    cur.execute("DELETE FROM items WHERE id = ANY(%s)", (ids,))
    return cur.rowcount


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--terapkan", action="store_true",
                    help="tulis ke basis data; tanpa ini hanya menampilkan rencana")
    ap.add_argument("--gudang", action="append", metavar="KODE",
                    help="batasi pada gudang ini (boleh diulang); gudang lain "
                         "tidak disentuh. Tanpa ini: seluruh perusahaan")
    ap.add_argument("--tahun", type=int, default=TAHUN_RIWAYAT,
                    help=f"panjang riwayat dalam tahun (bawaan {TAHUN_RIWAYAT})")
    a = ap.parse_args()
    hari_jendela = 365 * a.tahun
    print(f"Jam operasi    : {JAM_OPERASI_PER_HARI} jam/hari")
    print(f"Unit terpasang : {UNIT_TERPASANG} per komponen")
    print(f"Riwayat        : {a.tahun} tahun ({hari_jendela} hari)\n")
    print(f"Terpasang di dua pabrik: {len(PEMASANGAN)} dari {len(TABEL)} komponen\n")
    print(f"{'no':>2}  {'komponen':<34} {'gudang':<10} {'umur pakai':>13}  "
          f"{'ganti tiap':>11} {'penggantian':>12} {'sisa':>5}")
    sepi = []
    for r in rencana():
        if a.gudang and r["kode_gudang"] not in a.gudang:
            continue
        n = r["laju"] * hari_jendela
        if n < 3 and r["nama"] not in sepi:
            sepi.append(r["nama"])
        sisa = "-" if r["sasaran"] is None else str(r["sasaran"])
        print(f"{r['nomor']:>2}  {r['nama']:<34} {r['kode_gudang']:<10} "
              f"{r['umur_nilai']:>8,} {r['umur_satuan']:<4} "
              f"{r['umur_hari']:>8.0f} hr {n:>12.1f} {sisa:>5}")

    print("\nKolom 'sisa' = cadangan yang ditetapkan tersisa pada hari terakhir "
          "(PEMASANGAN);\n'-' berarti seadanya menurut siklus pemesanan.")

    if sepi:
        print(f"\n{len(sepi)} komponen bergerak kurang dari 3 kali sepanjang "
              f"riwayat ini, sehingga tidak akan mendapat prakiraan:")
        for nama in sepi:
            print(f"  - {nama}")
        print("  Perpanjang jendelanya dengan --tahun bila daur penggantiannya "
              "perlu terlihat.")

    if not a.terapkan:
        print("\n(rencana saja -- basis data tidak disentuh; "
              "tambahkan --terapkan untuk menulis)")
        return

    acak = random.Random(BENIH)
    try:
        with tenant.jalankan_sebagai(PERUSAHAAN, "Perusahaan Utama"):
            with transaction() as cur:
                hasil = bangun(cur, acak, a.tahun, a.gudang)
    finally:
        close_pool()

    print("\n== selesai ==")
    for kunci, nilai in hasil.items():
        print(f"  {kunci}: {nilai}")


if __name__ == "__main__":
    main()
