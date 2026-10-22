# -*- coding: utf-8 -*-
"""
Stok opname: hitung fisik, bandingkan, setujui, lalu koreksi.

    POST  /api/stock-opname                 buat draft; stok sistem dibekukan
    PATCH /api/stock-opname/{id}/lines      isi hasil hitung (boleh bertahap)
    POST  /api/stock-opname/{id}/post       setujui -> selisih masuk ledger
    POST  /api/stock-opname/{id}/cancel     batalkan draft

PEMBAGIAN PERAN. Staf boleh membuat dan mengisi hitungan; yang memposting
hanya admin/owner. Posting MENGUBAH stok tanpa barang bergerak sama sekali,
jadi ia butuh orang kedua -- inilah satu-satunya jalan stok berubah tanpa
dokumen penerimaan atau pengeluaran.

SELISIH DIHITUNG SAAT POSTING, BUKAN SAAT DRAFT DIBUAT. Menghitung satu gudang
bisa makan berjam-jam, dan selama itu penerimaan dan pengeluaran tetap
berjalan. Bila selisihnya diukur terhadap angka yang dibekukan saat draft
dibuat, barang yang keluar di tengah penghitungan akan "dikembalikan" oleh
opname. Karena itu saat posting stok sistem dibaca ulang (dengan kunci), dan
stok akhirnya disetel SAMA DENGAN hasil hitung. Angka beku saat draft tetap
ditampilkan sebagai pembanding, dan layar memperingatkan bila keduanya sudah
berbeda.
"""

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .. import i18n
from ..auth import wajib_admin, wajib_penulis
from ..common import (LOCK_ADJUSTMENT, PAGE_SIZE_DEFAULT, ambil_gudang_aktif,
                      clamp_page, next_document_number, page_envelope)
from ..config import APP_TZ
from ..db import readonly, transaction
from ..errors import AppError, invalid, not_found

router = APIRouter(prefix="/api/stock-opname", tags=["stock-opname"])

PREFIX = "OPN"


class OpnameIn(BaseModel):
    warehouse_id: int = Field(..., gt=0)
    notes: str | None = Field(default=None, max_length=2000)


class HitunganIn(BaseModel):
    item_id: int = Field(..., gt=0)
    # None mengosongkan hitungan (kembali "belum dihitung").
    actual_quantity: Decimal | None = Field(default=None, ge=0, max_digits=18, decimal_places=3)
    note: str | None = Field(default=None, max_length=255)


class HitunganBatchIn(BaseModel):
    lines: list[HitunganIn] = Field(..., min_length=1, max_length=2000)


def _kunci_draft(cur, adj_id: int) -> dict:
    cur.execute(
        "SELECT id, adjustment_number, warehouse_id, status FROM stock_adjustments"
        " WHERE id = %s AND reason = 'stock_opname' FOR UPDATE",
        (adj_id,),
    )
    dok = cur.fetchone()
    if dok is None:
        raise not_found("adjustment", adj_id)
    if dok["status"] != "draft":
        raise AppError(409, "NOT_DRAFT", i18n.t(
            "err.opname.not_draft", i18n.bahasa_permintaan(),
            no=dok["adjustment_number"], status=dok["status"]))
    return dok


