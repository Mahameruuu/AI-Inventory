# -*- coding: utf-8 -*-
"""
Validasi tiga lapisan sekaligus atas kasus-kasus ekstrem.

    .venv/bin/python -m pytest backend/tests -q

Uji lain di folder ini memeriksa rumus. Yang diperiksa DI SINI adalah apa yang
benar-benar sampai ke manusia: angka pada kartu halaman Forecasting dan
Reorder, dan angka yang diserahkan ke chatbot. Ketiganya harus menyimpulkan hal
yang sama tentang barang yang sama -- kontradiksi yang dilaporkan pengguna
("Segera pesan" berdampingan dengan "Belum ada jumlah yang perlu diadakan")
justru lolos dari uji rumus, karena masing-masing rumusnya benar sendiri-
sendiri.

BASIS DATANYA TIRUAN, JALUR KODENYA ASLI. Kursor palsu menjawab kelima query
`_susun()`, sehingga yang dilewati tetap router, mesin prakiraan, lapisan
keputusan, dan perakit muatan chatbot yang sebenarnya. Tanpa itu, kasus seperti
"lead time nol" atau "histori belum cukup" mustahil disusun dari data nyata.

DAFTAR FIELD UI DIBACA DARI BERKAS .tsx. Bila kelak antarmuka merender field
desimal yang baru, uji ini menangkapnya tanpa perlu diperbarui manual.
"""

import re
import sys
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

import pytest

AKAR_BACKEND = Path(__file__).resolve().parents[1]
AKAR = AKAR_BACKEND.parent
sys.path.insert(0, str(AKAR_BACKEND))

from app import db, tools  # noqa: E402
from app.routers import forecast_api  # noqa: E402
from app.routers import forecasting as fr  # noqa: E402

HARI_INI = date(2026, 8, 24)

# Dalam format Indonesia titik adalah pemisah RIBUAN ("3.667" = tiga ribu enam
# ratus enam puluh tujuh), jadi hanya koma yang menandakan pecahan.
DESIMAL = re.compile(r"\d,\d")

# Berkas yang merender objek jawaban /api/forecast lewat sebuah prop bernama
# `data`. Dari sinilah daftar field UI dibaca, sehingga antarmuka yang mulai
# merender field desimal baru tertangkap tanpa uji ini perlu diperbarui.
#
# app/reorder/page.tsx TIDAK LAGI DI SINI, 2 September 2026. Halaman itu kini
# merender jawaban /api/reorder -- sebuah DAFTAR -- sehingga `data.items` dan
# `data.summary` miliknya bukan field prakiraan dan tidak pernah ada pada
# jawaban yang diperiksa di berkas ini. Barisnya sendiri diperiksa terpisah;
# lihat TestBarisDaftarReorder.
FRONTEND = [
    "frontend/components/reorder-sections.tsx",
    "frontend/components/forecast-sections.tsx",
    "frontend/app/forecasting/page.tsx",
]

# Nilai chatbot -> nilai yang dirender antarmuka. Dibandingkan terhadap angka
# TAMPILAN, bukan float internal: yang tidak boleh berselisih adalah apa yang
# dibaca pengguna di kedua tempat.
SILANG = {
    "action_status": "action_status",
    "action_status_label": "action_status_label",
    "recommended_order_qty": "recommended_order_qty",
    "current_stock": "current_stock_int",
    "available_stock": "available_stock_int",
    "reorder_point": "reorder_point_int",
    "minimum_stock": "minimum_stock_int",
    "safety_stock": "safety_stock_int",
    "lead_time_demand": "lead_time_demand_int",
    "effective_reorder_point": "effective_reorder_point_int",
    "days_to_effective_rop": "days_to_effective_rop_int",
    "order_up_to_level": "order_up_to_level_int",
    "forecast_usage": "forecast_usage_int",
    "expected_stock": "expected_stock_int",
    "projected_shortage": "projected_shortage_int",
    "usage_frequency_label": "usage_frequency_label",
    "reorder_point_adequate": "reorder_point_adequate",
}


