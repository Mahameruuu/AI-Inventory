# -*- coding: utf-8 -*-
"""
Uji lapisan reorder (app/decision.py).

    .venv/bin/python -m pytest backend/tests -q

Yang dikunci di sini adalah PEMISAHAN LAPISAN. Prakiraan menjawab kebutuhan
selama horizon yang dipilih; keputusan dan rekomendasi reorder menjawab kapan
bertindak dan berapa dipesan, dan keduanya berpatokan waktu tunggu pengiriman.
Karena itu sejumlah uji di bawah ini justru memastikan bahwa mengubah
forecast_days TIDAK menggerakkan angka reorder sama sekali -- itulah invarian
yang paling mudah rusak tanpa disadari.
"""

import math
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import decision as d  # noqa: E402
from app import forecasting as f  # noqa: E402
from app import tools  # noqa: E402


def lapisan(**ubah):
    """Satu barang wajar; tiap uji hanya mengubah yang sedang diperiksa."""
    arg = dict(
        current_stock=156, available_stock=156, reorder_point=40,
        minimum_stock=20, safety_stock=10, avg_daily_usage=6.964,
        lead_time_days=7, forecast_days=30,
        keluar_harian=[7.0] * 30, hari_histori=30, hari_aktif=30,
    )
    arg.update(ubah)
    return d.lapisan_keputusan(**arg)


# ==========================================================================
# 1-2. Kecukupan titik pesan
# ==========================================================================

class TestKecukupanTitikPesan:

    def test_titik_pesan_efektif_mengambil_yang_tertinggi(self):
        """
        max() DIKEMBALIKAN. Titik pesan master 74 lebih tinggi daripada
        kebutuhan hitung (57,771 + 10 = 67,771), jadi 74 yang menjadi ambang:
        ambang yang ditetapkan petugas tidak boleh diturunkan diam-diam oleh
        perhitungan. Kecukupannya tetap dinilai terpisah.
        """
        r = lapisan(reorder_point=74, avg_daily_usage=8.253, safety_stock=10,
                    lead_time_days=7, current_stock=212, available_stock=212)
        assert r["lead_time_demand"] == 57.771
        assert r["effective_reorder_point"] == 74.0
        assert r["reorder_point_adequate"] is True

    def test_rop_tidak_cukup_ditandai(self):
        # rop master 40 < 48,748 + 10, jadi yang menang adalah hasil hitungnya.
        r = lapisan()
        assert r["lead_time_demand"] == 48.748
        assert r["effective_reorder_point"] == 58.748
        assert r["reorder_point_adequate"] is False

    def test_master_tinggi_tidak_lagi_menghasilkan_kontradiksi(self):
        """
        Inilah yang dulu memaksa max() dicabut: master 500 membuat statusnya
        mendesak sementara sasaran pengisian sudah terlampaui, sehingga
        jumlahnya nol. Yang memperbaikinya kini target_pengadaan(), yang tidak
        pernah turun di bawah ambangnya sendiri -- jadi max() boleh kembali dan
        jumlahnya tetap lebih besar dari nol.
        """
        r = lapisan(reorder_point=500)
        assert r["effective_reorder_point"] == 500.0
        assert r["action_status"] != d.STATUS_AMAN
        assert r["recommended_order_qty"] > 0


# ==========================================================================
# 3-4. Basis stok tersedia
# ==========================================================================

class TestBasisStokTersedia:

    def test_stok_tercadang_mengurangi_stok_tersedia(self):
        penuh = lapisan(current_stock=156, available_stock=156)
        tercadang = lapisan(current_stock=156, available_stock=100)
        assert penuh["available_stock_used"] == 156.0
        assert tercadang["available_stock_used"] == 100.0
        assert tercadang["days_to_effective_rop"] < penuh["days_to_effective_rop"]

    def test_keputusan_memakai_stok_tersedia_bukan_fisik(self):
        """
        Stok fisik jauh di atas titik pesan efektif, tetapi hampir seluruhnya
        sudah dikomitmenkan keluar. Yang menentukan adalah yang tersisa.
        """
        r = lapisan(current_stock=500, available_stock=50)
        assert r["action_status"] != d.STATUS_AMAN
        # Sasaran = max(58,748, 6,964 x 14 + 10) = 107,496; 107,496 - 50.
        assert r["recommended_order_qty"] == math.ceil(107.496 - 50)

    def test_tanpa_available_stock_mengikuti_stok_fisik(self):
        """Pemanggil lama tidak berubah perilakunya."""
        a = lapisan(available_stock=None)
        b = lapisan(available_stock=156)
        for k in ("effective_reorder_point", "days_to_effective_rop",
                  "action_status", "recommended_order_qty"):
            assert a[k] == b[k], k


