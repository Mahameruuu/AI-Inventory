# -*- coding: utf-8 -*-
"""
Rekomendasi rute (moda angkut) berbasis riwayat transfer -- app/rute_ml.py,
app/logistik.py, dan riwayat bangkitan tools/jaringan_gudang.py.
"""
import sys
from pathlib import Path

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from conftest import INDUK, NAMA_DB_UJI  # noqa: E402
from test_demo import dunia, klien  # noqa: E402,F401

from app import logistik  # noqa: E402


# --- model dunia (tanpa basis data) ---------------------------------------

SBY = {"latitude": -7.2575, "longitude": 112.7521}
JKT = {"latitude": -6.2088, "longitude": 106.8456}
SMG = {"latitude": -6.95, "longitude": 110.47}
MKS = {"latitude": -5.14, "longitude": 119.48}


def test_moda_darat_hanya_di_pulau_yang_sama():
    assert "darat" in logistik.moda_tersedia(SBY, JKT, 780.0)
    assert "darat" in logistik.moda_tersedia(SMG, JKT)
    # Makassar berada di luar Jawa: tidak ada jalan.
    assert set(logistik.moda_tersedia(SBY, MKS)) == {"laut", "udara"}


def test_kargo_udara_tidak_ditawarkan_untuk_jarak_pendek():
    dekat = {"latitude": -7.30, "longitude": 112.80}     # beberapa km dari Surabaya
    assert "udara" not in logistik.moda_tersedia(SBY, dekat)


def test_tarif_standar_masuk_akal():
    laut = logistik.tarif_standar("laut", 980, 100)
    udara = logistik.tarif_standar("udara", 780, 100)
    assert udara["hari"] < laut["hari"]            # udara lebih cepat
    assert udara["biaya"] > laut["biaya"]          # tetapi lebih mahal
    assert udara["terima"] > laut["terima"]        # dan lebih jarang merusak
    # makin banyak barang, makin mahal
    assert logistik.tarif_standar("udara", 780, 300)["biaya"] > udara["biaya"]


# --- lewat API pada penyewa demo ----------------------------------------------

@pytest.fixture()
def demo_terisi(klien, dunia):
    r = klien.post("/api/demo/reset", headers=dunia["hDemo"])
    assert r.status_code == 200, r.text[:300]
    cid = dunia["demo"]["company"]["id"]
    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute("SELECT code, id FROM warehouses WHERE company_id = %s", (cid,))
        gudang = dict(cur.fetchall())
    return {"h": dunia["hDemo"], "g": gudang, "cid": cid}


def _rute(klien, d, dari, ke, **p):
    return klien.get("/api/transfer/rute-ml", headers=d["h"], params={
        "from_warehouse_id": d["g"][dari], "to_warehouse_id": d["g"][ke],
        "quantity": 120, **p})


def test_makassar_hanya_bisa_lewat_laut_atau_udara(klien, demo_terisi):
    r = _rute(klien, demo_terisi, "WH-SBY", "WH-MKS")
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert {o["mode"] for o in j["options"]} == {"laut", "udara"}
    assert j["model"]["kind"] == "ml"
    assert j["model"]["n_train"] >= 200
    # Galat rata-rata model sanggup dipertanggungjawabkan.
    m = j["model"]["metrics"]
    assert m["hari_mae"] < 1.5 and m["biaya_mape"] < 0.25 and m["terima_mae"] < 0.10


def test_prioritas_mengubah_pilihan(klien, demo_terisi):
    murah = _rute(klien, demo_terisi, "WH-SBY", "WH-MKS", priority="termurah").json()
    cepat = _rute(klien, demo_terisi, "WH-SBY", "WH-MKS", priority="tercepat").json()
    assert murah["recommended_mode"] == "laut"
    assert cepat["recommended_mode"] == "udara"
    # Yang direkomendasikan selalu berperingkat 1, dan skor menurun.
    skor = [o["score"] for o in cepat["options"]]
    assert cepat["options"][0]["rank"] == 1 and skor == sorted(skor, reverse=True)


def test_batas_waktu_menandai_moda_yang_terlambat(klien, demo_terisi):
    j = _rute(klien, demo_terisi, "WH-SBY", "WH-MKS", deadline_days=4).json()
    laut = next(o for o in j["options"] if o["mode"] == "laut")
    udara = next(o for o in j["options"] if o["mode"] == "udara")
    assert laut["late"] is True and udara["late"] is False
    assert j["recommended_mode"] == "udara"


