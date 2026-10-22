# -*- coding: utf-8 -*-
"""
Stok opname dan jejak audit, lewat HTTP di atas basis data uji sungguhan.

    .venv/bin/python -m pytest backend/tests/test_opname_audit.py -q

Yang dikunci:
  - staf boleh membuat dan mengisi opname, tetapi TIDAK boleh mempostingnya;
  - posting menyetel stok sama dengan hasil hitung, menulis ledger
    'adjustment', dan melewati barang yang belum dihitung;
  - selisih dihitung terhadap stok SAAT POSTING, bukan saat draft dibuat;
  - setiap perubahan tercatat di audit_log beserta pelakunya, tanpa kata sandi;
  - role aplikasi tidak dapat menghapus atau menyunting jejak;
  - jejak satu perusahaan tidak terbaca perusahaan lain.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import INDUK, NAMA_DB_UJI, bangun_basis_uji  # noqa: E402

SANDI = "kataSandiOpname1"


@pytest.fixture(scope="module")
def klien():
    alasan = bangun_basis_uji()
    if alasan:
        pytest.skip(f"basis data uji tidak tersedia: {alasan}")
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def _masuk(klien, email):
    r = klien.post("/api/auth/login", json={"email": email, "password": SANDI})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="module")
def dunia(klien):
    import psycopg

    sesi = klien.post("/api/auth/signup", json={
        "company_name": "PT Uji Opname", "full_name": "Rina Owner",
        "email": "rina@ujiopname.id", "password": SANDI}).json()
    cid = sesi["company"]["id"]
    h_owner = {"Authorization": "Bearer " + sesi["access_token"]}

    r = klien.post("/api/users", headers=h_owner, json={
        "email": "staf@ujiopname.id", "full_name": "Sari Staf",
        "password": SANDI, "role": "staff"})
    assert r.status_code == 201, r.text
    h_staf = _masuk(klien, "staf@ujiopname.id")

    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}", autocommit=True) as k, k.cursor() as cur:
        cur.execute("INSERT INTO categories (company_id, name) VALUES (%s,'MRO') RETURNING id", (cid,))
        kat = cur.fetchone()[0]
        cur.execute("INSERT INTO units (company_id, name, code) VALUES (%s,'Pieces','PCS') RETURNING id",
                    (cid,))
        sat = cur.fetchone()[0]
        cur.execute("INSERT INTO warehouses (company_id, code, name) VALUES (%s,'WH-OPN','Gudang Opname')"
                    " RETURNING id", (cid,))
        wh = cur.fetchone()[0]
        barang = {}
        for sku, stok, cadang in (("OPN-A", 50, 0), ("OPN-B", 20, 0),
                                  ("OPN-C", 10, 0), ("OPN-D", 30, 8)):
            cur.execute(
                """INSERT INTO items (company_id, sku, name, category_id, unit_id, unit_price)
                   VALUES (%s,%s,%s,%s,%s,1000) RETURNING id""",
                (cid, sku, f"Barang {sku}", kat, sat))
            iid = cur.fetchone()[0]
            barang[sku] = iid
            cur.execute(
                """INSERT INTO inventory (company_id, item_id, warehouse_id, quantity,
                                          reserved_quantity, available_quantity)
                   VALUES (%s,%s,%s,%s,%s,%s)""", (cid, iid, wh, stok, cadang, stok - cadang))

    return {"cid": cid, "owner": h_owner, "staf": h_staf, "wh": wh, "barang": barang}


def _stok(item_id, wh):
    import psycopg
    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute("SELECT quantity, available_quantity FROM inventory"
                    " WHERE item_id=%s AND warehouse_id=%s", (item_id, wh))
        return cur.fetchone()


@pytest.fixture(scope="module")
def opname(klien, dunia):
    r = klien.post("/api/stock-opname", headers=dunia["staf"],
                   json={"warehouse_id": dunia["wh"], "notes": "opname bulanan"})
    assert r.status_code == 201, r.text
    return r.json()


class TestOpname:
    def test_draft_berisi_semua_barang_gudang(self, opname):
        assert opname["adjustment_number"].startswith("OPN-")
        assert opname["line_count"] == 4

    def test_staf_mengisi_hitungan(self, klien, dunia, opname):
        b = dunia["barang"]
        r = klien.patch(f"/api/stock-opname/{opname['id']}/lines", headers=dunia["staf"], json={
            "lines": [
                {"item_id": b["OPN-A"], "actual_quantity": 47, "note": "3 rusak"},
                {"item_id": b["OPN-B"], "actual_quantity": 20},
            ]})
        assert r.status_code == 200, r.text
        s = r.json()["summary"]
        assert s["counted_count"] == 2 and s["diff_count"] == 1
        baris = {x["sku"]: x for x in r.json()["lines"]}
        assert Decimal(baris["OPN-A"]["difference_quantity"]) == -3
        assert baris["OPN-A"]["counted_by_name"] == "Sari Staf"
        assert baris["OPN-C"]["actual_quantity"] is None

    def test_staf_tidak_boleh_memposting(self, klien, dunia, opname):
        r = klien.post(f"/api/stock-opname/{opname['id']}/post", headers=dunia["staf"])
        assert r.status_code == 403

    def test_hitungan_di_bawah_cadangan_ditolak_saat_posting(self, klien, dunia, opname):
        b = dunia["barang"]
        klien.patch(f"/api/stock-opname/{opname['id']}/lines", headers=dunia["staf"],
                    json={"lines": [{"item_id": b["OPN-D"], "actual_quantity": 5}]})
        r = klien.post(f"/api/stock-opname/{opname['id']}/post", headers=dunia["owner"])
        assert r.status_code == 422 and r.json()["error"]["code"] == "BELOW_RESERVED"
        # dikosongkan lagi: "belum dihitung", bukan nol
        r = klien.patch(f"/api/stock-opname/{opname['id']}/lines", headers=dunia["staf"],
                        json={"lines": [{"item_id": b["OPN-D"], "actual_quantity": None}]})
        assert {x["sku"]: x for x in r.json()["lines"]}["OPN-D"]["actual_quantity"] is None

    def test_posting_memakai_stok_saat_posting(self, klien, dunia, opname):
        b, wh = dunia["barang"], dunia["wh"]
        # Barang B keluar 2 unit di tengah penghitungan: hitungan 20 tetap
        # kebenaran fisik, jadi selisihnya diukur terhadap 18, bukan 20.
        r = klien.post("/api/stock-issues", headers=dunia["staf"], json={
            "warehouse_id": wh, "issue_date": str(__import__("datetime").date.today()),
            "items": [{"item_id": b["OPN-B"], "quantity": 2}]})
        assert r.status_code == 201, r.text
        assert klien.get(f"/api/stock-opname/{opname['id']}",
                         headers=dunia["owner"]).json()["summary"]["moved_since_draft"] == 1

        r = klien.post(f"/api/stock-opname/{opname['id']}/post", headers=dunia["owner"])
        assert r.status_code == 200, r.text
        hasil = r.json()
        assert hasil["opname"]["status"] == "completed"
        assert hasil["opname"]["approved_by_name"] == "Rina Owner"
        assert hasil["adjusted_count"] == 2

        assert _stok(b["OPN-A"], wh)[0] == 47
        assert _stok(b["OPN-B"], wh)[0] == 20
        assert _stok(b["OPN-C"], wh)[0] == 10   # tidak dihitung, tidak disentuh
        baris = {x["sku"]: x for x in hasil["lines"]}
        assert Decimal(baris["OPN-B"]["difference_quantity"]) == 2

    def test_ledger_mencatat_adjustment_beserta_pelakunya(self, dunia, opname):
        import psycopg
        with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
            cur.execute(
                """SELECT m.item_id, m.quantity, u.full_name FROM stock_movements m
                   LEFT JOIN users u ON u.id = m.created_by
                   WHERE m.movement_type='adjustment' AND m.reference_id=%s ORDER BY m.item_id""",
                (opname["id"],))
            rows = cur.fetchall()
        b = dunia["barang"]
        assert [(r[0], r[1]) for r in rows] == [(b["OPN-A"], -3), (b["OPN-B"], 2)]
        assert {r[2] for r in rows} == {"Rina Owner"}

    def test_dokumen_selesai_tidak_dapat_diubah(self, klien, dunia, opname):
        r = klien.patch(f"/api/stock-opname/{opname['id']}/lines", headers=dunia["staf"],
                        json={"lines": [{"item_id": dunia["barang"]["OPN-C"], "actual_quantity": 1}]})
        assert r.status_code == 409
        r = klien.post(f"/api/stock-opname/{opname['id']}/post", headers=dunia["owner"])
        assert r.status_code == 409

    def test_draft_dapat_dibatalkan(self, klien, dunia):
        r = klien.post("/api/stock-opname", headers=dunia["staf"], json={"warehouse_id": dunia["wh"]})
        r = klien.post(f"/api/stock-opname/{r.json()['id']}/cancel", headers=dunia["staf"])
        assert r.status_code == 200 and r.json()["opname"]["status"] == "cancelled"

    def test_daftar(self, klien, dunia):
        r = klien.get("/api/stock-opname", headers=dunia["staf"])
        assert r.status_code == 200 and r.json()["total"] == 2


class TestAudit:
    def test_staf_tidak_boleh_membaca_jejak(self, klien, dunia):
        assert klien.get("/api/audit-log", headers=dunia["staf"]).status_code == 403

    def test_perubahan_barang_tercatat_dengan_nilai_lama(self, klien, dunia):
        iid = dunia["barang"]["OPN-C"]
        r = klien.patch(f"/api/items/{iid}", headers=dunia["owner"], json={"name": "Nama Baru"})
        assert r.status_code == 200, r.text
        r = klien.get(f"/api/audit-log?table=items&row_id={iid}&action=UPDATE",
                      headers=dunia["owner"])
        assert r.status_code == 200
        j = r.json()["items"][0]
        assert j["old_data"] == {"name": "Barang OPN-C"}
        assert j["new_data"] == {"name": "Nama Baru"}
        assert j["user_name"] == "Rina Owner"
        assert j["label"] == "OPN-C"

    def test_posting_opname_tercatat(self, klien, dunia, opname):
        r = klien.get(f"/api/audit-log?table=stock_adjustments&row_id={opname['id']}",
                      headers=dunia["owner"]).json()["items"]
        posting = [x for x in r if x["action"] == "UPDATE"
                   and (x["new_data"] or {}).get("status") == "completed"]
        assert posting and posting[0]["user_name"] == "Rina Owner"

    def test_kata_sandi_tidak_pernah_masuk_jejak(self, klien, dunia):
        r = klien.get("/api/audit-log?table=users", headers=dunia["owner"]).json()["items"]
        assert r
        for x in r:
            assert "password_hash" not in (x["new_data"] or {})
            assert "password_hash" not in (x["old_data"] or {})

    def test_role_aplikasi_tidak_dapat_menghapus_jejak(self, dunia):
        import os

        import psycopg
        with psycopg.connect(os.environ["DATABASE_URL"]) as k, k.cursor() as cur:
            cur.execute("SELECT set_config('app.company_id', %s, false)", (str(dunia["cid"]),))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("DELETE FROM audit_log")

    def test_jejak_perusahaan_lain_tidak_terbaca(self, klien, dunia):
        lain = klien.post("/api/auth/signup", json={
            "company_name": "PT Lain", "full_name": "Orang Lain",
            "email": "lain@ujiopname.id", "password": SANDI}).json()
        h = {"Authorization": "Bearer " + lain["access_token"]}
        r = klien.get("/api/audit-log?table=items", headers=h)
        assert r.status_code == 200 and r.json()["total"] == 0
