# -*- coding: utf-8 -*-
"""
Uji empat perbaikan hasil validasi mesin prakiraan.

    .venv/bin/python -m pytest backend/tests -q

Yang dikunci di sini bukan hanya perilaku barunya, melainkan juga janji bahwa
perilaku LAMA tidak bergeser: WMA, forecast_usage, dan expected_stock harus
menghasilkan angka yang sama persis seperti sebelum perubahan, dan seluruh
baris tanpa stok tercadang harus tetap identik.
"""

import sys
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import decision as d  # noqa: E402
from app import forecasting as f  # noqa: E402
from app import tools  # noqa: E402
from app.routers import forecasting as fr  # noqa: E402


def _deret(nilai, akhir):
    n = len(nilai)
    return [(akhir - timedelta(days=n - 1 - i), v) for i, v in enumerate(nilai)]


def _jalankan(*, stok, keluar_harian, hari_prakiraan, tersedia=None,
              rop=20, minimum=10, akhir=date(2026, 8, 24)):
    keluar = _deret(keluar_harian, akhir)
    neto = [(t, -v) for t, v in keluar]
    return f.hitung(
        as_of=akhir, current_stock=stok,
        daily_outflow=keluar, daily_net=neto,
        minimum_stock=minimum, reorder_point=rop,
        forecast_days=hari_prakiraan, historical_days=len(keluar_harian),
        available_stock=tersedia,
    )


# ==========================================================================
# 1. Perilaku lama tidak boleh bergeser
# ==========================================================================

class TestTidakBergeser:

    def test_wma_tidak_berubah(self):
        """Rumus WMA dikunci pada nilai yang dihitung tangan."""
        # bobot 1..4 atas [10,20,30,40] -> (10+40+90+160)/10 = 30
        assert f.wma([Decimal("10"), Decimal("20"),
                      Decimal("30"), Decimal("40")]) == Decimal("30")
        # deret rata menghasilkan nilai yang sama dengan anggotanya
        assert f.wma([Decimal("7")] * 9) == Decimal("7")

    def test_forecast_usage_tetap_laju_kali_hari(self):
        h = _jalankan(stok=1000, keluar_harian=[10.0] * 30, hari_prakiraan=30)
        assert h["average_daily_outflow"] == 10.0
        assert h["predicted_usage"] == 300.0

    def test_expected_stock_tetap_berbasis_stok_fisik(self):
        """
        Meski shortage kini berbasis stok tersedia, expected_stock TIDAK
        ikut bergeser -- ia menggambarkan barang yang ada di rak.
        """
        h = _jalankan(stok=1000, keluar_harian=[10.0] * 30,
                      hari_prakiraan=30, tersedia=400)
        assert h["current_stock"] == 1000.0
        assert h["predicted_remaining_stock"] == 700.0   # 1000 - 300, bukan 400 - 300

    def test_pemanggil_lama_tanpa_available_stock_tetap_jalan(self):
        """available_stock opsional; tanpa itu ia mengikuti stok fisik."""
        h = _jalankan(stok=250, keluar_harian=[10.0] * 30, hari_prakiraan=30)
        assert h["available_stock"] == 250.0
        assert h["projected_shortage"] == 50.0           # 300 - 250


# ==========================================================================
# 2. projected_shortage berbasis stok tersedia
# ==========================================================================

class TestBasisStokTersedia:

    def test_tanpa_stok_tercadang_hasil_identik(self):
        """reserved = 0 -> available = quantity -> angka lama persis."""
        lama = _jalankan(stok=250, keluar_harian=[10.0] * 30, hari_prakiraan=30)
        baru = _jalankan(stok=250, keluar_harian=[10.0] * 30,
                         hari_prakiraan=30, tersedia=250)
        assert lama["projected_shortage"] == baru["projected_shortage"] == 50.0

    def test_stok_tercadang_memperbesar_kekurangan(self):
        """
        Stok fisik 250 dengan 100 sudah dikomitmenkan keluar: yang benar-benar
        bisa menyerap kebutuhan hanya 150, jadi kekurangannya 150, bukan 50.
        """
        h = _jalankan(stok=250, keluar_harian=[10.0] * 30,
                      hari_prakiraan=30, tersedia=150)
        assert h["predicted_usage"] == 300.0
        assert h["current_stock"] == 250.0
        assert h["available_stock"] == 150.0
        assert h["projected_shortage"] == 150.0

    def test_stok_tercadang_dapat_memunculkan_kekurangan_yang_tadinya_nol(self):
        h_fisik = _jalankan(stok=400, keluar_harian=[10.0] * 30, hari_prakiraan=30)
        h_tersedia = _jalankan(stok=400, keluar_harian=[10.0] * 30,
                               hari_prakiraan=30, tersedia=250)
        assert h_fisik["projected_shortage"] == 0.0      # 400 menutup 300
        assert h_tersedia["projected_shortage"] == 50.0  # 250 tidak

    def test_available_stock_hadir_juga_saat_histori_kurang(self):
        h = _jalankan(stok=400, keluar_harian=[5.0, 0.0], hari_prakiraan=30,
                      tersedia=150)
        assert h["status"] == f.STATUS_INSUFFICIENT
        assert h["available_stock"] == 150.0
        assert h["projected_shortage"] is None


