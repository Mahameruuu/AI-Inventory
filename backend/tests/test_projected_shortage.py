# -*- coding: utf-8 -*-
"""
Uji field `projected_shortage` pada mesin prakiraan (app/forecasting.py).

    .venv/bin/python -m pytest backend/tests -q

Yang diuji bukan "apakah rumusnya jalan", melainkan tiga hal yang mudah
terlewat: bahwa besaran defisit selamat dari pemangkasan `expected_stock` ke
nol, bahwa stok yang mencukupi menghasilkan nol dan bukan angka negatif, dan
bahwa histori yang belum cukup menghasilkan None -- bukan nol, yang akan
terbaca sebagai "tidak kurang".
"""

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import forecasting as f  # noqa: E402


def _deret(nilai: list[float], akhir: date) -> list[tuple[date, float]]:
    """Deret harian berakhir pada `akhir`, satu nilai per hari."""
    n = len(nilai)
    return [(akhir - timedelta(days=n - 1 - i), v) for i, v in enumerate(nilai)]


def _jalankan(*, stok, keluar_harian: list[float], hari_prakiraan: int,
              ramalan: list[float] | None = None):
    akhir = date(2026, 8, 24)
    keluar = _deret(keluar_harian, akhir)
    # Neto dibuat sama dengan pengeluaran (negatif) supaya rekonstruksi saldo
    # historis konsisten; yang diuji di sini bukan bagian itu.
    neto = [(t, -v) for t, v in keluar]
    return f.hitung(
        as_of=akhir,
        current_stock=stok,
        daily_outflow=keluar,
        daily_net=neto,
        minimum_stock=10,
        reorder_point=20,
        forecast_days=hari_prakiraan,
        historical_days=len(keluar_harian),
        ramalan_harian=ramalan,
    )


class TestProjectedShortage:

    def test_kekurangan_terhitung_saat_kebutuhan_melampaui_stok(self):
        """Kasus utama: butuh 1.000, stok 400, kurang 600."""
        # Ramalan 100/hari selama 10 hari = kebutuhan 1.000.
        h = _jalankan(
            stok=400,
            keluar_harian=[100.0] * 20,
            hari_prakiraan=10,
            ramalan=[100.0] * 10,
        )
        assert h["predicted_usage"] == 1000
        assert h["current_stock"] == 400
        assert h["projected_shortage"] == 600

    def test_kekurangan_selamat_dari_pemangkasan_expected_stock(self):
        """
        expected_stock berhenti di nol, projected_shortage tidak.

        Dua kebutuhan yang jauh berbeda menghasilkan expected_stock yang sama
        persis; yang membedakannya hanya field baru ini.
        """
        ringan = _jalankan(stok=400, keluar_harian=[50.0] * 20,
                           hari_prakiraan=10, ramalan=[50.0] * 10)
        berat = _jalankan(stok=400, keluar_harian=[100.0] * 20,
                          hari_prakiraan=10, ramalan=[100.0] * 10)

        assert ringan["predicted_remaining_stock"] == 0
        assert berat["predicted_remaining_stock"] == 0
        assert ringan["projected_shortage"] == 100
        assert berat["projected_shortage"] == 600

    def test_nol_saat_stok_mencukupi(self):
        h = _jalankan(stok=5000, keluar_harian=[100.0] * 20,
                      hari_prakiraan=10, ramalan=[100.0] * 10)
        assert h["predicted_usage"] == 1000
        assert h["projected_shortage"] == 0

    def test_tidak_pernah_negatif(self):
        h = _jalankan(stok=100000, keluar_harian=[1.0] * 20, hari_prakiraan=7)
        assert h["projected_shortage"] >= 0

    def test_nol_saat_kebutuhan_persis_sama_dengan_stok(self):
        """Batas tepat: kebutuhan == stok berarti cukup, bukan kurang."""
        h = _jalankan(stok=1000, keluar_harian=[100.0] * 20,
                      hari_prakiraan=10, ramalan=[100.0] * 10)
        assert h["predicted_usage"] == 1000
        assert h["projected_shortage"] == 0

    def test_none_saat_histori_belum_cukup(self):
        """
        Nol berarti "tidak kurang" -- klaim yang belum boleh dibuat saat
        angkanya memang tidak ada.
        """
        h = _jalankan(stok=400, keluar_harian=[5.0, 0.0, 0.0], hari_prakiraan=10)
        assert h["status"] == f.STATUS_INSUFFICIENT
        assert h["projected_shortage"] is None
        assert h["predicted_usage"] is None

    def test_konsisten_dengan_jalur_rata_rata_bergerak(self):
        """Tanpa ramalan model, field tetap terisi dan tetap konsisten."""
        h = _jalankan(stok=100, keluar_harian=[20.0] * 20, hari_prakiraan=30)
        assert h["method"] == "weighted_moving_average"
        assert h["projected_shortage"] == round(h["predicted_usage"] - 100, 3)


class TestFieldLamaTidakBerubah:
    """Perilaku yang sudah dipakai frontend harus tetap persis seperti semula."""

    def test_expected_stock_masih_dipangkas_ke_nol(self):
        h = _jalankan(stok=400, keluar_harian=[100.0] * 20,
                      hari_prakiraan=10, ramalan=[100.0] * 10)
        assert h["predicted_remaining_stock"] == 0

    def test_seluruh_kunci_lama_masih_ada(self):
        lama = {
            "status", "method", "baseline_daily_outflow", "message",
            "current_stock", "average_daily_outflow", "historical_period",
            "forecast_days", "predicted_usage", "predicted_remaining_stock",
            "days_until_reorder_point", "reorder_crossing_date",
            "days_until_stockout", "reorder_point", "minimum_stock",
            "data_quality", "requirements", "historical_data", "forecast_data",
        }
        h = _jalankan(stok=400, keluar_harian=[100.0] * 20, hari_prakiraan=10)
        assert lama <= set(h)

    def test_kunci_lama_lengkap_pada_cabang_histori_kurang(self):
        kurang = _jalankan(stok=400, keluar_harian=[5.0], hari_prakiraan=10)
        cukup = _jalankan(stok=400, keluar_harian=[100.0] * 20, hari_prakiraan=10)
        # Cabang "belum cukup" tidak membawa kunci metode; selebihnya sama.
        assert set(cukup) - set(kurang) == {"method", "baseline_daily_outflow"}
