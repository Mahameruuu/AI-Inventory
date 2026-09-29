# -*- coding: utf-8 -*-
"""
Penulisan penerimaan barang: satu jalur, satu tempat.

Rangkaian empat tabel yang menaikkan stok --

    stock_receipts -> stock_receipt_items -> stock_movements -> inventory

-- dulu hidup di dalam endpoint POST /api/stock-receipts. Begitu penerimaan
juga dapat lahir dari PO yang ditandai diterima, rangkaian itu punya DUA
pemanggil, dan menyalinnya berarti dua tempat yang harus sama-sama benar
selamanya. Perbedaan sekecil apa pun di antara keduanya akan berupa stok yang
salah, bukan tampilan yang salah.

Modul ini TIDAK memvalidasi master. Gudang, pemasok, dan barang diperiksa oleh
pemanggilnya, karena keduanya memvalidasi hal yang berbeda: formulir penerimaan
memeriksa apa yang diketik pengguna, sedangkan PO memeriksa apa yang sudah
tercatat pada pesanan.
"""

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from .common import LOCK_RECEIPT, next_document_number


def catat_penerimaan(
    cur,
    *,
    warehouse_id: int,
    supplier_id: int,
    received_date: date_type,
    stempel: datetime,
    reference_number: str | None,
    notes: str | None,
    baris: list[dict],
) -> dict:
    """
    Menulis satu penerimaan lengkap beserta akibatnya pada stok.

    `baris` berisi dict dengan kunci item_id, quantity, unit_price, dan boleh
    memuat batch_number, serial_number, expiry_date. Kuantitasnya WAJIB positif;
    pemanggil yang menjamin itu, sama seperti CHECK pada tabelnya.

    Harus dipanggil di dalam blok `transaction()`. Bila satu langkah gagal,
    ROLLBACK membatalkan seluruhnya -- tidak mungkin ada penerimaan tanpa
    pergerakan, atau pergerakan tanpa saldo.
    """
    receipt_number = next_document_number(
        cur,
        table="stock_receipts",
        column="receipt_number",
        prefix="GR",
        tanggal=received_date,
        lock_namespace=LOCK_RECEIPT,
    )

    # 1. header penerimaan
    cur.execute(
        """
        INSERT INTO stock_receipts
            (receipt_number, supplier_id, warehouse_id, receipt_date,
             reference_number, status, notes)
        VALUES (%s, %s, %s, %s, %s, 'completed', %s)
        RETURNING id
        """,
        (receipt_number, supplier_id, warehouse_id, stempel, reference_number, notes),
    )
    receipt_id = cur.fetchone()["id"]

    total_quantity = Decimal("0")
    total_value = Decimal("0")

    for b in baris:
        qty = Decimal(str(b["quantity"]))
        harga = Decimal(str(b["unit_price"]))

        # 2. rincian barang yang diterima
        cur.execute(
            """
            INSERT INTO stock_receipt_items
                (stock_receipt_id, item_id, quantity, unit_price,
                 batch_number, serial_number, received_date, expiry_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (receipt_id, b["item_id"], qty, harga, b.get("batch_number"),
             b.get("serial_number"), received_date, b.get("expiry_date")),
        )

        # 3. catatan pergerakan stok -- masuk, jadi kuantitasnya POSITIF
        cur.execute(
            """
            INSERT INTO stock_movements
                (item_id, warehouse_id, movement_type, reference_id,
                 movement_date, quantity, unit_price, batch_number)
            VALUES (%s, %s, 'stock_in', %s, %s, %s, %s, %s)
            """,
            (b["item_id"], warehouse_id, receipt_id, stempel, qty, harga,
             b.get("batch_number")),
        )

        # 4-6. saldo berjalan: tambah bila barisnya sudah ada, buat bila belum.
        # available_quantity selalu dihitung ulang dari kuantitas terbaru
        # dikurangi yang sudah dialokasikan.
        cur.execute(
            """
            INSERT INTO inventory
                (item_id, warehouse_id, quantity, reserved_quantity, available_quantity)
            VALUES (%s, %s, %s, 0, %s)
            -- company_id ikut disebut karena kunci uniknya kini
            -- (company_id, item_id, warehouse_id); nilainya sendiri datang
            -- dari DEFAULT kolom, yaitu penyewa yang sedang aktif.
            ON CONFLICT (company_id, item_id, warehouse_id) DO UPDATE
            SET quantity           = inventory.quantity + EXCLUDED.quantity,
                available_quantity = inventory.quantity + EXCLUDED.quantity
                                     - inventory.reserved_quantity,
                updated_at         = now()
            """,
            (b["item_id"], warehouse_id, qty, qty),
        )

        total_quantity += qty
        total_value += qty * harga

    return {
        "receipt_id": receipt_id,
        "receipt_number": receipt_number,
        "item_count": len(baris),
        "total_quantity": total_quantity,
        "total_value": total_value,
    }