class _KursorPalsu:
    """Menjawab kelima query `_susun()` menurut isi query-nya."""

    def __init__(self, barang, gudang, stok, harian):
        self.barang, self.gudang, self.stok, self.harian = barang, gudang, stok, harian
        self.hasil = None

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if "FROM items it" in s:
            self.hasil = self.barang
        elif "FROM warehouses" in s:
            self.hasil = self.gudang
        elif "FROM inventory" in s:
            self.hasil = self.stok
        elif "max(movement_date)" in s:
            self.hasil = {"terakhir": self.harian[-1]["tanggal"] if self.harian else None}
        elif "generate_series" in s:
            self.hasil = self.harian
        elif "quantity < 0" in s:
            # Pencari hari pengeluaran terbaru, yang memanjangkan jendela bila
            # 90 hari tidak memuat cukup. Kasus di berkas ini semuanya
            # berjendela padat, jadi jawabannya kosong: jendelanya tidak
            # dipanjangkan dan angka yang diuji di bawah tidak bergeser.
            self.hasil = []
        else:
            # Query baru yang belum dikenal lebih baik meledak di sini daripada
            # diam-diam menjawab data kasus sebelumnya.
            raise AssertionError(f"query tak terduga: {s[:120]}")

    def fetchone(self):
        return self.hasil if isinstance(self.hasil, dict) else None

    def fetchall(self):
        return self.hasil if isinstance(self.hasil, list) else []


def _deret(n_hari: int, per_hari: float, hari_keluar: int | None = None):
    baris = []
    for i in range(n_hari):
        keluar = per_hari if (hari_keluar is None or i < hari_keluar) else 0.0
        baris.append({
            "tanggal": HARI_INI - timedelta(days=n_hari - 1 - i),
            "keluar": keluar,
            "neto": -keluar,
        })
    return baris


# Parameter dasarnya kasus yang dilaporkan pengguna: lead 14, safety 22,
# pemakaian 1/hari -> titik pesan efektif 36, titik pesan master 44.
DASAR = dict(rop=44, minimum=15, safety=22, lead=14, laju=1.0, hari=60)


def jalankan(monkeypatch, stok, days=90, **ubah):
    """Satu kasus melewati API dan perakit muatan chatbot yang sebenarnya."""
    p = {**DASAR, **ubah}
    barang = {
        "id": 1, "sku": "TST-000001", "name": "Barang Uji",
        "minimum_stock": p["minimum"], "reorder_point": p["rop"],
        "maximum_stock": None, "is_active": True, "unit_code": "PCS",
        "category_id": 1, "unit_price": 1000,
        "lead_time_days": p["lead"], "safety_stock": p["safety"],
        # Umur pakai tidak dicatat pada kasus-kasus di berkas ini: yang diuji
        # di sini rantai prakiraan, dan jadwal penggantian tidak menyentuhnya.
        "service_life_value": None, "service_life_unit": None,
        "usage_type": "habis_pakai",
    }
    gudang = {"id": 1, "code": "WH01", "name": "Gudang Uji", "is_active": True}
    inv = {"quantity": stok, "reserved_quantity": 0, "available_quantity": stok}
    harian = _deret(p["hari"], p["laju"], p.get("hari_keluar"))

    @contextmanager
    def readonly_palsu():
        yield _KursorPalsu(barang, gudang, inv, harian)

    monkeypatch.setattr(db, "readonly", readonly_palsu)
    monkeypatch.setattr(fr, "readonly", readonly_palsu)

    api = forecast_api.forecast(warehouse_id=1, item_id=1, days=days,
                                historical_days=90, include_recommendation=False)
    bot = tools.get_forecast(item_id=1, warehouse_id=1, days=days)
    rek = (fr._rekomendasi_tanpa_ai(fr._susun(1, 1, days, 90))
           if api["has_forecast"] else None)
    return api, bot, rek


# Sepuluh kasus yang diminta, plus tiga varian yang membelah kasus ambigu:
# demand nol sungguhan versus nyaris nol, dan lead time kosong pada stok di
# atas maupun di bawah titik pesan master.
KASUS = {
    "1_stok_jauh_di_atas_rop": dict(stok=500),
    "2_stok_tepat_di_rop_efektif": dict(stok=36),
    "3_stok_sedikit_di_bawah_rop_efektif": dict(stok=35),
    "4_stok_jauh_di_bawah_rop": dict(stok=5),
    "5a_demand_nol": dict(stok=55, laju=0.0),
    "5b_demand_nyaris_nol": dict(stok=55, hari_keluar=3),
    "6_safety_stock_nol": dict(stok=55, safety=0),
    "7_lead_time_nol": dict(stok=55, lead=0),
    "8a_lead_time_kosong": dict(stok=55, lead=None),
    "8b_lead_time_kosong_stok_menipis": dict(stok=30, lead=None),
    "9_histori_belum_cukup": dict(stok=55, hari=10, hari_keluar=2),
    "10a_rop_master_lebih_tinggi": dict(stok=40, rop=100),
    "10b_rop_master_lebih_rendah": dict(stok=40, rop=5),
}
NAMA_KASUS = list(KASUS)


