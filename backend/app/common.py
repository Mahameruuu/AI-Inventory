# -*- coding: utf-8 -*-
"""
Bagian yang dipakai bersama oleh seluruh transaksi persediaan.

Ditaruh di satu tempat supaya penomoran dokumen dan pemeriksaan master data
tidak ditulis ulang per endpoint -- kalau aturannya berubah, cukup satu berkas
yang disunting.
"""

from datetime import date

from .errors import inactive, not_found

# Batas halaman. Tanpa batas atas, satu permintaan bisa menarik seluruh tabel.
PAGE_SIZE_DEFAULT = 25

# Jenis pemakaian barang (items.usage_type, migrasi 034).
JENIS_PEMAKAIAN = ("berumur_pakai", "habis_pakai")
PAGE_SIZE_MAX = 200


def clamp_page(page: int, page_size: int) -> tuple[int, int, int]:
    """Mengembalikan (page, page_size, offset) yang sudah dibatasi."""
    page = max(1, page)
    page_size = min(max(1, page_size), PAGE_SIZE_MAX)
    return page, page_size, (page - 1) * page_size


def page_envelope(rows: list, total: int, page: int, page_size: int) -> dict:
    return {
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }

# Ruang kunci penasihat per jenis dokumen. Dipisah supaya penomoran penerimaan
# dan pengeluaran tidak saling menunggu. Angkanya sembarang, asal tidak kembar.
LOCK_RECEIPT = 4711
LOCK_ISSUE = 4712
LOCK_PO = 4713
LOCK_TRANSFER = 4714
LOCK_ADJUSTMENT = 4715


def next_document_number(
    cur, *, table: str, column: str, prefix: str, tanggal: date, lock_namespace: int
) -> str:
    """
    Membentuk nomor dokumen PREFIX-YYYYMMDD-NNNN, urutan direset tiap hari.

    Kunci penasihat dipegang sampai transaksi berakhir sehingga dua permintaan
    bersamaan pada tanggal yang sama mustahil memperoleh nomor kembar. Kunci ini
    tidak menyentuh skema dan lepas sendiri saat COMMIT maupun ROLLBACK.

    `table` dan `column` berasal dari konstanta di kode, bukan dari masukan
    pengguna, sehingga aman disisipkan langsung ke perintah.
    """
    ymd = tanggal.strftime("%Y%m%d")
    cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (lock_namespace, int(ymd)))

    # Urutan mulai setelah "PREFIX-" + 8 digit tanggal + "-"
    posisi = len(prefix) + 11
    cur.execute(
        f"""
        SELECT COALESCE(MAX(SUBSTRING({column} FROM {posisi})::int), 0) + 1 AS urutan
        FROM {table}
        WHERE {column} LIKE %s AND {column} ~ %s
        """,
        (f"{prefix}-{ymd}-%", f"^{prefix}-[0-9]{{8}}-[0-9]+$"),
    )
    return f"{prefix}-{ymd}-{cur.fetchone()['urutan']:04d}"


def ambil_gudang_aktif(cur, warehouse_id: int, field: str = "warehouse_id") -> dict:
    cur.execute(
        "SELECT id, code, name, is_active FROM warehouses WHERE id = %s", (warehouse_id,)
    )
    row = cur.fetchone()
    if row is None:
        raise not_found("warehouse", warehouse_id, field)
    if not row["is_active"]:
        raise inactive("warehouse", row["name"], field)
    return row


def ambil_supplier_aktif(cur, supplier_id: int, field: str = "supplier_id") -> dict:
    cur.execute("SELECT id, name, is_active FROM suppliers WHERE id = %s", (supplier_id,))
    row = cur.fetchone()
    if row is None:
        raise not_found("supplier", supplier_id, field)
    if not row["is_active"]:
        raise inactive("supplier", row["name"], field)
    return row


def ambil_barang_aktif(
    cur, item_ids: list[int], field: str = "items.item_id"
) -> dict[int, dict]:
    """Satu query untuk seluruh barang; mengembalikan peta id -> baris."""
    cur.execute(
        "SELECT id, sku, name, is_active FROM items WHERE id = ANY(%s)", (item_ids,)
    )
    ditemukan = {r["id"]: r for r in cur.fetchall()}
    for iid in item_ids:
        row = ditemukan.get(iid)
        if row is None:
            raise not_found("item", iid, field)
        if not row["is_active"]:
            raise inactive("item", f"{row['sku']} - {row['name']}", field)
    return ditemukan
