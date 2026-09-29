# -*- coding: utf-8 -*-
"""
Analisis Umur Pakai -- perhitungan murni, tanpa basis data.

PERTANYAAN YANG DIJAWAB MODUL INI, dan hanya itu:

    Apakah komponen diganti lebih cepat atau lebih lambat daripada umur pakai
    yang diharapkan?

APA YANG BUKAN LINGKUPNYA. Modul ini TIDAK menyimpulkan SEBAB. Penggantian
yang lebih cepat daripada spesifikasi dapat berasal dari beban, suhu, kualitas
pelumas, jadwal pemeliharaan, atau kontaminasi -- dan basis data ini tidak
menyimpan satu pun di antaranya. Menuliskan "oli telat diganti membuat pompa
rusak" berarti mengarang hubungan yang tidak dapat ditunjukkan oleh data yang
ada. Yang boleh disebut hanyalah SELISIHNYA; sebabnya ditinggalkan terbuka,
dan halaman menyatakan secara terbuka bahwa data faktor pendukung belum ada.

Modul ini juga BUKAN predictive maintenance: ia tidak memprediksi kapan satu
unit akan rusak. Ia mengukur apa yang SUDAH terjadi, lalu menyerahkan
akibatnya pada persediaan -- pola penggantian yang memendek berarti kebutuhan
sparepart naik, dan itu dibaca di halaman Prakiraan serta Pemesanan Ulang yang
sudah ada. Tidak ada satu pun angka di sini yang mengubah keduanya.

DARI MANA UMUR PAKAI AKTUAL DIAMBIL. Basis data ini tidak mencatat pemasangan
maupun pelepasan satu unit; yang tercatat adalah PENGELUARAN barang dari
gudang. Karena itu umur pakai aktual diukur sebagai JARAK ANTAR PENGGANTIAN
untuk satu barang di satu gudang. Ukuran itu benar bila satu titik pemasangan
mengambil satu unit setiap kali komponennya diganti -- persis bentuk riwayat
yang dibangun tools/histori_umur_pakai.py, dan tiap pengeluaran di sana
berjumlah satu unit. Bila kelak satu barang terpasang pada banyak titik,
jaraknya menjadi jarak antar penggantian ARMADA, bukan umur satu unit; karena
itu setiap baris membawa `basis` yang menyebutkan hal ini apa adanya alih-alih
menyembunyikannya di balik satu angka yang terlihat pasti.
"""

from __future__ import annotations

import statistics
from datetime import date

from . import i18n
from .config import LIFETIME_MIN_INTERVAL_TREN, LIFETIME_TOLERANSI, OPERATING_HOURS_PER_DAY

HARI_PER_TAHUN = 365.0

# --- kategori ------------------------------------------------------------
# Tiga kategori, dan hanya tiga. Setiap kategori tambahan menuntut satu ambang
# tambahan, dan ambang yang tidak punya sumber data adalah tebakan yang
# menyamar sebagai aturan bisnis.
PREMATURE = "PREMATURE"
NORMAL = "NORMAL"
EXTENDED = "EXTENDED"
# Bukan kategori umur pakai melainkan pernyataan bahwa umurnya belum dapat
# diukur. Dipisahkan supaya tidak pernah terhitung sebagai "wajar".
INSUFFICIENT = "INSUFFICIENT"

KATEGORI = (PREMATURE, NORMAL, EXTENDED, INSUFFICIENT)

# Arah tren frekuensi penggantian.
TREN_NAIK = "increasing"      # jaraknya memendek -> lebih sering diganti
TREN_STABIL = "stable"
TREN_TURUN = "decreasing"     # jaraknya memanjang -> lebih jarang diganti

SATUAN_SAH = ("jam", "tahun")


def label_kategori(kategori: str, lang: str = i18n.BAHASA_BAWAAN) -> str:
    return i18n.t(f"lt.status.{kategori}", lang)


def label_tren(tren: str | None, lang: str = i18n.BAHASA_BAWAAN) -> str | None:
    return i18n.t(f"lt.trend.{tren}", lang) if tren else None


def umur_harapan_hari(nilai: float | None, satuan: str | None) -> float | None:
    """
    Umur pakai yang diharapkan, dinyatakan dalam hari kalender.

    Migrasi 029 sengaja menyimpan satuannya apa adanya karena mengubah jam
    operasi menjadi hari kalender menuntut satu angka yang tidak dimiliki
    basis data: berapa jam mesin benar-benar beroperasi tiap hari. Angka itu
    kini ada di satu tempat -- config.OPERATING_HOURS_PER_DAY, berasal dari
    keputusan dua shift yang diambil pengguna pada 1 September 2026 -- dan
    dipakai di sini serta oleh tools/histori_umur_pakai.py yang membangun
    riwayatnya. Satu sumber, bukan dua angka yang bisa berselisih.

    'tahun' TIDAK ikut dikalikan jam operasi: dua puluh tahun pada spesifikasi
    pompa berarti dua puluh tahun kalender, bukan dua puluh tahun jam jalan.
    """
    if nilai is None or satuan is None:
        return None
    nilai = float(nilai)
    if nilai <= 0:
        return None
    if satuan == "jam":
        return nilai / OPERATING_HOURS_PER_DAY
    if satuan == "tahun":
        return nilai * HARI_PER_TAHUN
    return None