@pytest.fixture(params=NAMA_KASUS)
def kasus(request, monkeypatch):
    api, bot, rek = jalankan(monkeypatch, **KASUS[request.param])
    return request.param, api, bot, rek


# Field yang SENGAJA dirender sebagai pecahan, dengan alasannya.
#
# Aturan umumnya tetap berlaku: apa pun yang sampai ke layar berupa bilangan
# bulat. Pengecualian di bawah dituliskan satu per satu supaya penambahan
# berikutnya menuntut keputusan sadar, bukan lolos diam-diam.
PECAHAN_DISENGAJA = {
    # Kartu "Rata-rata pemakaian" pada halaman Prakiraan mencetak laju harian
    # dengan satu desimal ("0,1 METER/hari"). Membulatkannya ke bilangan bulat
    # justru yang salah: barang yang keluar sekali seminggu menjadi "0 per
    # hari". Layarnya sendiri menjaga batasnya -- di bawah 0,05/hari ia jatuh
    # ke label frekuensi backend ("±1 per 62 hari") yang tetap bulat.
    "average_daily_usage",
}


def field_ui() -> set[str]:
    nama = set()
    for b in FRONTEND:
        nama |= set(re.findall(r"\bdata\.([a-z_][a-z0-9_]*)", (AKAR / b).read_text()))
    return nama - PECAHAN_DISENGAJA


def _pecahan(v) -> bool:
    """Apakah nilai ini akan mencetak pecahan di layar."""
    if isinstance(v, bool) or v is None or isinstance(v, int):
        return False
    if isinstance(v, float):
        return v != int(v)
    if isinstance(v, str):
        return bool(DESIMAL.search(v))
    return False


# ==========================================================================
# Invarian status <-> jumlah
# ==========================================================================

class TestInvarianStatusJumlah:

    def test_status_bertindak_selalu_punya_jumlah(self, kasus):
        nama, api, _, _ = kasus
        if api["action_status"] != "AMAN":
            qty = api["recommended_order_qty"]
            # None berarti "belum dapat dihitung" dan kartunya berkata begitu;
            # nol berarti "tidak ada yang perlu dipesan" dan itu yang dilarang.
            assert qty is None or qty > 0, nama

    def test_aman_tidak_pernah_membawa_jumlah(self, kasus):
        nama, api, _, _ = kasus
        if api["action_status"] == "AMAN":
            assert (api["recommended_order_qty"] or 0) == 0, nama

    def test_perlu_reorder_hanya_bila_stok_menyentuh_rop_efektif(self, kasus):
        nama, api, _, _ = kasus
        if api["action_status"] == "PERLU_REORDER":
            assert api["available_stock"] <= api["effective_reorder_point"], nama

    def test_risiko_stockout_selalu_prioritas_tinggi(self, kasus):
        nama, api, _, _ = kasus
        if api["action_status"] == "RISIKO_STOCKOUT":
            assert api["priority"] == "TINGGI", nama

    def test_jumlah_tidak_pernah_negatif(self, kasus):
        nama, api, _, _ = kasus
        assert (api["recommended_order_qty"] or 0) >= 0, nama

    def test_judul_pengadaan_selaras_dengan_status(self, kasus):
        nama, api, _, _ = kasus
        judul, qty = api["order_qty_title"], api["recommended_order_qty"]
        if qty is None:
            assert "belum dapat dihitung" in judul, nama
        elif qty == 0:
            assert judul == "Belum perlu pengadaan", nama
        else:
            assert judul == f"Pesan {qty} PCS", nama


# ==========================================================================
# Titik pesan master hanya referensi
# ==========================================================================

