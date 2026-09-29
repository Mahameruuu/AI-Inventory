# -*- coding: utf-8 -*-
"""
Transfer Antar Gudang, dari SQL sampai dokumen yang menggerakkan stok.

    .venv/bin/python -m pytest backend/tests/test_transfer_api.py -q

BASIS DATA SUNGGUHAN, LEWAT HTTP. test_transfer.py sudah mengunci rumus
pemilihan sumbernya di atas keadaan yang disusun tangan; yang TIDAK dapat
dijawab berkas itu adalah apakah keadaan tangan itu benar-benar sama dengan
yang lahir dari basis data -- apakah kekurangan yang dipinjam dari mesin
reorder memang angka yang sama, apakah surplus terbaca dari stok TERSEDIA
alih-alih stok fisik, dan apakah dokumen yang diajukan benar-benar menggerakkan
persediaan pada tahap yang tepat.

Enam kasus yang diminta spesifikasi dijalankan di sini sebagai barang
sungguhan di katalog uji, masing-masing dengan riwayat sembilan puluh harinya
sendiri. Nama kasusnya tertulis pada SKU supaya kegagalan menyebut kasusnya.

DUNIANYA TIGA GUDANG, dan ketiganya perlu:
    WH-TUJ  Surabaya, gudang yang kekurangan pada seluruh kasus
    WH-DEK  Sidoarjo, 25 km, tempuh 1 hari
    WH-JAU  Jakarta, 780 km, tempuh 3 hari
Tanpa gudang ketiga, "yang terdekat tidak cukup" dan "yang jauh cukup" tidak
dapat dibedakan sama sekali.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import INDUK, NAMA_DB_UJI, bangun_basis_uji  # noqa: E402

SANDI = "kataSandiTransfer1"

# Riwayat yang sama untuk seluruh barang: 90 hari, keluar 1 unit/hari.
# Lajunya karena itu tepat 1,0 dan seluruh angka harapan di bawah dapat dieja
# sebagai bilangan bulat alih-alih diperiksa dengan toleransi.
HARI_RIWAYAT = 90
LAJU = 1.0
LEAD = 10
CADANGAN = 5
ROP_MASTER = 10

#   titik pesan efektif = max(10, 1,0 x 10 + 5) = 15
#   sasaran pengisian   = max(15, 1,0 x 14 + 5) = 19
ROP_EFEKTIF = 15
SASARAN = 19

# Stok gudang tujuan pada seluruh kasus. Kekurangannya karena itu satu angka
# yang sama di mana-mana: 19 - 6 = 13, dan setiap harapan di bawah dapat
# dibaca sebagai pecahan dari angka itu.
STOK_TUJUAN = 6
BUTUH = SASARAN - STOK_TUJUAN  # 13

SURABAYA = (-7.2575, 112.7521)
SIDOARJO = (-7.4478, 112.7183)
JAKARTA = (-6.2088, 106.8456)


# ==========================================================================
# Kasus
# ==========================================================================
#
# `dek` dan `jau` adalah stok FISIK gudang sumber; None berarti barang ini
# memang tidak ada di gudang itu. Surplusnya = stok - 15, karena itulah batas
# di mana gudang sumber sendiri harus mulai memesan.

KASUS = {
    # Yang terdekat berlimpah: satu kiriman 25 km, dan yang jauh hanya
    # menjadi pilihan kedua yang tetap terbit di layar.
    "dekat_cukup": dict(
        dek=100, jau=100,
        keputusan="TRANSFER", transfer=BUTUH, beli=0,
        dari=["WH-DEK"], qty=[13]),

    # Yang terdekat hanya punya 2 dari 13. Kecukupan berbobot lebih besar
    # daripada jarak justru untuk keadaan ini: satu kiriman dari Jakarta lebih
    # murah daripada satu kiriman dari Sidoarjo yang tetap menyisakan sebelas
    # unit untuk dibeli.
    "dekat_kurang": dict(
        dek=17, jau=100,
        keputusan="TRANSFER", transfer=BUTUH, beli=0,
        dari=["WH-JAU"], qty=[13]),

    # Barangnya hanya ada di gudang yang jauh. Jarak menurunkan skor, tidak
    # pernah membatalkan kelayakan.
    "jauh_saja": dict(
        dek=None, jau=100,
        keputusan="TRANSFER", transfer=BUTUH, beli=0,
        dari=["WH-JAU"], qty=[13]),

    # Tidak satu pun cukup sendirian; keduanya digabung. Yang terbaik dikuras
    # lebih dulu, sisanya turun ke berikutnya.
    "gabungan": dict(
        dek=23, jau=20,   # surplus 8 dan 5
        keputusan="TRANSFER", transfer=BUTUH, beli=0,
        dari=["WH-DEK", "WH-JAU"], qty=[8, 5]),

    # Keduanya punya barangnya, keduanya sedang menipis. Memindahkan stok dari
    # gudang yang sendirinya sudah menyentuh titik pesan hanya memindahkan
    # masalahnya.
    "semua_kurang": dict(
        dek=12, jau=8,
        keputusan="PEMBELIAN", transfer=0, beli=BUTUH,
        dari=[], qty=[], ditolak=2),

    # Barangnya hanya ada di gudang ini.
    "tanpa_kandidat": dict(
        dek=None, jau=None,
        keputusan="PEMBELIAN", transfer=0, beli=BUTUH,
        dari=[], qty=[], ditolak=0),

    # Ada yang berlebih, tetapi tidak cukup. Sisanya WAJIB jatuh ke pembelian,
    # bukan hilang -- itulah cacat yang paling mudah lolos tanpa terlihat.
    "sebagian": dict(
        dek=25, jau=None,   # surplus 10 dari 13 yang dibutuhkan
        keputusan="TRANSFER_SEBAGIAN", transfer=10, beli=3,
        dari=["WH-DEK"], qty=[10]),
}


def _sku(nama: str) -> str:
    return f"TRF-{nama.upper()[:20]}"


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
    Satu perusahaan, tiga gudang, satu barang per kasus.

    Diisi lewat basis data langsung, bukan lewat API: yang diuji bukan cara
    data masuk melainkan kesimpulan yang ditarik mesin transfer darinya.
    """
    import psycopg

    sesi = klien.post("/api/auth/signup", json={
        "company_name": "PT Uji Transfer", "full_name": "Bayu Nugroho",
        "email": "bayu@ujitransfer.id", "password": SANDI}).json()
    cid = sesi["company"]["id"]
    hari_ini = date.today()

    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}", autocommit=True) as k, k.cursor() as cur:
        cur.execute("INSERT INTO categories (company_id, name) VALUES (%s,'MRO')"
                    " RETURNING id", (cid,))
        kat = cur.fetchone()[0]
        cur.execute("INSERT INTO units (company_id, name, code) VALUES (%s,'Pieces','PCS')"
                    " RETURNING id", (cid,))
        sat = cur.fetchone()[0]
        cur.execute("INSERT INTO units (company_id, name, code) VALUES (%s,'Liter','LTR')"
                    " RETURNING id", (cid,))
        sat_ltr = cur.fetchone()[0]

        gudang = {}
        for kode, nama, (lat, lon) in (
                ("WH-TUJ", "Gudang Tujuan Surabaya", SURABAYA),
                ("WH-DEK", "Gudang Dekat Sidoarjo", SIDOARJO),
                ("WH-JAU", "Gudang Jauh Jakarta", JAKARTA)):
            cur.execute(
                "INSERT INTO warehouses (company_id, code, name, latitude, longitude)"
                " VALUES (%s,%s,%s,%s,%s) RETURNING id", (cid, kode, nama, lat, lon))
            gudang[kode] = cur.fetchone()[0]

        # Jarak jalan darat, bukan garis lurus -- dan berarah, karena itulah
        # bentuk tabelnya.
        for asal, km, hari in (("WH-DEK", 25, 1), ("WH-JAU", 780, 3)):
            cur.execute(
                """INSERT INTO warehouse_distances
                       (company_id, from_warehouse_id, to_warehouse_id,
                        distance_km, lead_time_days)
                   VALUES (%s,%s,%s,%s,%s)""",
                (cid, gudang[asal], gudang["WH-TUJ"], km, hari))

        def buat_barang(sku, nama=None, unit=None):
            cur.execute(
                """INSERT INTO items (company_id, sku, name, category_id, unit_id,
                                      unit_price, minimum_stock, reorder_point,
                                      lead_time_days, safety_stock)
                   VALUES (%s,%s,%s,%s,%s,1000,5,%s,%s,%s) RETURNING id""",
                (cid, sku, nama or f"Barang {sku}", kat, unit or sat,
                 ROP_MASTER, LEAD, CADANGAN))
            return cur.fetchone()[0]

        def taruh(item_id, wh_id, stok):
            cur.execute(
                """INSERT INTO inventory (company_id, item_id, warehouse_id, quantity,
                                          reserved_quantity, available_quantity)
                   VALUES (%s,%s,%s,%s,0,%s)""", (cid, item_id, wh_id, stok, stok))
            cur.execute(
                """INSERT INTO stock_movements (company_id, item_id, warehouse_id,
                                                movement_type, movement_date, quantity)
                   VALUES (%s,%s,%s,'stock_in',%s,%s)""",
                (cid, item_id, wh_id, hari_ini - timedelta(days=HARI_RIWAYAT),
                 stok + HARI_RIWAYAT * LAJU))
            for i in range(HARI_RIWAYAT):
                cur.execute(
                    """INSERT INTO stock_movements (company_id, item_id, warehouse_id,
                                                    movement_type, movement_date, quantity)
                       VALUES (%s,%s,%s,'stock_out',%s,%s)""",
                    (cid, item_id, wh_id,
                     hari_ini - timedelta(days=HARI_RIWAYAT - 1 - i), -LAJU))

        barang = {}
        for nama, k_ in KASUS.items():
            iid = buat_barang(_sku(nama))
            barang[nama] = iid
            taruh(iid, gudang["WH-TUJ"], STOK_TUJUAN)
            for kode, kunci in (("WH-DEK", "dek"), ("WH-JAU", "jau")):
                if k_[kunci] is not None:
                    taruh(iid, gudang[kode], k_[kunci])

        # --- dua barang kembar untuk menguji pencocokan fuzzy ---
        # Nomornya berbeda, namanya hanya berbeda tanda hubung: persis bentuk
        # yang lahir dari dua orang yang memasukkan barang yang sama pada hari
        # yang berbeda.
        # Kemiripannya 0,9756 -- di atas ambang bawaan 0,88 dan di bawah 1,0,
        # sehingga pasangan ini dapat dipakai menguji KEDUA arah ambang: lolos
        # pada setelan bawaan, ditolak begitu ambangnya dinaikkan ke 1,0.
        kembar_tujuan = buat_barang("TRF-KEMBAR-A", "Filter Oli ABB 37613")
        kembar_sumber = buat_barang("TRF-KEMBAR-B", "Filter Olie ABB-37613")
        taruh(kembar_tujuan, gudang["WH-TUJ"], STOK_TUJUAN)
        taruh(kembar_sumber, gudang["WH-DEK"], 100)
        barang["kembar_tujuan"] = kembar_tujuan
        barang["kembar_sumber"] = kembar_sumber

        # Nama semirip itu, tetapi satuannya berbeda: jumlahnya tidak dapat
        # dibandingkan sama sekali, dan mesin harus menolaknya.
        satuan_a = buat_barang("TRF-SATUAN-A", "Oli Hidrolik Shell 36011", sat_ltr)
        satuan_b = buat_barang("TRF-SATUAN-B", "Oli Hidrolik Shell-36011", sat)
        taruh(satuan_a, gudang["WH-TUJ"], STOK_TUJUAN)
        taruh(satuan_b, gudang["WH-DEK"], 100)
        barang["satuan_a"] = satuan_a

    return {
        "cid": cid,
        "h": {"Authorization": "Bearer " + sesi["access_token"]},
        "gudang": gudang,
        "barang": barang,
    }


