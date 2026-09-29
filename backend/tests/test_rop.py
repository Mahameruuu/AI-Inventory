# -*- coding: utf-8 -*-
"""
Uji rantai ROP: model -> galat -> safety stock -> titik pesan.

    .venv/bin/python -m pytest backend/tests/test_rop.py -q

Tanpa basis data: app/rop.py adalah fungsi murni atas deret angka.

Yang dijaga di sini adalah RANTAINYA, bukan rumusnya saja. Rumus yang benar
tetapi tidak tersambung -- safety stock yang memakai galat rata-rata seluruh
model alih-alih galat model yang dipilih -- akan menghasilkan angka yang
masuk akal pada setiap pengujian tunggal, dan diam-diam membuat pilihan model
tidak berpengaruh apa-apa pada cadangan. Karena itu sebagian besar tes di
bawah membandingkan DUA pemanggilan, bukan memeriksa satu angka.
"""

import sys
from datetime import date
from math import sqrt
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import rop  # noqa: E402
from app.ml import klasik  # noqa: E402

SENIN = date(2026, 8, 31)
LEAD = 14.0

RUAS_WAJIB = {
    "selected_forecast_model", "predicted_daily_demand", "model_rmse",
    "safety_stock_basis", "selected_strategy", "calculated_safety_stock",
    "final_reorder_point",
}


def _riwayat_intermiten(n: int = 90, tiap: int = 5, ukuran: float = 10.0):
    return [ukuran if i % tiap == 0 else 0.0 for i in range(n)]


def _hitung(model="croston_sba", strategi="standar", lead=LEAD, riwayat=None):
    return rop.hitung_rop(
        riwayat=riwayat if riwayat is not None else _riwayat_intermiten(),
        lead_time_days=lead, model=model, strategi=strategi, as_of=SENIN)


# ==========================================================================
# Bentuk jawaban
# ==========================================================================

def test_jawaban_memuat_tepat_ruas_yang_diminta():
    """
    Kontrak keluarannya ringkas dan disebut namanya satu per satu. Ruas
    tambahan yang menyelinap masuk akan terbawa ke pemakai di luar dan sulit
    dicabut kemudian.

    `safety_stock_basis` ditambahkan dengan sadar, bukan menyelinap: sejak
    model "statistik" ada, `model_rmse` dapat berisi dua besaran yang berbeda
    artinya -- galat backtest model, atau simpangan baku permintaan harian.
    Menerbitkan angkanya tanpa menyebut dasarnya berarti pembacanya harus
    menebak dari nama model, dan tebakan itu akan keliru pada mode "terbaik"
    yang memilihkan modelnya sendiri.
    """
    assert set(_hitung()) == RUAS_WAJIB


@pytest.mark.parametrize("kunci", list(klasik.KLASIK))
def test_setiap_model_klasik_dapat_dipakai(kunci):
    h = _hitung(model=kunci)
    assert h["selected_forecast_model"] == kunci
    assert h["predicted_daily_demand"] >= 0
    assert h["model_rmse"] is not None and h["model_rmse"] >= 0


# ==========================================================================
# Strategi
# ==========================================================================

def test_z_score_sesuai_tingkat_layanan():
    assert rop.STRATEGI["aman"].z == 2.05
    assert rop.STRATEGI["standar"].z == 1.28
    assert rop.STRATEGI["hemat"].z == 0.84
    assert rop.STRATEGI["aman"].service_level == 0.98
    assert rop.STRATEGI["standar"].service_level == 0.90
    assert rop.STRATEGI["hemat"].service_level == 0.80


def test_strategi_tak_dikenal_jatuh_ke_standar():
    """
    Dikembalikan ke Standar, bukan ditolak dengan galat: yang mengirim nilai
    asing hampir selalu tautan lama, dan menjatuhkan permintaan karena satu
    parameter tampilan adalah hukuman yang tidak sebanding.
    """
    assert _hitung(strategi="ngawur")["selected_strategy"] == "standar"
    assert _hitung(strategi=None)["selected_strategy"] == "standar"


def test_makin_aman_makin_tebal_cadangannya():
    hemat = _hitung(strategi="hemat")
    standar = _hitung(strategi="standar")
    aman = _hitung(strategi="aman")
    assert (hemat["calculated_safety_stock"]
            < standar["calculated_safety_stock"]
            < aman["calculated_safety_stock"])
    assert (hemat["final_reorder_point"]
            < standar["final_reorder_point"]
            < aman["final_reorder_point"])


def test_strategi_hanya_menggerakkan_cadangan_bukan_permintaan():
    """
    Tingkat layanan adalah keputusan RISIKO, bukan ramalan. Ia tidak boleh
    mengubah berapa banyak barang diperkirakan terpakai; kalau ia ikut
    bergerak, berarti Z bocor ke sisi permintaan.
    """
    a, b = _hitung(strategi="hemat"), _hitung(strategi="aman")
    assert a["predicted_daily_demand"] == b["predicted_daily_demand"]
    assert a["model_rmse"] == b["model_rmse"]


# ==========================================================================
# Rumus
# ==========================================================================

