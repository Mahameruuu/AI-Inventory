# -*- coding: utf-8 -*-
"""Stok berjalan, stok menipis, dan buku besar pergerakan."""

from datetime import date

from fastapi import APIRouter, Query

from ..common import JENIS_PEMAKAIAN, PAGE_SIZE_DEFAULT, clamp_page, page_envelope
from ..db import readonly
from ..errors import invalid

router = APIRouter(tags=["inventory"])

# Ambang stok menipis: reorder_point bila diisi, kalau tidak minimum_stock.
AMBANG = "COALESCE(NULLIF(it.reorder_point, 0), it.minimum_stock)"


@router.get("/api/inventory")
def list_inventory(
    q: str | None = Query(None, description="Cari SKU atau nama barang"),
    warehouse_id: int | None = None,
    usage_type: str | None = Query(
        None, description="berumur_pakai atau habis_pakai; kosong = semuanya"),
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if usage_type:
        if usage_type not in JENIS_PEMAKAIAN:
            raise invalid(f"usage_type harus salah satu dari: "
                          f"{', '.join(JENIS_PEMAKAIAN)}", "usage_type")
        where += " AND it.usage_type = %s"
        params.append(usage_type)
    if q:
        where += " AND (it.sku ILIKE %s OR it.name ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if warehouse_id:
        where += " AND inv.warehouse_id = %s"
        params.append(warehouse_id)

    base = """
        FROM inventory inv
        JOIN items it      ON it.id = inv.item_id
        JOIN warehouses w  ON w.id = inv.warehouse_id
        JOIN units u       ON u.id = it.unit_id
    """
    with readonly() as cur:
        cur.execute(
            f"""SELECT count(*) AS n,
                       COALESCE(SUM(inv.quantity), 0) AS total_stock,
                       COALESCE(SUM(inv.quantity * it.unit_price), 0) AS total_value
                {base} {where}""",
            params,
        )
        ringkas = cur.fetchone()
        cur.execute(
            f"""
            SELECT inv.id, it.id AS item_id, it.sku, it.name AS item_name,
                   it.usage_type,
                   u.code AS unit_code, w.id AS warehouse_id, w.code AS warehouse_code,
                   w.name AS warehouse_name,
                   inv.quantity, inv.reserved_quantity, inv.available_quantity,
                   it.unit_price, (inv.quantity * it.unit_price) AS stock_value,
                   it.minimum_stock, it.reorder_point, inv.updated_at,
                   (inv.quantity <= {AMBANG}) AS is_low_stock,
                   -- Pergerakan terakhir yang sesungguhnya. inventory.updated_at
                   -- TIDAK bisa dipakai untuk ini: pada data hasil impor massal
                   -- seluruh barisnya bertanggal sama, yaitu hari impor, bukan
                   -- hari barang itu terakhir bergerak. LATERAL dengan LIMIT 1
                   -- memakai indeks (item_id, warehouse_id, movement_date),
                   -- jadi biayanya satu penelusuran indeks per baris halaman.
                   g.movement_date AS last_movement_date
            {base}
            LEFT JOIN LATERAL (
                SELECT sm.movement_date FROM stock_movements sm
                WHERE sm.item_id = inv.item_id AND sm.warehouse_id = inv.warehouse_id
                ORDER BY sm.movement_date DESC LIMIT 1
            ) g ON true
            {where}
            ORDER BY it.sku, w.code
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        hasil = page_envelope(cur.fetchall(), ringkas["n"], page, page_size)

    hasil["summary"] = {
        "total_stock": ringkas["total_stock"],
        "total_value": ringkas["total_value"],
    }
    return hasil


@router.get("/api/inventory/low-stock")
def low_stock(warehouse_id: int | None = None, page: int = 1, page_size: int = PAGE_SIZE_DEFAULT) -> dict:
    """
    Barang yang stoknya sudah menyentuh atau turun di bawah ambang.

    Ambangnya reorder_point; bila belum diisi dipakai minimum_stock. Barang
    yang kedua-duanya nol tidak pernah dianggap menipis -- tanpa aturan itu,
    setiap barang berstok nol akan selalu muncul.
    """
    page, page_size, offset = clamp_page(page, page_size)
    where, params = f"WHERE {AMBANG} > 0 AND inv.quantity <= {AMBANG}", []
    if warehouse_id:
        where += " AND inv.warehouse_id = %s"
        params.append(warehouse_id)

    base = """
        FROM inventory inv
        JOIN items it     ON it.id = inv.item_id
        JOIN warehouses w ON w.id = inv.warehouse_id
        JOIN units u      ON u.id = it.unit_id
    """
    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n {base} {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT it.id AS item_id, it.sku, it.name AS item_name, u.code AS unit_code,
                   w.id AS warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name,
                   inv.quantity, inv.available_quantity,
                   it.minimum_stock, it.reorder_point, it.criticality,
                   {AMBANG} AS threshold,
                   ({AMBANG} - inv.quantity) AS shortage,
                   CASE WHEN inv.quantity <= 0 THEN 'habis'
                        WHEN inv.quantity <= it.minimum_stock THEN 'kritis'
                        ELSE 'menipis' END AS severity
            {base} {where}
            ORDER BY (inv.quantity - {AMBANG}), it.sku
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        return page_envelope(cur.fetchall(), total, page, page_size)


@router.get("/api/stock-movements")
def list_movements(
    item_id: int | None = None,
    warehouse_id: int | None = None,
    movement_type: str | None = Query(None, description="stock_in | stock_out | ..."),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if item_id:
        where += " AND m.item_id = %s"
        params.append(item_id)
    if warehouse_id:
        where += " AND m.warehouse_id = %s"
        params.append(warehouse_id)
    if movement_type:
        where += " AND m.movement_type = %s"
        params.append(movement_type)
    if date_from:
        where += " AND m.movement_date >= %s"
        params.append(date_from)
    if date_to:
        where += " AND m.movement_date < (%s::date + 1)"
        params.append(date_to)

    base = """
        FROM stock_movements m
        JOIN items it     ON it.id = m.item_id
        JOIN warehouses w ON w.id = m.warehouse_id
    """
    with readonly() as cur:
        cur.execute(
            f"""SELECT count(*) AS n,
                       COALESCE(SUM(m.quantity) FILTER (WHERE m.quantity > 0), 0) AS total_in,
                       COALESCE(-SUM(m.quantity) FILTER (WHERE m.quantity < 0), 0) AS total_out
                {base} {where}""",
            params,
        )
        ringkas = cur.fetchone()
        cur.execute(
            f"""
            SELECT m.id, m.movement_type, m.movement_date, m.quantity, m.unit_price,
                   m.batch_number, m.reference_id,
                   it.id AS item_id, it.sku, it.name AS item_name,
                   w.id AS warehouse_id, w.code AS warehouse_code,
                   CASE m.movement_type
                       WHEN 'stock_in'     THEN (SELECT receipt_number    FROM stock_receipts    r WHERE r.id = m.reference_id)
                       WHEN 'stock_out'    THEN (SELECT issue_number      FROM stock_issues      i WHERE i.id = m.reference_id)
                       WHEN 'transfer_in'  THEN (SELECT transfer_number   FROM stock_transfers   t WHERE t.id = m.reference_id)
                       WHEN 'transfer_out' THEN (SELECT transfer_number   FROM stock_transfers   t WHERE t.id = m.reference_id)
                       WHEN 'adjustment'   THEN (SELECT adjustment_number FROM stock_adjustments a WHERE a.id = m.reference_id)
                       ELSE NULL END AS reference_number
            {base} {where}
            ORDER BY m.movement_date DESC, m.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        hasil = page_envelope(cur.fetchall(), ringkas["n"], page, page_size)

    hasil["summary"] = {"total_in": ringkas["total_in"], "total_out": ringkas["total_out"]}
    return hasil
