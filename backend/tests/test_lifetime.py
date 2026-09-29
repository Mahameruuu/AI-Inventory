# -*- coding: utf-8 -*-
"""
Uji perhitungan Analisis Umur Pakai (app/lifetime.py).

Seluruhnya tanpa basis data: modul yang diuji memang tidak menyentuhnya. Yang
dijaga di sini adalah hal-hal yang tidak akan menimbulkan galat bila salah --
konversi satuan yang tertukar, pita batas yang bergeser, kategori yang
terbalik -- dan karena itu hanya terlihat sebagai angka yang keliru di layar.
"""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import lifetime as lt  # noqa: E402
from app.config import LIFETIME_TOLERANSI, OPERATING_HOURS_PER_DAY  # noqa: E402


# ---------------------------------------------------------------- konversi

def test_satuan_jam_dibagi_jam_operasi():
    # 1.250 jam pada 16 jam/hari = 78,125 hari. Inilah angka yang membuat
    # Filter Oli terlihat wajar; membaginya dengan 24 akan membuat setiap
    # filter tampak berumur 50% lebih panjang daripada spesifikasinya.
    assert lt.umur_harapan_hari(1250, "jam") == pytest.approx(
        1250 / OPERATING_HOURS_PER_DAY)


def test_satuan_tahun_tidak_ikut_dikalikan_jam_operasi():
    """
    Kesalahan yang paling mudah terjadi di modul ini: memperlakukan "20 tahun"
    sebagai 20 tahun JAM JALAN. Hasilnya bukan sedikit meleset melainkan
    meleset satu setengah kali lipat, dan pompa yang wajar akan terbaca
    sebagai penggantian dini seumur hidup sistem ini.
    """
    assert lt.umur_harapan_hari(20, "tahun") == 20 * 365.0
    assert lt.umur_harapan_hari(20, "tahun") != lt.umur_harapan_hari(20 * 8760, "jam")


@pytest.mark.parametrize("nilai,satuan", [
    (None, None), (None, "jam"), (12500, None),
    (0, "jam"), (-5, "tahun"), (10, "bulan"),
])
def test_umur_harapan_tanpa_referensi_sah_bernilai_none(nilai, satuan):
    assert lt.umur_harapan_hari(nilai, satuan) is None


# -------------------------------------------------------------- pita batas

def test_pita_mengapit_umur_harapan():
    bawah, atas = lt.batas(100.0)
    assert bawah == pytest.approx(100 * (1 - LIFETIME_TOLERANSI))
    assert atas == pytest.approx(100 * (1 + LIFETIME_TOLERANSI))
    assert bawah < 100 < atas


def test_tanpa_referensi_pita_tidak_ada():
    assert lt.batas(None) == (None, None)


# ---------------------------------------------------------------- kategori

def test_contoh_gear_pump_dari_spesifikasi():
    """
    Contoh yang dipakai saat modul ini diminta: umur harapan 3 tahun, aktual
    2,1 tahun, deviasi -30%, status penggantian dini.
    """
    harapan = 3 * 365.0
    aktual = 2.1 * 365.0
    assert lt.deviasi_persen(aktual, harapan) == pytest.approx(-30.0)
    assert lt.kategori(aktual, harapan) == lt.PREMATURE


def test_kategori_di_dalam_pita_adalah_wajar():
    assert lt.kategori(100.0, 100.0) == lt.NORMAL
    assert lt.kategori(90.0, 100.0) == lt.NORMAL      # -10%, di dalam ±15%
    assert lt.kategori(110.0, 100.0) == lt.NORMAL     # +10%


def test_kategori_di_luar_pita():
    assert lt.kategori(80.0, 100.0) == lt.PREMATURE   # -20%
    assert lt.kategori(125.0, 100.0) == lt.EXTENDED   # +25%