def test_safety_stock_persis_z_kali_akar_lead_kali_rmse():
    """
    Toleransinya diturunkan dari pembulatan, bukan dikira-kira. `model_rmse`
    diterbitkan dengan tiga desimal sedangkan cadangannya dihitung dari RMSE
    presisi penuh, jadi menyusun ulang rumus dari angka yang sudah dibulatkan
    meleset paling banyak Z x akar(lead) x 0,0005. Menuliskan toleransi sebagai
    angka bulat "0,01" akan membuat tes ini pecah begitu lead time diperbesar,
    karena batasnya ikut tumbuh.
    """
    h = _hitung(strategi="aman")
    harap = 2.05 * sqrt(LEAD) * h["model_rmse"]
    toleransi = 2.05 * sqrt(LEAD) * 0.0005 + 0.001
    assert abs(h["calculated_safety_stock"] - harap) < toleransi, h


def test_rop_persis_permintaan_kali_lead_ditambah_cadangan():
    h = _hitung()
    harap = h["predicted_daily_demand"] * LEAD + h["calculated_safety_stock"]
    assert abs(h["final_reorder_point"] - harap) < 0.01, h


def test_cadangan_tumbuh_menurut_akar_lead_time():
    """
    Konsekuensi langsung dari konvensi akar: SS = Z x RMSE x akar(lead). Lead
    time dua kali lipat berarti cadangan naik akar dua kali, BUKAN dua kali.

    Yang dijaga di sini justru bentuk pertumbuhannya, bukan sekadar angkanya.
    Kembali ke bentuk linear akan tetap menghasilkan cadangan yang tampak wajar
    pada satu lead time mana pun -- dan baru terlihat keliru pada barang
    berlead time panjang, tempat selisihnya sudah berlipat-lipat.

    Toleransinya diturunkan dari pembulatan, sama seperti tes di atas: kedua
    cadangan diterbitkan dengan tiga desimal, jadi menyusun ulang perbandingan
    dari angka yang sudah dibulatkan meleset paling banyak (1 + akar 2) x
    0,0005. Bentuk linear akan menjawab 2x di sini, jauh di luar batas itu.
    """
    a = _hitung(lead=10)
    b = _hitung(lead=20)
    toleransi = (1 + sqrt(2)) * 0.0005
    assert abs(b["calculated_safety_stock"]
               - sqrt(2) * a["calculated_safety_stock"]) < toleransi, (a, b)


def test_lead_time_nol_meniadakan_seluruhnya():
    h = _hitung(lead=0)
    assert h["calculated_safety_stock"] == 0
    assert h["final_reorder_point"] == 0


def test_lead_time_negatif_diperlakukan_sebagai_nol():
    """Titik pesan negatif adalah angka mustahil; masukan keliru dijepit."""
    h = _hitung(lead=-5)
    assert h["final_reorder_point"] >= 0


# ==========================================================================
# Rantainya
# ==========================================================================

def test_mengganti_model_mengubah_permintaan_DAN_cadangan():
    """
    Inti seluruh berkas ini. Kalau mengganti model hanya menggeser permintaan
    sementara cadangannya tetap, berarti rantainya putus: galat yang dipakai
    bukan galat model yang dipilih.
    """
    a = _hitung(model="croston_sba")
    b = _hitung(model="theta")
    assert a["predicted_daily_demand"] != b["predicted_daily_demand"]
    assert a["model_rmse"] != b["model_rmse"], (
        "galat tidak ikut berganti saat model diganti -- rantainya putus")


def test_model_yang_lebih_tepat_menghasilkan_cadangan_lebih_tipis():
    """
    Janji utama safety stock dinamis: model yang meramal barang ini dengan
    tepat berhak atas cadangan yang lebih tipis. Diuji pada deret musiman
    mingguan, tempat naif musiman meramal nyaris sempurna sementara rata-rata
    bergerak selalu meleset pada hari Minggu.
    """
    musiman = [0.2 if (SENIN.toordinal() - 89 + i) % 7 == 6 else 5.0
               for i in range(90)]
    tepat = _hitung(model="seasonal_naive", riwayat=musiman)
    kasar = _hitung(model="wma", riwayat=musiman)
    assert tepat["model_rmse"] < kasar["model_rmse"]
    assert tepat["calculated_safety_stock"] < kasar["calculated_safety_stock"]


def test_mode_terbaik_memilih_dan_menyebut_pemenangnya():
    musiman = [0.2 if (SENIN.toordinal() - 89 + i) % 7 == 6 else 5.0
               for i in range(90)]
    h = _hitung(model=klasik.KUNCI_TERBAIK, riwayat=musiman)
    assert h["selected_forecast_model"] == "seasonal_naive"


def test_model_tak_dikenal_dilaporkan_apa_adanya():
    """
    Jatuh ke cadangan boleh; berbohong tidak. `selected_forecast_model` harus
    menyebut yang BENAR-BENAR meramal, bukan yang diminta -- angka yang
    dilaporkan di bawah nama model yang keliru adalah kesalahan yang tidak
    dapat ditelusuri siapa pun.
    """
    h = _hitung(model="model_yang_tidak_ada")
    assert h["selected_forecast_model"] == klasik.KUNCI_BAWAAN


def test_riwayat_terlalu_pendek_tidak_mengarang_cadangan():
    """
    Di bawah ambang adu model, galatnya tidak dapat diukur. Cadangan nol lebih
    jujur daripada angka karangan -- dan ROP-nya tetap terbit dari permintaan
    kali lead time, sehingga halaman tidak kosong.
    """
    h = _hitung(riwayat=[4.0] * 10)
    assert h["model_rmse"] is None
    assert h["calculated_safety_stock"] == 0
    assert h["final_reorder_point"] > 0