@pytest.fixture(scope="module")
def daftar(klien, dunia):
    r = klien.get("/api/transfer?page_size=200", headers=dunia["h"])
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def baris(daftar):
    """Peta SKU -> baris rekomendasi di gudang tujuan."""
    return {b["sku"]: b for b in daftar["items"] if b["to_warehouse_code"] == "WH-TUJ"}


# ==========================================================================
# 1. Enam kasus yang diminta
# ==========================================================================

class TestKasusYangDiminta:
    """
    Angka harapannya dieja pada tabel KASUS, bukan dihitung ulang di dalam uji.
    Uji yang menghitung sendiri rumus yang diujinya akan tetap lulus ketika
    rumus itu salah.
    """

    @pytest.mark.parametrize("nama", list(KASUS))
    def test_kebutuhan_dipinjam_utuh_dari_mesin_reorder(self, klien, dunia, baris, nama):
        """
        INVARIAN YANG PALING PENTING DI BERKAS INI. Kekurangan pada layar
        transfer wajib angka yang sama persis dengan yang disebut layar
        Pemesanan Ulang untuk barang dan gudang yang sama. Begitu keduanya
        berselisih, satu perusahaan akan memesan dua kali untuk satu kekurangan
        -- dan tidak ada satu pun galat yang terbit.
        """
        b = baris[_sku(nama)]
        assert b["need_qty"] == BUTUH, nama

        r = klien.get("/api/reorder?page_size=200", headers=dunia["h"]).json()
        reorder = {(x["sku"], x["warehouse_code"]): x for x in r["items"]}
        sama = reorder[(_sku(nama), "WH-TUJ")]
        assert b["need_qty"] == sama["recommended_order_qty"], nama
        assert b["effective_reorder_point_int"] == sama["effective_reorder_point_int"]

    @pytest.mark.parametrize("nama", list(KASUS))
    def test_keputusan(self, baris, nama):
        assert baris[_sku(nama)]["decision"] == KASUS[nama]["keputusan"], nama

    @pytest.mark.parametrize("nama", list(KASUS))
    def test_gudang_asal_dan_jumlah_tiap_kiriman(self, baris, nama):
        b, k = baris[_sku(nama)], KASUS[nama]
        assert [l["from_warehouse_code"] for l in b["legs"]] == k["dari"], nama
        assert [l["transfer_qty"] for l in b["legs"]] == k["qty"], nama

    @pytest.mark.parametrize("nama", list(KASUS))
    def test_transfer_ditambah_pembelian_selalu_menutup_kekurangan(self, baris, nama):
        b, k = baris[_sku(nama)], KASUS[nama]
        assert b["transfer_qty"] == k["transfer"], nama
        assert b["purchase_qty"] == k["beli"], nama
        # Tidak satu unit pun boleh menguap di antara kedua jalur.
        assert b["transfer_qty"] + b["purchase_qty"] == b["need_qty"], nama

    def test_gudang_yang_menipis_tercatat_sebagai_ditolak_beserta_sebabnya(self, baris):
        b = baris[_sku("semua_kurang")]
        assert len(b["rejected"]) == KASUS["semua_kurang"]["ditolak"]
        assert {r["rejected_reason"] for r in b["rejected"]} == {"TIDAK_AMAN"}
        # Sebabnya harus terbaca manusia, bukan hanya sebagai kunci.
        assert all(r["rejected_label"] for r in b["rejected"])

    def test_dua_jalan_menuju_pembelian_dibedakan_kalimatnya(self, baris):
        """
        "Barang ini hanya ada di gudang ini" dan "barang ini ada di mana-mana
        dan semuanya menipis" sama-sama berujung pembelian, dan yang kedua
        adalah kabar yang jauh lebih penting.
        """
        semua = baris[_sku("semua_kurang")]["reason"]
        sendiri = baris[_sku("tanpa_kandidat")]["reason"]
        assert semua != sendiri
        assert "tidak satu pun berlebih" in semua
        assert "Tidak ada gudang lain" in sendiri


