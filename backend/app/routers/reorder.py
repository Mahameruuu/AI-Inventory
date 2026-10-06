# -*- coding: utf-8 -*-
"""
Daftar keputusan pemesanan ulang.

SATU LAYAR UNTUK SELURUH GUDANG, bukan satu barang pada satu waktu. Layar
Pemesanan Ulang yang lama menjawab dengan benar untuk barang yang sedang
dipilih, tetapi tidak pernah menjawab pertanyaan yang sebenarnya dibawa orang
pengadaan ke depan komputer: MANA SAJA yang perlu dipesan hari ini. Untuk
menjawabnya dengan layar lama, seseorang harus memilih barang satu per satu
dari dropdown dan mengingat sendiri hasilnya.

TIDAK ADA RUMUS DI BERKAS INI. Setiap baris dihitung oleh jalur yang sama
persis dengan /api/forecast -- `forecasting._susun()` lalu
`decision.lapisan_keputusan()` -- sehingga satu barang mustahil menyebut status
atau jumlah yang berbeda di daftar ini dan di layar detailnya. Yang dikerjakan
di sini hanya perulangan, penyaringan, pengurutan, dan peringkasan.

PERIODE DAN MODELNYA MENGIKUTI HALAMAN PRAKIRAAN (sejak 6 Oktober 2026).
Dulu keduanya dipatok -- 14 hari, rumus statistik -- supaya setelan tampilan
di layar sebelah tidak menggeser jumlah pesanan diam-diam. Akibatnya dua
halaman menyebut dua kebutuhan untuk barang yang sama, dan tidak ada yang
dapat menjelaskan selisihnya di depan tabel. Kini keduanya parameter yang
terlihat di layar ini juga: `days` dan `model`, dengan bawaan yang sama
seperti sebelumnya bagi pemanggil yang tidak mengirim apa-apa (dasbor).
Status dan jumlahnya dihitung pada mode periode lapisan keputusan; lihat
decision.status_keputusan_periode.

BIAYANYA DIBATASI. Tiap baris menjalankan rantai prakiraan penuh, jadi jumlah
pasangan barang/gudang yang diproses dijepit pada BATAS_BARIS. Lebih baik
menjawab sebagian dengan jujur -- lewat `truncated` pada jawaban -- daripada
menahan permintaan selama puluhan detik atau, lebih buruk, diam-diam
menampilkan daftar yang tidak lengkap.
"""

from fastapi import APIRouter, Query

from .. import decision, forecasting, i18n
from ..common import clamp_page, PAGE_SIZE_DEFAULT
from ..db import readonly
from ..ml import klasik
from . import forecasting as fr

router = APIRouter(tags=["reorder"])

# Sebanyak-banyaknya pasangan barang/gudang yang dihitung dalam satu
# permintaan. Katalog penyewa saat ini jauh di bawah angka ini; batasnya ada
# supaya katalog yang membesar memperlambat halaman secara terukur, bukan
# menggantungkannya.
BATAS_BARIS = 400

# Urutan kerja: yang paling mendesak lebih dulu. Dipakai mengurutkan baris,
# bukan sekadar mewarnai -- daftar yang benar isinya tetapi acak urutannya
# menuntut pembacanya memindai seluruh halaman untuk menemukan yang genting.
_URUT_STATUS = {
    decision.STATUS_RISIKO_STOCKOUT: 0,
    decision.STATUS_PERLU_REORDER: 1,
    decision.STATUS_AMAN: 2,
}
_URUT_PRIORITAS = {
    decision.PRIORITAS_TINGGI: 0,
    decision.PRIORITAS_SEDANG: 1,
    decision.PRIORITAS_RENDAH: 2,
}


