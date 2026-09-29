# -*- coding: utf-8 -*-
"""
Uji pemisahan penyewa, lewat API sungguhan dan basis data sungguhan.

    .venv/bin/python -m pytest backend/tests/test_penyewa.py -q

KENAPA BUKAN UJI UNIT. Yang dijaga di sini adalah perilaku yang lahir dari
kerja sama tiga lapis: dependency yang menyetel penyewa (app/auth.py),
app/db.py yang menyalinnya ke setelan sesi PostgreSQL, dan policy Row Level
Security pada migrasi 028. Tidak satu pun dari ketiganya salah bila diuji
sendiri-sendiri; yang salah adalah sambungannya.

Dua kegagalan berikut betul-betul terjadi saat lapisan ini dibangun, dan
keduanya TIDAK terlihat oleh uji unit mana pun:

  1. Dependency yang sync dijalankan FastAPI di utas pekerja dengan SALINAN
     context, sehingga penyewa yang disetel di dalamnya lenyap sebelum endpoint
     berjalan. Setiap permintaan dijawab 200 dan setiap halaman kosong.

  2. Setelan sesi yang dipasang set_config(..., true) kembali menjadi STRING
     KOSONG -- bukan tidak ada -- begitu transaksi selesai, sehingga
     permintaan KEDUA pada koneksi pool yang sama gagal mengurai ''::bigint.
     Menguji satu permintaan tidak akan pernah menemukannya.

Karena itu berkas ini menjalankan permintaan berturut-turut lewat TestClient,
bukan memanggil fungsinya langsung.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import INDUK, NAMA_DB_UJI, bangun_basis_uji  # noqa: E402

SANDI_A = "kataSandiAlfa1"
SANDI_B = "kataSandiBeta1"


@pytest.fixture(scope="module")
def klien():
    """API yang menghadap basis data uji yang baru dibangun."""
    alasan = bangun_basis_uji()
    if alasan:
        pytest.skip(f"basis data uji tidak tersedia: {alasan}")

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def dunia(klien):
    """
    Dua perusahaan, masing-masing dengan barang dan gudang yang SENGAJA
    memakai kode dan SKU yang sama persis. Kesamaan itu bagian dari ujinya:
    ia yang membuktikan keunikan kini dihitung per perusahaan, dan ia pula yang
    membuat kebocoran mudah terlihat -- nama barangnya yang berbeda.
    """
    import psycopg

    a = klien.post("/api/auth/signup", json={
        "company_name": "PT Alfa Sejahtera", "full_name": "Andi Pratama",
        "email": "andi@alfacorp.id", "password": SANDI_A}).json()
    b = klien.post("/api/auth/signup", json={
        "company_name": "PT Beta Makmur", "full_name": "Budi Santoso",
        "email": "budi@betacorp.id", "password": SANDI_B}).json()

    # Diisi sebagai admin basis data, bukan lewat API: modul input master data
    # belum ada, dan yang sedang diuji bukan cara data itu masuk melainkan
    # siapa yang boleh melihatnya setelah masuk.
    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}", autocommit=True) as k, k.cursor() as cur:
        for sesi, tanda in ((a, "ALFA"), (b, "BETA")):
            cid = sesi["company"]["id"]
            cur.execute("INSERT INTO categories (company_id, name) VALUES (%s,'Umum') RETURNING id", (cid,))
            kat = cur.fetchone()[0]
            cur.execute("INSERT INTO units (company_id, name, code) VALUES (%s,'Pieces','PCS') RETURNING id", (cid,))
            sat = cur.fetchone()[0]
            cur.execute("INSERT INTO warehouses (company_id, code, name) VALUES (%s,'WH-01',%s)",
                        (cid, f"Gudang {tanda}"))
            for n in (1, 2):
                cur.execute(
                    """INSERT INTO items (company_id, sku, name, category_id, unit_id, unit_price)
                       VALUES (%s,%s,%s,%s,%s,1000)""",
                    (cid, f"SKU-00{n}", f"Barang {tanda} {n}", kat, sat))

    return {
        "a": a, "b": b,
        "hA": {"Authorization": "Bearer " + a["access_token"]},
        "hB": {"Authorization": "Bearer " + b["access_token"]},
    }


# ==========================================================================
# Tanpa token
# ==========================================================================

def test_health_tidak_menuntut_token(klien):
    assert klien.get("/api/health").status_code == 200


@pytest.mark.parametrize("jalur", [
    "/api/items", "/api/dashboard", "/api/warehouses", "/api/inventory",
    "/api/users", "/api/reports/stock",
])
def test_endpoint_data_menolak_tanpa_token(klien, jalur):
    assert klien.get(jalur).status_code == 401


def test_tanda_tangan_token_diperiksa(klien, dunia):
    import jwt as pyjwt
    palsu = pyjwt.encode(
        {"sub": "1", "cid": dunia["b"]["company"]["id"], "role": "owner",
         "tv": 1, "exp": 9_999_999_999},
        "kunci-yang-ditebak-penyerang", algorithm="HS256")
    r = klien.get("/api/items", headers={"Authorization": "Bearer " + palsu})
    assert r.status_code == 401


# ==========================================================================
# Pendaftaran
# ==========================================================================

def test_pendaftar_menjadi_owner(dunia):
    assert dunia["a"]["user"]["role"] == "owner"
    assert dunia["a"]["company"]["slug"] == "pt-alfa-sejahtera"


def test_dua_perusahaan_berbeda(dunia):
    assert dunia["a"]["company"]["id"] != dunia["b"]["company"]["id"]


def test_email_ganda_ditolak(klien, dunia):
    r = klien.post("/api/auth/signup", json={
        "company_name": "PT Lain Sekali", "full_name": "Xavier Tan",
        "email": "andi@alfacorp.id", "password": "kataSandiLain1"})
    assert r.status_code == 409


# ==========================================================================
# Yang terlihat masing-masing penyewa
# ==========================================================================

def test_daftar_barang_hanya_milik_sendiri(klien, dunia):
    a = klien.get("/api/items", headers=dunia["hA"]).json()["items"]
    b = klien.get("/api/items", headers=dunia["hB"]).json()["items"]
    assert sorted(x["name"] for x in a) == ["Barang ALFA 1", "Barang ALFA 2"]
    assert sorted(x["name"] for x in b) == ["Barang BETA 1", "Barang BETA 2"]


def test_sku_sama_boleh_ada_di_dua_perusahaan(klien, dunia):
    """Keunikan SKU dihitung per perusahaan (migrasi 027). Bila constraint
    lamanya masih berlaku, penyisipan pada fixture sudah gagal lebih dulu."""
    a = klien.get("/api/items", headers=dunia["hA"]).json()["items"]
    b = klien.get("/api/items", headers=dunia["hB"]).json()["items"]
    assert {x["sku"] for x in a} == {x["sku"] for x in b} == {"SKU-001", "SKU-002"}


def test_daftar_gudang_hanya_milik_sendiri(klien, dunia):
    g = klien.get("/api/warehouses", headers=dunia["hA"]).json()["items"]
    assert [x["name"] for x in g] == ["Gudang ALFA"]


def test_permintaan_berturut_turut_tetap_benar(klien, dunia):
    """
    Menyentuh koneksi pool berkali-kali dengan penyewa yang berganti-ganti.

    Inilah bentuk uji yang menemukan setelan sesi yang tertinggal menjadi
    string kosong. Satu permintaan saja selalu lulus.
    """
    for _ in range(6):
        a = klien.get("/api/items", headers=dunia["hA"]).json()["items"]
        b = klien.get("/api/items", headers=dunia["hB"]).json()["items"]
        assert all(x["name"].startswith("Barang ALFA") for x in a)
        assert all(x["name"].startswith("Barang BETA") for x in b)
        assert len(a) == len(b) == 2


# ==========================================================================
# Menjangkau baris penyewa lain lewat id
# ==========================================================================

def test_membaca_id_milik_penyewa_lain_menjadi_404(klien, dunia):
    id_b = klien.get("/api/items", headers=dunia["hB"]).json()["items"][0]["id"]
    assert klien.get(f"/api/items/{id_b}", headers=dunia["hA"]).status_code == 404


def test_menulis_ke_baris_penyewa_lain_ditolak(klien, dunia):
    import psycopg
    id_b = klien.get("/api/items", headers=dunia["hB"]).json()["items"][0]["id"]
    r = klien.patch(f"/api/items/{id_b}/reorder-point",
                    headers=dunia["hA"], json={"reorder_point": 999})
    assert r.status_code in (404, 422)

    # Kode jawaban saja belum cukup: yang benar-benar penting adalah barisnya
    # tidak berubah.
    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute("SELECT reorder_point FROM items WHERE id = %s", (id_b,))
        assert cur.fetchone()[0] is None


# ==========================================================================
# Masuk
# ==========================================================================

def test_masuk_dengan_kredensial_benar(klien, dunia):
    r = klien.post("/api/auth/login",
                   json={"email": "andi@alfacorp.id", "password": SANDI_A})
    assert r.status_code == 200
    assert r.json()["company"]["id"] == dunia["a"]["company"]["id"]


def test_email_tak_terdaftar_dan_sandi_salah_tak_dapat_dibedakan(klien, dunia):
    """
    Kalimat yang berbeda membuat halaman masuk menjadi alat memeriksa email
    mana yang terdaftar -- separuh pekerjaan pembobolan selesai sebelum kata
    sandi pertama dicoba.
    """
    salah = klien.post("/api/auth/login",
                       json={"email": "andi@alfacorp.id", "password": "salahsekali"})
    tiada = klien.post("/api/auth/login",
                       json={"email": "hantu@alfacorp.id", "password": "salahsekali"})
    assert salah.status_code == tiada.status_code == 401
    assert salah.json()["error"]["message"] == tiada.json()["error"]["message"]


# ==========================================================================
# Peran
# ==========================================================================

def test_peran_membatasi_pengelolaan_pengguna(klien, dunia):
    r = klien.post("/api/users", headers=dunia["hA"], json={
        "email": "citra@alfacorp.id", "full_name": "Citra Dewi",
        "password": "kataSandiCitra1", "role": "viewer"})
    assert r.status_code == 201

    v = klien.post("/api/auth/login", json={
        "email": "citra@alfacorp.id", "password": "kataSandiCitra1"}).json()
    hV = {"Authorization": "Bearer " + v["access_token"]}

    assert klien.get("/api/items", headers=hV).status_code == 200
    assert klien.get("/api/users", headers=hV).status_code == 403
    assert klien.post("/api/users", headers=hV, json={
        "email": "z@alfacorp.id", "full_name": "Zulkifli Rahman",
        "password": "kataSandiZzz1"}).status_code == 403


def test_peran_owner_tidak_dapat_diberikan(klien, dunia):
    r = klien.post("/api/users", headers=dunia["hA"], json={
        "email": "wawan@alfacorp.id", "full_name": "Wawan Setiawan",
        "password": "kataSandiWww1", "role": "owner"})
    assert r.status_code == 422


def test_owner_tidak_dapat_menurunkan_dirinya(klien, dunia):
    r = klien.patch(f"/api/users/{dunia['a']['user']['id']}",
                    headers=dunia["hA"], json={"role": "staff"})
    assert r.status_code == 422


# ==========================================================================
# Pencabutan sesi
# ==========================================================================

def test_menonaktifkan_pengguna_langsung_mematikan_tokennya(klien, dunia):
    klien.post("/api/users", headers=dunia["hA"], json={
        "email": "dodi@alfacorp.id", "full_name": "Dodi Kurnia",
        "password": "kataSandiDodi1", "role": "staff"})
    s = klien.post("/api/auth/login", json={
        "email": "dodi@alfacorp.id", "password": "kataSandiDodi1"}).json()
    h = {"Authorization": "Bearer " + s["access_token"]}
    assert klien.get("/api/items", headers=h).status_code == 200

    klien.patch(f"/api/users/{s['user']['id']}",
                headers=dunia["hA"], json={"is_active": False})

    # 401 dan bukan 403: token_version ikut naik, sehingga tokennya ditolak
    # sebagai tidak sah sebelum pemeriksaan is_active sempat dicapai. Yang
    # dijaga di sini adalah akibatnya -- tidak bisa dipakai lagi -- bukan lewat
    # jalur mana penolakannya terjadi.
    assert klien.get("/api/items", headers=h).status_code in (401, 403)


def test_ganti_sandi_mencabut_sesi_lama(klien, dunia):
    lama = dict(dunia["hB"])
    r = klien.post("/api/auth/change-password", headers=lama, json={
        "current_password": SANDI_B, "new_password": "kataSandiBeta2"})
    assert r.status_code == 200

    assert klien.get("/api/items", headers=lama).status_code == 401
    baru = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert klien.get("/api/items", headers=baru).status_code == 200

    # Fixture berbagi satu modul, jadi token B yang dipegang uji lain harus
    # ikut diperbarui.
    dunia["hB"] = baru