class TestTitikPesanMaster:

    def test_rop_efektif_adalah_yang_tertinggi(self, kasus):
        """
        max(titik pesan master, kebutuhan masa tunggu + cadangan). Diuji
        sebagai identitas, bukan sebagai angka tetap, supaya ia tetap berlaku
        untuk setiap kasus pada daftar.
        """
        nama, api, _, _ = kasus
        if api["lead_time_demand"] is None:
            return                      # jatuh ke master; diuji terpisah
        assert api["effective_reorder_point"] == pytest.approx(
            max(api["reorder_point"],
                api["lead_time_demand"] + api["safety_stock"]), abs=0.005), nama

    def test_rop_master_menaikkan_ambang_tetapi_tidak_menurunkannya(self, monkeypatch):
        """
        Master 5 dan 44 sama-sama di bawah hasil hitung (36 dibulatkan), jadi
        ambangnya tidak bergeser; master 100 di atasnya, jadi ia yang menang.
        """
        rendah = {rop: jalankan(monkeypatch, stok=40, rop=rop)[0]["effective_reorder_point_int"]
                  for rop in (5, 30)}
        assert len(set(rendah.values())) == 1, rendah
        tinggi = jalankan(monkeypatch, stok=40, rop=100)[0]
        assert tinggi["effective_reorder_point_int"] == 100

    def test_rop_master_terlewati_tidak_menghasilkan_kontradiksi(self, monkeypatch):
        """
        Kasus yang dilaporkan, dibalik: master 100 menjadi ambang dan stok 40
        berada di bawahnya. Dulu ini berbunyi "Segera pesan" dengan jumlah nol.
        Sekarang ia perlu reorder DAN punya jumlah -- karena sasaran pengisian
        tidak pernah turun di bawah ambangnya sendiri.
        """
        api, _, _ = jalankan(monkeypatch, stok=40, rop=100)
        assert api["effective_reorder_point_int"] == 100
        assert api["action_status"] != "AMAN"
        assert api["recommended_order_qty"] > 0
        assert api["order_qty_title"].startswith("Pesan ")


# ==========================================================================
# Bilangan bulat di seluruh permukaan yang dibaca manusia
# ==========================================================================

class TestBilanganBulat:

    def test_seluruh_field_yang_dirender_ui_ada_dan_bulat(self, kasus):
        nama, api, _, _ = kasus
        for f in sorted(field_ui()):
            assert f in api, f"{nama}: UI membaca data.{f}, tidak ada di API"
            assert not _pecahan(api[f]), f"{nama}: data.{f} = {api[f]!r}"

    def test_panel_detail_perhitungan_bulat(self, kasus):
        nama, api, _, _ = kasus
        for s in api["calculation_detail"]["sections"]:
            for b in s["rows"]:
                assert not DESIMAL.search(b["value"]), f"{nama}: {b['label']}"

    def test_muatan_chatbot_bulat(self, kasus):
        """
        Lebih ketat daripada layar: float 36.0 pun ditolak, karena JSON-nya
        berbunyi "36.0" dan model menyalinnya apa adanya menjadi "36,0".
        """
        nama, _, bot, _ = kasus
        for k, v in bot.items():
            assert not isinstance(v, float), f"{nama}: {k} = {v!r}"
            assert not _pecahan(v), f"{nama}: {k} = {v!r}"

    def test_kalimat_rekomendasi_bulat(self, kasus):
        nama, _, _, rek = kasus
        if rek:
            assert not DESIMAL.search(rek["body"]), f"{nama}: {rek['body']}"


# ==========================================================================
# Ketiga lapisan menyimpulkan hal yang sama
# ==========================================================================

