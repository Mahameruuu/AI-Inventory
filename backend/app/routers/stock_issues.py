# -*- coding: utf-8 -*-
"""
Pengeluaran barang.

Satu permintaan menghasilkan SATU transaksi basis data yang menulis empat
tabel sekaligus:

    stock_issues -> stock_issue_items -> stock_movements -> inventory

Bedanya dengan penerimaan: pengeluaran harus MEMERIKSA ketersediaan lebih dulu.
Baris `inventory` dikunci dengan SELECT ... FOR UPDATE sebelum diperiksa, lalu
kuncinya dipegang sampai transaksi berakhir. Tanpa itu, dua permintaan yang
datang bersamaan bisa sama-sama lolos pemeriksaan dan membuat stok jadi minus.
"""

from collections import OrderedDict
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Query

from ..common import (LOCK_ISSUE, PAGE_SIZE_DEFAULT, ambil_barang_aktif,
                      ambil_gudang_aktif, clamp_page, next_document_number,
                      page_envelope)
from .. import i18n
from ..config import APP_TZ
from ..db import readonly, transaction
from ..errors import AppError, invalid, not_found
from ..schemas import StockIssueIn, StockIssueOut

router = APIRouter(prefix="/api/stock-issues", tags=["stock-issues"])


def _stok_kurang(sku: str, gudang: str, diminta: Decimal, tersedia: Decimal) -> AppError:
    return AppError(
        422,
        "INSUFFICIENT_STOCK",
        i18n.t("err.insufficient_stock", i18n.bahasa_permintaan(),
               sku=sku, gudang=gudang,
               diminta=f"{diminta:.3f}", tersedia=f"{tersedia:.3f}"),
        "items.quantity",
    )


@router.post("", response_model=StockIssueOut, status_code=201)
def create_stock_issue(payload: StockIssueIn) -> StockIssueOut:
    if payload.issue_date > datetime.now(APP_TZ).date():
        raise invalid(i18n.t("err.date_future_issue", i18n.bahasa_permintaan()),
                      "issue_date")

    sekarang = datetime.now(APP_TZ)
    stempel = datetime.combine(payload.issue_date, sekarang.timetz())

    # Satu barang boleh muncul di beberapa baris. Kebutuhannya dijumlahkan dulu,
    # karena yang harus diuji terhadap stok adalah TOTALNYA -- kalau diperiksa
    # per baris, dua baris @30 bisa sama-sama lolos padahal stok hanya 50.
    kebutuhan: "OrderedDict[int, Decimal]" = OrderedDict()
    for baris in payload.items:
        kebutuhan[baris.item_id] = kebutuhan.get(baris.item_id, Decimal("0")) + baris.quantity

    with transaction() as cur:
        gudang = ambil_gudang_aktif(cur, payload.warehouse_id)
        barang = ambil_barang_aktif(cur, list(kebutuhan.keys()))

        # --- kunci baris stok lalu periksa ketersediaan ---
        # Urut menaik berdasarkan item_id agar dua transaksi yang mengambil
        # barang sama tidak saling mengunci dari arah berlawanan (deadlock).
        sebelum: dict[int, dict] = {}
        for item_id in sorted(kebutuhan.keys()):
            cur.execute(
                """
                SELECT quantity, reserved_quantity, available_quantity
                FROM inventory
                WHERE item_id = %s AND warehouse_id = %s
                FOR UPDATE
                """,
                (item_id, payload.warehouse_id),
            )
            stok = cur.fetchone()
            diminta = kebutuhan[item_id]
            sku = barang[item_id]["sku"]

            if stok is None:
                raise _stok_kurang(sku, gudang["name"], diminta, Decimal("0"))
            if diminta > stok["available_quantity"]:
                raise _stok_kurang(sku, gudang["name"], diminta, stok["available_quantity"])
            # Penjaga kedua: saldo fisik tidak boleh menjadi minus walaupun
            # available_quantity kebetulan tercatat lebih besar dari quantity.
            if diminta > stok["quantity"]:
                raise _stok_kurang(sku, gudang["name"], diminta, stok["quantity"])

            sebelum[item_id] = stok

        issue_number = next_document_number(
            cur,
            table="stock_issues",
            column="issue_number",
            prefix="ISS",
            tanggal=payload.issue_date,
            lock_namespace=LOCK_ISSUE,
        )

        # 1. header pengeluaran
        cur.execute(
            """
            INSERT INTO stock_issues
                (issue_number, warehouse_id, issue_date, purpose,
                 reference_number, status, notes)
            VALUES (%s, %s, %s, %s, %s, 'completed', %s)
            RETURNING id
            """,
            (
                issue_number,
                payload.warehouse_id,
                stempel,
                payload.purpose,
                payload.reference_number,
                payload.notes,
            ),
        )
        issue_id = cur.fetchone()["id"]

        total_quantity = Decimal("0")

        for baris in payload.items:
            # 2. rincian barang yang dikeluarkan -- selalu POSITIF, sesuai
            # CHECK pada tabel; arah keluarnya dicatat di ledger.
            cur.execute(
                """
                INSERT INTO stock_issue_items (stock_issue_id, item_id, quantity)
                VALUES (%s, %s, %s)
                """,
                (issue_id, baris.item_id, baris.quantity),
            )

            # 3. catatan pergerakan stok -- keluar, jadi kuantitasnya NEGATIF.
            # unit_price sengaja dikosongkan: menentukan harga pokok barang
            # keluar adalah perhitungan valuasi, yang belum menjadi lingkup
            # tahap ini.
            cur.execute(
                """
                INSERT INTO stock_movements
                    (item_id, warehouse_id, movement_type, reference_id,
                     movement_date, quantity, unit_price, batch_number)
                VALUES (%s, %s, 'stock_out', %s, %s, %s, NULL, NULL)
                """,
                (baris.item_id, payload.warehouse_id, issue_id, stempel, -baris.quantity),
            )
            total_quantity += baris.quantity

        # 4-5. kurangi saldo, lalu hitung ulang yang tersedia
        sesudah: dict[int, dict] = {}
        for item_id, diminta in kebutuhan.items():
            cur.execute(
                """
                UPDATE inventory
                SET quantity           = quantity - %s,
                    available_quantity = quantity - %s - reserved_quantity,
                    updated_at         = now()
                WHERE item_id = %s AND warehouse_id = %s
                RETURNING quantity, reserved_quantity, available_quantity
                """,
                (diminta, diminta, item_id, payload.warehouse_id),
            )
            sesudah[item_id] = cur.fetchone()

    return StockIssueOut(
        issue_id=issue_id,
        issue_number=issue_number,
        warehouse={"id": gudang["id"], "code": gudang["code"], "name": gudang["name"]},
        item_count=len(payload.items),
        total_quantity=f"{total_quantity:.3f}",
        lines=[
            {
                "item_id": item_id,
                "sku": barang[item_id]["sku"],
                "quantity_issued": f"{kebutuhan[item_id]:.3f}",
                "quantity_before": f"{sebelum[item_id]['quantity']:.3f}",
                "quantity_after": f"{sesudah[item_id]['quantity']:.3f}",
                "available_after": f"{sesudah[item_id]['available_quantity']:.3f}",
            }
            for item_id in kebutuhan
        ],
    )