# ==========================================================================
# 5-7. Rumus turunan
# ==========================================================================

class TestRumusTurunan:

    def test_lead_time_demand(self):
        assert lapisan(avg_daily_usage=6.964, lead_time_days=7)["lead_time_demand"] == 48.748
        assert lapisan(avg_daily_usage=2.0, lead_time_days=14)["lead_time_demand"] == 28.0

    def test_days_to_effective_rop(self):
        r = lapisan()
        # (156 - 58,748) / 6,964 = 13,96
        assert r["days_to_effective_rop"] == 13.96

    def test_days_to_effective_rop_nol_saat_sudah_tersentuh(self):
        r = lapisan(available_stock=50)
        assert r["days_to_effective_rop"] == 0.0

    def test_titik_pesan_master_tidak_ikut_dijumlahkan(self):
        """
        Titik pesan efektif adalah kebutuhan masa tunggu + safety stock saja.
        Menjumlahkannya dengan titik pesan master (40 + 48,748 + 10 = 98,748)
        berarti menghitung penyangga dua kali dan memesan jauh terlalu dini.
        """
        r = lapisan()
        assert r["effective_reorder_point"] == 58.748
        assert r["effective_reorder_point"] != 40 + 48.748 + 10

    def test_titik_pesan_master_menaikkan_tetapi_tidak_menurunkan(self):
        """
        Ambangnya yang tertinggi di antara master dan hasil hitung (58,748).
        Master di bawah itu tidak menurunkannya; master di atasnya menang.
        """
        for rop in (0, 5, 40):
            assert lapisan(reorder_point=rop)["effective_reorder_point"] == 58.748
        for rop in (200, 500):
            assert lapisan(reorder_point=rop)["effective_reorder_point"] == float(rop)

    def test_sasaran_pengisian_di_atas_titik_pesan_efektif(self):
        """
        Mengisi persis sampai titik pesan berarti barang datang tepat di
        ambangnya dan langsung memicu pemesanan berikutnya.
        """
        r = lapisan(available_stock=30)
        # Sasaran = max(58,748, 6,964 x 14 + 10) = 107,496.
        assert r["order_up_to_level"] == pytest.approx(107.496, abs=0.001)
        assert r["order_up_to_level"] > r["effective_reorder_point"]

    def test_sasaran_tidak_pernah_turun_di_bawah_ambangnya_sendiri(self):
        """
        PENJAGA INVARIAN. Masa tunggu 30 hari membuat ambangnya 30 x 1 + 10 =
        40, sedangkan kebutuhan horizon + cadangan hanya 1 x 14 + 10 = 24.
        Tanpa penjepitan, stok 30 berstatus perlu reorder dengan jumlah nol.
        """
        r = lapisan(avg_daily_usage=1.0, lead_time_days=30, safety_stock=10,
                    reorder_point=0, current_stock=30, available_stock=30,
                    keluar_harian=[1.0] * 30)
        assert r["effective_reorder_point"] == 40.0
        assert r["order_up_to_level"] == 40.0
        assert r["action_status"] != d.STATUS_AMAN
        assert r["recommended_order_qty"] == 10


# ==========================================================================
# 8-9. Horizon prakiraan tidak boleh memengaruhi reorder
# ==========================================================================

HORIZON = (7, 14, 30, 60, 90)
FIELD_REORDER = ("lead_time_demand", "effective_reorder_point",
                 "reorder_point_adequate", "days_to_effective_rop",
                 "action_status", "recommended_order_qty")