# ==========================================================================
# 2. Surplus: dari mana angkanya, dan apa yang dijaganya
# ==========================================================================

class TestSurplus:

    def test_surplus_diukur_dari_titik_pesan_efektif_gudang_asal(self, baris):
        # WH-DEK punya 23 fisik; titik pesan efektifnya 15, jadi yang benar-
        # benar berlebih 8 -- bukan 23, dan bukan pula 23 dikurangi cadangan.
        leg = baris[_sku("gabungan")]["legs"][0]
        assert leg["source_stock_int"] == 23
        assert leg["source_reorder_point_int"] == ROP_EFEKTIF
        assert leg["surplus"] == 8

    def test_gudang_asal_tidak_pernah_ditinggalkan_di_bawah_titik_pesannya(self, baris):
        """
        Setiap kiriman pada setiap kasus harus menyisakan gudang asalnya tetap
        di atas titik pesan efektifnya sendiri. Inilah satu-satunya jaminan
        bahwa modul ini menyelesaikan kekurangan alih-alih memindahkannya.
        """
        for nama in KASUS:
            for leg in baris[_sku(nama)]["legs"]:
                sisa = leg["source_stock_int"] - leg["transfer_qty"]
                assert sisa >= leg["source_reorder_point_int"], (nama, leg)

    def test_stok_tercadang_ikut_mengurangi_surplus(self, klien, dunia):
        """
        Surplus dibaca dari stok TERSEDIA, bukan stok fisik. Barang yang sudah
        dikomitmenkan keluar tidak dapat dinaikkan ke truk menuju gudang lain,
        dan membacanya sebagai surplus berarti menjanjikan barang yang sama
        kepada dua pihak.
        """
        import psycopg

        iid = dunia["barang"]["dekat_cukup"]
        wh = dunia["gudang"]["WH-DEK"]
        with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}", autocommit=True) as k, k.cursor() as cur:
            cur.execute(
                """UPDATE inventory SET reserved_quantity = 90,
                          available_quantity = quantity - 90
                    WHERE item_id = %s AND warehouse_id = %s""", (iid, wh))
        try:
            r = klien.get("/api/transfer/detail",
                          params={"item_id": iid,
                                  "warehouse_id": dunia["gudang"]["WH-TUJ"]},
                          headers=dunia["h"]).json()
            dek = next(k for k in r["candidates"] + r["rejected"]
                       if k["from_warehouse_code"] == "WH-DEK")
            # fisik 100, tercadang 90 -> tersedia 10, di bawah titik pesan 15.
            assert dek["source_stock_int"] == 10
            assert dek["eligible"] is False
        finally:
            with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}", autocommit=True) as k, k.cursor() as cur:
                cur.execute(
                    """UPDATE inventory SET reserved_quantity = 0,
                              available_quantity = quantity
                        WHERE item_id = %s AND warehouse_id = %s""", (iid, wh))


