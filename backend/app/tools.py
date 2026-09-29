# -*- coding: utf-8 -*-
"""
Tool yang boleh dipanggil model.

Model TIDAK PERNAH menyentuh basis data. Satu-satunya jalan memperoleh data
adalah lewat fungsi di berkas ini, dan setiap fungsi meneruskan panggilan ke
handler endpoint yang sama persis dengan yang dipakai frontend. Jadi apa pun
yang dilihat model sudah melewati filter, batas, dan validasi yang sama.

Pemanggilannya di dalam proses, bukan lewat HTTP ke diri sendiri: satu lapis
jaringan lebih sedikit, tanpa risiko kehabisan thread saat server memanggil
dirinya sendiri. Seluruh argumen dikirim eksplisit karena nilai bawaan
parameter endpoint berupa objek Query milik FastAPI, bukan None.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from . import decision
from .config import ASSISTANT_ALLOW_WRITE
from .errors import AppError
from .routers import (catalog, dashboard, inventory, lifetime, reports,
                      stock_issues, stock_receipts)
# Diberi alias supaya tidak tertukar dengan app/forecasting.py, mesin hitungnya.
from .routers import forecasting as forecasting_router
from .routers import transfer as transfer_router
from .schemas import (IssueItemIn, ReceiptItemIn, StockIssueIn, StockReceiptIn)

log = logging.getLogger("inventory.tools")

PESAN_DATA_GAGAL = "Data inventory tidak dapat diambil saat ini."

# Hasil tool dipangkas sebelum dikirim ke model: konteks model terbatas, dan
# ratusan baris mentah tidak membuat jawaban lebih baik.
BATAS_BARIS = 25


def jsonable(v: Any) -> Any:
    """Decimal, date, dan datetime tidak bisa langsung menjadi JSON."""
    if isinstance(v, Decimal):
        f = float(v)
        return int(f) if f.is_integer() else f
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return v


def _potong(hasil: Any) -> Any:
    """Membatasi jumlah baris pada amplop paginasi maupun daftar biasa."""
    if isinstance(hasil, dict):
        out = dict(hasil)
        for kunci in ("items", "rows", "recent_movements", "movements", "lines",
                      "stock", "by_item", "by_date", "by_supplier", "by_purpose",
                      "recent_transactions", "low_stock_preview"):
            nilai = out.get(kunci)
            if isinstance(nilai, list) and len(nilai) > BATAS_BARIS:
                out[kunci] = nilai[:BATAS_BARIS]
                out[f"{kunci}_truncated"] = True
                out[f"{kunci}_total_returned"] = len(nilai)
        return out
    if isinstance(hasil, list) and len(hasil) > BATAS_BARIS:
        return hasil[:BATAS_BARIS]
    return hasil


# --------------------------------------------------------------------------
# Pembungkus baca
# --------------------------------------------------------------------------

def get_dashboard() -> Any:
    return dashboard.dashboard()


def get_warehouses(q: str | None = None, only_active: bool = False) -> Any:
    return catalog.list_warehouses(q=q, only_active=only_active, page=1, page_size=50)


def get_warehouse(warehouse_id: int) -> Any:
    return catalog.get_warehouse(warehouse_id=warehouse_id)


def get_items(q: str | None = None, only_active: bool = False) -> Any:
    return catalog.list_items(
        q=q, category_id=None, only_active=only_active, page=1, page_size=50
    )


def get_item(item_id: int) -> Any:
    return catalog.get_item(item_id=item_id)


def get_inventory(q: str | None = None, warehouse_id: int | None = None) -> Any:
    return inventory.list_inventory(
        q=q, warehouse_id=warehouse_id, page=1, page_size=50
    )


def get_low_stock(warehouse_id: int | None = None) -> Any:
    return inventory.low_stock(warehouse_id=warehouse_id, page=1, page_size=50)


# Field yang diteruskan ke model. Deret harian (`historical_data`,
# `forecast_data`) sengaja TIDAK ikut: ratusan titik grafik tidak membuat
# penalaran lebih baik, hanya menghabiskan konteks.
#
# `status` (SAFE/ATTENTION/CRITICAL) SENGAJA TIDAK DIKIRIM. Nilainya ditentukan
# oleh perkiraan sisa stok pada AKHIR periode, sehingga ia bergerak hanya
# karena panjang periode diubah: barang yang sama berbunyi SAFE pada 7 hari dan
# CRITICAL pada 30 hari tanpa ada yang berubah pada stoknya. Itu mengukur
# panjang horizon, bukan kegawatan. Field-nya tetap terbit di API untuk
# antarmuka lama, tetapi model tidak boleh menjadikannya tingkat risiko.
# Urgensi diambil dari action_status, yang bersandar pada lead time dan tidak
# bergerak saat horizon berubah.
#
# SELURUH ANGKANYA VERSI TAMPILAN, yaitu bilangan bulat yang sama persis
# dengan yang tercetak di kartu -- lihat _SUMBER_TAMPILAN dan _DIBULATKAN di
# bawah. Model dilarang keras menghitung ulang atau membulatkan sendiri, jadi
# apa pun yang masuk ke sini keluar apa adanya pada jawabannya; mengirim
# "22,042" berarti pengguna membaca "22,042 PCS" di chat sementara layar
# berbunyi "22 PCS" untuk barang yang sama.
#
# Laju harian dikirim sebagai LABEL, bukan angka. Barang yang keluar tiga kali
# dalam enam puluh hari berlaju 0,003 per hari; dibulatkan ia menjadi nol dan
# jawaban model berubah menjadi "tidak ada pemakaian" -- salah, dan justru
# pada barang yang datanya paling tipis.
BIDANG_FORECAST = (
    "item", "warehouse",
    # Tiga basis stok, dikirim berdampingan supaya model tidak menebak.
    "current_stock", "reserved_stock", "available_stock",
    "forecast_days", "usage_frequency_label", "usage_frequency_detail",
    "forecast_usage",
    "projected_shortage", "expected_stock",
    "reorder_point", "minimum_stock",
    # Urgensi -- satu-satunya indikator keputusan.
    "action_status", "action_status_label",
    # Waktu menuju titik pesan: yang pertama sumber utama, yang kedua penanda
    # cakupan horizon.
    "days_to_rop", "reorder_point_within_horizon", "days_until_reorder_point",
    "days_until_stockout",
    # Ketahanan stok sampai habis, TIDAK dibatasi horizon: null di sini berarti
    # tidak ada pemakaian sama sekali, bukan "tidak habis dalam periode ini".
    "days_of_cover", "quality_level",
    # Catatan keandalan ikut serta pada SETIAP hasil prakiraan: angka yang
    # dikutip tanpa menyebut dasar historinya menyampaikan kepastian yang tidak
    # pernah dimiliki perhitungannya.
    "confidence_level", "confidence_note", "confidence_note_forecast",
    # --- lapisan reorder ---
    # Patokannya lead time, bukan horizon prakiraan. Dikirim berdampingan
    # dengan projected_shortage supaya model dapat menyatakan keduanya apa
    # adanya tanpa perlu menyimpulkan satu dari yang lain.
    # Masa tunggunya sendiri ikut dikirim, bukan hanya kebutuhan yang lahir
    # darinya: tanpa angka ini model dapat menyebut "kebutuhan selama masa
    # tunggu 14 PCS" tetapi tidak dapat menjawab "berapa lama menunggunya",
    # padahal itu pertanyaan pertama yang muncul setelah kalimat tadi. null
    # berarti master barang belum mengisinya -- atau mengisinya dengan nilai
    # yang tidak dapat dipakai -- dan itu berbeda dari nol.
    "lead_time_days",
    "safety_stock", "lead_time_demand", "effective_reorder_point",
    "days_to_effective_rop", "reorder_point_adequate", "recommended_order_qty",
    # Sampai berapa stok diisi saat pengadaan dilakukan. Tanpa angka ini,
    # jumlah pesanan yang lebih besar dari selisih terhadap titik pesan
    # terbaca seperti kelebihan pesan.
    "order_up_to_level",
)

# Field yang punya versi bulat sendiri pada hasil mesin; nilai itulah yang
# dikirim, di bawah nama lama supaya prompt dan jawaban lama tetap berlaku.
_SUMBER_TAMPILAN = {
    "current_stock": "current_stock_int",
    "available_stock": "available_stock_int",
    "reorder_point": "reorder_point_int",
    "minimum_stock": "minimum_stock_int",
    "safety_stock": "safety_stock_int",
    "lead_time_days": "lead_time_days_int",
    "lead_time_demand": "lead_time_demand_int",
    "effective_reorder_point": "effective_reorder_point_int",
    "days_to_effective_rop": "days_to_effective_rop_int",
    "days_of_cover": "days_of_cover_int",
    "order_up_to_level": "order_up_to_level_int",
}

# Sisanya dibulatkan di sini karena tidak dipakai antarmuka mana pun, jadi
# tidak punya field `_int` sendiri.
_DIBULATKAN = ("reserved_stock", "forecast_usage", "expected_stock",
               "projected_shortage", "days_to_rop")


def get_forecast(item_id: int, warehouse_id: int, days: int = 30) -> Any:
    """
    Prakiraan kebutuhan satu barang pada satu gudang.

    Memakai mesin yang sama persis dengan halaman Forecasting, dipanggil di
    dalam proses. Angkanya tidak pernah dihitung ulang di sini dan tidak
    pernah dihitung model: yang keluar dari fungsi ini adalah hasil mesin.
    """
    days = max(1, min(int(days), forecasting_router.FORECAST_DAYS_MAX))
    h = forecasting_router._susun(
        item_id, warehouse_id, days, forecasting_router.HISTORICAL_DAYS_DEFAULT
    )
    # Nama internal mesin dipetakan ke nama yang dipakai antarmuka, supaya
    # jawaban chatbot dan halaman Forecasting menyebut angka yang sama dengan
    # sebutan yang sama.
    rata = {
        **h,
        "forecast_usage": h["predicted_usage"],
        "expected_stock": h["predicted_remaining_stock"],
        "safety_stock": h["safety_stock_value"],
        "safety_stock_int": h["safety_stock_int"],
    }
    hasil = {}
    for k in BIDANG_FORECAST:
        if k in _SUMBER_TAMPILAN:
            hasil[k] = rata[_SUMBER_TAMPILAN[k]]
        elif k in _DIBULATKAN:
            hasil[k] = decision.bulat(rata[k])
        else:
            hasil[k] = rata[k]
    # Ketersediaan prakiraan dinyatakan sebagai boolean tersendiri, bukan lewat
    # `status`. Model butuh tahu "apakah ada angka", bukan "seberapa gawat
    # menurut horizon".
    kurang_data = h["status"] == forecasting_router.forecasting.STATUS_INSUFFICIENT
    hasil["has_forecast"] = not kurang_data
    if kurang_data:
        hasil["message"] = h["message"]
        hasil["requirements"] = h["requirements"]
    return hasil


# Field yang diteruskan tool keputusan reorder. Sengaja LEBIH SEMPIT daripada
# BIDANG_FORECAST: pertanyaan "apakah saya perlu order barang ini" dijawab oleh
# lapisan reorder saja, dan menyodorkan seluruh lapisan prakiraan di sebelahnya
# hanya mengundang model menyimpulkan urgensi dari angka horizon -- persis
# kekeliruan yang seluruh berkas ini berusaha cegah.
#
# TIDAK SATU PUN field di sini bergerak saat panjang periode prakiraan diubah.
# forecast_usage, projected_shortage, dan days_until_stockout sengaja TIDAK
# ikut; keduanya tersedia lewat get_forecast bila memang ditanyakan.
BIDANG_REORDER = (
    "item", "warehouse",
    # Tiga basis stok, berdampingan supaya model tidak menebak yang mana.
    "current_stock", "reserved_stock", "available_stock",
    # Ambang pada master barang, untuk dibandingkan dengan yang efektif.
    "reorder_point", "minimum_stock", "safety_stock", "lead_time_days",
    # --- inti keputusan ---
    "lead_time_demand", "effective_reorder_point",
    "effective_reorder_point_reached", "days_to_effective_rop",
    "days_of_cover", "reorder_point_adequate",
    "recommended_order_qty", "order_up_to_level",
    "action_status", "action_status_label",
    # --- kalimat yang SUDAH disusun backend, memakai angka bulat yang sama
    # dengan halaman Reorder. Model mengutipnya, bukan menyusun ulang. ---
    "reorder_status_reason", "effective_reorder_point_basis",
    "days_to_effective_rop_label", "order_qty_title", "order_qty_reason",
    "advice_text",
    # --- keandalan: WAJIB ikut, lihat catatan pada get_reorder_decision ---
    "confidence_level", "confidence_note",
    "low_confidence_estimate", "low_confidence_reason",
    "usage_frequency_label", "usage_frequency_detail",
)

_SUMBER_TAMPILAN_REORDER = {
    **_SUMBER_TAMPILAN,
    "days_of_cover": "days_of_cover_int",
}

_DIBULATKAN_REORDER = ("reserved_stock",)

# Horizon yang dipakai tool reorder. BUKAN pilihan model, dan bukan parameter
# tool: lapisan reorder tidak memakai forecast_days sama sekali -- titik pesan
# efektif, hari menuju titik pesan, dan jumlah pengadaan seluruhnya berpatokan
# lead time atas stok tersedia. Satu-satunya jalur halusnya adalah rata-rata
# pemakaian harian, yang dirata-ratakan dari deret prakiraan sepanjang horizon,
# jadi nilainya dipatok sama dengan halaman Reorder (HARI_ACUAN) supaya chatbot
# dan layar mustahil menyebut angka yang berbeda untuk barang yang sama.
HARI_ACUAN_REORDER = 7


def get_reorder_decision(item_id: int, warehouse_id: int) -> Any:
    """
    Keputusan pemesanan ulang satu barang pada satu gudang.

    INILAH jawaban untuk "apakah saya perlu order barang ini". Sebelumnya
    pertanyaan itu dijawab model dari angka stok mentah -- stok 156 terhadap
    titik pesan master 40 terbaca "aman" -- padahal ambang yang menentukan
    adalah titik pesan EFEKTIF (kebutuhan selama masa tunggu + safety stock),
    yang bisa jauh lebih tinggi daripada yang tercatat di master barang.

    Sumbernya mesin yang sama persis dengan halaman Reorder, dipanggil di dalam
    proses, dengan horizon yang dipatok sama. Tidak ada angka yang dihitung
    ulang di sini dan tidak ada yang boleh dihitung model.

    CATATAN KEANDALAN IKUT SERTA, BUKAN OPSIONAL. Seluruh angka di atas lahir
    dari laju pemakaian, dan laju pemakaian lahir dari histori yang panjangnya
    bisa saja hanya sepekan. Jawaban yang menyebut "titik pesan efektif 59
    UNIT" tanpa menyebut bahwa angka itu berdiri di atas histori tujuh hari
    menyampaikan kepastian yang tidak pernah dimiliki perhitungannya.
    """
    h = forecasting_router._susun(
        item_id, warehouse_id, HARI_ACUAN_REORDER,
        forecasting_router.HISTORICAL_DAYS_DEFAULT,
    )
    rata = {**h, "safety_stock": h["safety_stock_value"]}
    hasil = {}
    for k in BIDANG_REORDER:
        if k in _SUMBER_TAMPILAN_REORDER:
            hasil[k] = rata[_SUMBER_TAMPILAN_REORDER[k]]
        elif k in _DIBULATKAN_REORDER:
            hasil[k] = decision.bulat(rata[k])
        else:
            hasil[k] = rata[k]
    kurang_data = h["status"] == forecasting_router.forecasting.STATUS_INSUFFICIENT
    hasil["has_forecast"] = not kurang_data
    if kurang_data:
        hasil["message"] = h["message"]
        hasil["requirements"] = h["requirements"]
    return hasil


# Ringkasan prakiraan: hanya angka yang menjawab "berapa kebutuhan periode
# ini dan apakah stok menutupinya". Tidak memuat satu pun field lapisan
# reorder, supaya tool ini tidak dapat dipakai menyimpulkan urgensi.
BIDANG_RINGKASAN = (
    "item", "warehouse",
    "current_stock", "reserved_stock", "available_stock",
    "forecast_days", "usage_frequency_label", "usage_frequency_detail",
    "forecast_usage", "expected_stock", "projected_shortage",
    "days_until_reorder_point", "reorder_point_within_horizon",
    "days_until_stockout", "days_of_cover",
    # Catatan keandalannya versi PRAKIRAAN: ia menyebut angka yang benar-benar
    # ada pada jawaban ini. Versi reorder menyebut titik pesan efektif dan
    # kawan-kawannya, yang sengaja tidak ikut ke sini.
    "confidence_level", "confidence_note_forecast",
)


def get_forecast_summary(item_id: int, warehouse_id: int, days: int = 30) -> Any:
    """
    Ringkasan prakiraan satu barang: kebutuhan periode, sisa, dan kekurangan.

    Bentuk ringkas dari get_forecast, tanpa lapisan reorder. Dipakai untuk
    pertanyaan tentang KECUKUPAN pada suatu periode; pertanyaan tentang PERLU
    ATAU TIDAKNYA MEMESAN dijawab get_reorder_decision, dan pemisahan itulah
    yang membuat kedua jawaban tidak dapat tertukar.
    """
    days = max(1, min(int(days), forecasting_router.FORECAST_DAYS_MAX))
    h = forecasting_router._susun(
        item_id, warehouse_id, days, forecasting_router.HISTORICAL_DAYS_DEFAULT
    )
    rata = {
        **h,
        "forecast_usage": h["predicted_usage"],
        "expected_stock": h["predicted_remaining_stock"],
    }
    hasil = {}
    for k in BIDANG_RINGKASAN:
        if k in _SUMBER_TAMPILAN_REORDER:
            hasil[k] = rata[_SUMBER_TAMPILAN_REORDER[k]]
        elif k in ("reserved_stock", "forecast_usage", "expected_stock",
                   "projected_shortage"):
            hasil[k] = decision.bulat(rata[k])
        else:
            hasil[k] = rata[k]
    kurang_data = h["status"] == forecasting_router.forecasting.STATUS_INSUFFICIENT
    hasil["has_forecast"] = not kurang_data
    if kurang_data:
        hasil["message"] = h["message"]
        hasil["requirements"] = h["requirements"]
    return hasil


def get_stock_movements(
    item_id: int | None = None,
    warehouse_id: int | None = None,
    movement_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> Any:
    return inventory.list_movements(
        item_id=item_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        date_from=_tanggal(date_from),
        date_to=_tanggal(date_to),
        page=1,
        page_size=50,
    )


def get_stock_receipts(
    q: str | None = None,
    warehouse_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> Any:
    return stock_receipts.list_stock_receipts(
        q=q,
        warehouse_id=warehouse_id,
        supplier_id=None,
        date_from=_tanggal(date_from),
        date_to=_tanggal(date_to),
        page=1,
        page_size=50,
    )


def get_stock_receipt(receipt_id: int) -> Any:
    return stock_receipts.get_stock_receipt(receipt_id=receipt_id)


def get_stock_issues(
    q: str | None = None,
    warehouse_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> Any:
    return stock_issues.list_stock_issues(
        q=q,
        warehouse_id=warehouse_id,
        date_from=_tanggal(date_from),
        date_to=_tanggal(date_to),
        page=1,
        page_size=50,
    )


def get_stock_issue(issue_id: int) -> Any:
    return stock_issues.get_stock_issue(issue_id=issue_id)


def get_stock_report(warehouse_id: int | None = None) -> Any:
    return reports.stock_report(warehouse_id=warehouse_id)


def get_receipt_report(date_from: str | None = None, date_to: str | None = None) -> Any:
    return reports.receipt_report(
        date_from=_tanggal(date_from), date_to=_tanggal(date_to), warehouse_id=None
    )


def get_issue_report(date_from: str | None = None, date_to: str | None = None) -> Any:
    return reports.issue_report(
        date_from=_tanggal(date_from), date_to=_tanggal(date_to), warehouse_id=None
    )


def get_transfer_recommendations(
    warehouse_id: int | None = None,
    q: str | None = None,
) -> Any:
    return transfer_router.daftar_transfer(
        warehouse_id=warehouse_id, decision_filter=None, q=q,
        fuzzy=transfer_router.TRANSFER_FUZZY_BAWAAN,
        similarity=transfer_router.TRANSFER_KEMIRIPAN_MIN,
        page=1, page_size=50,
    )


def get_transfer_documents(
    status: str | None = None,
    warehouse_id: int | None = None,
    q: str | None = None,
) -> Any:
    return transfer_router.daftar_dokumen(
        status=status, warehouse_id=warehouse_id, q=q, page=1, page_size=50,
    )


def get_transfer_document(transfer_id: int) -> Any:
    return transfer_router.satu_dokumen(transfer_id=transfer_id)


def get_lifetime_analysis(
    warehouse_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
) -> Any:
    return lifetime.daftar(
        warehouse_id=warehouse_id, status=status, q=q, page=1, page_size=50,
    )


def get_lifetime_detail(item_id: int, warehouse_id: int) -> Any:
    return lifetime.detail(item_id=item_id, warehouse_id=warehouse_id)


def _tanggal(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Pembungkus tulis -- selalu butuh konfirmasi tegas
# --------------------------------------------------------------------------

def _pastikan_boleh_menulis(confirm: bool) -> None:
    if not ASSISTANT_ALLOW_WRITE:
        raise AppError(
            403,
            "WRITE_DISABLED",
            "Asisten sedang disetel hanya-baca, jadi tidak dapat membuat transaksi.",
        )
    if not confirm:
        raise AppError(
            422,
            "CONFIRMATION_REQUIRED",
            "Transaksi tidak dijalankan. Konfirmasi eksplisit dari pengguna "
            "diperlukan lebih dulu: sebutkan gudang, barang, dan jumlahnya, "
            "lalu minta pengguna menyetujui.",
        )


def create_stock_receipt(
    warehouse_id: int,
    supplier_id: int,
    received_date: str,
    items: list[dict],
    reference_number: str | None = None,
    confirm: bool = False,
) -> Any:
    _pastikan_boleh_menulis(confirm)
    payload = StockReceiptIn(
        warehouse_id=warehouse_id,
        supplier_id=supplier_id,
        received_date=_tanggal(received_date) or date.today(),
        reference_number=reference_number,
        notes=None,
        items=[
            ReceiptItemIn(
                item_id=int(b["item_id"]),
                quantity=Decimal(str(b["quantity"])),
                unit_price=Decimal(str(b.get("unit_price", 0))),
            )
            for b in items
        ],
    )
    return stock_receipts.create_stock_receipt(payload).model_dump()


def create_stock_issue(
    warehouse_id: int,
    issue_date: str,
    items: list[dict],
    purpose: str | None = None,
    reference_number: str | None = None,
    confirm: bool = False,
) -> Any:
    _pastikan_boleh_menulis(confirm)
    payload = StockIssueIn(
        warehouse_id=warehouse_id,
        issue_date=_tanggal(issue_date) or date.today(),
        purpose=purpose,
        reference_number=reference_number,
        notes=None,
        items=[
            IssueItemIn(item_id=int(b["item_id"]), quantity=Decimal(str(b["quantity"])))
            for b in items
        ],
    )
    return stock_issues.create_stock_issue(payload).model_dump()


# --------------------------------------------------------------------------
# Katalog untuk model
# --------------------------------------------------------------------------

def _t(name: str, desc: str, props: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required or [],
            },
        },
    }


_STR = {"type": "string"}
_BOOL = {"type": "boolean"}
# Penjelasan "boleh dikosongkan" ditulis pada tiap parameter opsional karena
# tanpa itu model cenderung berhenti dan bertanya balik kepada pengguna
# alih-alih memanggil tool dengan cakupan penuh.
_INT = {"type": "integer", "description": "Opsional. Kosongkan untuk mencakup seluruhnya."}
_TGL = {
    "type": "string",
    "description": "Opsional, format YYYY-MM-DD. Kosongkan untuk seluruh periode.",
}

SPESIFIKASI: list[dict] = [
    _t("get_dashboard", "Ringkasan seluruh persediaan dalam satu panggilan: jumlah gudang, "
       "jumlah barang, total stok, nilai persediaan, jumlah stok menipis, sepuluh transaksi "
       "terbaru, stok per gudang, serta total barang masuk dan keluar 30 hari terakhir. "
       "Tool pertama yang dipakai untuk pertanyaan umum tentang kondisi inventory maupun "
       "perbandingan masuk-keluar. Tidak perlu parameter apa pun.", {}),
    _t("get_warehouses", "Daftar gudang beserta jumlah barang dan total stok di dalamnya.",
       {"q": {**_STR, "description": "Cari kode atau nama gudang"}, "only_active": _BOOL}),
    _t("get_warehouse", "Detail satu gudang: profil, ringkasan stok, isi stok, pergerakan terakhir.",
       {"warehouse_id": _INT}, ["warehouse_id"]),
    _t("get_items", "Daftar master barang beserta total stok di seluruh gudang.",
       {"q": {**_STR, "description": "Cari SKU atau nama barang"}, "only_active": _BOOL}),
    _t("get_item", "Detail satu barang: master, total stok, stok per gudang, pergerakan terakhir.",
       {"item_id": _INT}, ["item_id"]),
    _t("get_inventory", "Stok berjalan per barang per gudang, termasuk stok tersedia dan penanda menipis.",
       {"q": {**_STR, "description": "Cari SKU atau nama barang"}, "warehouse_id": _INT}),
    _t("get_low_stock", "Barang yang stoknya menyentuh atau di bawah ambang pemesanan ulang, "
       "yaitu barang yang perlu direstock. Panggil tanpa parameter untuk seluruh gudang.",
       {"warehouse_id": _INT}),
    _t("get_forecast", "Prakiraan kebutuhan satu barang pada satu gudang untuk beberapa hari "
       "ke depan. Dipakai untuk SEMUA pertanyaan tentang masa depan: apakah stok cukup, "
       "berapa kebutuhan periode mendatang, kapan stok habis, kapan perlu memesan, atau "
       "berapa potensi kekurangannya. Wajib memakai item_id dan warehouse_id; keduanya "
       "diperoleh lebih dulu dari get_inventory dengan parameter q berisi SKU atau nama "
       "barang. JANGAN menghitung sendiri angka apa pun dari hasil ini. Arti tiap field: "
       "forecast_usage = perkiraan kebutuhan SELAMA seluruh periode forecast_days, bukan "
       "per hari; current_stock = stok fisik di gudang; reserved_stock = bagian stok yang "
       "sudah dikomitmenkan keluar; available_stock = stok yang benar-benar bisa dipakai; "
       "projected_shortage = potensi kekurangan, sudah dihitung terhadap available_stock, "
       "bernilai 0 bila mencukupi; expected_stock = perkiraan sisa stok fisik di akhir "
       "periode; action_status_label = tingkat urgensi, SATU-SATUNYA indikator keputusan; "
       "days_to_rop = perkiraan berapa hari lagi menyentuh titik pesan, PAKAI INI untuk "
       "pertanyaan kapan harus memesan; reorder_point_within_horizon = apakah titik pesan "
       "tersentuh di dalam periode ini; days_until_stockout = hari ke berapa stok habis; "
       "has_forecast = false berarti histori belum cukup dan seluruh angka kosong. "
       "Lapisan reorder, patokannya waktu tunggu pengiriman dan BUKAN periode prakiraan: "
       "lead_time_days = perkiraan berapa hari sejak pesanan dibuat sampai barang tiba, "
       "null berarti belum diisi pada master barang; "
       "lead_time_demand = perkiraan pemakaian selama menunggu kiriman, yaitu laju "
       "pemakaian harian dikali lead_time_days; "
       "effective_reorder_point = titik pesan hasil perhitungan, yaitu "
       "lead_time_demand ditambah safety_stock; INILAH ambang yang menentukan "
       "urgensi, sedangkan reorder_point adalah ambang yang ditetapkan pada master "
       "barang dan keduanya boleh berbeda; "
       "days_to_effective_rop = berapa hari lagi menyentuh titik pesan itu; "
       "order_up_to_level = sampai berapa stok diisi saat pengadaan dilakukan; "
       "reorder_point_adequate = false berarti titik pesan pada master barang terlalu "
       "rendah untuk menutup waktu tunggu, yaitu masalah data induk yang perlu "
       "dikalibrasi, bukan tingkat kegawatan; "
       "recommended_order_qty = jumlah yang disarankan dipesan, 0 berarti tidak perlu "
       "membeli sedangkan null berarti belum dapat dihitung. "
       "recommended_order_qty dan projected_shortage MENJAWAB PERTANYAAN BERBEDA dan "
       "biasanya berbeda nilainya; jangan pernah menyamakan atau menukar keduanya.",
       {"item_id": {"type": "integer", "description": "Wajib. Dari hasil get_inventory."},
        "warehouse_id": {"type": "integer", "description": "Wajib. Dari hasil get_inventory."},
        "days": {"type": "integer",
                 "description": "Panjang periode prakiraan dalam hari. Bawaannya 30."}},
       ["item_id", "warehouse_id"]),
    _t("get_reorder_decision",
       "KEPUTUSAN PEMESANAN ULANG satu barang pada satu gudang, langsung dari modul "
       "Reorder. INILAH tool yang menjawab pertanyaan 'apakah saya perlu order barang "
       "ini', 'kapan harus pesan', dan 'berapa yang harus dipesan'. JANGAN pernah "
       "menjawab pertanyaan itu dari angka stok mentah get_inventory atau get_low_stock: "
       "keduanya membandingkan stok dengan ambang pada master barang, sedangkan yang "
       "menentukan adalah titik pesan EFEKTIF yang dihitung dari waktu tunggu pengiriman "
       "dan cadangan penyangga, dan kedua angka itu kerap jauh berbeda. Wajib memakai "
       "item_id dan warehouse_id; keduanya diperoleh lebih dulu dari get_inventory dengan "
       "parameter q berisi SKU atau nama barang. Tidak ada parameter periode, dan itu "
       "disengaja: tidak satu pun angka pada hasil ini bergerak karena panjang periode "
       "prakiraan. JANGAN menghitung, mengurangkan, atau membulatkan angka apa pun dari "
       "hasil ini. Arti tiap field: "
       "action_status_label = tingkat urgensi (Stok aman, Perlu dipantau, Segera pesan), "
       "SATU-SATUNYA indikator keputusan; "
       "reorder_status_reason = kalimat alasan status itu, sudah menyebut angkanya; "
       "effective_reorder_point = ambang yang menentukan urgensi, yaitu lead_time_demand "
       "ditambah safety_stock, sedangkan reorder_point adalah ambang yang ditetapkan pada "
       "master barang; keduanya boleh berbeda dan bila menyebut keduanya jelaskan bedanya; "
       "effective_reorder_point_basis = kalimat asal-usul ambang itu; "
       "effective_reorder_point_reached = apakah stok tersedia sudah menyentuhnya; "
       "days_to_effective_rop = berapa hari lagi menyentuh ambang itu, dan "
       "days_to_effective_rop_label kalimat siap sebutnya; "
       "days_of_cover = berapa hari lagi stok habis sama sekali, TIDAK dibatasi periode "
       "prakiraan; "
       "recommended_order_qty = jumlah yang disarankan dipesan, 0 berarti belum perlu "
       "memesan sedangkan null berarti belum dapat dihitung dan itu BUKAN nol; "
       "order_qty_title dan order_qty_reason = judul dan alasan jumlah itu, siap dikutip; "
       "order_up_to_level = sampai berapa stok diisi saat pengadaan dilakukan; "
       "reorder_point_adequate = false berarti titik pesan pada master barang terlalu "
       "rendah untuk menutup waktu tunggu, yaitu masalah data induk yang perlu "
       "dikalibrasi, BUKAN tingkat kegawatan; "
       "advice_text = ringkasan siap sebut yang menggabungkan ketahanan stok dan jarak ke "
       "titik pesan, keduanya dalam hari; "
       "confidence_level dan confidence_note = mutu histori yang mendasari SELURUH angka "
       "di atas, WAJIB ikut disampaikan pada jawaban; "
       "has_forecast = false berarti histori belum cukup sehingga angka turunannya kosong.",
       {"item_id": {"type": "integer", "description": "Wajib. Dari hasil get_inventory."},
        "warehouse_id": {"type": "integer", "description": "Wajib. Dari hasil get_inventory."}},
       ["item_id", "warehouse_id"]),
    _t("get_forecast_summary",
       "RINGKASAN PRAKIRAAN satu barang untuk periode tertentu: perkiraan kebutuhan, "
       "perkiraan sisa stok, dan potensi kekurangan. Dipakai untuk pertanyaan tentang "
       "KECUKUPAN pada suatu periode - 'apakah stok cukup untuk 30 hari ke depan', "
       "'berapa kebutuhan bulan depan', 'kapan stok habis'. Sengaja TIDAK memuat satu pun "
       "angka keputusan reorder: pertanyaan 'apakah perlu memesan' dijawab "
       "get_reorder_decision, dan kedua jawaban itu tidak boleh tertukar. Wajib memakai "
       "item_id dan warehouse_id dari get_inventory. Arti tiap field: "
       "forecast_usage = perkiraan kebutuhan SELAMA seluruh periode forecast_days, bukan "
       "per hari; expected_stock = perkiraan sisa stok fisik di akhir periode; "
       "projected_shortage = potensi kekurangan terhadap available_stock, 0 berarti "
       "mencukupi; days_until_stockout = hari ke berapa stok habis DI DALAM periode ini, "
       "null berarti tidak habis di dalamnya; days_of_cover = ketahanan stok sampai habis "
       "tanpa dibatasi periode; confidence_level dan confidence_note = mutu histori yang "
       "mendasari seluruh angka itu, WAJIB ikut disampaikan.",
       {"item_id": {"type": "integer", "description": "Wajib. Dari hasil get_inventory."},
        "warehouse_id": {"type": "integer", "description": "Wajib. Dari hasil get_inventory."},
        "days": {"type": "integer",
                 "description": "Panjang periode prakiraan dalam hari. Bawaannya 30."}},
       ["item_id", "warehouse_id"]),
    _t("get_stock_movements", "Riwayat pergerakan stok, terurut dari yang paling baru. "
       "Kuantitas positif berarti masuk, negatif keluar. Panggil tanpa parameter untuk "
       "melihat aktivitas terbaru seluruh gudang.",
       {"item_id": _INT, "warehouse_id": _INT,
        "movement_type": {**_STR, "description": "Opsional: stock_in atau stock_out"},
        "date_from": _TGL, "date_to": _TGL}),
    _t("get_stock_receipts", "Daftar dokumen penerimaan barang, terurut dari yang terbaru.",
       {"q": _STR, "warehouse_id": _INT, "date_from": _TGL, "date_to": _TGL}),
    _t("get_stock_receipt", "Detail satu penerimaan beserta baris barang dan pergerakan yang dihasilkan.",
       {"receipt_id": _INT}, ["receipt_id"]),
    _t("get_stock_issues", "Daftar dokumen pengeluaran barang.",
       {"q": _STR, "warehouse_id": _INT, "date_from": _TGL, "date_to": _TGL}),
    _t("get_stock_issue", "Detail satu pengeluaran beserta baris barang dan pergerakan yang dihasilkan.",
       {"issue_id": _INT}, ["issue_id"]),
    _t("get_stock_report", "Laporan stok: ringkasan, komposisi per gudang dan per kategori.",
       {"warehouse_id": _INT}),
    _t("get_receipt_report", "Laporan barang masuk per supplier, per tanggal, dan per barang.",
       {"date_from": _TGL, "date_to": _TGL}),
    _t("get_issue_report", "Laporan barang keluar per keperluan, per tanggal, dan per barang.",
       {"date_from": _TGL, "date_to": _TGL}),
    _t("get_transfer_recommendations",
       "Rekomendasi transfer ANTAR GUDANG SENDIRI dari modul Warehouse Transfers: mana "
       "barang yang kekurangannya dapat ditutup dari gudang lain sebelum membeli. Hanya "
       "barang yang benar-benar kekurangan yang muncul. Tiap baris punya decision berupa "
       "TRANSFER (tertutup penuh dari gudang lain), TRANSFER_SEBAGIAN (tertutup sebagian, "
       "sisanya harus dibeli), atau PEMBELIAN (tidak ada gudang lain berkelebihan, harus "
       "beli seluruhnya). Dipakai untuk pertanyaan seperti 'barang apa yang bisa dipindah "
       "dari gudang lain', 'apakah perlu beli atau bisa transfer saja', atau 'berapa unit "
       "bisa dihemat dari transfer antar gudang'. warehouse_id menyaring gudang TUJUAN "
       "(yang kekurangan). Beda dengan get_transfer_documents: tool ini rekomendasi yang "
       "BELUM diajukan, bukan dokumen transfer yang sudah dibuat.",
       {"warehouse_id": {**_INT, "description":
                        "Opsional. Gudang TUJUAN yang kekurangan. Kosongkan untuk seluruhnya."},
        "q": {**_STR, "description": "Cari SKU atau nama barang"}}),
    _t("get_transfer_documents",
       "Dokumen transfer antar gudang yang SUDAH DIAJUKAN, terbaru lebih dulu, beserta "
       "statusnya (diajukan/disetujui/dikirim/diterima/dibatalkan). Dipakai untuk "
       "pertanyaan tentang transfer yang sedang berjalan atau riwayatnya, bukan untuk "
       "rekomendasi yang belum diajukan -- itu get_transfer_recommendations. warehouse_id "
       "menyaring gudang TUJUAN (peminta).",
       {"status": {**_STR, "description":
                   "Opsional: status dokumen, mis. draft, approved, shipped, received, cancelled"},
        "warehouse_id": {**_INT, "description": "Opsional. Gudang TUJUAN (peminta)."},
        "q": {**_STR, "description": "Cari nomor transfer"}}),
    _t("get_transfer_document", "Detail satu dokumen transfer: header, rute, dan baris barangnya.",
       {"transfer_id": _INT}, ["transfer_id"]),
    _t("get_lifetime_analysis",
       "Umur pakai komponen dari modul Lifetime Analysis: umur pakai aktual dibandingkan "
       "umur pakai yang diharapkan pada master barang, dan berapa kali sudah diganti. "
       "Status PREMATURE berarti diganti lebih cepat dari seharusnya, NORMAL berarti "
       "dalam batas wajar, EXTENDED berarti bertahan lebih lama dari seharusnya, dan "
       "INSUFFICIENT berarti belum cukup data atau belum punya umur pakai referensi pada "
       "master barang. Dipakai untuk pertanyaan seperti 'komponen apa yang cepat rusak', "
       "'apakah umur pakai bearing ini normal', atau 'berapa kali oli ini sudah diganti'.",
       {"warehouse_id": _INT,
        "status": {**_STR, "description":
                   "Opsional: PREMATURE, NORMAL, EXTENDED, atau INSUFFICIENT"},
        "q": {**_STR, "description": "Cari SKU atau nama komponen"}}),
    _t("get_lifetime_detail",
       "Riwayat penggantian satu komponen di satu gudang: tiap kejadian penggantian "
       "beserta umur pakai yang diakhirinya. Wajib memakai item_id dan warehouse_id, "
       "keduanya diperoleh lebih dulu dari get_inventory atau get_lifetime_analysis.",
       {"item_id": _INT, "warehouse_id": _INT}, ["item_id", "warehouse_id"]),
    _t(
        "create_stock_receipt",
        "Mencatat barang masuk. HANYA panggil setelah pengguna menyetujui gudang, "
        "supplier, barang, jumlah, dan harga secara tegas. Set confirm=true hanya "
        "bila persetujuan itu benar-benar sudah diberikan pada percakapan ini.",
        {
            "warehouse_id": _INT,
            "supplier_id": _INT,
            "received_date": _TGL,
            "reference_number": _STR,
            "confirm": {**_BOOL, "description": "true hanya bila pengguna sudah menyetujui"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"item_id": _INT, "quantity": {"type": "number"},
                                   "unit_price": {"type": "number"}},
                    "required": ["item_id", "quantity", "unit_price"],
                },
            },
        },
        ["warehouse_id", "supplier_id", "received_date", "items", "confirm"],
    ),
    _t(
        "create_stock_issue",
        "Mencatat barang keluar. HANYA panggil setelah pengguna menyetujui gudang, "
        "barang, dan jumlah secara tegas. Periksa dulu stok tersedia lewat "
        "get_inventory. Set confirm=true hanya bila persetujuan sudah diberikan.",
        {
            "warehouse_id": _INT,
            "issue_date": _TGL,
            "purpose": _STR,
            "reference_number": _STR,
            "confirm": {**_BOOL, "description": "true hanya bila pengguna sudah menyetujui"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"item_id": _INT, "quantity": {"type": "number"}},
                    "required": ["item_id", "quantity"],
                },
            },
        },
        ["warehouse_id", "issue_date", "items", "confirm"],
    ),
]

PELAKSANA: dict[str, Callable[..., Any]] = {
    "get_dashboard": get_dashboard,
    "get_warehouses": get_warehouses,
    "get_warehouse": get_warehouse,
    "get_items": get_items,
    "get_item": get_item,
    "get_inventory": get_inventory,
    "get_low_stock": get_low_stock,
    "get_forecast": get_forecast,
    "get_reorder_decision": get_reorder_decision,
    "get_forecast_summary": get_forecast_summary,
    "get_stock_movements": get_stock_movements,
    "get_stock_receipts": get_stock_receipts,
    "get_stock_receipt": get_stock_receipt,
    "get_stock_issues": get_stock_issues,
    "get_stock_issue": get_stock_issue,
    "get_stock_report": get_stock_report,
    "get_receipt_report": get_receipt_report,
    "get_issue_report": get_issue_report,
    "get_transfer_recommendations": get_transfer_recommendations,
    "get_transfer_documents": get_transfer_documents,
    "get_transfer_document": get_transfer_document,
    "get_lifetime_analysis": get_lifetime_analysis,
    "get_lifetime_detail": get_lifetime_detail,
    "create_stock_receipt": create_stock_receipt,
    "create_stock_issue": create_stock_issue,
}

TOOL_TULIS = {"create_stock_receipt", "create_stock_issue"}


def spesifikasi_aktif() -> list[dict]:
    if ASSISTANT_ALLOW_WRITE:
        return SPESIFIKASI
    return [s for s in SPESIFIKASI if s["function"]["name"] not in TOOL_TULIS]


def jalankan(nama: str, argumen: dict) -> dict:
    """
    Menjalankan satu tool dan mengembalikan hasil yang siap dikirim ke model.

    Kegagalan tidak dilempar keluar: model perlu tahu bahwa panggilannya gagal
    agar bisa memberi tahu pengguna, bukan diam-diam mengarang jawaban.
    """
    fn = PELAKSANA.get(nama)
    if fn is None:
        return {"ok": False, "error": f"Tool '{nama}' tidak dikenali."}
    try:
        hasil = fn(**argumen)
        return {"ok": True, "data": jsonable(_potong(hasil))}
    except AppError as e:
        log.info("Tool %s ditolak: %s", nama, e.message)
        return {"ok": False, "error": e.message}
    except TypeError as e:
        log.info("Argumen tool %s tidak sesuai: %s", nama, e)
        return {"ok": False, "error": f"Argumen untuk '{nama}' tidak sesuai: {e}"}
    except Exception as e:  # noqa: BLE001
        log.exception("Tool %s gagal", nama, exc_info=e)
        return {"ok": False, "error": PESAN_DATA_GAGAL}