class TestHorizonTidakMemengaruhiReorder:

    @pytest.mark.parametrize("field", FIELD_REORDER)
    def test_field_reorder_tetap_pada_semua_horizon(self, field):
        nilai = {h: lapisan(forecast_days=h)[field] for h in HORIZON}
        assert len(set(nilai.values())) == 1, nilai

    def test_juga_tetap_pada_barang_yang_kekurangan(self):
        nilai = {h: tuple(lapisan(available_stock=30, forecast_days=h)[k]
                          for k in FIELD_REORDER) for h in HORIZON}
        assert len(set(nilai.values())) == 1, nilai

    def test_projected_shortage_justru_HARUS_ikut_horizon(self):
        """
        Sisi lain dari invarian yang sama: potensi kekurangan memang mengukur
        horizon, jadi ia wajib bergerak. Bila suatu saat ia berhenti bergerak,
        artinya definisinya tergeser.
        """
        akhir = date(2026, 8, 24)
        keluar = [(akhir - timedelta(days=29 - i), 7.0) for i in range(30)]
        # Stok sengaja rendah supaya SETIAP horizon menghasilkan kekurangan;
        # pada stok tinggi horizon pendek sama-sama nol dan uji ini kehilangan
        # daya bedanya.
        nilai = [
            f.hitung(as_of=akhir, current_stock=20, available_stock=20,
                     daily_outflow=keluar, daily_net=[(t, -v) for t, v in keluar],
                     minimum_stock=5, reorder_point=10,
                     forecast_days=h, historical_days=30)["projected_shortage"]
            for h in HORIZON
        ]
        assert len(set(nilai)) == len(HORIZON), nilai
        assert nilai == sorted(nilai), nilai   # horizon lebih panjang, kurang lebih banyak


# ==========================================================================
# 10-11. Rekomendasi bukan potensi kekurangan
# ==========================================================================

class TestBukanProjectedShortage:

    def test_qty_tidak_sama_dengan_projected_shortage(self):
        """
        BRU-000001 pada horizon 30 hari: kekurangan 52,929 tetapi yang perlu
        dipesan 0. Menyamakan keduanya akan menyuruh membeli barang yang
        belum perlu dibeli.
        """
        akhir = date(2026, 8, 24)
        keluar = [(akhir - timedelta(days=29 - i), 6.964) for i in range(30)]
        h = f.hitung(as_of=akhir, current_stock=156, available_stock=156,
                     daily_outflow=keluar, daily_net=[(t, -v) for t, v in keluar],
                     minimum_stock=20, reorder_point=40,
                     forecast_days=30, historical_days=30)
        r = lapisan()
        assert h["projected_shortage"] > 0
        assert r["recommended_order_qty"] == 0
        assert r["recommended_order_qty"] != h["projected_shortage"]

    def test_qty_bukan_forecast_usage_dikurangi_tersedia(self):
        r = lapisan()
        assert r["recommended_order_qty"] != math.ceil(6.964 * 30 - 156)

    def test_qty_bukan_shortage_ditambah_safety(self):
        r = lapisan(available_stock=30)
        assert r["recommended_order_qty"] == 78     # ceil(58,748 + 48,748 - 30)
        assert r["recommended_order_qty"] != math.ceil(6.964 * 30 - 30 + 10)

    def test_qty_tidak_bergerak_saat_horizon_prakiraan_digeser(self):
        """
        Prakiraan 90 hari (627 unit) tidak boleh menjadi jumlah pesanan; itu
        pertanyaan yang berbeda dan jawabannya berubah tiap kali pengguna
        menggeser pilihan periode pada layar Forecasting.
        """
        nilai = {h: lapisan(available_stock=30, forecast_days=h)["recommended_order_qty"]
                 for h in HORIZON}
        assert set(nilai.values()) == {78}
        assert 78 != math.ceil(6.964 * 90)


# ==========================================================================
# 12-17. Kasus tepi
# ==========================================================================