# ==========================================================================
# 3. action_status tidak bergantung horizon
# ==========================================================================

class TestUrgensiTidakBergantungHorizon:

    def test_action_status_tetap_saat_horizon_berubah(self):
        """
        Inti perbaikan #1: urgensi diukur dari waktu menuju titik pesan
        terhadap lead time, bukan dari sisa stok di akhir periode. Karena itu
        ia tidak boleh bergerak hanya karena periodenya diperpanjang.
        """
        hasil = {
            hari: d.lapisan_keputusan(
                current_stock=1000, reorder_point=100, minimum_stock=50,
                avg_daily_usage=10, keluar_harian=[10] * 60,
                lead_time_days=14, forecast_days=hari, hari_histori=60, hari_aktif=60,
            )["action_status"]
            for hari in (7, 14, 30, 60, 90)
        }
        assert len(set(hasil.values())) == 1, hasil

    def test_status_forecast_memang_bergerak_karena_horizon(self):
        """
        Sisi lain dari perbaikan yang sama: `status` DIBIARKAN apa adanya demi
        antarmuka lama, dan uji ini merekam bahwa ia memang bergantung horizon
        -- alasan mengapa ia tidak boleh dipakai sebagai tingkat risiko.
        """
        pendek = _jalankan(stok=1000, keluar_harian=[10.0] * 60,
                           hari_prakiraan=7, rop=100, minimum=50)
        panjang = _jalankan(stok=1000, keluar_harian=[10.0] * 60,
                            hari_prakiraan=90, rop=100, minimum=50)
        assert pendek["status"] == f.STATUS_SAFE
        assert panjang["status"] == f.STATUS_CRITICAL

    def test_status_tidak_dikirim_ke_chatbot(self):
        assert "status" not in tools.BIDANG_FORECAST
        assert "action_status_label" in tools.BIDANG_FORECAST
        assert "action_status" in tools.BIDANG_FORECAST


# ==========================================================================
# 4. days_to_rop sebagai sumber utama
# ==========================================================================

