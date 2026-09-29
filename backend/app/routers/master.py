# -*- coding: utf-8 -*-
"""
Master data: membuat, mengubah, dan menonaktifkan.

MENGISI JALAN MASUK YANG SELAMA INI TIDAK ADA. Sampai berkas ini, seluruh
master data hanya bisa DIBACA lewat API; satu-satunya cara memasukkan barang,
gudang, atau supplier adalah lewat SQL. Itu yang membuat sistem ini belum bisa
dipakai pelanggan baru: mereka tidak punya cara memasukkan datanya sendiri.

JALUR BACANYA TETAP DI catalog.py. Alamat yang dipakai sama persis --
POST /api/items berdampingan dengan GET /api/items yang sudah ada -- hanya
berkasnya yang terpisah, supaya keduanya tidak tumbuh menjadi satu berkas
tujuh ratus baris. Bagi pemakai API, tidak ada bedanya.

MENGHAPUS ITU PENGECUALIAN, BUKAN ATURAN. Seluruh foreign key ke master data
memakai NO ACTION, jadi begitu satu kategori dipakai satu barang saja, ia tidak
akan pernah bisa dihapus lagi -- itu memang benar, karena menghapusnya berarti
riwayat transaksi kehilangan artinya. Yang disediakan di sini: menonaktifkan
(is_active) untuk data yang sudah terpakai, dan menghapus HANYA untuk data yang
belum tersentuh apa pun. Yang kedua itu bukan kemewahan: saat mengisi data awal,
salah ketik satu baris lalu terpaksa hidup dengan "SATAUN" selamanya di daftar
pilihan adalah pengalaman yang membuat orang berhenti mengisi.

PERAN. Seluruh perubahan di sini menuntut owner atau admin. Alasannya bukan
kehati-hatian umum: satu SKU yang salah atau satu satuan yang diubah artinya
menjalar ke setiap transaksi, setiap laporan, dan setiap prakiraan yang
menyebutnya -- dan tidak ada satu pun layar yang akan menampilkan galat.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from psycopg import errors as pg_errors
from pydantic import BaseModel, Field, field_validator

from .. import i18n
from ..auth import wajib_admin
from ..common import PAGE_SIZE_DEFAULT, clamp_page, page_envelope
from ..db import readonly, transaction
from ..errors import AppError, not_found

router = APIRouter(tags=["master"], dependencies=[Depends(wajib_admin)])

KRITIKALITAS = ("critical", "high", "medium", "low")


# ==========================================================================
# Pembantu
# ==========================================================================

def _galat(kunci: str, status: int, kode: str, **params) -> AppError:
    return AppError(status, kode,
                    i18n.t(kunci, i18n.bahasa_permintaan(), **params))


def _bentrok(e: pg_errors.UniqueViolation, entitas: str, nilai: dict) -> AppError:
    """
    Mengubah pelanggaran UNIQUE menjadi kalimat yang menyebut kolom mana yang
    bentrok BESERTA nilainya.

    Nama constraint-nya berpola <tabel>_<kolom>_unique, jadi kolomnya dapat
    dibaca dari sana tanpa daftar pemetaan yang harus dirawat terpisah setiap
    kali ada constraint baru. Nilainya diambil dari apa yang barusan dikirim --
    "SKU 'BRG-001' sudah ada" jauh lebih berguna daripada "data sudah ada" bagi
    orang yang sedang menempelkan dua ratus baris dari spreadsheet.
    """
    nama = e.diag.constraint_name or ""
    kolom = "data"
    for k in ("sku", "code", "name"):
        if nama.endswith(f"_{k}_unique"):
            kolom = k
            break
    return _galat("err.master.duplicate", 409, "CONFLICT",
                  entitas=i18n.t(f"err.entity.{entitas}", i18n.bahasa_permintaan()),
                  kolom=kolom, nilai=nilai.get(kolom, ""))


def _perbarui(cur, *, tabel: str, entitas: str, id_: int,
              nilai: dict, kembalikan: str) -> dict:
    """
    Satu UPDATE dari kolom yang benar-benar dikirim.

    Field yang tidak disebut pemanggil TIDAK ikut ditulis. Bedanya nyata: PATCH
    yang menulis seluruh kolom akan mengosongkan alamat supplier hanya karena
    seseorang mengubah nomor teleponnya dari layar yang tidak menampilkan
    alamat.
    """
    isi = {k: v for k, v in nilai.items() if v is not None}
    if not isi:
        raise _galat("err.master.no_change", 422, "VALIDATION_ERROR")

    set_bagian = ", ".join(f"{k} = %s" for k in isi) + ", updated_at = now()"
    try:
        cur.execute(
            f"UPDATE {tabel} SET {set_bagian} WHERE id = %s RETURNING {kembalikan}",
            list(isi.values()) + [id_],
        )
    except pg_errors.UniqueViolation as e:
        raise _bentrok(e, entitas, isi) from None

    baris = cur.fetchone()
    if baris is None:
        raise not_found(entitas, id_)
    return baris


def _hapus_bila_belum_terpakai(cur, *, tabel: str, entitas: str, id_: int,
                               nama_kolom: str, rujukan: list[tuple[str, str]]) -> dict:
    """
    Menghapus satu baris master, tetapi hanya bila belum dirujuk apa pun.

    Pemeriksaannya dilakukan sendiri alih-alih membiarkan foreign key yang
    menolak, karena pesan foreign key menyebut nama constraint dan nama tabel --
    keterangan yang tidak berarti apa-apa bagi orang yang sedang merapikan
    daftar satuannya, dan yang tidak boleh keluar ke klien sama sekali (lihat
    app/errors.py).
    """
    cur.execute(f"SELECT id, {nama_kolom} AS nama FROM {tabel} WHERE id = %s", (id_,))
    baris = cur.fetchone()
    if baris is None:
        raise not_found(entitas, id_)

    jumlah = 0
    for tabel_rujuk, kolom in rujukan:
        cur.execute(f"SELECT count(*) AS n FROM {tabel_rujuk} WHERE {kolom} = %s", (id_,))
        jumlah += cur.fetchone()["n"]

    if jumlah:
        raise _galat("err.master.in_use", 409, "CONFLICT",
                     entitas=i18n.t(f"err.entity.{entitas}", i18n.bahasa_permintaan()),
                     nama=baris["nama"], jumlah=jumlah)

    cur.execute(f"DELETE FROM {tabel} WHERE id = %s", (id_,))
    return {"deleted": True, "id": id_, "name": baris["nama"]}


# ==========================================================================
# Kategori
# ==========================================================================

class KategoriIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = None


class KategoriUbah(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = None
    is_active: bool | None = None


@router.get("/api/categories")
def daftar_kategori(q: str | None = Query(None), only_active: bool = Query(False),
                    page: int = 1, page_size: int = PAGE_SIZE_DEFAULT) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if q:
        where += " AND c.name ILIKE %s"
        params.append(f"%{q}%")
    if only_active:
        where += " AND c.is_active"

    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM categories c {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT c.id, c.name, c.description, c.is_active,
                   (SELECT count(*) FROM items i WHERE i.category_id = c.id) AS item_count
              FROM categories c {where}
             ORDER BY c.name LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        return page_envelope(cur.fetchall(), total, page, page_size)


@router.post("/api/categories", status_code=201)
def buat_kategori(body: KategoriIn) -> dict:
    with transaction() as cur:
        try:
            cur.execute(
                "INSERT INTO categories (name, description) VALUES (%s, %s) "
                "RETURNING id, name, description, is_active",
                (body.name.strip(), body.description),
            )
        except pg_errors.UniqueViolation as e:
            raise _bentrok(e, "category", {"name": body.name.strip()}) from None
        return cur.fetchone()


@router.patch("/api/categories/{kategori_id}")
def ubah_kategori(kategori_id: int, body: KategoriUbah) -> dict:
    with transaction() as cur:
        return _perbarui(
            cur, tabel="categories", entitas="category", id_=kategori_id,
            nilai={"name": body.name.strip() if body.name else None,
                   "description": body.description, "is_active": body.is_active},
            kembalikan="id, name, description, is_active")


@router.delete("/api/categories/{kategori_id}")
def hapus_kategori(kategori_id: int) -> dict:
    with transaction() as cur:
        return _hapus_bila_belum_terpakai(
            cur, tabel="categories", entitas="category", id_=kategori_id,
            nama_kolom="name", rujukan=[("items", "category_id")])


# ==========================================================================
# Satuan
# ==========================================================================

class SatuanIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)


class SatuanUbah(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=20)
    is_active: bool | None = None


@router.get("/api/units")
def daftar_satuan(q: str | None = Query(None), only_active: bool = Query(False),
                  page: int = 1, page_size: int = PAGE_SIZE_DEFAULT) -> dict:
    page, page_size, offset = clamp_page(page, page_size)
    where, params = "WHERE 1=1", []
    if q:
        where += " AND (u.name ILIKE %s OR u.code ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if only_active:
        where += " AND u.is_active"

    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM units u {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT u.id, u.name, u.code, u.is_active,
                   (SELECT count(*) FROM items i WHERE i.unit_id = u.id) AS item_count
              FROM units u {where}
             ORDER BY u.code LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        return page_envelope(cur.fetchall(), total, page, page_size)


@router.post("/api/units", status_code=201)
def buat_satuan(body: SatuanIn) -> dict:
    with transaction() as cur:
        try:
            cur.execute(
                "INSERT INTO units (name, code) VALUES (%s, %s) "
                "RETURNING id, name, code, is_active",
                (body.name.strip(), body.code.strip().upper()),
            )
        except pg_errors.UniqueViolation as e:
            raise _bentrok(e, "unit", {"name": body.name.strip(),
                                       "code": body.code.strip().upper()}) from None
        return cur.fetchone()


@router.patch("/api/units/{satuan_id}")
def ubah_satuan(satuan_id: int, body: SatuanUbah) -> dict:
    with transaction() as cur:
        return _perbarui(
            cur, tabel="units", entitas="unit", id_=satuan_id,
            nilai={"name": body.name.strip() if body.name else None,
                   "code": body.code.strip().upper() if body.code else None,
                   "is_active": body.is_active},
            kembalikan="id, name, code, is_active")


@router.delete("/api/units/{satuan_id}")
def hapus_satuan(satuan_id: int) -> dict:
    with transaction() as cur:
        return _hapus_bila_belum_terpakai(
            cur, tabel="units", entitas="unit", id_=satuan_id,
            nama_kolom="name", rujukan=[("items", "unit_id")])


# ==========================================================================
# Gudang
# ==========================================================================

class GudangIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=150)
    location: str | None = Field(default=None, max_length=255)
    # Koordinat dan waktu tempuh dipakai memeringkat gudang sumber pada modul
    # Transfer Antar Gudang (migrasi 031). Boleh kosong: gudang tanpa koordinat
    # tetap dapat menjadi sumber, hanya komponen jaraknya dinilai netral
    # alih-alih ditebak.
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    transfer_lead_time_days: int | None = Field(default=None, ge=0, le=365)


class GudangUbah(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=150)
    location: str | None = Field(default=None, max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    transfer_lead_time_days: int | None = Field(default=None, ge=0, le=365)
    is_active: bool | None = None


@router.post("/api/warehouses", status_code=201)
def buat_gudang(body: GudangIn) -> dict:
    with transaction() as cur:
        try:
            cur.execute(
                "INSERT INTO warehouses (code, name, location, latitude, longitude, "
                "transfer_lead_time_days) VALUES (%s, %s, %s, %s, %s, %s) "
                "RETURNING id, code, name, location, latitude, longitude, "
                "transfer_lead_time_days, is_active",
                (body.code.strip().upper(), body.name.strip(), body.location,
                 body.latitude, body.longitude, body.transfer_lead_time_days),
            )
        except pg_errors.UniqueViolation as e:
            raise _bentrok(e, "warehouse", {"code": body.code.strip().upper(),
                                            "name": body.name.strip()}) from None
        return cur.fetchone()


@router.patch("/api/warehouses/{gudang_id}")
def ubah_gudang(gudang_id: int, body: GudangUbah) -> dict:
    with transaction() as cur:
        return _perbarui(
            cur, tabel="warehouses", entitas="warehouse", id_=gudang_id,
            nilai={"code": body.code.strip().upper() if body.code else None,
                   "name": body.name.strip() if body.name else None,
                   "location": body.location,
                   "latitude": body.latitude, "longitude": body.longitude,
                   "transfer_lead_time_days": body.transfer_lead_time_days,
                   "is_active": body.is_active},
            kembalikan="id, code, name, location, latitude, longitude, "
                       "transfer_lead_time_days, is_active")


@router.delete("/api/warehouses/{gudang_id}")
def hapus_gudang(gudang_id: int) -> dict:
    with transaction() as cur:
        return _hapus_bila_belum_terpakai(
            cur, tabel="warehouses", entitas="warehouse", id_=gudang_id,
            nama_kolom="name",
            rujukan=[("inventory", "warehouse_id"),
                     ("stock_movements", "warehouse_id"),
                     ("stock_receipts", "warehouse_id"),
                     ("stock_issues", "warehouse_id"),
                     ("stock_adjustments", "warehouse_id"),
                     ("purchase_orders", "warehouse_id"),
                     ("stock_transfers", "from_warehouse_id"),
                     ("stock_transfers", "to_warehouse_id")])


# ==========================================================================
# Supplier
# ==========================================================================

class SupplierIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None
    lead_time_days: int | None = Field(default=None, ge=0, le=365)


class SupplierUbah(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    address: str | None = None
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    is_active: bool | None = None


KOLOM_SUPPLIER = "id, code, name, phone, email, address, lead_time_days, is_active"


@router.post("/api/suppliers", status_code=201)
def buat_supplier(body: SupplierIn) -> dict:
    with transaction() as cur:
        try:
            cur.execute(
                f"""
                INSERT INTO suppliers (code, name, phone, email, address, lead_time_days)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING {KOLOM_SUPPLIER}
                """,
                (body.code.strip().upper(), body.name.strip(), body.phone,
                 body.email, body.address, body.lead_time_days),
            )
        except pg_errors.UniqueViolation as e:
            raise _bentrok(e, "supplier", {"code": body.code.strip().upper(),
                                           "name": body.name.strip()}) from None
        return cur.fetchone()


@router.patch("/api/suppliers/{supplier_id}")
def ubah_supplier(supplier_id: int, body: SupplierUbah) -> dict:
    with transaction() as cur:
        return _perbarui(
            cur, tabel="suppliers", entitas="supplier", id_=supplier_id,
            nilai={"code": body.code.strip().upper() if body.code else None,
                   "name": body.name.strip() if body.name else None,
                   "phone": body.phone, "email": body.email,
                   "address": body.address, "lead_time_days": body.lead_time_days,
                   "is_active": body.is_active},
            kembalikan=KOLOM_SUPPLIER)


@router.delete("/api/suppliers/{supplier_id}")
def hapus_supplier(supplier_id: int) -> dict:
    with transaction() as cur:
        return _hapus_bila_belum_terpakai(
            cur, tabel="suppliers", entitas="supplier", id_=supplier_id,
            nama_kolom="name",
            rujukan=[("stock_receipts", "supplier_id"),
                     ("purchase_orders", "supplier_id")])


# ==========================================================================
# Barang
# ==========================================================================

def _kritikalitas(v: str | None) -> str | None:
    """
    Nilai kekritisan yang dikenal, atau kosong.

    Dipisahkan menjadi fungsi biasa supaya dua model di bawah memakai aturan
    yang SAMA, bukan dua salinan yang bisa berbeda diam-diam. Kolomnya sendiri
    berupa teks bebas di basis data (lihat komentar pada migrasi 005), jadi
    tanpa pemeriksaan di sini "Tinggi", "HIGH", dan "high" akan hidup
    berdampingan sebagai tiga nilai berbeda, dan setiap penyaringan berdasarkan
    kekritisan akan melewatkan sebagiannya.
    """
    if v is None or v == "":
        return None
    if v.lower() not in KRITIKALITAS:
        raise ValueError(
            f"criticality harus salah satu dari: {', '.join(KRITIKALITAS)}")
    return v.lower()


class BarangIn(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=255)
    category_id: int = Field(..., gt=0)
    unit_id: int = Field(..., gt=0)
    unit_price: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_stock: Decimal = Field(default=Decimal("0"), ge=0)
    maximum_stock: Decimal | None = Field(default=None, ge=0)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    safety_stock: Decimal | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    criticality: str | None = None
    usage_type: str = Field(default="habis_pakai", pattern="^(berumur_pakai|habis_pakai)$")

    _kritikalitas_dikenal = field_validator("criticality")(
        staticmethod(_kritikalitas))


class BarangUbah(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: int | None = Field(default=None, gt=0)
    unit_id: int | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    minimum_stock: Decimal | None = Field(default=None, ge=0)
    maximum_stock: Decimal | None = Field(default=None, ge=0)
    reorder_point: Decimal | None = Field(default=None, ge=0)
    safety_stock: Decimal | None = Field(default=None, ge=0)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    criticality: str | None = None
    is_active: bool | None = None
    usage_type: str | None = Field(default=None, pattern="^(berumur_pakai|habis_pakai)$")

    _kritikalitas_dikenal = field_validator("criticality")(
        staticmethod(_kritikalitas))


KOLOM_BARANG = ("id, sku, name, category_id, unit_id, unit_price, minimum_stock, "
                "maximum_stock, reorder_point, safety_stock, lead_time_days, "
                "criticality, is_active, usage_type")


def _periksa_rujukan_barang(cur, category_id: int | None, unit_id: int | None) -> None:
    """
    Memastikan kategori dan satuan yang ditunjuk benar-benar ada.

    Diperiksa sendiri, tidak diserahkan ke foreign key: pelanggaran foreign key
    menyebut nama constraint, dan pesan seperti itu tidak boleh keluar ke klien
    sekaligus tidak menolong siapa pun yang sedang mengisi formulir.
    """
    if category_id is not None:
        cur.execute("SELECT id FROM categories WHERE id = %s", (category_id,))
        if cur.fetchone() is None:
            raise not_found("category", category_id, "category_id")
    if unit_id is not None:
        cur.execute("SELECT id FROM units WHERE id = %s", (unit_id,))
        if cur.fetchone() is None:
            raise not_found("unit", unit_id, "unit_id")


@router.post("/api/items", status_code=201)
def buat_barang(body: BarangIn) -> dict:
    with transaction() as cur:
        _periksa_rujukan_barang(cur, body.category_id, body.unit_id)
        try:
            cur.execute(
                f"""
                INSERT INTO items
                    (sku, name, category_id, unit_id, unit_price, minimum_stock,
                     maximum_stock, reorder_point, safety_stock, lead_time_days,
                     criticality, usage_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING {KOLOM_BARANG}
                """,
                (body.sku.strip().upper(), body.name.strip(), body.category_id,
                 body.unit_id, body.unit_price, body.minimum_stock,
                 body.maximum_stock, body.reorder_point, body.safety_stock,
                 body.lead_time_days, body.criticality, body.usage_type),
            )
        except pg_errors.UniqueViolation as e:
            raise _bentrok(e, "item", {"sku": body.sku.strip().upper(),
                                       "name": body.name.strip()}) from None
        return cur.fetchone()


@router.patch("/api/items/{barang_id}")
def ubah_barang(barang_id: int, body: BarangUbah) -> dict:
    with transaction() as cur:
        _periksa_rujukan_barang(cur, body.category_id, body.unit_id)
        return _perbarui(
            cur, tabel="items", entitas="item", id_=barang_id,
            nilai={"sku": body.sku.strip().upper() if body.sku else None,
                   "name": body.name.strip() if body.name else None,
                   "category_id": body.category_id, "unit_id": body.unit_id,
                   "unit_price": body.unit_price,
                   "minimum_stock": body.minimum_stock,
                   "maximum_stock": body.maximum_stock,
                   "reorder_point": body.reorder_point,
                   "safety_stock": body.safety_stock,
                   "lead_time_days": body.lead_time_days,
                   "criticality": body.criticality, "is_active": body.is_active,
                   "usage_type": body.usage_type},
            kembalikan=KOLOM_BARANG)


@router.delete("/api/items/{barang_id}")
def hapus_barang(barang_id: int) -> dict:
    with transaction() as cur:
        return _hapus_bila_belum_terpakai(
            cur, tabel="items", entitas="item", id_=barang_id, nama_kolom="name",
            rujukan=[("inventory", "item_id"),
                     ("stock_movements", "item_id"),
                     ("stock_receipt_items", "item_id"),
                     ("stock_issue_items", "item_id"),
                     ("stock_transfer_items", "item_id"),
                     ("stock_adjustment_items", "item_id"),
                     ("purchase_order_items", "item_id"),
                     ("stock_batches", "item_id"),
                     ("serial_numbers", "item_id")])


# ==========================================================================
# Jarak antar gudang
# ==========================================================================
#
# KENAPA ADA DI SINI DAN BUKAN DI ROUTER TRANSFER. Isinya master data: ia tidak
# berubah dari hari ke hari, tidak lahir dari perhitungan apa pun, dan yang
# berhak menyuntingnya sama dengan yang berhak menyunting gudangnya sendiri --
# penjagaan peran pada router ini berlaku apa adanya. Router transfer MEMBACA
# tabel ini; ia tidak mengurusnya.

class JarakIn(BaseModel):
    from_warehouse_id: int = Field(..., gt=0)
    to_warehouse_id: int = Field(..., gt=0)
    # Keduanya boleh kosong, tetapi tidak boleh dua-duanya: baris tanpa jarak
    # dan tanpa waktu tempuh tidak menyatakan apa pun.
    distance_km: float | None = Field(default=None, ge=0, le=40000)
    lead_time_days: int | None = Field(default=None, ge=0, le=365)
    notes: str | None = None

    @field_validator("to_warehouse_id")
    @classmethod
    def gudang_berbeda(cls, v: int, info) -> int:
        if v == info.data.get("from_warehouse_id"):
            raise ValueError("gudang asal dan tujuan tidak boleh sama")
        return v


@router.get("/api/warehouse-distances")
def daftar_jarak() -> dict:
    """
    Seluruh pasangan jarak yang ditetapkan tangan.

    Tanpa halaman: satu perusahaan dengan sepuluh gudang paling banyak punya
    sembilan puluh baris, dan yang membacanya adalah layar penyuntingan yang
    memang membutuhkan seluruhnya sekaligus untuk menandai pasangan mana yang
    belum diisi.
    """
    with readonly() as cur:
        cur.execute(
            """
            SELECT d.id, d.from_warehouse_id, d.to_warehouse_id,
                   d.distance_km, d.lead_time_days, d.notes,
                   wf.code AS from_warehouse_code, wf.name AS from_warehouse_name,
                   wt.code AS to_warehouse_code,   wt.name AS to_warehouse_name
              FROM warehouse_distances d
              JOIN warehouses wf ON wf.id = d.from_warehouse_id
              JOIN warehouses wt ON wt.id = d.to_warehouse_id
             ORDER BY wf.code, wt.code
            """
        )
        baris = cur.fetchall()
    return {"items": baris, "total": len(baris)}


@router.put("/api/warehouse-distances")
def simpan_jarak(body: JarakIn) -> dict:
    """
    Menyimpan satu pasangan jarak; menimpa bila pasangannya sudah ada.

    PUT, bukan POST, dan itu bukan selera: yang dikirim adalah keadaan satu
    pasangan gudang yang identitasnya ditentukan isinya sendiri. Dua permintaan
    yang sama berturut-turut harus berakhir pada keadaan yang sama, bukan pada
    dua baris kembar yang saling bertentangan tentang jarak Surabaya-Jakarta.

    ARAHNYA BERARTI. A->B dan B->A adalah dua baris terpisah, karena waktu
    tempuh pulang tidak selalu sama dengan pergi.
    """
    if body.distance_km is None and body.lead_time_days is None:
        raise _galat("err.master.no_change", 422, "VALIDATION_ERROR")

    with transaction() as cur:
        for kolom, nilai in (("from_warehouse_id", body.from_warehouse_id),
                             ("to_warehouse_id", body.to_warehouse_id)):
            cur.execute("SELECT id FROM warehouses WHERE id = %s", (nilai,))
            if cur.fetchone() is None:
                raise not_found("warehouse", nilai, kolom)

        cur.execute(
            """
            INSERT INTO warehouse_distances
                (from_warehouse_id, to_warehouse_id, distance_km, lead_time_days, notes)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (company_id, from_warehouse_id, to_warehouse_id) DO UPDATE
               SET distance_km    = EXCLUDED.distance_km,
                   lead_time_days = EXCLUDED.lead_time_days,
                   notes          = EXCLUDED.notes,
                   updated_at     = now()
            RETURNING id, from_warehouse_id, to_warehouse_id, distance_km,
                      lead_time_days, notes
            """,
            (body.from_warehouse_id, body.to_warehouse_id, body.distance_km,
             body.lead_time_days, body.notes),
        )
        return cur.fetchone()


@router.delete("/api/warehouse-distances/{jarak_id}")
def hapus_jarak(jarak_id: int) -> dict:
    """
    Membuang satu pasangan jarak.

    Menghapusnya TIDAK melumpuhkan apa pun: pasangan tanpa baris jatuh kembali
    ke jarak haversine dari koordinat gudang, dan bila koordinatnya pun kosong,
    komponen jaraknya dinilai netral. Itulah sebabnya baris di sini boleh
    dihapus bebas sementara master gudang tidak.
    """
    with transaction() as cur:
        cur.execute("DELETE FROM warehouse_distances WHERE id = %s RETURNING id",
                    (jarak_id,))
        baris = cur.fetchone()
        if baris is None:
            raise not_found("warehouse", jarak_id, "id")
        return {"deleted": baris["id"]}
