# -*- coding: utf-8 -*-
"""
Satu barang, tiga layar, satu kesimpulan.

    .venv/bin/python -m pytest backend/tests/test_dasbor.py -q

APA YANG DIJAGA DI SINI, dan kenapa berkas ini ada. Uji lain memeriksa rumus
(test_decision, test_rop) dan memeriksa bahwa halaman Prakiraan dan Pemesanan
Ulang menyebut angka yang sama untuk satu barang (test_kasus_ekstrem).
Yang tidak pernah diperiksa siapa pun adalah lapisan ketiga: DASBOR. Ia
meringkas seluruh katalog, dan ringkasan adalah tempat paling mudah bagi
sebuah angka untuk menyimpang tanpa terlihat -- tidak ada baris yang bisa
dibandingkan mata, hanya satu bilangan pada satu kartu.

Tiga cacat berikut benar-benar ada sebelum berkas ini ditulis, dan tidak satu
pun tertangkap uji mana pun:

  1. Kartu "Prakiraan pemakaian 14 hari" menjumlahkan angka yang SUDAH
     dibulatkan per baris. Pada katalog MRO yang berlaju 0,09/hari, setiap
     baris membulat menjadi nol dan kartunya berbunyi "0" -- berdampingan
     dengan kartu "Disarankan dipesan: 2" tepat di sebelahnya.

  2. Dasbor meminta 400 baris kepada mesin pemesanan ulang, sementara
     common.clamp_page() menjepit ukuran halaman pada 200. Seluruh angka yang
     dijumlahkan dari `items` karena itu diam-diam hanya mencakup dua ratus
     baris teratas begitu katalog melewatinya, sementara kartu di sebelahnya
     yang membaca `summary` tetap mencakup seluruhnya.

  3. Tabel "Perlu Perhatian" mencetak stok FISIK sementara halaman Pemesanan
     Ulang mencetak stok TERSEDIA untuk barang yang sama. Barang dengan stok
     tercadang berbunyi berbeda di dua layar -- dan yang di dasbor bahkan
     tidak menjelaskan statusnya sendiri: "stok 12, titik pesan 10, perlu
     reorder".

BASIS DATA SUNGGUHAN, LEWAT HTTP. Ketiganya lahir dari sambungan antar lapis,
bukan dari rumus, jadi yang diuji harus jalur yang sebenarnya: SQL dasbor,
mesin pemesanan ulang, dan penomoran halaman di antaranya.

SEMBILAN KASUS YANG DIMINTA disusun sebagai barang sungguhan di katalog uji,
masing-masing dengan riwayat pergerakan hariannya sendiri. Nama kasusnya
tertulis pada SKU supaya kegagalan menyebut kasusnya, bukan nomor baris.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import INDUK, NAMA_DB_UJI, bangun_basis_uji  # noqa: E402

SANDI = "kataSandiDasbor1"

# Riwayat: 90 hari, pengeluaran 1 unit/hari. Lajunya karena itu 1,0/hari
# tepat, sehingga seluruh angka harapan di bawah dapat dieja sebagai bilangan
# bulat alih-alih diperiksa dengan toleransi.
HARI_RIWAYAT = 90
LAJU = 1.0

# Masa tunggu dan cadangan bawaan untuk kasus-kasus yang tidak mengubahnya.
#   titik pesan efektif = max(titik pesan master, laju x lead + cadangan)
#                       = max(10, 1,0 x 10 + 5) = 15
LEAD = 10
CADANGAN = 5
ROP_MASTER = 10
ROP_EFEKTIF = 15

# Horizon keputusan yang dipatok mesin; sasaran pengisian memakainya.
#   sasaran = max(titik pesan efektif, laju x 14 + cadangan) = max(15, 19) = 19
HORIZON = 14
SASARAN = 19


# ==========================================================================
# Kasus uji
# ==========================================================================
#
# `stok` adalah stok FISIK, `tercadang` yang sudah dikomitmenkan keluar.
# Keputusan berpatokan selisihnya -- stok tersedia -- dan salah satu kasus di
# bawah memang ada untuk membuktikannya.
#
# `gerak` False berarti barang ini tidak pernah dikeluarkan sama sekali:
# itulah bentuk "prakiraan nol" yang benar-benar dapat terjadi di sistem ini.
# Riwayat tanpa pengeluaran tidak menghasilkan laju nol melainkan jawaban
# "histori belum cukup", dan jumlah pesanannya karena itu "belum dapat
# dihitung", BUKAN nol.

KASUS = {
    # nama                      stok  tercadang  ss        rop        gerak  status         qty
    "aman":                     dict(stok=100, ss=CADANGAN, status="AMAN", qty=0),
    "tepat_di_titik_pesan":     dict(stok=15,  ss=CADANGAN, status="PERLU_REORDER", qty=4),
    "di_bawah_titik_pesan":     dict(stok=12,  ss=CADANGAN, status="PERLU_REORDER", qty=7),
    "habis_sebelum_lead_time":  dict(stok=8,   ss=CADANGAN, status="RISIKO_STOCKOUT", qty=11),
    "cukup_sampai_lead_time":   dict(stok=11,  ss=CADANGAN, status="PERLU_REORDER", qty=8),
    "prakiraan_nol":            dict(stok=50,  ss=CADANGAN, gerak=False, status="AMAN", qty=None),
    # Cadangan 200 mengangkat titik pesan efektif ke 210, jauh di atas stok
    # yang menurut ukuran mana pun tebal. Sasarannya max(210, 14 + 200) = 214.
    "cadangan_tinggi":          dict(stok=100, ss=200, status="PERLU_REORDER", qty=114,
                                     rop_efektif=210, sasaran=214),
    "stok_nol":                 dict(stok=0,   ss=CADANGAN, status="RISIKO_STOCKOUT", qty=19),
    # Fisik 40 tetapi 25 sudah dikomitmenkan keluar: yang benar-benar dapat
    # dipakai tinggal 15, dan keputusannya harus lahir dari angka itu.
    # Cadangannya 20 -- di atas stok tersedia -- sehingga prioritasnya TINGGI
    # dan barisnya pasti masuk enam baris teratas tabel "Perlu Perhatian" di
    # dasbor, tempat uji regresi stok tercadang di bawah membacanya.
    #   titik pesan efektif = max(10, 10 + 20) = 30
    #   sasaran             = max(30, 14 + 20) = 34  ->  34 - 15 = 19
    "stok_tercadang":           dict(stok=40, tercadang=25, ss=20,
                                     status="PERLU_REORDER", qty=19,
                                     rop_efektif=30, sasaran=34),
}

# Barang yang sama, dua gudang, stok berbeda. Ia menjawab pertanyaan yang
# tidak dapat dijawab satu barang mana pun di atas: apakah keputusan benar
# benar dihitung per pasangan barang/gudang, atau diam-diam per barang.
SKU_MULTI = "UJI-MULTI"
MULTI = {
    "WH-01": dict(stok=100, status="AMAN", qty=0),
    "WH-02": dict(stok=6, status="RISIKO_STOCKOUT", qty=13),
}


def _sku(nama: str) -> str:
    return f"UJI-{nama.upper()[:20]}"


# ==========================================================================
# Dunia uji
# ==========================================================================

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
def dunia(klien):
    """
    Satu perusahaan, dua gudang, sebelas pasangan barang/gudang.

    Diisi lewat basis data langsung, bukan lewat API: yang sedang diuji bukan
    cara data masuk melainkan kesimpulan yang ditarik ketiga layar darinya,
    dan menyusun riwayat sembilan puluh hari lewat endpoint pengeluaran akan
    membuat berkas ini lebih panjang daripada yang diujinya.
    """
    import psycopg

    sesi = klien.post("/api/auth/signup", json={
        "company_name": "PT Uji Dasbor", "full_name": "Citra Handayani",
        "email": "citra@ujidasbor.id", "password": SANDI}).json()
    cid = sesi["company"]["id"]
    hari_ini = date.today()

    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}", autocommit=True) as k, k.cursor() as cur:
        cur.execute("INSERT INTO categories (company_id, name) VALUES (%s,'MRO') RETURNING id",
                    (cid,))
        kat = cur.fetchone()[0]
        cur.execute("INSERT INTO units (company_id, name, code) VALUES (%s,'Pieces','PCS')"
                    " RETURNING id", (cid,))
        sat = cur.fetchone()[0]

        gudang = {}
        for kode, nama in (("WH-01", "Gudang Satu"), ("WH-02", "Gudang Dua")):
            cur.execute("INSERT INTO warehouses (company_id, code, name) VALUES (%s,%s,%s)"
                        " RETURNING id", (cid, kode, nama))
            gudang[kode] = cur.fetchone()[0]

        def buat_barang(sku, ss, rop=ROP_MASTER, lead=LEAD):
            cur.execute(
                """INSERT INTO items (company_id, sku, name, category_id, unit_id,
                                      unit_price, minimum_stock, reorder_point,
                                      lead_time_days, safety_stock)
                   VALUES (%s,%s,%s,%s,%s,1000,5,%s,%s,%s) RETURNING id""",
                (cid, sku, f"Barang {sku}", kat, sat, rop, lead, ss))
            return cur.fetchone()[0]

        def taruh(item_id, wh_id, stok, tercadang=0, gerak=True):
            cur.execute(
                """INSERT INTO inventory (company_id, item_id, warehouse_id, quantity,
                                          reserved_quantity, available_quantity)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (cid, item_id, wh_id, stok, tercadang, stok - tercadang))
            # Satu penerimaan pembuka supaya jendela histori punya titik awal
            # yang jelas, lalu pengeluaran harian sebanyak HARI_RIWAYAT.
            cur.execute(
                """INSERT INTO stock_movements (company_id, item_id, warehouse_id,
                                                movement_type, movement_date, quantity)
                   VALUES (%s,%s,%s,'stock_in',%s,%s)""",
                (cid, item_id, wh_id,
                 hari_ini - timedelta(days=HARI_RIWAYAT), stok + HARI_RIWAYAT * LAJU))
            if not gerak:
                return
            for i in range(HARI_RIWAYAT):
                cur.execute(
                    """INSERT INTO stock_movements (company_id, item_id, warehouse_id,
                                                    movement_type, movement_date, quantity)
                       VALUES (%s,%s,%s,'stock_out',%s,%s)""",
                    (cid, item_id, wh_id,
                     hari_ini - timedelta(days=HARI_RIWAYAT - 1 - i), -LAJU))

        for nama, k_ in KASUS.items():
            iid = buat_barang(_sku(nama), k_["ss"])
            taruh(iid, gudang["WH-01"], k_["stok"], k_.get("tercadang", 0),
                  k_.get("gerak", True))

        iid = buat_barang(SKU_MULTI, CADANGAN)
        for kode, m in MULTI.items():
            taruh(iid, gudang[kode], m["stok"])

    return {
        "cid": cid,
        "h": {"Authorization": "Bearer " + sesi["access_token"]},
        "gudang": gudang,
    }


