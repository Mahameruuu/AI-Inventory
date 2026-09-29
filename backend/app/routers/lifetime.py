# -*- coding: utf-8 -*-
"""
Analisis Umur Pakai.

    GET /api/lifetime                          daftar komponen + ringkasannya
    GET /api/lifetime/{item_id}/{warehouse_id} riwayat penggantian satu komponen

TIDAK ADA RUMUS DI BERKAS INI. Seluruh perhitungan -- konversi satuan, pita
batas, deviasi, kategori, tren -- tinggal di app/lifetime.py, tanpa basis
data, sehingga dapat diuji tanpa satu baris SQL pun. Yang dikerjakan di sini
hanya membaca, mengelompokkan, menyaring, dan mengurutkan.

SUMBER PENGGANTIAN. Satu penggantian = satu baris stock_issue_items. Tidak
ada tabel "pemasangan"; pengeluaran barang dari gudang adalah satu-satunya
jejak yang dimiliki basis data ini, dan lingkupnya dinyatakan apa adanya pada
`basis` di tiap baris jawaban.

MODUL INI TIDAK MENYENTUH PRAKIRAAN MAUPUN PEMESANAN ULANG. Ia analitis: ia
menjelaskan pola penggantian yang sudah terjadi. Menyambungkannya ke titik
pesan menuntut aturan bisnis yang belum ada, dan aturan yang dikarang di sini
akan menggerakkan uang pengadaan tanpa seorang pun pernah menyetujuinya.
"""

from fastapi import APIRouter, Query

from .. import i18n, lifetime as lt
from ..common import PAGE_SIZE_DEFAULT, clamp_page
from ..db import readonly
from ..errors import invalid, not_found

router = APIRouter(prefix="/api/lifetime", tags=["lifetime"])

# Sebanyak-banyaknya kejadian penggantian yang dikirim pada panel detail.
# Perusahaan Utama menyimpan sampai 93 penggantian untuk satu filter oli
# sepanjang dua puluh tahun; yang dibaca orang adalah yang terakhir, dan
# mengirim seluruhnya hanya membesarkan jawaban tanpa menambah keterangan.
BATAS_KEJADIAN_DETAIL = 60


