# -*- coding: utf-8 -*-
"""
Pesanan pembelian.

PESANAN, BUKAN PENERIMAAN -- dan seluruh berkas ini ada supaya perbedaan itu
tidak pernah kabur. Satu permintaan di sini menulis DUA tabel:

    purchase_orders -> purchase_order_items

dan berhenti di situ. Tidak ada `stock_movements`, tidak ada `inventory`.
Bandingkan dengan stock_receipts.py, yang menulis empat tabel justru karena
barangnya memang sudah sampai di rak.

Perbedaan itu bukan soal rapi-rapian. Sebelum modul ini ada, satu-satunya cara
mencatat rencana pembelian adalah membuat penerimaan barang, dan itu menaikkan
`inventory.quantity` untuk barang yang belum dikirim -- stok di layar naik,
padahal raknya masih kosong, dan prakiraan yang membaca stok itu langsung
menyimpulkan tidak perlu membeli apa-apa.

PO yang lahir dari panel Reorder berstatus `draft` dan tanpa pemasok: master
barang tidak menyimpan pemasok, jadi tidak ada pemasok yang dapat dipilih
sistem tanpa mengarang. Pemasoknya diisi saat PO benar-benar diterbitkan.
"""

from datetime import date as date_type
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Query

from ..common import (LOCK_PO, PAGE_SIZE_DEFAULT, ambil_barang_aktif,
                      ambil_gudang_aktif, ambil_supplier_aktif, clamp_page,
                      next_document_number, page_envelope)
from ..config import APP_TZ
from ..db import readonly, transaction
from ..errors import invalid, not_found
from ..penerimaan import catat_penerimaan
from ..schemas import (PurchaseOrderIn, PurchaseOrderOut,
                       PurchaseOrderReceiveIn, PurchaseOrderStatusIn)

router = APIRouter(prefix="/api/purchase-orders", tags=["purchase-orders"])


@router.post("", response_model=PurchaseOrderOut, status_code=201)
def create_purchase_order(payload: PurchaseOrderIn) -> PurchaseOrderOut:
    """
    Mencatat satu pesanan pembelian. TIDAK mengubah stok sama sekali.

    Barang yang sama boleh dipesan dua kali; endpoint ini tidak menolak PO
    kembar. Menolaknya menuntut aturan yang belum ada jawabannya -- berapa lama
    dua PO dianggap kembar, dan apakah PO yang sudah dibatalkan ikut dihitung --
    dan menebak aturan itu di sini akan menghalangi pemesanan susulan yang sah.
    Pencegahan klik ganda adalah urusan layar, dan nomor PO yang dikembalikan
    di bawah adalah yang membuatnya bisa dilakukan.
    """
    sekarang = datetime.now(APP_TZ)
    tanggal = payload.order_date or sekarang.date()

    with transaction() as cur:
        gudang = ambil_gudang_aktif(cur, payload.warehouse_id)
        if payload.supplier_id is not None:
            ambil_supplier_aktif(cur, payload.supplier_id)
        barang = ambil_barang_aktif(cur, list({it.item_id for it in payload.items}))

        # Harga dan lead time diambil dari master dalam satu query, bukan satu
        # query per baris: PO berisi banyak barang adalah keadaan biasa.
        cur.execute(
            "SELECT id, unit_price, lead_time_days FROM items WHERE id = ANY(%s)",
            (list(barang.keys()),),
        )
        master = {r["id"]: r for r in cur.fetchall()}

        # Perkiraan lengkap memakai lead time TERPANJANG di antara barangnya:
        # PO baru selesai ketika baris terakhirnya datang, bukan yang pertama.
        lead = [master[i]["lead_time_days"] for i in master
                if master[i]["lead_time_days"] is not None]
        expected = tanggal + timedelta(days=int(max(lead))) if lead else None

        po_number = next_document_number(
            cur,
            table="purchase_orders",
            column="po_number",
            prefix="PO",
            tanggal=tanggal,
            lock_namespace=LOCK_PO,
        )

        cur.execute(
            """
            INSERT INTO purchase_orders
                (po_number, warehouse_id, supplier_id, order_date, expected_date,
                 status, source, notes)
            VALUES (%s, %s, %s, %s, %s, 'draft', %s, %s)
            RETURNING id
            """,
            (po_number, payload.warehouse_id, payload.supplier_id, tanggal,
             expected, payload.source, payload.notes),
        )
        po_id = cur.fetchone()["id"]

        total_qty = Decimal("0")
        total_nilai = Decimal("0")
        for baris in payload.items:
            harga = baris.unit_price
            if harga is None:
                harga = Decimal(str(master[baris.item_id]["unit_price"] or 0))
            cur.execute(
                """
                INSERT INTO purchase_order_items
                    (purchase_order_id, item_id, quantity, unit_price)
                VALUES (%s, %s, %s, %s)
                """,
                (po_id, baris.item_id, baris.quantity, harga),
            )
            total_qty += baris.quantity
            total_nilai += baris.quantity * harga

    return PurchaseOrderOut(
        purchase_order_id=po_id,
        po_number=po_number,
        status="draft",
        warehouse={"id": gudang["id"], "code": gudang["code"], "name": gudang["name"]},
        order_date=tanggal,
        expected_date=expected,
        item_count=len(payload.items),
        total_quantity=str(total_qty),
        total_value=str(total_nilai),
    )


