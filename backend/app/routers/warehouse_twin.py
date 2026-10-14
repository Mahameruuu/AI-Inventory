# -*- coding: utf-8 -*-
"""
Dashboard terpadu: bahan baku tampilan 3D satu gudang.

TIDAK ADA LOKASI RAK DI BASIS DATA. Skema hanya tahu stok per barang per
gudang (tabel inventory); tidak ada zona, rak, maupun bin. Karena itu
endpoint ini hanya mengembalikan FAKTA yang ada -- barang, kategori, jumlah,
ambang, dan keputusan mesin -- dan tidak pernah mengarang posisi. Pengelompokan
menjadi rak dilakukan layar sebagai tata letak VIRTUAL yang diberi label demikian.

STATUS DIPINJAM DARI MESIN PEMESANAN ULANG, tidak dihitung di sini. Versi awal
modul ini punya aturan sendiri (stok vs stok minimum), dan itu definisi kedua
untuk pertanyaan "perlu perhatian" yang sudah dijawab dasbor dan halaman
Pemesanan Ulang. Kini ketiganya membaca `reorder.daftar_reorder()`:

  AMAN             -> normal
  PERLU_REORDER    -> perhatian
  RISIKO_STOCKOUT  -> kritis
  (tak ada baris)  -> tidak_diketahui; barang nonaktif atau yang tak dapat
                      dirakit mesin tidak boleh tampil seolah aman.
"""

from fastapi import APIRouter, Query

from .. import decision, i18n
from ..db import readonly
from ..errors import invalid
from . import lifetime as lt_router
from . import reorder as ro

router = APIRouter(tags=["warehouse-twin"])

_PETA_STATUS = {
    decision.STATUS_AMAN: "normal",
    decision.STATUS_PERLU_REORDER: "perhatian",
    decision.STATUS_RISIKO_STOCKOUT: "kritis",
}


def status_dari_aksi(aksi: str | None) -> str:
    return _PETA_STATUS.get(aksi or "", "tidak_diketahui")


@router.get("/api/warehouse-twin")
def warehouse_twin(
    warehouse_id: int,
    lang: str = Query(i18n.BAHASA_BAWAAN),
) -> dict:
    lang = i18n.normalisasi(lang)
    with readonly() as cur:
        cur.execute("SELECT id, code, name, location FROM warehouses WHERE id = %s",
                    (warehouse_id,))
        gudang = cur.fetchone()
        if gudang is None:
            raise invalid("Gudang tidak ditemukan", "warehouse_id")
        cur.execute(
            """
            SELECT it.id AS item_id, it.sku, it.name, it.category_id,
                   COALESCE(c.name, '(tanpa kategori)') AS category_name,
                   COALESCE(u.code, '-') AS unit_code,
                   inv.quantity, inv.reserved_quantity,
                   it.minimum_stock, it.reorder_point, it.maximum_stock
            FROM inventory inv
            JOIN items it      ON it.id = inv.item_id
            -- LEFT JOIN: kategori/satuan yang tak terlihat (RLS atau data yatim)
            -- tidak boleh membuat stok hilang diam-diam dari tampilan.
            LEFT JOIN categories c ON c.id = it.category_id
            LEFT JOIN units u      ON u.id = it.unit_id
            WHERE inv.warehouse_id = %s
            ORDER BY c.name, it.sku
            """,
            (warehouse_id,),
        )
        baris = cur.fetchall()

    hasil = ro.daftar_reorder(
        warehouse_id=warehouse_id, status=None, priority=None, q=None,
        page=1, page_size=ro.BATAS_BARIS, lang=lang,
    )
    mesin = {b["item_id"]: b for b in hasil["items"]}

    # Umur pakai DIPINJAM dari modul Analisis Umur Pakai, bukan dihitung ulang.
    # Kegagalannya tidak boleh menjatuhkan tampilan stok: lapisan itu saja yang
    # menjadi "belum dinilai", dan jawabannya menyebutnya terus terang.
    umur: dict = {}
    umur_tersedia = True
    try:
        hu = lt_router.daftar(warehouse_id=warehouse_id, status=None, q=None,
                              page=1, page_size=200, lang=lang)
        umur = {b["item"]["id"]: b for b in hu["items"]}
    except Exception:
        umur_tersedia = False
    for b in baris:
        m = mesin.get(b["item_id"])
        b["status"] = status_dari_aksi(m["action_status"] if m else None)
        # Rekomendasi mesin ikut dibawa apa adanya untuk panel detail.
        b["decision"] = None if m is None else {
            "status_label": m["action_status_label"],
            "recommended_order_qty": m["recommended_order_qty"],
            "days_of_cover": m["days_of_cover_int"],
            "effective_reorder_point": m["effective_reorder_point_int"],
            "available_stock": m["available_stock_int"],
            "forecast_usage": m["forecast_usage_int"],
            "horizon_days": m["decision_horizon_days"],
            "priority_label": m["priority_label"],
        }
    for b in baris:
        u = umur.get(b["item_id"])
        b["lifetime"] = None if u is None else {
            "status": u["status"],
            "status_label": u["status_label"],
            "deviation_percentage": u["deviation_percentage"],
            "has_reference": u["has_reference"],
            "basis": u["basis"],
        }
    return {
        "warehouse": gudang,
        "lifetime_available": umur_tersedia,
        "items": baris,
        "truncated": hasil["truncated"],
        "location_mapping": {"available": False, "source": "none"},
    }
