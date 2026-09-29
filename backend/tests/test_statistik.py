# -*- coding: utf-8 -*-
"""
Uji titik pesan dari statistik biasa (app/statistik.py) dan sambungannya ke
rantai ROP (app/rop.py).

    .venv/bin/python -m pytest backend/tests/test_statistik.py -q

Tanpa basis data: keduanya fungsi murni atas deret angka.

YANG DIJAGA DI SINI ADA DUA, dan yang kedua lebih mudah rusak. Pertama,
rumusnya sendiri: ROP = rata-rata x masa tunggu + Z x simpangan x akar(masa
tunggu).
Kedua, bahwa jalur ini benar-benar TERLEPAS dari adu model -- safety stock yang
diam-diam kembali membaca RMSE backtest akan tetap menghasilkan angka yang
masuk akal pada setiap pengujian tunggal, dan baru ketahuan pada riwayat pendek,
tempat backtest menyerah dan cadangannya berbunyi nol. Karena itu beberapa uji
di bawah memakai riwayat di bawah MIN_RIWAYAT_ADU dengan sengaja.
"""

import sys
from datetime import date
from math import sqrt
from pathlib import Path
from statistics import stdev

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import rop, statistik  # noqa: E402
from app.ml import klasik  # noqa: E402

SENIN = date(2026, 8, 31)
LEAD = 14.0
Z_STANDAR = 1.28


def _riwayat_intermiten(n: int = 90, tiap: int = 5, ukuran: float = 10.0):
    return [ukuran if i % tiap == 0 else 0.0 for i in range(n)]


def _hitung(model=klasik.KUNCI_STATISTIK, strategi="standar", lead=LEAD,
            riwayat=None):
    return rop.hitung_rop(
        riwayat=riwayat if riwayat is not None else _riwayat_intermiten(),
        lead_time_days=lead, model=model, strategi=strategi, as_of=SENIN)


# ==========================================================================
# Rata-rata dan simpangan
# ==========================================================================

def test_rata_rata_adalah_rata_rata_biasa():
    assert statistik.permintaan_harian([2.0, 4.0, 6.0]) == 4.0


def test_hari_nol_ikut_menurunkan_laju():
    """
    Hari tanpa pengeluaran adalah hari dengan permintaan nol, bukan hari yang
    hilang. Membuangnya akan menyatakan barang terpakai setiap hari, dan laju
    yang ditinggikan begitu merambat ke titik pesan lewat perkalian masa
    tunggu.
    """
    assert statistik.permintaan_harian([10.0, 0.0, 0.0, 0.0]) == 2.5


def test_riwayat_kosong_belum_punya_jawaban():
    """None, bukan nol: 'belum diketahui' dan 'memang tidak terpakai' adalah
    dua keadaan berbeda, dan hanya yang kedua boleh menghasilkan titik pesan
    nol."""
    assert statistik.permintaan_harian([]) is None
    assert statistik.simpangan_harian([]) is None


def test_satu_hari_tidak_punya_sebaran():
    """
    Cadangan nol adalah pernyataan bahwa permintaan pasti. Riwayat satu hari
    tidak pernah menjadi dasar pernyataan seperti itu, jadi yang keluar None.
    """
    assert statistik.permintaan_harian([5.0]) == 5.0
    assert statistik.simpangan_harian([5.0]) is None


def test_simpangan_memakai_pembagi_sampel():
    """
    n-1, bukan n. Riwayat yang ada adalah contoh dari pemakaian yang mungkin
    terjadi, bukan seluruhnya -- dan pada riwayat pendek, meremehkan
    ketidakpastian adalah arah yang paling berbahaya bagi keputusan pembelian.
    """
    deret = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    assert statistik.simpangan_harian(deret) == pytest.approx(stdev(deret))
    # Pembagi populasi akan menghasilkan 2,0 pada deret ini; sampel 2,138.
    assert statistik.simpangan_harian(deret) > 2.0


def test_pemakaian_yang_mantap_tidak_menuntut_cadangan():
    """Permintaan yang sama persis tiap hari tidak punya sebaran, dan cadangan
    yang tetap tebal di atasnya hanya menahan modal tanpa menutup risiko apa
    pun."""
    assert statistik.simpangan_harian([4.0] * 30) == 0.0


