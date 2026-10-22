# -*- coding: utf-8 -*-
"""
Uji penyewa demo: pengisian, simulasi penjualan, dan penjaganya.

    .venv/bin/python -m pytest backend/tests/test_demo.py -q

YANG PALING PENTING DI SINI ADALAH DUA HAL.

Pertama, PENJAGANYA. Pengisian ulang menghapus SELURUH isi satu perusahaan.
Bila penjaganya keliru sedikit saja, tombol yang dimaksudkan untuk merapikan
demo akan mengosongkan data pelanggan sungguhan -- kesalahan yang tidak ada
jalan pulangnya. Karena itu penolakan pada perusahaan biasa diuji sama
seriusnya dengan keberhasilannya pada perusahaan demo.

Kedua, KETERPADUAN ANGKANYA. Data demo yang saldo stoknya tidak cocok dengan
riwayat pergerakannya akan hancur pada pertanyaan pertama calon pelanggan yang
teliti. Invarian itu diuji langsung, bukan diandaikan.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import INDUK, NAMA_DB_UJI, bangun_basis_uji, buat_perusahaan  # noqa: E402
from app import demo  # noqa: E402

SANDI = "kataSandiDemo123"


@pytest.fixture(scope="module")
def klien():
    alasan = bangun_basis_uji()
    if alasan:
        pytest.skip(f"basis data uji tidak tersedia: {alasan}")

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def _tandai_demo(company_id: int) -> None:
    """
    Menandai perusahaan sebagai demo, lewat admin basis data.

    Di dunia nyata penandaan ini dikerjakan app/jobs/buat_demo.py. Di sini
    dipendekkan supaya yang diuji adalah perilaku SESUDAH penandaan, bukan
    perintah baris perintahnya.
    """
    import psycopg

    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}", autocommit=True) as k, k.cursor() as cur:
        cur.execute("UPDATE companies SET is_demo = TRUE WHERE id = %s", (company_id,))


@pytest.fixture(scope="module")
def dunia(klien):
    """Satu perusahaan demo dan satu perusahaan biasa, berdampingan."""
    demo = buat_perusahaan(klien, "Demo Inventory AI", "Akun Demo", "demo", SANDI)
    asli = buat_perusahaan(klien, "PT Pelanggan Sungguhan", "Rina Hartati", "rina", SANDI)

    _tandai_demo(demo["company"]["id"])

    return {
        "demo": demo,
        "asli": asli,
        "hDemo": {"Authorization": "Bearer " + demo["access_token"]},
        "hAsli": {"Authorization": "Bearer " + asli["access_token"]},
    }


# ==========================================================================
# Penjaga
# ==========================================================================

def test_perusahaan_biasa_tidak_dikenali_sebagai_demo(klien, dunia):
    r = klien.get("/api/demo/status", headers=dunia["hAsli"])
    assert r.status_code == 200
    assert r.json()["is_demo"] is False


def test_perusahaan_biasa_tidak_dapat_mengosongkan_dirinya(klien, dunia):
    """
    Penjaga yang paling penting di seluruh modul ini.

    Endpoint-nya sengaja dipanggil langsung, bukan lewat tombol -- justru
    pemanggilan langsung itulah yang harus ditolak, karena tombolnya memang
    tidak pernah ditampilkan pada perusahaan biasa.
    """
    import psycopg

    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute("SELECT count(*) FROM users WHERE company_id = %s",
                    (dunia["asli"]["company"]["id"],))
        pengguna_sebelum = cur.fetchone()[0]

    r = klien.post("/api/demo/reset", headers=dunia["hAsli"])
    assert r.status_code == 403

    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute("SELECT count(*) FROM users WHERE company_id = %s",
                    (dunia["asli"]["company"]["id"],))
        assert cur.fetchone()[0] == pengguna_sebelum


def test_viewer_tidak_dapat_mengisi_ulang(klien, dunia):
    klien.post("/api/users", headers=dunia["hDemo"], json={
        "username": "penonton", "full_name": "Penonton Demo",
        "password": "kataSandiLihat1", "role": "viewer"})
    v = klien.post("/api/auth/login", json={
        "username": "penonton", "password": "kataSandiLihat1"}).json()
    h = {"Authorization": "Bearer " + v["access_token"]}

    # Boleh TAHU bahwa ini perusahaan demo -- itu yang dipakai antarmuka untuk
    # memutuskan menampilkan tombol -- tetapi tidak boleh menekannya.
    assert klien.get("/api/demo/status", headers=h).json()["is_demo"] is True
    assert klien.post("/api/demo/reset", headers=h).status_code == 403


# ==========================================================================
# Pengisian
# ==========================================================================

def test_pengisian_menghasilkan_data_yang_terpakai(klien, dunia):
    r = klien.post("/api/demo/reset", headers=dunia["hDemo"], params={"hari": 45})
    assert r.status_code == 200, r.text[:300]
    terisi = r.json()["terisi"]

    # Diturunkan dari daftar sumbernya, bukan ditulis mati: isi katalog demo
    # sudah dua kali berubah (Bandung dihapus 31 Agustus 2026, katalog dipangkas
    # menjadi 20 barang 1 September 2026) dan angka tetap di sini membuat tes
    # gagal karena alasan yang tidak ada hubungannya dengan yang sedang diuji --
    # yaitu bahwa pengisian menghasilkan data yang terpakai.
    assert terisi["barang"] == len(demo.BARANG)
    assert terisi["gudang"] == len(demo.GUDANG)
    assert terisi["penerimaan"] > 0
    assert terisi["pengeluaran"] > 30   # tidak mungkin hanya beberapa hari
    # Satu baris stok untuk tiap barang, DITAMBAH satu baris lagi untuk tiap
    # barang yang sengaja disimpan di dua gudang (demo.SEBARAN). Diturunkan dari
    # kedua daftar itu, bukan ditulis mati: yang diuji di sini adalah bahwa
    # pengisian menghasilkan data yang terpakai, bukan panjang katalognya.
    assert terisi["baris_stok"] == len(demo.BARANG) + len(demo.SEBARAN)
    assert terisi["transfer"] == len(demo.DOKUMEN_TRANSFER)


def test_sebaran_gudang_mengikuti_katalog(klien, dunia):
    """
    Tiap barang berada di gudang yang disebut katalog -- tidak lebih, tidak
    kurang.

    Bentuknya berubah 3 September 2026. Sebelumnya satu barang hanya boleh
    tinggal di satu gudang, dan justru itu yang membuat halaman Transfer Antar
    Gudang menjawab "beli baru" pada setiap baris: tidak pernah ada gudang lain
    yang sudah punya barangnya. Kini tujuh barang pada demo.SEBARAN disimpan di
    dua gudang sekaligus, dan sisanya tetap di satu gudang.

    Diuji lewat basis data, bukan lewat panjang daftar saja: yang bisa salah
    bukan katalognya melainkan penyebarannya -- satu barang bisa tercatat di
    gudang yang bukan gudangnya tanpa mengubah jumlah barang.
    """
    import psycopg

    klien.post("/api/demo/reset", headers=dunia["hDemo"], params={"hari": 30})
    cid = dunia["demo"]["company"]["id"]

    # Empat gudang: Surabaya, Jakarta, Semarang (di Jawa), Makassar (di luar
    # Jawa). Dua puluh komponen berumur pakai tinggal di Surabaya/Jakarta (13 +
    # 12 baris), sepuluh barang habis pakai tersebar di keempatnya
    # (tools/jaringan_gudang.SEBAR: 37 penempatan): Surabaya 10, Jakarta 10,
    # Semarang 9, Makassar 8.
    baru_dua_gudang = ["FO-7013", "FO-7016", "GP-7001", "GP-7011", "OH-7006"]
    per_gudang = {"WH-SBY": 23, "WH-JKT": 22, "WH-SMG": 9, "WH-MKS": 8}
    from tools import jaringan_gudang
    sebaran = {sku: None for sku in baru_dua_gudang}
    sebaran.update({sku: None for sku in jaringan_gudang.SEBAR})

    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute(
            """
            SELECT w.code, count(*)
              FROM inventory inv
              JOIN warehouses w ON w.id = inv.warehouse_id
             WHERE inv.company_id = %s
             GROUP BY w.code ORDER BY w.code
            """,
            (cid,),
        )
        assert dict(cur.fetchall()) == per_gudang

        # Yang tinggal di dua gudang tepat yang disebut SEBARAN, bukan yang lain.
        cur.execute(
            """
            SELECT it.sku
              FROM inventory inv
              JOIN items it ON it.id = inv.item_id
             WHERE inv.company_id = %s
             GROUP BY it.sku HAVING count(*) > 1
             ORDER BY it.sku
            """,
            (cid,),
        )
        assert [r[0] for r in cur.fetchall()] == sorted(sebaran)


def test_halaman_utama_terisi_setelah_pengisian(klien, dunia):
    """Bukan sekadar tabelnya berisi: halaman yang dipakai saat demo harus
    benar-benar menampilkan sesuatu."""
    for jalur in ("/api/dashboard", "/api/inventory", "/api/items",
                  "/api/warehouses", "/api/stock-issues"):
        r = klien.get(jalur, headers=dunia["hDemo"])
        assert r.status_code == 200, f"{jalur}: {r.text[:200]}"

    stok = klien.get("/api/inventory", headers=dunia["hDemo"]).json()
    assert stok["total"] > 0


def test_saldo_stok_cocok_dengan_riwayat_pergerakan(klien, dunia):
    """
    Invarian yang menentukan apakah data demo layak ditunjukkan.

    Bila tabel inventory ditulis sendiri dan stock_movements ditulis sendiri,
    keduanya akan berbeda cepat atau lambat -- dan perbedaan itu muncul sebagai
    laporan stok yang bertentangan dengan riwayatnya, tepat di depan orang yang
    sedang menilai apakah sistem ini bisa dipercaya.
    """
    import psycopg

    cid = dunia["demo"]["company"]["id"]
    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FROM (
                SELECT inv.item_id, inv.warehouse_id, inv.quantity,
                       COALESCE(SUM(m.quantity), 0) AS dari_gerakan
                  FROM inventory inv
                  LEFT JOIN stock_movements m
                         ON m.item_id = inv.item_id
                        AND m.warehouse_id = inv.warehouse_id
                        AND m.company_id = inv.company_id
                 WHERE inv.company_id = %s
                 GROUP BY inv.item_id, inv.warehouse_id, inv.quantity
                HAVING inv.quantity <> COALESCE(SUM(m.quantity), 0)
            ) selisih
            """,
            (cid,),
        )
        assert cur.fetchone()[0] == 0


