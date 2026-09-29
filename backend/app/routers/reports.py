# -*- coding: utf-8 -*-
"""
Laporan.

Seluruh angka dihitung langsung dari tabel operasional -- tidak ada tabel
laporan tersendiri, sesuai keputusan skema. Nilai memakai harga referensi
master (items.unit_price) untuk stok, dan harga transaksi sebenarnya untuk
penerimaan.
"""

from datetime import date

from fastapi import APIRouter, Query

from .. import i18n
from ..db import readonly

router = APIRouter(prefix="/api/reports", tags=["reports"])

AMBANG = "COALESCE(NULLIF(it.reorder_point, 0), it.minimum_stock)"


@router.get("/stock")
def stock_report(
    warehouse_id: int | None = None,
    lang: str = Query(i18n.BAHASA_BAWAAN,
                      description="Bahasa keterangan dasar nilai: id atau en."),
) -> dict:
    where, params = "WHERE 1=1", []
    if warehouse_id:
        where += " AND inv.warehouse_id = %s"
        params.append(warehouse_id)

    with readonly() as cur:
        cur.execute(
            f"""
            SELECT count(*) AS baris_stok,
                   COALESCE(SUM(inv.quantity), 0) AS total_quantity,
                   COALESCE(SUM(inv.reserved_quantity), 0) AS total_reserved,
                   COALESCE(SUM(inv.quantity * it.unit_price), 0) AS total_value,
                   count(*) FILTER (WHERE {AMBANG} > 0 AND inv.quantity <= {AMBANG}) AS low_stock
            FROM inventory inv JOIN items it ON it.id = inv.item_id {where}
            """,
            params,
        )
        summary = cur.fetchone()

        cur.execute(
            f"""
            SELECT w.code AS warehouse_code, w.name AS warehouse_name,
                   count(*) AS item_count,
                   COALESCE(SUM(inv.quantity), 0) AS total_quantity,
                   COALESCE(SUM(inv.quantity * it.unit_price), 0) AS total_value
            FROM inventory inv
            JOIN items it ON it.id = inv.item_id
            JOIN warehouses w ON w.id = inv.warehouse_id {where}
            GROUP BY w.code, w.name ORDER BY total_value DESC
            """,
            params,
        )
        by_warehouse = cur.fetchall()

        cur.execute(
            f"""
            SELECT c.name AS category_name, count(*) AS item_count,
                   COALESCE(SUM(inv.quantity), 0) AS total_quantity,
                   COALESCE(SUM(inv.quantity * it.unit_price), 0) AS total_value
            FROM inventory inv
            JOIN items it ON it.id = inv.item_id
            JOIN categories c ON c.id = it.category_id {where}
            GROUP BY c.name ORDER BY total_value DESC
            """,
            params,
        )
        by_category = cur.fetchall()

        cur.execute(
            f"""
            SELECT it.sku, it.name AS item_name, w.code AS warehouse_code,
                   inv.quantity, inv.reserved_quantity, inv.available_quantity,
                   it.unit_price, (inv.quantity * it.unit_price) AS stock_value,
                   ({AMBANG} > 0 AND inv.quantity <= {AMBANG}) AS is_low_stock
            FROM inventory inv
            JOIN items it ON it.id = inv.item_id
            JOIN warehouses w ON w.id = inv.warehouse_id {where}
            ORDER BY stock_value DESC LIMIT 200
            """,
            params,
        )
        rows = cur.fetchall()

    return {
        "summary": summary,
        "by_warehouse": by_warehouse,
        "by_category": by_category,
        "rows": rows,
        "value_basis": i18n.t("reports.value_basis", lang),
    }


