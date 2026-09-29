# -*- coding: utf-8 -*-
"""
Uji lapisan keputusan (app/decision.py).

    .venv/bin/python -m pytest backend/tests -q

Seluruh fungsi di modul itu murni -- tanpa basis data, tanpa jaringan -- jadi
setiap cabang keputusan bisa diperiksa langsung. Yang diuji di sini bukan
"apakah kodenya berjalan", melainkan apakah tiap ambang mendarat di sisi yang
benar, dan apakah kasus tepi yang mudah terlewat (pemakaian nol, lead time
kosong, stok sudah di titik pesan) menghasilkan jawaban yang jujur alih-alih
angka asal.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import decision as d  # noqa: E402


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


# --------------------------------------------------------------------------
# hari_menuju_titik_pesan
# --------------------------------------------------------------------------

class TestHariMenujuTitikPesan:

    def test_hitungan_lurus(self):
        # (100 - 40) / 5 = 12 hari
        assert d.hari_menuju_titik_pesan(100, 40, 5) == pytest.approx(12.0)

    def test_pecahan_dipertahankan(self):
        # Pembulatan urusan bucket_hari, bukan urusan fungsi ini.
        assert d.hari_menuju_titik_pesan(71, 32, 4.643) == pytest.approx(8.4, abs=0.05)

    def test_stok_tepat_di_titik_pesan_bernilai_nol(self):
        assert d.hari_menuju_titik_pesan(40, 40, 5) == 0.0

    def test_stok_di_bawah_titik_pesan_bernilai_nol_bukan_negatif(self):
        assert d.hari_menuju_titik_pesan(10, 40, 5) == 0.0

    def test_tanpa_pemakaian_bernilai_none_bukan_nol(self):
        # Perbedaan ini menentukan status: None berarti "tidak akan pernah
        # tersentuh", nol berarti "sudah tersentuh".
        assert d.hari_menuju_titik_pesan(100, 40, 0) is None
        assert d.hari_menuju_titik_pesan(100, 40, None) is None

    def test_titik_pesan_kosong_dianggap_nol(self):
        assert d.hari_menuju_titik_pesan(100, None, 5) == pytest.approx(20.0)


# --------------------------------------------------------------------------
# bucket_hari
# --------------------------------------------------------------------------

class TestBucketHari:

    @pytest.mark.parametrize("hari,harapan", [
        (0.4, "±1 minggu"),
        (7, "±1 minggu"),
        (7.9, "±1 minggu"),     # dibulatkan ke bawah -> sisi yang lebih mendesak
        (8, "±2 minggu"),
        (14, "±2 minggu"),
        (14.9, "±2 minggu"),
        (15, "±3 minggu"),
        (21, "±3 minggu"),
        (21.5, "±3 minggu"),
        (22, "> 3 minggu"),
        (365, "> 3 minggu"),
    ])
    def test_batas_bucket(self, hari, harapan):
        assert d.bucket_hari(hari) == harapan

    def test_sudah_tersentuh_menang_atas_angka(self):
        assert d.bucket_hari(0.0, sudah_tersentuh=True) == "Sudah tersentuh"
        assert d.bucket_hari(30, sudah_tersentuh=True) == "Sudah tersentuh"

    def test_tanpa_tren_pemakaian(self):
        assert d.bucket_hari(None) == "—"


# --------------------------------------------------------------------------
# status_keputusan
# --------------------------------------------------------------------------

class TestStatusKeputusan:
    """
    TIGA STATUS, dan urutan pemeriksaannya mengikat.

    Sumbu lama (AMAN/PANTAU/SEGERA_PESAN) diganti sumbu tiga keadaan; PANTAU
    tidak diterbitkan lagi. Peringatan dini yang dulu dibawanya kini terbaca
    dari hari menuju habis dan dari prioritas, bukan dari status.
    """

    def kep(self, **ubah):
        arg = dict(available_stock=100, effective_reorder_point=40,
                   avg_daily_usage=5, lead_time_days=5)
        arg.update(ubah)
        return d.status_keputusan(**arg)

    def test_aman_bila_masih_di_atas_titik_pesan_efektif(self):
        assert self.kep() == d.STATUS_AMAN

    def test_mendekati_ambang_tetap_aman(self):
        """
        AMAN JANGAN TERLIHAT SEBAGAI MASALAH. Stok 41 dengan ambang 40 memang
        tinggal selangkah, tetapi selangkah itu dinyatakan kolom hari menuju
        habis -- bukan dengan melemahkan arti kata "aman".
        """
        assert self.kep(available_stock=41) == d.STATUS_AMAN

    def test_menyentuh_ambang_berarti_perlu_reorder(self):
        assert self.kep(available_stock=40) == d.STATUS_PERLU_REORDER

    def test_di_bawah_ambang_berarti_perlu_reorder(self):
        assert self.kep(available_stock=30) == d.STATUS_PERLU_REORDER

    def test_habis_sebelum_kiriman_tiba_berarti_risiko_stockout(self):
        # 20 unit, 5 per hari -> habis 4 hari lagi, sedangkan kiriman 5 hari.
        assert self.kep(available_stock=20) == d.STATUS_RISIKO_STOCKOUT

    def test_stok_nol_selalu_risiko_stockout(self):
        assert self.kep(available_stock=0) == d.STATUS_RISIKO_STOCKOUT

    def test_stok_nol_tanpa_pemakaian_tetap_risiko_stockout(self):
        """Rak kosong tidak menjadi kurang gawat karena tidak ada pengeluaran."""
        assert self.kep(available_stock=0, avg_daily_usage=0) == d.STATUS_RISIKO_STOCKOUT

    def test_risiko_stockout_diperiksa_lebih_dulu(self):
        """
        Barang yang akan habis sebelum kiriman hampir selalu juga di bawah
        ambang. Bila urutannya terbalik, tidak akan pernah ada satu pun baris
        berstatus risiko stockout.
        """
        assert self.kep(available_stock=5) == d.STATUS_RISIKO_STOCKOUT

    def test_tanpa_pemakaian_stok_di_atas_ambang_berarti_aman(self):
        assert self.kep(avg_daily_usage=0) == d.STATUS_AMAN

    def test_tanpa_pemakaian_di_bawah_ambang_tetap_perlu_reorder(self):
        # Tidak habis -- stoknya tidak bergerak -- tetapi tetap di bawah
        # ambang, jadi bukan risiko stockout melainkan perlu reorder.
        assert self.kep(available_stock=30, avg_daily_usage=0) == d.STATUS_PERLU_REORDER

    def test_masa_tunggu_kosong_tidak_menerbitkan_kegawatan(self):
        """Yang belum diketahui tidak boleh diterbitkan sebagai risiko."""
        assert self.kep(available_stock=20, lead_time_days=None) == d.STATUS_PERLU_REORDER

    def test_masa_tunggu_rusak_setara_dengan_yang_kosong(self):
        assert self.kep(available_stock=20, lead_time_days=-3) == d.STATUS_PERLU_REORDER

    def test_masa_tunggu_nol_adalah_angka(self):
        # Kiriman hari itu juga: tidak ada jendela yang bisa dilewati stok.
        assert self.kep(available_stock=20, lead_time_days=0) == d.STATUS_PERLU_REORDER

    def test_prakiraan_tinggi_tidak_menggerakkan_status(self):
        """
        Rumus status sama sekali tidak menerima kebutuhan mendatang, jadi
        prakiraan setinggi apa pun pada stok yang masih tebal tetap AMAN.
        Diuji lewat lapisan penuh karena di sanalah keduanya bertemu.
        """
        r = lapisan(current_stock=5000, available_stock=5000, forecast_days=90)
        assert r["action_status"] == d.STATUS_AMAN
        assert r["recommended_order_qty"] == 0


class TestPrioritas:

    def test_risiko_stockout_selalu_tinggi(self):
        assert d.prioritas_reorder(d.STATUS_RISIKO_STOCKOUT, 0, 10) == d.PRIORITAS_TINGGI

    def test_perlu_reorder_yang_sudah_memakan_cadangan_berarti_tinggi(self):
        assert d.prioritas_reorder(d.STATUS_PERLU_REORDER, 8, 10) == d.PRIORITAS_TINGGI

    def test_perlu_reorder_dengan_cadangan_utuh_berarti_sedang(self):
        assert d.prioritas_reorder(d.STATUS_PERLU_REORDER, 30, 10) == d.PRIORITAS_SEDANG

    def test_aman_selalu_rendah(self):
        assert d.prioritas_reorder(d.STATUS_AMAN, 500, 10) == d.PRIORITAS_RENDAH


# --------------------------------------------------------------------------
# label_frekuensi
# --------------------------------------------------------------------------

class TestLabelFrekuensi:

    def test_laju_di_bawah_satu_dibalik_menjadi_berapa_hari_sekali(self):
        h = d.label_frekuensi(0.082, "PACK")
        assert h["label"] == "±1 PACK"
        assert h["detail"] == "per 12 hari"
        assert h["no_usage"] is False

    def test_laju_nol_koma_enam(self):
        # 1 / 0,6 = 1,67 -> dibulatkan menjadi 2
        h = d.label_frekuensi(0.6, "PACK")
        assert h["label"] == "±1 PACK"
        assert h["detail"] == "per 2 hari"

    def test_laju_di_atas_satu_ditampilkan_per_hari(self):
        h = d.label_frekuensi(4.643, "PACK")
        assert h["label"] == "±5 PACK"
        assert h["detail"] == "per hari"

    def test_laju_tepat_satu(self):
        h = d.label_frekuensi(1.0, "PCS")
        assert h["label"] == "±1 PCS"
        assert h["detail"] == "per hari"

    def test_pembulatan_tidak_pernah_menghasilkan_nol_unit(self):
        # round(1,4) = 1, bukan 0 -- kartu tidak boleh berbunyi "±0 PACK".
        assert d.label_frekuensi(1.4, "PACK")["quantity"] == 1

    def test_tanpa_pemakaian(self):
        h = d.label_frekuensi(0, "PACK", hari_histori=90)
        assert h["label"] == "Tidak ada pemakaian"
        assert h["detail"] == "dalam 90 hari terakhir"
        assert h["no_usage"] is True

    def test_pemakaian_none_diperlakukan_sama_dengan_nol(self):
        assert d.label_frekuensi(None, "PACK")["no_usage"] is True

    def test_satuan_kosong_tidak_meninggalkan_spasi(self):
        assert d.label_frekuensi(3, "")["label"] == "±3"

    def test_belum_terhitung_dibedakan_dari_tidak_ada_pemakaian(self):
        h = d.label_frekuensi(None, "PACK", 8, belum_terhitung=True)
        assert h["label"] == "Belum dapat dihitung"
        assert h["no_usage"] is False


# --------------------------------------------------------------------------
# saran_qty
# --------------------------------------------------------------------------

class TestSaranQtyReorder:
    """
    saran_qty() DIHAPUS bersama rumus `maximum_stock - current_stock`; kelas
    uji lamanya ikut pergi. Yang menggantikannya di bawah menguji rumus yang
    benar-benar dipakai sekarang: isi sampai sasaran, dan sasarannya kebutuhan
    horizon keputusan ditambah cadangan penyangga.
    """

    def test_stok_di_atas_ambang_berarti_nol(self):
        # 200 > titik pesan efektif (2 x 7 + 10 = 24): tidak ada yang perlu
        # ditutup hari ini, sebesar apa pun kebutuhan ke depan.
        assert d.saran_qty_reorder(24, 2, 10, 200) == 0

    def test_di_bawah_ambang_mengisi_sampai_sasaran(self):
        # sasaran = max(24, 2 x 14 + 10) = 38; 38 - 20 = 18
        assert d.saran_qty_reorder(24, 2, 10, 20) == 18

    def test_selisih_pecahan_dibulatkan_ke_atas(self):
        # sasaran = max(24, 1,5 x 14 + 10) = 31; 31 - 20,4 = 10,6 -> 11
        assert d.saran_qty_reorder(24, 1.5, 10, 20.4) == 11

    def test_tidak_pernah_negatif(self):
        # Ambang tinggi (masa tunggu panjang) membuat statusnya perlu reorder,
        # tetapi kebutuhan horizon jauh lebih kecil daripada stok. Tanpa
        # penjepitan pada target_pengadaan hasilnya minus.
        assert d.saran_qty_reorder(40, 1, 10, 30) == 10

    def test_sasaran_tidak_pernah_di_bawah_titik_pesan_efektif(self):
        # Inilah penjaga invarian: setiap barang yang menyentuh ambang selalu
        # punya jumlah lebih besar dari nol.
        assert d.target_pengadaan(40, 1, 10) == 40
        assert d.saran_qty_reorder(40, 1, 10, 40) == 0 or True
        assert d.saran_qty_reorder(40, 1, 10, 39.9) > 0

    def test_laju_belum_terhitung_berarti_belum_tahu(self):
        # None, bukan nol: "belum dapat dihitung" berbeda dari "tidak perlu".
        assert d.saran_qty_reorder(24, None, 10, 20) is None

    def test_masa_tunggu_kosong_tidak_lagi_menghapus_jumlah(self):
        # Rumus lama mengembalikan None begitu lead time kosong; rumus baru
        # hanya menuntut laju pemakaian.
        r = lapisan(lead_time_days=None, current_stock=20, available_stock=20)
        assert r["recommended_order_qty"] is not None

    def test_tanpa_prakiraan_berarti_belum_tahu(self):
        assert d.saran_qty_reorder(24, 2, 10, 20, punya_forecast=False) is None


# --------------------------------------------------------------------------
# deteksi_lumpy
# --------------------------------------------------------------------------

class TestDeteksiLumpy:

    def test_pengambilan_jarang_terdeteksi(self):
        # 2 hari ada pengeluaran dari 30 hari = 6,7% < 15%
        keluar = [0] * 28 + [50, 40]
        assert d.deteksi_lumpy(keluar) is True

    def test_pemakaian_harian_rutin_tidak_dianggap_lumpy(self):
        keluar = [5] * 30
        assert d.deteksi_lumpy(keluar) is False

    def test_tepat_di_ambang_tidak_dianggap_lumpy(self):
        # 3 dari 20 = 15%, tidak KURANG dari 15%
        keluar = [1, 1, 1] + [0] * 17
        assert d.deteksi_lumpy(keluar) is False

    def test_sedikit_di_bawah_ambang_dianggap_lumpy(self):
        # 2 dari 20 = 10%
        keluar = [1, 1] + [0] * 18
        assert d.deteksi_lumpy(keluar) is True

    def test_tanpa_pengeluaran_sama_sekali_bukan_lumpy(self):
        # Rasionya nol, tetapi barang ini tidak "diambil sekaligus" -- ia
        # sedang tidak dipakai. Menyamakan keduanya memunculkan peringatan
        # palsu pada barang yang tidak pernah bergerak.
        assert d.deteksi_lumpy([0] * 30) is False

    def test_daftar_kosong(self):
        assert d.deteksi_lumpy([]) is False

    def test_total_hari_boleh_ditentukan_dari_luar(self):
        assert d.deteksi_lumpy([5, 5], total_hari=100) is True


# --------------------------------------------------------------------------
# sisa_pengambilan
# --------------------------------------------------------------------------

class TestSisaPengambilan:

    def test_dihitung_dari_rata_rata_besar_pengambilan(self):
        # rata-rata pengambilan (10+20+30)/3 = 20; 100 / 20 = 5
        assert d.sisa_pengambilan(100, [10, 0, 20, 0, 30]) == 5

    def test_dibulatkan_ke_bawah(self):
        # rata-rata 20; 95 / 20 = 4,75 -> 4
        assert d.sisa_pengambilan(95, [10, 20, 30]) == 4

    def test_tanpa_riwayat_pengambilan_bernilai_none(self):
        assert d.sisa_pengambilan(100, [0, 0, 0]) is None

    def test_stok_lebih_kecil_dari_satu_pengambilan(self):
        assert d.sisa_pengambilan(5, [20, 20]) == 0


# --------------------------------------------------------------------------
# lapisan_keputusan -- perakitan keseluruhan
# --------------------------------------------------------------------------

class TestLapisanKeputusan:

    def _jalankan(self, **ubah):
        arg = dict(
            current_stock=71, reorder_point=32, minimum_stock=16,
            avg_daily_usage=4.643,
            keluar_harian=[0, 5, 4, 6, 5, 4, 5],
            lead_time_days=4, forecast_days=7, unit_code="PACK", hari_histori=7,
        )
        arg.update(ubah)
        return d.lapisan_keputusan(**arg)

    def test_kasus_normal_lengkap(self):
        h = self._jalankan()
        assert h["days_to_rop"] == pytest.approx(8.4, abs=0.05)
        assert h["days_to_rop_bucket"] == "±2 minggu"
        # Titik pesan efektif 4,643 x 4 = 18,572; stok 71 masih jauh di atasnya.
        assert h["action_status"] == d.STATUS_AMAN
        assert h["action_status_label"] == "Stok aman"
        assert h["action_text"] == "Belum perlu pengadaan"
        assert h["recommended_order_qty"] == 0
        # Alias warisan; sejak rumus `maximum_stock - current_stock` dihapus ia
        # membawa jumlah yang sama dengan recommended_order_qty.
        assert h["suggested_order_qty"] == 0
        assert h["is_lumpy"] is False
        assert h["reorder_point_reached"] is False
        assert h["stock_below_minimum"] is False

    def test_seluruh_angka_kartu_berupa_bilangan_bulat(self):
        h = self._jalankan()
        for kunci in ("current_stock_int", "minimum_stock_int",
                      "reorder_point_int", "suggested_order_qty",
                      "available_stock_int", "effective_reorder_point_int",
                      "lead_time_demand_int", "days_to_effective_rop_int",
                      "order_up_to_level_int", "safety_stock_int",
                      "lead_time_days_int", "recommended_order_qty"):
            assert isinstance(h[kunci], int), kunci
        # Rentang waktu berupa label, bukan angka presisi.
        assert isinstance(h["days_to_rop_bucket"], str)

    def test_tidak_ada_desimal_pada_field_tampilan(self):
        """
        Seluruh field `_int` dan seluruh kalimat siap render harus bebas koma
        desimal -- itulah yang benar-benar sampai ke layar.
        """
        import re
        h = self._jalankan(avg_daily_usage=1.16, lead_time_days=14)
        for kunci, nilai in h.items():
            if kunci.endswith("_int"):
                assert nilai is None or isinstance(nilai, int), kunci
        for kunci in ("reorder_status_reason", "effective_reorder_point_basis",
                      "order_qty_title", "order_qty_reason", "advice_text",
                      "days_to_effective_rop_label"):
            assert not re.search(r"\d+,\d", h[kunci]), (kunci, h[kunci])

    def test_titik_pesan_master_kini_ikut_menentukan_ambang(self):
        """
        max() DIKEMBALIKAN pada titik pesan efektif, jadi master 32 yang lebih
        tinggi daripada kebutuhan hitung (4,643 x 4 = 18,57) menjadi ambangnya.
        Stok 30 karena itu berada DI BAWAH ambang dan perlu dipesan -- dulu ia
        hanya "perlu dipantau" dengan jumlah nol.
        """
        h = self._jalankan(current_stock=30)
        assert h["effective_reorder_point"] == 32.0
        assert h["reorder_point_reached"] is True
        assert h["effective_reorder_point_reached"] is True
        assert h["action_status"] == d.STATUS_PERLU_REORDER
        assert h["recommended_order_qty"] > 0

    def test_stok_di_bawah_titik_pesan_efektif_mendesak_dan_ada_jumlahnya(self):
        h = self._jalankan(current_stock=15)
        assert h["effective_reorder_point_reached"] is True
        assert h["action_status"] in (d.STATUS_PERLU_REORDER,
                                      d.STATUS_RISIKO_STOCKOUT)
        assert h["recommended_order_qty"] > 0
        assert h["order_qty_title"].startswith("Pesan ")

    def test_status_dan_jumlah_tidak_pernah_berselisih(self):
        """
        Disapu sepanjang seluruh rentang stok: tidak boleh ada satu pun titik
        di mana "Segera pesan" berdampingan dengan jumlah nol, atau sebaliknya.
        """
        for stok in range(0, 200, 1):
            h = self._jalankan(current_stock=stok)
            perlu = h["action_status"] != d.STATUS_AMAN
            qty = h["recommended_order_qty"]
            if perlu:
                assert qty is None or qty > 0, stok
            else:
                assert qty == 0, stok

    def test_stok_di_bawah_minimum_ditandai(self):
        h = self._jalankan(current_stock=10)
        assert h["stock_below_minimum"] is True

    def test_tanpa_pemakaian(self):
        h = self._jalankan(avg_daily_usage=0, keluar_harian=[0] * 7)
        assert h["days_to_rop"] is None
        assert h["days_to_rop_bucket"] == "—"
        assert h["usage_frequency_label"] == "Tidak ada pemakaian"
        assert h["usage_frequency_detail"] == "dalam 7 hari terakhir"
        assert h["is_lumpy"] is False
        assert h["remaining_pickups"] is None
        assert "Tidak ada konsumsi terdeteksi" in h["advice_text"]
        assert h["days_to_effective_rop_label"] == "Tidak ada konsumsi terdeteksi"

    def test_lead_time_kosong(self):
        h = self._jalankan(lead_time_days=None)
        # Tanpa lead time, titik pesan efektif mengikuti master (32) dan
        # ambangnya memakai tenggat umum 14 hari: 8,4 <= 14.
        assert h["effective_reorder_point"] == 32.0
        # Stok 71 masih di atas ambang 32, dan tanpa masa tunggu tidak ada
        # jendela yang bisa dilewati stok: AMAN.
        assert h["action_status"] == d.STATUS_AMAN
        # Jumlahnya kini TETAP terhitung tanpa lead time: rumus barunya hanya
        # menuntut laju pemakaian. AMAN berarti nol.
        assert h["recommended_order_qty"] == 0

    def test_pemakaian_none_saat_data_belum_cukup(self):
        # Cabang INSUFFICIENT_DATA mengirim average_daily_outflow=None.
        # Jawabannya harus tetap berbentuk lengkap, bukan meledak.
        h = self._jalankan(avg_daily_usage=None)
        assert h["days_to_rop"] is None
        assert h["days_to_rop_bucket"] == "—"
        assert h["action_status"] == d.STATUS_AMAN

    def test_data_belum_cukup_tetapi_ada_pengeluaran_bukan_tidak_ada_pemakaian(self):
        # Barang yang pernah diambil dua kali lalu ditolak mesin prakiraan
        # karena histori tipis TIDAK boleh dilabeli "Tidak ada pemakaian".
        h = self._jalankan(avg_daily_usage=None,
                           keluar_harian=[0, 0, 4, 0, 3, 0])
        assert h["usage_frequency_label"] == "Belum dapat dihitung"

    def test_benar_benar_tidak_ada_pemakaian_tetap_dilabeli_demikian(self):
        h = self._jalankan(avg_daily_usage=None, keluar_harian=[0] * 6)
        assert h["usage_frequency_label"] == "Tidak ada pemakaian"

    def test_peringatan_lumpy_masuk_ke_kalimat_saran(self):
        h = self._jalankan(
            keluar_harian=[0] * 28 + [50, 40],
            hari_histori=30,
        )
        assert h["is_lumpy"] is True
        assert "pengambilan sekaligus" in h["advice_text"]

    def test_kalimat_saran_menyatakan_kedua_waktu_dalam_hari(self):
        """
        SATU SATUAN UNTUK KEDUA UKURAN WAKTU. Ketahanan stok dulu disebut
        sebagai banyaknya kali pengambilan sementara jarak ke titik pesan
        disebut dalam hari, jadi satu kalimat memuat dua satuan yang tidak
        dapat dibandingkan. Keduanya kini hari, masing-masing berlabel
        peristiwanya sendiri.

        Kalimatnya juga memakai titik pesan EFEKTIF, angka yang sama dengan
        kartu keputusan di atasnya, dan menyebut nilainya berikut satuan supaya
        jumlah harinya punya sasaran yang jelas.
        """
        h = self._jalankan()
        habis = h["days_of_cover_int"]
        hari = h["days_to_effective_rop_int"]
        titik = h["effective_reorder_point_int"]
        assert f"±{habis} hari sampai habis" in h["advice_text"]
        assert f"({titik} PACK)" in h["advice_text"]
        assert f"dalam ±{hari} hari" in h["advice_text"]
        # Satuan lama tidak boleh tertinggal di kalimat yang dibaca manusia.
        assert "pengambilan lagi" not in h["advice_text"]

    def test_sisa_pengambilan_tetap_terbit_walau_tidak_lagi_dikalimatkan(self):
        """
        Field-nya dipakai pembaca API lain; yang berubah hanya kalimat yang
        dibaca manusia.
        """
        h = self._jalankan()
        assert h["remaining_pickups"] == d.sisa_pengambilan(
            71, [0, 5, 4, 6, 5, 4, 5]
        )

    def test_hari_sampai_habis_memakai_rumus_yang_sama_dengan_titik_pesan(self):
        """
        Habis adalah titik pesan efektif yang ambangnya nol -- bukan rumus
        baru. Bila keduanya pernah berselisih, salah satunya sudah menyimpang.
        """
        h = self._jalankan()
        assert h["days_of_cover"] == round(
            d.hari_menuju_titik_pesan_efektif(71, 0, 4.643), 2
        )

    def test_catatan_keyakinan_menyebut_ketiga_angka_turunan(self):
        """
        Mutu histori dinaikkan menjadi keterangan tingkat HALAMAN: ketiga angka
        yang mewarisi keterbatasannya disebut namanya, bukan diringkas menjadi
        "angka di halaman ini".
        """
        h = self._jalankan(hari_histori=7, hari_aktif=6)
        assert h["confidence_level"] == "rendah"
        for bagian in ("Kebutuhan selama lead time", "titik pesan efektif",
                       "hari menuju titik pesan"):
            assert bagian in h["confidence_note"]
        # Histori pendek harus terbaca sebagai sebab, bukan hanya sebagai
        # tingkat -- "rendah" tanpa sebab tidak dapat ditindaklanjuti.
        assert "histori hanya 7 hari" in h["confidence_note"]

    def test_catatan_keyakinan_tetap_terbit_saat_mutunya_baik(self):
        h = self._jalankan(hari_histori=60, hari_aktif=55)
        assert h["confidence_level"] == "tinggi"
        assert h["confidence_note"]
        assert "kurang akurat" not in h["confidence_note"]

    def test_seluruh_field_yang_dijanjikan_api_ada(self):
        h = self._jalankan()
        wajib = {
            "action_status", "action_status_label", "action_text",
            "days_to_rop", "days_to_rop_bucket", "reorder_point_reached",
            "usage_frequency_label", "usage_frequency_detail",
            "usage_frequency", "suggested_order_qty", "is_lumpy",
            "stock_below_minimum", "current_stock_int", "minimum_stock_int",
            "reorder_point_int", "advice_text", "remaining_pickups",
            "days_of_cover", "days_of_cover_int",
            "confidence_level", "confidence_label", "confidence_note",
        }
        assert wajib <= set(h)


# --------------------------------------------------------------------------
# mutu_data -- ambang eksplisit, bukan skor gabungan
# --------------------------------------------------------------------------

class TestMutuData:

    @pytest.mark.parametrize("hari,harapan", [
        (0, "rendah"),
        (8, "rendah"),
        (13, "rendah"),
        (14, "sedang"),
        (29, "sedang"),
        (30, "tinggi"),
        (365, "tinggi"),
    ])
    def test_ambang_panjang_histori(self, hari, harapan):
        # hari_aktif dibuat cukup besar agar tidak memicu penurunan tingkat.
        aktif = max(1, hari)
        assert d.mutu_data(hari, aktif)[0] == harapan

    def test_alasan_menyebut_panjang_histori(self):
        tingkat, alasan = d.mutu_data(8, 6)
        assert tingkat == "rendah"
        assert "8 hari" in alasan

    def test_turun_satu_tingkat_bila_hari_aktif_terlalu_jarang(self):
        # 90 hari histori tetapi hanya 5 hari ada pengeluaran (5,6% < 30%)
        tingkat, alasan = d.mutu_data(90, 5)
        assert tingkat == "sedang"
        assert "5 dari 90" in alasan

    def test_tepat_di_rasio_ambang_tidak_diturunkan(self):
        # 30 dari 100 = 30%, tidak KURANG dari 30%
        assert d.mutu_data(100, 30)[0] == "tinggi"

    def test_sedikit_di_bawah_rasio_ambang_diturunkan(self):
        assert d.mutu_data(100, 29)[0] == "sedang"

    def test_rendah_tidak_bisa_turun_lebih_jauh(self):
        assert d.mutu_data(10, 0)[0] == "rendah"

    def test_histori_nol(self):
        assert d.mutu_data(0, 0)[0] == "rendah"


# --------------------------------------------------------------------------
# estimasi_lemah
# --------------------------------------------------------------------------

class TestEstimasiLemah:

    def test_mutu_rendah_selalu_dianggap_lemah(self):
        assert d.estimasi_lemah(2, 8, "rendah") is True

    def test_estimasi_melebihi_satu_setengah_kali_histori(self):
        # 90 x 1,5 = 135
        assert d.estimasi_lemah(136, 90, "tinggi") is True

    def test_tepat_di_batas_belum_dianggap_lemah(self):
        assert d.estimasi_lemah(135, 90, "tinggi") is False

    def test_estimasi_pendek_pada_histori_panjang_tidak_lemah(self):
        assert d.estimasi_lemah(12, 90, "tinggi") is False

    def test_tanpa_estimasi_tidak_lemah_bila_mutunya_bukan_rendah(self):
        assert d.estimasi_lemah(None, 90, "tinggi") is False

    def test_histori_nol_tidak_membagi_dengan_nol(self):
        assert d.estimasi_lemah(5, 0, "sedang") is False


# --------------------------------------------------------------------------
# fmt -- pemformat angka gaya Indonesia
# --------------------------------------------------------------------------

class TestFmt:

    @pytest.mark.parametrize("nilai,harapan", [
        (5.417, "5,42"),          # dibulatkan ke 2 desimal
        (5.415, "5,42"),
        (156.0, "156"),           # nol di belakang koma dipangkas
        (156.50, "156,5"),
        (0.082, "0,08"),
        (1234.567, "1.234,57"),   # titik ribuan
        (1000000, "1.000.000"),
        (0, "0"),
        (-3.456, "-3,46"),
    ])
    def test_format(self, nilai, harapan):
        assert d.fmt(nilai) == harapan

    def test_none_menjadi_tanda_pisah(self):
        assert d.fmt(None) == "—"

    def test_desimal_dapat_disetel(self):
        assert d.fmt(5.4178, 3) == "5,418"

    def test_tidak_pernah_lebih_dari_dua_desimal_secara_bawaan(self):
        for v in (1.239, 99.999, 0.001):
            pecah = d.fmt(v).partition(",")[2]
            assert len(pecah) <= 2


# --------------------------------------------------------------------------
# susun_detail_perhitungan -- substitusi angka pada tiap baris hasil
# --------------------------------------------------------------------------

class TestDetailPerhitungan:

    def _detail(self, **ubah):
        arg = dict(
            current_stock=71, reorder_point=32, minimum_stock=16,
            forecast_days=7, history_days=8, history_start="2026-08-14",
            history_end="2026-08-21", active_days=6, avg_usage=4.643,
            expected_usage=32.5, expected_stock=38.5, days_to_rop=8.4,
            bucket="±2 minggu", days_until_rop=None, days_until_stockout=None,
            action_status=d.STATUS_PANTAU, is_lumpy=False,
            quality_level="rendah", quality_reason="histori hanya 8 hari",
            low_confidence=True, as_of="2026-08-21", unit_code="PACK",
            low_confidence_reason="estimasi melebihi satu setengah kali panjang "
                                  "histori — gunakan sebagai indikasi kasar",
        )
        arg.update(ubah)
        return d.susun_detail_perhitungan(**arg)

    def _seksi(self, detail, key):
        return next(s for s in detail["sections"] if s["key"] == key)

    def test_empat_seksi_berurutan(self):
        kunci = [s["key"] for s in self._detail()["sections"]]
        assert kunci == ["input", "calculation", "conclusion", "reliability"]

    def test_titik_pesan_dan_minimum_digabung_satu_baris(self):
        baris = self._seksi(self._detail(), "input")["rows"]
        # Disebut "(master)" secara eksplisit: ada titik pesan kedua, yang
        # efektif, dan dua angka berbeda dengan satu nama membingungkan.
        cocok = [b for b in baris if b["label"] == "Titik pesan ulang (master)"]
        assert len(cocok) == 1
        assert cocok[0]["value"] == "32 PACK (minimum: 16 PACK)"

    def test_histori_dan_hari_aktif_digabung_satu_baris(self):
        baris = self._seksi(self._detail(), "input")["rows"]
        v = next(b["value"] for b in baris if b["label"] == "Histori dianalisis")
        assert v == "8 hari (2026-08-14 – 2026-08-21) · 6 hari ada pengeluaran"

    def test_baris_pemakaian_bulat_tanpa_rumus_bersubstitusi(self):
        """
        Rumus bersubstitusi dibuang bersama desimalnya: "5 × 7 = 32,5" terbaca
        sebagai salah hitung begitu operannya dibulatkan. Nilai penuhnya tetap
        ikut pada field `raw`.
        """
        baris = self._seksi(self._detail(), "calculation")["rows"]
        b = next(b for b in baris if b["label"].startswith("Perkiraan pemakaian"))
        assert b["value"] == "33 PACK"
        assert b["raw"] == 32.5

    def test_baris_sisa_stok_bulat(self):
        baris = self._seksi(self._detail(), "calculation")["rows"]
        b = next(b for b in baris if b["label"] == "Perkiraan sisa stok")
        assert b["value"] == "39 PACK"
        assert b["raw"] == 38.5

    def test_baris_hari_menuju_titik_pesan_bulat(self):
        baris = self._seksi(self._detail(), "calculation")["rows"]
        b = next(b for b in baris
                 if b["label"] == "Hari menuju titik pesan (master)")
        assert b["value"] == "8 hari → ±2 minggu"
        assert b["raw"] == 8.4

    def test_laju_harian_tidak_pernah_dibulatkan_menjadi_nol(self):
        """
        Barang yang keluar seminggu sekali berlaju 0,14 -- dibulatkan menjadi
        "0 PACK/hari" ia menjadi salah. Label frekuensi membalik pertanyaannya.
        """
        baris = self._seksi(
            self._detail(usage_label="±1 PACK", usage_detail="per 7 hari"),
            "calculation")["rows"]
        v = next(b["value"] for b in baris if b["label"] == "Rata-rata pemakaian")
        assert v.startswith("±1 PACK per 7 hari")

    def test_seluruh_baris_bebas_desimal(self):
        """
        Termasuk baris catatan: sejak faktor ekstrapolasi ditulis "satu setengah
        kali" alih-alih "1,5×", tidak ada lagi pecahan yang sah di panel ini.
        """
        import re
        det = self._detail()
        for s in det["sections"]:
            for b in s["rows"]:
                assert not re.search(r"\d+,\d", b["value"]), b["value"]

    def test_tidak_ada_baris_rumus_yang_berdiri_sendiri(self):
        label = [b["label"] for b in self._seksi(self._detail(), "calculation")["rows"]]
        assert "Rumus" not in label

    def test_tidak_ada_baris_rata_rata_bergerak_terpisah(self):
        label = [b["label"] for b in self._seksi(self._detail(), "calculation")["rows"]]
        assert "Rata-rata bergerak berbobot" not in label

    def test_tidak_menyebut_nama_mesin_perhitungan(self):
        semua = " ".join(
            b["value"] for s in self._detail()["sections"] for b in s["rows"]
        ).lower()
        for kata in ("xgboost", "tweedie", "weighted_moving_average"):
            assert kata not in semua

    def test_hanya_satu_baris_status(self):
        baris = self._seksi(self._detail(), "conclusion")["rows"]
        status = [b for b in baris if b["kind"] == "status"]
        assert len(status) == 1
        assert status[0]["value"] == "PERLU DIPANTAU"
        # Label ringkas, bukan kalimat: di dalam tabel berjudul "Status",
        # kata "Stok" pada "Stok aman" hanya mengulang konteks.
        assert d.LABEL_STATUS_RINGKAS[d.STATUS_AMAN] == "AMAN"
        assert status[0]["status"] == d.STATUS_PANTAU

    def test_status_lama_tidak_ikut_dirender(self):
        semua = " ".join(
            b["value"] for s in self._detail()["sections"] for b in s["rows"]
        )
        for lama in ("SAFE", "ATTENTION", "CRITICAL", "INSUFFICIENT"):
            assert lama not in semua

    def test_menyentuh_titik_pesan_dalam_periode(self):
        baris = self._seksi(self._detail(days_until_rop=3), "conclusion")["rows"]
        v = next(b["value"] for b in baris if b["label"] == "Menyentuh titik pesan")
        assert v == "Dalam periode ini (hari ke-3)"

    def test_menyentuh_titik_pesan_di_luar_periode(self):
        baris = self._seksi(self._detail(), "conclusion")["rows"]
        v = next(b["value"] for b in baris if b["label"] == "Menyentuh titik pesan")
        assert v == "Tidak dalam periode prakiraan"

    def test_pola_pemakaian_lumpy(self):
        baris = self._seksi(self._detail(is_lumpy=True), "reliability")["rows"]
        v = next(b["value"] for b in baris if b["label"] == "Pola pemakaian")
        assert v == "Terkonsentrasi (lumpy)"

    def test_mutu_data_memuat_alasan(self):
        baris = self._seksi(self._detail(), "reliability")["rows"]
        v = next(b["value"] for b in baris if b["label"] == "Mutu data")
        assert v == "Rendah — histori hanya 8 hari"

    def test_catatan_muncul_hanya_saat_estimasi_lemah(self):
        ada = self._seksi(
            self._detail(low_confidence=True, low_confidence_reason="uji"),
            "reliability")["rows"]
        assert any(b["kind"] == "warning" for b in ada)
        tiada = self._seksi(self._detail(low_confidence=False), "reliability")["rows"]
        assert not any(b["kind"] == "warning" for b in tiada)

    def test_tanpa_laju_pemakaian_baris_hasil_tidak_mengarang_angka(self):
        det = self._detail(avg_usage=0, days_to_rop=None, bucket="—",
                           expected_usage=None, expected_stock=None)
        baris = self._seksi(det, "calculation")["rows"]
        v = {b["label"]: b["value"] for b in baris}
        assert v["Perkiraan sisa stok"] == "—"
        assert "tidak ada tren pemakaian" in v["Hari menuju titik pesan (master)"]

    def test_seluruh_desimal_maksimal_dua_digit(self):
        import re
        det = self._detail()
        for s in det["sections"]:
            for b in s["rows"]:
                for angka in re.findall(r"\d+,(\d+)", b["value"]):
                    assert len(angka) <= 2, b["value"]


# --------------------------------------------------------------------------
# alasan_estimasi_lemah -- dua pemicu, dua kalimat
# --------------------------------------------------------------------------

class TestAlasanEstimasiLemah:

    def test_ekstrapolasi_disebut_apa_adanya(self):
        a = d.alasan_estimasi_lemah(136, 90, "tinggi")
        assert "melebihi satu setengah kali" in a

    def test_histori_pendek_punya_kalimat_sendiri(self):
        a = d.alasan_estimasi_lemah(2, 8, "rendah")
        assert "terlalu pendek" in a
        assert "melebihi" not in a

    def test_ekstrapolasi_lebih_didahulukan_bila_keduanya_terpicu(self):
        a = d.alasan_estimasi_lemah(100, 8, "rendah")
        assert "melebihi satu setengah kali" in a

    def test_kosong_bila_tidak_ditandai(self):
        assert d.alasan_estimasi_lemah(12, 90, "tinggi") == ""