class TestWaktuMenujuTitikPesan:

    def test_days_to_rop_menjawab_di_luar_horizon(self):
        """
        Kasus yang menjebak: titik pesan tersentuh pada hari ke-39 sementara
        horizon 30 hari. Mesin prakiraan berkata None; lapisan keputusan tetap
        menjawab angkanya.
        """
        h = _jalankan(stok=156, keluar_harian=[3.0] * 60,
                      hari_prakiraan=30, rop=40, minimum=20)
        assert h["days_until_reorder_point"] is None

        k = d.lapisan_keputusan(
            current_stock=156, reorder_point=40, minimum_stock=20,
            avg_daily_usage=3.0, keluar_harian=[3.0] * 60,
            lead_time_days=7, forecast_days=30,
            hari_histori=60, hari_aktif=60,
            days_until_rop=h["days_until_reorder_point"],
        )
        assert k["days_to_rop"] == 38.67
        assert k["reorder_point_within_horizon"] is False

    def test_none_di_luar_horizon_berbeda_dari_tidak_pernah(self):
        """
        Dua keadaan yang sama-sama menghasilkan days_until_reorder_point None,
        dibedakan tegas oleh lapisan keputusan.
        """
        di_luar_horizon = d.lapisan_keputusan(
            current_stock=156, reorder_point=40, minimum_stock=20,
            avg_daily_usage=3.0, keluar_harian=[3.0] * 60,
            lead_time_days=7, forecast_days=30,
            hari_histori=60, hari_aktif=60, days_until_rop=None,
        )
        tidak_pernah = d.lapisan_keputusan(
            current_stock=156, reorder_point=40, minimum_stock=20,
            avg_daily_usage=0, keluar_harian=[0] * 60,
            lead_time_days=7, forecast_days=30,
            hari_histori=60, hari_aktif=0, days_until_rop=None,
        )
        assert di_luar_horizon["days_to_rop"] == 38.67     # akan tersentuh
        assert tidak_pernah["days_to_rop"] is None         # tidak akan pernah
        assert di_luar_horizon["reorder_point_within_horizon"] is False
        assert tidak_pernah["reorder_point_within_horizon"] is False

    def test_within_horizon_true_saat_tersentuh_di_dalam_periode(self):
        k = d.lapisan_keputusan(
            current_stock=100, reorder_point=40, minimum_stock=20,
            avg_daily_usage=5.0, keluar_harian=[5.0] * 60,
            lead_time_days=7, forecast_days=30,
            hari_histori=60, hari_aktif=60, days_until_rop=12,
        )
        assert k["reorder_point_within_horizon"] is True
        assert k["days_to_rop"] == 12.0

    def test_kedua_field_dikirim_ke_chatbot(self):
        for nama in ("days_to_rop", "reorder_point_within_horizon",
                     "days_until_reorder_point"):
            assert nama in tools.BIDANG_FORECAST


# ==========================================================================
# 5. Tanggal acuan mengikuti data, bukan jam server
# ==========================================================================

class TestTanggalAcuan:

    def test_memakai_tanggal_transaksi_terakhir(self):
        """Kasus yang memicu perbaikan: data berhenti empat hari lalu."""
        assert fr.tanggal_acuan(date(2026, 8, 20), date(2026, 8, 24)) == date(2026, 8, 20)

    def test_tidak_ikut_maju_saat_jam_server_maju(self):
        """Jendela histori tidak boleh bergeser hanya karena hari berganti."""
        terakhir = date(2026, 8, 20)
        acuan = [fr.tanggal_acuan(terakhir, date(2026, 8, d)) for d in (20, 21, 24, 31)]
        assert acuan == [terakhir] * 4

    def test_jeda_pendek_masih_dianggap_pencatatan_tertinggal(self):
        """Batas toleransinya dua minggu; di dalamnya jangkarnya tidak bergeser."""
        assert (fr.tanggal_acuan(date(2026, 8, 10), date(2026, 8, 24))
                == date(2026, 8, 10))

    def test_jeda_panjang_memakai_hari_ini(self):
        """
        Kebalikan dari tes di atas, dan alasannya ada pada komponen berumur
        tahunan: pompa yang terakhir diganti 2012 lalu berjalan mulus sampai
        sekarang TIDAK berlaju satu unit per sebelas hari. Tahun-tahun kosong
        sesudah penggantian itu bagian dari jawabannya, bukan data yang hilang,
        jadi jendelanya harus berakhir hari ini.
        """
        assert (fr.tanggal_acuan(date(2012, 1, 11), date(2026, 9, 1))
                == date(2026, 9, 1))
        assert (fr.tanggal_acuan(date(2026, 7, 1), date(2026, 8, 24))
                == date(2026, 8, 24))

    def test_barang_belum_pernah_bergerak_memakai_hari_ini(self):
        assert fr.tanggal_acuan(None, date(2026, 8, 24)) == date(2026, 8, 24)

    def test_hari_kosong_di_ujung_menekan_laju(self):
        """
        Alasan perbaikan ini ada, dinyatakan sebagai angka: ekor nol mendapat
        bobot TERBESAR pada rata-rata bergerak berbobot, sehingga menurunkan
        laju -- selalu ke arah meremehkan kebutuhan.
        """
        nyata = [Decimal("10")] * 30
        dengan_ekor = nyata + [Decimal("0")] * 4
        assert f.wma(dengan_ekor) < f.wma(nyata)
        assert f.wma(nyata) == Decimal("10")

    def test_prakiraan_tidak_berubah_saat_jam_server_maju(self):
        """
        Jendela yang sama menghasilkan angka yang sama, berapa pun tanggal
        server -- karena as_of kini tidak lagi membacanya.
        """
        keluar = [10.0] * 30
        a = _jalankan(stok=500, keluar_harian=keluar, hari_prakiraan=30,
                      akhir=date(2026, 8, 20))
        b = _jalankan(stok=500, keluar_harian=keluar, hari_prakiraan=30,
                      akhir=date(2026, 9, 30))
        for kunci in ("average_daily_outflow", "predicted_usage",
                      "predicted_remaining_stock", "projected_shortage",
                      "days_until_stockout", "days_until_reorder_point"):
            assert a[kunci] == b[kunci], kunci



