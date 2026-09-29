# -*- coding: utf-8 -*-
"""Bentuk permintaan dan jawaban API."""

from datetime import date
from decimal import Decimal

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ReceiptItemIn(BaseModel):
    item_id: int = Field(..., gt=0)
    quantity: Decimal
    unit_price: Decimal
    batch_number: str | None = Field(default=None, max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    expiry_date: date | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("quantity harus lebih besar dari 0")
        return v

    @field_validator("unit_price")
    @classmethod
    def price_not_negative(cls, v: Decimal) -> Decimal:
        if v < 0:
            raise ValueError("unit_price tidak boleh negatif")
        return v


class StockReceiptIn(BaseModel):
    warehouse_id: int = Field(..., gt=0)
    supplier_id: int = Field(..., gt=0)
    received_date: date
    reference_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    items: list[ReceiptItemIn] = Field(..., min_length=1)


class WarehouseOut(BaseModel):
    id: int
    code: str
    name: str


class StockReceiptOut(BaseModel):
    receipt_id: int
    receipt_number: str
    warehouse: WarehouseOut
    item_count: int
    # Kuantitas dan nilai dikirim sebagai teks supaya ketelitian desimal tidak
    # hilang saat melewati JSON. Sisi frontend sudah memakai Number(...).
    total_quantity: str
    total_value: str


class PurchaseOrderItemIn(BaseModel):
    item_id: int = Field(..., gt=0)
    quantity: Decimal
    # Kosong berarti "pakai harga pada master barang". Dibedakan dari nol,
    # karena nol adalah harga yang sah untuk barang bantuan atau garansi.
    unit_price: Decimal | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("quantity harus lebih besar dari 0")
        return v

    @field_validator("unit_price")
    @classmethod
    def unit_price_non_negative(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("unit_price tidak boleh negatif")
        return v


class PurchaseOrderIn(BaseModel):
    warehouse_id: int = Field(..., gt=0)
    # Boleh kosong: PO draft dari panel Reorder belum tahu pemasoknya, karena
    # master barang tidak menyimpan pemasok sama sekali.
    supplier_id: int | None = Field(default=None, gt=0)
    # Kosong berarti hari ini menurut zona waktu aplikasi.
    order_date: date | None = None
    notes: str | None = None
    source: str | None = Field(default=None, max_length=30)
    items: list[PurchaseOrderItemIn] = Field(..., min_length=1)


class PurchaseOrderOut(BaseModel):
    purchase_order_id: int
    po_number: str
    status: str
    warehouse: WarehouseOut
    order_date: date
    expected_date: date | None
    item_count: int
    # Sama seperti StockReceiptOut: dikirim sebagai teks supaya ketelitian
    # desimalnya tidak hilang saat melewati JSON.
    total_quantity: str
    total_value: str


class PurchaseOrderStatusIn(BaseModel):
    """Perpindahan status yang TIDAK menyentuh stok: dikirim atau dibatalkan."""

    status: Literal["sent", "cancelled"]
    # Hanya berarti saat menuju "sent": PO yang dikirim harus punya pemasok.
    # Boleh kosong bila pemasoknya sudah tercatat pada PO.
    supplier_id: int | None = Field(default=None, gt=0)


class PurchaseOrderReceiveIn(BaseModel):
    """
    Penerimaan barang atas satu PO.

    Tidak menerima daftar barang: yang diterima adalah apa yang dipesan, persis
    seperti tercatat pada purchase_order_items. Penerimaan sebagian dan
    penerimaan yang berbeda dari pesanan adalah dua persoalan tersendiri yang
    menuntut kolom qty_received per baris, dan skema ini belum memilikinya.
    """

    received_date: date | None = None
    reference_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None


class IssueItemIn(BaseModel):
    item_id: int = Field(..., gt=0)
    quantity: Decimal

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("quantity harus lebih besar dari 0")
        return v


class StockIssueIn(BaseModel):
    warehouse_id: int = Field(..., gt=0)
    issue_date: date
    purpose: str | None = Field(default=None, max_length=150)
    reference_number: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    items: list[IssueItemIn] = Field(..., min_length=1)


class IssuedLineOut(BaseModel):
    item_id: int
    sku: str
    quantity_issued: str
    quantity_before: str
    quantity_after: str
    available_after: str


class StockIssueOut(BaseModel):
    issue_id: int
    issue_number: str
    warehouse: WarehouseOut
    item_count: int
    total_quantity: str
    lines: list[IssuedLineOut]