def test_perkiraan_menyebut_barang_yang_diterima_dan_biaya_total(klien, demo_terisi):
    j = _rute(klien, demo_terisi, "WH-JKT", "WH-SBY").json()
    for o in j["options"]:
        assert 0 < o["predicted_received"] <= 120
        assert o["predicted_cost"] > 0 and o["total_cost"] >= o["predicted_cost"]
        assert o["distance_km"] > 0


def test_masukan_tidak_sah_ditolak(klien, demo_terisi):
    d = demo_terisi
    assert _rute(klien, d, "WH-SBY", "WH-SBY").status_code == 422
    assert _rute(klien, d, "WH-SBY", "WH-MKS", priority="asal").status_code == 422


def test_dokumen_mencatat_moda_yang_dipilih(klien, demo_terisi):
    d = demo_terisi
    item = klien.get("/api/items", headers=d["h"],
                     params={"q": "SP-1001"}).json()["items"][0]["id"]
    r = klien.post("/api/transfers", headers=d["h"], json={
        "from_warehouse_id": d["g"]["WH-SBY"], "to_warehouse_id": d["g"]["WH-MKS"],
        "transport_mode": "laut", "planned_days": 8,
        "items": [{"item_id": item, "quantity": 5}]})
    assert r.status_code in (200, 201), r.text[:300]
    doc = klien.get(f"/api/transfers/{r.json()['transfer_id']}", headers=d["h"]).json()
    assert doc["transfer"]["transport_mode"] == "laut"
    assert float(doc["transfer"]["planned_days"]) == 8.0
    r = klien.post("/api/transfers", headers=d["h"], json={
        "from_warehouse_id": d["g"]["WH-SBY"], "to_warehouse_id": d["g"]["WH-MKS"],
        "transport_mode": "kereta", "items": [{"item_id": item, "quantity": 1}]})
    assert r.status_code == 422


# --- riwayat bangkitan -------------------------------------------------------

def test_riwayat_transfer_menjaga_buku_besar(demo_terisi):
    """Saldo tabel stok = jumlah pergerakan, dan tidak pernah minus di tengah jalan."""
    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cid = demo_terisi["cid"]
        cur.execute(
            """
            SELECT count(*) FROM inventory v
             WHERE v.company_id = %s AND v.quantity <> COALESCE((
                   SELECT SUM(m.quantity) FROM stock_movements m
                    WHERE m.item_id = v.item_id AND m.warehouse_id = v.warehouse_id), 0)
            """, (cid,))
        assert cur.fetchone()[0] == 0
        cur.execute(
            """
            SELECT count(*) FROM (
              SELECT SUM(quantity) OVER (PARTITION BY item_id, warehouse_id
                                         ORDER BY movement_date, id) AS saldo
                FROM stock_movements WHERE company_id = %s) t
             WHERE saldo < -0.0001
            """, (cid,))
        assert cur.fetchone()[0] == 0


def test_riwayat_transfer_lengkap_dan_beragam(demo_terisi):
    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute(
            """
            SELECT transport_mode, count(*),
                   bool_and(shipping_cost IS NOT NULL AND planned_days IS NOT NULL
                            AND received_at > shipped_at)
              FROM stock_transfers WHERE company_id = %s AND status = 'completed'
             GROUP BY 1 ORDER BY 1
            """, (demo_terisi["cid"],))
        baris = {m: (n, ok) for m, n, ok in cur.fetchall()}
        # Ketiga moda muncul, dan setiap dokumen selesai punya biaya dan janji.
        assert set(baris) == {"darat", "laut", "udara"}
        assert all(ok for _, ok in baris.values())
        assert all(n >= 20 for n, _ in baris.values())
        # Sebagian kiriman memang tidak utuh sampai.
        cur.execute(
            """
            SELECT count(*) FROM stock_transfer_items
             WHERE company_id = %s AND received_quantity < quantity
            """, (demo_terisi["cid"],))
        assert cur.fetchone()[0] > 0