@router.get("/receipts")
def receipt_report(
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: int | None = None,
) -> dict:
    where, params = "WHERE 1=1", []
    if date_from:
        where += " AND r.receipt_date >= %s"
        params.append(date_from)
    if date_to:
        where += " AND r.receipt_date < (%s::date + 1)"
        params.append(date_to)
    if warehouse_id:
        where += " AND r.warehouse_id = %s"
        params.append(warehouse_id)

    base = """
        FROM stock_receipts r
        JOIN stock_receipt_items ri ON ri.stock_receipt_id = r.id
        JOIN items it     ON it.id = ri.item_id
        JOIN suppliers s  ON s.id = r.supplier_id
        JOIN warehouses w ON w.id = r.warehouse_id
    """
    with readonly() as cur:
        cur.execute(
            f"""SELECT count(DISTINCT r.id) AS receipt_count, count(*) AS line_count,
                       COALESCE(SUM(ri.quantity), 0) AS total_quantity,
                       COALESCE(SUM(ri.quantity * ri.unit_price), 0) AS total_value
                {base} {where}""",
            params,
        )
        summary = cur.fetchone()

        cur.execute(
            f"""SELECT s.name AS supplier_name, count(DISTINCT r.id) AS receipt_count,
                       COALESCE(SUM(ri.quantity), 0) AS total_quantity,
                       COALESCE(SUM(ri.quantity * ri.unit_price), 0) AS total_value
                {base} {where} GROUP BY s.name ORDER BY total_value DESC""",
            params,
        )
        by_supplier = cur.fetchall()

        cur.execute(
            f"""SELECT r.receipt_date::date AS periode, count(DISTINCT r.id) AS receipt_count,
                       COALESCE(SUM(ri.quantity), 0) AS total_quantity,
                       COALESCE(SUM(ri.quantity * ri.unit_price), 0) AS total_value
                {base} {where} GROUP BY 1 ORDER BY 1 DESC LIMIT 60""",
            params,
        )
        by_date = cur.fetchall()

        cur.execute(
            f"""SELECT it.sku, it.name AS item_name, COALESCE(SUM(ri.quantity), 0) AS total_quantity,
                       COALESCE(SUM(ri.quantity * ri.unit_price), 0) AS total_value
                {base} {where} GROUP BY it.sku, it.name ORDER BY total_value DESC LIMIT 50""",
            params,
        )
        by_item = cur.fetchall()

    return {"summary": summary, "by_supplier": by_supplier, "by_date": by_date, "by_item": by_item}


@router.get("/issues")
def issue_report(
    date_from: date | None = None,
    date_to: date | None = None,
    warehouse_id: int | None = None,
) -> dict:
    where, params = "WHERE 1=1", []
    if date_from:
        where += " AND i.issue_date >= %s"
        params.append(date_from)
    if date_to:
        where += " AND i.issue_date < (%s::date + 1)"
        params.append(date_to)
    if warehouse_id:
        where += " AND i.warehouse_id = %s"
        params.append(warehouse_id)

    base = """
        FROM stock_issues i
        JOIN stock_issue_items ii ON ii.stock_issue_id = i.id
        JOIN items it     ON it.id = ii.item_id
        JOIN warehouses w ON w.id = i.warehouse_id
    """
    with readonly() as cur:
        cur.execute(
            f"""SELECT count(DISTINCT i.id) AS issue_count, count(*) AS line_count,
                       COALESCE(SUM(ii.quantity), 0) AS total_quantity
                {base} {where}""",
            params,
        )
        summary = cur.fetchone()

        cur.execute(
            f"""SELECT COALESCE(i.purpose, 'Tanpa keterangan') AS purpose,
                       count(DISTINCT i.id) AS issue_count,
                       COALESCE(SUM(ii.quantity), 0) AS total_quantity
                {base} {where} GROUP BY 1 ORDER BY total_quantity DESC""",
            params,
        )
        by_purpose = cur.fetchall()

        cur.execute(
            f"""SELECT i.issue_date::date AS periode, count(DISTINCT i.id) AS issue_count,
                       COALESCE(SUM(ii.quantity), 0) AS total_quantity
                {base} {where} GROUP BY 1 ORDER BY 1 DESC LIMIT 60""",
            params,
        )
        by_date = cur.fetchall()

        cur.execute(
            f"""SELECT it.sku, it.name AS item_name,
                       COALESCE(SUM(ii.quantity), 0) AS total_quantity
                {base} {where} GROUP BY it.sku, it.name ORDER BY total_quantity DESC LIMIT 50""",
            params,
        )
        by_item = cur.fetchall()

    return {"summary": summary, "by_purpose": by_purpose, "by_date": by_date, "by_item": by_item}
