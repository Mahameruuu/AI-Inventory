# -*- coding: utf-8 -*-
"""Master data yang dibaca frontend: gudang dan barang."""

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ..common import (JENIS_PEMAKAIAN, PAGE_SIZE_DEFAULT, clamp_page,
                      page_envelope)
from ..db import readonly, transaction
from ..errors import invalid, not_found

router = APIRouter(tags=["catalog"])


@router.get("/api/warehouses")
def list_warehouses(
    q: str | None = Query(None, description="Cari kode atau nama"),
    only_active: bool = Query(False),
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if q:
        where += " AND (w.code ILIKE %s OR w.name ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if only_active:
        where += " AND w.is_active"

    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM warehouses w {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT w.id, w.code, w.name, w.location, w.is_active,
                   -- dipakai modul Transfer Antar Gudang untuk menghitung
                   -- jarak; diterbitkan di sini supaya layar master gudang
                   -- dapat menyuntingnya tanpa endpoint kedua
                   w.latitude, w.longitude, w.transfer_lead_time_days,
                   COALESCE(agg.item_count, 0)  AS item_count,
                   COALESCE(agg.total_stock, 0) AS total_stock,
                   COALESCE(agg.stock_value, 0) AS stock_value
            FROM warehouses w
            LEFT JOIN (
                SELECT inv.warehouse_id,
                       count(*)                              AS item_count,
                       SUM(inv.quantity)                     AS total_stock,
                       SUM(inv.quantity * it.unit_price)     AS stock_value
                FROM inventory inv
                JOIN items it ON it.id = inv.item_id
                GROUP BY inv.warehouse_id
            ) agg ON agg.warehouse_id = w.id
            {where}
            ORDER BY w.code
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        return page_envelope(cur.fetchall(), total, page, page_size)


@router.get("/api/warehouses/{warehouse_id}")
def get_warehouse(warehouse_id: int) -> dict:
    with readonly() as cur:
        cur.execute(
            """
            SELECT w.id, w.code, w.name, w.location, w.is_active,
                   w.latitude, w.longitude, w.transfer_lead_time_days,
                   w.created_at, w.updated_at
            FROM warehouses w WHERE w.id = %s
            """,
            (warehouse_id,),
        )
        gudang = cur.fetchone()
        if gudang is None:
            raise not_found("warehouse", warehouse_id)

        cur.execute(
            """
            SELECT count(*)                          AS item_count,
                   COALESCE(SUM(inv.quantity), 0)    AS total_stock,
                   COALESCE(SUM(inv.reserved_quantity), 0) AS total_reserved,
                   COALESCE(SUM(inv.quantity * it.unit_price), 0) AS stock_value
            FROM inventory inv JOIN items it ON it.id = inv.item_id
            WHERE inv.warehouse_id = %s
            """,
            (warehouse_id,),
        )
        ringkasan = cur.fetchone()

        cur.execute(
            """
            SELECT it.id AS item_id, it.sku, it.name, u.code AS unit_code,
                   inv.quantity, inv.reserved_quantity, inv.available_quantity,
                   it.unit_price, (inv.quantity * it.unit_price) AS stock_value,
                   it.minimum_stock, it.reorder_point
            FROM inventory inv
            JOIN items it ON it.id = inv.item_id
            JOIN units u  ON u.id = it.unit_id
            WHERE inv.warehouse_id = %s
            ORDER BY it.sku
            LIMIT 100
            """,
            (warehouse_id,),
        )
        stok = cur.fetchall()

        cur.execute(
            """
            SELECT m.id, m.movement_type, m.movement_date, m.quantity,
                   it.sku, it.name AS item_name
            FROM stock_movements m JOIN items it ON it.id = m.item_id
            WHERE m.warehouse_id = %s
            ORDER BY m.movement_date DESC, m.id DESC
            LIMIT 10
            """,
            (warehouse_id,),
        )
        aktivitas = cur.fetchall()

    return {"warehouse": gudang, "summary": ringkasan, "stock": stok, "recent_movements": aktivitas}


@router.get("/api/suppliers")
def list_suppliers(
    q: str | None = Query(None, description="Cari kode atau nama"),
    only_active: bool = Query(False),
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    """
    Dibutuhkan formulir penerimaan untuk mengisi pilihan supplier.

    Tidak ada di daftar endpoint awal, tetapi tanpa ini formulir terpaksa
    memakai daftar yang dituliskan mati di frontend -- persis yang dilarang.
    """
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if q:
        where += " AND (s.code ILIKE %s OR s.name ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if only_active:
        where += " AND s.is_active"

    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM suppliers s {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT s.id, s.code, s.name, s.phone, s.email, s.address,
                   s.lead_time_days, s.is_active,
                   COALESCE(r.receipt_count, 0) AS receipt_count
            FROM suppliers s
            LEFT JOIN (
                SELECT supplier_id, count(*) AS receipt_count
                FROM stock_receipts GROUP BY supplier_id
            ) r ON r.supplier_id = s.id
            {where}
            ORDER BY s.name
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        return page_envelope(cur.fetchall(), total, page, page_size)


@router.get("/api/items")
def list_items(
    q: str | None = Query(None, description="Cari SKU atau nama"),
    category_id: int | None = None,
    only_active: bool = Query(False),
    usage_type: str | None = Query(
        None, description="berumur_pakai atau habis_pakai; kosong = semuanya"),
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if q:
        where += " AND (it.sku ILIKE %s OR it.name ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if category_id:
        where += " AND it.category_id = %s"
        params.append(category_id)
    if only_active:
        where += " AND it.is_active"
    if usage_type:
        if usage_type not in JENIS_PEMAKAIAN:
            raise invalid(f"usage_type harus salah satu dari: "
                          f"{', '.join(JENIS_PEMAKAIAN)}", "usage_type")
        where += " AND it.usage_type = %s"
        params.append(usage_type)

    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM items it {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT it.id, it.sku, it.name, it.unit_price, it.minimum_stock,
                   it.maximum_stock, it.reorder_point, it.criticality, it.is_active,
                   -- Id kategori dan satuan ikut terbaca, bukan hanya namanya.
                   -- Formulir ubah pada layar Master Barang mengisi kedua
                   -- pilihannya dari sini; tanpa id-nya, keduanya tampil kosong
                   -- pada barang yang jelas-jelas punya kategori, dan menyimpan
                   -- tanpa menyentuhnya diam-diam membiarkan nilai lamanya --
                   -- benar, tetapi tampak seperti data yang hilang.
                   it.category_id, it.unit_id, it.safety_stock, it.lead_time_days,
                   it.usage_type, it.service_life_value, it.service_life_unit,
                   c.name AS category_name, u.code AS unit_code,
                   COALESCE(s.total_stock, 0) AS total_stock,
                   COALESCE(s.warehouse_count, 0) AS warehouse_count
            FROM items it
            JOIN categories c ON c.id = it.category_id
            JOIN units u      ON u.id = it.unit_id
            LEFT JOIN (
                SELECT item_id, SUM(quantity) AS total_stock, count(*) AS warehouse_count
                FROM inventory GROUP BY item_id
            ) s ON s.item_id = it.id
            {where}
            ORDER BY it.sku
            LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        return page_envelope(cur.fetchall(), total, page, page_size)


@router.get("/api/items/{item_id}")
def get_item(item_id: int) -> dict:
    with readonly() as cur:
        cur.execute(
            """
            SELECT it.id, it.sku, it.name, it.unit_price, it.minimum_stock,
                   it.maximum_stock, it.reorder_point, it.criticality, it.is_active,
                   it.created_at, it.updated_at,
                   c.id AS category_id, c.name AS category_name,
                   u.id AS unit_id, u.code AS unit_code, u.name AS unit_name
            FROM items it
            JOIN categories c ON c.id = it.category_id
            JOIN units u      ON u.id = it.unit_id
            WHERE it.id = %s
            """,
            (item_id,),
        )
        barang = cur.fetchone()
        if barang is None:
            raise not_found("item", item_id)

        cur.execute(
            """
            SELECT w.id AS warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name,
                   inv.quantity, inv.reserved_quantity, inv.available_quantity,
                   inv.updated_at
            FROM inventory inv JOIN warehouses w ON w.id = inv.warehouse_id
            WHERE inv.item_id = %s ORDER BY w.code
            """,
            (item_id,),
        )
        per_gudang = cur.fetchall()

        cur.execute(
            """
            SELECT COALESCE(SUM(quantity), 0) AS total_stock,
                   COALESCE(SUM(reserved_quantity), 0) AS total_reserved,
                   COALESCE(SUM(available_quantity), 0) AS total_available
            FROM inventory WHERE item_id = %s
            """,
            (item_id,),
        )
        ringkasan = cur.fetchone()

        cur.execute(
            """
            SELECT m.id, m.movement_type, m.movement_date, m.quantity, m.unit_price,
                   w.code AS warehouse_code
            FROM stock_movements m JOIN warehouses w ON w.id = m.warehouse_id
            WHERE m.item_id = %s
            ORDER BY m.movement_date DESC, m.id DESC LIMIT 20
            """,
            (item_id,),
        )
        pergerakan = cur.fetchall()

    return {
        "item": barang,
        "summary": ringkasan,
        "stock_by_warehouse": per_gudang,
        "recent_movements": pergerakan,
    }


class ReorderPointIn(BaseModel):
    """Nilai titik pesan ulang yang baru untuk satu barang."""

    reorder_point: float = Field(..., ge=0, description="Titik pesan ulang baru, >= 0")


@router.patch("/api/items/{item_id}/reorder-point")
def set_reorder_point(item_id: int, body: ReorderPointIn) -> dict:
    """
    Mengubah titik pesan ulang pada MASTER BARANG.

    BERLAKU UNTUK SELURUH GUDANG. `items.reorder_point` adalah satu kolom pada
    master barang; tabel `inventory` tidak menyimpan ambang per gudang sama
    sekali. Jadi nilai yang disarankan layar Reorder -- yang lahir dari laju
    pemakaian dan lead time SATU gudang -- begitu disimpan akan menjadi ambang
    bagi kelima puluh gudang yang menyimpan barang itu. Itu sifat skemanya,
    bukan efek samping endpoint ini, dan pemanggil wajib menyatakannya kepada
    pengguna sebelum tombolnya ditekan.

    Titik pesan master TIDAK menentukan status pada layar Reorder: yang
    menentukan adalah titik pesan efektif, yang dihitung ulang dari laju
    pemakaian setiap kali halaman dimuat. Menyimpan nilai baru di sini
    memperbaiki mutu master data; ia tidak mengubah keputusan hari ini.

    Mengembalikan nilai lama dan baru supaya pemanggil dapat menampilkan apa
    yang benar-benar tersimpan, bukan apa yang dikiranya tersimpan.
    """
    with transaction() as cur:
        cur.execute(
            "SELECT id, sku, name, reorder_point FROM items WHERE id = %s FOR UPDATE",
            (item_id,),
        )
        barang = cur.fetchone()
        if barang is None:
            raise not_found("item", item_id)

        # Ambang yang melampaui stok maksimum tidak dapat dipenuhi pengadaan
        # mana pun: barang akan berdiri permanen di bawah titik pesannya.
        cur.execute("SELECT maximum_stock FROM items WHERE id = %s", (item_id,))
        maks = cur.fetchone()["maximum_stock"]
        if maks is not None and float(body.reorder_point) > float(maks):
            raise invalid(
                f"Titik pesan {body.reorder_point:g} melampaui stok maksimum "
                f"{float(maks):g} pada master barang.",
                "reorder_point",
            )

        cur.execute(
            "UPDATE items SET reorder_point = %s, updated_at = now() WHERE id = %s",
            (body.reorder_point, item_id),
        )

    return {
        "item": {"id": barang["id"], "sku": barang["sku"], "name": barang["name"]},
        "reorder_point_before": float(barang["reorder_point"] or 0),
        "reorder_point": float(body.reorder_point),
    }