# ------------------------------------------------------------------ #
# Alur status                                                         #
# ------------------------------------------------------------------ #
#
# draft ── kirim ──> sent ── terima ──> received
#   │                 │
#   └──── batal ──────┴──> cancelled
#
# received dan cancelled TIDAK punya jalan keluar. PO yang sudah diterima
# berarti stok sudah bertambah; mengembalikannya ke draft akan membuat catatan
# pesanan dan catatan stok bercerita hal yang berbeda tentang barang yang sama.
# Pembatalan setelah penerimaan adalah retur, persoalan tersendiri dengan
# pergerakan stoknya sendiri, dan bukan perpindahan status.
PERPINDAHAN: dict[str, set[str]] = {
    "draft": {"sent", "cancelled"},
    "sent": {"received", "cancelled"},
    "received": set(),
    "cancelled": set(),
}


def _ambil_po(cur, po_id: int, *, kunci: bool = False) -> dict:
    cur.execute(
        f"""
        SELECT po.id, po.po_number, po.status, po.warehouse_id, po.supplier_id,
               po.order_date, po.expected_date, po.stock_receipt_id
        FROM purchase_orders po WHERE po.id = %s
        {"FOR UPDATE" if kunci else ""}
        """,
        (po_id,),
    )
    row = cur.fetchone()
    if row is None:
        raise not_found("purchase_order", po_id)
    return row


def _tolak_perpindahan(dari: str, ke: str) -> None:
    if ke not in PERPINDAHAN.get(dari, set()):
        raise invalid(
            f"PO berstatus '{dari}' tidak dapat dipindahkan ke '{ke}'.", "status"
        )


@router.patch("/{po_id}/status")
def set_status(po_id: int, body: PurchaseOrderStatusIn) -> dict:
    """
    Menandai PO dikirim atau dibatalkan. TIDAK menyentuh stok.

    Menuju "sent" MEWAJIBKAN pemasok. PO yang dikirim tanpa pemasok tidak
    berarti apa-apa -- dikirim kepada siapa? -- dan pemasok itu pula yang
    nantinya wajib diisi pada penerimaan barangnya, karena
    `stock_receipts.supplier_id` tidak boleh kosong. Menuntutnya di sini, bukan
    saat penerimaan, membuat kesalahannya ketahuan sebelum barangnya berangkat.
    """
    with transaction() as cur:
        po = _ambil_po(cur, po_id, kunci=True)
        _tolak_perpindahan(po["status"], body.status)

        supplier_id = po["supplier_id"]
        if body.supplier_id is not None:
            ambil_supplier_aktif(cur, body.supplier_id)
            supplier_id = body.supplier_id

        if body.status == "sent" and supplier_id is None:
            raise invalid(
                "PO tidak dapat dikirim tanpa pemasok. Pilih pemasoknya lebih dulu.",
                "supplier_id",
            )

        cur.execute(
            "UPDATE purchase_orders SET status = %s, supplier_id = %s, updated_at = now() "
            "WHERE id = %s",
            (body.status, supplier_id, po_id),
        )

    return {
        "purchase_order_id": po_id,
        "po_number": po["po_number"],
        "status_before": po["status"],
        "status": body.status,
        "supplier_id": supplier_id,
    }