def test_tidak_ada_stok_negatif_setelah_pengisian(klien, dunia):
    import psycopg

    cid = dunia["demo"]["company"]["id"]
    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM inventory WHERE company_id = %s AND quantity < 0",
            (cid,))
        assert cur.fetchone()[0] == 0


def test_pengisian_ulang_tidak_menumpuk(klien, dunia):
    """Menekan tombolnya dua kali harus menghasilkan keadaan yang sama, bukan
    dua kali lipat isinya."""
    pertama = klien.post("/api/demo/reset", headers=dunia["hDemo"],
                         params={"hari": 30}).json()["terisi"]
    kedua = klien.post("/api/demo/reset", headers=dunia["hDemo"],
                       params={"hari": 30}).json()["terisi"]
    assert pertama == kedua


def test_pengisian_tidak_menyentuh_perusahaan_lain(klien, dunia):
    """Perusahaan biasa yang berdampingan harus utuh sesudahnya."""
    barang_asli = klien.get("/api/items", headers=dunia["hAsli"]).json()
    klien.post("/api/demo/reset", headers=dunia["hDemo"], params={"hari": 30})
    assert klien.get("/api/items", headers=dunia["hAsli"]).json()["total"] == barang_asli["total"]
    assert klien.get("/api/auth/me", headers=dunia["hAsli"]).status_code == 200


