# -*- coding: utf-8 -*-
"""
Penyewa demo: mengisi, mengosongkan, dan menyimulasikan penjualan.

UNTUK APA. Menjual sistem ini menuntut satu hal yang tidak bisa disiapkan
sebelumnya: calon pelanggan harus melihat angkanya BERGERAK. Tangkapan layar
tidak membuktikan apa pun, dan mengetik transaksi satu per satu di depan orang
membuat presentasi berhenti di formulir. Modul ini menyediakan satu tombol yang
mencatat penjualan sungguhan, lalu membiarkan seluruh sistem bereaksi
sendiri -- stok turun, peringatan stok menipis menyala, prakiraan bergeser,
rekomendasi pemesanan berubah.

DATANYA DIBANGKITKAN, BUKAN DISALIN. Menyalin dari perusahaan lain berarti
membaca lintas penyewa, dan itu tepat yang dilarang seluruh lapisan pada Tahap
1. Membangkitkannya sendiri membuat modul ini berjalan sebagai penyewa demo
biasa, dengan hak yang sama seperti pengguna mana pun -- sehingga tombol reset
di layar tidak menuntut satu pun hak istimewa.

ANGKANYA TETAP SAMA SETIAP KALI. Pembangkit acaknya berbenih tetap, jadi
demo yang diulang menghasilkan angka yang sama persis. Itu disengaja: orang
yang mendemokan sistem ini perlu tahu apa yang akan muncul di layar sebelum ia
menekan tombolnya.

PENJAGA. Seluruh fungsi yang MENGHAPUS memeriksa lebih dulu bahwa perusahaan
yang sedang aktif benar-benar bertanda demo. Perusahaan biasa tidak akan pernah
bisa mengosongkan dirinya sendiri lewat jalur ini, bahkan bila endpoint-nya
dipanggil langsung.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from decimal import Decimal

from .common import (LOCK_ISSUE, LOCK_RECEIPT, LOCK_TRANSFER,
                     next_document_number)
from .config import APP_TZ
from .errors import AppError

# Benih tetap: lihat catatan pada docstring.
BENIH = 20260828

# Panjang riwayat yang dibangkitkan. 90 hari cukup untuk memberi prakiraan dua
# belas siklus mingguan penuh -- jauh di atas ambang minimum pada config.py --
# tanpa membuat pengisian ulang terasa lambat saat tombol reset ditekan.
HARI_RIWAYAT = 90

# Besar satu pesanan, dinyatakan dalam hari kebutuhan. Angka ini yang
# menentukan berapa banyak barang tampak "stok menipis" pada hari demo
# dijalankan, dan itu pertanyaan tampilan, bukan hanya pertanyaan simulasi.
#
# Satu pasangan barang/gudang berada di bawah titik pesan selama waktu tunggu
# supplier, lalu terisi kembali. Jadi porsi barang yang tampak menipis pada satu
# hari mana pun kira-kira = waktu tunggu / panjang siklus. Dengan waktu tunggu
# 5-14 hari dan pesanan sebesar 55 hari kebutuhan, angkanya jatuh sekitar 15%.
#
# Itu angka yang dituju, dan dituju dengan sengaja. Pesanan sebesar 28 hari --
# nilai yang dipakai lebih dulu -- membuat 43% seluruh rak tampak kritis, dan
# gudang yang hampir seluruhnya merah tidak terbaca sebagai sistem yang
# mengawasi dengan baik, melainkan sebagai gudang yang kacau. Sebaliknya, tanpa
# ada satu pun yang menipis, halaman Stok Menipis dan Pemesanan Ulang kosong --
# dan dua halaman itu justru yang paling ingin dilihat calon pelanggan.
HARI_STOK_PESANAN = 55

# --- irama kiriman untuk barang yang tersebar di dua gudang ----------------
#
# Barang pada SEBARAN tidak mengikuti pemesanan otomatis simulasi, melainkan
# jadwal kiriman tetap: tiap SIKLUS_SEBARAN hari, dan yang terakhir
# JEDA_SEBARAN hari sebelum hari ini. Tiap kiriman mengisi sampai setinggi
# "lantai yang dituju + perkiraan pemakaian sampai kiriman berikutnya",
# sehingga pada hari terakhir riwayat pasangan itu berdiri persis di lantainya.
#
# KENAPA TIDAK MENGANDALKAN SIKLUS BIASA. Posisi akhir siklus otomatis
# bergantung pada fase awal yang diundi, dan fase itu bergeser tiap kali panjang
# riwayat atau tanggal hari ini berubah. Skenario transfer menuntut yang
# sebaliknya: satu gudang harus BENAR-BENAR di bawah titik pesan dan gudang
# seberangnya benar-benar berlebih, setiap kali tombol Isi Ulang ditekan, hari
# apa pun.
#
# SELURUH KOREKSINYA BERUPA PENERIMAAN, tidak pernah pengeluaran. Prakiraan
# dibangun dari pergerakan bertanda negatif (routers/forecasting.py), jadi
# menambah barang tidak menyentuh laju pemakaian sama sekali -- sedangkan
# "menurunkan stok supaya terlihat menipis" berarti mengarang lonjakan
# permintaan, yang kemudian ikut menaikkan titik pesan dan jumlah pesanan di
# layar tanpa ada yang benar-benar memakainya.
SIKLUS_SEBARAN = 21
JEDA_SEBARAN = 14

# Pemakaian rata-rata satu hari sebagai pecahan laju harian barang: rata-rata
# pola mingguan (0,821) dikali rata-rata sebaran acak pada _permintaan (1,025).
# Dipakai HANYA untuk menaksir tinggi isi ulang; simpangannya selama dua minggu
# tinggal sekitar satu laju harian, jauh lebih kecil daripada jarak antar lantai
# pada SEBARAN.
LAJU_EFEKTIF = 0.84


# ==========================================================================
# Katalog
# ==========================================================================
#
# Ditulis sebagai data, bukan disebar di dalam kode pengisian. Menambah barang
# atau gudang cukup menyunting daftar di bawah; tidak ada satu baris logika pun
# yang perlu ikut berubah.

KATEGORI = [
    "Sparepart Mesin", "Pelumas & Kimia", "Alat Listrik",
    "Alat Pelindung Diri", "Perkakas", "Consumable Produksi",
]

SATUAN = [
    ("Pieces", "PCS"), ("Box", "BOX"), ("Liter", "LTR"),
    ("Meter", "MTR"), ("Set", "SET"),
]

# Gudang Bandung dihapus 31 Agustus 2026 atas permintaan pengguna: tidak
# dipakai, dan tiga gudang membuat layar perbandingan lebih ramai daripada
# gunanya.
#
# URUTAN DAFTAR INI BERARTI: tiap barang pada BARANG menyebut gudangnya menurut
# posisi di sini, 0 untuk yang pertama. Menghapus atau menyisipkan baris tanpa
# ikut membetulkan kolom itu memindahkan barang ke gudang yang salah, atau
# menunjuk gudang yang tidak ada -- karena itu ada pemeriksaan tepat di bawah
# katalog.
# Koordinat dan waktu tempuh ikut sejak modul Transfer Antar Gudang: keduanya
# yang membuat jarak antar gudang dapat dihitung sama sekali. Gudang demo tanpa
# koordinat akan membuat setiap kandidat transfer dinilai netral pada komponen
# jarak, dan layar yang dipakai memperkenalkan modul itu justru tidak dapat
# menunjukkan hal yang membedakannya.
#
# (kode, nama, lokasi, lintang, bujur, waktu tempuh ke gudang ini dalam hari)
GUDANG = [
    ("WH-JKT", "Gudang Pusat Jakarta", "Cakung, Jakarta Timur", -6.2088, 106.8456, 3),
    ("WH-SBY", "Gudang Surabaya", "Rungkut, Surabaya", -7.2575, 112.7521, 2),
]

SUPPLIER = [
    ("SUP-01", "PT Sinar Teknik Nusantara", 7),
    ("SUP-02", "CV Mitra Industri Jaya", 14),
    ("SUP-03", "PT Karya Pelumas Prima", 5),
    ("SUP-04", "PT Aman Sentosa Safety", 10),
]

# (sku, nama, kategori, satuan, harga, permintaan harian rata-rata,
#  kekritisan, gudang)
#
# SATU BARANG HANYA DI SATU GUDANG, sepuluh barang di tiap gudang. Bentuk ini
# mengikuti basis data yang dipangkas 1 September 2026 atas permintaan pengguna;
# sebelumnya katalog berisi 36 barang, gudang pusat menyimpan seluruhnya dan
# cabang menyimpan sebagian yang dipilih acak -- sekitar 60 baris stok, lebih
# banyak daripada yang sempat dibaca siapa pun selama satu demo berlangsung.
#
# YANG DIKORBANKAN: barang berputaran rendah. Katalog lama merentang 0,3 sampai
# 40 unit per hari; yang tersisa 4 sampai 40. Itu bukan kebetulan -- barang yang
# dipakai kurang dari sekali seminggu justru yang riwayatnya terlalu tipis untuk
# diprakirakan, dan ia muncul sebagai "Insufficient Data" tepat di halaman yang
# paling ingin ditunjukkan. Menambahkannya kembali cukup dengan menulis
# barisnya di sini; tidak ada tempat lain yang mengunci angka sepuluh.
BARANG = [
    # --- WH-JKT, Gudang Pusat Jakarta ---
    ("SP-1003", "V-Belt A-52",                  0, 0,    62_000,  4.0, "medium", 0),
    ("SP-1004", "Seal Oli 35x52x7",             0, 0,    28_000,  8.0, "medium", 0),
    ("PL-2002", "Oli Gearbox EP-90",            1, 2,    45_000, 12.0, "medium", 0),
    ("PL-2003", "Grease Multipurpose EP-2",     1, 0,    52_000,  6.5, "medium", 0),
    ("PL-2004", "Cairan Pendingin Radiator",    1, 2,    26_000,  9.0, "low",    0),
    ("PL-2006", "Thinner Industri",             1, 2,    22_000, 15.0, "low",    0),
    ("PD-4002", "Kacamata Safety Bening",       3, 0,    45_000,  5.0, "medium", 0),
    ("PK-5004", "Mata Gerinda Potong 4 inci",   4, 1,    95_000,  9.5, "medium", 0),
    ("CP-6001", "Kawat Las RB-26 2.6mm",        5, 1,   165_000, 13.0, "high",   0),
    ("CP-6005", "Cat Anti Karat Merah",         5, 2,    88_000,  4.5, "medium", 0),

    # --- WH-SBY, Gudang Surabaya ---
    ("SP-1001", "Bearing 6205 ZZ",              0, 0,    85_000,  6.0, "high",   1),
    ("PL-2001", "Oli Hidrolik ISO VG 46",       1, 2,    38_000, 24.0, "high",   1),
    ("EL-3001", "Kabel NYY 3x2.5mm",            2, 3,    18_500, 40.0, "medium", 1),
    ("EL-3006", "Terminal Block 10mm",          2, 1,    12_000, 18.0, "low",    1),
    ("PD-4001", "Sarung Tangan Nitril",         3, 1,    75_000, 22.0, "medium", 1),
    ("PD-4005", "Masker Respirator N95",        3, 1,   135_000, 11.0, "high",   1),
    ("PD-4006", "Earplug Busa",                 3, 1,    38_000,  7.0, "low",    1),
    ("CP-6002", "Amplas Roll P80",              5, 3,    32_000, 16.0, "low",    1),
    ("CP-6003", "Lakban Industri 2 inci",       5, 0,    18_000, 20.0, "low",    1),
    ("CP-6004", "Majun Katun",                  5, 1,    28_000, 25.0, "low",    1),
]


# Gagal saat modul dimuat, bukan saat tombol Reset Demo ditekan di depan calon
# pelanggan. Bukan `assert`: python -O membuang assert, dan penjaga yang hilang
# di produksi justru di lingkungan itulah kegagalannya paling mahal.
_gudang_salah = [b[0] for b in BARANG if not 0 <= b[7] < len(GUDANG)]
if _gudang_salah:
    raise RuntimeError(
        "Katalog demo menyebut gudang di luar daftar GUDANG: "
        + ", ".join(_gudang_salah))


# ==========================================================================
# Barang yang sengaja disimpan di DUA gudang
# ==========================================================================
#
# KENAPA ADA. Sampai 3 September 2026 tidak ada satu pun barang demo yang
# tersimpan di lebih dari satu gudang, dan akibatnya halaman Transfer Antar
# Gudang menjawab "beli baru" pada setiap barisnya. Bukan karena mesinnya salah:
# modul itu mencari gudang lain yang SUDAH punya barangnya, dan gudang seperti
# itu memang tidak pernah ada. Halaman yang selalu menjawab hal yang sama tidak
# dapat dipakai memperkenalkan apa pun.
#
# Daftar di bawah menyebut barang mana yang disimpan di dua gudang sekaligus,
# BESERTA posisi tiap gudang pada hari terakhir riwayat -- dinyatakan sebagai
# KELIPATAN TITIK PESAN barang itu, bukan jumlah unit, supaya angkanya ikut
# benar untuk barang yang lajunya 4 unit/hari maupun 40.
#
#   0,55 - 0,90  di bawah titik pesan: gudang inilah yang kekurangan
#   1,70         di atas titik pesan, tetapi surplusnya TIDAK menutup seluruh
#                kebutuhan gudang seberang -> transfer sebagian
#   3,40         berlebih; surplusnya menutup seluruh kebutuhan -> transfer penuh
#   2,00 - 2,40  sama-sama aman; tidak muncul di daftar rekomendasi sama sekali
#
# ANGKANYA DAPAT DIPERIKSA, dan dipilih supaya dapat. Titik pesan demo = laju x
# (waktu tunggu + 3) dan sasaran pengadaan = laju x max(waktu tunggu + 3, 17)
# (lihat app/decision.py). Dengan waktu tunggu skenario dipatok tujuh hari,
# titik pesan = 10 laju dan sasaran = 17 laju, sehingga:
#
#   gudang di 0,55 titik pesan  -> kebutuhannya 1,15 titik pesan
#   sumber di 3,40 titik pesan  -> surplusnya   2,40 titik pesan  -> menutup
#   sumber di 1,70 titik pesan  -> surplusnya   0,70 titik pesan  -> sebagian
#   sumber di 0,90 titik pesan  -> surplusnya   nol, dan gudang itu sendiri
#                                  perlu memesan -> ditolak sebagai sumber
#
# WAKTU TUNGGUNYA DIPATOK justru supaya perhitungan di atas berlaku. Barang lain
# mengundi waktu tunggunya 5/7/10/14 hari, dan pada 14 hari sasaran pengadaan
# berimpit dengan titik pesan sehingga kebutuhannya menyusut sampai seperlima --
# skenario "transfer sebagian" akan berubah menjadi transfer penuh tanpa satu
# baris pun yang berubah di berkas ini.
TUNGGU_SEBARAN = 7

# (sku, {indeks gudang: kelipatan titik pesan}, apa yang hendak ditunjukkan)
SEBARAN = [
    ("SP-1001", {1: 3.40, 0: 0.55},
     "transfer penuh: Surabaya berlebih, Jakarta di bawah titik pesan"),
    ("CP-6001", {0: 3.40, 1: 0.55},
     "transfer penuh arah sebaliknya: Jakarta yang berlebih"),
    ("PL-2001", {1: 1.70, 0: 0.80},
     "transfer sebagian: surplus Surabaya hanya menutup sebagian kebutuhan"),
    ("PD-4005", {1: 0.90, 0: 0.65},
     "tetap pembelian: gudang seberang punya barangnya tetapi ikut menipis"),
    ("PL-2002", {0: 2.40, 1: 2.00},
     "dua gudang sama-sama aman; dipakai dokumen transfer yang sudah diterima"),
    ("PD-4001", {1: 2.20, 0: 2.00},
     "dua gudang aman; dipakai dokumen yang sedang dalam perjalanan"),
    ("EL-3006", {1: 2.30, 0: 2.00},
     "dua gudang aman; dipakai dokumen yang baru disetujui"),
]

# Jarak jalan darat antar gudang, BUKAN jarak garis lurus. Haversine Jakarta ->
# Surabaya 665 km; yang benar-benar ditempuh truk lewat tol Trans-Jawa hampir
# 800 km, dan arah baliknya tidak persis sama. Tanpa baris ini modul Transfer
# tetap berjalan -- ia jatuh ke haversine -- tetapi layar yang dipakai
# memperkenalkannya justru tidak dapat menunjukkan hal yang membedakannya.
#
# (indeks gudang asal, indeks gudang tujuan, km, hari, catatan)
JARAK_GUDANG = [
    (0, 1, 795.0, 3, "Tol Trans-Jawa, muat balik lewat Semarang"),
    (1, 0, 780.0, 2, "Tol Trans-Jawa, langsung"),
]

# --- dokumen transfer yang sudah berjalan ---------------------------------
#
# KENAPA DOKUMENNYA IKUT DIBANGKITKAN. Rekomendasi menjawab "apa yang sebaiknya
# dipindahkan"; ia tidak pernah menunjukkan seperti apa barang yang MEMANG
# sedang berpindah. Tanpa dokumen, tab Dokumen kosong pada demo pertama dan
# empat tahap yang membedakan modul ini -- diajukan, disetujui, dikirim,
# diterima -- tidak pernah terlihat satu pun.
#
# BARANGNYA SENGAJA BUKAN BARANG SKENARIO. Dokumen yang disetujui mencadangkan
# stok gudang asal dan yang dikirim benar-benar menguranginya; menaruhnya pada
# pasangan yang angkanya sudah disetel di SEBARAN berarti angka-angka yang
# dijelaskan di atas tidak lagi cocok dengan yang tampil di layar. Tiga barang
# terakhir pada SEBARAN ada justru untuk ini: dua gudangnya sama-sama aman, jadi
# stok yang bergerak sedikit tidak memindahkan satu baris pun ke daftar merah.
# Kecuali yang terakhir: dokumen "diajukan" tidak menyentuh stok sama sekali,
# jadi ia boleh -- dan memang seharusnya -- berdiri di atas rekomendasi hari ini.
#
# (sku, gudang asal, gudang tujuan, kelipatan titik pesan, status akhir,
#  berapa hari lalu diajukan, skor saat pengajuan, alasan yang dibekukan)
DOKUMEN_TRANSFER = [
    ("PL-2002", 0, 1, 0.40, "completed", 6, 78,
     "Jakarta menyimpan surplus 3 kali kebutuhan; menutup seluruh kekurangan "
     "Surabaya tanpa pembelian."),
    ("PD-4001", 1, 0, 0.35, "in_transit", 2, 82,
     "Surabaya surplus dan berjarak 780 km, waktu tempuh 2 hari -- tercepat "
     "di antara gudang yang punya barangnya."),
    ("PL-2002", 0, 1, 0.30, "in_transit", 1, 77,
     "Jakarta masih menyisakan cadangan setelah kiriman sebelumnya; jarak 795 km, "
     "waktu tempuh 3 hari. Arah sebaliknya dari kiriman Surabaya yang sedang jalan."),
    ("EL-3006", 1, 0, 0.30, "approved", 1, 74,
     "Surplus Surabaya mencukupi; stok dicadangkan menunggu jadwal kirim."),
    ("SP-1001", 1, 0, 1.15, "draft", 0, 88,
     "Surabaya berlebih 2,4 kali titik pesan; seluruh kebutuhan Jakarta dapat "
     "ditutup tanpa membeli."),
]

# Urutan tahap yang dilewati sebuah dokumen. Sama dengan app/transfer.PERPINDAHAN
# dibaca dari draft ke completed; ditulis di sini supaya pembangkit dapat
# berhenti di tahap mana pun.
_RANTAI_STATUS = ("draft", "approved", "in_transit", "completed")

# Penjaga yang sama seperti pada katalog: gagal saat modul dimuat, bukan di
# depan calon pelanggan.
_sku_katalog = {b[0]: b for b in BARANG}


def _periksa_sebaran() -> None:
    for sku, isi, _ in SEBARAN:
        if sku not in _sku_katalog:
            raise RuntimeError(f"SEBARAN menyebut SKU di luar katalog: {sku}")
        if len(isi) < 2:
            raise RuntimeError(
                f"SEBARAN {sku} hanya menyebut satu gudang; barang yang tidak "
                f"tersimpan di dua tempat tidak perlu ada di daftar ini")
        salah = [g for g in isi if not 0 <= g < len(GUDANG)]
        if salah:
            raise RuntimeError(f"SEBARAN {sku} menyebut gudang di luar GUDANG: {salah}")
        # Gudang asal barang pada katalog wajib ikut disebut. Kalau tidak,
        # barangnya pindah rumah diam-diam dan kolom gudang pada BARANG
        # berhenti berarti.
        if _sku_katalog[sku][7] not in isi:
            raise RuntimeError(
                f"SEBARAN {sku} tidak menyebut gudang asalnya pada BARANG")

    isi_per_sku = {sku: isi for sku, isi, _ in SEBARAN}
    for sku, asal, tujuan, *_ in DOKUMEN_TRANSFER:
        if sku not in isi_per_sku:
            raise RuntimeError(
                f"DOKUMEN_TRANSFER {sku} bukan barang yang tersebar di dua "
                f"gudang; dokumennya akan menuju gudang yang tidak menyimpannya")
        if asal == tujuan or not {asal, tujuan} <= set(isi_per_sku[sku]):
            raise RuntimeError(
                f"DOKUMEN_TRANSFER {sku}: gudang asal/tujuan tidak cocok "
                f"dengan sebaran barangnya")


_periksa_sebaran()


def _galat(pesan: str, status: int = 422) -> AppError:
    return AppError(status, "DEMO", pesan)


# ==========================================================================
# Penjaga
# ==========================================================================

def perusahaan_demo(cur) -> dict:
    """
    Memastikan perusahaan yang sedang aktif memang penyewa demo.

    RLS membuat SELECT di bawah hanya pernah mengembalikan perusahaan yang
    sedang aktif, sehingga tidak ada cara memeriksa -- apalagi mengosongkan --
    perusahaan lain dari sini. Yang tersisa hanya satu pertanyaan: apakah
    perusahaan INI boleh dikosongkan.
    """
    cur.execute("SELECT id, name, slug, is_demo FROM companies")
    baris = cur.fetchone()
    if baris is None:
        raise _galat("Perusahaan tidak ditemukan.", 404)
    if not baris["is_demo"]:
        raise _galat(
            "Perusahaan ini bukan perusahaan demo. Pengisian ulang dan "
            "penghapusan massal hanya berlaku pada perusahaan demo.",
            403,
        )
    return baris


# ==========================================================================
# Mengosongkan
# ==========================================================================

# Urutan MENGIKUT ARAH FOREIGN KEY, dari yang paling bergantung ke yang paling
# dirujuk. purchase_orders harus sebelum stock_receipts karena ia menunjuk
# penerimaan yang lahir darinya (migrasi 023).
URUTAN_HAPUS = [
    "serial_numbers",
    "stock_batches",
    "stock_movements",
    "inventory",
    "purchase_order_items",
    "purchase_orders",
    "stock_receipt_items",
    "stock_receipts",
    "stock_issue_items",
    "stock_issues",
    "stock_transfer_items",
    "stock_transfers",
    "stock_adjustment_items",
    "stock_adjustments",
    "items",
    "categories",
    "units",
    # Sebelum warehouses: barisnya menunjuk gudang lewat foreign key, dan
    # gudang yang masih dirujuk tidak dapat dihapus.
    "warehouse_distances",
    "warehouses",
    "suppliers",
]


def kosongkan(cur) -> dict[str, int]:
    """
    Menghapus SELURUH data perusahaan demo yang sedang aktif.

    Tidak ada klausa WHERE company_id di sini, dan itu disengaja: policy RLS
    sudah membatasi setiap DELETE pada baris milik penyewa yang aktif.
    Menuliskannya lagi hanya membuat satu aturan yang sama hidup di dua tempat,
    dan yang satu bisa ikut salah tanpa ketahuan bila yang lain diubah.
    """
    perusahaan_demo(cur)
    terhapus: dict[str, int] = {}
    for tabel in URUTAN_HAPUS:
        cur.execute(f"DELETE FROM {tabel}")
        if cur.rowcount:
            terhapus[tabel] = cur.rowcount
    return terhapus


# ==========================================================================
# Mengisi
# ==========================================================================

def _faktor_hari(d: date) -> float:
    """
    Pola mingguan. Sabtu setengah hari, Minggu nyaris berhenti.

    Tanpa pola ini seluruh barang akan tampak dipakai rata setiap hari, dan
    halaman prakiraan kehilangan hal paling nyata yang bisa ia tunjukkan kepada
    calon pelanggan: bahwa sistemnya mengenali irama kerja mereka.
    """
    return (1.0, 1.05, 1.0, 1.05, 0.95, 0.55, 0.15)[d.weekday()]


def _permintaan(acak: random.Random, dasar: float, hari: date) -> int:
    """Permintaan satu barang pada satu hari, dibulatkan ke unit utuh."""
    nilai = dasar * _faktor_hari(hari) * acak.uniform(0.6, 1.45)
    # Barang berputaran rendah tidak dipakai setiap hari; membulatkannya ke
    # bawah membuat harinya benar-benar kosong, bukan selalu "satu".
    utuh = int(nilai)
    if acak.random() < (nilai - utuh):
        utuh += 1
    return utuh


def _jadwal_sebaran(mulai: date, hari_ini: date, laju: float,
                    lantai: float) -> dict[date, float]:
    """
    Tanggal kiriman terjadwal satu pasangan, beserta tinggi isi ulangnya.

    Kiriman terakhir berjarak JEDA_SEBARAN hari dari hari ini, sisanya mundur
    tiap SIKLUS_SEBARAN hari. Tinggi tiap kiriman = lantai + perkiraan pemakaian
    sampai peristiwa berikutnya, sehingga saldo menyentuh lantainya tepat ketika
    kiriman berikutnya datang -- dan pada kiriman terakhir, tepat pada hari ini.
    Pola gigi gergaji yang dihasilkannya justru pola gudang sungguhan yang
    dipasok berkala.
    """
    tanggal: list[date] = []
    d = hari_ini - timedelta(days=JEDA_SEBARAN)
    while d > mulai:
        tanggal.append(d)
        d -= timedelta(days=SIKLUS_SEBARAN)
    tanggal.reverse()

    # Peristiwa berikutnya sesudah tiap pengisian; yang terakhir adalah hari
    # ini, dan itulah yang membuat saldo akhir mendarat di lantainya.
    berikut = tanggal + [hari_ini]
    jadwal: dict[date, float] = {}
    for i, awal in enumerate([mulai] + tanggal):
        jadwal[awal] = lantai + LAJU_EFEKTIF * laju * (berikut[i] - awal).days
    return jadwal


def isi(cur, hari: int = HARI_RIWAYAT) -> dict:
    """
    Membangun seluruh isi perusahaan demo: master data dan riwayat `hari` hari.

    RIWAYATNYA DISIMULASIKAN, BUKAN DIKARANG PER TABEL. Saldo berjalan setiap
    pasangan barang/gudang dihitung hari demi hari; penerimaan lahir ketika
    saldo menembus titik pesan, dan pengeluaran dicatat sebesar yang benar-benar
    bisa dilayani. Karena itu isi tabel inventory bukan angka yang ditulis
    terpisah, melainkan hasil akhir dari pergerakan yang tercatat -- persis
    seperti pada data sungguhan. Kalau keduanya ditulis sendiri-sendiri, laporan
    stok dan riwayat pergerakan akan saling bertentangan sejak hari pertama, dan
    itu justru pertanyaan pertama yang diajukan calon pelanggan yang teliti.
    """
    perusahaan_demo(cur)
    acak = random.Random(BENIH)
    hari_ini = datetime.now(APP_TZ).date()
    mulai = hari_ini - timedelta(days=hari)

    # --- master data -----------------------------------------------------
    id_kategori = []
    for nama in KATEGORI:
        cur.execute("INSERT INTO categories (name) VALUES (%s) RETURNING id", (nama,))
        id_kategori.append(cur.fetchone()["id"])

    id_satuan = []
    for nama, kode in SATUAN:
        cur.execute("INSERT INTO units (name, code) VALUES (%s, %s) RETURNING id",
                    (nama, kode))
        id_satuan.append(cur.fetchone()["id"])

    id_gudang = []
    for kode, nama, lokasi, lintang, bujur, tempuh in GUDANG:
        cur.execute(
            "INSERT INTO warehouses (code, name, location, latitude, longitude, "
            "transfer_lead_time_days) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (kode, nama, lokasi, lintang, bujur, tempuh))
        id_gudang.append(cur.fetchone()["id"])

    id_supplier = []
    for kode, nama, tunggu in SUPPLIER:
        cur.execute(
            "INSERT INTO suppliers (code, name, lead_time_days) VALUES (%s, %s, %s) RETURNING id",
            (kode, nama, tunggu))
        id_supplier.append(cur.fetchone()["id"])

    # --- barang ----------------------------------------------------------
    sebaran = {sku: isi_gudang for sku, isi_gudang, _ in SEBARAN}

    barang: list[dict] = []
    for sku, nama, kat, sat, harga, laju, kritis, gud in BARANG:
        # Barang yang tersebar di dua gudang memakai waktu tunggu yang dipatok:
        # seluruh aritmetika skenario pada SEBARAN berdiri di atasnya.
        tunggu = TUNGGU_SEBARAN if sku in sebaran else acak.choice((5, 7, 10, 14))
        # Titik pesan = kebutuhan selama waktu tunggu + cadangan pengaman.
        # Dihitung, bukan diisi angka bulat, supaya panel perhitungan pada
        # halaman Pemesanan Ulang menunjukkan angka yang benar-benar berasal
        # dari laju pemakaian barang itu.
        cadangan = round(laju * 3, 3)
        titik_pesan = round(laju * tunggu + cadangan, 3)
        cur.execute(
            """
            INSERT INTO items
                (sku, name, category_id, unit_id, unit_price, minimum_stock,
                 maximum_stock, reorder_point, criticality, lead_time_days,
                 safety_stock)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (sku, nama, id_kategori[kat], id_satuan[sat], harga,
             cadangan, round(laju * 45, 3), titik_pesan, kritis, tunggu, cadangan),
        )
        barang.append({
            "id": cur.fetchone()["id"], "sku": sku, "harga": harga,
            "laju": laju, "titik_pesan": titik_pesan, "tunggu": tunggu,
            "gudang": gud, "sebaran": sebaran.get(sku),
        })

    # --- sebaran barang ke gudang ---------------------------------------
    # Satu barang hanya di satu gudang; gudangnya tertulis pada katalog, bukan
    # diundi di sini. Sebelumnya gudang pusat menyimpan seluruh katalog dan
    # cabang menyimpan sebagian secara acak, dengan laju pemakaian cabang
    # diskalakan menjadi sepersekian (PORSI_CABANG) -- padahal titik pesan yang
    # tersimpan di items dihitung dari laju PENUH. Akibatnya panel perhitungan
    # di halaman Pemesanan Ulang menyebut angka yang tidak pernah persis cocok
    # dengan pemakaian yang terlihat pada baris cabang. Dengan satu gudang per
    # barang, keduanya kembali menjadi satu angka yang sama.
    #
    # SEJAK 3 SEPTEMBER 2026 ADA PENGECUALIANNYA, dan itu bukan pelonggaran
    # aturan di atas melainkan penerapannya: barang pada SEBARAN memang
    # disimpan di dua gudang, lajunya PENUH di kedua tempat, dan karena itu
    # titik pesan yang tersimpan di items tetap satu angka yang sama-sama benar
    # untuk keduanya. Yang dulu salah bukan "satu barang di dua gudang",
    # melainkan laju cabang yang diskalakan diam-diam.
    pasangan: list[tuple[dict, int, float | None]] = []
    for b in barang:
        if b["sebaran"]:
            pasangan += [(b, id_gudang[g], b["sebaran"][g])
                         for g in sorted(b["sebaran"])]
        else:
            pasangan.append((b, id_gudang[b["gudang"]], None))

    # --- simulasi hari demi hari -----------------------------------------
    saldo: dict[tuple[int, int], float] = {}
    # (tanggal, gudang) -> [(item_id, qty)]
    keluar: dict[tuple[date, int], list[tuple[int, int]]] = {}
    # (tanggal, gudang, supplier) -> [(item_id, qty, harga)]
    masuk: dict[tuple[date, int, int], list[tuple[int, int, int]]] = {}
    # Penerimaan yang sedang dalam perjalanan: tanggal tiba -> daftar
    dalam_perjalanan: dict[date, list[tuple[dict, int]]] = {}
    # Pasangan yang kirimannya sedang di jalan. Himpunan, bukan penelusuran
    # ulang seluruh isi dalam_perjalanan pada setiap barang setiap hari --
    # yang terakhir itu berarti puluhan ribu perbandingan untuk menjawab
    # pertanyaan yang bisa dijawab sekali lihat.
    menunggu: set[tuple[int, int]] = set()
    # Pasangan yang dipasok menurut jadwal, bukan menurut pemesanan otomatis:
    # (barang, gudang) -> {tanggal kiriman: tinggi isi ulang}
    jadwal: dict[tuple[int, int], dict[date, float]] = {}

    for b, gid, lantai in pasangan:
        # FASE AWAL DIACAK, DAN INI YANG MENENTUKAN TAMPILAN AKHIRNYA.
        #
        # Bila seluruh pasangan dimulai dengan jumlah hari kebutuhan yang sama,
        # semuanya menuruni siklusnya serentak dan pada hari terakhir berdiri di
        # posisi yang kurang lebih sama -- entah hampir semuanya penuh, entah
        # hampir semuanya menipis, bergantung panjang riwayat yang kebetulan
        # dipilih. Gudang sungguhan tidak pernah begitu: setiap barang berada di
        # titik yang berbeda pada siklusnya sendiri.
        #
        # Dengan titik awal yang tersebar rata antara titik pesan dan stok
        # penuh, sebaran itu bertahan sampai hari terakhir, dan porsi barang
        # yang menipis menjadi apa yang seharusnya -- kira-kira waktu tunggu
        # dibagi panjang siklus -- bukan akibat kebetulan panjang riwayat.
        if lantai is None:
            penuh = b["laju"] * HARI_STOK_PESANAN
            dasar = b["titik_pesan"]
            awal = max(1, int(dasar + acak.random() * penuh))
        else:
            # Pasangan berjadwal: fasenya tidak diundi sama sekali. Kiriman
            # pertama sudah setinggi yang dituntut jadwalnya, dan yang berikut
            # menyusul pada tanggal yang sudah ditetapkan.
            rencana = _jadwal_sebaran(mulai, hari_ini, b["laju"],
                                      lantai * b["titik_pesan"])
            awal = max(1, int(rencana.pop(mulai)))
            jadwal[(b["id"], gid)] = rencana
        saldo[(b["id"], gid)] = awal
        sup = id_supplier[acak.randrange(len(id_supplier))]
        masuk.setdefault((mulai, gid, sup), []).append((b["id"], awal, b["harga"]))


    tanggal = mulai + timedelta(days=1)
    while tanggal <= hari_ini:
        # Barang yang tiba hari ini
        for b, gid in dalam_perjalanan.pop(tanggal, []):
            jumlah = max(1, int(b["laju"] * HARI_STOK_PESANAN))
            saldo[(b["id"], gid)] += jumlah
            menunggu.discard((b["id"], gid))
            sup = id_supplier[acak.randrange(len(id_supplier))]
            masuk.setdefault((tanggal, gid, sup), []).append(
                (b["id"], jumlah, b["harga"]))

        for b, gid, lantai in pasangan:
            kunci = (b["id"], gid)

            # Kiriman terjadwal, bila hari ini tanggalnya. Dicatat sebagai
            # penerimaan biasa: yang membedakannya dari kiriman lain hanyalah
            # apa yang menentukan tanggal dan jumlahnya.
            tinggi = jadwal.get(kunci, {}).get(tanggal)
            if tinggi is not None:
                tambah = int(tinggi - saldo[kunci] + 0.999)
                if tambah > 0:
                    saldo[kunci] += tambah
                    sup = id_supplier[acak.randrange(len(id_supplier))]
                    masuk.setdefault((tanggal, gid, sup), []).append(
                        (b["id"], tambah, b["harga"]))

            diminta = _permintaan(acak, b["laju"], tanggal)
            dilayani = min(diminta, int(saldo[kunci]))
            if dilayani > 0:
                saldo[kunci] -= dilayani
                keluar.setdefault((tanggal, gid), []).append((b["id"], dilayani))

            # Pemesanan ulang: begitu saldo menembus titik pesan dan belum ada
            # kiriman dalam perjalanan, pesan sekarang -- tiba setelah waktu
            # tunggu supplier.
            ambang = b["titik_pesan"]
            if lantai is not None:
                # Pasokannya sudah diatur jadwal di atas. Membiarkan pemesanan
                # otomatis ikut jalan berarti dua sumber kiriman untuk satu
                # pasangan, dan saldo akhirnya berhenti dapat diramalkan --
                # yaitu tepat yang hendak dihindari SEBARAN.
                continue
            if saldo[kunci] <= ambang and kunci not in menunggu:
                tiba = tanggal + timedelta(days=b["tunggu"])
                menunggu.add(kunci)
                if tiba <= hari_ini:
                    dalam_perjalanan.setdefault(tiba, []).append((b, gid))
                # Pesanan yang baru tiba SETELAH hari terakhir sengaja tidak
                # dicatat sebagai penerimaan: pada hari demo dijalankan, barang
                # itu memang belum sampai. Barangnya tetap ditandai sedang
                # dipesan supaya tidak dipesan berulang setiap hari -- dan
                # justru itulah yang membuat halaman Pemesanan Ulang punya
                # barang yang benar-benar sedang menunggu kiriman.

        tanggal += timedelta(days=1)

    # --- tulis penerimaan -------------------------------------------------
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
            (nomor, sup, gid, stempel, f"DEMO-{tgl:%Y%m%d}", "Data demo"),
        )
        rid = cur.fetchone()["id"]
        jumlah_gr += 1
        cur.executemany(
            """
            INSERT INTO stock_receipt_items
                (stock_receipt_id, item_id, quantity, unit_price, received_date)
            VALUES (%s, %s, %s, %s, %s)
            """,
            [(rid, iid, qty, harga, tgl) for iid, qty, harga in baris],
        )
        cur.executemany(
            """
            INSERT INTO stock_movements
                (item_id, warehouse_id, movement_type, reference_id,
                 movement_date, quantity, unit_price)
            VALUES (%s, %s, 'stock_in', %s, %s, %s, %s)
            """,
            [(iid, gid, rid, stempel, qty, harga) for iid, qty, harga in baris],
        )

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
            (nomor, gid, stempel, "Pemakaian produksi",
             f"DEMO-{tgl:%Y%m%d}", "Data demo"),
        )
        iid_doc = cur.fetchone()["id"]
        jumlah_iss += 1
        cur.executemany(
            "INSERT INTO stock_issue_items (stock_issue_id, item_id, quantity) VALUES (%s, %s, %s)",
            [(iid_doc, iid, qty) for iid, qty in baris],
        )
        cur.executemany(
            """
            INSERT INTO stock_movements
                (item_id, warehouse_id, movement_type, reference_id,
                 movement_date, quantity)
            VALUES (%s, %s, 'stock_out', %s, %s, %s)
            """,
            [(iid, gid, iid_doc, stempel, -qty) for iid, qty in baris],
        )

    # --- saldo akhir ------------------------------------------------------
    # Dihitung ulang DARI pergerakan, bukan dari variabel simulasi. Kalau
    # keduanya berbeda, yang salah adalah penulisan pergerakannya -- dan
    # perbedaan itu akan langsung terlihat sebagai laporan stok yang tidak
    # cocok dengan riwayatnya, tepat seperti pada sistem sungguhan.
    cur.execute(
        """
        INSERT INTO inventory (item_id, warehouse_id, quantity,
                               reserved_quantity, available_quantity)
        SELECT item_id, warehouse_id, SUM(quantity), 0, SUM(quantity)
          FROM stock_movements
         GROUP BY item_id, warehouse_id
        """
    )
    cur.execute("SELECT count(*) AS n FROM inventory")
    baris_stok = cur.fetchone()["n"]

    # --- transfer antar gudang -------------------------------------------
    # Sesudah persediaan berdiri, bukan sebelumnya: dokumen yang disetujui
    # mencadangkan stok dan yang dikirim menguranginya, dan keduanya menyentuh
    # baris inventory yang baru saja dihitung dari pergerakan di atas.
    _jarak_gudang(cur, id_gudang)
    dokumen_trf = _dokumen_transfer(cur, barang=barang, id_gudang=id_gudang,
                                    hari_ini=hari_ini)

    # --- Surabaya diganti komponen berumur pakai --------------------------
    # Atas permintaan pengguna 28 September 2026: WH-SBY demo berisi sepuluh
    # komponen (Gear Pump, Bearing, Oli Hidrolik, Centrifugal Pump) dengan
    # riwayat yang diturunkan dari lama pemakaian, bukan barang harian di atas.
    # Dikerjakan SESUDAH katalog bawaan supaya Jakarta dan sisa katalog tetap
    # apa adanya; logikanya di tools/histori_umur_pakai.py. Tanpa langkah ini
    # tombol Isi Ulang mengembalikan Surabaya ke isi lamanya.
    from tools import histori_umur_pakai
    umur = histori_umur_pakai.terapkan_pada_demo(cur)

    return {
        "hari_riwayat": hari,
        "barang": len(barang),
        "gudang": len(id_gudang),
        "supplier": len(id_supplier),
        "penerimaan": jumlah_gr,
        "pengeluaran": jumlah_iss,
        "baris_stok": baris_stok,
        "barang_dua_gudang": len(SEBARAN),
        "transfer": len(dokumen_trf),
        "surabaya_umur_pakai": umur,
    }