@pytest.fixture(scope="module")
def dasbor(klien, dunia):
    r = klien.get("/api/dashboard", headers=dunia["h"])
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def reorder(klien, dunia):
    r = klien.get("/api/reorder?page_size=200", headers=dunia["h"])
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def baris(reorder):
    """Peta (sku, kode gudang) -> baris daftar pemesanan ulang."""
    return {(b["sku"], b["warehouse_code"]): b for b in reorder["items"]}


def prakiraan(klien, dunia, sku, kode="WH-01", **q):
    """Jawaban /api/forecast untuk satu barang di satu gudang."""
    daftar = klien.get("/api/items?page_size=200", headers=dunia["h"]).json()["items"]
    iid = next(x["id"] for x in daftar if x["sku"] == sku)
    p = {"item_id": iid, "warehouse_id": dunia["gudang"][kode],
         "include_recommendation": "false", **q}
    r = klien.get("/api/forecast", params=p, headers=dunia["h"])
    assert r.status_code == 200, r.text
    return r.json()


# ==========================================================================
# 1. Sembilan kasus: keputusan yang benar
# ==========================================================================

class TestKasusYangDiminta:
    """
    Angka harapannya dieja apa adanya, bukan dihitung ulang di dalam uji.
    Uji yang menghitung sendiri rumus yang diujinya akan tetap lulus ketika
    rumus itu salah.
    """

    @pytest.mark.parametrize("nama", list(KASUS))
    def test_status_dan_jumlah(self, baris, nama):
        b = baris[(_sku(nama), "WH-01")]
        k = KASUS[nama]
        assert b["action_status"] == k["status"], nama
        assert b["recommended_order_qty"] == k["qty"], nama

    @pytest.mark.parametrize("nama", list(KASUS))
    def test_titik_pesan_efektif(self, baris, nama):
        b = baris[(_sku(nama), "WH-01")]
        k = KASUS[nama]
        if not k.get("gerak", True):
            # Tanpa laju, kebutuhan masa tunggu tidak diketahui dan ambangnya
            # jatuh ke titik pesan master. Itu jawaban yang benar, bukan
            # kelalaian: menghitung ambang dari angka yang tidak ada hanya
            # menghasilkan peringatan palsu.
            assert b["effective_reorder_point_int"] == ROP_MASTER, nama
            return
        assert b["effective_reorder_point_int"] == k.get("rop_efektif", ROP_EFEKTIF), nama
        assert b["order_up_to_level_int"] == k.get("sasaran", SASARAN), nama

    @pytest.mark.parametrize("nama", list(KASUS))
    def test_aman_berarti_nol_dan_bertindak_berarti_lebih_dari_nol(self, baris, nama):
        b = baris[(_sku(nama), "WH-01")]
        qty = b["recommended_order_qty"]
        if b["action_status"] == "AMAN":
            assert (qty or 0) == 0, nama
        else:
            assert qty is None or qty > 0, nama

    def test_stok_tercadang_yang_memutuskan_bukan_stok_fisik(self, baris):
        """
        Fisik 40, tercadang 25, tersedia 15 -- di bawah titik pesan efektif 30.
        Bila keputusan lahir dari stok fisik, barang ini berbunyi AMAN.
        """
        b = baris[(_sku("stok_tercadang"), "WH-01")]
        assert b["current_stock_int"] == 40
        assert b["available_stock_int"] == 15
        assert b["action_status"] == "PERLU_REORDER"

    def test_prakiraan_nol_menjawab_belum_tahu_bukan_tidak_perlu(self, baris):
        """
        Nol dan None adalah dua jawaban yang berbeda, dan menyamakan keduanya
        akan mencetak "tidak perlu dipesan" untuk barang yang belum pernah
        dinilai sama sekali.
        """
        b = baris[(_sku("prakiraan_nol"), "WH-01")]
        assert b["has_forecast"] is False
        assert b["recommended_order_qty"] is None

    def test_prioritas_mengikuti_kegentingan(self, baris):
        assert baris[(_sku("stok_nol"), "WH-01")]["priority"] == "TINGGI"
        assert baris[(_sku("aman"), "WH-01")]["priority"] == "RENDAH"


