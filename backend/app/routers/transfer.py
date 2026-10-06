# -*- coding: utf-8 -*-
"""
Transfer Antar Gudang: rekomendasi dan dokumennya.

DUA LAPIS YANG SENGAJA DIPISAH.

    REKOMENDASI dihitung ulang setiap kali diminta, dari stok yang berlaku saat
    itu. Ia tidak disimpan di mana pun, persis seperti daftar Pemesanan Ulang:
    rekomendasi yang diawetkan akan menyebut surplus yang sudah tidak ada lagi
    begitu seseorang mengeluarkan barang dari gudang asal.

    DOKUMEN adalah apa yang terjadi setelah orang menyetujuinya. Ia disimpan,
    ia menggerakkan stok, dan ia membawa salinan beku dari skor serta alasan
    yang berlaku SAAT DIAJUKAN -- lihat migrasi 031.

TIDAK ADA SATU PUN RUMUS PRAKIRAAN ATAU REORDER DI BERKAS INI. Kekurangan tiap
gudang datang dari `forecasting._susun()` lalu `decision.lapisan_keputusan()`,
jalur yang sama persis dengan /api/forecast dan /api/reorder. Yang dikerjakan
di sini hanya: mengumpulkan jawaban mesin itu untuk seluruh pasangan
barang/gudang, mencocokkan yang kekurangan dengan yang berlebih, lalu
menyerahkan pemeringkatannya ke app/transfer.py.

BIAYANYA DIBATASI, dengan alasan yang sama seperti pada daftar Pemesanan
Ulang: tiap pasangan menjalankan rantai prakiraan penuh. Bedanya, di sini
pemotongan lebih berbahaya -- pasangan yang terbuang bukan hanya hilang dari
daftar, ia juga hilang sebagai KANDIDAT SUMBER bagi baris lain. Karena itu
`truncated` pada jawaban tidak boleh disembunyikan layar.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator

from .. import i18n, rute_ml, transfer
from .. import jalur as jalur_mod
from ..auth import wajib_penulis
from ..common import (LOCK_TRANSFER, PAGE_SIZE_DEFAULT, ambil_barang_aktif,
                      ambil_gudang_aktif, clamp_page, next_document_number,
                      page_envelope)
from ..config import (APP_TZ, TRANSFER_BATAS_BARIS, TRANSFER_FUZZY_BAWAAN,
                      TRANSFER_KEMIRIPAN_MIN)
from ..db import readonly, transaction
from ..errors import AppError, invalid, not_found
from ..ml import klasik
from . import forecasting as fr

router = APIRouter(tags=["transfer"])

# Jenis objek yang berdiri sebagai nilai bawaan Query milik FastAPI.
# Dibaca sekali di sini alih-alih diimpor dari jeroan pustaka, supaya
# pemeriksaannya tetap benar bila nama internalnya kelak berpindah.
Query_type = type(Query(None))

BATAS_BARIS = TRANSFER_BATAS_BARIS

# Urutan kerja pada daftar rekomendasi. Yang seluruhnya dapat ditutup transfer
# lebih dulu: itu pekerjaan yang menghemat pembelian penuh, dan menundanya
# berarti membeli barang yang sudah dimiliki perusahaan ini.
_URUT_KEPUTUSAN = {
    transfer.TRANSFER: 0,
    transfer.TRANSFER_SEBAGIAN: 1,
    transfer.PEMBELIAN: 2,
}


def _diminta(nilai, bawaan):
    """
    Nilai parameter yang BENAR-BENAR diminta pemanggil.

    Fungsi router di aplikasi ini kerap dipanggil langsung sebagai fungsi
    Python -- oleh tool asisten, oleh skrip pemeliharaan, oleh uji. Pada
    pemanggilan seperti itu FastAPI tidak pernah berjalan, sehingga objek
    `Query(...)` yang berdiri sebagai nilai bawaan ikut masuk apa adanya. Objek
    itu TRUTHY: `if warehouse_id:` menjadi benar untuk saringan yang tidak
    pernah diminta siapa pun, dan `float(similarity)` melempar TypeError.
    Keduanya tidak terlihat sama sekali lewat HTTP, dan itulah yang membuat
    kegagalan seperti ini bertahan lama.

    Catatan yang sama sudah ada pada `strategi` di routers/forecasting.py;
    di sini ia dijadikan satu fungsi supaya tidak ditulis ulang per parameter.
    """
    return bawaan if isinstance(nilai, Query_type) else nilai


# ==========================================================================
# Pengumpulan keadaan seluruh pasangan barang/gudang
# ==========================================================================

def _pasangan(q: str | None) -> tuple[list[dict], bool]:
    """
    Seluruh pasangan barang/gudang yang punya baris persediaan.

    TIDAK DISARING MENURUT GUDANG, dan itu berbeda dari daftar Pemesanan Ulang.
    Menyaring di sini akan membuang gudang lain dari himpunan yang sama --
    yaitu membuang justru kandidat sumbernya. Saringan gudang berlaku pada
    TUJUAN saja, dan dijalankan setelah kandidat dikumpulkan.
    """
    where, params = "WHERE it.is_active AND w.is_active", []
    if q:
        where += " AND (it.sku ILIKE %s OR it.name ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]

    with readonly() as cur:
        cur.execute(
            f"""
            SELECT inv.item_id, inv.warehouse_id
              FROM inventory inv
              JOIN items it     ON it.id = inv.item_id
              JOIN warehouses w ON w.id = inv.warehouse_id
             {where}
             ORDER BY inv.item_id, inv.warehouse_id
             LIMIT %s
            """,
            [*params, BATAS_BARIS + 1],
        )
        baris = [dict(r) for r in cur.fetchall()]
    return baris[:BATAS_BARIS], len(baris) > BATAS_BARIS


def _periode(days, model) -> tuple[int, str]:
    """
    Periode dan model yang sah, dengan bawaan yang SAMA seperti daftar
    Pemesanan Ulang -- diambil dari sana, bukan ditulis ulang, supaya kedua
    halaman mustahil memakai bawaan yang berbeda.
    """
    from . import reorder as ro  # impor tunda: kedua router saling mengenal
    model = _diminta(model, "")
    return (ro._hari(_diminta(days, None)),
            fr._model_sah(model if isinstance(model, str) else ""))


def _keadaan(item_id: int, warehouse_id: int, lang: str,
             days: int = fr.HORIZON_KEPUTUSAN,
             model: str = klasik.KUNCI_STATISTIK) -> dict | None:
    """
    Keadaan satu pasangan barang/gudang menurut mesin keputusan.

    Field yang diambil sengaja sedikit: hanya yang dipakai memilih sumber dan
    menakar kekurangan. Satu baris yang gagal dirakit mengembalikan None dan
    tidak menjatuhkan seluruh halaman -- master data yang terhapus di tengah
    perulangan tidak boleh membuat sembilan belas baris lain ikut hilang.
    """
    try:
        # MODE PERIODE, sama dengan daftar Pemesanan Ulang (6 Oktober 2026):
        # barang yang di sana terbaca kurang untuk periode yang dipilih, di
        # sini terbaca sebagai tujuan transfer dengan jumlah yang sama.
        h = fr._susun(item_id, warehouse_id, days,
                      fr.HISTORICAL_DAYS_DEFAULT, lang, model=model,
                      keputusan_periode=True)
    except Exception:
        return None

    return {
        "item_id": item_id,
        "warehouse_id": warehouse_id,
        "sku": h["item"]["sku"],
        "item_name": h["item"]["name"],
        "unit_code": h["item"]["unit_code"] or "",
        "warehouse_code": h["warehouse"]["code"],
        "warehouse_name": h["warehouse"]["name"],
        "available_stock_int": h["available_stock_int"],
        "current_stock_int": h["current_stock_int"],
        "effective_reorder_point_int": h["effective_reorder_point_int"],
        "safety_stock_int": h["safety_stock_int"],
        "lead_time_days_int": h["lead_time_days_int"],
        "days_of_cover_int": h["days_of_cover_int"],
        "decision_horizon_days": h["decision_horizon_days"],
        "forecast_usage_int": h["decision_horizon_usage_int"],
        "period_shortage_int": h["period_shortage_int"],
        "action_status": h["action_status"],
        "action_status_label": h["action_status_label"],
        "priority": h["priority"],
        # KEKURANGANNYA, DIPINJAM UTUH dari mesin reorder. Inilah satu-satunya
        # angka kebutuhan di seluruh modul ini; tidak ada rumus kedua.
        "recommended_order_qty": h["recommended_order_qty"],
        "reorder_reason": h["reorder_status_reason"],
    }


def _gudang() -> dict[int, dict]:
    """Koordinat dan waktu tempuh tiap gudang, sekali untuk seluruh perhitungan."""
    with readonly() as cur:
        cur.execute(
            """
            SELECT id, code, name, is_active, latitude, longitude,
                   transfer_lead_time_days
              FROM warehouses
            """
        )
        return {r["id"]: dict(r) for r in cur.fetchall()}


def _matriks() -> dict[tuple[int, int], dict]:
    """Jarak dan waktu tempuh yang ditetapkan tangan, berarah asal -> tujuan."""
    with readonly() as cur:
        cur.execute(
            """
            SELECT from_warehouse_id, to_warehouse_id, distance_km, lead_time_days
              FROM warehouse_distances
            """
        )
        return {(r["from_warehouse_id"], r["to_warehouse_id"]): dict(r)
                for r in cur.fetchall()}


# ==========================================================================
# Perakitan satu rekomendasi
# ==========================================================================

def _kandidat_mentah(tujuan: dict, semua: list[dict], *, fuzzy: bool,
                     ambang: float) -> list[tuple[dict, str, float]]:
    """
    Gudang mana saja yang menyimpan barang ini, beserta DASAR pencocokannya.

    COCOK PASTI SELALU LEBIH DULU DAN TIDAK PERNAH DIGANTIKAN. Pasangan dengan
    item_id yang sama adalah barang yang sama menurut master data; tidak ada
    tebakan di dalamnya, dan pencocokan nama tidak pernah dijalankan untuk
    gudang yang sudah punya barisnya sendiri. Fuzzy hanya menjangkau gudang
    yang TIDAK punya barang ini menurut nomornya.
    """
    hasil: list[tuple[dict, str, float]] = []
    sudah: set[int] = set()

    for baris in semua:
        if baris["warehouse_id"] == tujuan["warehouse_id"]:
            continue
        if baris["item_id"] == tujuan["item_id"]:
            hasil.append((baris, transfer.COCOK_SKU, 1.0))
            sudah.add(baris["warehouse_id"])

    if not fuzzy:
        return hasil

    for baris in semua:
        if baris["warehouse_id"] == tujuan["warehouse_id"]:
            continue
        if baris["item_id"] == tujuan["item_id"]:
            continue
        if baris["warehouse_id"] in sudah:
            continue
        cocok, skor = transfer.cocok_fuzzy(tujuan["item_name"],
                                           baris["item_name"], ambang)
        if cocok:
            hasil.append((baris, transfer.COCOK_FUZZY, skor))

    return hasil


def _susun_kandidat(*, tujuan: dict, mentah: list[tuple[dict, str, float]],
                    kebutuhan: int, gudang: dict[int, dict],
                    matriks: dict[tuple[int, int], dict],
                    lang: str) -> tuple[list[dict], list[dict]]:
    """
    Menilai tiap kandidat, lalu memisahkan yang layak dari yang ditolak.

    KEDUANYA DIKEMBALIKAN. Daftar yang hanya memuat pemenang tidak dapat
    menjawab pertanyaan yang paling sering datang di depan layar -- "gudang
    Jakarta kan punya barangnya, kenapa tidak dipakai?" -- dan pertanyaan itu
    dijawab satu kali di sini, bukan berulang kali lewat telepon.
    """
    layak: list[dict] = []
    ditolak: list[dict] = []

    g_tujuan = gudang.get(tujuan["warehouse_id"], {})

    for baris, dasar, skor_nama in mentah:
        g_asal = gudang.get(baris["warehouse_id"], {})
        surplus = transfer.surplus_gudang(baris["available_stock_int"],
                                          baris["effective_reorder_point_int"])

        tetap = matriks.get((baris["warehouse_id"], tujuan["warehouse_id"]), {})
        jarak, dasar_jarak = transfer.jarak_antar(
            jarak_tetap=tetap.get("distance_km"), asal=g_asal, tujuan=g_tujuan)
        # Waktu tempuh: yang ditetapkan per pasangan lebih dulu, lalu angka
        # khas gudang tujuan. Keduanya boleh kosong, dan kosong berarti
        # komponennya dinilai netral -- bukan nol.
        hari = tetap.get("lead_time_days")
        if hari is None:
            hari = g_tujuan.get("transfer_lead_time_days")

        satuan_sama = (baris["unit_code"] or "") == (tujuan["unit_code"] or "")
        alasan_tolak = transfer.kelayakan_sumber(
            status_aksi=baris["action_status"],
            aktif=bool(g_asal.get("is_active", True)),
            surplus=surplus,
            satuan_sama=satuan_sama,
        )

        k = {
            "from_warehouse_id": baris["warehouse_id"],
            "from_warehouse_code": baris["warehouse_code"],
            "from_warehouse_name": baris["warehouse_name"],
            "item_id": baris["item_id"],
            "sku": baris["sku"],
            "item_name": baris["item_name"],
            "unit_code": baris["unit_code"],
            "source_stock_int": baris["available_stock_int"],
            "source_reorder_point_int": baris["effective_reorder_point_int"],
            "source_status": baris["action_status"],
            "source_status_label": baris["action_status_label"],
            "surplus": int(surplus),
            "distance_km": jarak,
            "distance_basis": dasar_jarak,
            "lead_time_days": (int(hari) if hari is not None else None),
            "match_type": dasar,
            "match_similarity": (round(float(skor_nama), 4)
                                 if dasar == transfer.COCOK_FUZZY else None),
        }

        if alasan_tolak:
            k["score"] = 0
            k["eligible"] = False
            k["rejected_reason"] = alasan_tolak
            k["rejected_label"] = transfer.label_penolakan(alasan_tolak, lang)
            k["why"] = k["rejected_label"]
            ditolak.append(k)
            continue

        nilai = transfer.skor_kandidat(
            kebutuhan=kebutuhan, surplus=surplus,
            tersedia_sumber=baris["available_stock_int"],
            jarak_km=jarak, lead_time_hari=hari,
            kemiripan_nama=(skor_nama if dasar == transfer.COCOK_FUZZY else 1.0),
        )
        k.update(nilai)
        k["eligible"] = True
        k["rejected_reason"] = None
        k["rejected_label"] = None
        k["why"] = transfer.kalimat_kandidat(kandidat=k, kebutuhan=kebutuhan,
                                             lang=lang)
        layak.append(k)

    layak.sort(key=transfer.urutan_kandidat)
    ditolak.sort(key=lambda k: (str(k["from_warehouse_code"]), k["item_id"]))
    return layak, ditolak


def _rekomendasi(*, tujuan: dict, semua: list[dict], gudang: dict[int, dict],
                 matriks: dict[tuple[int, int], dict], fuzzy: bool,
                 ambang: float, lang: str) -> dict:
    """Satu baris rekomendasi lengkap untuk satu barang di satu gudang tujuan."""
    kebutuhan = tujuan["recommended_order_qty"]
    butuh = transfer.bulat_atas(kebutuhan) if kebutuhan is not None else None

    mentah = _kandidat_mentah(tujuan, semua, fuzzy=fuzzy, ambang=ambang)
    layak, ditolak = _susun_kandidat(
        tujuan=tujuan, mentah=mentah, kebutuhan=butuh or 0,
        gudang=gudang, matriks=matriks, lang=lang)

    rencana = transfer.rencana(kebutuhan=kebutuhan, kandidat=layak,
                               ditolak=ditolak, lang=lang)

    return {
        # --- tujuan ---
        "item_id": tujuan["item_id"],
        "warehouse_id": tujuan["warehouse_id"],
        "sku": tujuan["sku"],
        "item_name": tujuan["item_name"],
        "unit_code": tujuan["unit_code"],
        "to_warehouse_id": tujuan["warehouse_id"],
        "to_warehouse_code": tujuan["warehouse_code"],
        "to_warehouse_name": tujuan["warehouse_name"],

        # --- keadaan gudang tujuan, seluruhnya dari mesin keputusan ---
        "available_stock_int": tujuan["available_stock_int"],
        "effective_reorder_point_int": tujuan["effective_reorder_point_int"],
        "safety_stock_int": tujuan["safety_stock_int"],
        "lead_time_days_int": tujuan["lead_time_days_int"],
        "days_of_cover_int": tujuan["days_of_cover_int"],
        # Kebutuhan periode yang dipilih: angka yang menjelaskan kekurangannya,
        # sama dengan kolom Kebutuhan pada daftar Pemesanan Ulang.
        "decision_horizon_days": tujuan.get("decision_horizon_days",
                                            fr.HORIZON_KEPUTUSAN),
        "forecast_usage_int": tujuan.get("forecast_usage_int"),
        "action_status": tujuan["action_status"],
        "action_status_label": tujuan["action_status_label"],
        "priority": tujuan["priority"],
        "reorder_reason": tujuan["reorder_reason"],

        # --- rencana ---
        "need_qty": rencana["need_qty"],
        "transfer_qty": rencana["transfer_qty"],
        "purchase_qty": rencana["purchase_qty"],
        "decision": rencana["decision"],
        "decision_label": transfer.label_keputusan(rencana["decision"], lang),
        "reason": rencana["reason"],
        "legs": rencana["legs"],
        # Kandidat yang lolos tetapi TIDAK kebagian alokasi tetap terbit:
        # yang membaca layar berhak tahu bahwa ada pilihan kedua bila gudang
        # teratas menolak mengirim hari itu.
        "candidates": layak,
        "rejected": ditolak,
        "candidate_count": len(layak) + len(ditolak),
    }


# ==========================================================================
# Daftar rekomendasi
# ==========================================================================

@router.get("/api/transfer")
def daftar_transfer(
    warehouse_id: int | None = Query(None, gt=0,
                                     description="Saring gudang TUJUAN"),
    decision_filter: str | None = Query(
        None, alias="decision",
        description="TRANSFER, TRANSFER_SEBAGIAN, PEMBELIAN"),
    q: str | None = Query(None, description="Cari SKU atau nama barang"),
    fuzzy: bool = Query(TRANSFER_FUZZY_BAWAAN,
                        description="Cocokkan juga lewat kemiripan nama barang"),
    similarity: float = Query(TRANSFER_KEMIRIPAN_MIN, ge=0.5, le=1.0),
    days: int = Query(fr.HORIZON_KEPUTUSAN, ge=1, le=fr.FORECAST_DAYS_MAX,
                      description="Periode kebutuhan, sama dengan /api/reorder"),
    model: str = Query(klasik.KUNCI_STATISTIK,
                       description="Model prakiraan, sama dengan /api/reorder"),
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
    lang: str = Query(i18n.BAHASA_BAWAAN),
) -> dict:
    """
    Mana saja yang dapat ditutup dari gudang sendiri sebelum dibeli.

    HANYA BARIS YANG MEMANG KEKURANGAN yang muncul. Barang yang stoknya aman
    tidak punya kebutuhan untuk ditutup, dan menampilkannya dengan kolom
    "qty transfer 0" hanya memanjangkan daftar tanpa menambah satu pun
    tindakan yang dapat diambil.

    RINGKASANNYA DIHITUNG ATAS SELURUH HASIL, bukan atas halaman yang sedang
    tampil -- alasan yang sama seperti pada daftar Pemesanan Ulang.
    """
    warehouse_id = _diminta(warehouse_id, None)
    decision_filter = _diminta(decision_filter, None)
    q = _diminta(q, None)
    fuzzy = bool(_diminta(fuzzy, TRANSFER_FUZZY_BAWAAN))
    similarity = float(_diminta(similarity, TRANSFER_KEMIRIPAN_MIN))
    page, page_size, offset = clamp_page(page, page_size)
    lang = i18n.normalisasi(_diminta(lang, i18n.BAHASA_BAWAAN))
    days, model = _periode(days, model)

    pasangan, terpotong = _pasangan(q)
    semua = [k for k in (_keadaan(p["item_id"], p["warehouse_id"], lang,
                                  days, model)
                         for p in pasangan) if k is not None]

    gudang, matriks = _gudang(), _matriks()

    # Tujuan = baris yang mesin reorder menyatakan ada yang perlu dipesan.
    # `recommended_order_qty` None berarti belum dapat dihitung; ia bukan
    # kekurangan dan tidak boleh menghasilkan rencana transfer.
    tujuan = [k for k in semua if (k["recommended_order_qty"] or 0) > 0]
    if warehouse_id:
        tujuan = [k for k in tujuan if k["warehouse_id"] == warehouse_id]

    hasil = [_rekomendasi(tujuan=t, semua=semua, gudang=gudang, matriks=matriks,
                          fuzzy=fuzzy, ambang=similarity, lang=lang)
             for t in tujuan]

    ringkas = {
        "total_baris": len(hasil),
        "dapat_transfer": sum(1 for r in hasil
                              if r["decision"] == transfer.TRANSFER),
        "transfer_sebagian": sum(1 for r in hasil
                                 if r["decision"] == transfer.TRANSFER_SEBAGIAN),
        "harus_beli": sum(1 for r in hasil
                          if r["decision"] == transfer.PEMBELIAN),
        # Total unit yang dapat dipindahkan alih-alih dibeli. Inilah angka yang
        # menyatakan nilai modul ini dalam satu bilangan.
        "total_qty_transfer": sum(r["transfer_qty"] for r in hasil),
        "total_qty_beli": sum(r["purchase_qty"] or 0 for r in hasil),
        "memakai_fuzzy": bool(fuzzy),
        "ambang_kemiripan": round(float(similarity), 4),
    }

    if decision_filter:
        hasil = [r for r in hasil if r["decision"] == decision_filter]

    # Yang seluruhnya tertutup transfer lebih dulu, lalu yang terbesar
    # jumlahnya: dua baris berkeputusan sama diurutkan menurut besarnya akibat.
    hasil.sort(key=lambda r: (
        _URUT_KEPUTUSAN.get(r["decision"], 9),
        -(r["transfer_qty"] or 0),
        r["sku"],
    ))

    total = len(hasil)
    halaman = hasil[offset:offset + page_size]
    _lampirkan_rute(halaman)
    return {
        "items": halaman,
        "summary": ringkas,
        # Periode yang dipakai menakar kekurangan seluruh daftar ini.
        "horizon_days": days,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "truncated": terpotong,
        "row_limit": BATAS_BARIS,
    }


def _batas_waktu(b: dict) -> float | None:
    """
    Kapan barang paling lambat harus tiba di tujuan.

    Transfer yang lebih lambat daripada MEMBELI BARU tidak ada gunanya, jadi
    batasnya lead time pembelian. Bila stok tujuan habis lebih cepat dari itu
    (sisa hari stok), yang berlaku sisa hari stok -- dengan lantai tiga hari
    bagi barang yang sudah kosong, supaya batas nol tidak menandai SEMUA moda
    terlambat sekaligus dan skor kehilangan daya bedanya.
    """
    lead = b.get("lead_time_days_int")
    sisa = b.get("days_of_cover_int")
    kandidat = []
    if lead:
        kandidat.append(float(lead))
    if sisa is not None:
        kandidat.append(float(sisa) if sisa > 0 else 3.0)
    return min(kandidat) if kandidat else None


def _lampirkan_rute(baris: list[dict]) -> None:
    """
    Menempelkan SATU rute terbaik pada tiap kiriman rekomendasi -- PER PASANGAN
    GUDANG, bukan per barang.

    Barang-barang yang sama-sama berangkat dari A ke B naik SATU pengiriman
    (itulah dokumen "rute" yang diajukan), jadi modanya satu dan biayanya
    dibagi menurut jumlah. Menghitungnya per barang menghasilkan garis yang
    berbohong: peta menggambar satu garis untuk pasangan itu, sementara tiap
    kartunya menyebut moda yang berbeda (darat untuk yang satu, udara untuk
    yang lain, dalam pasangan yang sama).

    Yang dinilai adalah pengiriman GABUNGAN: jumlah dan nilai seluruh barang,
    dengan batas waktu yang PALING KETAT di antara barang-barangnya -- satu
    barang yang mendesak menentukan modanya untuk seluruh pengiriman.

    Model dan riwayatnya dimuat SEKALI untuk seluruh halaman.
    """
    for b in baris:
        b["route_deadline_days"] = _batas_waktu(b)
    kaki = [(b, k) for b in baris for k in b["legs"] if k["transfer_qty"] > 0]
    if not kaki:
        return
    pasangan: dict[tuple[int, int], list[tuple[dict, dict]]] = {}
    for b, k in kaki:
        pasangan.setdefault((k["from_warehouse_id"], b["to_warehouse_id"]), []).append((b, k))
    with readonly() as cur:
        konteks = rute_ml.bundel(cur)
        cur.execute("SELECT id, unit_price FROM items WHERE id = ANY(%s)",
                    ([k["item_id"] for _, k in kaki],))
        harga = {r["id"]: float(r["unit_price"]) for r in cur.fetchall()}
        for (dari, ke), isi in pasangan.items():
            total_qty = sum(k["transfer_qty"] for _, k in isi)
            total_nilai = sum(harga.get(k["item_id"], 0.0) * k["transfer_qty"] for _, k in isi)
            batas = [b["route_deadline_days"] for b, _ in isi if b["route_deadline_days"]]
            batas_min = min(batas) if batas else None
            try:
                r = rute_ml.rekomendasi(cur, dari_id=dari, ke_id=ke, jumlah=total_qty,
                                        nilai=total_nilai, batas_hari=batas_min,
                                        konteks=konteks)
            except KeyError:
                continue
            if not r["options"]:
                continue
            o = r["options"][0]
            for _, k in isi:
                bagian = k["transfer_qty"] / total_qty
                k["route_ml"] = {
                    "mode": o["mode"],
                    "predicted_days": o["predicted_days"],
                    # Biaya kiriman gabungan dibagi menurut jumlah unit.
                    "predicted_cost": round(o["predicted_cost"] * bagian, -3),
                    "predicted_received": int(round(k["transfer_qty"] * o["predicted_received_ratio"])),
                    "alternatives": len(r["options"]) - 1,
                    # Kiriman gabungan yang dinilai; kartu memakainya untuk
                    # menanyakan perbandingan moda pada angka yang SAMA.
                    "shipment_qty": total_qty,
                    "shipment_value": round(total_nilai, 2),
                    "shipment_items": len(isi),
                    "shipment_cost": o["predicted_cost"],
                    "deadline_days": batas_min,
                }


@router.get("/api/transfer/rute-ml")
def rute_terbaik(
    from_warehouse_id: int = Query(..., gt=0),
    to_warehouse_id: int = Query(..., gt=0),
    quantity: int = Query(..., gt=0, description="Jumlah unit yang dikirim"),
    item_id: int | None = Query(None, gt=0, description="Untuk menakar nilai barang"),
    value: float | None = Query(None, ge=0, description="Nilai barang (rupiah); menggantikan item_id"),
    priority: str = Query("seimbang", description="seimbang, tercepat, termurah, terpenuh"),
    deadline_days: float | None = Query(None, gt=0, le=120,
                                        description="Batas lama tempuh, mis. lead time pembelian baru"),
) -> dict:
    """
    Moda angkut terbaik (darat/laut/udara) untuk satu kiriman, diperingkat.

    Model gradient boosting yang dilatih dari riwayat transfer SELESAI
    perusahaan ini memperkirakan lama di jalan, biaya, dan jumlah yang sampai
    untuk tiap moda; skor berbobot menurut `priority`. Bila riwayat belum
    cukup, jawabannya memakai tarif standar dan `model.kind` menyebutnya.
    """
    if from_warehouse_id == to_warehouse_id:
        raise invalid("gudang asal dan tujuan tidak boleh sama", "to_warehouse_id")
    if priority not in rute_ml.PRIORITAS:
        raise invalid(f"priority harus salah satu dari: {', '.join(rute_ml.PRIORITAS)}",
                      "priority")
    with readonly() as cur:
        nilai = value
        if nilai is None and item_id:
            cur.execute("SELECT unit_price FROM items WHERE id = %s", (item_id,))
            b = cur.fetchone()
            if b is None:
                raise not_found("item", item_id, "item_id")
            nilai = float(b["unit_price"]) * quantity
        try:
            return rute_ml.rekomendasi(
                cur, dari_id=from_warehouse_id, ke_id=to_warehouse_id,
                jumlah=quantity, nilai=nilai or 0.0, prioritas=priority,
                batas_hari=deadline_days)
        except KeyError:
            raise not_found("warehouse", from_warehouse_id, "from_warehouse_id") from None


@router.get("/api/transfer/jalur")
def jalur_jalan(
    dari_lat: float = Query(..., ge=-90, le=90),
    dari_lon: float = Query(..., ge=-180, le=180),
    ke_lat: float = Query(..., ge=-90, le=90),
    ke_lon: float = Query(..., ge=-180, le=180),
):
    """
    Pilihan jalan dari satu koordinat ke koordinat lain, untuk digambar peta.
    Tiap pilihan membawa jarak, durasi (jalan lengang, tanpa lalu lintas
    langsung), penanda tercepat/terpendek, ruas tol, dan estimasi biaya dari
    ASUMSI di config (dikirim bersama hasilnya). Rekomendasinya deterministik
    dan alasannya berupa kode + angka; kalimatnya disusun layar. TIDAK ADA
    penilaian keamanan.

    `ada: false` BUKAN galat: OSRM boleh saja tidak terjangkau, dan peta
    menjawabnya dengan kembali ke busur. Endpoint ini hanya memberi garis;
    tidak ada angka bisnis yang lahir di sini.
    """
    opsi = jalur_mod.jalur((dari_lat, dari_lon), (ke_lat, ke_lon))
    if not opsi:
        return {"ada": False, "opsi": []}
    return {
        "ada": True,
        "opsi": opsi,
        "rekomendasi": jalur_mod.analisis(opsi),
        "asumsi": jalur_mod.asumsi(),
    }


@router.get("/api/transfer/detail")
def detail_transfer(
    item_id: int = Query(..., gt=0),
    warehouse_id: int = Query(..., gt=0, description="Gudang TUJUAN"),
    fuzzy: bool = Query(TRANSFER_FUZZY_BAWAAN),
    similarity: float = Query(TRANSFER_KEMIRIPAN_MIN, ge=0.5, le=1.0),
    days: int = Query(fr.HORIZON_KEPUTUSAN, ge=1, le=fr.FORECAST_DAYS_MAX),
    model: str = Query(klasik.KUNCI_STATISTIK),
    lang: str = Query(i18n.BAHASA_BAWAAN),
) -> dict:
    """
    Satu barang di satu gudang, dengan SELURUH kandidat dan rincian skornya.

    Dipakai panel yang terbuka di bawah satu baris daftar. Ia menghitung ulang
    dari sumber yang sama, bukan menerima potongan daftar sebelumnya: panel
    yang menampilkan angka dari permintaan sebelumnya akan menyebut surplus
    yang sudah tidak ada lagi.
    """
    fuzzy = bool(_diminta(fuzzy, TRANSFER_FUZZY_BAWAAN))
    similarity = float(_diminta(similarity, TRANSFER_KEMIRIPAN_MIN))
    lang = i18n.normalisasi(_diminta(lang, i18n.BAHASA_BAWAAN))

    days, model = _periode(days, model)
    tujuan = _keadaan(item_id, warehouse_id, lang, days, model)
    if tujuan is None:
        raise not_found("item", item_id, "item_id")

    pasangan, terpotong = _pasangan(None)
    semua = [k for k in (_keadaan(p["item_id"], p["warehouse_id"], lang,
                                  days, model)
                         for p in pasangan) if k is not None]
    # Tujuan wajib ikut walau ia berada di luar potongan BATAS_BARIS: tanpa
    # itu, membuka detail satu baris dapat menjawab keadaan yang berbeda dari
    # barisnya sendiri.
    if not any(k["item_id"] == item_id and k["warehouse_id"] == warehouse_id
               for k in semua):
        semua.append(tujuan)

    hasil = _rekomendasi(tujuan=tujuan, semua=semua, gudang=_gudang(),
                         matriks=_matriks(), fuzzy=fuzzy, ambang=similarity,
                         lang=lang)
    hasil["truncated"] = terpotong
    return hasil


# ==========================================================================
# Dokumen transfer
# ==========================================================================

class BarisTransferIn(BaseModel):
    item_id: int = Field(..., gt=0, description="Barang yang benar-benar dikirim")
    quantity: Decimal
    # Kebutuhan barang mana yang hendak ditutup baris ini. Sama dengan item_id
    # kecuali pada pencocokan fuzzy -- lihat migrasi 031.
    for_item_id: int | None = Field(default=None, gt=0)
    match_type: str | None = Field(default=None, max_length=20)
    match_similarity: float | None = Field(default=None, ge=0, le=1)

    @field_validator("quantity")
    @classmethod
    def qty_bulat_positif(cls, v: Decimal) -> Decimal:
        """
        Kuantitas transfer WAJIB bilangan bulat.

        Bukan kerapian tampilan: yang dipindahkan barang fisik, dan setengah
        bearing tidak dapat dinaikkan ke truk. Ditolak di sini, di pintu masuk,
        supaya tidak ada satu pun baris berdesimal yang pernah tersimpan lalu
        harus dibulatkan lagi di setiap layar yang membacanya.
        """
        if v <= 0:
            raise ValueError("quantity harus lebih besar dari 0")
        if v != v.to_integral_value():
            raise ValueError("quantity transfer harus bilangan bulat")
        return v


class TransferIn(BaseModel):
    from_warehouse_id: int = Field(..., gt=0)
    to_warehouse_id: int = Field(..., gt=0)
    transfer_date: date_type | None = None
    notes: str | None = None
    # Jejak keputusan, dibekukan pada dokumen. Boleh kosong untuk transfer yang
    # diketik orang tanpa lewat rekomendasi.
    source: str | None = Field(default="transfer_engine", max_length=30)
    score: int | None = Field(default=None, ge=0, le=100)
    reason: str | None = None
    distance_km: float | None = Field(default=None, ge=0)
    # Moda yang dipilih (rekomendasi rute) dan janji lama tempuhnya; boleh
    # kosong. Biaya sesungguhnya dicatat kelak, saat barang diterima.
    transport_mode: str | None = Field(default=None, pattern="^(darat|laut|udara)$")
    planned_days: float | None = Field(default=None, ge=0, le=90)
    items: list[BarisTransferIn] = Field(..., min_length=1)


class TerimaBarisIn(BaseModel):
    item_id: int = Field(..., gt=0)
    received_quantity: Decimal = Field(..., ge=0)


class StatusTransferIn(BaseModel):
    status: str = Field(..., description="approved, in_transit, completed, cancelled")
    # Hanya bermakna pada status "completed". Barang yang tidak disebut dianggap
    # diterima utuh; yang disebut tidak boleh melebihi jumlah kirimnya.
    received: list[TerimaBarisIn] | None = None
    # Boleh diisi saat menerima bila sudah diketahui; biasanya menyusul sendiri
    # lewat PATCH /api/transfers/{id}/biaya ketika tagihan ekspedisi tiba.
    shipping_cost: Decimal | None = Field(default=None, ge=0)

    @field_validator("status")
    @classmethod
    def status_dikenal(cls, v: str) -> str:
        if v not in transfer.STATUS:
            raise ValueError(f"status harus salah satu dari: {', '.join(transfer.STATUS)}")
        return v


def _stok_kurang(sku: str, gudang: str, diminta, tersedia) -> AppError:
    return AppError(
        422, "INSUFFICIENT_STOCK",
        i18n.t("err.transfer.no_surplus", i18n.bahasa_permintaan(),
               gudang=gudang, sku=sku,
               diminta=f"{Decimal(diminta):.0f}", tersedia=f"{Decimal(tersedia):.0f}"),
        "items.quantity",
    )


@router.post("/api/transfers", status_code=201,
             dependencies=[Depends(wajib_penulis)])
def ajukan_transfer(payload: TransferIn) -> dict:
    """
    Mengajukan satu transfer. TIDAK menyentuh stok sama sekali.

    Pengajuan hanya mencatat niat. Stok baru bergerak pada perpindahan status
    berikutnya -- dicadangkan saat disetujui, berkurang saat dikirim, bertambah
    saat diterima -- dan pemisahan itu yang membuat dokumen ini dapat ditolak
    tanpa meninggalkan jejak pada persediaan.

    Ketersediaan tetap DIPERIKSA di sini, di atas stok yang tersedia hari ini.
    Mengajukan transfer 40 unit dari gudang yang hanya punya 12 bukan rencana
    melainkan kesalahan ketik, dan menemukan itu tiga hari kemudian saat
    hendak dikirim jauh lebih mahal.
    """
    if payload.from_warehouse_id == payload.to_warehouse_id:
        raise invalid(i18n.t("err.transfer.same_warehouse", i18n.bahasa_permintaan()),
                      "to_warehouse_id")

    tanggal = payload.transfer_date or datetime.now(APP_TZ).date()
    stempel = datetime.combine(tanggal, datetime.now(APP_TZ).timetz())

    with transaction() as cur:
        asal = ambil_gudang_aktif(cur, payload.from_warehouse_id, "from_warehouse_id")
        tuju = ambil_gudang_aktif(cur, payload.to_warehouse_id, "to_warehouse_id")
        barang = ambil_barang_aktif(cur, [b.item_id for b in payload.items])
        if any(b.for_item_id for b in payload.items):
            ambil_barang_aktif(cur, [b.for_item_id for b in payload.items
                                     if b.for_item_id], "items.for_item_id")

        for b in payload.items:
            cur.execute(
                """
                SELECT quantity, available_quantity FROM inventory
                 WHERE item_id = %s AND warehouse_id = %s
                """,
                (b.item_id, payload.from_warehouse_id),
            )
            stok = cur.fetchone()
            punya = stok["available_quantity"] if stok else Decimal("0")
            if b.quantity > punya:
                raise _stok_kurang(barang[b.item_id]["sku"], asal["name"],
                                   b.quantity, punya)

        nomor = next_document_number(
            cur, table="stock_transfers", column="transfer_number",
            prefix="TRF", tanggal=tanggal, lock_namespace=LOCK_TRANSFER)

        cur.execute(
            """
            INSERT INTO stock_transfers
                (transfer_number, from_warehouse_id, to_warehouse_id,
                 transfer_date, status, notes, source, score, reason, distance_km,
                 transport_mode, planned_days)
            VALUES (%s, %s, %s, %s, 'draft', %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (nomor, payload.from_warehouse_id, payload.to_warehouse_id, stempel,
             payload.notes, payload.source, payload.score, payload.reason,
             payload.distance_km, payload.transport_mode, payload.planned_days),
        )
        transfer_id = cur.fetchone()["id"]

        total = Decimal("0")
        for b in payload.items:
            cur.execute(
                """
                INSERT INTO stock_transfer_items
                    (stock_transfer_id, item_id, quantity, for_item_id,
                     match_type, match_similarity)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (transfer_id, b.item_id, b.quantity, b.for_item_id,
                 b.match_type, b.match_similarity),
            )
            total += b.quantity

    return {
        "transfer_id": transfer_id,
        "transfer_number": nomor,
        "status": transfer.DRAFT,
        "status_label": transfer.label_status(transfer.DRAFT,
                                              i18n.bahasa_permintaan()),
        "from_warehouse": {"id": asal["id"], "code": asal["code"], "name": asal["name"]},
        "to_warehouse": {"id": tuju["id"], "code": tuju["code"], "name": tuju["name"]},
        "item_count": len(payload.items),
        "total_quantity": int(total),
    }


def _gerakkan_stok(cur, *, transfer_id: int, dari: str, ke: str,
                   header: dict, baris: list[dict],
                   stempel: datetime | None = None) -> None:
    """
    Akibat satu perpindahan status pada persediaan.

    TIGA TAHAP, TIGA AKIBAT YANG BERBEDA, dan pemisahannya bukan formalitas:

        disetujui   Stok asal DICADANGKAN. Fisiknya belum bergerak, tetapi
                    available_quantity turun -- dan karena mesin rekomendasi
                    membaca stok TERSEDIA, gudang itu berhenti ditawarkan
                    sebagai sumber untuk kebutuhan lain. Tanpa langkah ini,
                    satu tumpukan barang yang sama akan dijanjikan ke tiga
                    gudang sekaligus dan tidak ada satu pun galat yang terbit.
        dikirim     Cadangan dilepas dan saldo asal benar-benar berkurang;
                    ledger mencatat transfer_out.
        diterima    Saldo tujuan bertambah; ledger mencatat transfer_in.

    Barang yang dicatat masuk ke gudang tujuan adalah item_id YANG DIKIRIM,
    bukan for_item_id. Yang turun dari truk adalah barang milik gudang asal;
    menuliskannya sebagai barang lain akan membuat saldo dua nomor barang
    sama-sama salah.

    `stempel` boleh diisi pemanggil, dan satu-satunya yang mengisinya adalah
    pembangkit data demo: dokumen yang menyatakan dirinya dikirim enam hari lalu
    harus meninggalkan jejak ledger bertanggal enam hari lalu juga. Pada jalur
    HTTP ia selalu kosong, dan perpindahan status selalu tercatat pada waktu ia
    benar-benar terjadi.
    """
    stempel = stempel or datetime.now(APP_TZ)

    if dari == transfer.DRAFT and ke == transfer.APPROVED:
        for b in baris:
            cur.execute(
                """
                UPDATE inventory
                   SET reserved_quantity  = reserved_quantity + %s,
                       available_quantity = quantity - (reserved_quantity + %s),
                       updated_at         = now()
                 WHERE item_id = %s AND warehouse_id = %s
                RETURNING available_quantity
                """,
                (b["quantity"], b["quantity"], b["item_id"],
                 header["from_warehouse_id"]),
            )
            sisa = cur.fetchone()
            if sisa is None or sisa["available_quantity"] < 0:
                raise _stok_kurang(b["sku"], header["from_warehouse_name"],
                                   b["quantity"],
                                   (sisa["available_quantity"] + b["quantity"])
                                   if sisa else Decimal("0"))

    elif dari == transfer.APPROVED and ke == transfer.CANCELLED:
        for b in baris:
            cur.execute(
                """
                UPDATE inventory
                   SET reserved_quantity  = GREATEST(0, reserved_quantity - %s),
                       available_quantity = quantity - GREATEST(0, reserved_quantity - %s),
                       updated_at         = now()
                 WHERE item_id = %s AND warehouse_id = %s
                """,
                (b["quantity"], b["quantity"], b["item_id"],
                 header["from_warehouse_id"]),
            )

    elif dari == transfer.APPROVED and ke == transfer.IN_TRANSIT:
        for b in baris:
            cur.execute(
                """
                UPDATE inventory
                   SET quantity           = quantity - %s,
                       reserved_quantity  = GREATEST(0, reserved_quantity - %s),
                       available_quantity = (quantity - %s)
                                            - GREATEST(0, reserved_quantity - %s),
                       updated_at         = now()
                 WHERE item_id = %s AND warehouse_id = %s
                RETURNING quantity
                """,
                (b["quantity"], b["quantity"], b["quantity"], b["quantity"],
                 b["item_id"], header["from_warehouse_id"]),
            )
            sisa = cur.fetchone()
            if sisa is None or sisa["quantity"] < 0:
                raise _stok_kurang(b["sku"], header["from_warehouse_name"],
                                   b["quantity"], Decimal("0"))
            cur.execute(
                """
                INSERT INTO stock_movements
                    (item_id, warehouse_id, movement_type, reference_id,
                     movement_date, quantity)
                VALUES (%s, %s, 'transfer_out', %s, %s, %s)
                """,
                (b["item_id"], header["from_warehouse_id"], transfer_id,
                 stempel, -b["quantity"]),
            )

    elif dari == transfer.IN_TRANSIT and ke == transfer.COMPLETED:
        for b in baris:
            # Yang masuk ke gudang tujuan adalah yang DITERIMA, bukan yang
            # dikirim. Selisihnya rusak atau hilang di jalan: ia sudah keluar
            # dari gudang asal (transfer_out sebesar kiriman) dan tidak pernah
            # menjadi stok siapa pun -- persis kerugian yang harus tampak di
            # buku besar, bukan disembunyikan dengan menganggap semuanya sampai.
            diterima = b.get("received", b["quantity"])
            # Barang yang belum pernah ada di gudang tujuan tetap dapat
            # diterima: barisnya dibuat di sini, bukan ditolak. Menolaknya
            # berarti transfer hanya bisa menuju gudang yang sudah menyimpan
            # barang itu -- padahal justru gudang yang belum punyalah yang
            # paling sering kekurangan.
            cur.execute(
                """
                INSERT INTO inventory
                    (item_id, warehouse_id, quantity, reserved_quantity,
                     available_quantity)
                VALUES (%s, %s, %s, 0, %s)
                -- Sasaran konflik memuat company_id karena keunikan inventory
                -- dihitung PER PERUSAHAAN sejak migrasi 027. Menyebut hanya
                -- (item_id, warehouse_id) membuat perintah ini ditolak
                -- PostgreSQL -- dan penolakannya baru terbit pada penerimaan
                -- transfer pertama yang menuju gudang yang belum menyimpan
                -- barang itu, yaitu jalur yang paling jarang dilewati.
                -- company_id-nya sendiri tidak disebutkan pada daftar kolom:
                -- ia terisi dari setelan sesi lewat DEFAULT, sama seperti pada
                -- seluruh tabel data lain.
                ON CONFLICT (company_id, item_id, warehouse_id) DO UPDATE
                   SET quantity           = inventory.quantity + EXCLUDED.quantity,
                       available_quantity = (inventory.quantity + EXCLUDED.quantity)
                                            - inventory.reserved_quantity,
                       updated_at         = now()
                """,
                (b["item_id"], header["to_warehouse_id"], diterima, diterima),
            )
            cur.execute(
                """
                INSERT INTO stock_movements
                    (item_id, warehouse_id, movement_type, reference_id,
                     movement_date, quantity)
                VALUES (%s, %s, 'transfer_in', %s, %s, %s)
                """,
                (b["item_id"], header["to_warehouse_id"], transfer_id,
                 stempel, diterima),
            )


def terapkan_status(cur, *, transfer_id: int, dari: str, ke: str,
                    header: dict, baris: list[dict],
                    stempel: datetime | None = None) -> None:
    """
    Seluruh akibat satu perpindahan status: stok bergerak, cap waktunya ditulis.

    Berdiri sebagai fungsi tersendiri karena ada pemanggil kedua di luar HTTP --
    pembangkit data demo, yang perlu menerbitkan dokumen transfer pada beberapa
    tahap sekaligus tanpa melewati endpoint. Menyalin dua perintah di bawah ke
    sana berarti satu tahap yang kelak ditambahkan di sini akan bergerak benar
    lewat layar dan salah lewat tombol Isi Ulang, tanpa satu pun galat.

    YANG TIDAK ADA DI SINI: pemeriksaan perpindahan yang sah dan penguncian
    barisnya. Keduanya milik pemanggil, dan endpoint di bawah mengerjakannya
    sebelum memanggil fungsi ini.
    """
    stempel = stempel or datetime.now(APP_TZ)
    _gerakkan_stok(cur, transfer_id=transfer_id, dari=dari, ke=ke,
                   header=header, baris=baris, stempel=stempel)

    # Cap waktu tiap tahap. Ditulis dari nama statusnya, bukan lewat rangkaian
    # if: kolom yang terlewat di sini berarti dokumen yang tidak dapat dijawab
    # "kapan ini dikirim" tanpa membaca ledger.
    kolom = {transfer.APPROVED: "approved_at", transfer.IN_TRANSIT: "shipped_at",
             transfer.COMPLETED: "received_at", transfer.CANCELLED: "cancelled_at"}[ke]
    cur.execute(
        f"UPDATE stock_transfers SET status = %s, {kolom} = %s, "
        f"updated_at = now() WHERE id = %s",
        (ke, stempel, transfer_id),
    )


@router.patch("/api/transfers/{transfer_id}/status",
              dependencies=[Depends(wajib_penulis)])
def ubah_status_transfer(transfer_id: int, payload: StatusTransferIn) -> dict:
    """
    Menyetujui, mengirim, menerima, atau membatalkan satu transfer.

    PERPINDAHANNYA DIJAGA app/transfer.PERPINDAHAN, bukan oleh urutan tombol di
    layar. Dokumen yang melompat dari "diajukan" langsung ke "diterima" akan
    menambah stok di gudang tujuan tanpa pernah menguranginya di gudang asal,
    dan selisih itu tidak akan pernah muncul sebagai galat -- hanya sebagai
    stok yang tidak pernah cocok saat opname.

    Barisnya dikunci FOR UPDATE sebelum statusnya dibaca. Dua permintaan
    "kirim" yang datang bersamaan akan sama-sama membaca "approved" tanpa
    kunci itu, dan stok asal berkurang dua kali untuk satu dokumen.
    """
    lang = i18n.bahasa_permintaan()

    with transaction() as cur:
        cur.execute(
            """
            SELECT t.id, t.transfer_number, t.status, t.from_warehouse_id,
                   t.to_warehouse_id, wf.name AS from_warehouse_name
              FROM stock_transfers t
              JOIN warehouses wf ON wf.id = t.from_warehouse_id
             WHERE t.id = %s
             FOR UPDATE OF t
            """,
            (transfer_id,),
        )
        header = cur.fetchone()
        if header is None:
            raise not_found("transfer", transfer_id)

        dari, ke = header["status"], payload.status
        if not transfer.boleh_pindah(dari, ke):
            raise AppError(
                422, "INVALID_TRANSITION",
                i18n.t("err.transfer.bad_status", lang,
                       dari=transfer.label_status(dari, lang),
                       ke=transfer.label_status(ke, lang)),
                "status",
            )

        cur.execute(
            """
            SELECT ti.item_id, ti.quantity, it.sku
              FROM stock_transfer_items ti
              JOIN items it ON it.id = ti.item_id
             WHERE ti.stock_transfer_id = %s
             ORDER BY ti.item_id
            """,
            (transfer_id,),
        )
        baris = [dict(r) for r in cur.fetchall()]

        diterima_total = None
        if ke == transfer.COMPLETED:
            jumlah_kirim = {b["item_id"]: b["quantity"] for b in baris}
            lapor = {r.item_id: r.received_quantity for r in (payload.received or [])}
            asing = [i for i in lapor if i not in jumlah_kirim]
            if asing:
                raise invalid(f"barang tidak ada pada dokumen ini: {asing}", "received")
            for iid, qty in lapor.items():
                if qty > jumlah_kirim[iid]:
                    raise invalid(
                        f"jumlah diterima ({qty}) melebihi jumlah dikirim "
                        f"({jumlah_kirim[iid]}) untuk barang {iid}", "received")
            for b in baris:
                b["received"] = lapor.get(b["item_id"], b["quantity"])
            diterima_total = sum(b["received"] for b in baris)

        terapkan_status(cur, transfer_id=transfer_id, dari=dari, ke=ke,
                        header=header, baris=baris)

        if ke == transfer.COMPLETED:
            for b in baris:
                cur.execute(
                    "UPDATE stock_transfer_items SET received_quantity = %s "
                    "WHERE stock_transfer_id = %s AND item_id = %s",
                    (b["received"], transfer_id, b["item_id"]))
            if payload.shipping_cost is not None:
                cur.execute("UPDATE stock_transfers SET shipping_cost = %s WHERE id = %s",
                            (payload.shipping_cost, transfer_id))

    hasil = {
        "transfer_id": transfer_id,
        "transfer_number": header["transfer_number"],
        "status": ke,
        "status_label": transfer.label_status(ke, lang),
        "previous_status": dari,
    }
    if diterima_total is not None:
        hasil["received_total"] = int(diterima_total)
        hasil["shipped_total"] = int(sum(b["quantity"] for b in baris))
    return hasil


class BiayaIn(BaseModel):
    shipping_cost: Decimal | None = Field(
        ..., ge=0, description="Biaya angkut sesungguhnya (rupiah); null = hapus")


@router.patch("/api/transfers/{transfer_id}/biaya",
              dependencies=[Depends(wajib_penulis)])
def catat_biaya_transfer(transfer_id: int, payload: BiayaIn) -> dict:
    """
    Mencatat biaya angkut sesungguhnya.

    LANGKAH TERPISAH dari menerima barang: tagihan ekspedisi biasanya baru
    tiba beberapa hari sesudah barang sampai, dan yang mengisinya orang
    keuangan, bukan petugas gudang. Boleh diisi begitu dokumennya dikirim, dan
    boleh diperbaiki kemudian. Dokumen yang belum berangkat belum punya biaya.
    """
    with transaction() as cur:
        cur.execute("SELECT status, transfer_number FROM stock_transfers WHERE id = %s "
                    "FOR UPDATE", (transfer_id,))
        h = cur.fetchone()
        if h is None:
            raise not_found("transfer", transfer_id)
        if h["status"] not in (transfer.IN_TRANSIT, transfer.COMPLETED):
            raise AppError(422, "INVALID_STATE",
                           "Biaya angkut baru dapat dicatat setelah dokumen dikirim.",
                           "shipping_cost")
        cur.execute("UPDATE stock_transfers SET shipping_cost = %s, updated_at = now() "
                    "WHERE id = %s", (payload.shipping_cost, transfer_id))
    return {"transfer_id": transfer_id, "transfer_number": h["transfer_number"],
            "shipping_cost": payload.shipping_cost}


@router.get("/api/transfers")
def daftar_dokumen(
    status: str | None = Query(None),
    warehouse_id: int | None = Query(None, gt=0,
                                     description="Gudang TUJUAN (peminta)"),
    q: str | None = Query(None, description="Cari nomor transfer"),
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
    lang: str = Query(i18n.BAHASA_BAWAAN),
) -> dict:
    """Dokumen transfer yang sudah diajukan, terbaru lebih dulu."""
    status = _diminta(status, None)
    warehouse_id = _diminta(warehouse_id, None)
    q = _diminta(q, None)
    page, page_size, offset = clamp_page(page, page_size)
    lang = i18n.normalisasi(_diminta(lang, i18n.BAHASA_BAWAAN))

    where, params = "WHERE 1=1", []
    if status:
        where += " AND t.status = %s"
        params.append(status)
    if warehouse_id:
        # Sama dengan /api/transfer: saringan "Gudang tujuan" berarti gudang
        # yang MEMINTA barang. Memakai asal ATAU tujuan membuat dokumen yang
        # gudang itu kirim ikut tampil di bawah label "tujuan".
        where += " AND t.to_warehouse_id = %s"
        params.append(warehouse_id)
    if q:
        where += " AND t.transfer_number ILIKE %s"
        params.append(f"%{q}%")

    with readonly() as cur:
        cur.execute(f"SELECT count(*) AS n FROM stock_transfers t {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(
            f"""
            SELECT t.id, t.transfer_number, t.transfer_date, t.status, t.notes,
                   t.source, t.score, t.reason, t.distance_km,
                   t.transport_mode, t.shipping_cost, t.planned_days,
                   t.approved_at, t.shipped_at, t.received_at, t.cancelled_at,
                   wf.id AS from_warehouse_id, wf.code AS from_warehouse_code,
                   wf.name AS from_warehouse_name,
                   wt.id AS to_warehouse_id, wt.code AS to_warehouse_code,
                   wt.name AS to_warehouse_name,
                   -- Koordinat kedua gudang, supaya peta pada layar Dokumen
                   -- dapat menggambar rutenya dari jawaban INI saja alih-alih
                   -- menjahitnya dengan /api/warehouses. Keduanya boleh NULL,
                   -- dan yang NULL memang tidak digambar: layar tidak pernah
                   -- mengarang letak gudang yang letaknya belum diisi.
                   -- Tidak satu pun angka transfer bergantung padanya.
                   wf.latitude  AS from_latitude,  wf.longitude AS from_longitude,
                   wt.latitude  AS to_latitude,    wt.longitude AS to_longitude,
                   COALESCE(d.line_count, 0) AS line_count,
                   COALESCE(d.total_quantity, 0) AS total_quantity
              FROM stock_transfers t
              JOIN warehouses wf ON wf.id = t.from_warehouse_id
              JOIN warehouses wt ON wt.id = t.to_warehouse_id
              LEFT JOIN (
                  SELECT stock_transfer_id, count(*) AS line_count,
                         SUM(quantity) AS total_quantity
                    FROM stock_transfer_items GROUP BY stock_transfer_id
              ) d ON d.stock_transfer_id = t.id
             {where}
             ORDER BY t.transfer_date DESC, t.id DESC
             LIMIT %s OFFSET %s
            """,
            params + [page_size, offset],
        )
        baris = []
        for r in cur.fetchall():
            row = dict(r)
            row["status_label"] = transfer.label_status(row["status"], lang)
            # Bilangan bulat, di sini dan di setiap layar yang membacanya.
            row["total_quantity"] = int(row["total_quantity"] or 0)
            row["next_statuses"] = list(transfer.PERPINDAHAN.get(row["status"], ()))
            # numeric -> float, bukan Decimal: Decimal berangkat sebagai string
            # JSON, dan peta yang menerima "112.752100" alih-alih 112.7521
            # meletakkan gudangnya di tengah Samudra Atlantik tanpa satu pun
            # galat yang terbit.
            for k in ("from_latitude", "from_longitude",
                      "to_latitude", "to_longitude"):
                row[k] = None if row[k] is None else float(row[k])
            baris.append(row)

    return page_envelope(baris, total, page, page_size)


@router.get("/api/transfers/{transfer_id}")
def satu_dokumen(transfer_id: int,
                 lang: str = Query(i18n.BAHASA_BAWAAN)) -> dict:
    lang = i18n.normalisasi(_diminta(lang, i18n.BAHASA_BAWAAN))
    with readonly() as cur:
        cur.execute(
            """
            SELECT t.*, wf.code AS from_warehouse_code, wf.name AS from_warehouse_name,
                   wt.code AS to_warehouse_code, wt.name AS to_warehouse_name
              FROM stock_transfers t
              JOIN warehouses wf ON wf.id = t.from_warehouse_id
              JOIN warehouses wt ON wt.id = t.to_warehouse_id
             WHERE t.id = %s
            """,
            (transfer_id,),
        )
        header = cur.fetchone()
        if header is None:
            raise not_found("transfer", transfer_id)

        cur.execute(
            """
            SELECT ti.id, ti.item_id, it.sku, it.name AS item_name,
                   u.code AS unit_code, ti.quantity,
                   ti.for_item_id, fi.sku AS for_sku, fi.name AS for_item_name,
                   ti.match_type, ti.match_similarity, ti.received_quantity
              FROM stock_transfer_items ti
              JOIN items it       ON it.id = ti.item_id
              JOIN units u        ON u.id  = it.unit_id
              LEFT JOIN items fi  ON fi.id = ti.for_item_id
             WHERE ti.stock_transfer_id = %s ORDER BY ti.id
            """,
            (transfer_id,),
        )
        lines = [{**dict(r), "quantity": int(r["quantity"]),
                  "received_quantity": (int(r["received_quantity"])
                                        if r["received_quantity"] is not None else None)}
                 for r in cur.fetchall()]

        cur.execute(
            """
            SELECT m.id, m.movement_type, m.movement_date, m.quantity,
                   m.warehouse_id, it.sku
              FROM stock_movements m JOIN items it ON it.id = m.item_id
             WHERE m.reference_id = %s
               AND m.movement_type IN ('transfer_in', 'transfer_out')
             ORDER BY m.id
            """,
            (transfer_id,),
        )
        movements = cur.fetchall()

    head = dict(header)
    head["status_label"] = transfer.label_status(head["status"], lang)
    head["next_statuses"] = list(transfer.PERPINDAHAN.get(head["status"], ()))
    return {
        "transfer": head,
        "lines": lines,
        "movements": movements,
        "summary": {"line_count": len(lines),
                    "total_quantity": sum(l["quantity"] for l in lines)},
    }
