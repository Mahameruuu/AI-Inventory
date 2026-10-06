# -*- coding: utf-8 -*-
"""
Ringkasan untuk halaman Dashboard.

TIGA PERTANYAAN, DAN HANYA TIGA. Dasbor ini dirapikan pada 2 September 2026
karena versi sebelumnya menjawab pertanyaan yang tidak diajukan siapa pun:
delapan kartu angka, dua di antaranya mengulang isi kartu lain, ditambah dua
gauge "kesiapan" yang menghitung persentase barang aktif -- angka yang tidak
membuat seorang pun mengambil keputusan apa pun. Yang tersisa hanya yang
menjawab salah satu dari:

    1. Bagaimana kondisi persediaan sekarang?
    2. Apa yang membutuhkan perhatian?
    3. Apa yang diprakirakan akan terjadi?

SEMUA ANGKA "PERLU PERHATIAN" DAN "KE DEPAN" DATANG DARI MESIN PEMESANAN
ULANG, bukan dihitung ulang di sini. Sebelumnya dasbor punya definisi "stok
menipis" miliknya sendiri -- `quantity <= COALESCE(NULLIF(reorder_point,0),
minimum_stock)` -- sementara halaman Pemesanan Ulang memakai TITIK PESAN
EFEKTIF yang memperhitungkan laju pemakaian, lead time, dan safety stock.
Dua definisi berarti dasbor dapat berbunyi "3 barang menipis" sementara
halaman di sebelahnya menyebut lima, dan tidak ada satu pun galat yang
menunjukkan mana yang benar. Kini dasbor MEMANGGIL `reorder.daftar_reorder()`
dan hanya meringkas jawabannya.

Biayanya sudah diukur: dua puluh pasangan barang/gudang selesai dalam 0,3
detik, dan mesinnya sendiri menjepit diri pada `reorder.BATAS_BARIS`.

Nilai persediaan dihitung dari items.unit_price (harga referensi master),
BUKAN dari harga penerimaan sebenarnya. Metode valuasi (FIFO / rata-rata
bergerak) belum menjadi lingkup sistem ini, jadi dasarnya dinyatakan terbuka
lewat field `value_basis` supaya angkanya tidak disalahartikan.
"""

from fastapi import APIRouter, Query

from .. import decision, i18n
from ..db import readonly
from . import reorder as ro

router = APIRouter(tags=["dashboard"])

# Sebanyak-banyaknya baris pada tabel "Perlu perhatian". Dasbor bukan daftar
# kerja: yang dituju adalah membuat pembacanya tahu ADA apa, lalu menyerahkan
# penanganannya ke halaman Pemesanan Ulang yang memang dibuat untuk itu.
BATAS_PERHATIAN = 6