# ==========================================================================
# 2. Multi-gudang
# ==========================================================================

class TestMultiGudang:

    @pytest.mark.parametrize("kode", list(MULTI))
    def test_keputusan_dihitung_per_gudang(self, baris, kode):
        b = baris[(SKU_MULTI, kode)]
        assert b["action_status"] == MULTI[kode]["status"], kode
        assert b["recommended_order_qty"] == MULTI[kode]["qty"], kode

    def test_satu_barang_dua_kesimpulan(self, baris):
        """
        Barang yang sama boleh -- dan harus -- berstatus berbeda di dua gudang.
        Bila keputusan diam-diam dihitung per barang, kedua baris akan kembar.
        """
        a = baris[(SKU_MULTI, "WH-01")]
        b = baris[(SKU_MULTI, "WH-02")]
        assert a["action_status"] != b["action_status"]

    def test_saringan_gudang_tidak_mengubah_barisnya(self, klien, dunia, baris):
        r = klien.get(f"/api/reorder?warehouse_id={dunia['gudang']['WH-02']}&page_size=200",
                      headers=dunia["h"]).json()
        satu = next(b for b in r["items"] if b["sku"] == SKU_MULTI)
        for f in ("action_status", "recommended_order_qty",
                  "effective_reorder_point_int", "available_stock_int"):
            assert satu[f] == baris[(SKU_MULTI, "WH-02")][f], f