def test_tepi_pita_masih_wajar():
    """
    Tepat di batas bukan pelanggaran batas. Bila tepi ikut terhitung
    menyimpang, satu barang yang persis sesuai toleransinya akan berpindah
    kategori karena pembulatan di tempat lain.
    """
    bawah, atas = lt.batas(100.0)
    assert lt.kategori(bawah, 100.0) == lt.NORMAL
    assert lt.kategori(atas, 100.0) == lt.NORMAL


def test_tanpa_umur_terukur_bukan_wajar_melainkan_belum_cukup():
    """
    Perbedaan yang menentukan: barang yang belum dapat diukur TIDAK boleh
    menambah hitungan "wajar". Kartu ringkas yang menghitungnya sebagai wajar
    akan melaporkan sistem lebih sehat daripada yang sebenarnya diketahui.
    """
    assert lt.kategori(None, 100.0) == lt.INSUFFICIENT
    assert lt.kategori(80.0, None) == lt.INSUFFICIENT
    assert lt.kategori(None, None) == lt.INSUFFICIENT


def test_deviasi_tanpa_pembanding_bernilai_none_bukan_nol():
    # Nol berarti "persis sesuai harapan" -- kebalikan dari "tidak diketahui".
    assert lt.deviasi_persen(None, 100.0) is None
    assert lt.deviasi_persen(80.0, None) is None
    assert lt.deviasi_persen(80.0, 0) is None


# ---------------------------------------------------------------- interval

def test_interval_adalah_jarak_antar_penggantian_berurutan():
    hari = [date(2026, 1, 1), date(2026, 1, 11), date(2026, 2, 1)]
    assert lt.interval_penggantian(hari) == [10, 21]


def test_interval_mengurutkan_lebih_dulu():
    hari = [date(2026, 2, 1), date(2026, 1, 1), date(2026, 1, 11)]
    assert lt.interval_penggantian(hari) == [10, 21]


def test_penggantian_pada_hari_sama_tidak_menjadi_umur_nol():
    """
    Dua baris pada tanggal yang sama adalah satu kejadian yang tercatat dua
    kali, atau dua unit yang diganti bersamaan -- bukan komponen yang bertahan
    nol hari. Meloloskannya akan menyeret median seluruh barang ke bawah dan
    menerbitkan "penggantian dini" yang tidak pernah terjadi.
    """
    hari = [date(2026, 1, 1), date(2026, 1, 1), date(2026, 3, 1)]
    assert lt.interval_penggantian(hari) == [59]


def test_satu_penggantian_tidak_menghasilkan_interval():
    assert lt.interval_penggantian([date(2026, 1, 1)]) == []
    assert lt.umur_aktual([]) is None


def test_umur_aktual_memakai_median_bukan_rata_rata():
    """
    Satu jarak yang melar karena mesin berhenti sebulan tidak boleh menggeser
    kesimpulan seluruh barang.
    """
    interval = [70, 72, 75, 78, 400]
    assert lt.umur_aktual(interval) == 75
    assert lt.umur_aktual(interval) < sum(interval) / len(interval)


# -------------------------------------------------------------------- tren

def test_tren_tidak_disebut_di_atas_deret_pendek():
    """Menamai arah atas dua atau tiga angka berarti menamai kebetulan."""
    assert lt.tren_penggantian([100, 50]) is None
    assert lt.tren_penggantian([100, 90, 50]) is None


def test_jarak_memendek_berarti_frekuensi_naik():
    # Paruh awal ~100 hari, paruh akhir ~60 hari: komponen diganti lebih
    # sering, yang berarti kebutuhan sparepart berpotensi naik.
    assert lt.tren_penggantian([100, 102, 98, 60, 58, 62]) == lt.TREN_NAIK


def test_jarak_memanjang_berarti_frekuensi_turun():
    assert lt.tren_penggantian([60, 58, 62, 100, 102, 98]) == lt.TREN_TURUN


def test_pergeseran_di_dalam_toleransi_bukan_tren():
    assert lt.tren_penggantian([100, 101, 99, 105, 104, 106]) == lt.TREN_STABIL


