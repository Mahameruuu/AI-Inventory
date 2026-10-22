# -*- coding: utf-8 -*-
"""
Uji master data, transfer, penyesuaian stok, dan impor berkas.

    .venv/bin/python -m pytest backend/tests/test_master.py -q

Yang dijaga di sini bukan "endpoint-nya menjawab 200", melainkan hal-hal yang
baru terasa salah setelah dipakai berminggu-minggu:

  - saldo stok harus tetap sama dengan jumlah seluruh pergerakan setelah
    transfer dan penyesuaian, sama seperti setelah penerimaan dan pengeluaran;
  - master data yang sudah dipakai transaksi TIDAK boleh terhapus, karena
    riwayatnya akan kehilangan arti;
  - impor yang dijalankan dua kali dengan berkas yang sama tidak boleh
    menggandakan apa pun;
  - sel yang dikosongkan pada berkas impor ulang tidak boleh menghapus nilai
    yang sudah ada.
"""

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import INDUK, NAMA_DB_UJI, bangun_basis_uji, buat_perusahaan  # noqa: E402

SANDI = "kataSandiMaster12"


@pytest.fixture(scope="module")
def klien():
    alasan = bangun_basis_uji()
    if alasan:
        pytest.skip(f"basis data uji tidak tersedia: {alasan}")

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def h(klien):
    """Header owner sebuah perusahaan kosong."""
    s = buat_perusahaan(klien, "PT Uji Master", "Master Tester", "master", SANDI)
    return {"Authorization": "Bearer " + s["access_token"]}


@pytest.fixture(scope="module")
def dasar(klien, h):
    """Kategori, satuan, dua gudang, dan satu supplier -- dibuat lewat API."""
    kat = klien.post("/api/categories", headers=h,
                     json={"name": "Sparepart Mesin"}).json()
    sat = klien.post("/api/units", headers=h,
                     json={"name": "Pieces", "code": "pcs"}).json()
    g1 = klien.post("/api/warehouses", headers=h,
                    json={"code": "wh-jkt", "name": "Gudang Jakarta"}).json()
    g2 = klien.post("/api/warehouses", headers=h,
                    json={"code": "wh-sby", "name": "Gudang Surabaya"}).json()
    sup = klien.post("/api/suppliers", headers=h,
                     json={"code": "sup-01", "name": "PT Pemasok",
                           "lead_time_days": 7}).json()
    return {"kategori": kat, "satuan": sat, "g1": g1, "g2": g2, "supplier": sup}


def test_kode_dinormalkan_menjadi_huruf_besar(klien, h, dasar):
    """
    "pcs" dan "PCS" adalah satuan yang sama. Membiarkan keduanya hidup
    berdampingan menghasilkan dua satuan yang tampak sah pada daftar pilihan,
    dan riwayat yang terbelah di antara keduanya.
    """
    assert dasar["satuan"]["code"] == "PCS"
    assert dasar["g1"]["code"] == "WH-JKT"
    assert dasar["supplier"]["code"] == "SUP-01"


def test_kode_ganda_ditolak_dengan_menyebut_nilainya(klien, h, dasar):
    r = klien.post("/api/warehouses", headers=h,
                   json={"code": "WH-JKT", "name": "Gudang Kembar"})
    assert r.status_code == 409
    # Pesannya harus menyebut nilai yang bentrok, bukan hanya "sudah ada":
    # orang yang menempelkan dua ratus baris perlu tahu yang mana.
    assert "WH-JKT" in r.json()["error"]["message"]


def test_patch_hanya_menulis_kolom_yang_dikirim(klien, h, dasar):
    """
    Layar yang hanya menampilkan nomor telepon tidak boleh mengosongkan alamat
    hanya karena alamat tidak ikut dikirim.
    """
    sid = dasar["supplier"]["id"]
    klien.patch(f"/api/suppliers/{sid}", headers=h,
                json={"address": "Jl. Industri No. 5, Bekasi"})
    klien.patch(f"/api/suppliers/{sid}", headers=h, json={"phone": "021-555-0100"})

    s = klien.get("/api/suppliers", headers=h).json()["items"]
    baris = next(x for x in s if x["id"] == sid)
    assert baris["address"] == "Jl. Industri No. 5, Bekasi"
    assert baris["phone"] == "021-555-0100"


def test_kekritisan_disamakan_bentuknya(klien, h, dasar):
    r = klien.post("/api/items", headers=h, json={
        "sku": "krit-01", "name": "Barang Kritis",
        "category_id": dasar["kategori"]["id"], "unit_id": dasar["satuan"]["id"],
        "criticality": "HIGH"})
    assert r.status_code == 201
    assert r.json()["criticality"] == "high"
    assert r.json()["sku"] == "KRIT-01"


def test_kekritisan_asing_ditolak(klien, h, dasar):
    r = klien.post("/api/items", headers=h, json={
        "sku": "krit-02", "name": "Barang X",
        "category_id": dasar["kategori"]["id"], "unit_id": dasar["satuan"]["id"],
        "criticality": "sangat penting"})
    assert r.status_code == 422


def test_kategori_tak_dikenal_ditolak_dengan_jelas(klien, h, dasar):
    r = klien.post("/api/items", headers=h, json={
        "sku": "xx-01", "name": "Barang", "category_id": 999999,
        "unit_id": dasar["satuan"]["id"]})
    assert r.status_code == 404
    assert r.json()["error"]["field"] == "category_id"