# ==========================================================================
# 3. Prakiraan -> Pemesanan Ulang: satu barang, satu kesimpulan
# ==========================================================================

class TestPrakiraanSelarasDenganReorder:

    SILANG = ("action_status", "priority", "recommended_order_qty",
              "effective_reorder_point_int", "available_stock_int",
              "current_stock_int", "reorder_point_int", "safety_stock_int",
              "lead_time_demand_int", "order_up_to_level_int",
              "days_of_cover_int", "decision_horizon_days")

    @pytest.mark.parametrize("nama", list(KASUS))
    def test_kedua_endpoint_menyebut_angka_yang_sama(self, klien, dunia, baris, nama):
        f = prakiraan(klien, dunia, _sku(nama))
        b = baris[(_sku(nama), "WH-01")]
        for k in self.SILANG:
            assert f[k] == b[k], f"{nama}: {k}"

    @pytest.mark.parametrize("hari", [7, 30, 90])
    def test_periode_layar_tidak_menggeser_keputusan(self, klien, dunia, baris, hari):
        """
        Halaman Prakiraan boleh mengganti periodenya sesuka pengguna; tidak
        satu pun angka keputusan boleh ikut bergerak. Bila ia bergerak, dua
        halaman akan menyebut jumlah pesanan yang berbeda untuk barang yang
        sama tanpa ada satu pun kendali yang terlihat di layar Pemesanan Ulang.
        """
        f = prakiraan(klien, dunia, _sku("di_bawah_titik_pesan"), days=hari)
        b = baris[(_sku("di_bawah_titik_pesan"), "WH-01")]
        for k in self.SILANG:
            assert f[k] == b[k], f"{hari} hari: {k}"