def batas(harapan_hari: float | None) -> tuple[float | None, float | None]:
    """
    Batas bawah dan batas atas umur pakai, mengapit umur harapan.

    SUMBER ANGKANYA, bukan karangan: riwayat penggantian perusahaan ini
    dibangun dengan ragam +-15% terhadap umur pakai spesifikasi
    (tools/histori_umur_pakai.py, `acak.uniform(0.85, 1.15)`). Itulah lebar
    sebaran yang memang dinyatakan untuk data ini, sehingga itu pula yang
    dipakai memisahkan "masih sesuai spesifikasi" dari "menyimpang".

    Bila kelak SME memberikan batas bawah/atas per komponen, ganti pemanggilan
    fungsi ini dengan kolom masternya -- bentuk keluarannya sudah berupa
    tiga angka (bawah, harapan, atas) supaya penggantian itu tidak menuntut
    perombakan di tempat lain.
    """
    if harapan_hari is None:
        return None, None
    return (harapan_hari * (1 - LIFETIME_TOLERANSI),
            harapan_hari * (1 + LIFETIME_TOLERANSI))


def deviasi_persen(aktual_hari: float | None,
                   harapan_hari: float | None) -> float | None:
    """
    Selisih umur aktual terhadap umur harapan, dalam persen.

        (aktual - harapan) / harapan x 100

    Negatif berarti komponen tidak sampai umurnya; positif berarti melewatinya.
    """
    if aktual_hari is None or not harapan_hari:
        return None
    return (aktual_hari - harapan_hari) / harapan_hari * 100.0


def kategori(aktual_hari: float | None, harapan_hari: float | None) -> str:
    """
    Kategori satu umur pakai terhadap pita batas bawah--batas atas.

    Perbandingannya dilakukan terhadap PITA, bukan terhadap deviasi yang sudah
    dibulatkan: pembulatan pada angka persen membuat baris tepat di tepi pita
    berpindah kategori tergantung berapa desimal yang kebetulan ditampilkan.
    """
    if aktual_hari is None or not harapan_hari:
        return INSUFFICIENT
    bawah, atas = batas(harapan_hari)
    if aktual_hari < bawah:
        return PREMATURE
    if aktual_hari > atas:
        return EXTENDED
    return NORMAL


def interval_penggantian(tanggal: list[date]) -> list[int]:
    """
    Jarak hari antar penggantian berurutan.

    Dua penggantian pada hari yang SAMA menghasilkan jarak nol, dan nol bukan
    umur pakai -- itu satu kejadian yang tercatat dua kali, atau dua unit yang
    diganti bersamaan. Keduanya dibuang di sini alih-alih diloloskan sebagai
    "umur pakai 0 hari" yang akan menenggelamkan seluruh rata-rata.
    """
    urut = sorted(tanggal)
    return [(urut[i + 1] - urut[i]).days
            for i in range(len(urut) - 1)
            if (urut[i + 1] - urut[i]).days > 0]


def umur_aktual(interval: list[int]) -> float | None:
    """
    Umur pakai aktual yang mewakili satu barang: MEDIAN jarak antar
    penggantian.

    Median, bukan rata-rata. Satu penggantian yang dimajukan karena kerusakan
    tidak sengaja -- atau satu jarak yang melar karena mesin berhenti sebulan
    -- menggeser rata-rata cukup jauh untuk memindahkan kategori seluruh
    barang, sedangkan yang ingin dijawab adalah "berapa umur yang LAZIM".
    """
    return statistics.median(interval) if interval else None


def tren_penggantian(interval: list[int]) -> str | None:
    """
    Apakah penggantian menjadi lebih sering, lebih jarang, atau tetap.

    Membandingkan median paruh AWAL dengan median paruh AKHIR dari deret
    jarak. Cara ini sengaja dipilih di atas regresi: ia tidak menuntut asumsi
    bentuk hubungan apa pun, dan tahan terhadap satu jarak yang menyimpang
    jauh -- sifat yang penting justru karena deretnya pendek.

    Mengembalikan None bila jaraknya terlalu sedikit untuk dibandingkan.
    Menyebut "tren" atas dua atau tiga angka berarti menamai kebetulan.

    Ambang perubahannya memakai toleransi yang sama dengan pita umur pakai:
    pergeseran yang masih di dalam sebaran normal komponen bukan tren.
    """
    if len(interval) < LIFETIME_MIN_INTERVAL_TREN:
        return None
    tengah = len(interval) // 2
    awal = statistics.median(interval[:tengah])
    akhir = statistics.median(interval[tengah:])
    if not awal:
        return None
    ubah = (akhir - awal) / awal
    if ubah < -LIFETIME_TOLERANSI:
        return TREN_NAIK       # jaraknya memendek -> frekuensi naik
    if ubah > LIFETIME_TOLERANSI:
        return TREN_TURUN      # jaraknya memanjang -> frekuensi turun
    return TREN_STABIL