def _pasangan_penggantian(warehouse_id: int | None, q: str | None) -> tuple[list[dict], dict]:
    """
    Master komponen beserta seluruh tanggal penggantiannya.

    SATU QUERY untuk master dan satu untuk kejadiannya, bukan satu query per
    barang: dua puluh barang hari ini akan menjadi dua ratus, dan pola
    "sekali per baris" baru terasa setelah halaman terlanjur dipakai.

    Barang TANPA umur pakai referensi tetap ikut terbaca -- ia tidak dapat
    dianalisis, dan halaman harus dapat mengatakan BERAPA BANYAK yang belum
    punya referensi. Menyaringnya di SQL membuat angka itu mustahil dihitung.
    """
    where, params = ["it.is_active", "w.is_active"], []
    if warehouse_id:
        where.append("inv.warehouse_id = %s")
        params.append(warehouse_id)
    if q:
        where.append("(it.sku ILIKE %s OR it.name ILIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    syarat = " AND ".join(where)

    with readonly() as cur:
        # Pasangan barang/gudang berasal dari PERSEDIAAN, sama dengan halaman
        # Pemesanan Ulang: itulah daftar barang yang benar-benar dikelola di
        # gudang tersebut. Menurunkannya dari riwayat pengeluaran saja akan
        # menghilangkan komponen yang belum pernah diganti sekalipun -- justru
        # baris yang perlu berbunyi "belum cukup data".
        cur.execute(
            f"""
            SELECT inv.item_id, inv.warehouse_id,
                   it.sku, it.name AS item_name,
                   u.code AS unit_code,
                   it.service_life_value, it.service_life_unit,
                   w.code AS warehouse_code, w.name AS warehouse_name
              FROM inventory inv
              JOIN items it      ON it.id = inv.item_id
              JOIN warehouses w  ON w.id = inv.warehouse_id
              LEFT JOIN units u  ON u.id = it.unit_id
             WHERE {syarat}
             ORDER BY it.name, w.code
            """,
            params,
        )
        master = [dict(r) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT sii.item_id, si.warehouse_id, si.issue_date::date AS tanggal
              FROM stock_issue_items sii
              JOIN stock_issues si ON si.id = sii.stock_issue_id
             ORDER BY 1, 2, 3
            """
        )
        kejadian: dict[tuple[int, int], list] = {}
        for r in cur.fetchall():
            kejadian.setdefault((r["item_id"], r["warehouse_id"]), []).append(r["tanggal"])

    return master, kejadian


def _baris(m: dict, tanggal: list, lang: str) -> dict:
    """Satu baris daftar: master + riwayatnya, dilewatkan ke app/lifetime.py."""
    harapan = lt.umur_harapan_hari(m["service_life_value"], m["service_life_unit"])
    bawah, atas = lt.batas(harapan)

    # TANPA UMUR PAKAI REFERENSI, RIWAYATNYA TIDAK DIBACA SAMA SEKALI.
    #
    # Bukan sekadar penghematan. Pengeluaran barang berarti "penggantian
    # komponen" hanya untuk barang yang memang punya umur pakai; untuk barang
    # habis pakai -- majun, amplas, kawat las, yang keluar tiap hari untuk
    # produksi -- jarak antar pengeluaran adalah IRAMA PEMAKAIAN, bukan umur
    # satu unit. Menghitungnya tetap akan membuat halaman ini melaporkan
    # "90 penggantian, umur pakai 1 hari" untuk sekantong majun, dan angka
    # yang salah artinya lebih buruk daripada kolom yang kosong.
    #
    # Yang perlu dilakukan pada baris seperti ini adalah mengisi umur pakai di
    # halaman Master Barang -- atau menerima bahwa barang itu memang bukan
    # komponen yang punya umur pakai.
    if harapan is None:
        tanggal, interval = [], []
    else:
        interval = lt.interval_penggantian(tanggal)

    aktual = lt.umur_aktual(interval)
    kategori = lt.kategori(aktual, harapan)
    tren = lt.tren_penggantian(interval)

    return {
        "item": {"id": m["item_id"], "sku": m["sku"], "name": m["item_name"],
                 "unit_code": m["unit_code"]},
        "warehouse": {"id": m["warehouse_id"], "code": m["warehouse_code"],
                      "name": m["warehouse_name"]},

        # --- umur pakai harapan, apa adanya DAN dalam hari ---
        # Keduanya dikirim: satuannya asli yang dikenali pengguna ("12.500
        # jam"), dan hari kalender yang membuat pembandingan mungkin. Yang
        # kedua saja akan menyembunyikan asumsi jam operasi di balik satu
        # angka yang terlihat pasti.
        "expected_value": (float(m["service_life_value"])
                           if m["service_life_value"] is not None else None),
        "expected_unit": m["service_life_unit"],
        "expected_lifetime_days": harapan,
        "lower_lifetime_days": bawah,
        "upper_lifetime_days": atas,
        "has_reference": harapan is not None,

        # --- umur pakai aktual ---
        "replacement_count": len(tanggal),
        "interval_count": len(interval),
        "actual_lifetime_days": aktual,
        "last_actual_lifetime_days": float(interval[-1]) if interval else None,
        "shortest_lifetime_days": float(min(interval)) if interval else None,
        "longest_lifetime_days": float(max(interval)) if interval else None,
        "last_replacement_date": max(tanggal).isoformat() if tanggal else None,

        # --- kesimpulan ---
        "deviation_percentage": lt.deviasi_persen(aktual, harapan),
        "status": kategori,
        "status_label": lt.label_kategori(kategori, lang),
        "replacement_trend": tren,
        "replacement_trend_label": lt.label_tren(tren, lang),
        "replacements_per_year": lt.frekuensi_per_tahun(aktual),

        # --- di atas apa angka-angka di atas berdiri ---
        "basis": lt.kalimat_dasar(harapan is not None, len(tanggal),
                                  len(interval), lang),
        "inventory_impact": lt.kalimat_dampak(kategori, tren, lang),
    }


# Urutan kerja: yang menyimpang lebih dulu, karena itulah baris yang menuntut
# dibaca. Baris tanpa umur terukur turun ke bawah -- ia tidak menyatakan apa
# pun, dan menaruhnya di atas berarti menutupi yang menyatakan sesuatu.
_URUT_STATUS = {lt.PREMATURE: 0, lt.EXTENDED: 1, lt.NORMAL: 2, lt.INSUFFICIENT: 3}


@router.get("")
def daftar(
    warehouse_id: int | None = Query(None, gt=0),
    status: str | None = Query(
        None, description="PREMATURE, NORMAL, EXTENDED, INSUFFICIENT"),
    q: str | None = Query(None, description="Cari SKU atau nama komponen"),
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
    lang: str = Query(i18n.BAHASA_BAWAAN),
) -> dict:
    """
    Umur pakai seluruh komponen pada gudang terpilih.

    RINGKASANNYA DIHITUNG ATAS SELURUH BARIS, bukan atas halaman yang sedang
    tampil maupun atas saringan status yang sedang aktif. Kartu "penggantian
    dini" yang menyusut karena pembacanya menyaring satu tab tidak menjawab
    pertanyaan apa pun.
    """
    if status and status not in lt.KATEGORI:
        raise invalid(i18n.t("lt.err.status", lang,
                             sah=", ".join(lt.KATEGORI)), "status")

    page, page_size, offset = clamp_page(page, page_size)
    lang = i18n.normalisasi(lang)

    master, kejadian = _pasangan_penggantian(warehouse_id, q)
    semua = [_baris(m, kejadian.get((m["item_id"], m["warehouse_id"]), []), lang)
             for m in master]

    ringkas = {
        "total_items": len(semua),
        "premature": sum(1 for b in semua if b["status"] == lt.PREMATURE),
        "normal": sum(1 for b in semua if b["status"] == lt.NORMAL),
        "extended": sum(1 for b in semua if b["status"] == lt.EXTENDED),
        "insufficient": sum(1 for b in semua if b["status"] == lt.INSUFFICIENT),
        # Dihitung terpisah dari `insufficient`: "belum punya umur pakai
        # referensi" dan "sudah punya referensi tetapi baru diganti sekali"
        # adalah dua kekurangan yang berbeda, dan yang pertama diperbaiki di
        # halaman Master Barang sedangkan yang kedua hanya oleh waktu.
        "without_reference": sum(1 for b in semua if not b["has_reference"]),
        "total_replacements": sum(b["replacement_count"] for b in semua),
        "trend_increasing": sum(1 for b in semua
                                if b["replacement_trend"] == lt.TREN_NAIK),
    }

    if status:
        semua = [b for b in semua if b["status"] == status]

    semua.sort(key=lambda b: (
        _URUT_STATUS.get(b["status"], 9),
        # Di dalam satu status, simpangan terbesar lebih dulu.
        -abs(b["deviation_percentage"] or 0),
        b["item"]["sku"],
    ))

    total = len(semua)
    return {
        "items": semua[offset:offset + page_size],
        "summary": ringkas,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        # Asumsi yang menopang SELURUH halaman, dikirim supaya terbaca di layar
        # dan bukan hanya di kode.
        "assumptions": {
            "operating_hours_per_day": lt.OPERATING_HOURS_PER_DAY,
            "tolerance_percentage": lt.LIFETIME_TOLERANSI * 100,
            "note": i18n.t("lt.assumption", lang,
                           jam=int(lt.OPERATING_HOURS_PER_DAY),
                           persen=int(lt.LIFETIME_TOLERANSI * 100)),
        },
    }


@router.get("/{item_id}/{warehouse_id}")
def detail(item_id: int, warehouse_id: int,
           lang: str = Query(i18n.BAHASA_BAWAAN)) -> dict:
    """
    Riwayat penggantian satu komponen di satu gudang.

    Tiap kejadian membawa umur pakai yang DIAKHIRINYA -- jarak dari penggantian
    sebelumnya -- beserta kategorinya sendiri. Kejadian pertama tidak punya
    pendahulu, jadi umurnya null: tidak diketahui, bukan nol.
    """
    lang = i18n.normalisasi(lang)

    with readonly() as cur:
        cur.execute(
            """
            SELECT it.id AS item_id, it.sku, it.name AS item_name,
                   u.code AS unit_code,
                   it.service_life_value, it.service_life_unit,
                   w.id AS warehouse_id, w.code AS warehouse_code,
                   w.name AS warehouse_name
              FROM items it
              JOIN warehouses w  ON w.id = %s
              LEFT JOIN units u  ON u.id = it.unit_id
             WHERE it.id = %s
            """,
            (warehouse_id, item_id),
        )
        m = cur.fetchone()
        if m is None:
            raise not_found("item", item_id)
        m = dict(m)

        cur.execute(
            """
            SELECT si.id, si.issue_date::date AS tanggal, si.issue_number,
                   sii.quantity
              FROM stock_issue_items sii
              JOIN stock_issues si ON si.id = sii.stock_issue_id
             WHERE sii.item_id = %s AND si.warehouse_id = %s
             ORDER BY si.issue_date, si.id
            """,
            (item_id, warehouse_id),
        )
        catatan = [dict(r) for r in cur.fetchall()]

    tanggal = [r["tanggal"] for r in catatan]
    baris = _baris(m, tanggal, lang)
    harapan = baris["expected_lifetime_days"]

    # Kejadian dirakit dari catatan berurutan; umur pakai satu kejadian adalah
    # jarak ke kejadian SEBELUMNYA, yaitu lama unit yang baru saja dicabut.
    kejadian = []
    for i, r in enumerate(catatan):
        umur = (r["tanggal"] - catatan[i - 1]["tanggal"]).days if i else None
        umur = float(umur) if umur else None
        kejadian.append({
            "id": r["id"],
            "date": r["tanggal"].isoformat(),
            "document": r["issue_number"],
            "quantity": float(r["quantity"]),
            "lifetime_days": umur,
            "deviation_percentage": lt.deviasi_persen(umur, harapan),
            "status": lt.kategori(umur, harapan) if umur is not None else None,
            "status_label": (lt.label_kategori(lt.kategori(umur, harapan), lang)
                             if umur is not None else None),
        })

    return {
        **baris,
        # Yang terbaru lebih dulu, dan hanya sebanyak BATAS_KEJADIAN_DETAIL.
        "events": list(reversed(kejadian))[:BATAS_KEJADIAN_DETAIL],
        "events_total": len(kejadian),
        # SELALU terkirim, meski seluruhnya kosong. Panel yang menghilang saat
        # datanya tidak ada membuat pembacanya menyimpulkan sendiri sebab
        # penggantian dini dari satu-satunya angka yang tersisa di layar.
        "contributing_factors": lt.faktor_pendukung(lang),
        "contributing_factors_note": i18n.t("lt.factor.none", lang),
    }