# ==========================================================================
# 4. Dasbor -> Pemesanan Ulang: ringkasan yang tidak boleh menyimpang
# ==========================================================================

class TestDasborSelarasDenganReorder:

    def test_kartu_perhatian_sama_dengan_ringkasan_mesin(self, dasbor, reorder):
        a, s = dasbor["attention"], reorder["summary"]
        assert a["need_reorder"] == s["perlu_reorder"]
        assert a["stockout_risk"] == s["risiko_stockout"]
        assert a["high_priority"] == s["prioritas_tinggi"]
        assert a["healthy"] == s["aman"]

    def test_status_persediaan_menjumlah_seluruh_baris(self, dasbor, reorder):
        """Grafik "Status Persediaan" membagi katalog menjadi tiga; ketiganya
        harus menutupi seluruhnya, tanpa sisa dan tanpa tumpang tindih."""
        a = dasbor["attention"]
        assert a["healthy"] + a["need_reorder"] + a["stockout_risk"] == \
            reorder["summary"]["total_baris"] == reorder["total"]

    def test_kartu_kebutuhan_sama_dengan_ringkasan_mesin(self, dasbor, reorder):
        f, s = dasbor["forecast"], reorder["summary"]
        assert f["horizon_days"] == s["horizon_hari"] == HORIZON
        assert f["forecast_usage"] == s["total_kebutuhan_horizon"]
        assert f["recommended_order_qty"] == s["total_qty"]
        assert f["qty_unknown"] == s["qty_belum_terhitung"]
        assert f["projected_stockout"] == s["habis_dalam_horizon"]
        assert f["without_forecast"] == s["tanpa_prakiraan"]

    def test_prakiraan_pemakaian_bukan_jumlah_angka_yang_sudah_dibulatkan(
            self, dasbor, reorder):
        """
        Cacat yang benar-benar terjadi: dua puluh baris berlaju 0,09/hari
        masing-masing membulat menjadi nol, dan kartunya berbunyi "0" di
        sebelah kartu "Disarankan dipesan: 2".

        Yang diperiksa di sini identitasnya, bukan angkanya: total harus
        bersandar pada nilai PENUH tiap baris, dan itu tidak akan pernah lebih
        kecil daripada jumlah pesanan yang sudah dibulatkan ke atas per baris
        pada katalog yang bergerak.
        """
        penuh = sum(b["forecast_usage"] or 0.0 for b in reorder["items"])
        assert dasbor["forecast"]["forecast_usage"] == round(penuh + 1e-9)
        assert dasbor["forecast"]["forecast_usage"] > 0

    def test_baris_perhatian_sama_dengan_baris_daftar(self, dasbor, baris):
        """
        Setiap baris tabel "Perlu Perhatian" harus menyebut angka yang sama
        dengan baris yang sama pada halaman Pemesanan Ulang -- termasuk
        kolom stoknya, yang keduanya kini stok TERSEDIA.
        """
        assert dasbor["attention"]["rows"], "tidak ada baris perhatian untuk diperiksa"
        for r in dasbor["attention"]["rows"]:
            b = baris[(r["sku"], r["warehouse_code"])]
            assert r["current_stock"] == b["available_stock_int"], r["sku"]
            assert r["reorder_point"] == b["effective_reorder_point_int"], r["sku"]
            assert r["days_of_cover"] == b["days_of_cover_int"], r["sku"]
            assert r["recommended_order_qty"] == b["recommended_order_qty"], r["sku"]
            assert r["status"] == b["action_status"], r["sku"]
            assert r["priority"] == b["priority"], r["sku"]

    def test_ringkasan_tidak_bergantung_ukuran_halaman(self, klien, dunia):
        """
        Ringkasan lahir SEBELUM pemenggalan halaman, jadi ia harus sama persis
        berapa pun baris yang diminta. Inilah yang membuat cacat nomor dua di
        kepala berkas ini mustahil terulang: selama dasbor membaca `summary`,
        ukuran halaman yang dimintanya tidak dapat menggeser satu pun angka.
        """
        a = klien.get("/api/reorder?page_size=1", headers=dunia["h"]).json()["summary"]
        b = klien.get("/api/reorder?page_size=200", headers=dunia["h"]).json()["summary"]
        assert a == b

    def test_dasbor_utuh_walau_halaman_dijepit(self, klien, dunia, monkeypatch, reorder):
        """
        Reproduksi langsung cacat nomor dua. common.clamp_page() menjepit
        ukuran halaman pada PAGE_SIZE_MAX; di sini jepitannya diturunkan
        menjadi dua baris, yaitu keadaan yang dialami katalog nyata begitu ia
        melewati dua ratus pasangan barang/gudang. Seluruh angka kartu harus
        tetap mencakup katalog penuh.
        """
        from app.routers import reorder as ro

        asli = ro.clamp_page
        monkeypatch.setattr(ro, "clamp_page",
                            lambda page, page_size: asli(page, min(page_size, 2)))

        d = klien.get("/api/dashboard", headers=dunia["h"]).json()
        s = reorder["summary"]
        assert d["forecast"]["forecast_usage"] == s["total_kebutuhan_horizon"]
        assert d["forecast"]["recommended_order_qty"] == s["total_qty"]
        assert d["forecast"]["projected_stockout"] == s["habis_dalam_horizon"]
        assert d["forecast"]["without_forecast"] == s["tanpa_prakiraan"]
        assert d["attention"]["need_reorder"] == s["perlu_reorder"]

    def test_baris_perhatian_hanya_yang_menuntut_tindakan(self, dasbor):
        for r in dasbor["attention"]["rows"]:
            assert r["status"] != "AMAN", r["sku"]

    def test_baris_perhatian_terurut_paling_genting_dulu(self, dasbor):
        urut = {"RISIKO_STOCKOUT": 0, "PERLU_REORDER": 1, "AMAN": 2}
        nilai = [urut[r["status"]] for r in dasbor["attention"]["rows"]]
        assert nilai == sorted(nilai)

    def test_stok_tercadang_tidak_berselisih_antar_layar(self, dasbor, baris):
        """
        Regresi langsung atas cacat yang diperbaiki: barang dengan stok
        tercadang pernah berbunyi 40 di dasbor dan 15 di halaman Pemesanan
        Ulang, dan yang di dasbor bahkan tidak menjelaskan statusnya sendiri.
        """
        r = next(x for x in dasbor["attention"]["rows"]
                 if x["sku"] == _sku("stok_tercadang"))
        assert r["current_stock"] == 15
        assert r["current_stock"] <= r["reorder_point"]