class TestKonsistensiLintasLapisan:

    def test_chatbot_menyebut_angka_yang_sama_dengan_layar(self, kasus):
        nama, api, bot, _ = kasus
        for k_bot, k_api in SILANG.items():
            assert bot[k_bot] == api[k_api], f"{nama}: {k_bot}"

    def test_halaman_forecasting_tidak_membawa_keputusan_reorder(self):
        """
        Pemisahan lapisan, dijaga dari sisi berkasnya: blok Forecasting tidak
        boleh membaca satu pun field keputusan reorder. Bila kelak ada yang
        menaruhnya kembali di sana, satu layar akan kembali memuat dua patokan
        waktu sekaligus.
        """
        teks = (AKAR / "frontend/components/forecast-sections.tsx").read_text()
        terlarang = ("action_status", "recommended_order_qty", "order_qty_title",
                     "effective_reorder_point", "days_to_effective_rop",
                     "lead_time_demand", "order_up_to_level")
        for f in terlarang:
            assert f"data.{f}" not in teks, f

    def test_angka_reorder_tidak_bergerak_mengikuti_periode(self, monkeypatch):
        """
        Halaman Reorder memakai horizon tetap, tetapi endpoint-nya sama.
        Mengganti periode di layar Forecasting tidak boleh menggeser satu pun
        angka keputusan.
        """
        kunci = ("effective_reorder_point_int", "action_status",
                 "recommended_order_qty", "days_to_effective_rop_int",
                 "order_up_to_level_int", "lead_time_demand_int")
        nilai = {d: tuple(jalankan(monkeypatch, stok=40, days=d)[0][k] for k in kunci)
                 for d in (7, 14, 30, 60, 90)}
        assert len(set(nilai.values())) == 1, nilai


# ==========================================================================
# Kasus per kasus: angka yang diharapkan, dieja apa adanya
# ==========================================================================

class TestNilaiTiapKasus:
    """
    Tabel harapan yang eksplisit. Uji di atas menjaga invarian; yang di sini
    menjaga agar invariannya tidak dipenuhi dengan angka yang salah.
    """

    # Parameter dasar: rop master 44, safety 22, lead 14, laju 1/hari.
    #   kebutuhan masa tunggu = 14 -> 14 + 22 = 36
    #   titik pesan efektif   = max(44, 36) = 44
    #   sasaran pengisian     = max(44, 1 x 14 + 22) = 44
    #   habis sebelum kiriman bila stok <= 14
    @pytest.mark.parametrize("nama,stok,eff,status,qty", [
        ("1_stok_jauh_di_atas_rop", 500, 44, "AMAN", 0),
        ("2_stok_tepat_di_rop_efektif", 36, 44, "PERLU_REORDER", 8),
        ("3_stok_sedikit_di_bawah_rop_efektif", 35, 44, "PERLU_REORDER", 9),
        # 5 unit pada laju 1/hari habis dalam 5 hari, kiriman 14 hari.
        ("4_stok_jauh_di_bawah_rop", 5, 44, "RISIKO_STOCKOUT", 39),
        # safety 0 -> 14 + 0 = 14, kalah oleh master 44.
        ("6_safety_stock_nol", 55, 44, "AMAN", 0),
        # lead 0 -> 0 + 22 = 22, kalah oleh master 44.
        ("7_lead_time_nol", 55, 44, "AMAN", 0),
        ("10a_rop_master_lebih_tinggi", 40, 100, "PERLU_REORDER", 60),
        ("10b_rop_master_lebih_rendah", 40, 36, "AMAN", 0),
    ])
    def test_nilai(self, monkeypatch, nama, stok, eff, status, qty):
        api, _, _ = jalankan(monkeypatch, **KASUS[nama])
        assert api["available_stock_int"] == stok
        assert api["effective_reorder_point_int"] == eff
        assert api["action_status"] == status
        assert api["recommended_order_qty"] == qty

    def test_demand_nol_tidak_pernah_membagi_dengan_nol(self, monkeypatch):
        api, _, _ = jalankan(monkeypatch, **KASUS["5a_demand_nol"])
        assert api["days_to_effective_rop"] is None
        assert api["days_to_effective_rop_label"] == "Tidak ada konsumsi terdeteksi"
        assert api["action_status"] == "AMAN"

    def test_histori_belum_cukup_menjawab_belum_tahu_bukan_nol(self, monkeypatch):
        api, bot, _ = jalankan(monkeypatch, **KASUS["9_histori_belum_cukup"])
        assert api["has_forecast"] is False
        assert api["recommended_order_qty"] is None
        assert bot["recommended_order_qty"] is None
        assert "belum dapat dihitung" in api["order_qty_title"]

    def test_lead_time_kosong_jatuh_ke_titik_pesan_master(self, monkeypatch):
        api, _, _ = jalankan(monkeypatch, **KASUS["8a_lead_time_kosong"])
        assert api["lead_time_demand"] is None
        assert api["effective_reorder_point_int"] == api["reorder_point_int"] == 44
        assert api["reorder_point_adequate"] is None
        # Stok 55 di atas ambang 44 -> aman, dan aman berarti nol. Jumlahnya
        # KINI terhitung walau lead time kosong: rumus barunya hanya menuntut
        # laju pemakaian.
        assert api["action_status"] == "AMAN"
        assert api["recommended_order_qty"] == 0

    def test_lead_time_kosong_stok_menipis_tetap_mendapat_jumlah(self, monkeypatch):
        """
        Dulu inilah satu-satunya keadaan yang mendesak TANPA angka: sasaran
        pengisian bersandar pada kebutuhan masa tunggu, dan tanpa lead time ia
        tidak terhitung. Rumus barunya bersandar pada laju pemakaian, jadi
        jumlahnya terbit walau lead time belum diisi.
        """
        api, _, _ = jalankan(monkeypatch, **KASUS["8b_lead_time_kosong_stok_menipis"])
        assert api["action_status"] == "PERLU_REORDER"
        assert api["recommended_order_qty"] == 14      # 44 - 30
        assert api["order_qty_title"] == "Pesan 14 PCS"