def test_status_melaporkan_isi_terkini(klien, dunia):
    klien.post("/api/demo/reset", headers=dunia["hDemo"], params={"hari": 30})
    s = klien.get("/api/demo/status", headers=dunia["hDemo"]).json()
    assert s["is_demo"] is True
    assert s["terisi"] is True
    # Dua puluh komponen berumur pakai + sepuluh barang harian yang dipertahankan.
    assert s["barang"] == 30
    assert s["pengeluaran"] > 0


# ==========================================================================
# Mutu data demo
# ==========================================================================
#
# Dua uji di bawah menjaga hal yang TIDAK terlihat dari kode jawaban 200, dan
# keduanya sempat salah saat modul ini dibangun.
#
# Pengisian versi pertama membuat 43% seluruh rak berada di bawah titik pesan,
# karena setiap pasangan barang/gudang memulai siklusnya dari titik yang sama
# lalu menuruninya serentak. Akibatnya dua hal sekaligus: gudangnya terbaca
# kacau, dan tombol simulasi tidak menggerakkan apa pun -- semuanya sudah
# terlanjur merah sebelum tombolnya ditekan. Seluruh uji tetap lulus.

def test_porsi_stok_menipis_masuk_akal(klien, dunia):
    """
    Bukan hampir semuanya, dan bukan tidak satu pun.

    Batas atas menjaga gudang demo tidak terbaca sebagai gudang yang kacau.
    Batas bawah menjaga halaman Stok Menipis dan Pemesanan Ulang -- dua halaman
    yang paling ingin dilihat calon pelanggan -- tidak kosong.
    """
    import psycopg

    cid = dunia["demo"]["company"]["id"]
    klien.post("/api/demo/reset", headers=dunia["hDemo"])

    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute(
            """
            SELECT count(*) FILTER (
                       WHERE inv.available_quantity <= it.reorder_point) AS menipis,
                   count(*) AS semua
              FROM inventory inv
              JOIN items it ON it.id = inv.item_id
             WHERE inv.company_id = %s AND it.reorder_point IS NOT NULL
            """,
            (cid,),
        )
        menipis, semua = cur.fetchone()

    porsi = menipis / semua
    assert 0.05 <= porsi <= 0.35, (
        f"{menipis} dari {semua} baris stok menipis ({porsi:.0%}); "
        f"di luar rentang yang layak ditunjukkan"
    )