# ==========================================================================
# 5. Kondisi persediaan: satu populasi untuk seluruh halaman
# ==========================================================================

class TestKondisiPersediaan:

    def test_total_stok_sama_dengan_jumlah_per_gudang(self, dasbor):
        assert dasbor["condition"]["stock"] == \
            sum(w["total_stock"] for w in dasbor["stock_by_warehouse"])

    def test_gudang_aktif_seluruhnya_muncul(self, dasbor):
        assert [w["code"] for w in dasbor["stock_by_warehouse"]] == ["WH-01", "WH-02"]
        assert dasbor["condition"]["warehouses"] == 2

    def test_barang_nonaktif_keluar_dari_ketiga_angka_sekaligus(self, klien, dunia):
        """
        Sebelum perbaikan, "Total Stok" menjumlahkan SELURUH baris persediaan
        sementara "Total SKU", "Stok per Gudang", dan mesin pemesanan ulang
        menyaring barang nonaktif. Menonaktifkan satu barang karena itu
        membuat Total Stok berhenti sama dengan jumlah Stok per Gudang, tanpa
        satu pun galat yang menunjukkannya.
        """
        import psycopg

        sebelum = klien.get("/api/dashboard", headers=dunia["h"]).json()
        sku = _sku("aman")
        with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}", autocommit=True) as k, k.cursor() as cur:
            cur.execute("UPDATE items SET is_active = FALSE WHERE sku = %s AND company_id = %s",
                        (sku, dunia["cid"]))
        try:
            sesudah = klien.get("/api/dashboard", headers=dunia["h"]).json()
            r = klien.get("/api/reorder?page_size=200", headers=dunia["h"]).json()

            assert sesudah["condition"]["items"] == sebelum["condition"]["items"] - 1
            assert sesudah["condition"]["stock"] == sebelum["condition"]["stock"] - 100
            assert sesudah["condition"]["stock"] == \
                sum(w["total_stock"] for w in sesudah["stock_by_warehouse"])
            assert sku not in {b["sku"] for b in r["items"]}
            assert sesudah["attention"]["healthy"] + sesudah["attention"]["need_reorder"] \
                + sesudah["attention"]["stockout_risk"] == r["summary"]["total_baris"]
        finally:
            with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}", autocommit=True) as k, k.cursor() as cur:
                cur.execute("UPDATE items SET is_active = TRUE WHERE sku = %s AND company_id = %s",
                            (sku, dunia["cid"]))