class TestJadwalPenggantian:
    """
    Jadwal dari umur pakai, untuk komponen yang riwayatnya tidak akan pernah
    cukup diramal.
    """

    def test_satuan_tahun_menghasilkan_tanggal_jatuh_tempo(self):
        j = fr._jadwal_penggantian(20, "tahun", date(2012, 1, 11), date(2026, 9, 1))
        assert j["due_date"] == "2032-01-06"
        assert j["days_remaining"] == 1953
        assert j["last_replacement"] == "2012-01-11"

    def test_satuan_jam_tidak_menebak_tanggal(self):
        """
        Mengubah jam operasi menjadi tanggal menuntut jam operasi per hari, dan
        angka itu tidak ada di basis data -- lihat migrasi 029. Umur pakainya
        tetap terbit, kesimpulannya tidak.
        """
        j = fr._jadwal_penggantian(12_500, "jam", date(2025, 8, 4), date(2026, 9, 1))
        assert j["value"] == 12_500
        assert j["unit"] == "jam"
        assert j["due_date"] is None
        assert j["days_remaining"] is None

    def test_jatuh_tempo_terlewat_bersisa_negatif(self):
        """Angka negatif, bukan nol: komponen yang telat diganti harus terbaca."""
        j = fr._jadwal_penggantian(20, "tahun", date(2000, 1, 1), date(2026, 9, 1))
        assert j["days_remaining"] < 0

    def test_tanpa_umur_pakai_tidak_ada_jadwal(self):
        assert fr._jadwal_penggantian(None, None, date(2026, 1, 1), date(2026, 9, 1)) is None

    def test_belum_pernah_diganti_tanpa_tanggal(self):
        j = fr._jadwal_penggantian(20, "tahun", None, date(2026, 9, 1))
        assert j["last_replacement"] is None and j["due_date"] is None