def test_semarang_dan_makassar_punya_dokumen_aktif_di_ketiga_moda(klien, demo_terisi):
    """Kedua cabang baru tidak kosong pada peta: ada dokumen hidup yang menyentuhnya."""
    d = demo_terisi
    dok = []
    for status in ("draft", "approved", "in_transit"):
        r = klien.get("/api/transfers", headers=d["h"],
                      params={"status": status, "page_size": 100})
        assert r.status_code == 200, r.text[:300]
        dok += r.json()["items"]
    for kode in ("WH-SMG", "WH-MKS"):
        gid = d["g"][kode]
        assert any(gid in (x["from_warehouse_id"], x["to_warehouse_id"]) for x in dok), kode
    # Kendaraan di peta ditentukan status dan moda: ketiganya harus terwakili.
    assert {x["transport_mode"] for x in dok} == {"darat", "laut", "udara"}
    dikirim = [x for x in dok if x["status"] == "in_transit"]
    assert {x["transport_mode"] for x in dikirim} == {"darat", "laut", "udara"}


# --- konfirmasi penerimaan: jumlah diterima dan biaya --------------------------

def _buat_dan_kirim(klien, d, qty=10):
    """Satu dokumen SBY -> SMG (darat) sampai berstatus Dikirim."""
    item = klien.get("/api/items", headers=d["h"],
                     params={"q": "PL-2003"}).json()["items"][0]["id"]
    r = klien.post("/api/transfers", headers=d["h"], json={
        "from_warehouse_id": d["g"]["WH-SBY"], "to_warehouse_id": d["g"]["WH-SMG"],
        "transport_mode": "darat", "planned_days": 2,
        "items": [{"item_id": item, "quantity": qty}]})
    assert r.status_code in (200, 201), r.text[:300]
    tid = r.json()["transfer_id"]
    for s in ("approved", "in_transit"):
        assert klien.patch(f"/api/transfers/{tid}/status", headers=d["h"],
                           json={"status": s}).status_code == 200
    return tid, item


def _saldo(cid, item, gudang):
    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute("SELECT COALESCE(quantity, 0) FROM inventory WHERE company_id = %s "
                    "AND item_id = %s AND warehouse_id = %s", (cid, item, gudang))
        r = cur.fetchone()
        cur.execute("SELECT COALESCE(SUM(quantity), 0) FROM stock_movements WHERE company_id = %s "
                    "AND item_id = %s AND warehouse_id = %s", (cid, item, gudang))
        return float(r[0] if r else 0), float(cur.fetchone()[0])


def test_penerimaan_sebagian_menambah_tujuan_sebesar_yang_diterima(klien, demo_terisi):
    d = demo_terisi
    tid, item = _buat_dan_kirim(klien, d, qty=10)
    a0, _ = _saldo(d["cid"], item, d["g"]["WH-SBY"])
    t0, _ = _saldo(d["cid"], item, d["g"]["WH-SMG"])
    r = klien.patch(f"/api/transfers/{tid}/status", headers=d["h"], json={
        "status": "completed", "received": [{"item_id": item, "received_quantity": 8}],
        "shipping_cost": 1_250_000})
    assert r.status_code == 200, r.text[:300]
    assert r.json()["received_total"] == 8 and r.json()["shipped_total"] == 10
    # Tujuan bertambah 8 (bukan 10); saldo tabel = jumlah pergerakan.
    t1, tm = _saldo(d["cid"], item, d["g"]["WH-SMG"])
    assert t1 - t0 == 8 and t1 == tm
    a1, am = _saldo(d["cid"], item, d["g"]["WH-SBY"])
    assert a1 == am
    doc = klien.get(f"/api/transfers/{tid}", headers=d["h"]).json()
    assert doc["lines"][0]["received_quantity"] == 8
    assert float(doc["transfer"]["shipping_cost"]) == 1_250_000


def test_penerimaan_tanpa_isian_dianggap_utuh(klien, demo_terisi):
    d = demo_terisi
    tid, item = _buat_dan_kirim(klien, d, qty=6)
    t0, _ = _saldo(d["cid"], item, d["g"]["WH-SMG"])
    r = klien.patch(f"/api/transfers/{tid}/status", headers=d["h"], json={"status": "completed"})
    assert r.status_code == 200, r.text[:300]
    assert _saldo(d["cid"], item, d["g"]["WH-SMG"])[0] - t0 == 6
    doc = klien.get(f"/api/transfers/{tid}", headers=d["h"]).json()
    assert doc["lines"][0]["received_quantity"] == 6