# ------------------------------------------------------- frekuensi & dampak

def test_frekuensi_per_tahun():
    assert lt.frekuensi_per_tahun(365.0) == pytest.approx(1.0)
    assert lt.frekuensi_per_tahun(78.125) == pytest.approx(4.672, abs=1e-3)
    assert lt.frekuensi_per_tahun(None) is None


def test_dampak_tidak_pernah_menyebut_sebab():
    """
    Batas yang paling penting pada modul ini. Kalimat dampak boleh menyebut
    KEBUTUHAN SPAREPART; ia tidak boleh menyebut kenapa komponennya gagal.
    """
    terlarang = ("karena", "akibat", "disebabkan", "caused", "because", "due to")
    for kategori in (lt.PREMATURE, lt.NORMAL, lt.EXTENDED):
        for tren in (None, lt.TREN_NAIK, lt.TREN_STABIL, lt.TREN_TURUN):
            for lang in ("id", "en"):
                kalimat = lt.kalimat_dampak(kategori, tren, lang)
                assert kalimat
                assert not any(k in kalimat.lower() for k in terlarang), kalimat


def test_dampak_penggantian_dini_menaikkan_kebutuhan():
    assert lt.kalimat_dampak(lt.PREMATURE, None) == lt.i18n.t("lt.impact.higher")
    assert lt.kalimat_dampak(lt.NORMAL, lt.TREN_NAIK) == lt.i18n.t("lt.impact.higher")
    assert lt.kalimat_dampak(lt.EXTENDED, None) == lt.i18n.t("lt.impact.lower")


def test_tanpa_umur_terukur_tidak_ada_kalimat_dampak():
    # Tidak ada yang diketahui, jadi tidak ada yang boleh dikatakan.
    assert lt.kalimat_dampak(lt.INSUFFICIENT, None) is None


# ------------------------------------------------------- faktor pendukung

def test_seluruh_faktor_pendukung_dinyatakan_belum_tersedia():
    """
    Daftar ini ADA justru untuk menyatakan bahwa datanya kosong. Bila kelak
    satu faktor benar-benar masuk, uji ini gagal -- dan itulah yang diinginkan:
    baris `available: True` menuntut jalur yang benar-benar membaca datanya,
    bukan sekadar tanda centang di layar.
    """
    faktor = lt.faktor_pendukung()
    assert {f["key"] for f in faktor} == set(lt.FAKTOR_PENDUKUNG)
    assert all(f["available"] is False for f in faktor)
    assert all(f["label"] for f in faktor)


# ------------------------------------------------------------------- label

@pytest.mark.parametrize("lang", ["id", "en"])
def test_setiap_kategori_punya_label_di_kedua_bahasa(lang):
    for k in lt.KATEGORI:
        label = lt.label_kategori(k, lang)
        assert label and label != f"lt.status.{k}"


@pytest.mark.parametrize("lang", ["id", "en"])
def test_setiap_arah_tren_punya_label(lang):
    for tren in (lt.TREN_NAIK, lt.TREN_STABIL, lt.TREN_TURUN):
        label = lt.label_tren(tren, lang)
        assert label and label != f"lt.trend.{tren}"
    assert lt.label_tren(None, lang) is None


# ------------------------------------------------------------ kalimat dasar

def test_tiga_keadaan_dasar_berbunyi_berbeda():
    """
    "Belum diisi di master" dan "baru diganti sekali" menuntut tindakan yang
    berbeda -- yang pertama dapat diperbaiki hari ini, yang kedua hanya oleh
    waktu. Satu kalimat untuk keduanya menyembunyikan perbedaan itu.
    """
    tanpa = lt.kalimat_dasar(False, 0, 0)
    sekali = lt.kalimat_dasar(True, 1, 0)
    terukur = lt.kalimat_dasar(True, 9, 8)
    assert len({tanpa, sekali, terukur}) == 3
    assert "9" in terukur and "8" in terukur