@router.post("/{po_id}/receive", status_code=201)
def receive(po_id: int, body: PurchaseOrderReceiveIn) -> dict:
    """
    Menandai PO diterima, dan MENAIKKAN STOK karenanya.

    Ini satu-satunya endpoint pada berkas ini yang menyentuh stok, dan ia tidak
    menghitung sendiri: seluruh rangkaian empat tabelnya diserahkan ke
    `catat_penerimaan()`, jalur yang sama persis dengan formulir Penerimaan
    Barang. Penerimaan lewat PO dan penerimaan lewat formulir karena itu
    mustahil menghasilkan saldo yang berbeda.

    Nomor PO ikut sebagai `reference_number` bila pemanggil tidak mengisinya,
    sehingga penerimaannya dapat ditelusuri balik ke pesanannya walau seseorang
    hanya membuka layar Penerimaan Barang.

    PO dikunci FOR UPDATE sepanjang transaksi. Dua permintaan "terima" yang
    datang bersamaan karena itu tidak dapat sama-sama lolos: yang kedua
    menunggu, lalu membaca status yang sudah 'received' dan ditolak -- bukan
    menaikkan stok dua kali.
    """
    sekarang = datetime.now(APP_TZ)
    tanggal = body.received_date or sekarang.date()
    if tanggal > sekarang.date():
        raise invalid("Tanggal penerimaan tidak boleh di masa depan.", "received_date")

    with transaction() as cur:
        po = _ambil_po(cur, po_id, kunci=True)
        _tolak_perpindahan(po["status"], "received")

        if po["supplier_id"] is None:
            raise invalid(
                "PO tidak dapat diterima tanpa pemasok pada catatannya.", "supplier_id"
            )
        gudang = ambil_gudang_aktif(cur, po["warehouse_id"])
        ambil_supplier_aktif(cur, po["supplier_id"])

        cur.execute(
            """
            SELECT item_id, quantity, unit_price
            FROM purchase_order_items WHERE purchase_order_id = %s ORDER BY id
            """,
            (po_id,),
        )
        baris = cur.fetchall()
        # Tidak akan terjadi lewat endpoint pembuatan -- yang menuntut minimal
        # satu baris -- tetapi PO tanpa baris tetap harus ditolak di sini, bukan
        # menghasilkan penerimaan kosong yang tidak menaikkan apa pun.
        if not baris:
            raise invalid("PO ini tidak memuat satu barang pun.", "items")

        ambil_barang_aktif(cur, [b["item_id"] for b in baris])

        hasil = catat_penerimaan(
            cur,
            warehouse_id=po["warehouse_id"],
            supplier_id=po["supplier_id"],
            received_date=tanggal,
            # Tanggal dari permintaan digabung dengan jam saat diproses, supaya
            # urutan transaksi dalam satu hari tetap terbaca pada ledger.
            stempel=datetime.combine(tanggal, sekarang.timetz()),
            reference_number=body.reference_number or po["po_number"],
            notes=body.notes,
            baris=[dict(b) for b in baris],
        )

        cur.execute(
            "UPDATE purchase_orders SET status = 'received', stock_receipt_id = %s, "
            "updated_at = now() WHERE id = %s",
            (hasil["receipt_id"], po_id),
        )

    return {
        "purchase_order_id": po_id,
        "po_number": po["po_number"],
        "status": "received",
        "warehouse": {"id": gudang["id"], "code": gudang["code"], "name": gudang["name"]},
        "receipt_id": hasil["receipt_id"],
        "receipt_number": hasil["receipt_number"],
        "item_count": hasil["item_count"],
        "total_quantity": f"{hasil['total_quantity']:.3f}",
        "total_value": f"{hasil['total_value']:.2f}",
    }


