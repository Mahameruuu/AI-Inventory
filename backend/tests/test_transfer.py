# -*- coding: utf-8 -*-
"""
Uji Transfer Antar Gudang (app/transfer.py dan perakitannya di router).

    .venv/bin/python -m pytest backend/tests/test_transfer.py -q

SELURUHNYA TANPA BASIS DATA. Yang diuji di sini adalah rantai pemilihan
sumber, dan rantai itu memang tidak menyentuh basis data sama sekali: router
mengumpulkan keadaan tiap pasangan barang/gudang lebih dulu, lalu menyerahkan
kumpulan itu ke fungsi murni. Karena itu enam kasus yang diminta pada
spesifikasi dapat dijalankan dengan menyusun keadaannya langsung -- lebih
cepat, dan yang lebih penting, tanpa satu pun angka yang kebetulan benar
karena data contoh.

YANG DIJAGA DI SINI, dan seluruhnya adalah hal yang TIDAK akan menimbulkan
galat bila salah:

  * gudang yang sendirinya menipis tidak pernah menjadi sumber -- kesalahan
    yang hanya terlihat dua minggu kemudian sebagai gudang kedua yang kosong;
  * surplus tidak pernah menembus titik pesan efektif gudang asal;
  * kuantitas selalu bilangan bulat, dibulatkan ke arah yang tidak pernah
    menjanjikan barang yang tidak ada;
  * fuzzy tidak pernah menggantikan cocok pasti, dan tidak pernah menang atas
    cocok pasti pada keadaan lain yang sama;
  * kekurangan yang tidak tertutup transfer JATUH KE PEMBELIAN, bukan hilang.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import transfer as tf  # noqa: E402
from app.routers.transfer import _kandidat_mentah, _rekomendasi  # noqa: E402


# ==========================================================================
# Penyusun keadaan
# ==========================================================================
#
# Bentuk dict-nya sama persis dengan yang dikembalikan router._keadaan(), yaitu
# jawaban mesin keputusan untuk satu pasangan barang/gudang. Ditulis sebagai
# pembantu supaya tiap uji hanya menyebut angka yang sedang diperiksanya.

def keadaan(*, item_id=1, warehouse_id=1, sku="SKU-1", nama="Gear Pump ABB 29805",
            satuan="PCS", kode="WH-1", tersedia=0, titik_efektif=0,
            status="AMAN", butuh=None):
    return {
        "item_id": item_id,
        "warehouse_id": warehouse_id,
        "sku": sku,
        "item_name": nama,
        "unit_code": satuan,
        "warehouse_code": kode,
        "warehouse_name": f"Gudang {kode}",
        "available_stock_int": tersedia,
        "current_stock_int": tersedia,
        "effective_reorder_point_int": titik_efektif,
        "safety_stock_int": 0,
        "lead_time_days_int": 7,
        "days_of_cover_int": 3,
        "action_status": status,
        "action_status_label": status,
        "priority": "SEDANG",
        "recommended_order_qty": butuh,
        "reorder_reason": "",
    }


def gudang(id_, kode, lat=None, lon=None, hari=None, aktif=True):
    return {"id": id_, "code": kode, "name": f"Gudang {kode}", "is_active": aktif,
            "latitude": lat, "longitude": lon, "transfer_lead_time_days": hari}


# Tiga gudang di kota yang benar-benar berjauhan, supaya komponen jarak pada
# uji di bawah adalah angka yang dapat diperiksa sendiri, bukan konstanta yang
# dipilih agar hasilnya cocok.
SURABAYA = (-7.2575, 112.7521)
SIDOARJO = (-7.4478, 112.7183)     # ~21 km dari Surabaya
JAKARTA = (-6.2088, 106.8456)      # ~663 km dari Surabaya

GUDANG = {
    1: gudang(1, "WH-SBY", *SURABAYA),
    2: gudang(2, "WH-SDA", *SIDOARJO),
    3: gudang(3, "WH-JKT", *JAKARTA),
}


def rekomendasi(tujuan, sumber, *, fuzzy=False, ambang=tf.TRANSFER_KEMIRIPAN_MIN,
                matriks=None, gudang_=None):
    return _rekomendasi(tujuan=tujuan, semua=[tujuan, *sumber],
                        gudang=gudang_ or GUDANG, matriks=matriks or {},
                        fuzzy=fuzzy, ambang=ambang, lang="id")


# ==========================================================================
# Enam kasus yang diminta spesifikasi
# ==========================================================================

def test_gudang_terdekat_punya_stok_cukup():
    """
    Sidoarjo 21 km dengan surplus berlimpah, Jakarta 663 km dengan surplus yang
    sama. Keduanya sanggup menutup seluruh kebutuhan, jadi yang membedakan
    tinggal jarak -- dan satu kiriman dari Sidoarjo harus menang telak.
    """
    tujuan = keadaan(warehouse_id=1, kode="WH-SBY", tersedia=1,
                     titik_efektif=12, status="PERLU_REORDER", butuh=10)
    dekat = keadaan(warehouse_id=2, kode="WH-SDA", tersedia=60, titik_efektif=10)
    jauh = keadaan(warehouse_id=3, kode="WH-JKT", tersedia=60, titik_efektif=10)

    hasil = rekomendasi(tujuan, [dekat, jauh])

    assert hasil["decision"] == tf.TRANSFER
    assert hasil["purchase_qty"] == 0
    assert len(hasil["legs"]) == 1
    satu = hasil["legs"][0]
    assert satu["from_warehouse_code"] == "WH-SDA"
    assert satu["transfer_qty"] == 10
    # Jaraknya benar-benar dihitung, bukan diisi nol karena tidak diketahui.
    assert 15 < satu["distance_km"] < 30
    # Skor kandidat yang kalah tetap terbit: yang membaca layar berhak tahu
    # ada pilihan kedua bila Sidoarjo menolak mengirim hari itu.
    assert [k["from_warehouse_code"] for k in hasil["candidates"]] == ["WH-SDA", "WH-JKT"]
    assert hasil["candidates"][0]["score"] > hasil["candidates"][1]["score"]


def test_gudang_terdekat_tidak_cukup_kalah_dari_gudang_jauh_yang_cukup():
    """
    Yang paling dekat hanya punya 2 dari 10 yang dibutuhkan; yang jauh sanggup
    seluruhnya. Kecukupan berbobot lebih besar daripada jarak justru untuk
    keadaan ini: satu kiriman dari Jakarta lebih murah daripada satu kiriman
    dari Sidoarjo yang tetap menyisakan delapan unit untuk dibeli.

    Sidoarjo TIDAK dibuang -- ia turun ke urutan kedua, dan tetap kebagian
    alokasi bila Jakarta ternyata tidak cukup.
    """
    tujuan = keadaan(warehouse_id=1, kode="WH-SBY", tersedia=1,
                     titik_efektif=12, status="PERLU_REORDER", butuh=10)
    dekat = keadaan(warehouse_id=2, kode="WH-SDA", tersedia=12, titik_efektif=10)
    jauh = keadaan(warehouse_id=3, kode="WH-JKT", tersedia=40, titik_efektif=10)

    hasil = rekomendasi(tujuan, [dekat, jauh])

    assert hasil["decision"] == tf.TRANSFER
    assert [l["from_warehouse_code"] for l in hasil["legs"]] == ["WH-JKT"]
    assert hasil["legs"][0]["transfer_qty"] == 10
    assert hasil["purchase_qty"] == 0
    # Yang dekat tetap tercatat sebagai kandidat yang sah, hanya kalah skor.
    kandidat = {k["from_warehouse_code"]: k for k in hasil["candidates"]}
    assert kandidat["WH-SDA"]["eligible"] is True
    assert kandidat["WH-SDA"]["surplus"] == 2
    assert kandidat["WH-JKT"]["score"] > kandidat["WH-SDA"]["score"]


def test_gudang_jauh_punya_stok_cukup_dan_menjadi_satu_satunya_sumber():
    """
    Satu-satunya gudang yang punya barangnya berada 663 km jauhnya. Jarak
    MENURUNKAN skornya, tetapi tidak pernah membatalkan kelayakannya: transfer
    jauh tetap lebih baik daripada membeli barang yang sudah dimiliki
    perusahaan ini.
    """
    tujuan = keadaan(warehouse_id=1, kode="WH-SBY", tersedia=0,
                     titik_efektif=8, status="RISIKO_STOCKOUT", butuh=6)
    jauh = keadaan(warehouse_id=3, kode="WH-JKT", tersedia=50, titik_efektif=10)

    hasil = rekomendasi(tujuan, [jauh])

    assert hasil["decision"] == tf.TRANSFER
    assert hasil["legs"][0]["from_warehouse_code"] == "WH-JKT"
    assert hasil["legs"][0]["transfer_qty"] == 6
    assert hasil["purchase_qty"] == 0
    # Skornya turun karena jarak, bukan karena kecukupan: komponennya dipisah
    # supaya perbedaan itu terbaca, bukan tersembunyi di balik satu angka.
    k = hasil["candidates"][0]
    assert k["components"]["sufficiency"] == 1.0
    assert k["components"]["distance"] < 0.5


def test_beberapa_gudang_digabung_ketika_tidak_ada_yang_cukup_sendirian():
    """
    Butuh 10; tidak satu pun gudang punya 10. Mesin BOLEH menggabungkan, dan
    urutan pengambilannya mengikuti peringkat: yang terbaik dikuras dulu,
    sisanya turun ke berikutnya.
    """
    tujuan = keadaan(warehouse_id=1, kode="WH-SBY", tersedia=0,
                     titik_efektif=12, status="RISIKO_STOCKOUT", butuh=10)
    a = keadaan(warehouse_id=2, kode="WH-SDA", tersedia=16, titik_efektif=10)  # surplus 6
    b = keadaan(warehouse_id=3, kode="WH-JKT", tersedia=15, titik_efektif=10)  # surplus 5

    hasil = rekomendasi(tujuan, [a, b])

    assert hasil["decision"] == tf.TRANSFER
    assert len(hasil["legs"]) == 2
    assert sum(l["transfer_qty"] for l in hasil["legs"]) == 10
    # Kandidat teratas dikuras lebih dulu; yang kedua hanya menutup sisanya --
    # bukan seluruh surplusnya.
    assert hasil["legs"][0]["transfer_qty"] == 6
    assert hasil["legs"][1]["transfer_qty"] == 4
    assert hasil["purchase_qty"] == 0
    assert "2 gudang" in hasil["reason"]


def test_semua_gudang_kekurangan_maka_jatuh_ke_pembelian():
    """
    Setiap gudang punya barangnya, dan setiap gudang sedang menipis. Tidak satu
    pun boleh menjadi sumber: memindahkan stok dari gudang yang sendirinya
    sudah menyentuh titik pesan hanya memindahkan masalahnya, dan barangnya
    sudah terlanjur di jalan saat itu ketahuan.

    Kalimatnya WAJIB membedakan keadaan ini dari "tidak ada gudang lain yang
    punya barangnya": yang pertama adalah kabar bahwa seluruh jaringan sedang
    menipis, dan itu jauh lebih penting.
    """
    tujuan = keadaan(warehouse_id=1, kode="WH-SBY", tersedia=1,
                     titik_efektif=12, status="PERLU_REORDER", butuh=10)
    a = keadaan(warehouse_id=2, kode="WH-SDA", tersedia=3, titik_efektif=10,
                status="PERLU_REORDER")
    b = keadaan(warehouse_id=3, kode="WH-JKT", tersedia=0, titik_efektif=10,
                status="RISIKO_STOCKOUT")

    hasil = rekomendasi(tujuan, [a, b])

    assert hasil["decision"] == tf.PEMBELIAN
    assert hasil["legs"] == []
    assert hasil["transfer_qty"] == 0
    # Seluruh kebutuhan berpindah ke pembelian, tidak satu unit pun hilang.
    assert hasil["purchase_qty"] == 10
    assert len(hasil["rejected"]) == 2
    assert {k["rejected_reason"] for k in hasil["rejected"]} == {tf.TOLAK_TIDAK_AMAN}
    assert "tidak satu pun berlebih" in hasil["reason"]


def test_tanpa_kandidat_sama_sekali_jatuh_ke_pembelian_dengan_alasan_berbeda():
    """
    Barangnya hanya ada di gudang ini. Berujung pada pembelian sama seperti uji
    di atas, tetapi kalimatnya harus menyebut sebab yang benar -- dan itu satu-
    satunya perbedaan yang dapat ditindaklanjuti pembacanya.
    """
    tujuan = keadaan(warehouse_id=1, kode="WH-SBY", tersedia=1,
                     titik_efektif=12, status="PERLU_REORDER", butuh=7)

    hasil = rekomendasi(tujuan, [])

    assert hasil["decision"] == tf.PEMBELIAN
    assert hasil["purchase_qty"] == 7
    assert hasil["candidates"] == [] and hasil["rejected"] == []
    assert "Tidak ada gudang lain" in hasil["reason"]


# ==========================================================================
# Transfer sebagian: sisanya tidak boleh hilang
# ==========================================================================

def test_transfer_sebagian_menyisakan_pembelian_yang_tepat():
    """
    Yang paling mudah rusak tanpa terlihat: sisa yang tidak tertutup transfer
    diam-diam dibulatkan menjadi nol, dan orang pengadaan tidak pernah memesan
    tiga unit yang tetap kurang.
    """
    tujuan = keadaan(warehouse_id=1, kode="WH-SBY", tersedia=0,
                     titik_efektif=12, status="RISIKO_STOCKOUT", butuh=10)
    a = keadaan(warehouse_id=2, kode="WH-SDA", tersedia=17, titik_efektif=10)

    hasil = rekomendasi(tujuan, [a])

    assert hasil["decision"] == tf.TRANSFER_SEBAGIAN
    assert hasil["transfer_qty"] == 7
    assert hasil["purchase_qty"] == 3
    assert hasil["transfer_qty"] + hasil["purchase_qty"] == hasil["need_qty"]


def test_kebutuhan_belum_terhitung_tidak_menghasilkan_rencana_transfer():
    """
    Histori belum cukup berarti kekurangannya BELUM DAPAT DIHITUNG, bukan nol.
    Menyusun rencana transfer di atas angka yang tidak ada berarti memindahkan
    barang atas dasar tebakan.
    """
    hasil = tf.rencana(kebutuhan=None, kandidat=[{"surplus": 99, "score": 90}])
    assert hasil["decision"] == tf.PEMBELIAN
    assert hasil["legs"] == []
    assert hasil["need_qty"] is None
    assert hasil["purchase_qty"] is None


# ==========================================================================
# Surplus dan kelayakan sumber
# ==========================================================================

def test_surplus_diukur_dari_titik_pesan_efektif_bukan_dari_stok_fisik():
    # 40 tersedia, titik pesan efektif 25 -> hanya 15 yang benar-benar berlebih.
    assert tf.surplus_gudang(40, 25) == 15
    # Stok di bawah titik pesannya sendiri tidak punya surplus, bukan surplus negatif.
    assert tf.surplus_gudang(20, 25) == 0


def test_surplus_dibulatkan_ke_bawah():
    """
    Surplus 2,9 berarti DUA unit yang benar-benar dapat dinaikkan ke truk.
    Membulatkannya ke atas berarti menjanjikan barang yang tidak ada, dan
    gudang asal menembus titik pesannya sendiri karena pembulatan.
    """
    assert tf.surplus_gudang(27.9, 25) == 2
    assert tf.surplus_gudang(25.99, 25) == 0


def test_kebutuhan_dibulatkan_ke_atas():
    """Arah sebaliknya, dan alasannya juga sebaliknya: 7,2 unit yang kurang
    tidak tertutup oleh tujuh unit."""
    assert tf.bulat_atas(7.2) == 8
    assert tf.rencana(kebutuhan=7.2, kandidat=[])["need_qty"] == 8


@pytest.mark.parametrize("status,harapan", [
    ("AMAN", None),
    ("PERLU_REORDER", tf.TOLAK_TIDAK_AMAN),
    ("RISIKO_STOCKOUT", tf.TOLAK_TIDAK_AMAN),
])
def test_hanya_gudang_berstatus_aman_yang_boleh_menjadi_sumber(status, harapan):
    assert tf.kelayakan_sumber(status_aksi=status, aktif=True, surplus=50) == harapan


def test_gudang_nonaktif_ditolak_dengan_sebabnya_sendiri():
    """
    Gudang nonaktif yang KEBETULAN juga kekurangan harus berbunyi "nonaktif":
    itulah yang dapat ditindaklanjuti, sedangkan "sedang menipis" mengirim
    pembacanya memeriksa stok gudang yang sudah tidak dipakai lagi.
    """
    assert tf.kelayakan_sumber(status_aksi="PERLU_REORDER", aktif=False,
                               surplus=0) == tf.TOLAK_NONAKTIF


def test_gudang_nonaktif_tidak_pernah_masuk_alokasi():
    tujuan = keadaan(warehouse_id=1, kode="WH-SBY", tersedia=0,
                     titik_efektif=10, status="RISIKO_STOCKOUT", butuh=5)
    sumber = keadaan(warehouse_id=3, kode="WH-JKT", tersedia=90, titik_efektif=10)
    mati = {**GUDANG, 3: gudang(3, "WH-JKT", *JAKARTA, aktif=False)}

    hasil = rekomendasi(tujuan, [sumber], gudang_=mati)

    assert hasil["decision"] == tf.PEMBELIAN
    assert hasil["rejected"][0]["rejected_reason"] == tf.TOLAK_NONAKTIF


# ==========================================================================
# Kuantitas: bilangan bulat, tanpa kecuali
# ==========================================================================

def test_seluruh_kuantitas_pada_jawaban_adalah_bilangan_bulat():
    """
    Bukan soal tampilan. Yang dipindahkan barang fisik, dan satu angka
    berdesimal yang lolos ke dokumen transfer menjadi perintah yang tidak dapat
    dijalankan siapa pun di gudang.
    """
    tujuan = keadaan(warehouse_id=1, kode="WH-SBY", tersedia=0,
                     titik_efektif=12.4, status="RISIKO_STOCKOUT", butuh=9.3)
    a = keadaan(warehouse_id=2, kode="WH-SDA", tersedia=16.8, titik_efektif=10.2)
    b = keadaan(warehouse_id=3, kode="WH-JKT", tersedia=20.9, titik_efektif=10.5)

    hasil = rekomendasi(tujuan, [a, b])

    for nama in ("need_qty", "transfer_qty", "purchase_qty"):
        assert isinstance(hasil[nama], int), nama
    for leg in hasil["legs"]:
        assert isinstance(leg["transfer_qty"], int)
        assert isinstance(leg["surplus"], int)
    for k in hasil["candidates"]:
        assert isinstance(k["score"], int)


# ==========================================================================
# Pencocokan fuzzy
# ==========================================================================

def test_urutan_kata_berbeda_tetap_barang_yang_sama():
    assert tf.kemiripan("Roller Bearing SKF 6205", "Bearing Roller SKF 6205") == 1.0
    assert tf.cocok_fuzzy("Filter Oli ABB 37613", "filter  oli abb-37613")[0] is True


def test_merek_berbeda_bukan_barang_yang_sama():
    """
    Data produksi penyewa ini memuat "Gear Pump ABB 29805" dan "Gear Pump Bosch
    93252" -- dua pompa dari dua pabrikan, dan separuh namanya sama. Ambang
    0,88 harus menolaknya; yang lolos hanyalah perbedaan ejaan dan tanda baca.
    """
    cocok, skor = tf.cocok_fuzzy("Gear Pump ABB 29805", "Gear Pump Bosch 93252")
    assert cocok is False
    assert skor < tf.TRANSFER_KEMIRIPAN_MIN


def test_fuzzy_mati_secara_bawaan_pada_perakitan_kandidat():
    tujuan = keadaan(item_id=1, warehouse_id=1, nama="Filter Oli ABB 37613")
    kembar = keadaan(item_id=99, warehouse_id=2, kode="WH-SDA",
                     sku="SKU-99", nama="Filter Oli ABB-37613")

    assert _kandidat_mentah(tujuan, [kembar], fuzzy=False, ambang=0.88) == []
    hidup = _kandidat_mentah(tujuan, [kembar], fuzzy=True, ambang=0.88)
    assert [b[1] for b in hidup] == [tf.COCOK_FUZZY]


def test_cocok_pasti_tidak_pernah_digantikan_fuzzy_di_gudang_yang_sama():
    """
    Batas yang diminta spesifikasi secara harfiah: fuzzy tidak boleh menjadi
    pengganti nomor barang yang sudah pasti cocok. Gudang yang sudah punya
    barang ini menurut item_id-nya tidak pernah ikut dicocokkan namanya, walau
    ia juga menyimpan barang lain yang namanya mirip.
    """
    tujuan = keadaan(item_id=1, warehouse_id=1, nama="Filter Oli ABB 37613")
    pasti = keadaan(item_id=1, warehouse_id=2, kode="WH-SDA",
                    nama="Filter Oli ABB 37613")
    kembar = keadaan(item_id=99, warehouse_id=2, kode="WH-SDA", sku="SKU-99",
                     nama="Filter Oli ABB-37613")

    hasil = _kandidat_mentah(tujuan, [pasti, kembar], fuzzy=True, ambang=0.88)

    assert len(hasil) == 1
    baris, dasar, skor = hasil[0]
    assert dasar == tf.COCOK_SKU and baris["item_id"] == 1 and skor == 1.0


def test_kandidat_fuzzy_kalah_dari_cocok_pasti_pada_keadaan_lain_yang_sama():
    """
    Kemiripan nama MENGALIKAN skor, bukan menambah komponen kelima. Dua gudang
    dengan surplus, jarak, dan waktu tempuh yang sama persis harus berakhir
    dengan yang cocok pasti di atas -- keraguan tidak boleh gratis.
    """
    pasti = tf.skor_kandidat(kebutuhan=10, surplus=20, tersedia_sumber=30,
                             jarak_km=50, lead_time_hari=2, kemiripan_nama=1.0)
    ragu = tf.skor_kandidat(kebutuhan=10, surplus=20, tersedia_sumber=30,
                            jarak_km=50, lead_time_hari=2, kemiripan_nama=0.9)
    assert pasti["score"] > ragu["score"]


def test_satuan_berbeda_ditolak_walau_namanya_mirip():
    """
    Satu barang tercatat dalam LTR di satu gudang dan PCS di gudang lain berarti
    jumlahnya tidak dapat dibandingkan sama sekali. Mengirim "8" tanpa tahu
    delapan apa adalah kesalahan yang tidak akan pernah terbit sebagai galat.
    """
    tujuan = keadaan(item_id=1, warehouse_id=1, nama="Oli Hidrolik Shell 36011",
                     satuan="LTR", tersedia=0, titik_efektif=10,
                     status="RISIKO_STOCKOUT", butuh=8)
    kembar = keadaan(item_id=99, warehouse_id=2, kode="WH-SDA", sku="SKU-99",
                     nama="Oli Hidrolik Shell-36011", satuan="PCS",
                     tersedia=90, titik_efektif=10)

    hasil = rekomendasi(tujuan, [kembar], fuzzy=True)

    assert hasil["decision"] == tf.PEMBELIAN
    assert hasil["rejected"][0]["rejected_reason"] == tf.TOLAK_SATUAN_BEDA


def test_baris_fuzzy_membawa_skor_kemiripannya_sendiri():
    """Barisnya harus dapat ditolak orang gudang SEBELUM barang bergerak, dan
    itu hanya mungkin bila angkanya ikut sampai ke layar."""
    tujuan = keadaan(item_id=1, warehouse_id=1, nama="Filter Oli ABB 37613",
                     tersedia=0, titik_efektif=10, status="RISIKO_STOCKOUT",
                     butuh=5)
    kembar = keadaan(item_id=99, warehouse_id=2, kode="WH-SDA", sku="SKU-99",
                     nama="Filter Oli ABB-37613", tersedia=90, titik_efektif=10)

    hasil = rekomendasi(tujuan, [kembar], fuzzy=True)

    leg = hasil["legs"][0]
    assert leg["match_type"] == tf.COCOK_FUZZY
    assert leg["match_similarity"] >= tf.TRANSFER_KEMIRIPAN_MIN
    assert "kemiripan nama" in leg["why"]
    # Barang yang DIKIRIM adalah milik gudang asal; kebutuhan yang ditutupnya
    # milik barang lain, dan keduanya harus tetap dapat dibedakan.
    assert leg["item_id"] == 99 and hasil["item_id"] == 1


# ==========================================================================
# Jarak
# ==========================================================================

def test_jarak_yang_ditetapkan_tangan_mengalahkan_haversine():
    """
    Garis lurus Surabaya-Jakarta 663 km; yang ditempuh truk lebih jauh. Selama
    ada baris yang menyatakannya, angka itulah yang dipakai -- bukan yang
    diukur di peta.
    """
    km, dasar = tf.jarak_antar(jarak_tetap=780,
                               asal=GUDANG[1], tujuan=GUDANG[3])
    assert (km, dasar) == (780.0, "matrix")

    km, dasar = tf.jarak_antar(asal=GUDANG[1], tujuan=GUDANG[3])
    assert dasar == "haversine" and 650 < km < 675


def test_jarak_tidak_diketahui_dinilai_netral_bukan_terbaik():
    """
    Nol berarti "gudang yang sama persis letaknya", yaitu skor jarak tertinggi.
    Memakainya sebagai pengganti "tidak tahu" akan membuat gudang yang justru
    tidak diketahui letaknya memenangkan setiap peringkat.
    """
    tanpa = tf.skor_kandidat(kebutuhan=10, surplus=20, tersedia_sumber=30,
                             jarak_km=None)
    dekat = tf.skor_kandidat(kebutuhan=10, surplus=20, tersedia_sumber=30,
                             jarak_km=5)
    jauh = tf.skor_kandidat(kebutuhan=10, surplus=20, tersedia_sumber=30,
                            jarak_km=990)
    assert tanpa["components"]["distance"] == tf.NETRAL
    assert jauh["score"] < tanpa["score"] < dekat["score"]


def test_koordinat_kosong_tidak_menghasilkan_jarak():
    assert tf.jarak_haversine(None, 112.0, -7.0, 112.0) is None
    assert tf.jarak_haversine(-7.0, 112.0, -6.2, None) is None


def test_waktu_tempuh_per_pasangan_mengalahkan_angka_khas_gudang():
    """
    Gudang tujuan menyatakan 9 hari sebagai angka khasnya, tetapi pasangan
    Sidoarjo->Surabaya punya barisnya sendiri: 1 hari. Yang lebih spesifik
    menang, dan itu yang membuat matriks berguna sama sekali.
    """
    tujuan = keadaan(warehouse_id=1, kode="WH-SBY", tersedia=0,
                     titik_efektif=10, status="RISIKO_STOCKOUT", butuh=5)
    dekat = keadaan(warehouse_id=2, kode="WH-SDA", tersedia=90, titik_efektif=10)
    g = {**GUDANG, 1: gudang(1, "WH-SBY", *SURABAYA, hari=9)}

    hasil = rekomendasi(tujuan, [dekat], gudang_=g,
                        matriks={(2, 1): {"distance_km": 25, "lead_time_days": 1}})

    assert hasil["legs"][0]["lead_time_days"] == 1
    assert hasil["legs"][0]["distance_km"] == 25.0
    assert hasil["legs"][0]["distance_basis"] == "matrix"


# ==========================================================================
# Skor: bobot, batas, dan keterulangan
# ==========================================================================

def test_bobot_berjumlah_satu_sehingga_skor_selalu_di_dalam_nol_seratus():
    from app.config import (TRANSFER_BOBOT_JARAK, TRANSFER_BOBOT_KECUKUPAN,
                            TRANSFER_BOBOT_SURPLUS, TRANSFER_BOBOT_WAKTU)
    total = (TRANSFER_BOBOT_KECUKUPAN + TRANSFER_BOBOT_SURPLUS
             + TRANSFER_BOBOT_JARAK + TRANSFER_BOBOT_WAKTU)
    assert total == pytest.approx(1.0)

    sempurna = tf.skor_kandidat(kebutuhan=1, surplus=99, tersedia_sumber=99,
                                jarak_km=0, lead_time_hari=0)
    terburuk = tf.skor_kandidat(kebutuhan=99, surplus=1, tersedia_sumber=10_000,
                                jarak_km=99_999, lead_time_hari=99_999)
    assert sempurna["score"] == 100
    assert 0 <= terburuk["score"] < 5


def test_skor_menerbitkan_komponen_dan_bobotnya_sekaligus():
    """
    Skor tunggal tidak dapat dibantah siapa pun. Yang membuat peringkat ini
    dapat diperiksa adalah keempat komponennya berdampingan dengan bobot yang
    dipakai mengalikannya.
    """
    k = tf.skor_kandidat(kebutuhan=10, surplus=5, tersedia_sumber=20,
                         jarak_km=100, lead_time_hari=3)
    assert set(k["components"]) == {"sufficiency", "surplus_ratio", "distance",
                                    "lead_time", "name_similarity"}
    assert set(k["weights"]) == {"sufficiency", "surplus_ratio", "distance",
                                "lead_time"}
    assert k["components"]["sufficiency"] == 0.5


def test_urutan_kandidat_berskor_sama_tetap_sama_di_setiap_permintaan():
    """
    Daftar yang berubah urutannya tanpa ada data yang berubah tidak dapat
    dipercaya siapa pun. Pemutus serinya karena itu deterministik sampai ke
    kode gudang.
    """
    dasar = {"score": 70, "surplus": 10, "distance_km": 50}
    a = {**dasar, "from_warehouse_code": "WH-B"}
    b = {**dasar, "from_warehouse_code": "WH-A"}
    assert [k["from_warehouse_code"] for k in sorted([a, b], key=tf.urutan_kandidat)] \
        == ["WH-A", "WH-B"]
    # dan kebalikannya menghasilkan urutan yang sama
    assert [k["from_warehouse_code"] for k in sorted([b, a], key=tf.urutan_kandidat)] \
        == ["WH-A", "WH-B"]


def test_kandidat_tanpa_jarak_diurutkan_di_belakang_yang_diketahui():
    dekat = {"score": 70, "surplus": 10, "distance_km": 50, "from_warehouse_code": "A"}
    entah = {"score": 70, "surplus": 10, "distance_km": None, "from_warehouse_code": "B"}
    assert sorted([entah, dekat], key=tf.urutan_kandidat)[0] is dekat


# ==========================================================================
# Alokasi
# ==========================================================================

def test_alokasi_berhenti_begitu_kebutuhan_tertutup():
    kandidat = [{"surplus": 8, "from_warehouse_code": "A"},
                {"surplus": 8, "from_warehouse_code": "B"},
                {"surplus": 8, "from_warehouse_code": "C"}]
    legs = tf.alokasi(10, kandidat)
    assert [l["from_warehouse_code"] for l in legs] == ["A", "B"]
    assert [l["transfer_qty"] for l in legs] == [8, 2]


def test_alokasi_melewati_kandidat_bersurplus_nol_tanpa_membuat_baris():
    """Dokumen transfer berjumlah nol bukan dokumen."""
    legs = tf.alokasi(5, [{"surplus": 0, "from_warehouse_code": "A"},
                          {"surplus": 5, "from_warehouse_code": "B"}])
    assert [l["from_warehouse_code"] for l in legs] == ["B"]


def test_alokasi_tidak_pernah_melebihi_surplus_satu_gudang():
    legs = tf.alokasi(100, [{"surplus": 3, "from_warehouse_code": "A"}])
    assert legs[0]["transfer_qty"] == 3
    assert sum(l["transfer_qty"] for l in legs) == 3


# ==========================================================================
# Alur status dokumen
# ==========================================================================

@pytest.mark.parametrize("dari,ke", [
    (tf.DRAFT, tf.APPROVED), (tf.DRAFT, tf.CANCELLED),
    (tf.APPROVED, tf.IN_TRANSIT), (tf.APPROVED, tf.CANCELLED),
    (tf.IN_TRANSIT, tf.COMPLETED),
])
def test_perpindahan_status_yang_sah(dari, ke):
    assert tf.boleh_pindah(dari, ke) is True


@pytest.mark.parametrize("dari,ke", [
    # Lompatan yang menambah stok di tujuan tanpa pernah menguranginya di asal.
    (tf.DRAFT, tf.COMPLETED),
    (tf.DRAFT, tf.IN_TRANSIT),
    (tf.APPROVED, tf.COMPLETED),
    # Barang yang sudah di jalan tidak dibatalkan; itu transfer balik, dan itu
    # dokumen tersendiri.
    (tf.IN_TRANSIT, tf.CANCELLED),
    # Ujung jalan.
    (tf.COMPLETED, tf.IN_TRANSIT),
    (tf.CANCELLED, tf.APPROVED),
])
def test_perpindahan_status_yang_ditolak(dari, ke):
    assert tf.boleh_pindah(dari, ke) is False


def test_setiap_status_punya_label_dua_bahasa():
    for s in tf.STATUS:
        for bahasa in ("id", "en"):
            label = tf.label_status(s, bahasa)
            # Kunci mentah yang bocor ke layar berarti terjemahannya tertinggal.
            assert label and not label.startswith("tf.")


def test_setiap_keputusan_dan_alasan_penolakan_punya_label_dua_bahasa():
    for k in tf.KEPUTUSAN:
        for bahasa in ("id", "en"):
            assert not tf.label_keputusan(k, bahasa).startswith("tf.")
    for a in (tf.TOLAK_TIDAK_AMAN, tf.TOLAK_TANPA_SURPLUS, tf.TOLAK_NONAKTIF,
              tf.TOLAK_SATUAN_BEDA, tf.TOLAK_MIRIP_KURANG):
        for bahasa in ("id", "en"):
            assert not tf.label_penolakan(a, bahasa).startswith("tf.")