# ==========================================================================
# 3. Jarak dan skor
# ==========================================================================

class TestJarakDanSkor:

    def test_jarak_yang_ditetapkan_tangan_yang_dipakai(self, baris):
        """
        Garis lurus Sidoarjo-Surabaya sekitar 21 km; tabel jarak menyatakan 25
        km jalan darat. Yang dipakai harus yang ditempuh truk.
        """
        leg = baris[_sku("dekat_cukup")]["legs"][0]
        assert leg["distance_km"] == 25.0
        assert leg["distance_basis"] == "matrix"
        assert leg["lead_time_days"] == 1

    def test_skor_menerbitkan_komponen_yang_menyusunnya(self, baris):
        """Peringkat yang tidak dapat dibantah bukan peringkat. Empat
        komponennya harus ikut sampai ke layar."""
        leg = baris[_sku("dekat_cukup")]["legs"][0]
        assert 0 <= leg["score"] <= 100
        assert set(leg["components"]) >= {"sufficiency", "surplus_ratio",
                                          "distance", "lead_time"}
        assert leg["components"]["sufficiency"] == 1.0

    def test_alasan_menyebut_angka_yang_sama_dengan_kolomnya(self, baris):
        leg = baris[_sku("dekat_cukup")]["legs"][0]
        assert str(leg["surplus"]) in leg["why"]
        assert "25" in leg["why"]

    def test_kandidat_kalah_tetap_terbit_dengan_skornya(self, baris):
        """
        Yang membaca layar berhak tahu ada pilihan kedua bila gudang teratas
        menolak mengirim hari itu.
        """
        b = baris[_sku("dekat_cukup")]
        assert [k["from_warehouse_code"] for k in b["candidates"]] == ["WH-DEK", "WH-JAU"]
        assert b["candidates"][0]["score"] > b["candidates"][1]["score"]