@router.post("", status_code=201, dependencies=[Depends(wajib_penulis)])
def buat_opname(payload: OpnameIn) -> dict:
    """Draft berisi SEMUA barang aktif yang punya baris stok di gudang itu."""
    sekarang = datetime.now(APP_TZ)
    with transaction() as cur:
        gudang = ambil_gudang_aktif(cur, payload.warehouse_id)
        nomor = next_document_number(
            cur, table="stock_adjustments", column="adjustment_number",
            prefix=PREFIX, tanggal=sekarang.date(), lock_namespace=LOCK_ADJUSTMENT)
        cur.execute(
            """
            INSERT INTO stock_adjustments
                (adjustment_number, warehouse_id, adjustment_date, reason, status, notes)
            VALUES (%s, %s, %s, 'stock_opname', 'draft', %s)
            RETURNING id
            """,
            (nomor, gudang["id"], sekarang, payload.notes),
        )
        adj_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO stock_adjustment_items (stock_adjustment_id, item_id, system_quantity)
            SELECT %s, inv.item_id, inv.quantity
            FROM inventory inv JOIN items it ON it.id = inv.item_id
            WHERE inv.warehouse_id = %s AND it.is_active
            ORDER BY it.sku
            """,
            (adj_id, gudang["id"]),
        )
        if cur.rowcount == 0:
            raise invalid(i18n.t("err.opname.no_items", i18n.bahasa_permintaan()),
                          "warehouse_id")
        jumlah = cur.rowcount
    return {"id": adj_id, "adjustment_number": nomor, "line_count": jumlah}


@router.patch("/{adj_id}/lines", dependencies=[Depends(wajib_penulis)])
def isi_hitungan(adj_id: int, payload: HitunganBatchIn) -> dict:
    """
    Mengisi hitungan untuk satu atau banyak barang.

    Barang yang belum ada di draft (mis. ditemukan di rak padahal tidak pernah
    tercatat di gudang ini) ditambahkan dengan stok sistem nol.
    """
    with transaction() as cur:
        dok = _kunci_draft(cur, adj_id)
        baru = [b.item_id for b in payload.lines]
        cur.execute("SELECT item_id FROM stock_adjustment_items WHERE stock_adjustment_id = %s",
                    (adj_id,))
        sudah = {r["item_id"] for r in cur.fetchall()}
        tambahan = [i for i in baru if i not in sudah]
        if tambahan:
            cur.execute("SELECT id, sku, is_active FROM items WHERE id = ANY(%s)", (tambahan,))
            ada = {r["id"]: r for r in cur.fetchall()}
            for iid in tambahan:
                if iid not in ada:
                    raise not_found("item", iid, "lines.item_id")
            for iid in dict.fromkeys(tambahan):
                cur.execute(
                    """
                    INSERT INTO stock_adjustment_items (stock_adjustment_id, item_id, system_quantity)
                    VALUES (%s, %s, COALESCE((SELECT quantity FROM inventory
                                              WHERE item_id = %s AND warehouse_id = %s), 0))
                    """,
                    (adj_id, iid, iid, dok["warehouse_id"]),
                )

        for b in payload.lines:
            cur.execute(
                """
                UPDATE stock_adjustment_items
                SET actual_quantity     = %s::numeric,
                    difference_quantity = %s::numeric - system_quantity,
                    note                = %s,
                    counted_by          = NULLIF(current_setting('app.user_id', true), '')::bigint,
                    counted_at          = CASE WHEN %s::numeric IS NULL THEN NULL ELSE now() END,
                    updated_at          = now()
                WHERE stock_adjustment_id = %s AND item_id = %s
                """,
                (b.actual_quantity, b.actual_quantity, b.note, b.actual_quantity,
                 adj_id, b.item_id),
            )
        cur.execute("UPDATE stock_adjustments SET updated_at = now() WHERE id = %s", (adj_id,))
    return get_opname(adj_id)


@router.post("/{adj_id}/post", dependencies=[Depends(wajib_admin)])
def posting_opname(adj_id: int) -> dict:
    """
    Menyetujui opname: stok tiap barang yang dihitung disetel sama dengan hasil
    hitungnya, dan selisihnya dicatat di ledger sebagai 'adjustment'. Barang
    yang belum dihitung dilewati -- stoknya tidak disentuh.
    """
    sekarang = datetime.now(APP_TZ)
    lang = i18n.bahasa_permintaan()
    with transaction() as cur:
        dok = _kunci_draft(cur, adj_id)
        cur.execute(
            """
            SELECT ai.id, ai.item_id, ai.actual_quantity, it.sku
            FROM stock_adjustment_items ai JOIN items it ON it.id = ai.item_id
            WHERE ai.stock_adjustment_id = %s AND ai.actual_quantity IS NOT NULL
            ORDER BY ai.item_id
            """,
            (adj_id,),
        )
        baris = cur.fetchall()
        if not baris:
            raise invalid(i18n.t("err.opname.nothing_counted", lang))

        disesuaikan = 0
        for b in baris:
            # Kunci urut item_id, sama seperti pengeluaran, supaya tidak saling
            # mengunci dari arah berlawanan.
            cur.execute(
                "SELECT quantity, reserved_quantity FROM inventory"
                " WHERE item_id = %s AND warehouse_id = %s FOR UPDATE",
                (b["item_id"], dok["warehouse_id"]),
            )
            stok = cur.fetchone()
            sistem = stok["quantity"] if stok else Decimal("0")
            cadang = stok["reserved_quantity"] if stok else Decimal("0")
            aktual = b["actual_quantity"]
            if aktual < cadang:
                raise AppError(422, "BELOW_RESERVED", i18n.t(
                    "err.opname.below_reserved", lang, sku=b["sku"],
                    aktual=f"{aktual:.3f}", cadang=f"{cadang:.3f}"), "lines.actual_quantity")
            selisih = aktual - sistem

            cur.execute(
                """
                UPDATE stock_adjustment_items
                SET system_quantity = %s, difference_quantity = %s, updated_at = now()
                WHERE id = %s
                """,
                (sistem, selisih, b["id"]),
            )
            if selisih == 0:
                continue
            disesuaikan += 1
            cur.execute(
                """
                INSERT INTO stock_movements
                    (item_id, warehouse_id, movement_type, reference_id, movement_date, quantity)
                VALUES (%s, %s, 'adjustment', %s, %s, %s)
                """,
                (b["item_id"], dok["warehouse_id"], adj_id, sekarang, selisih),
            )
            if stok is None:
                cur.execute(
                    """
                    INSERT INTO inventory (item_id, warehouse_id, quantity,
                                           reserved_quantity, available_quantity)
                    VALUES (%s, %s, %s, 0, %s)
                    """,
                    (b["item_id"], dok["warehouse_id"], aktual, aktual),
                )
            else:
                cur.execute(
                    """
                    UPDATE inventory
                    SET quantity = %s, available_quantity = %s - reserved_quantity,
                        updated_at = now()
                    WHERE item_id = %s AND warehouse_id = %s
                    """,
                    (aktual, aktual, b["item_id"], dok["warehouse_id"]),
                )

        cur.execute(
            """
            UPDATE stock_adjustments
            SET status = 'completed', adjustment_date = %s,
                approved_by = NULLIF(current_setting('app.user_id', true), '')::bigint,
                approved_at = now(), updated_at = now()
            WHERE id = %s
            """,
            (sekarang, adj_id),
        )
    hasil = get_opname(adj_id)
    hasil["adjusted_count"] = disesuaikan
    return hasil


@router.post("/{adj_id}/cancel", dependencies=[Depends(wajib_penulis)])
def batalkan_opname(adj_id: int) -> dict:
    with transaction() as cur:
        _kunci_draft(cur, adj_id)
        cur.execute(
            "UPDATE stock_adjustments SET status = 'cancelled', updated_at = now() WHERE id = %s",
            (adj_id,),
        )
    return get_opname(adj_id)


@router.get("")
def daftar_opname(
    status: str | None = None,
    warehouse_id: int | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE a.reason = 'stock_opname'", []
    if status:
        where += " AND a.status = %s"
        params.append(status)
    if warehouse_id:
        where += " AND a.warehouse_id = %s"
        params.append(warehouse_id)
    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM stock_adjustments a {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT a.id, a.adjustment_number, a.adjustment_date, a.status, a.notes,
                   a.created_at, a.approved_at,
                   w.code AS warehouse_code, w.name AS warehouse_name,
                   uc.full_name AS created_by_name, ua.full_name AS approved_by_name,
                   d.line_count, d.counted_count, d.diff_count
            FROM stock_adjustments a
            JOIN warehouses w ON w.id = a.warehouse_id
            LEFT JOIN users uc ON uc.id = a.created_by
            LEFT JOIN users ua ON ua.id = a.approved_by
            LEFT JOIN LATERAL (
                SELECT count(*) AS line_count,
                       count(actual_quantity) AS counted_count,
                       count(*) FILTER (WHERE difference_quantity <> 0) AS diff_count
                FROM stock_adjustment_items WHERE stock_adjustment_id = a.id
            ) d ON true
            {where}
            ORDER BY a.created_at DESC, a.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        return page_envelope(cur.fetchall(), total, page, page_size)


@router.get("/{adj_id}")
def get_opname(adj_id: int) -> dict:
    with readonly() as cur:
        cur.execute(
            """
            SELECT a.id, a.adjustment_number, a.adjustment_date, a.status, a.notes,
                   a.created_at, a.approved_at, a.warehouse_id,
                   w.code AS warehouse_code, w.name AS warehouse_name,
                   uc.full_name AS created_by_name, ua.full_name AS approved_by_name
            FROM stock_adjustments a
            JOIN warehouses w ON w.id = a.warehouse_id
            LEFT JOIN users uc ON uc.id = a.created_by
            LEFT JOIN users ua ON ua.id = a.approved_by
            WHERE a.id = %s AND a.reason = 'stock_opname'
            """,
            (adj_id,),
        )
        dok = cur.fetchone()
        if dok is None:
            raise not_found("adjustment", adj_id)
        cur.execute(
            """
            SELECT ai.item_id, it.sku, it.name AS item_name, u.code AS unit_code,
                   it.unit_price,
                   ai.system_quantity, ai.actual_quantity, ai.difference_quantity,
                   ai.note, ai.counted_at, uc.full_name AS counted_by_name,
                   COALESCE(inv.quantity, 0) AS current_quantity
            FROM stock_adjustment_items ai
            JOIN items it ON it.id = ai.item_id
            JOIN units u  ON u.id = it.unit_id
            LEFT JOIN users uc ON uc.id = ai.counted_by
            LEFT JOIN inventory inv
                   ON inv.item_id = ai.item_id AND inv.warehouse_id = %s
            WHERE ai.stock_adjustment_id = %s
            ORDER BY it.sku
            """,
            (dok["warehouse_id"], adj_id),
        )
        baris = cur.fetchall()

    dihitung = [b for b in baris if b["actual_quantity"] is not None]
    nilai = sum(
        ((b["difference_quantity"] or 0) * (b["unit_price"] or 0) for b in dihitung),
        Decimal("0"),
    )
    return {
        "opname": dok,
        "lines": baris,
        "summary": {
            "line_count": len(baris),
            "counted_count": len(dihitung),
            "diff_count": sum(1 for b in dihitung if b["difference_quantity"]),
            # Barang yang stok sistemnya sudah bergerak sejak draft dibuat:
            # selisihnya akan dihitung ulang saat posting.
            "moved_since_draft": sum(
                1 for b in baris
                if dok["status"] == "draft" and b["current_quantity"] != b["system_quantity"]),
            "difference_value": nilai,
        },
    }
