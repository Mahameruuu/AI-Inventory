# -*- coding: utf-8 -*-
"""
Uji model prakiraan klasik dan pemilih model terbaik.

    .venv/bin/python -m pytest backend/tests/test_model_klasik.py -q

Tanpa basis data: seluruhnya fungsi murni atas deret angka.

Yang dijaga di sini bukan "rumusnya jalan", melainkan bahwa TIAP MODEL MENANG
PADA BENTUK DERET YANG MEMANG DIRANCANG UNTUKNYA. Itulah satu-satunya bukti
bahwa implementasinya benar dan bukan sekadar menghasilkan angka yang masuk
akal: Croston pada permintaan berlubang, naif musiman pada irama mingguan,
Theta pada deret yang menanjak. Rumus yang keliru tetap mengembalikan angka --
ia hanya kalah pada kasus yang seharusnya ia kuasai.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml import klasik  # noqa: E402

SENIN = date(2026, 8, 31)
HORIZON = 7


def _deret_mantap(n: int = 60, nilai: float = 4.0) -> list[float]:
    return [nilai] * n


def _deret_intermiten(n: int = 60, tiap: int = 5, ukuran: float = 10.0) -> list[float]:
    """Keluar sekali tiap lima hari; sisanya nol. Bentuk khas suku cadang."""
    return [ukuran if i % tiap == 0 else 0.0 for i in range(n)]


def _deret_mingguan(n: int = 60, as_of: date = SENIN) -> list[float]:
    """Ramai pada hari kerja, nyaris berhenti pada hari Minggu."""
    return [0.2 if (as_of - timedelta(days=n - 1 - i)).weekday() == 6 else 5.0
            for i in range(n)]


def _deret_menanjak(n: int = 60) -> list[float]:
    return [i * 0.1 for i in range(n)]


# ==========================================================================
# Kontrak bersama
# ==========================================================================

@pytest.mark.parametrize("kunci", list(klasik.KLASIK))
def test_panjang_ramalan_sesuai_permintaan(kunci):
    r = klasik.ramal(kunci, _deret_mantap(), HORIZON, SENIN)
    assert len(r) == HORIZON


@pytest.mark.parametrize("kunci", list(klasik.KLASIK))
@pytest.mark.parametrize("deret", [
    _deret_mantap(), _deret_intermiten(), _deret_mingguan(), _deret_menanjak(),
    [0.0] * 40,           # tidak pernah keluar sama sekali
    [7.0],                # riwayat satu hari
    [],                   # tidak ada riwayat
])
def test_tidak_pernah_negatif(kunci, deret):
    """
    Permintaan negatif adalah angka mustahil, dan satu angka mustahil sudah
    cukup membuat seluruh halaman diragukan. Theta paling rawan: garis
    regresinya bisa menembus nol pada deret yang menurun.
    """
    r = klasik.ramal(kunci, deret, HORIZON, SENIN)
    assert all(v >= 0 for v in r), (kunci, r)


@pytest.mark.parametrize("kunci", list(klasik.KLASIK))
def test_deret_kosong_tidak_menjatuhkan(kunci):
    assert klasik.ramal(kunci, [], HORIZON, SENIN) == [0.0] * HORIZON


def test_kunci_asing_mengembalikan_none(kunci="tidak_ada_model_ini"):
    assert klasik.ramal(kunci, _deret_mantap(), HORIZON, SENIN) is None


# ==========================================================================
# Kebenaran tiap model
# ==========================================================================

@pytest.mark.parametrize("kunci", list(klasik.KLASIK))
def test_deret_mantap_diramal_mendekati_nilainya(kunci):
    """Permintaan tetap 4/hari: model apa pun harus mendekati 4."""
    r = klasik.ramal(kunci, _deret_mantap(nilai=4.0), HORIZON, SENIN)
    rata = sum(r) / len(r)
    assert 3.5 <= rata <= 4.5, (kunci, rata)


def test_croston_mendekati_laju_sebenarnya_pada_deret_berlubang():
    """
    Sepuluh unit tiap lima hari = 2 unit/hari. Pemulusan biasa akan tertarik
    mendekati nol karena empat dari lima harinya nol; Croston tidak, karena ia
    memisahkan ukuran dari jaraknya.
    """
    r = klasik.ramal("croston_sba", _deret_intermiten(), HORIZON, SENIN)
    assert 1.5 <= r[0] <= 2.2, r[0]


def test_naif_musiman_meramal_berbeda_tiap_hari():
    """
    Satu-satunya model yang ramalannya tidak rata. Bila ia mengembalikan angka
    yang sama untuk tujuh hari, berarti pengelompokan hari-nya tidak bekerja
    dan seluruh keunggulannya hilang tanpa suara.
    """
    r = klasik.ramal("seasonal_naive", _deret_mingguan(), HORIZON, SENIN)
    assert len(set(round(v, 3) for v in r)) > 1, r
    # Hari ke-6 sesudah Senin adalah Minggu; itu yang harus paling sepi.
    minggu = min(range(HORIZON), key=lambda j: r[j])
    assert (SENIN + timedelta(days=minggu + 1)).weekday() == 6, r


def test_theta_membawa_arah_pada_deret_menanjak():
    """Model yang rata akan meramal di bawah kenyataan pada deret menanjak."""
    deret = _deret_menanjak()
    theta = klasik.ramal("theta", deret, HORIZON, SENIN)
    datar = klasik.ramal("wma", deret, HORIZON, SENIN)
    assert theta[-1] > theta[0], "theta tidak menanjak"
    assert sum(theta) > sum(datar), (sum(theta), sum(datar))


# ==========================================================================
# Perlombaan
# ==========================================================================

@pytest.mark.parametrize("deret,pemenang", [
    (_deret_intermiten(), "croston_sba"),
    (_deret_mingguan(), "seasonal_naive"),
    (_deret_menanjak(), "theta"),
])
def test_pemenang_adalah_model_yang_dirancang_untuk_bentuk_itu(deret, pemenang):
    """
    Inti seluruh berkas ini. Kalau pemenangnya bukan model yang memang
    dirancang untuk bentuk deret tersebut, entah rumusnya keliru entah cara
    mengadunya yang keliru -- dan keduanya membuat kata "terbaik" kehilangan
    arti.
    """
    menang, papan = klasik.pilih_terbaik(deret, HORIZON, SENIN)
    assert menang == pemenang, [(p["model"], p["mase"]) for p in papan]


def test_papan_terurut_dari_galat_terkecil():
    _, papan = klasik.pilih_terbaik(_deret_intermiten(), HORIZON, SENIN)
    nilai = [p["mase"] for p in papan]
    assert nilai == sorted(nilai), nilai


def test_seluruh_model_ikut_bertanding():
    _, papan = klasik.pilih_terbaik(_deret_mingguan(), HORIZON, SENIN)
    assert {p["model"] for p in papan} == set(klasik.KLASIK)


def test_riwayat_terlalu_pendek_tidak_diadu():
    """
    Di bawah ambang, pemenangnya hanya mencerminkan keberuntungan pada
    beberapa titik. Lebih jujur menyatakan tidak ada perlombaan daripada
    menobatkan pemenang yang tidak berarti.
    """
    menang, papan = klasik.pilih_terbaik([3.0] * 10, HORIZON, SENIN)
    assert menang is None and papan == []


def test_model_tambahan_ikut_diadu_dan_yang_gagal_tidak_menang():
    """
    Model pembelajaran mesin masuk lewat `tambahan`. Yang mengembalikan None --
    karena berkas modelnya tidak termuat, misalnya -- tidak boleh muncul di
    papan sama sekali; model yang tidak bertanding tidak boleh menang.
    """
    deret = _deret_mingguan()
    sempurna = {"ml_bagus": lambda d, h, a: klasik.ramal("seasonal_naive", d, h, a)}
    gagal = {"ml_mati": lambda d, h, a: None}

    _, papan = klasik.pilih_terbaik(deret, HORIZON, SENIN, {**sempurna, **gagal})
    kunci = {p["model"] for p in papan}
    assert "ml_bagus" in kunci
    assert "ml_mati" not in kunci


def test_ramalan_sempurna_bergalat_nol():
    """Deret yang dapat diramal persis harus bergalat nol, bukan sekadar kecil."""
    menang, papan = klasik.pilih_terbaik(_deret_mingguan(), HORIZON, SENIN)
    teratas = papan[0]
    assert teratas["model"] == "seasonal_naive"
    assert teratas["mase"] == 0.0, teratas


def test_daftar_kunci_memuat_terbaik_dan_seluruh_klasik():
    kunci = klasik.semua_kunci()
    assert kunci[0] == klasik.KUNCI_TERBAIK
    assert set(klasik.KLASIK).issubset(kunci)
    assert klasik.KUNCI_ML in kunci
    assert klasik.KUNCI_ML not in klasik.semua_kunci(dengan_ml=False)
