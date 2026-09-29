# -*- coding: utf-8 -*-
"""
Uji jalur kegagalan pemuatan model XGBoost (app/ml/predict.py).

    .venv/bin/python -m pytest backend/tests/test_predict.py -q

Tanpa basis data. Yang dijaga di sini BUKAN akurasi model -- itu di luar
lingkup uji ini -- melainkan janji di docstring predict.py: "Prakiraan tidak
boleh mati hanya karena model bermasalah." Tiap cara model bisa gagal dimuat
(berkas hilang, metadata hilang, pustaka belum terpasang, dimatikan lewat
konfigurasi) harus berakhir di `tersedia() -> False` dan `info()["fallback"]
== "weighted_moving_average"`, bukan galat yang menjatuhkan proses.

Modul predict.py memuat model SEKALI ke variabel modul (_model, _alasan, dst)
dan menolak memuat ulang selama salah satunya sudah terisi (lihat _muat()).
Karena itu tiap uji di sini mengembalikan variabel-variabel itu ke None
sebelum dan sesudah berjalan, supaya satu skenario tidak mencemari yang lain.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml import predict  # noqa: E402


@pytest.fixture(autouse=True)
def _bersihkan_cache_model(monkeypatch):
    """
    Mengosongkan cache modul sebelum dan sesudah tiap uji, dan menyalakan
    kembali FORECAST_USE_MODEL -- tests/conftest.py mematikannya secara
    bawaan (FORECAST_USE_MODEL=false) supaya suite lain tidak diam-diam
    mencoba memuat model 757 MB. Uji di berkas ini justru menguji jalur
    pemuatan itu sendiri, jadi perlu dinyalakan lagi per uji.
    """
    def kosongkan():
        monkeypatch.setattr(predict, "_model", None)
        monkeypatch.setattr(predict, "_meta", None)
        monkeypatch.setattr(predict, "_kategori", None)
        monkeypatch.setattr(predict, "_kat_dtype", None)
        monkeypatch.setattr(predict, "_alasan", None)
    kosongkan()
    monkeypatch.setattr(predict, "FORECAST_USE_MODEL", True)
    yield
    kosongkan()


def test_dimatikan_lewat_konfigurasi(monkeypatch):
    monkeypatch.setattr(predict, "FORECAST_USE_MODEL", False)
    assert predict.tersedia() is False
    assert "dimatikan" in predict.info()["reason"]
    assert predict.info()["fallback"] == "weighted_moving_average"
    assert predict.metode() == "weighted_moving_average"


def test_berkas_model_tidak_ada(monkeypatch, tmp_path):
    monkeypatch.setattr(predict, "BERKAS_MODEL", tmp_path / "tidak_ada.json")
    monkeypatch.setattr(predict, "BERKAS_META", tmp_path / "meta_tidak_dipakai.json")
    assert predict.tersedia() is False
    assert "tidak ditemukan" in predict.info()["reason"]


def test_berkas_meta_tidak_ada(monkeypatch, tmp_path):
    berkas_model = tmp_path / "model.json"
    berkas_model.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(predict, "BERKAS_MODEL", berkas_model)
    monkeypatch.setattr(predict, "BERKAS_META", tmp_path / "meta_tidak_ada.json")
    assert predict.tersedia() is False
    assert "metadata" in predict.info()["reason"]


def test_pustaka_belum_terpasang(monkeypatch, tmp_path):
    """
    Mensimulasikan xgboost/pandas belum terpasang, terlepas dari apakah
    lingkungan uji ini kebetulan memilikinya -- ini jalur yang pernah
    membingungkan (lihat docstring _tentukan_dtype_kategori): sebelumnya galat
    aslinya tertelan dan selalu dilaporkan sebagai "tipe indeks kategori tidak
    cocok". Di sini kita pastikan pesannya menyebut pustaka yang hilang.
    """
    berkas_model = tmp_path / "model.json"
    berkas_model.write_text("{}", encoding="utf-8")
    berkas_meta = tmp_path / "meta.json"
    berkas_meta.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(predict, "BERKAS_MODEL", berkas_model)
    monkeypatch.setattr(predict, "BERKAS_META", berkas_meta)
    monkeypatch.setitem(sys.modules, "xgboost", None)

    assert predict.tersedia() is False
    assert "xgboost" in predict.info()["reason"]
    assert "belum terpasang" in predict.info()["reason"]


def test_ramal_deret_kembali_none_saat_model_tak_tersedia(monkeypatch, tmp_path):
    """Pemanggil (forecasting.py) mengandalkan None ini untuk pindah ke WMA."""
    monkeypatch.setattr(predict, "BERKAS_MODEL", tmp_path / "tidak_ada.json")
    monkeypatch.setattr(predict, "BERKAS_META", tmp_path / "tidak_dipakai.json")

    hasil = predict.ramal_deret(
        riwayat=[1.0] * 40, as_of=predict.date(2026, 1, 30), hari=3,
        current_stock=10.0, neto_hari_terakhir=-1.0, lead_time_days=3,
        reorder_point=5, safety_stock=2, unit_price=1000,
        item_id=1, warehouse_id=1, category_id=1)

    assert hasil is None


def test_kegagalan_tidak_melempar_galat(monkeypatch, tmp_path):
    """
    Berkas model ada tapi isinya sampah -- load_model() akan gagal di tengah.
    Skenario ini menegaskan bagian _muat_terkunci() yang menangkap Exception
    apa pun (baris "model rusak tidak boleh menjatuhkan API"): tersedia()
    tidak boleh melempar, hanya melaporkan tidak tersedia.
    """
    berkas_model = tmp_path / "model.json"
    berkas_model.write_text("bukan json xgboost yang sah", encoding="utf-8")
    berkas_meta = tmp_path / "meta.json"
    berkas_meta.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(predict, "BERKAS_MODEL", berkas_model)
    monkeypatch.setattr(predict, "BERKAS_META", berkas_meta)

    assert predict.tersedia() is False
    assert predict.info()["available"] is False