def frekuensi_per_tahun(aktual_hari: float | None) -> float | None:
    """
    Berapa kali satu titik pemasangan menuntut penggantian dalam setahun.

    Inilah satu-satunya angka pada modul ini yang berbicara langsung dalam
    bahasa persediaan: ia berbanding lurus dengan berapa banyak unit yang
    harus tersedia setiap tahun. Ia DITAMPILKAN saja -- tidak satu pun jalur
    Prakiraan atau Pemesanan Ulang membacanya, karena aturan bisnis yang
    menghubungkan keduanya belum ada.
    """
    if not aktual_hari:
        return None
    return HARI_PER_TAHUN / aktual_hari


# --- faktor pendukung ----------------------------------------------------
# Yang PERLU ada untuk menerangkan kenapa satu komponen tidak mencapai umurnya.
# Tidak satu pun tersimpan di basis data ini hari ini, dan daftar ini ada
# justru untuk mengatakannya -- halaman yang diam soal ini membuat pembacanya
# menyimpulkan sendiri sebabnya dari satu-satunya angka yang tersedia.
#
# Bila kelak salah satunya masuk, pindahkan kuncinya dari daftar ini ke jalur
# yang benar-benar membaca datanya. Daftar yang kosong seluruhnya berarti
# panel "Faktor pendukung" menyatakan dirinya kosong, bukan menghilang.
FAKTOR_PENDUKUNG = (
    "operating_hours",
    "maintenance_interval",
    "oil_change_interval",
    "temperature",
    "vibration",
    "load",
    "contamination",
)


def faktor_pendukung(lang: str = i18n.BAHASA_BAWAAN) -> list[dict]:
    """Daftar faktor beserta ketersediaan datanya. Semuanya masih kosong."""
    return [{"key": k, "label": i18n.t(f"lt.factor.{k}", lang), "available": False}
            for k in FAKTOR_PENDUKUNG]


# --- ringkasan kalimat ---------------------------------------------------

def kalimat_dasar(punya_referensi: bool, jumlah_penggantian: int,
                  jumlah_interval: int, lang: str = i18n.BAHASA_BAWAAN) -> str:
    """
    Di atas apa angka-angka satu baris berdiri -- ATAU kenapa tidak ada angka.

    Tiga kalimat, karena ada tiga keadaan yang berbeda dan hanya satu di
    antaranya yang dapat diperbaiki hari ini:

      tanpa referensi   umur pakai belum diisi di Master Barang. Dapat
                        diperbaiki sekarang juga, oleh orang yang mengetahuinya.
      baru sekali       referensinya ada, penggantiannya baru satu, sehingga
                        belum ada JARAK yang dapat diukur. Hanya waktu yang
                        memperbaikinya.
      terukur           angkanya berdiri di atas sekian jarak penggantian.

    Menyatukan ketiganya menjadi "belum cukup data" membuat baris yang
    menunggu satu isian master terlihat sama dengan baris yang menunggu
    bertahun-tahun.
    """
    if not punya_referensi:
        return i18n.t("lt.basis.no_reference", lang)
    if jumlah_interval == 0:
        return i18n.t("lt.basis.single", lang, n=jumlah_penggantian)
    return i18n.t("lt.basis", lang, n=jumlah_penggantian,
                  interval=jumlah_interval)


def kalimat_dampak(kategori_: str, tren: str | None,
                   lang: str = i18n.BAHASA_BAWAAN) -> str | None:
    """
    Akibatnya bagi persediaan -- dan HANYA bagi persediaan.

    Kalimatnya sengaja berbunyi "berpotensi", bukan "akan": yang diketahui
    adalah pola yang sudah terjadi, bukan permintaan yang pasti datang. Tidak
    ada satu pun angka pesanan yang lahir dari kalimat ini.
    """
    if kategori_ == INSUFFICIENT:
        return None
    if tren == TREN_NAIK or kategori_ == PREMATURE:
        return i18n.t("lt.impact.higher", lang)
    if tren == TREN_TURUN or kategori_ == EXTENDED:
        return i18n.t("lt.impact.lower", lang)
    return i18n.t("lt.impact.stable", lang)