# ==========================================================================
# Transfer antar gudang
# ==========================================================================
#
# Dua uji di bawah menjaga hal yang menjadi alasan SEBARAN ada sama sekali.
# Sebelum 3 September 2026 seluruh uji demo lulus sementara halaman Transfer
# menjawab "beli baru" pada setiap barisnya -- bukan karena mesinnya salah,
# melainkan karena data demo tidak pernah menyimpan satu barang pun di dua
# gudang. Yang tidak diuji di sini justru itu: bahwa datanya bisa menjawab
# pertanyaan yang ditanyakan modul itu.

def test_data_demo_menghasilkan_rekomendasi_transfer(klien, dunia):
    """
    Barang skenario benar-benar terbaca sebagai transfer oleh mesinnya.

    Disaring per SKU, bukan meminta seluruh daftar: tiap pasangan
    barang/gudang menjalankan rantai prakiraan penuh, dan menilai dua puluh
    tujuh pasangan sekaligus membuat uji ini berjalan berpuluh detik untuk
    menjawab pertanyaan yang sudah terjawab oleh dua barang.
    """
    klien.post("/api/demo/reset", headers=dunia["hDemo"])

    # SP-1001: Surabaya berlebih 3,4 kali titik pesan; Jakarta (0,55) dan
    # Makassar (0,50) kekurangan -- dua baris tujuan, keduanya ditutup dari
    # Surabaya tanpa pembelian.
    r = klien.get("/api/transfer", headers=dunia["hDemo"], params={"q": "SP-1001"})
    assert r.status_code == 200, r.text[:300]
    baris = r.json()["items"]
    assert {b["to_warehouse_code"] for b in baris} == {"WH-JKT", "WH-MKS"}
    for b in baris:
        assert b["decision"] == "TRANSFER", b["reason"]
        assert b["legs"] and b["legs"][0]["from_warehouse_code"] == "WH-SBY"
        assert b["purchase_qty"] == 0

    # Filter Oli ABB: Surabaya kehabisan, Jakarta menyimpan 4 -- surplusnya
    # menutup seluruh kebutuhan.
    r = klien.get("/api/transfer", headers=dunia["hDemo"],
                  params={"q": "ABB 37613"})
    assert r.status_code == 200, r.text[:300]
    baris = r.json()["items"]
    assert len(baris) == 1, "hanya gudang tujuan yang kekurangan yang boleh muncul"
    assert baris[0]["decision"] == "TRANSFER", baris[0]["reason"]
    assert baris[0]["to_warehouse_code"] == "WH-SBY"
    assert baris[0]["legs"] and baris[0]["legs"][0]["from_warehouse_code"] == "WH-JKT"
    assert baris[0]["purchase_qty"] == 0

    # Filter Oli Timken: surplus Jakarta 1 unit, kebutuhan Surabaya 2 --
    # sebagian dikirim, sisanya tetap dibeli.
    r = klien.get("/api/transfer", headers=dunia["hDemo"],
                  params={"q": "Timken 58773"})
    baris = r.json()["items"]
    assert baris[0]["decision"] == "TRANSFER_SEBAGIAN", baris[0]["reason"]
    assert baris[0]["transfer_qty"] > 0 and baris[0]["purchase_qty"] > 0