def _pasangan(q: str | None, warehouse_id: int | None) -> list[dict]:
    """
    Pasangan barang/gudang yang punya baris persediaan.

    Disaring di BASIS DATA, bukan setelah seluruh rantai prakiraan berjalan:
    menghitung empat ratus baris lalu membuang tiga ratus sembilan puluh di
    antaranya karena tidak cocok dengan kata pencarian adalah pekerjaan yang
    seluruhnya terbuang.

    Barang nonaktif tidak ikut. Ia tidak dibeli lagi, jadi menampilkannya pada
    daftar pengadaan hanya menambah baris yang tidak akan pernah ditindak.
    """
    where, params = "WHERE it.is_active AND w.is_active", []
    if warehouse_id:
        where += " AND inv.warehouse_id = %s"
        params.append(warehouse_id)
    if q:
        where += " AND (it.sku ILIKE %s OR it.name ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]

    with readonly() as cur:
        cur.execute(
            f"""
            SELECT inv.item_id, inv.warehouse_id
              FROM inventory inv
              JOIN items it     ON it.id = inv.item_id
              JOIN warehouses w ON w.id = inv.warehouse_id
             {where}
             ORDER BY inv.item_id, inv.warehouse_id
             LIMIT %s
            """,
            [*params, BATAS_BARIS + 1],
        )
        return [dict(r) for r in cur.fetchall()]


def _hari(days) -> int:
    """
    Periode yang sah, atau bawaannya.

    Fungsi router di aplikasi ini kerap dipanggil langsung sebagai fungsi
    Python (dasbor melakukannya), dan pada pemanggilan seperti itu nilai bawaan
    Query milik FastAPI masuk apa adanya -- sebuah objek, bukan bilangan.
    """
    if isinstance(days, bool) or not isinstance(days, int):
        return decision.HORIZON_KEPUTUSAN
    return max(1, min(days, fr.FORECAST_DAYS_MAX))


def _baris(item_id: int, warehouse_id: int, lang: str,
           days: int = decision.HORIZON_KEPUTUSAN,
           model: str = klasik.KUNCI_STATISTIK) -> dict | None:
    """
    Satu baris daftar, dari jalur perhitungan yang sama dengan layar detail.

    Mengembalikan None bila barang/gudangnya tidak dapat dirakit sama sekali --
    master data terhapus di tengah perulangan, misalnya. Satu baris yang gagal
    tidak boleh menjatuhkan seluruh halaman: yang lain tetap dapat ditindak.
    """
    try:
        h = fr._susun(item_id, warehouse_id, days,
                      fr.HISTORICAL_DAYS_DEFAULT, lang, model=model,
                      keputusan_periode=True)
    except Exception:
        return None

    return {
        "item_id": item_id,
        "warehouse_id": warehouse_id,
        "sku": h["item"]["sku"],
        "item_name": h["item"]["name"],
        "unit_code": h["item"]["unit_code"],
        "warehouse_code": h["warehouse"]["code"],
        "warehouse_name": h["warehouse"]["name"],

        # --- keadaan stok ---
        "current_stock_int": h["current_stock_int"],
        "available_stock_int": h["available_stock_int"],
        "reorder_point_int": h["reorder_point_int"],
        "effective_reorder_point_int": h["effective_reorder_point_int"],
        "safety_stock_int": h["safety_stock_int"],
        "lead_time_days_int": h["lead_time_days_int"],
        "lead_time_demand_int": h["lead_time_demand_int"],

        # --- kebutuhan ke depan, pada PERIODE yang dipilih di layar ---
        # Sama persis dengan tiga kartu halaman Prakiraan untuk periode dan
        # model yang sama: kebutuhan, lalu kurang ATAU sisa terhadap stok
        # tersedia. Kedua selisih itu None bila prakiraannya belum tersedia.
        "decision_horizon_days": h["decision_horizon_days"],
        "forecast_usage_int": h["decision_horizon_usage_int"],
        "period_shortage_int": h["period_shortage_int"],
        "period_surplus_int": h["period_surplus_int"],
        # Versi PENUH dari angka di atas, dan ia ada di sini untuk satu
        # keperluan saja: dijumlahkan. Kolom tabel merender yang `_int`;
        # ringkasan katalog menjumlahkan yang ini lalu membulatkan SEKALI di
        # ujung. Menjumlahkan angka yang sudah dibulatkan satu per satu adalah
        # cara paling mudah membuat dua puluh barang berlaju 0,1/hari
        # berjumlah nol -- dan itulah yang tercetak di dasbor sebelum
        # perubahan ini: "prakiraan pemakaian 14 hari: 0" berdampingan dengan
        # "disarankan dipesan: 2".
        "forecast_usage": h["decision_horizon_usage"],
        "usage_frequency_label": h["usage_frequency_label"],
        "usage_frequency_detail": h["usage_frequency_detail"],

        # --- kapan habis ---
        # days_of_cover, BUKAN days_until_stockout: yang kedua dibatasi panjang
        # periode prakiraan dan karena itu kosong pada barang yang habisnya
        # lebih jauh dari horizon. Kolom "hari menuju habis" harus menjawab
        # untuk setiap baris, bukan hanya yang genting.
        "days_of_cover_int": h["days_of_cover_int"],
        "days_to_effective_rop_int": h["days_to_effective_rop_int"],

        # --- keputusan ---
        "action_status": h["action_status"],
        "action_status_label": h["action_status_label"],
        "priority": h["priority"],
        "priority_label": h["priority_label"],
        "reason": h["reorder_status_reason"],
        "recommended_order_qty": h["recommended_order_qty"],
        "order_up_to_level_int": h["order_up_to_level_int"],
        # `has_forecast` dirakit forecast_api, bukan _susun(); diturunkan di
        # sini dari sumber yang sama persis supaya kedua endpoint mustahil
        # berselisih tentang barang yang sama.
        "has_forecast": h["status"] != forecasting.STATUS_INSUFFICIENT,
    }