class TestKasusTepi:

    def test_pemakaian_nol_tetap_aman(self):
        r = lapisan(avg_daily_usage=0, keluar_harian=[0] * 30, hari_aktif=0,
                    available_stock=156)
        assert r["action_status"] == d.STATUS_AMAN
        assert r["days_to_effective_rop"] is None

    def test_lead_time_kosong_jatuh_ke_titik_pesan_master(self):
        r = lapisan(lead_time_days=None)
        assert r["lead_time_demand"] is None
        assert r["effective_reorder_point"] == 40.0   # master sendirian
        assert r["reorder_point_adequate"] is None    # belum dapat dinilai
        # Jumlahnya KINI terhitung tanpa lead time: rumus barunya hanya
        # menuntut laju pemakaian. Stok 156 masih di atas ambang -> nol.
        assert r["recommended_order_qty"] == 0
        assert r["action_status"] == d.STATUS_AMAN

    def test_histori_belum_cukup_menghasilkan_none_bukan_nol(self):
        r = lapisan(has_forecast=False, avg_daily_usage=None)
        assert r["recommended_order_qty"] is None
        assert r["recommended_order_qty"] is not None or True   # None, bukan 0

    def test_laju_none_menghasilkan_none(self):
        r = lapisan(avg_daily_usage=None)
        assert r["recommended_order_qty"] is None

    def test_qty_tidak_pernah_negatif(self):
        for tersedia in (0, 50, 100, 500, 10_000):
            r = lapisan(available_stock=tersedia)
            assert r["recommended_order_qty"] >= 0

    def test_pembulatan_jumlah_pesanan_selalu_ke_atas(self):
        """
        58,748 + 48,748 - 30 = 77,496 -> 78. Ke bawah akan menghasilkan 77,
        yaitu satu unit lebih sedikit dari yang dibutuhkan. Ini SATU-SATUNYA
        angka tampilan yang tidak memakai pembulatan setengah ke atas.
        """
        r = lapisan(available_stock=30)
        # 6,964 x 14 + 10 = 107,496; 107,496 - 30 = 77,496 -> 78.
        assert r["recommended_order_qty"] == 78
        assert isinstance(r["recommended_order_qty"], int)

    def test_lead_time_nol_tetap_menghasilkan_lapisan_reorder(self):
        """
        Pemasok yang mengirim di hari yang sama menghasilkan kebutuhan masa
        tunggu nol -- itu jawaban yang sah, bukan kolom kosong. Titik pesan
        efektifnya menjadi safety stock saja.
        """
        r = lapisan(lead_time_days=0, available_stock=5)
        assert r["lead_time_demand"] == 0.0
        # max(master 40, 0 + safety 10) = 40.
        assert r["effective_reorder_point"] == 40.0
        assert r["action_status"] != d.STATUS_AMAN
        # Sasaran = max(40, 6,964 x 14 + 10) = 107,496; 107,496 - 5 -> 103.
        assert r["recommended_order_qty"] == math.ceil(107.496 - 5)

    def test_safety_stock_nol(self):
        r = lapisan(safety_stock=0, available_stock=30)
        assert r["effective_reorder_point"] == 48.748
        assert r["action_status"] != d.STATUS_AMAN
        # Sasaran = max(48,748, 6,964 x 14 + 0) = 97,496.
        assert r["recommended_order_qty"] == math.ceil(97.496 - 30)

    def test_pemakaian_nol_tidak_pernah_membagi_dengan_nol(self):
        r = lapisan(avg_daily_usage=0, keluar_harian=[0] * 30, hari_aktif=0)
        assert r["days_to_effective_rop"] is None
        assert r["days_to_effective_rop_label"] == "Tidak ada konsumsi terdeteksi"

    def test_stok_berlimpah_menghasilkan_nol_bukan_none(self):
        r = lapisan(available_stock=10_000)
        assert r["recommended_order_qty"] == 0


# ==========================================================================
# 18-21. Contoh dari spesifikasi
# ==========================================================================