# ==========================================================================
# 4. Pencocokan fuzzy
# ==========================================================================

class TestFuzzy:

    def test_mati_secara_bawaan(self, klien, dunia):
        r = klien.get("/api/transfer/detail",
                      params={"item_id": dunia["barang"]["kembar_tujuan"],
                              "warehouse_id": dunia["gudang"]["WH-TUJ"]},
                      headers=dunia["h"]).json()
        assert r["decision"] == "PEMBELIAN"
        assert r["candidates"] == [] and r["rejected"] == []

    def test_menyala_atas_permintaan_dan_menandai_dasarnya(self, klien, dunia):
        r = klien.get("/api/transfer/detail",
                      params={"item_id": dunia["barang"]["kembar_tujuan"],
                              "warehouse_id": dunia["gudang"]["WH-TUJ"],
                              "fuzzy": "true"},
                      headers=dunia["h"]).json()
        assert r["decision"] == "TRANSFER"
        leg = r["legs"][0]
        assert leg["match_type"] == "fuzzy"
        assert leg["match_similarity"] >= 0.88
        # Barang yang DIKIRIM milik gudang asal; kebutuhan yang ditutupnya
        # milik barang lain, dan keduanya harus tetap dapat dibedakan.
        assert leg["item_id"] == dunia["barang"]["kembar_sumber"]
        assert r["item_id"] == dunia["barang"]["kembar_tujuan"]

    def test_ambang_dapat_dinaikkan_sampai_menolak(self, klien, dunia):
        """
        Ambangnya adalah kendali, bukan hiasan. Dinaikkan ke 1,0 ia menuntut
        nama yang sama persis setelah dinormalisasi -- dan pasangan yang mirip
        97% pun berhenti menjadi kandidat.
        """
        r = klien.get("/api/transfer/detail",
                      params={"item_id": dunia["barang"]["kembar_tujuan"],
                              "warehouse_id": dunia["gudang"]["WH-TUJ"],
                              "fuzzy": "true", "similarity": "1.0"},
                      headers=dunia["h"]).json()
        assert r["decision"] == "PEMBELIAN"
        assert r["candidates"] == []

    def test_satuan_berbeda_ditolak_walau_namanya_mirip(self, klien, dunia):
        r = klien.get("/api/transfer/detail",
                      params={"item_id": dunia["barang"]["satuan_a"],
                              "warehouse_id": dunia["gudang"]["WH-TUJ"],
                              "fuzzy": "true"},
                      headers=dunia["h"]).json()
        assert r["decision"] == "PEMBELIAN"
        assert r["rejected"][0]["rejected_reason"] == "SATUAN_BEDA"

    def test_ringkasan_menyatakan_fuzzy_sedang_menyala(self, klien, dunia):
        mati = klien.get("/api/transfer?page_size=200", headers=dunia["h"]).json()
        hidup = klien.get("/api/transfer?page_size=200&fuzzy=true",
                          headers=dunia["h"]).json()
        assert mati["summary"]["memakai_fuzzy"] is False
        assert hidup["summary"]["memakai_fuzzy"] is True
        # Menyalakannya hanya boleh MENAMBAH kemungkinan, tidak pernah
        # mengurangi: cocok pasti tidak tersentuh olehnya.
        assert hidup["summary"]["total_qty_transfer"] >= mati["summary"]["total_qty_transfer"]