def test_jumlah_diterima_tidak_boleh_melebihi_kiriman(klien, demo_terisi):
    d = demo_terisi
    tid, item = _buat_dan_kirim(klien, d, qty=5)
    r = klien.patch(f"/api/transfers/{tid}/status", headers=d["h"], json={
        "status": "completed", "received": [{"item_id": item, "received_quantity": 9}]})
    assert r.status_code == 422
    # Dokumen tetap Dikirim; tidak ada stok yang bergerak.
    doc = klien.get(f"/api/transfers/{tid}", headers=d["h"]).json()
    assert doc["transfer"]["status"] == "in_transit"


def test_biaya_baru_dapat_dicatat_setelah_dikirim(klien, demo_terisi):
    d = demo_terisi
    item = klien.get("/api/items", headers=d["h"], params={"q": "PL-2003"}).json()["items"][0]["id"]
    r = klien.post("/api/transfers", headers=d["h"], json={
        "from_warehouse_id": d["g"]["WH-SBY"], "to_warehouse_id": d["g"]["WH-SMG"],
        "items": [{"item_id": item, "quantity": 3}]})
    tid = r.json()["transfer_id"]
    # Diajukan: belum ada biaya.
    assert klien.patch(f"/api/transfers/{tid}/biaya", headers=d["h"],
                       json={"shipping_cost": 500000}).status_code == 422
    for s in ("approved", "in_transit"):
        klien.patch(f"/api/transfers/{tid}/status", headers=d["h"], json={"status": s})
    assert klien.patch(f"/api/transfers/{tid}/biaya", headers=d["h"],
                       json={"shipping_cost": 500000}).status_code == 200
    klien.patch(f"/api/transfers/{tid}/status", headers=d["h"], json={"status": "completed"})
    # Tagihan menyusul sesudah diterima dan boleh dikoreksi.
    assert klien.patch(f"/api/transfers/{tid}/biaya", headers=d["h"],
                       json={"shipping_cost": 640000}).status_code == 200
    assert float(klien.get(f"/api/transfers/{tid}", headers=d["h"]).json()["transfer"]["shipping_cost"]) == 640000
    assert klien.patch(f"/api/transfers/{tid}/biaya", headers=d["h"],
                       json={"shipping_cost": -1}).status_code == 422


def test_tiap_kiriman_rekomendasi_membawa_satu_rute_terbaik(klien, demo_terisi):
    """Peta menggambar SATU rute per usulan: modanya datang dari /api/transfer."""
    d = demo_terisi
    r = klien.get("/api/transfer", headers=d["h"], params={"q": "SP-1001"})
    assert r.status_code == 200, r.text[:300]
    kaki = [k for b in r.json()["items"] for k in b["legs"]]
    assert kaki
    for k in kaki:
        assert k["route_ml"]["mode"] in ("darat", "laut", "udara")
    # Ke Makassar (luar Jawa) tidak pernah darat.
    ke_mks = [k for b in r.json()["items"] if b["to_warehouse_code"] == "WH-MKS"
              for k in b["legs"]]
    assert ke_mks and all(k["route_ml"]["mode"] != "darat" for k in ke_mks)
    assert all(b["route_deadline_days"] for b in r.json()["items"])


def test_satu_pasangan_gudang_satu_moda_untuk_seluruh_barangnya(klien, demo_terisi):
    """Barang yang berangkat dari A ke B naik satu kiriman: modanya tidak boleh berbeda-beda."""
    d = demo_terisi
    items = klien.get("/api/transfer", headers=d["h"], params={"page_size": 100}).json()["items"]
    per_pasangan = {}
    for b in items:
        for k in b["legs"]:
            if k["transfer_qty"] > 0:
                per_pasangan.setdefault((k["from_warehouse_id"], b["to_warehouse_id"]), []).append(k)
    assert per_pasangan
    for pasangan, kaki in per_pasangan.items():
        assert len({k["route_ml"]["mode"] for k in kaki}) == 1, pasangan
        # Jumlah kiriman gabungan = jumlah seluruh barang pada pasangan itu.
        assert {k["route_ml"]["shipment_qty"] for k in kaki} == {sum(k["transfer_qty"] for k in kaki)}
        assert {k["route_ml"]["shipment_items"] for k in kaki} == {len(kaki)}
    # Biaya tiap barang = bagian dari biaya kiriman (jumlah bagian ~ biaya gabungan).
    for kaki in per_pasangan.values():
        total = sum(k["route_ml"]["predicted_cost"] for k in kaki)
        assert abs(total - kaki[0]["route_ml"]["shipment_cost"]) <= 1000 * len(kaki)