@router.get("/api/dashboard")
def dashboard(
    lang: str = Query(i18n.BAHASA_BAWAAN,
                      description="Bahasa kalimat temuan: id atau en."),
) -> dict:
    lang = i18n.normalisasi(lang)

    # ---------- 1. kondisi sekarang ----------
    #
    # SATU POPULASI UNTUK SELURUH HALAMAN: barang aktif di gudang aktif.
    # Sebelumnya ketiga blok di bawah menghitung atas tiga himpunan yang
    # berbeda -- "Total SKU" hanya barang aktif, "Total Stok" seluruh baris
    # persediaan tanpa kecuali, "Stok per Gudang" hanya gudang aktif tetapi
    # tetap memuat barang nonaktif, dan mesin pemesanan ulang (yang mengisi
    # kartu "Perlu Pesan Ulang") hanya barang aktif di gudang aktif. Empat
    # kartu berdampingan yang menjumlahkan katalog yang berbeda-beda; satu
    # barang dinonaktifkan dan Total Stok berhenti sama dengan jumlah Stok per
    # Gudang, tanpa satu pun galat yang menunjukkannya.
    #
    # Barang nonaktif memang tidak hilang dari gudang, tetapi ia juga tidak
    # ikut satu pun keputusan di halaman ini -- dan dasbor menjawab pertanyaan
    # tentang persediaan yang dikelola, bukan tentang isi rak seluruhnya.
    # Laporan persediaan penuh sudah punya halamannya sendiri.
    with readonly() as cur:
        cur.execute(
            """
            SELECT (SELECT count(*) FROM warehouses WHERE is_active) AS warehouses,
                   (SELECT count(*) FROM items WHERE is_active)      AS items,
                   COALESCE(SUM(inv.quantity), 0)                    AS stock,
                   COALESCE(SUM(inv.quantity * it.unit_price), 0)    AS value
              FROM inventory inv
              JOIN items it      ON it.id = inv.item_id
              JOIN warehouses w  ON w.id = inv.warehouse_id
             WHERE it.is_active AND w.is_active
            """
        )
        kondisi = dict(cur.fetchone())
        # Satuan gudang diskrit: yang sampai ke layar bilangan bulat, satu
        # aturan pembulatan yang sama dengan seluruh modul (decision.bulat).
        kondisi["stock"] = decision.bulat(kondisi["stock"]) or 0

        # Penyaringan barang aktif ada di ON, bukan di WHERE: gudang aktif yang
        # belum punya stok sama sekali tetap harus muncul sebagai baris nol,
        # dan memindahkannya ke WHERE akan menghapusnya dari daftar.
        cur.execute(
            """
            SELECT w.code, w.name,
                   COALESCE(SUM(inv.quantity), 0)                  AS total_stock,
                   COALESCE(SUM(inv.quantity * it.unit_price), 0)  AS stock_value
              FROM warehouses w
              LEFT JOIN items it      ON it.is_active
              LEFT JOIN inventory inv ON inv.warehouse_id = w.id
                                     AND inv.item_id = it.id
             WHERE w.is_active
             GROUP BY w.id, w.code, w.name
             ORDER BY w.code
            """
        )
        per_gudang = [{**dict(r), "total_stock": decision.bulat(r["total_stock"]) or 0}
                      for r in cur.fetchall()]

    # ---------- 2 & 3. perhatian dan kebutuhan ke depan ----------
    # Satu panggilan, dua bagian layar. Memanggilnya dua kali berarti menjalankan
    # rantai prakiraan dua kali untuk jawaban yang sama persis.
    #
    # HANYA PUCUK DAFTARNYA YANG DIMINTA. Mesinnya menghitung dan meringkas
    # SELURUH katalog apa pun ukuran halaman yang diminta -- `summary` lahir
    # sebelum pemenggalan halaman -- sehingga dasbor cukup meminta sebanyak
    # baris yang benar-benar dicetak tabelnya.
    #
    # Sebelumnya di sini tertulis `page_size=ro.BATAS_BARIS` (400), dan itu
    # cacat yang diam: common.clamp_page() menjepit ukuran halaman pada
    # PAGE_SIZE_MAX (200), jadi seluruh angka yang dijumlahkan dari `items`
    # diam-diam hanya mencakup dua ratus baris teratas begitu katalog
    # melewatinya -- sementara kartu di sebelahnya, yang membaca `summary`,
    # tetap mencakup seluruhnya. Angka-angka itu kini datang dari `summary`
    # juga, jadi ukuran halaman tidak lagi dapat menggeser satu pun dari
    # mereka.
    hasil = ro.daftar_reorder(
        warehouse_id=None, status=None, priority=None, q=None,
        page=1, page_size=BATAS_PERHATIAN, lang=lang,
    )
    baris = hasil["items"]
    ringkas = hasil["summary"]

    # Baris sudah terurut menurut kegentingan oleh mesinnya sendiri; yang
    # diambil di sini hanya pucuknya, dan hanya yang memang menuntut tindakan.
    perhatian = [
        {
            "sku": b["sku"],
            "item_name": b["item_name"],
            "warehouse_code": b["warehouse_code"],
            "unit_code": b["unit_code"],
            # Stok TERSEDIA, bukan stok fisik -- angka yang sama dengan kolom
            # "Stok tersedia" pada halaman Pemesanan Ulang, dan angka yang
            # benar-benar dibandingkan mesin terhadap titik pesan efektif di
            # kolom sebelahnya. Sebelumnya kolom ini mencetak stok FISIK,
            # sehingga satu barang yang punya stok tercadang berbunyi berbeda
            # di dasbor dan di halaman pemesanan ulang -- dua angka untuk satu
            # barang, dan yang di dasbor bahkan tidak menjelaskan statusnya
            # sendiri ("stok 10, titik pesan 8, perlu reorder").
            "current_stock": b["available_stock_int"],
            "reorder_point": b["effective_reorder_point_int"],
            # Kebutuhan pada periode bawaan mesin itu. Sejak status mengikuti
            # periode, INILAH angka yang menjelaskan barisnya: barang dapat
            # perlu dipesan dengan stok masih di atas titik pesan, karena
            # stoknya kurang untuk kebutuhan ini.
            "forecast_usage": b["forecast_usage_int"],
            "horizon_days": b["decision_horizon_days"],
            "days_of_cover": b["days_of_cover_int"],
            "recommended_order_qty": b["recommended_order_qty"],
            "status": b["action_status"],
            "status_label": b["action_status_label"],
            "priority": b["priority"],
            "priority_label": b["priority_label"],
        }
        for b in baris if b["action_status"] != decision.STATUS_AMAN
    ][:BATAS_PERHATIAN]

    # Kebutuhan ke depan, SELURUHNYA dari ringkasan mesin pemesanan ulang.
    # Tidak ada satu pun penjumlahan yang dikerjakan di sini: yang dijumlahkan
    # dasbor sendiri adalah yang paling mudah menyimpang dari halaman
    # Pemesanan Ulang tanpa ada yang menyadarinya.
    #
    # `horizon_days` adalah horizon KEPUTUSAN yang dipatok mesin itu, bukan
    # periode prakiraan yang dipilih pengguna di layar Prakiraan -- menyebut
    # angka satu horizon dengan label horizon yang lain adalah cara paling
    # mudah membuat dua halaman terlihat berselisih.
    prakiraan = {
        # None pada katalog yang masih kosong: layar menyembunyikan seluruh
        # kartu alih-alih mencetak tiga nol yang tidak menjelaskan apa pun.
        "horizon_days": ringkas["horizon_hari"] if ringkas["total_baris"] else None,
        "forecast_usage": ringkas["total_kebutuhan_horizon"],
        "recommended_order_qty": ringkas["total_qty"],
        "qty_unknown": ringkas["qty_belum_terhitung"],
        # Barang yang stoknya habis DI DALAM horizon keputusan. Pertanyaan
        # yang berbeda dari kartu "Risiko Kehabisan" di atas, yang bertanya
        # apakah stok habis sebelum KIRIMAN tiba; label kedua kartu menyebut
        # tenggatnya masing-masing supaya keduanya tidak terbaca sebagai satu
        # angka yang berselisih.
        "projected_stockout": ringkas["habis_dalam_horizon"],
        "without_forecast": ringkas["tanpa_prakiraan"],
    }

    # ---------- kalimat kondisi ----------
    # SATU kalimat, bukan daftar berbutir. Versi sebelumnya menerbitkan sampai
    # empat baris temuan yang mengulang angka kartu di bawahnya; yang dibaca
    # orang dari dasbor adalah satu kesimpulan, dan sisanya sudah ada di kartu.
    if kondisi["items"] == 0:
        kondisi_teks, nada = i18n.t("dash.state.no_items", lang), "info"
    elif ringkas["risiko_stockout"]:
        kondisi_teks, nada = i18n.t(
            "dash.state.stockout", lang, n=ringkas["risiko_stockout"],
            reorder=ringkas["perlu_reorder"]), "warning"
    elif ringkas["perlu_reorder"]:
        kondisi_teks, nada = i18n.t(
            "dash.state.reorder", lang, n=ringkas["perlu_reorder"]), "warning"
    else:
        kondisi_teks, nada = i18n.t(
            "dash.state.clear", lang, n=ringkas["aman"]), "good"

    return {
        "condition": kondisi,
        "stock_by_warehouse": per_gudang,
        "attention": {
            "need_reorder": ringkas["perlu_reorder"],
            "stockout_risk": ringkas["risiko_stockout"],
            "high_priority": ringkas["prioritas_tinggi"],
            "healthy": ringkas["aman"],
            "rows": perhatian,
        },
        "forecast": prakiraan,
        "state": {"text": kondisi_teks, "level": nada},
        "value_basis": i18n.t("dash.value_basis", lang),
        # True berarti katalognya melebihi batas mesin pemesanan ulang dan
        # angka "perlu perhatian" dihitung atas sebagian barang saja. Dasbor
        # yang diam-diam meringkas sebagian adalah dasbor yang menyesatkan.
        "truncated": hasil["truncated"],
    }
