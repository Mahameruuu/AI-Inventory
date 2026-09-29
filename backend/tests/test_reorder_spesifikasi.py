# -*- coding: utf-8 -*-
"""
Sepuluh kasus validasi yang diminta pada spesifikasi modul Reorder.

    .venv/bin/python -m pytest backend/tests/test_reorder_spesifikasi.py -q

Berkas ini SENGAJA TERPISAH dari test_reorder.py. Yang di sana menguji rumus
satu per satu dan tumbuh mengikuti kode; yang di sini adalah daftar terima --
tiap uji memetakan satu-satu ke satu butir spesifikasi, dan nomornya
dipertahankan supaya keduanya dapat dicocokkan tanpa menebak.

PARAMETER DASARNYA SATU, dan tiap kasus hanya menggeser yang sedang diperiksa.
Dengan begitu perbedaan hasil antar kasus pasti berasal dari yang digeser, bukan
dari dua barang yang kebetulan berbeda di banyak tempat sekaligus.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import decision as d  # noqa: E402


# rop master 40, safety 10, lead 7, laju 2/hari:
#   kebutuhan masa tunggu = 2 x 7            = 14
#   titik pesan efektif   = max(40, 14 + 10) = 40
#   kebutuhan horizon     = 2 x 14           = 28
#   sasaran pengisian     = max(40, 28 + 10) = 40
#   habis sebelum kiriman bila stok <= 14
def lapisan(**ubah):
    arg = dict(
        current_stock=100, available_stock=100, reorder_point=40,
        minimum_stock=15, safety_stock=10, avg_daily_usage=2.0,
        lead_time_days=7, forecast_days=30,
        keluar_harian=[2.0] * 30, hari_histori=30, hari_aktif=30,
        unit_code="PCS",
    )
    arg.update(ubah)
    return d.lapisan_keputusan(**arg)


class TestSepuluhKasus:

    def test_1_stok_jauh_di_atas_titik_pesan_aman_dan_nol(self):
        r = lapisan(current_stock=500, available_stock=500)
        assert r["action_status"] == d.STATUS_AMAN
        assert r["recommended_order_qty"] == 0
        assert r["priority"] == d.PRIORITAS_RENDAH

    def test_2_stok_mendekati_titik_pesan_perlu_reorder(self):
        """
        Tepat DI titik pesan efektif. Ambangnya "pada atau di bawah", jadi
        menyentuh sudah cukup -- menunggu sampai benar-benar lewat berarti
        memesan satu hari terlambat setiap kali.
        """
        r = lapisan(current_stock=40, available_stock=40)
        assert r["action_status"] == d.STATUS_PERLU_REORDER
        assert r["recommended_order_qty"] > 0

    def test_3_stok_di_bawah_titik_pesan_perlu_reorder(self):
        r = lapisan(current_stock=30, available_stock=30)
        assert r["action_status"] == d.STATUS_PERLU_REORDER
        assert r["recommended_order_qty"] == 10          # 40 - 30

    def test_4_stok_habis_sebelum_lead_time_berarti_risiko_stockout(self):
        """12 unit pada laju 2/hari habis dalam 6 hari; kiriman 7 hari."""
        r = lapisan(current_stock=12, available_stock=12)
        assert r["action_status"] == d.STATUS_RISIKO_STOCKOUT
        assert r["priority"] == d.PRIORITAS_TINGGI
        assert r["recommended_order_qty"] == 28          # 40 - 12

    def test_5_stok_nol_berarti_risiko_stockout(self):
        r = lapisan(current_stock=0, available_stock=0)
        assert r["action_status"] == d.STATUS_RISIKO_STOCKOUT
        assert r["recommended_order_qty"] == 40

    def test_5b_stok_nol_tanpa_pemakaian_tetap_risiko_stockout(self):
        """Rak kosong tidak menjadi kurang gawat karena tidak ada pengeluaran."""
        r = lapisan(current_stock=0, available_stock=0, avg_daily_usage=0,
                    keluar_harian=[0] * 30, hari_aktif=0)
        assert r["action_status"] == d.STATUS_RISIKO_STOCKOUT

    def test_6_prakiraan_tinggi_dengan_stok_aman_tidak_memicu_reorder(self):
        """
        Prakiraan periode 90 hari sama sekali tidak menyentuh status. Barang
        yang stoknya masih jauh di atas ambang tetap AMAN dan tetap nol,
        walaupun kebutuhan tiga bulannya jauh lebih besar dari stoknya.
        """
        r = lapisan(current_stock=500, available_stock=500, forecast_days=90)
        assert r["action_status"] == d.STATUS_AMAN
        assert r["recommended_order_qty"] == 0

    def test_6b_periode_prakiraan_tidak_menggeser_satu_pun_angka_keputusan(self):
        """
        Invarian yang paling mudah rusak: menggeser dropdown periode di layar
        Prakiraan tidak boleh mengubah apa pun di layar Pemesanan Ulang.
        """
        acuan = lapisan(forecast_days=7)
        for hari in (14, 30, 60, 90):
            lain = lapisan(forecast_days=hari)
            for k in ("action_status", "priority", "recommended_order_qty",
                      "effective_reorder_point", "order_up_to_level",
                      "decision_horizon_usage"):
                assert acuan[k] == lain[k], (k, hari)

    def test_7_prakiraan_rendah_dengan_stok_aman_tetap_aman(self):
        r = lapisan(current_stock=500, available_stock=500,
                    avg_daily_usage=0.1, keluar_harian=[0.1] * 30)
        assert r["action_status"] == d.STATUS_AMAN
        assert r["recommended_order_qty"] == 0

    def test_8_jumlah_tidak_pernah_negatif(self):
        """
        Disapu sepanjang seluruh rentang stok, masa tunggu, dan cadangan --
        termasuk masa tunggu panjang, tempat sasaran pengisian bisa jatuh di
        bawah stok yang ada bila penjepitnya hilang.
        """
        for stok in range(0, 300, 7):
            for lead in (0, 1, 7, 30, 90, None):
                for safety in (0, 10, 100):
                    r = lapisan(current_stock=stok, available_stock=stok,
                                lead_time_days=lead, safety_stock=safety)
                    qty = r["recommended_order_qty"]
                    assert qty is None or qty >= 0, (stok, lead, safety, qty)

    def test_9_tidak_ada_lagi_rumus_stok_maksimum(self):
        """
        `maximum_stock` tidak lagi menjadi parameter lapisan keputusan sama
        sekali, jadi rumus `maximum_stock - current_stock` mustahil hidup lagi
        di jalur ini -- diperiksa pada tanda tangan fungsinya, bukan pada
        keluarannya, karena keluaran yang kebetulan sama tidak membuktikan apa
        pun.
        """
        import inspect
        tanda = inspect.signature(d.lapisan_keputusan).parameters
        assert "maximum_stock" not in tanda
        assert not hasattr(d, "saran_qty")
        sumber = inspect.getsource(d.saran_qty_reorder)
        assert "maximum_stock" not in sumber

    def test_10_konsisten_dengan_prakiraan(self):
        """
        Satu laju pemakaian menghasilkan kedua lapisan. Kebutuhan horizon
        keputusan harus persis laju x horizon, dan kebutuhan periode prakiraan
        persis laju x periode -- keduanya dari angka yang sama, hanya rentang
        yang berbeda.
        """
        r = lapisan(avg_daily_usage=2.0, forecast_days=30)
        assert r["decision_horizon_days"] == d.HORIZON_KEPUTUSAN
        assert r["decision_horizon_usage"] == 2.0 * d.HORIZON_KEPUTUSAN
        # Titik pesan efektif memakai laju yang sama.
        assert r["lead_time_demand"] == 2.0 * 7


class TestPrinsip:
    """Empat prinsip yang dituliskan pada spesifikasi, sebagai uji."""

    def test_aman_tidak_pernah_terlihat_sebagai_masalah(self):
        """AMAN selalu prioritas rendah dan selalu berjumlah nol."""
        for stok in (41, 60, 100, 5_000):
            r = lapisan(current_stock=stok, available_stock=stok)
            if r["action_status"] == d.STATUS_AMAN:
                assert r["priority"] == d.PRIORITAS_RENDAH, stok
                assert r["recommended_order_qty"] == 0, stok

    def test_perlu_reorder_bukan_berarti_stok_habis(self):
        """
        Barang berstatus perlu reorder masih punya stok, dan masih punya hari
        tersisa yang lebih panjang daripada masa tunggu -- itulah bedanya dari
        risiko stockout.
        """
        r = lapisan(current_stock=30, available_stock=30)
        assert r["action_status"] == d.STATUS_PERLU_REORDER
        assert r["available_stock_int"] > 0
        assert r["days_of_cover"] > 7

    def test_risiko_stockout_selalu_prioritas_tertinggi(self):
        for stok in (0, 1, 5, 14):
            r = lapisan(current_stock=stok, available_stock=stok)
            assert r["action_status"] == d.STATUS_RISIKO_STOCKOUT, stok
            assert r["priority"] == d.PRIORITAS_TINGGI, stok

    def test_status_bertindak_selalu_disertai_jumlah(self):
        """Tidak ada satu pun titik yang mendesak tetapi berjumlah nol."""
        for stok in range(0, 200):
            r = lapisan(current_stock=stok, available_stock=stok)
            qty = r["recommended_order_qty"]
            if r["action_status"] == d.STATUS_AMAN:
                assert qty == 0, stok
            else:
                assert qty is None or qty > 0, stok

    def test_satu_satunya_nol_yang_bukan_aman_adalah_barang_tanpa_pemakaian(self):
        """
        Barang yang tidak pernah diambil dan kebetulan duduk di titik pesannya
        memang tidak perlu dipesan: tidak ada yang akan terpakai. Nol di situ
        jawaban yang benar, bukan kontradiksi -- dan ia SATU-SATUNYA.
        """
        r = lapisan(current_stock=40, available_stock=40, avg_daily_usage=0,
                    keluar_harian=[0] * 30, hari_aktif=0)
        assert r["action_status"] == d.STATUS_PERLU_REORDER
        assert r["recommended_order_qty"] == 0