@router.get("")
def list_stock_issues(
    q: str | None = Query(None, description="Cari nomor issue atau nomor referensi"),
    warehouse_id: int | None = None,
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if q:
        where += " AND (i.issue_number ILIKE %s OR i.reference_number ILIKE %s OR i.purpose ILIKE %s)"
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if warehouse_id:
        where += " AND i.warehouse_id = %s"
        params.append(warehouse_id)
    if date_from:
        where += " AND i.issue_date >= %s"
        params.append(date_from)
    if date_to:
        where += " AND i.issue_date < (%s::date + 1)"
        params.append(date_to)

    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM stock_issues i {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT i.id, i.issue_number, i.issue_date, i.purpose, i.reference_number,
                   i.status, i.notes,
                   w.id AS warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name,
                   COALESCE(d.line_count, 0) AS line_count,
                   COALESCE(d.total_quantity, 0) AS total_quantity
            FROM stock_issues i
            JOIN warehouses w ON w.id = i.warehouse_id
            LEFT JOIN (
                SELECT stock_issue_id, count(*) AS line_count, SUM(quantity) AS total_quantity
                FROM stock_issue_items GROUP BY stock_issue_id
            ) d ON d.stock_issue_id = i.id
            {where}
            ORDER BY i.issue_date DESC, i.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        return page_envelope(cur.fetchall(), total, page, page_size)


@router.get("/{issue_id}")
def get_stock_issue(issue_id: int) -> dict:
    with readonly() as cur:
        cur.execute(
            """
            SELECT i.id, i.issue_number, i.issue_date, i.purpose, i.reference_number,
                   i.status, i.notes, i.created_at,
                   w.id AS warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name
            FROM stock_issues i JOIN warehouses w ON w.id = i.warehouse_id
            WHERE i.id = %s
            """,
            (issue_id,),
        )
        header = cur.fetchone()
        if header is None:
            raise not_found("issue", issue_id)

        cur.execute(
            """
            SELECT ii.id, ii.item_id, it.sku, it.name AS item_name, u.code AS unit_code,
                   ii.quantity
            FROM stock_issue_items ii
            JOIN items it ON it.id = ii.item_id
            JOIN units u  ON u.id = it.unit_id
            WHERE ii.stock_issue_id = %s ORDER BY ii.id
            """,
            (issue_id,),
        )
        lines = cur.fetchall()

        cur.execute(
            """
            SELECT m.id, m.movement_type, m.movement_date, m.quantity, it.sku
            FROM stock_movements m JOIN items it ON it.id = m.item_id
            WHERE m.movement_type = 'stock_out' AND m.reference_id = %s ORDER BY m.id
            """,
            (issue_id,),
        )
        movements = cur.fetchall()

    return {
        "issue": header,
        "lines": lines,
        "movements": movements,
        "summary": {
            "line_count": len(lines),
            "total_quantity": sum(r["quantity"] for r in lines),
        },
    }