class TestJendelaMemanjang:
    """
    Jendela histori memanjang sampai memuat cukup hari pengeluaran -- dan
    berhenti di situ.

    Yang diuji BUKAN angka prakiraannya melainkan tanggal mulai yang benar-benar
    diminta ke basis data, karena di situlah keputusannya diambil. Barang yang
    diganti tiap sebelas minggu punya riwayat dua puluh tahun berisi puluhan
    penggantian, tetapi sembilan puluh hari terakhir memuat satu kejadian; yang
    kurang panjang jendelanya, bukan datanya.
    """

    class _Kursor:
        """Mencatat rentang yang diminta generate_series."""

        def __init__(self, hari_keluar, hari_ini):
            self.hari_keluar, self.hari_ini = hari_keluar, hari_ini
            self.diminta = None
            self.hasil = None

        def execute(self, sql, params=None):
            s = " ".join(sql.split())
            if "FROM items it" in s:
                self.hasil = {
                    "id": 1, "sku": "TST-1", "name": "Barang Uji",
                    "minimum_stock": 1, "reorder_point": 2, "maximum_stock": None,
                    "is_active": True, "unit_code": "PCS", "category_id": 1,
                    "unit_price": 1000, "lead_time_days": 7, "safety_stock": 1,
                    "service_life_value": None, "service_life_unit": None,
                    "usage_type": "habis_pakai",
                }
            elif "FROM warehouses" in s:
                self.hasil = {"id": 1, "code": "WH01", "name": "Gudang Uji",
                              "is_active": True}
            elif "FROM inventory" in s:
                self.hasil = {"quantity": 5, "reserved_quantity": 0,
                              "available_quantity": 5}
            elif "max(movement_date)" in s:
                self.hasil = {"terakhir": self.hari_ini}
            elif "generate_series" in s:
                # Didahulukan: query harian pun memuat "quantity < 0" di dalam
                # klausa FILTER-nya, jadi urutan cabang di sini menentukan.
                self.diminta = (params[0], params[1])
                self.hasil = []
            elif "quantity < 0" in s:
                # Terbaru dulu, sebanyak-banyaknya sepanjang LIMIT-nya.
                batas = params[-1]
                self.hasil = [{"hari": h} for h in self.hari_keluar[:batas]]
            else:
                raise AssertionError(f"query tak terduga: {s[:120]}")

        def fetchone(self):
            return self.hasil if isinstance(self.hasil, dict) else None

        def fetchall(self):
            return self.hasil if isinstance(self.hasil, list) else []

    def _mulai(self, monkeypatch, mundur):
        """
        Jalankan _susun dengan pergerakan terakhir HARI INI, lalu kembalikan
        rentang yang benar-benar diminta. `mundur` = daftar "berapa hari lalu"
        tiap hari pengeluaran, terbaru dulu.

        Pergerakan terakhirnya sengaja hari ini, bukan tanggal tetap: jam server
        tidak dapat dipalsukan (`datetime.date` tidak menerima monkeypatch), dan
        tanggal tetap akan membuat jeda terhadap hari ini ikut tumbuh sehingga
        jangkarnya berpindah dan tes ini gagal sendiri seiring waktu.
        """
        hari_ini = date.today()
        kursor = self._Kursor([hari_ini - timedelta(days=m) for m in mundur],
                              hari_ini)

        @contextmanager
        def readonly_palsu():
            yield kursor

        monkeypatch.setattr(fr, "readonly", readonly_palsu)
        fr._susun(1, 1, 30, fr.HISTORICAL_DAYS_DEFAULT, "id", "statistik", None)
        return hari_ini, kursor.diminta

    def test_jendela_padat_tidak_dipanjangkan(self, monkeypatch):
        """Kejadian keempat sudah di dalam 90 hari: tidak ada yang berubah."""
        hari_ini, (mulai, akhir) = self._mulai(monkeypatch, [0, 3, 6, 10])
        assert akhir == hari_ini
        assert mulai == hari_ini - timedelta(days=fr.HISTORICAL_DAYS_DEFAULT - 1)

    def test_jendela_renggang_mulai_sehari_sesudah_kejadian_keempat(self, monkeypatch):
        """
        Sehari SESUDAH, bukan tepat pada kejadiannya: jendela yang dimulai tepat
        pada satu penggantian membentang tiga selang tetapi memuat empat
        penggantian, dan lajunya terbaca sepertiga terlalu tinggi.
        """
        hari_ini, (mulai, _) = self._mulai(monkeypatch, [0, 150, 300, 450])
        assert mulai == hari_ini - timedelta(days=449)

    def test_kejadian_pas_tiga_memakai_yang_tertua(self, monkeypatch):
        """
        Tidak ada kejadian keempat untuk dilewati. Lebih baik laju yang sedikit
        terlalu tinggi daripada menolaknya sebagai data yang belum cukup.
        """
        hari_ini, (mulai, _) = self._mulai(monkeypatch, [0, 150, 300])
        assert mulai == hari_ini - timedelta(days=300)

    def test_penarikan_dibatasi(self, monkeypatch):
        """Barang yang bergerak sekali seabad tidak menarik jendela sejauh itu."""
        hari_ini, (mulai, _) = self._mulai(monkeypatch, [0, 100, 20_000, 30_000])
        assert mulai == hari_ini - timedelta(days=fr.LOOKBACK_MAKS_HARI)

    def test_kejadian_kurang_dari_ambang_jendela_tetap(self, monkeypatch):
        """Dua kejadian tidak dapat ditolong panjang jendela mana pun."""
        hari_ini, (mulai, _) = self._mulai(monkeypatch, [0, 900])
        assert mulai == hari_ini - timedelta(days=fr.HISTORICAL_DAYS_DEFAULT - 1)


# ==========================================================================
# 6. Basis stok tersedia sampai ke chatbot
# ==========================================================================

class TestPayloadChatbot:

    def test_tiga_basis_stok_dikirim(self):
        for nama in ("current_stock", "reserved_stock", "available_stock"):
            assert nama in tools.BIDANG_FORECAST

    def test_deret_harian_tidak_ikut(self):
        for nama in ("historical_data", "forecast_data", "historical", "forecast"):
            assert nama not in tools.BIDANG_FORECAST