# ==========================================================================
# 5. Bilangan bulat
# ==========================================================================

def test_seluruh_kuantitas_pada_jawaban_adalah_bilangan_bulat(daftar):
    for b in daftar["items"]:
        for nama in ("need_qty", "transfer_qty", "purchase_qty"):
            assert isinstance(b[nama], int), (b["sku"], nama)
        for leg in b["legs"]:
            assert isinstance(leg["transfer_qty"], int)
            assert isinstance(leg["surplus"], int)
            assert isinstance(leg["source_stock_int"], int)


def test_ringkasan_menjumlahkan_seluruh_hasil_bukan_satu_halaman(klien, dunia):
    penuh = klien.get("/api/transfer?page_size=200", headers=dunia["h"]).json()
    sehalaman = klien.get("/api/transfer?page_size=1", headers=dunia["h"]).json()
    assert sehalaman["summary"] == penuh["summary"]
    assert len(sehalaman["items"]) == 1


def test_saringan_gudang_tujuan_tidak_membuang_kandidat_sumber(klien, dunia):
    """
    Cacat yang paling mudah terjadi saat menyalin pola dari daftar Pemesanan
    Ulang: menyaring pasangan barang/gudang di SQL menurut gudang yang dipilih.
    Saringan itu membuang gudang lain dari himpunan yang sama -- yaitu membuang
    justru kandidat sumbernya -- dan hasilnya adalah "tidak ada gudang lain
    yang punya barang ini" untuk barang yang jelas-jelas ada di sebelah.
    """
    r = klien.get("/api/transfer", params={"warehouse_id": dunia["gudang"]["WH-TUJ"],
                                           "page_size": 200},
                  headers=dunia["h"]).json()
    b = {x["sku"]: x for x in r["items"]}[_sku("dekat_cukup")]
    assert b["decision"] == "TRANSFER"
    assert b["legs"][0]["from_warehouse_code"] == "WH-DEK"


# ==========================================================================
# 6. Dokumen: alur status dan akibatnya pada stok
# ==========================================================================

@pytest.fixture(scope="module")
def diajukan(klien, dunia, baris):
    """
    Satu transfer nyata, diajukan dari baris rekomendasi kasus 'dekat_cukup'.

    Berlingkup MODUL, bukan kelas: uji pemisahan penyewa di bawah membacanya
    juga, dan dokumen kedua yang dibuat khusus untuk uji itu akan menguji
    jalur yang berbeda dari yang benar-benar dipakai orang.
    """
    b = baris[_sku("dekat_cukup")]
    leg = b["legs"][0]
    r = klien.post("/api/transfers", headers=dunia["h"], json={
        "from_warehouse_id": leg["from_warehouse_id"],
        "to_warehouse_id": b["to_warehouse_id"],
        "score": leg["score"], "reason": leg["why"],
        "distance_km": leg["distance_km"], "source": "transfer_engine",
        "items": [{"item_id": leg["item_id"], "quantity": leg["transfer_qty"],
                   "for_item_id": b["item_id"], "match_type": leg["match_type"]}],
    })
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture(scope="module")
def stok():
    """
    Saldo satu barang di satu gudang, dibaca LANGSUNG dari basis data.

    Sengaja tidak lewat API: yang sedang diperiksa adalah akibat perpindahan
    status pada persediaan, dan membacanya lewat endpoint yang sama-sama bisa
    salah berarti dua kesalahan yang saling menutupi.
    """
    import psycopg

    def baca(item_id, wh_id):
        with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
            cur.execute(
                """SELECT quantity, reserved_quantity, available_quantity
                     FROM inventory WHERE item_id = %s AND warehouse_id = %s""",
                (item_id, wh_id))
            b = cur.fetchone()
            return None if b is None else tuple(int(v) for v in b)
    return baca