# ==========================================================================
# Transfer antar gudang
# ==========================================================================

def _jarak_gudang(cur, id_gudang: list[int]) -> None:
    """Jarak jalan darat antar gudang, yang mengalahkan haversine."""
    for asal, tujuan, km, tempuh, catatan in JARAK_GUDANG:
        cur.execute(
            """
            INSERT INTO warehouse_distances
                (from_warehouse_id, to_warehouse_id, distance_km,
                 lead_time_days, notes)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (id_gudang[asal], id_gudang[tujuan], km, tempuh, catatan),
        )


def _dokumen_transfer(cur, *, barang: list[dict], id_gudang: list[int],
                      hari_ini: date) -> list[str]:
    """
    Dokumen transfer yang sudah berjalan, satu untuk tiap tahap.

    TAHAPNYA DILEWATI SATU PER SATU, tidak ditulis langsung sebagai "sudah
    diterima". Yang menggerakkan stok adalah perpindahan status, bukan status
    itu sendiri (routers/transfer.terapkan_status), jadi dokumen yang disisipkan
    langsung dalam keadaan akhir akan menyatakan barang sudah sampai sementara
    gudang asalnya tidak pernah kehilangan satu unit pun -- selisih yang tidak
    pernah terbit sebagai galat, hanya sebagai stok yang tidak cocok saat
    opname. Melewati tahapnya juga yang membuat cap waktu tiap tahap terisi,
    dan itulah yang dibaca layar.

    Impornya di dalam fungsi, bukan di kepala berkas: modul ini dipakai perintah
    baris perintah `python -m app.jobs.buat_demo`, dan routers/transfer.py
    menarik seluruh rantai prakiraan beserta pustaka modelnya.
    """
    from .routers.transfer import terapkan_status

    per_sku = {b["sku"]: b for b in barang}
    jarak = {(a, t): km for a, t, km, _, _ in JARAK_GUDANG}
    nomor_terbit: list[str] = []

    cur.execute("SELECT id, name FROM warehouses")
    nama_gudang = {r["id"]: r["name"] for r in cur.fetchall()}

    for sku, asal, tujuan, kelipatan, akhir, lalu, skor, alasan in DOKUMEN_TRANSFER:
        b = per_sku[sku]
        gid_asal, gid_tujuan = id_gudang[asal], id_gudang[tujuan]
        qty = max(1, int(b["titik_pesan"] * kelipatan))
        tanggal = hari_ini - timedelta(days=lalu)
        stempel = datetime.combine(tanggal, datetime.min.time())

        nomor = next_document_number(
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
            (nomor, gid_asal, gid_tujuan, stempel, "Data demo", skor, alasan,
             jarak.get((asal, tujuan))),
        )
        transfer_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO stock_transfer_items
                (stock_transfer_id, item_id, quantity, for_item_id, match_type)
            VALUES (%s, %s, %s, %s, 'sku')
            """,
            (transfer_id, b["id"], qty, b["id"]),
        )

        header = {"from_warehouse_id": gid_asal, "to_warehouse_id": gid_tujuan,
                  "from_warehouse_name": nama_gudang.get(gid_asal, "")}
        baris = [{"item_id": b["id"], "quantity": Decimal(qty), "sku": sku}]

        dari = _RANTAI_STATUS[0]
        for langkah, ke in enumerate(
                _RANTAI_STATUS[1:_RANTAI_STATUS.index(akhir) + 1], start=0):
            # Tiap tahap sehari sesudah tahap sebelumnya, dan tidak pernah
            # melewati hari ini: dokumen yang cap kirimnya besok tidak dapat
            # dijelaskan kepada siapa pun.
            waktu = datetime.combine(
                min(hari_ini, tanggal + timedelta(days=langkah)),
                datetime.min.time())
            terapkan_status(cur, transfer_id=transfer_id, dari=dari, ke=ke,
                            header=header, baris=baris, stempel=waktu)
            dari = ke

        nomor_terbit.append(nomor)

    return nomor_terbit