class TestContohSpesifikasi:

    def test_kontradiksi_yang_dilaporkan_pengguna(self):
        """
        Kasus persis dari laporan: stok 55, minimum 15, titik pesan master 44,
        lead time 14 hari, safety stock 22, laju ±1 per hari.

        Layar lama berbunyi "Segera pesan" -- karena jarak ke titik pesan
        (9 hari) lebih pendek dari lead time -- sementara blok pengadaan
        berbunyi "Belum ada jumlah yang perlu diadakan". Dua kesimpulan
        berbeda untuk satu barang.

        Sekarang: titik pesan efektif max(44, 14 + 22) = 44, stok 55 masih di
        atasnya, jadi statusnya aman DAN jumlahnya nol. Satu kesimpulan.
        """
        r = lapisan(current_stock=55, available_stock=55, reorder_point=44,
                    minimum_stock=15, safety_stock=22, avg_daily_usage=1.0,
                    lead_time_days=14, keluar_harian=[1.0] * 30, unit_code="PCS")
        assert r["lead_time_demand"] == 14.0
        assert r["effective_reorder_point"] == 44.0
        assert r["effective_reorder_point_int"] == 44
        assert r["reorder_point_int"] == 44          # master, tetap tampil
        assert r["days_to_effective_rop_int"] == 11
        assert r["action_status"] == d.STATUS_AMAN
        assert r["recommended_order_qty"] == 0
        assert r["order_qty_title"] == "Belum perlu pengadaan"

    def test_kontradiksi_yang_dilaporkan_pengguna_saat_stok_menipis(self):
        """Barang yang sama pada stok 30: mendesak, dan ADA jumlahnya."""
        r = lapisan(current_stock=30, available_stock=30, reorder_point=44,
                    minimum_stock=15, safety_stock=22, avg_daily_usage=1.0,
                    lead_time_days=14, keluar_harian=[1.0] * 30, unit_code="PCS")
        assert r["action_status"] != d.STATUS_AMAN
        # Sasaran = max(44, 1 x 14 + 22) = 44; 44 - 30 = 14.
        assert r["recommended_order_qty"] == 14
        assert r["order_qty_title"] == "Pesan 14 PCS"

    def test_bru_000001(self):
        """§13 -- titik pesan master kurang, tetapi belum perlu memesan."""
        r = lapisan()
        assert r["lead_time_demand"] == 48.748
        assert r["effective_reorder_point"] == 58.748
        assert r["days_to_effective_rop"] == pytest.approx(13.97, abs=0.02)
        # 13,97 hari masih lebih panjang dari satu kali lead time (7 hari).
        assert r["action_status"] == d.STATUS_AMAN
        assert r["recommended_order_qty"] == 0
        assert r["reorder_point_adequate"] is False

    def test_bru_000001_stok_menipis(self):
        """§14 -- stok 30, mendesak, diisi sampai 107,496."""
        r = lapisan(available_stock=30, current_stock=30)
        assert r["action_status"] != d.STATUS_AMAN
        assert r["recommended_order_qty"] == 78

    def test_con_884484(self):
        r = lapisan(current_stock=7, available_stock=7, reorder_point=2,
                    minimum_stock=1, safety_stock=1, avg_daily_usage=0.319,
                    lead_time_days=7)
        assert r["lead_time_demand"] == 2.233
        assert r["effective_reorder_point"] == 3.233
        assert r["reorder_point_adequate"] is False
        # 7 unit pada laju 0,319 masih 11,8 hari dari titik pesan efektif,
        # lebih panjang dari lead time 7 hari.
        assert r["action_status"] == d.STATUS_AMAN
        assert r["recommended_order_qty"] == 0

    def test_ins_616403(self):
        r = lapisan(current_stock=63, available_stock=63, reorder_point=18,
                    minimum_stock=9, safety_stock=9, avg_daily_usage=2.666,
                    lead_time_days=7)
        assert r["lead_time_demand"] == 18.662
        assert r["effective_reorder_point"] == 27.662
        assert r["reorder_point_adequate"] is False
        assert r["action_status"] == d.STATUS_AMAN
        assert r["recommended_order_qty"] == 0

    def test_per_643896_rop_memadai(self):
        """
        Contoh §15: rop master 74 melampaui 57,771 + 10, jadi titik pesan
        master dinilai MEMADAI -- dan sejak max() dikembalikan, ia pula yang
        menjadi ambangnya.
        """
        r = lapisan(current_stock=212, available_stock=212, reorder_point=74,
                    minimum_stock=37, safety_stock=10, avg_daily_usage=8.253,
                    lead_time_days=7)
        assert r["lead_time_demand"] == 57.771
        assert r["effective_reorder_point"] == 74.0
        assert r["reorder_point_adequate"] is True
        assert r["action_status"] == d.STATUS_AMAN

    def test_per_643896_dgn_safety_sesungguhnya_tetap_aman(self):
        """
        Nilai safety_stock yang sesungguhnya pada master barang ini 37, bukan
        10. Titik pesan efektif naik menjadi 94,771 dan titik pesan masternya
        jadi tidak memadai -- tetapi urgensinya TETAP AMAN, karena masih ada
        14,2 hari sebelum menyentuhnya sementara ambang PANTAU-nya 7 hari.

        Inilah pembeda yang dicari: barang ini tidak boleh ikut naik hanya
        karena punya potensi kekurangan pada horizon 30 hari.
        """
        r = lapisan(current_stock=212, available_stock=212, reorder_point=74,
                    minimum_stock=37, safety_stock=37, avg_daily_usage=8.253,
                    lead_time_days=7)
        assert r["effective_reorder_point"] == 94.771
        assert r["reorder_point_adequate"] is False
        assert r["days_to_effective_rop"] == pytest.approx(14.20, abs=0.02)
        assert r["action_status"] == d.STATUS_AMAN
        assert r["recommended_order_qty"] == 0