def test_dokumen_transfer_demo_melewati_seluruh_tahap(klien, dunia):
    """
    Tab Dokumen tidak kosong, dan keempat tahapnya benar-benar terwakili.

    Cap waktunya ikut diperiksa: dokumen yang berstatus "dikirim" tetapi tidak
    punya shipped_at berarti statusnya ditulis langsung, bukan dilewati -- dan
    dokumen seperti itu tidak pernah menggerakkan stok gudang asalnya.
    """
    klien.post("/api/demo/reset", headers=dunia["hDemo"])

    r = klien.get("/api/transfers", headers=dunia["hDemo"])
    assert r.status_code == 200, r.text[:300]
    dokumen = r.json()["items"]
    # Empat dokumen skenario (satu per tahap) di atas arsip transfer setahun.
    assert r.json()["total"] > 200

    # Dokumen skenario = yang bukan arsip; alasan dan skornya dibekukan.
    dokumen = [d for d in dokumen
               if d["notes"] not in ("Arsip transfer", "Skenario cabang")]
    assert len(dokumen) == 4

    per_status = {d["status"]: d for d in dokumen}
    assert set(per_status) == {"draft", "approved", "in_transit", "completed"}
    assert per_status["draft"]["approved_at"] is None
    assert per_status["approved"]["approved_at"] is not None
    assert per_status["in_transit"]["shipped_at"] is not None
    assert per_status["completed"]["received_at"] is not None
    # Alasan dan skor dibekukan saat pengajuan; layar membacanya dari sini.
    assert all(d["reason"] and d["score"] for d in dokumen)


def test_transfer_yang_dikirim_benar_benar_mengurangi_gudang_asal(klien, dunia):
    """
    Dokumen "dalam perjalanan" bukan sekadar label.

    Barangnya sudah turun dari rak gudang asal dan belum sampai di gudang
    tujuan; ledger harus memuat transfer_out sebesar itu, dan saldo gudang asal
    harus cocok dengan riwayatnya sendiri.
    """
    import psycopg

    klien.post("/api/demo/reset", headers=dunia["hDemo"])
    cid = dunia["demo"]["company"]["id"]

    with psycopg.connect(f"{INDUK}/{NAMA_DB_UJI}") as k, k.cursor() as cur:
        cur.execute(
            """
            SELECT count(*), COALESCE(SUM(-quantity), 0)
              FROM stock_movements
             WHERE company_id = %s AND movement_type = 'transfer_out'
            """,
            (cid,),
        )
        jumlah, unit = cur.fetchone()
        # Dua dokumen skenario sudah meninggalkan gudang asal (satu dikirim,
        # satu diterima) ditambah ratusan pengiriman arsip.
        assert jumlah >= 2 and unit > 0

        cur.execute(
            """
            SELECT count(*) FROM stock_movements
             WHERE company_id = %s AND movement_type = 'transfer_in'
            """,
            (cid,),
        )
        assert cur.fetchone()[0] >= 1
