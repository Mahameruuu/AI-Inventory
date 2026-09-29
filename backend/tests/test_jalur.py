# -*- coding: utf-8 -*-
"""Penyederhanaan garis jalan untuk peta transfer (app/jalur.py)."""

import math

from app import jalur


def _garis(n: int):
    # Sinus di atas garis lurus: ada tikungan yang harus dipertahankan.
    return [[-7.0 + i * 0.001, 112.0 + 0.05 * math.sin(i / 40)] for i in range(n)]


def test_garis_pendek_tidak_diubah():
    g = _garis(50)
    assert jalur.sederhanakan(g) == g


def test_garis_panjang_dipangkas_ke_batas_dan_ujungnya_tetap():
    g = _garis(10_000)
    out = jalur.sederhanakan(g)
    assert len(out) <= jalur.MAKS_TITIK
    assert out[0] == g[0] and out[-1] == g[-1]
    # tikungan tidak hilang: garis hasil masih bergelombang, bukan lurus
    bujur = [p[1] for p in out]
    assert max(bujur) - min(bujur) > 0.04


def test_jalan_lurus_sangat_panjang_tidak_meledakkan_rekursi():
    g = [[-7.0 + i * 1e-5, 112.0] for i in range(20_000)]
    out = jalur.sederhanakan(g)
    assert 2 <= len(out) <= jalur.MAKS_TITIK


def test_label_tercepat_dan_terpendek_bisa_pada_jalur_berbeda():
    opsi = jalur.beri_label([
        {"points": [], "distance_m": 774_000, "duration_s": 32_000},
        {"points": [], "distance_m": 748_000, "duration_s": 36_000},
    ])
    assert [o["tercepat"] for o in opsi] == [True, False]
    assert [o["terpendek"] for o in opsi] == [False, True]


def test_satu_jalur_memegang_kedua_label():
    opsi = jalur.beri_label([{"points": [], "distance_m": 10, "duration_s": 5}])
    assert opsi[0]["tercepat"] and opsi[0]["terpendek"]


def _opsi(jarak_km, jam, tol_km, tercepat, terpendek, feri=False):
    return {"points": [], "distance_m": jarak_km * 1000, "duration_s": int(jam * 3600),
            "tol_m": tol_km * 1000, "feri": feri, "tercepat": tercepat, "terpendek": terpendek}


def test_rekomendasi_memilih_total_biaya_terendah_dan_menyebut_alasannya():
    # Jalur 0 tercepat tapi tolnya panjang; jalur 1 lebih lama namun jauh lebih murah.
    opsi = [_opsi(748, 9.2, 427, True, True), _opsi(774, 10.1, 100, False, False)]
    hasil = jalur.analisis(opsi)
    b0, b1 = opsi[0]["biaya"]["total"], opsi[1]["biaya"]["total"]
    assert b1 < b0  # tol 327 km lebih pendek mengalahkan 0,9 jam dan 26 km ekstra
    assert hasil["index"] == 1
    assert hasil["alasan"][0]["kode"] == "hemat_walau_lebih_lama"
    assert hasil["alasan"][0]["hemat_rp"] == b0 - b1
    assert hasil["alasan"][0]["lebih_lama_detik"] == opsi[1]["duration_s"] - opsi[0]["duration_s"]


def test_rekomendasi_tercepat_bila_jalur_lain_tak_lebih_murah():
    opsi = [_opsi(700, 8.0, 0, True, True), _opsi(800, 11.0, 300, False, False)]
    hasil = jalur.analisis(opsi)
    assert hasil["index"] == 0
    assert hasil["alasan"][0]["kode"] == "tercepat_dan_hemat"


def test_biaya_dibulatkan_ribuan_dan_feri_ditandai():
    opsi = [_opsi(100, 2.0, 50, True, True, feri=True)]
    hasil = jalur.analisis(opsi)
    assert all(v % 1000 == 0 for k, v in opsi[0]["biaya"].items() if k != "liter")
    assert {"kode": "ada_feri"} in hasil["alasan"]
    assert hasil["alasan"][0]["kode"] == "satu_jalur"


# --- jalur alternatif lewat kota perantara ---------------------------------

SBY = (-7.2575, 112.7521)
JKT = (-6.2088, 106.8456)


def test_perantara_dipilih_di_antara_ujung_dan_menyebar():
    kota = jalur.pilih_perantara(SBY, JKT)
    nama = [n for n, _, _ in kota]
    # Bandung terlalu dekat ujung Jakarta, Malang terlalu dekat Surabaya.
    assert "Bandung" not in nama and "Malang" not in nama
    assert 1 <= len(nama) <= 6
    assert len(set(nama)) == len(nama)


def test_perantara_kosong_bila_dua_titik_berimpit():
    assert jalur.pilih_perantara(SBY, SBY) == []


def test_jalur_yang_menyusuri_jalur_lain_dibuang():
    lurus = [[-7.0 + i * 0.01, 110.0] for i in range(100)]
    kembar = [[-7.0 + i * 0.01, 110.01] for i in range(100)]   # ~1 km di sebelahnya
    lain = [[-7.0 + i * 0.01, 111.0] for i in range(100)]       # ~110 km jauhnya
    opsi = [
        {"points": lurus, "duration_s": 100, "distance_m": 1},
        {"points": kembar, "duration_s": 90, "distance_m": 1},
        {"points": lain, "duration_s": 200, "distance_m": 1},
    ]
    hasil = jalur.gabung_pilihan(opsi, maks=4)
    assert len(hasil) == 2
    assert [o["duration_s"] for o in hasil] == [100, 200]   # yang lebih dulu menang


def test_jumlah_pilihan_dibatasi():
    opsi = [{"points": [[-7.0 + i * 0.01, 110.0 + k] for i in range(50)],
             "duration_s": 100 + k, "distance_m": 1} for k in range(8)]
    assert len(jalur.gabung_pilihan(opsi, maks=3)) == 3