# ==========================================================================
# Invarian status <-> jumlah, disapu lintas parameter
# ==========================================================================

class TestStatusDanJumlahSelaras:
    """
    Kontradiksi yang dilaporkan pengguna berbunyi "Segera pesan" berdampingan
    dengan "Belum ada jumlah yang perlu diadakan". Uji ini menyapu seluruh
    kombinasi parameter yang masuk akal untuk memastikan pasangan itu tidak
    dapat muncul lagi dari sudut mana pun.
    """

    @pytest.mark.parametrize("stok", [0, 5, 15, 30, 44, 55, 60, 100, 500])
    @pytest.mark.parametrize("lead", [0, 1, 7, 14, None])
    @pytest.mark.parametrize("safety", [0, 10, 22])
    @pytest.mark.parametrize("laju", [0, 0.319, 1.0, 6.964])
    def test_segera_selalu_punya_jumlah(self, stok, lead, safety, laju):
        r = lapisan(current_stock=stok, available_stock=stok,
                    lead_time_days=lead, safety_stock=safety,
                    avg_daily_usage=laju,
                    keluar_harian=[laju] * 30, hari_aktif=30 if laju else 0)
        qty = r["recommended_order_qty"]
        # Invarian yang sama, disesuaikan dengan sumbu tiga status: apa pun
        # yang BUKAN aman harus punya jumlah, dan yang aman harus nol.
        if r["action_status"] != d.STATUS_AMAN:
            assert qty is None or qty > 0, (stok, lead, safety, laju, qty)
        else:
            assert qty in (0, None), (stok, lead, safety, laju, qty)

    @pytest.mark.parametrize("stok", [0, 30, 55, 500])
    @pytest.mark.parametrize("lead", [0, 7, 14, None])
    def test_judul_pengadaan_selaras_dengan_status(self, stok, lead):
        r = lapisan(current_stock=stok, available_stock=stok, lead_time_days=lead)
        judul = r["order_qty_title"]
        if r["action_status"] != d.STATUS_AMAN:
            assert judul.startswith("Pesan ") or "belum dapat dihitung" in judul
        else:
            assert not judul.startswith("Pesan ")

    @pytest.mark.parametrize("stok", [0, 30, 55, 500])
    @pytest.mark.parametrize("laju", [0, 1.0, 6.964])
    def test_tidak_ada_desimal_pada_field_tampilan(self, stok, laju):
        r = lapisan(current_stock=stok, available_stock=stok,
                    avg_daily_usage=laju, keluar_harian=[laju] * 30,
                    hari_aktif=30 if laju else 0, unit_code="PCS")
        for kunci, nilai in r.items():
            if kunci.endswith("_int"):
                assert nilai is None or isinstance(nilai, int), kunci
        for kunci in ("days_to_effective_rop_label", "reorder_status_reason",
                      "effective_reorder_point_basis", "order_qty_title",
                      "order_qty_reason", "advice_text"):
            assert not re.search(r"\d+,\d", r[kunci]), (kunci, r[kunci])


# ==========================================================================
# Payload chatbot
# ==========================================================================

class TestPayloadChatbot:

    def test_field_reorder_dikirim(self):
        for nama in ("lead_time_demand", "effective_reorder_point",
                     "days_to_effective_rop", "reorder_point_adequate",
                     "recommended_order_qty", "safety_stock"):
            assert nama in tools.BIDANG_FORECAST

    def test_status_tetap_tidak_dikirim(self):
        assert "status" not in tools.BIDANG_FORECAST


# ==========================================================================
# Masa tunggu: dari pemesanan sampai barang tiba
# ==========================================================================
#
# `items.lead_time_days` adalah RENTANG WAKTU YANG BERLALU antara pesanan
# dibuat dan kiriman diterima. Nol sah -- pemasok yang mengirim di hari yang
# sama -- tetapi negatif tidak, karena barang tidak tiba sebelum dipesan.
#
# Yang dikunci di sini: nilai rusak harus menempuh JALUR YANG SAMA dengan
# kolom yang belum diisi, di SELURUH lapisan sekaligus. Dulu penolakannya
# hanya hidup di permintaan_selama_lead(), sehingga kebutuhan masa tunggu
# berbunyi None sementara status masih memakai angka mustahil itu sebagai
# ambang peringatan dini -- dan master data yang RUSAK menghasilkan peringatan
# yang lebih lemah daripada master data yang KOSONG.

