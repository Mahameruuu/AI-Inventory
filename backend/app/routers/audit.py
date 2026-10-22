# -*- coding: utf-8 -*-
"""
Jejak audit: siapa mengubah apa, kapan, dan nilai sebelumnya.

Hanya BACA. Barisnya ditulis trigger basis data (migrasi 036), dan role
aplikasi memang tidak punya hak menulis ke tabelnya -- tidak ada endpoint yang
bisa menambah, mengubah, atau menghapus jejak.

Terbatas pada admin/owner: isi jejak memuat data induk seluruh perusahaan,
termasuk perubahan pengguna dan peran.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query

from ..auth import wajib_admin
from ..common import PAGE_SIZE_DEFAULT, clamp_page, page_envelope
from ..db import readonly

router = APIRouter(prefix="/api/audit-log", tags=["audit"],
                   dependencies=[Depends(wajib_admin)])

# Kolom yang paling mudah dikenali orang untuk tiap tabel, dipakai sebagai
# label baris. Diambil dari jejaknya sendiri, bukan dari tabel asal, supaya
# baris yang sudah dihapus tetap terbaca namanya.
LABEL = {
    "items": "sku", "warehouses": "code", "categories": "name", "units": "code",
    "suppliers": "name", "users": "username",
    "stock_receipts": "receipt_number", "stock_issues": "issue_number",
    "stock_transfers": "transfer_number", "stock_adjustments": "adjustment_number",
    "purchase_orders": "po_number",
}


@router.get("")
def daftar_jejak(
    table: str | None = None,
    action: str | None = Query(None, pattern="^(INSERT|UPDATE|DELETE)$"),
    user_id: int | None = None,
    row_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if table:
        where += " AND a.table_name = %s"
        params.append(table)
    if action:
        where += " AND a.action = %s"
        params.append(action)
    if user_id:
        where += " AND a.user_id = %s"
        params.append(user_id)
    if row_id:
        where += " AND a.row_id = %s"
        params.append(row_id)
    if date_from:
        where += " AND a.changed_at >= %s"
        params.append(date_from)
    if date_to:
        where += " AND a.changed_at < (%s::date + 1)"
        params.append(date_to)

    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM audit_log a {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT a.id, a.table_name, a.row_id, a.action, a.changed_at,
                   a.old_data, a.new_data, a.user_id,
                   u.full_name AS user_name, u.email AS user_email
            FROM audit_log a
            LEFT JOIN users u ON u.id = a.user_id
            {where}
            ORDER BY a.changed_at DESC, a.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        rows = cur.fetchall()

        # UPDATE hanya menyimpan kolom yang berubah, jadi labelnya biasanya
        # tidak ada di jejak; ambil dari baris yang masih ada. Nama tabel dan
        # kolom berasal dari LABEL, bukan dari masukan.
        kurang: dict[str, set[int]] = {}
        for r in rows:
            kolom = LABEL.get(r["table_name"])
            sumber = {**(r["old_data"] or {}), **(r["new_data"] or {})}
            r["label"] = sumber.get(kolom) if kolom else None
            if r["label"] is None and kolom and r["row_id"]:
                kurang.setdefault(r["table_name"], set()).add(r["row_id"])
        kini: dict[tuple[str, int], str] = {}
        for tabel, ids in kurang.items():
            cur.execute(f"SELECT id, {LABEL[tabel]} AS label FROM {tabel} WHERE id = ANY(%s)",
                        (list(ids),))
            for b in cur.fetchall():
                kini[(tabel, b["id"])] = b["label"]
        for r in rows:
            if r["label"] is None:
                r["label"] = kini.get((r["table_name"], r["row_id"]))
    return page_envelope(rows, total, page, page_size)


@router.get("/filters")
def pilihan_saringan() -> dict:
    """Tabel dan pengguna yang benar-benar muncul di jejak, untuk dropdown."""
    with readonly() as cur:
        cur.execute("SELECT DISTINCT table_name FROM audit_log ORDER BY 1")
        tabel = [r["table_name"] for r in cur.fetchall()]
        cur.execute(
            """
            SELECT DISTINCT u.id, u.full_name, u.email
            FROM audit_log a JOIN users u ON u.id = a.user_id
            ORDER BY u.full_name
            """
        )
        return {"tables": tabel, "users": cur.fetchall()}