# ==========================================================================
# 6. Bilangan bulat sampai ke layar
# ==========================================================================

class TestBilanganBulat:

    def _bulat(self, nilai) -> bool:
        return nilai is None or isinstance(nilai, bool) or (
            isinstance(nilai, (int, float)) and float(nilai) == int(nilai))

    def test_angka_dasbor_bulat(self, dasbor):
        for k in ("items", "warehouses", "stock"):
            assert self._bulat(dasbor["condition"][k]), k
        for w in dasbor["stock_by_warehouse"]:
            assert self._bulat(w["total_stock"]), w["code"]
        for k, v in dasbor["forecast"].items():
            assert self._bulat(v), k
        for k, v in dasbor["attention"].items():
            if k != "rows":
                assert self._bulat(v), k
        for r in dasbor["attention"]["rows"]:
            for k in ("current_stock", "reorder_point", "days_of_cover",
                      "recommended_order_qty"):
                assert self._bulat(r[k]), f"{r['sku']}: {k}"

    def test_angka_kolom_reorder_bulat(self, reorder):
        kolom = ("current_stock_int", "available_stock_int", "reorder_point_int",
                 "effective_reorder_point_int", "safety_stock_int",
                 "lead_time_days_int", "lead_time_demand_int", "forecast_usage_int",
                 "days_of_cover_int", "days_to_effective_rop_int",
                 "order_up_to_level_int", "recommended_order_qty")
        for b in reorder["items"]:
            for k in kolom:
                assert self._bulat(b[k]), f"{b['sku']}: {k} = {b[k]!r}"


# ==========================================================================
# 7. Kalimat alasan
# ==========================================================================

class TestAlasanRekomendasi:

    @pytest.mark.parametrize("nama", list(KASUS))
    def test_setiap_baris_membawa_alasannya(self, baris, nama):
        b = baris[(_sku(nama), "WH-01")]
        assert b["reason"], nama

    @pytest.mark.parametrize("nama", list(KASUS))
    def test_judul_pengadaan_tidak_bertentangan_dengan_jumlah(self, klien, dunia, nama):
        """
        Kontradiksi yang pernah dilaporkan pengguna: "Segera pesan"
        berdampingan dengan "Belum ada jumlah yang perlu diadakan".
        """
        f = prakiraan(klien, dunia, _sku(nama))
        judul, qty = f["order_qty_title"], f["recommended_order_qty"]
        if qty is None:
            assert "belum dapat dihitung" in judul, nama
        elif qty == 0:
            assert judul == "Belum perlu pengadaan", nama
        else:
            assert judul == f"Pesan {qty} PCS", nama
