# -*- coding: utf-8 -*-
"""
Jenis pemakaian barang (items.usage_type, migrasi 034): berumur_pakai
dijadwalkan, habis_pakai diprakirakan.
"""
import pytest

from tests.test_demo import dunia, klien  # noqa: F401  (fixture yang sama)


def _isi_demo(klien, dunia):
    r = klien.post("/api/demo/reset", headers=dunia["hDemo"], params={"hari": 30})
    assert r.status_code == 200, r.text[:300]


def test_penyaring_jenis_pada_daftar_barang(klien, dunia):
    _isi_demo(klien, dunia)
    h = dunia["hDemo"]
    umur = klien.get("/api/items", headers=h,
                     params={"usage_type": "berumur_pakai", "page_size": 100}).json()
    habis = klien.get("/api/items", headers=h,
                      params={"usage_type": "habis_pakai", "page_size": 100}).json()
    semua = klien.get("/api/items", headers=h, params={"page_size": 100}).json()
    # Dua puluh komponen berumur pakai + sepuluh barang harian.
    assert umur["total"] == 20 and habis["total"] == 10
    assert umur["total"] + habis["total"] == semua["total"]
    assert all(b["usage_type"] == "berumur_pakai" for b in umur["items"])
    assert all(b["usage_type"] == "habis_pakai" for b in habis["items"])


def test_jenis_tidak_dikenal_ditolak(klien, dunia):
    r = klien.get("/api/items", headers=dunia["hDemo"],
                  params={"usage_type": "cepat"})
    assert r.status_code == 422
    r = klien.get("/api/inventory", headers=dunia["hDemo"],
                  params={"usage_type": "cepat"})
    assert r.status_code == 422


def test_stok_dan_prakiraan_menyebut_jenis(klien, dunia):
    _isi_demo(klien, dunia)
    h = dunia["hDemo"]
    baris = klien.get("/api/inventory", headers=h,
                      params={"usage_type": "berumur_pakai", "page_size": 5}).json()["items"]
    assert baris and all(b["usage_type"] == "berumur_pakai" for b in baris)
    f = klien.get("/api/forecast", headers=h, params={
        "item_id": baris[0]["item_id"], "warehouse_id": baris[0]["warehouse_id"],
        "include_recommendation": False}).json()
    assert f["item"]["usage_type"] == "berumur_pakai"


def test_jenis_dapat_diubah_lewat_master(klien, dunia):
    _isi_demo(klien, dunia)
    h = dunia["hDemo"]
    b = klien.get("/api/items", headers=h,
                  params={"usage_type": "habis_pakai", "page_size": 1}).json()["items"][0]
    r = klien.patch(f"/api/items/{b['id']}", headers=h,
                    json={"usage_type": "berumur_pakai"})
    assert r.status_code == 200, r.text[:300]
    assert r.json()["usage_type"] == "berumur_pakai"
    r = klien.patch(f"/api/items/{b['id']}", headers=h, json={"usage_type": "asal"})
    assert r.status_code == 422