@router.get("/api/reorder")
def daftar_reorder(
    warehouse_id: int | None = Query(None, gt=0),
    status: str | None = Query(None, description="AMAN, PERLU_REORDER, RISIKO_STOCKOUT"),
    priority: str | None = Query(None, description="TINGGI, SEDANG, RENDAH"),
    q: str | None = Query(None, description="Cari SKU atau nama barang"),
    days: int = Query(decision.HORIZON_KEPUTUSAN, ge=1, le=fr.FORECAST_DAYS_MAX,
                      description="Periode kebutuhan, sama dengan /api/forecast"),
    model: str = Query(klasik.KUNCI_STATISTIK,
                       description="Model prakiraan, sama dengan /api/forecast"),
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
    lang: str = Query(i18n.BAHASA_BAWAAN),
) -> dict:
    """
    Daftar keputusan pemesanan ulang untuk seluruh barang di gudang terpilih.

    RINGKASANNYA DIHITUNG ATAS SELURUH HASIL SARINGAN, bukan atas halaman yang
    sedang ditampilkan. Kartu "Total perlu reorder" yang hanya menghitung dua
    puluh baris pertama akan berbunyi berbeda setiap kali orang membuka halaman
    berikutnya, dan angka yang berubah karena navigasi tidak dapat dipakai
    mengambil keputusan apa pun.

    Saringan status dan prioritas TIDAK ikut menyusutkan ringkasannya: kartu
    ringkas menjawab "berapa banyak yang perlu ditangani", dan jawabannya tidak
    boleh berubah hanya karena pembacanya sedang menyaring satu tab.
    """
    page, page_size, offset = clamp_page(page, page_size)
    lang = i18n.normalisasi(lang)
    days = _hari(days)
    model = fr._model_sah(model if isinstance(model, str) else "")

    pasangan = _pasangan(q, warehouse_id)
    terpotong = len(pasangan) > BATAS_BARIS
    pasangan = pasangan[:BATAS_BARIS]

    semua = [b for b in (_baris(p["item_id"], p["warehouse_id"], lang,
                                days, model)
                         for p in pasangan) if b is not None]

    # Ringkasan atas SELURUH baris, sebelum saringan status/prioritas.
    ringkas = {
        "perlu_reorder": sum(1 for b in semua
                             if b["action_status"] == decision.STATUS_PERLU_REORDER),
        "risiko_stockout": sum(1 for b in semua
                               if b["action_status"] == decision.STATUS_RISIKO_STOCKOUT),
        "prioritas_tinggi": sum(1 for b in semua
                                if b["priority"] == decision.PRIORITAS_TINGGI),
        "aman": sum(1 for b in semua if b["action_status"] == decision.STATUS_AMAN),
        # Jumlah total yang direkomendasikan, atas baris yang memang perlu
        # dipesan. None (belum dapat dihitung) tidak dijumlahkan sebagai nol --
        # ia dihitung terpisah supaya total yang terlihat tidak diam-diam
        # mengecil karena sebagian barang belum punya angka.
        "total_qty": sum(b["recommended_order_qty"] or 0 for b in semua),
        "qty_belum_terhitung": sum(1 for b in semua
                                   if b["recommended_order_qty"] is None),
        "total_baris": len(semua),

        # --- kebutuhan ke depan, seluruh katalog ---
        #
        # DIHITUNG DI SINI, BUKAN DI DASBOR. Ketiga angka di bawah adalah
        # ringkasan atas jawaban mesin ini, jadi rumahnya ringkasan mesin ini
        # -- sama seperti "perlu_reorder" dan "risiko_stockout" di atasnya.
        # Sebelumnya dasbor menghitungnya sendiri dari `items`, yaitu HALAMAN
        # PERTAMA jawaban ini: begitu katalog melewati PAGE_SIZE_MAX (200
        # baris) angka kartu "kebutuhan ke depan" diam-diam hanya mencakup dua
        # ratus baris teratas, sementara kartu "perlu reorder" di sebelahnya
        # tetap mencakup seluruhnya. Tidak ada satu pun galat yang terbit dari
        # perselisihan seperti itu.
        "horizon_hari": days,
        # Dijumlahkan sebagai pecahan lalu dibulatkan SEKALI. Lihat catatan
        # pada "forecast_usage" di _baris().
        "total_kebutuhan_horizon": decision.bulat(
            sum(b["forecast_usage"] or 0.0 for b in semua)) or 0,
        # Barang yang stoknya diproyeksikan habis DI DALAM horizon keputusan.
        # Pertanyaan yang berbeda dari "risiko_stockout" di atas, yang
        # bertanya apakah stok habis sebelum KIRIMAN tiba -- dan karena
        # keduanya memakai tenggat yang berbeda, keduanya memang boleh
        # berbeda. Label di layar wajib menyebut tenggatnya masing-masing.
        "habis_dalam_horizon": sum(
            1 for b in semua
            if b["days_of_cover_int"] is not None
            and b["days_of_cover_int"] <= days),
        "tanpa_prakiraan": sum(1 for b in semua if not b["has_forecast"]),
    }

    if status:
        semua = [b for b in semua if b["action_status"] == status]
    if priority:
        semua = [b for b in semua if b["priority"] == priority]

    # Paling mendesak lebih dulu, lalu yang jumlahnya terbesar: dua baris
    # dengan status dan prioritas sama diurutkan menurut besarnya akibat.
    semua.sort(key=lambda b: (
        _URUT_STATUS.get(b["action_status"], 9),
        _URUT_PRIORITAS.get(b["priority"], 9),
        -(b["recommended_order_qty"] or 0),
        b["sku"],
    ))

    total = len(semua)
    pages = max(1, -(-total // page_size))
    return {
        "items": semua[offset:offset + page_size],
        "summary": ringkas,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        # True berarti katalognya melebihi BATAS_BARIS dan daftar ini sebagian.
        # Layar WAJIB menyatakannya; daftar pengadaan yang diam-diam terpotong
        # adalah cara paling mudah melewatkan barang yang justru genting.
        "truncated": terpotong,
        "row_limit": BATAS_BARIS,
    }