def test_deret_yang_lebih_liar_menuntut_cadangan_lebih_tebal():
    tenang = statistik.simpangan_harian([4.0, 5.0, 4.0, 5.0, 4.0, 5.0])
    liar = statistik.simpangan_harian([0.0, 9.0, 0.0, 9.0, 0.0, 9.0])
    assert tenang < liar


# ==========================================================================
# Rumusnya
# ==========================================================================

def test_rop_persis_permintaan_kali_lead_ditambah_cadangan():
    """Rumus yang diminta, dieja apa adanya."""
    deret = [2.0, 4.0, 6.0, 8.0]
    h = statistik.hitung(riwayat=deret, lead_time_days=10.0, z=Z_STANDAR)
    assert h["permintaan_harian"] == 5.0
    assert h["simpangan_harian"] == pytest.approx(stdev(deret))
    assert h["safety_stock"] == pytest.approx(
        Z_STANDAR * stdev(deret) * sqrt(10.0))
    assert h["reorder_point"] == pytest.approx(5.0 * 10.0 + h["safety_stock"])


def test_cadangan_tumbuh_menurut_akar_lead_time():
    """
    SS = Z x sebaran x akar(masa tunggu). Masa tunggu empat kali lipat berarti
    cadangan DUA kali lipat, bukan empat -- karena hari yang meleset ke atas
    sebagian ditutup hari yang meleset ke bawah, dan peredaman itulah yang
    membuat simpangan total tumbuh menurut akar waktu.

    Kelipatan empat dipakai dengan sengaja: pada kelipatan itu jawaban konvensi
    akar (2x) dan konvensi linear (4x) berjauhan, sehingga kembalinya bentuk
    lama mustahil lolos sebagai selisih pembulatan.
    """
    deret = _riwayat_intermiten()
    a = statistik.hitung(riwayat=deret, lead_time_days=5.0, z=Z_STANDAR)
    b = statistik.hitung(riwayat=deret, lead_time_days=20.0, z=Z_STANDAR)
    assert b["safety_stock"] == pytest.approx(2 * a["safety_stock"])


def test_lead_time_nol_meniadakan_seluruhnya():
    """Pemasok yang mengirim di hari yang sama tidak menuntut apa pun ada di
    rak saat pesanan dibuat."""
    h = statistik.hitung(riwayat=_riwayat_intermiten(), lead_time_days=0.0,
                         z=Z_STANDAR)
    assert h["safety_stock"] == 0.0
    assert h["reorder_point"] == 0.0


def test_lead_time_negatif_dijepit_bukan_dibalik():
    """Masa tunggu negatif adalah data rusak; membiarkannya menghasilkan titik
    pesan negatif, yang diam-diam berarti 'tidak perlu memesan, selamanya'."""
    h = statistik.hitung(riwayat=_riwayat_intermiten(), lead_time_days=-5.0,
                         z=Z_STANDAR)
    assert h["reorder_point"] == 0.0


def test_sebaran_tak_diketahui_tidak_menjadi_cadangan_nol():
    """
    None diteruskan sebagai None pada `safety_stock`, sementara ROP tetap
    terbit dari permintaan kali masa tunggu. Halamannya tidak kosong, dan
    pembacanya tetap tahu persis bahwa yang hilang adalah cadangannya -- bukan
    disuguhi nol yang tampak seperti hasil hitungan.
    """
    h = statistik.hitung(riwayat=[6.0], lead_time_days=10.0, z=Z_STANDAR)
    assert h["safety_stock"] is None
    assert h["reorder_point"] == 60.0


def test_z_hanya_menggerakkan_cadangan_bukan_permintaan():
    """Tingkat layanan adalah keputusan RISIKO. Kalau ia ikut menggeser
    permintaan, berarti Z bocor ke sisi yang salah."""
    deret = _riwayat_intermiten()
    hemat = statistik.hitung(riwayat=deret, lead_time_days=LEAD, z=0.84)
    aman = statistik.hitung(riwayat=deret, lead_time_days=LEAD, z=2.05)
    assert hemat["permintaan_harian"] == aman["permintaan_harian"]
    assert hemat["safety_stock"] < aman["safety_stock"]


# ==========================================================================
# Sambungannya ke rantai ROP
# ==========================================================================