# ==========================================================================
# Baris daftar Pemesanan Ulang
# ==========================================================================

class TestBarisDaftarReorder:
    """
    /api/reorder merakit barisnya dari `_susun()` yang sama, jadi kursor palsu
    yang sama dapat dipakai. Yang diperiksa di sini bukan rumusnya -- itu sudah
    dijaga uji di atas -- melainkan JANJI BENTUKNYA: setiap field yang dirender
    kolom tabel ada, bulat, dan tidak berselisih dengan jawaban /api/forecast
    untuk barang yang sama.
    """

    # Kolom tabel dan panel detailnya membaca field ini apa adanya.
    FIELD_BULAT = (
        "current_stock_int", "available_stock_int", "reorder_point_int",
        "effective_reorder_point_int", "safety_stock_int",
        "lead_time_days_int", "lead_time_demand_int", "forecast_usage_int",
        "days_of_cover_int", "days_to_effective_rop_int",
        "order_up_to_level_int", "recommended_order_qty",
        "decision_horizon_days",
    )

    def _baris(self, monkeypatch, nama):
        from app.routers import reorder as ro
        # Kursor palsu dipasang lewat jalur yang sama dengan jalankan().
        jalankan(monkeypatch, **KASUS[nama])
        return ro._baris(1, 1, "id")

    @pytest.mark.parametrize("nama", NAMA_KASUS)
    def test_seluruh_field_kolom_ada_dan_bulat(self, monkeypatch, nama):
        b = self._baris(monkeypatch, nama)
        for f in self.FIELD_BULAT:
            assert f in b, f"{nama}: kolom membaca {f}, tidak ada pada baris"
            assert not _pecahan(b[f]), f"{nama}: {f} = {b[f]!r}"

    @pytest.mark.parametrize("nama", NAMA_KASUS)
    def test_tidak_berselisih_dengan_api_forecast(self, monkeypatch, nama):
        """
        Satu barang, dua endpoint, satu kesimpulan. Inilah yang paling mudah
        rusak tanpa disadari: daftar dan layar detail dihitung dua panggilan
        yang berbeda, dan tidak ada apa pun di layar yang akan menunjukkan
        bahwa keduanya mulai berselisih.
        """
        api, _, _ = jalankan(monkeypatch, **KASUS[nama])
        b = self._baris(monkeypatch, nama)
        for f in ("action_status", "priority", "recommended_order_qty",
                  "effective_reorder_point_int", "available_stock_int",
                  "reorder_point_int", "safety_stock_int"):
            assert b[f] == api[f], f"{nama}: {f}"

    @pytest.mark.parametrize("nama", NAMA_KASUS)
    def test_jumlah_tidak_pernah_negatif(self, monkeypatch, nama):
        b = self._baris(monkeypatch, nama)
        assert (b["recommended_order_qty"] or 0) >= 0, nama

    @pytest.mark.parametrize("nama", NAMA_KASUS)
    def test_horizon_tidak_mengikuti_periode_layar(self, monkeypatch, nama):
        """
        Kebutuhan yang dicetak kolom Forecast berpatokan horizon KEPUTUSAN yang
        dipatok, bukan `days` yang diminta layar Prakiraan.
        """
        from app import decision as d
        b = self._baris(monkeypatch, nama)
        assert b["decision_horizon_days"] == d.HORIZON_KEPUTUSAN, nama
