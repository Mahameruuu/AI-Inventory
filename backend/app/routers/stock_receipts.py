# -*- coding: utf-8 -*-
"""
Penerimaan barang.

Satu permintaan menghasilkan SATU transaksi basis data yang menulis empat
tabel sekaligus:

    stock_receipts -> stock_receipt_items -> stock_movements -> inventory

Basis data tidak punya trigger maupun function, jadi seluruh rangkaian itu
ditulis secara eksplisit -- di app/penerimaan.py, bukan di sini. Ia dipindah ke
sana ketika penerimaan juga dapat lahir dari PO yang ditandai diterima: dua
pemanggil untuk satu rangkaian yang menaikkan stok, dan menyalinnya berarti dua
tempat yang harus sama-sama benar selamanya.

Yang tinggal di berkas ini adalah pemeriksaan masukan formulir dan bentuk
jawabannya. Bila satu langkah gagal, blok `transaction()` melakukan ROLLBACK
dan tidak ada satu pun baris yang tersisa.
"""

from datetime import datetime

from datetime import date as date_type

from fastapi import APIRouter, Query

from ..common import (PAGE_SIZE_DEFAULT, ambil_barang_aktif,
                      ambil_gudang_aktif, ambil_supplier_aktif, clamp_page,
                      page_envelope)
from ..penerimaan import catat_penerimaan
from .. import i18n
from ..config import APP_TZ
from ..db import readonly, transaction
from ..errors import invalid, not_found
from ..schemas import StockReceiptIn, StockReceiptOut

router = APIRouter(prefix="/api/stock-receipts", tags=["stock-receipts"])


def _validate_master(cur, payload: StockReceiptIn) -> dict:
    """Memastikan gudang, supplier, dan seluruh barang ada serta masih aktif."""
    gudang = ambil_gudang_aktif(cur, payload.warehouse_id)
    ambil_supplier_aktif(cur, payload.supplier_id)
    ambil_barang_aktif(cur, list({it.item_id for it in payload.items}))
    return gudang


@router.post("", response_model=StockReceiptOut, status_code=201)
def create_stock_receipt(payload: StockReceiptIn) -> StockReceiptOut:
    if payload.received_date > datetime.now(APP_TZ).date():
        raise invalid(i18n.t("err.date_future_receipt", i18n.bahasa_permintaan()),
                      "received_date")

    # Tanggal dari permintaan digabung dengan jam saat diproses, supaya urutan
    # transaksi dalam satu hari tetap dapat ditelusuri pada ledger.
    sekarang = datetime.now(APP_TZ)
    stempel = datetime.combine(payload.received_date, sekarang.timetz())

    with transaction() as cur:
        gudang = _validate_master(cur, payload)
        hasil = catat_penerimaan(
            cur,
            warehouse_id=payload.warehouse_id,
            supplier_id=payload.supplier_id,
            received_date=payload.received_date,
            stempel=stempel,
            reference_number=payload.reference_number,
            notes=payload.notes,
            baris=[
                {
                    "item_id": b.item_id,
                    "quantity": b.quantity,
                    "unit_price": b.unit_price,
                    "batch_number": b.batch_number,
                    "serial_number": b.serial_number,
                    "expiry_date": b.expiry_date,
                }
                for b in payload.items
            ],
        )

    return StockReceiptOut(
        receipt_id=hasil["receipt_id"],
        receipt_number=hasil["receipt_number"],
        warehouse={"id": gudang["id"], "code": gudang["code"], "name": gudang["name"]},
        item_count=hasil["item_count"],
        total_quantity=f"{hasil['total_quantity']:.3f}",
        total_value=f"{hasil['total_value']:.2f}",
    )


@router.get("")
def list_stock_receipts(
    q: str | None = Query(None, description="Cari nomor receipt atau nomor referensi"),
    warehouse_id: int | None = None,
    supplier_id: int | None = None,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if q:
        where += " AND (r.receipt_number ILIKE %s OR r.reference_number ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if warehouse_id:
        where += " AND r.warehouse_id = %s"
        params.append(warehouse_id)
    if supplier_id:
        where += " AND r.supplier_id = %s"
        params.append(supplier_id)
    if date_from:
        where += " AND r.receipt_date >= %s"
        params.append(date_from)
    if date_to:
        where += " AND r.receipt_date < (%s::date + 1)"
        params.append(date_to)

    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM stock_receipts r {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT r.id, r.receipt_number, r.receipt_date, r.reference_number,
                   r.status, r.notes,
                   s.id AS supplier_id, s.name AS supplier_name,
                   w.id AS warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name,
                   COALESCE(d.line_count, 0)   AS line_count,
                   COALESCE(d.total_quantity, 0) AS total_quantity,
                   COALESCE(d.total_value, 0)  AS total_value
            FROM stock_receipts r
            JOIN suppliers s  ON s.id = r.supplier_id
            JOIN warehouses w ON w.id = r.warehouse_id
            LEFT JOIN (
                SELECT stock_receipt_id, count(*) AS line_count,
                       SUM(quantity) AS total_quantity,
                       SUM(quantity * unit_price) AS total_value
                FROM stock_receipt_items GROUP BY stock_receipt_id
            ) d ON d.stock_receipt_id = r.id
            {where}
            ORDER BY r.receipt_date DESC, r.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        return page_envelope(cur.fetchall(), total, page, page_size)


@router.get("/{receipt_id}")
def get_stock_receipt(receipt_id: int) -> dict:
    with readonly() as cur:
        cur.execute(
            """
            SELECT r.id, r.receipt_number, r.receipt_date, r.reference_number,
                   r.status, r.notes, r.created_at,
                   s.id AS supplier_id, s.code AS supplier_code, s.name AS supplier_name,
                   w.id AS warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name
            FROM stock_receipts r
            JOIN suppliers s  ON s.id = r.supplier_id
            JOIN warehouses w ON w.id = r.warehouse_id
            WHERE r.id = %s
            """,
            (receipt_id,),
        )
        header = cur.fetchone()
        if header is None:
            raise not_found("receipt", receipt_id)

        cur.execute(
            """
            SELECT ri.id, ri.item_id, it.sku, it.name AS item_name, u.code AS unit_code,
                   ri.quantity, ri.unit_price, (ri.quantity * ri.unit_price) AS line_value,
                   ri.batch_number, ri.serial_number, ri.received_date, ri.expiry_date
            FROM stock_receipt_items ri
            JOIN items it ON it.id = ri.item_id
            JOIN units u  ON u.id = it.unit_id
            WHERE ri.stock_receipt_id = %s ORDER BY ri.id
            """,
            (receipt_id,),
        )
        lines = cur.fetchall()

        cur.execute(
            """
            SELECT m.id, m.movement_type, m.movement_date, m.quantity, it.sku
            FROM stock_movements m JOIN items it ON it.id = m.item_id
            WHERE m.movement_type = 'stock_in' AND m.reference_id = %s ORDER BY m.id
            """,
            (receipt_id,),
        )
        movements = cur.fetchall()

    total_quantity = sum(r["quantity"] for r in lines)
    total_value = sum(r["line_value"] for r in lines)
    return {
        "receipt": header,
        "lines": lines,
        "movements": movements,
        "summary": {
            "line_count": len(lines),
            "total_quantity": total_quantity,
            "total_value": total_value,
        },
    }