def test_permintaan_harian_adalah_rata_rata_riwayat():
    """
    Model "statistik" meramal datar, jadi permintaan harian pada jawaban ROP
    harus sama persis dengan rata-rata riwayatnya -- bukan sekadar mendekati.
    Selisih di sini berarti ada pemulusan yang menyelinap masuk.
    """
    deret = _riwayat_intermiten()
    h = _hitung(riwayat=deret)
    assert h["predicted_daily_demand"] == pytest.approx(
        statistik.permintaan_harian(deret), abs=0.001)


def test_dasarnya_disebut_dan_bukan_galat_model():
    """
    Ruas yang membuat `model_rmse` dapat dibaca. Tanpa `safety_stock_basis`,
    angka yang sama dapat berarti dua hal dan pembacanya harus menebak dari
    nama model -- tebakan yang pasti keliru pada mode "terbaik".
    """
    h = _hitung()
    assert h["safety_stock_basis"] == "demand_stdev"
    assert h["model_rmse"] == pytest.approx(
        statistik.simpangan_harian(_riwayat_intermiten()), abs=0.001)


def test_model_lain_tetap_memakai_galat_backtest():
    """Jalur lama tidak boleh ikut berpindah: model yang diadu tetap membayar
    cadangannya dengan galatnya sendiri."""
    h = _hitung(model="croston_sba")
    assert h["safety_stock_basis"] == "model_rmse"
    assert h["model_rmse"] != pytest.approx(
        statistik.simpangan_harian(_riwayat_intermiten()), abs=0.001)


def test_cadangan_tetap_terbit_pada_riwayat_yang_terlalu_pendek_untuk_diadu():
    """
    INTI SELURUH PERUBAHAN INI. Di bawah MIN_RIWAYAT_ADU tidak ada model yang
    boleh diadu, sehingga jalur model kehilangan galatnya dan cadangannya jatuh
    ke nol -- barang baru justru berangkat tanpa penyangga sama sekali.
    Simpangan baku hanya menuntut dua hari, jadi jalur statistik tetap
    menjawab.
    """
    pendek = [4.0, 0.0, 9.0, 2.0, 0.0, 7.0, 3.0, 1.0, 0.0, 5.0]
    assert len(pendek) < klasik.MIN_RIWAYAT_ADU

    stat = _hitung(riwayat=pendek)
    model = _hitung(model="croston_sba", riwayat=pendek)

    assert stat["model_rmse"] is not None
    assert stat["calculated_safety_stock"] > 0
    assert model["model_rmse"] is None
    assert model["calculated_safety_stock"] == 0


def test_permintaan_yang_mantap_menghasilkan_cadangan_nol_bukan_karangan():
    """
    Sebaran nol adalah jawaban yang sah, bukan kegagalan: permintaan 4 unit
    tiap hari selama sebulan memang tidak menuntut penyangga apa pun. Titik
    pesannya tetap terbit dari permintaan kali masa tunggu.
    """
    h = _hitung(riwayat=[4.0] * 30)
    assert h["calculated_safety_stock"] == 0
    assert h["final_reorder_point"] == pytest.approx(4.0 * LEAD, abs=0.01)


def test_strategi_menebalkan_cadangan_pada_jalur_statistik_juga():
    hemat = _hitung(strategi="hemat")
    standar = _hitung(strategi="standar")
    aman = _hitung(strategi="aman")
    assert (hemat["calculated_safety_stock"]
            < standar["calculated_safety_stock"]
            < aman["calculated_safety_stock"])
    # Sebarannya sendiri tidak boleh ikut bergerak: ia sifat barangnya, bukan
    # sifat keberanian pembelinya.
    assert hemat["model_rmse"] == aman["model_rmse"]


def test_rop_pada_jalur_statistik_menyusun_ulang_rumusnya():
    h = _hitung(strategi="aman")
    harap = h["predicted_daily_demand"] * LEAD + h["calculated_safety_stock"]
    assert abs(h["final_reorder_point"] - harap) < 0.01, h


def test_statistik_ikut_daftar_model_yang_dapat_dipilih():
    """Terdaftar sebagai model penuh, bukan cabang khusus di router: itulah
    yang membuatnya muncul di dropdown dan ikut papan adu tanpa satu baris pun
    ditambahkan di layar."""
    assert klasik.KUNCI_STATISTIK in klasik.semua_kunci()
    assert klasik.KUNCI_STATISTIK in klasik.KLASIK