class TestMasaTunggu:

    def test_nol_adalah_angka(self):
        """Kirim di hari yang sama: kebutuhan masa tunggu nol, bukan None."""
        assert d.masa_tunggu(0) == 0.0
        r = lapisan(lead_time_days=0)
        assert r["lead_time_demand"] == 0.0
        assert r["lead_time_days_int"] == 0

    def test_belum_diisi_berarti_belum_diketahui(self):
        assert d.masa_tunggu(None) is None
        assert d.masa_tunggu("") is None

    def test_negatif_ditolak_sebagai_masa_tunggu(self):
        """Barang tidak tiba sebelum dipesan: itu master data rusak."""
        assert d.masa_tunggu(-1) is None
        assert d.masa_tunggu(-5) is None

    def test_masa_tunggu_rusak_setara_dengan_yang_kosong(self):
        """
        Invarian inti. Pada stok yang sama persis, lead time -5 dan lead time
        kosong harus menghasilkan keputusan yang sama: keduanya sama-sama
        tidak dapat dipakai sebagai tenggat.
        """
        arg = dict(current_stock=41, available_stock=41, reorder_point=40,
                   avg_daily_usage=2.0, safety_stock=5)
        rusak = lapisan(lead_time_days=-5, **arg)
        kosong = lapisan(lead_time_days=None, **arg)
        for kunci in ("action_status", "lead_time_demand", "lead_time_days_int",
                      "recommended_order_qty", "effective_reorder_point",
                      "order_up_to_level", "reorder_point_adequate"):
            assert rusak[kunci] == kosong[kunci], kunci

    def test_masa_tunggu_rusak_tidak_membungkam_peringatan_dini(self):
        """
        Setengah hari dari titik pesan efektif. Dulu lead -5 berbunyi "AMAN"
        karena tidak ada jarak yang pernah lebih kecil dari bilangan negatif,
        sedangkan lead kosong berbunyi "PANTAU" pada keadaan yang sama.

        Sumbu status kini tiga keadaan dan tidak lagi punya tingkat peringatan
        dini, jadi yang dikunci di sini adalah hal yang tersisa dan tetap
        penting: masa tunggu rusak menempuh jalur yang SAMA PERSIS dengan yang
        kosong -- pada seluruh field, bukan hanya statusnya.
        """
        rusak = lapisan(lead_time_days=-5, current_stock=41, available_stock=41,
                        reorder_point=40, avg_daily_usage=2.0, safety_stock=5)
        kosong = lapisan(lead_time_days=None, current_stock=41, available_stock=41,
                         reorder_point=40, avg_daily_usage=2.0, safety_stock=5)
        for k in ("action_status", "effective_reorder_point",
                  "recommended_order_qty", "lead_time_days_int",
                  "lead_time_demand_int", "priority"):
            assert rusak[k] == kosong[k], k

    def test_angka_yang_ditampilkan_adalah_angka_yang_dipakai(self):
        """Masa tunggu rusak tidak boleh tercetak "-5 hari" di kartu."""
        r = lapisan(lead_time_days=-5)
        assert r["lead_time_days_int"] is None
        assert r["lead_time_demand_int"] is None

    def test_kebutuhan_masa_tunggu_adalah_laju_kali_lama_menunggu(self):
        """Definisi dasarnya, dikunci apa adanya."""
        assert d.permintaan_selama_lead(2.0, 7) == 14.0
        assert d.permintaan_selama_lead(0.5, 10) == 5.0
        # Laju atau masa tunggu tidak diketahui -> None, bukan nol.
        assert d.permintaan_selama_lead(None, 7) is None
        assert d.permintaan_selama_lead(2.0, None) is None
        assert d.permintaan_selama_lead(2.0, -1) is None

    def test_masa_tunggu_dikirim_ke_chatbot(self):
        """
        Model menjelaskan lapisan reorder, jadi ia harus dapat menyebut berapa
        lama menunggunya -- bukan hanya kebutuhan yang lahir dari lama itu.
        """
        assert "lead_time_days" in tools.BIDANG_FORECAST
        assert tools._SUMBER_TAMPILAN["lead_time_days"] == "lead_time_days_int"