class TestDokumen:

    def test_pengajuan_tidak_menyentuh_stok_sama_sekali(self, dunia, stok, diajukan):
        """
        Pengajuan hanya mencatat niat. Pemisahan ini yang membuat dokumen dapat
        ditolak tanpa meninggalkan jejak apa pun pada persediaan.
        """
        assert diajukan["status"] == "draft"
        assert stok(dunia["barang"]["dekat_cukup"], dunia["gudang"]["WH-DEK"]) \
            == (100, 0, 100)

    def test_jejak_keputusan_dibekukan_pada_dokumen(self, klien, dunia, diajukan):
        """
        Rekomendasi dihitung ulang setiap kali dibuka; dokumen tidak boleh ikut
        berubah alasannya. Yang perlu dijawab sebulan kemudian adalah kenapa
        WAKTU ITU gudang ini yang dipilih.
        """
        r = klien.get(f"/api/transfers/{diajukan['transfer_id']}",
                      headers=dunia["h"]).json()
        assert r["transfer"]["score"] > 0
        assert r["transfer"]["reason"]
        assert float(r["transfer"]["distance_km"]) == 25.0
        assert r["transfer"]["source"] == "transfer_engine"
        assert r["lines"][0]["quantity"] == 13

    def test_daftar_dokumen_membawa_koordinat_kedua_gudang(self, klien, dunia,
                                                          diajukan):
        """
        Peta rute menggambar dari jawaban INI, bukan dari daftar gudang yang
        dijahit di layar.

        DAN ANGKA, BUKAN STRING. Kolomnya numeric, dan Decimal berangkat ke
        JSON sebagai "112.752100": peta yang menerimanya sebagai teks
        meletakkan gudangnya di tengah Samudra Atlantik -- tanpa satu pun galat
        yang terbit, karena secara teknis tidak ada yang gagal.
        """
        d = next(x for x in klien.get("/api/transfers", headers=dunia["h"]).json()["items"]
                 if x["id"] == diajukan["transfer_id"])

        for kunci in ("from_latitude", "from_longitude",
                      "to_latitude", "to_longitude"):
            assert isinstance(d[kunci], float), f"{kunci} bukan angka: {d[kunci]!r}"

        assert (d["from_latitude"], d["from_longitude"]) == SIDOARJO
        assert (d["to_latitude"], d["to_longitude"]) == SURABAYA

    def test_lompatan_status_ditolak(self, klien, dunia, diajukan):
        """
        Dari "diajukan" langsung ke "diterima" berarti stok bertambah di gudang
        tujuan tanpa pernah berkurang di gudang asal, dan selisihnya tidak akan
        pernah muncul sebagai galat -- hanya sebagai stok yang tidak cocok saat
        opname.
        """
        r = klien.patch(f"/api/transfers/{diajukan['transfer_id']}/status",
                        headers=dunia["h"], json={"status": "completed"})
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "INVALID_TRANSITION"

    def test_persetujuan_mencadangkan_stok_asal(self, klien, dunia, stok, diajukan):
        """
        Fisiknya belum bergerak, tetapi stok TERSEDIA turun -- dan karena mesin
        rekomendasi membaca stok tersedia, gudang itu berhenti menawarkan
        barang yang sama untuk kebutuhan gudang ketiga.
        """
        r = klien.patch(f"/api/transfers/{diajukan['transfer_id']}/status",
                        headers=dunia["h"], json={"status": "approved"})
        assert r.status_code == 200, r.text
        assert stok(dunia["barang"]["dekat_cukup"], dunia["gudang"]["WH-DEK"]) \
            == (100, 13, 87)

    def test_pengiriman_mengurangi_stok_asal_dan_mencatat_ledger(
            self, klien, dunia, stok, diajukan):
        r = klien.patch(f"/api/transfers/{diajukan['transfer_id']}/status",
                        headers=dunia["h"], json={"status": "in_transit"})
        assert r.status_code == 200, r.text
        # Cadangan dilepas dan saldo benar-benar berkurang; keduanya sekaligus,
        # bukan salah satu.
        assert stok(dunia["barang"]["dekat_cukup"], dunia["gudang"]["WH-DEK"]) \
            == (87, 0, 87)

        d = klien.get(f"/api/transfers/{diajukan['transfer_id']}",
                      headers=dunia["h"]).json()
        keluar = [m for m in d["movements"] if m["movement_type"] == "transfer_out"]
        assert len(keluar) == 1 and float(keluar[0]["quantity"]) == -13

    def test_barang_dalam_perjalanan_tidak_dapat_dibatalkan(self, klien, dunia, diajukan):
        """Membatalkan barang yang sudah di jalan bukan pembatalan melainkan
        transfer balik, dan itu dokumen tersendiri."""
        r = klien.patch(f"/api/transfers/{diajukan['transfer_id']}/status",
                        headers=dunia["h"], json={"status": "cancelled"})
        assert r.status_code == 422

    def test_penerimaan_menambah_stok_tujuan(self, klien, dunia, stok, diajukan):
        sebelum = stok(dunia["barang"]["dekat_cukup"], dunia["gudang"]["WH-TUJ"])
        r = klien.patch(f"/api/transfers/{diajukan['transfer_id']}/status",
                        headers=dunia["h"], json={"status": "completed"})
        assert r.status_code == 200, r.text
        sesudah = stok(dunia["barang"]["dekat_cukup"], dunia["gudang"]["WH-TUJ"])
        assert sesudah[0] == sebelum[0] + 13
        assert sesudah[2] == sebelum[2] + 13

        d = klien.get(f"/api/transfers/{diajukan['transfer_id']}",
                      headers=dunia["h"]).json()
        masuk = [m for m in d["movements"] if m["movement_type"] == "transfer_in"]
        assert len(masuk) == 1 and float(masuk[0]["quantity"]) == 13
        # Kedua sisi tercatat: buku besar harus menjelaskan seluruh perpindahan,
        # bukan hanya ujungnya.
        assert len(d["movements"]) == 2

    def test_dokumen_selesai_tidak_dapat_dipindahkan_lagi(self, klien, dunia, diajukan):
        for tujuan in ("in_transit", "cancelled", "approved"):
            r = klien.patch(f"/api/transfers/{diajukan['transfer_id']}/status",
                            headers=dunia["h"], json={"status": tujuan})
            assert r.status_code == 422, tujuan

    def test_rekomendasi_berkurang_setelah_barang_benar_benar_pindah(
            self, klien, dunia, baris):
        """
        Ujung yang membuat modul ini berarti: setelah transfer diterima, gudang
        tujuan tidak lagi muncul sebagai kekurangan yang sama. Angkanya lahir
        dari stok, bukan dari catatan bahwa transfernya pernah dibuat.
        """
        r = klien.get("/api/transfer?page_size=200", headers=dunia["h"]).json()
        sekarang = {b["sku"]: b for b in r["items"]}
        sebelumnya = baris[_sku("dekat_cukup")]["need_qty"]
        assert _sku("dekat_cukup") not in sekarang or \
            sekarang[_sku("dekat_cukup")]["need_qty"] < sebelumnya