def test_master_yang_belum_dipakai_boleh_dihapus(klien, h):
    baru = klien.post("/api/categories", headers=h,
                      json={"name": "Salah Ketikk"}).json()
    r = klien.delete(f"/api/categories/{baru['id']}", headers=h)
    assert r.status_code == 200
    sisa = klien.get("/api/categories", headers=h).json()["items"]
    assert all(k["name"] != "Salah Ketikk" for k in sisa)


def test_master_yang_sudah_dipakai_tidak_boleh_dihapus(klien, h, dasar):
    """
    Menghapus kategori yang dipakai barang berarti riwayat transaksi barang itu
    kehilangan artinya. Yang ditawarkan sebagai gantinya -- menonaktifkan --
    disebut di dalam pesannya.
    """
    r = klien.delete(f"/api/categories/{dasar['kategori']['id']}", headers=h)
    assert r.status_code == 409
    assert "nonaktif" in r.json()["error"]["message"].lower()


def test_staf_tidak_boleh_mengubah_master(klien, h, dasar):
    klien.post("/api/users", headers=h, json={
        "username": "staf", "full_name": "Staf Gudang",
        "password": "kataSandiStaf12", "role": "staff"})
    s = klien.post("/api/auth/login", json={
        "username": "staf", "password": "kataSandiStaf12"}).json()
    hs = {"Authorization": "Bearer " + s["access_token"]}

    assert klien.get("/api/items", headers=hs).status_code == 200
    assert klien.post("/api/categories", headers=hs,
                      json={"name": "Diam-diam"}).status_code == 403


# ==========================================================================
# Transfer antar gudang
# ==========================================================================

@pytest.fixture(scope="module")
def berstok(klien, h, dasar):
    """Satu barang dengan 100 unit di gudang Jakarta."""
    barang = klien.post("/api/items", headers=h, json={
        "sku": "trf-01", "name": "Barang Transfer",
        "category_id": dasar["kategori"]["id"], "unit_id": dasar["satuan"]["id"],
        "unit_price": 50000, "reorder_point": 20}).json()

    r = klien.post("/api/stock-receipts", headers=h, json={
        "warehouse_id": dasar["g1"]["id"], "supplier_id": dasar["supplier"]["id"],
        "received_date": "2026-08-01",
        "items": [{"item_id": barang["id"], "quantity": 100, "unit_price": 50000}]})
    assert r.status_code == 201, r.text[:300]
    return barang


RUAS_FORMULIR_BARANG = (
    "sku", "name", "category_id", "unit_id", "unit_price", "minimum_stock",
    "maximum_stock", "reorder_point", "safety_stock", "lead_time_days",
    "criticality", "is_active",
)

RUAS_FORMULIR_SUPPLIER = (
    "code", "name", "phone", "email", "address", "lead_time_days", "is_active",
)


def test_daftar_barang_membawa_semua_ruas_formulir(klien, h, dasar, berstok):
    baris = klien.get("/api/items", headers=h).json()["items"][0]
    kurang = [r for r in RUAS_FORMULIR_BARANG if r not in baris]
    assert not kurang, f"kolom tidak dikembalikan daftar barang: {kurang}"


def test_daftar_supplier_membawa_semua_ruas_formulir(klien, h, dasar):
    baris = klien.get("/api/suppliers", headers=h).json()["items"][0]
    kurang = [r for r in RUAS_FORMULIR_SUPPLIER if r not in baris]
    assert not kurang, f"kolom tidak dikembalikan daftar supplier: {kurang}"


@pytest.mark.parametrize("jalur,ruas", [
    ("/api/categories", ("name", "description", "is_active")),
    ("/api/units", ("name", "code", "is_active")),
    ("/api/warehouses", ("code", "name", "location", "is_active")),
])
def test_daftar_master_lain_membawa_ruas_formulirnya(klien, h, dasar, jalur, ruas):
    baris = klien.get(jalur, headers=h).json()["items"][0]
    kurang = [r for r in ruas if r not in baris]
    assert not kurang, f"{jalur}: kolom tidak dikembalikan: {kurang}"


def test_ubah_barang_dari_baris_daftar_utuh(klien, h, dasar, berstok):
    """
    Meniru persis yang dikerjakan layar: ambil baris dari daftar, isi
    formulir dari situ, ubah satu ruas saja, kirim kembali seluruh isian.
    Kategori dan satuan harus tetap seperti semula.
    """
    baris = next(x for x in klien.get("/api/items", headers=h).json()["items"]
                 if x["sku"] == "TRF-01")
    isian = {r: baris[r] for r in RUAS_FORMULIR_BARANG
             if baris.get(r) not in (None, "")}
    isian["name"] = "Barang Transfer (diperbarui)"

    r = klien.patch(f"/api/items/{baris['id']}", headers=h, json=isian)
    assert r.status_code == 200, r.text[:300]

    sesudah = r.json()
    assert sesudah["name"] == "Barang Transfer (diperbarui)"
    assert sesudah["category_id"] == dasar["kategori"]["id"]
    assert sesudah["unit_id"] == dasar["satuan"]["id"]