# ------------------------------------------------------------------ #
# Pembacaan                                                           #
# ------------------------------------------------------------------ #

@router.get("")
def list_purchase_orders(
    q: str | None = Query(None, description="Cari nomor PO"),
    warehouse_id: int | None = None,
    supplier_id: int | None = None,
    status: str | None = Query(None, description="draft, sent, received, cancelled"),
    date_from: date_type | None = None,
    date_to: date_type | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if q:
        where += " AND po.po_number ILIKE %s"
        params.append(f"%{q}%")
    if warehouse_id:
        where += " AND po.warehouse_id = %s"
        params.append(warehouse_id)
    if supplier_id:
        where += " AND po.supplier_id = %s"
        params.append(supplier_id)
    if status:
        where += " AND po.status = %s"
        params.append(status)
    if date_from:
        where += " AND po.order_date >= %s"
        params.append(date_from)
    if date_to:
        where += " AND po.order_date <= %s"
        params.append(date_to)

    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM purchase_orders po {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT po.id, po.po_number, po.status, po.order_date, po.expected_date,
                   po.notes, po.source, po.stock_receipt_id,
                   r.receipt_number,
                   s.id AS supplier_id, s.name AS supplier_name,
                   w.id AS warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name,
                   COALESCE(d.line_count, 0)     AS line_count,
                   COALESCE(d.total_quantity, 0) AS total_quantity,
                   COALESCE(d.total_value, 0)    AS total_value
            FROM purchase_orders po
            JOIN warehouses w            ON w.id = po.warehouse_id
            LEFT JOIN suppliers s        ON s.id = po.supplier_id
            LEFT JOIN stock_receipts r   ON r.id = po.stock_receipt_id
            LEFT JOIN (
                SELECT purchase_order_id,
                       count(*)                      AS line_count,
                       SUM(quantity)                 AS total_quantity,
                       SUM(quantity * unit_price)    AS total_value
                FROM purchase_order_items GROUP BY purchase_order_id
            ) d ON d.purchase_order_id = po.id
            {where}
            ORDER BY po.order_date DESC, po.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        return page_envelope(cur.fetchall(), total, page, page_size)


@router.get("/{po_id}")
def get_purchase_order(po_id: int) -> dict:
    with readonly() as cur:
        cur.execute(
            """
            SELECT po.id, po.po_number, po.status, po.order_date, po.expected_date,
                   po.notes, po.source, po.stock_receipt_id, po.created_at, po.updated_at,
                   r.receipt_number,
                   s.id AS supplier_id, s.name AS supplier_name,
                   w.id AS warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name
            FROM purchase_orders po
            JOIN warehouses w          ON w.id = po.warehouse_id
            LEFT JOIN suppliers s      ON s.id = po.supplier_id
            LEFT JOIN stock_receipts r ON r.id = po.stock_receipt_id
            WHERE po.id = %s
            """,
            (po_id,),
        )
        po = cur.fetchone()
        if po is None:
            raise not_found("purchase_order", po_id)

        cur.execute(
            """
            SELECT poi.id, poi.item_id, i.sku, i.name AS item_name, u.code AS unit_code,
                   poi.quantity, poi.unit_price, (poi.quantity * poi.unit_price) AS line_value
            FROM purchase_order_items poi
            JOIN items i ON i.id = poi.item_id
            JOIN units u ON u.id = i.unit_id
            WHERE poi.purchase_order_id = %s ORDER BY poi.id
            """,
            (po_id,),
        )
        return {**po, "items": cur.fetchall()}