# ==========================================================================
# 7. Penjagaan pintu masuk
# ==========================================================================

class TestPenjagaan:

    def test_kuantitas_berdesimal_ditolak(self, klien, dunia):
        """
        Yang dipindahkan barang fisik. "Kirim 3,4 bearing" bukan perintah yang
        dapat dijalankan siapa pun, dan menolaknya di pintu masuk jauh lebih
        murah daripada membulatkannya di setiap layar yang membacanya.
        """
        r = klien.post("/api/transfers", headers=dunia["h"], json={
            "from_warehouse_id": dunia["gudang"]["WH-DEK"],
            "to_warehouse_id": dunia["gudang"]["WH-TUJ"],
            "items": [{"item_id": dunia["barang"]["gabungan"], "quantity": 3.4}],
        })
        assert r.status_code == 422
        assert "bulat" in r.json()["error"]["message"].lower()

    def test_gudang_asal_dan_tujuan_tidak_boleh_sama(self, klien, dunia):
        r = klien.post("/api/transfers", headers=dunia["h"], json={
            "from_warehouse_id": dunia["gudang"]["WH-TUJ"],
            "to_warehouse_id": dunia["gudang"]["WH-TUJ"],
            "items": [{"item_id": dunia["barang"]["gabungan"], "quantity": 1}],
        })
        assert r.status_code == 422

    def test_pengajuan_melebihi_stok_tersedia_ditolak(self, klien, dunia):
        """
        Mengajukan 500 unit dari gudang yang punya 23 bukan rencana melainkan
        kesalahan ketik, dan menemukannya tiga hari kemudian saat hendak
        dikirim jauh lebih mahal.
        """
        r = klien.post("/api/transfers", headers=dunia["h"], json={
            "from_warehouse_id": dunia["gudang"]["WH-DEK"],
            "to_warehouse_id": dunia["gudang"]["WH-TUJ"],
            "items": [{"item_id": dunia["barang"]["gabungan"], "quantity": 500}],
        })
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "INSUFFICIENT_STOCK"

    def test_transfer_penyewa_lain_tidak_terlihat(self, klien, dunia, diajukan):
        """
        Row Level Security berlaku atas tabel dokumen ini persis seperti atas
        tabel lain. Penyewa kedua tidak boleh melihat, apalagi memindahkan,
        transfer milik penyewa pertama.
        """
        lain = klien.post("/api/auth/signup", json={
            "company_name": "PT Tetangga", "full_name": "Rina Kusuma",
            "email": "rina@tetangga.id", "password": SANDI}).json()
        h = {"Authorization": "Bearer " + lain["access_token"]}

        assert klien.get("/api/transfers", headers=h).json()["items"] == []
        assert klien.get(f"/api/transfers/{diajukan['transfer_id']}",
                         headers=h).status_code == 404
        assert klien.patch(f"/api/transfers/{diajukan['transfer_id']}/status",
                           headers=h, json={"status": "cancelled"}).status_code == 404
