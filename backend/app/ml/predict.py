# -*- coding: utf-8 -*-
"""
Penyajian model XGBoost global untuk prakiraan permintaan.

Model dimuat SEKALI ke memori proses, tidak dibaca ulang setiap permintaan.
Berkasnya ratusan MB, jadi pemuatan dilakukan di latar saat proses menyala
(lihat main.py). Bila berkasnya tidak ada, pustaka xgboost belum terpasang,
atau daftar fiturnya tidak cocok, modul ini menyatakan dirinya tidak tersedia
dan pemanggilnya memakai rata-rata bergerak berbobot. Prakiraan tidak boleh
mati hanya karena model bermasalah.


BENTUK BERKAS DAN MEMORI -- sebab proses ini pernah memakai 11,7 GB
-------------------------------------------------------------------
Model yang sama dapat dibaca dari JSON teks atau dari UBJSON biner. Bacaan
JSON memuncak di 11,6 GB dan sampahnya menetap di arena glibc, sehingga proses
tampak memakai belasan giga seumur hidupnya. Bacaan UBJSON memuncak di 1,7 GB.
Isi modelnya sendiri sekitar 90 MB. Dua tempat yang mengurus ini:
_pilih_berkas_model() memilih bentuk berkasnya, _bebaskan_arena() menyerahkan
sisa penguraiannya kembali ke kernel. Keduanya menjelaskan dirinya sendiri.


PENYELARASAN HARI -- bagian paling mudah salah di berkas ini
------------------------------------------------------------
Saat pelatihan, satu baris bertanggal D berisi:

    fitur lag/rolling : permintaan sampai D-1  (jendela closed="left")
    fitur kalender    : hari D
    current_stock     : saldo akhir D-1
    target            : permintaan D+1

Perhatikan permintaan hari D sendiri TIDAK ikut menjadi fitur. Jadi model
memetakan "keadaan awal hari D" menjadi "permintaan D+1" -- dua hari di depan
data terakhir yang dilihatnya, bukan satu.

Karena itu, untuk meramal hari P, baris fitur harus disusun dengan tanggal
kalender P-1 dan riwayat yang berakhir di P-2. Menyusunnya dengan tanggal P
akan menggeser seluruh pola mingguan satu hari dan menghasilkan angka hari
berikutnya yang dilabeli hari ini.

Akibat baiknya: dengan riwayat teramati sampai hari ini T, dua hari pertama
(T+1 dan T+2) diramal dari data sungguhan; baru hari ketiga dan seterusnya
memakai ramalan sendiri sebagai riwayat.
"""

from __future__ import annotations

import ctypes
import gc
import json
import logging
import threading
from datetime import date, timedelta
from pathlib import Path

from ..config import (FORECAST_MODEL_DIR, FORECAST_MODEL_FILE,
                      FORECAST_MODEL_META, FORECAST_MODEL_PREFER_UBJ,
                      FORECAST_USE_MODEL)
from . import features as F

log = logging.getLogger("inventory.ml")

# Letak berkas model. Bawaannya di sebelah kode; FORECAST_MODEL_DIR
# memindahkannya ke direktori yang dipasang dari luar, sehingga berkas 757 MB
# itu tidak perlu ikut masuk image. Lihat catatan pada app/config.py.
MODEL_DIR = Path(FORECAST_MODEL_DIR) if FORECAST_MODEL_DIR else (
    Path(__file__).resolve().parents[2] / "models")
BERKAS_META = MODEL_DIR / FORECAST_MODEL_META


def _pilih_berkas_model() -> Path:
    """
    Memilih berkas model: salinan biner UBJSON bila ada, JSON bila tidak.

    Keduanya adalah model yang SAMA. Berkas .ubj dibuat dengan memuat
    production_tweedie.json lalu menyimpannya kembali lewat save_model(); tidak
    ada pelatihan ulang, tidak ada parameter yang berubah, dan tidak ada
    pembulatan -- angka pemisah cabang sudah float32 di kedua bentuk. Kesamaan
    hasilnya diuji, bukan diasumsikan; lihat backend/tools/konversi_ubj.py.

    Yang berbeda hanya ongkos MEMBACANYA, dan ongkos itu ternyata besar sekali.
    JSON adalah teks, jadi xgboost harus membangun pohon dokumen sementara di
    memori: satu objek kecil untuk setiap angka di setiap simpul dari 1.850
    pohon. Puncaknya 11,6 GB dan makan 26 detik. UBJSON menyimpan deretan angka
    sebagai larik biner bertipe, sehingga pembacaannya memuncak di 1,7 GB dan
    selesai dalam setengah detik.

    Modelnya sendiri hanya sekitar 90 MB begitu berada di memori. Selisih
    belasan giga itu murni sampah penguraian teks -- dan sampah itulah yang
    dulu menetap sebagai 11,7 GB RSS seumur hidup proses.
    """
    diminta = MODEL_DIR / FORECAST_MODEL_FILE
    if FORECAST_MODEL_PREFER_UBJ and diminta.suffix != ".ubj":
        ubj = diminta.with_suffix(".ubj")
        if ubj.exists():
            return ubj
    return diminta


BERKAS_MODEL = _pilih_berkas_model()


def _rss_mb() -> float:
    """Memori proses (RSS) dalam MB; 0.0 bila /proc tidak ada, mis. di macOS."""
    try:
        with open("/proc/self/status", encoding="ascii") as f:
            for baris in f:
                if baris.startswith("VmRSS:"):
                    return int(baris.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def _bebaskan_arena() -> None:
    """
    Mengembalikan memori bekas penguraian model kepada kernel.

    Ini bukan kerapian yang bersifat kosmetik, melainkan bagian yang membuat
    pemuatan model tidak meninggalkan jejak permanen. Mengurai berkas model
    membebaskan jutaan blok kecil sekaligus, dan glibc menyimpan blok bebas itu
    di arena-nya sendiri alih-alih menyerahkannya kembali ke sistem. Dengan
    transparent huge pages menyala -- bawaan mesin ini -- satu blok yang masih
    hidup sudah cukup menahan seluruh halaman 2 MB tetap terhitung, sehingga
    arena yang nyaris kosong pun tetap terbaca sebagai memori terpakai.

    Hasilnya proses tampak memakai 11,7 GB selamanya padahal isi sebenarnya
    sekitar 240 MB. malloc_trim() menyerahkan kembali bagian yang sudah bebas.
    """
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        # Bukan glibc (musl, atau bukan Linux). Tidak fatal: pemuatan tetap
        # benar, hanya memorinya tidak sempat dikembalikan.
        pass


_kunci = threading.Lock()
_model = None
_meta: dict | None = None
_kategori: dict | None = None
_kat_dtype: str | None = None    # tipe indeks kategori yang diterima model
_alasan: str | None = None       # sebab kegagalan, untuk /api/health dan log


def _periksa_fitur(model) -> str | None:
    """
    Memastikan model menerima fitur yang persis sama dengan yang disusun kode.

    Nama DAN urutannya harus sama. XGBoost memberi kolom ke pohon berdasarkan
    posisi; satu kolom tertukar tidak menimbulkan galat apa pun, hanya angka
    yang salah diam-diam. Karena itu ketidakcocokan di sini membatalkan
    pemuatan, bukan sekadar mencatat peringatan.
    """
    nama = model.get_booster().feature_names
    if nama is None:
        return "model tidak menyimpan nama fitur"
    if list(nama) != list(F.KOLOM_FITUR):
        hilang = [k for k in F.KOLOM_FITUR if k not in nama]
        asing = [k for k in nama if k not in F.KOLOM_FITUR]
        if hilang or asing:
            return (f"daftar fitur berbeda; tidak ada di model: {hilang or '-'}; "
                    f"tidak dikenal kode: {asing or '-'}")
        beda = next(i for i, (a, b) in enumerate(zip(nama, F.KOLOM_FITUR)) if a != b)
        return (f"urutan fitur berbeda pada posisi {beda}: "
                f"model '{nama[beda]}' vs kode '{F.KOLOM_FITUR[beda]}'")
    if len(nama) != 27:
        return f"jumlah fitur {len(nama)}, seharusnya 27"
    return None


def _baris_contoh() -> dict:
    """Satu baris fitur yang sah, untuk membuktikan model benar-benar bisa meramal."""
    return F.baris_fitur(
        riwayat=[1.0] * (F.MIN_HISTORY + 1), tanggal_target=date(2026, 1, 1),
        current_stock=10.0, lead_time_days=1, reorder_point=1, safety_stock=1,
        unit_price=1, item_id=int(_kategori["item_id"][0]),
        warehouse_id=int(_kategori["warehouse_id"][0]),
        category_id=int(_kategori["category_id"][0]))


def _tentukan_dtype_kategori(model) -> tuple[str | None, str | None]:
    """
    Mencari tipe indeks kategori yang diterima model, lalu MEMBUKTIKANNYA.

    XGBoost mencocokkan tipe indeks kategori antara data latih dan data
    penyajian. Daftar kategori dibaca dari JSON sebagai int Python, sedangkan
    model bisa saja dilatih dengan int32 demi menghemat memori. Menebak tipenya
    akan gagal diam-diam pada saat permintaan, jauh dari tempat sebabnya.

    Karena itu tipenya ditentukan lewat satu prediksi percobaan di sini, bukan
    diasumsikan. Sekalian ini membuktikan model memang dapat meramal, bukan
    sekadar terbaca dari berkas.

    Mengembalikan (dtype, sebab_gagal). Sebab aslinya WAJIB ikut keluar: versi
    sebelumnya menelan galat apa pun dan selalu melaporkan "tipe indeks
    kategori tidak cocok", sehingga pandas yang belum terpasang -- yang sama
    sekali bukan soal tipe indeks -- terbaca sebagai model rusak dan menyita
    waktu untuk dilacak.
    """
    sebab: list[str] = []
    for dt in ("int32", "int64"):
        try:
            model.predict(_bingkai(_baris_contoh(), dt))
            return dt, None
        except Exception as e:  # noqa: BLE001 -- tipe berikutnya yang dicoba
            sebab.append(f"{dt}: {type(e).__name__}: {e}")
    return None, "; ".join(sebab)


def _muat() -> None:
    if _model is not None or _alasan is not None:
        return
    with _kunci:
        if _model is not None or _alasan is not None:
            return
        sebelum = _rss_mb()
        try:
            _muat_terkunci()
        finally:
            # Di `finally`, bukan di jalur sukses saja: pemuatan yang GAGAL di
            # tengah -- fitur tidak cocok, uji ramal ditolak -- meninggalkan
            # sampah penguraian yang sama besarnya. Lihat _bebaskan_arena().
            _bebaskan_arena()
            log.info("Memori proses %.0f MB setelah pemuatan model "
                     "(sebelumnya %.0f MB)", _rss_mb(), sebelum)


def _muat_terkunci() -> None:
    """
    Isi sebenarnya dari _muat(), dipanggil dengan _kunci sudah dipegang.

    Dipisah semata-mata supaya _muat() dapat membungkusnya dengan `finally`
    yang selalu membebaskan arena, tanpa harus menyisipkan pembebasan di
    belasan titik `return` di bawah ini.
    """
    global _model, _meta, _kategori, _kat_dtype, _alasan

    if not FORECAST_USE_MODEL:
        _alasan = "dimatikan lewat FORECAST_USE_MODEL"
        log.info("Model prakiraan dimatikan lewat konfigurasi")
        return
    if not BERKAS_MODEL.exists():
        _alasan = f"berkas model tidak ditemukan: {BERKAS_MODEL.name}"
        log.warning("Model prakiraan tidak ditemukan di %s", BERKAS_MODEL)
        return
    if not BERKAS_META.exists():
        _alasan = f"berkas metadata tidak ditemukan: {BERKAS_META.name}"
        log.warning("Metadata model tidak ditemukan di %s", BERKAS_META)
        return

    try:
        # Diperiksa lebih dulu dan terpisah. Keduanya baru dipakai jauh di
        # dalam alur (_bingkai mengimpor pandas saat dipanggil), sehingga
        # tanpa pemeriksaan ini pustaka yang belum terpasang muncul sebagai
        # kegagalan meramal, bukan sebagai kegagalan pemasangan.
        for pustaka in ("xgboost", "pandas"):
            try:
                __import__(pustaka)
            except ImportError:
                _alasan = f"pustaka {pustaka} belum terpasang"
                log.error("Model prakiraan ditolak, %s", _alasan)
                return

        from xgboost import XGBRegressor

        m = XGBRegressor(enable_categorical=True)
        m.load_model(BERKAS_MODEL)

        galat = _periksa_fitur(m)
        if galat:
            _alasan = f"fitur tidak cocok: {galat}"
            log.error("Model prakiraan ditolak, %s", _alasan)
            return

        meta = json.loads(BERKAS_META.read_text(encoding="utf-8"))
        if meta.get("target") and meta["target"] != F.TARGET:
            _alasan = (f"target berbeda: model '{meta['target']}' "
                       f"vs kode '{F.TARGET}'")
            log.error("Model prakiraan ditolak, %s", _alasan)
            return

        _meta = meta
        _kategori = meta.get("categories", {})
        if not _kategori:
            _alasan = "metadata tidak memuat daftar kategori"
            log.error("Model prakiraan ditolak, %s", _alasan)
            _meta = _kategori = None
            return

        _kat_dtype, sebab = _tentukan_dtype_kategori(m)
        if _kat_dtype is None:
            _alasan = f"model gagal meramal baris percobaan -- {sebab}"
            log.error("Model prakiraan ditolak, %s", _alasan)
            _meta = _kategori = None
            return

        _model = m
        log.info(
            "Model prakiraan dimuat: %s (%s, %d pohon, dilatih %s), "
            "27 fitur cocok, kategori %s, uji ramal lolos",
            BERKAS_MODEL.name, meta.get("objective", "?"),
            int(meta.get("best_iteration", 0)) + 1, meta.get("trained_at", "?"),
            _kat_dtype)
    except Exception as e:  # noqa: BLE001 -- model rusak tidak boleh menjatuhkan API
        _alasan = f"{type(e).__name__}: {e}"
        log.warning("Model prakiraan gagal dimuat: %s", _alasan)


def muat_awal() -> None:
    """Dipanggil saat proses menyala supaya permintaan pertama tidak menunggu."""
    _muat()


def tersedia() -> bool:
    _muat()
    return _model is not None


def metode() -> str:
    """Nama metode untuk dilaporkan API. Mengikuti objective model sebenarnya."""
    _muat()
    if _model is None:
        return "weighted_moving_average"
    obj = (_meta or {}).get("objective", "")
    return "xgboost_tweedie" if "tweedie" in obj else "xgboost"


def info() -> dict:
    _muat()
    if _model is None:
        return {"available": False, "reason": _alasan or "belum dimuat",
                "fallback": "weighted_moving_average"}
    return {
        "available": True,
        "method": metode(),
        "model_file": BERKAS_MODEL.name,
        "objective": _meta.get("objective"),
        "trained_at": _meta.get("trained_at"),
        "best_iteration": _meta.get("best_iteration"),
        "n_features": len(F.KOLOM_FITUR),
        "category_index_dtype": _kat_dtype,
        "n_items_known": len((_kategori or {}).get("item_id", [])),
        "min_history": min_history(),
        # Satu-satunya jendela memori yang ditinggalkan di lingkungan nyata:
        # dibaca saat diminta lewat /api/health, bukan dicatat tiap permintaan.
        # Angka sehat berkisar 250-400 MB; kalau ia merangkak naik terus,
        # ada yang menumpuk dan pantas ditelusuri.
        "process_rss_mb": round(_rss_mb()),
        "test_metrics": _meta.get("metrics_retrained"),
        "split": _meta.get("split"),
        "fallback": "weighted_moving_average",
    }


def min_history() -> int:
    """
    Panjang riwayat minimum agar seluruh fitur terisi.

    Satu hari lebih panjang daripada jendela terpanjang: baris fitur hari
    pertama berakhir di T-1, jadi butuh 28 hari SEBELUM hari terakhir.
    """
    _muat()
    dasar = int(_meta.get("min_history", F.MIN_HISTORY)) if _meta else F.MIN_HISTORY
    return dasar + 1


def _bingkai(baris: dict, dtype: str | None = None):
    import pandas as pd

    dt = dtype or _kat_dtype or "int64"
    X = pd.DataFrame([baris], columns=F.KOLOM_FITUR)
    for k in F.KOLOM_KATEGORI:
        # Barang atau gudang yang tidak ikut dalam data latih dibiarkan menjadi
        # NaN; XGBoost mengarahkannya ke cabang bawaan, bukan menolak permintaan.
        kat = (_kategori or {}).get(k)
        if kat:
            # Tipe indeks kategori harus sama persis dengan saat pelatihan;
            # lihat _tentukan_dtype_kategori().
            X[k] = pd.Categorical(X[k].astype(dt),
                                  categories=pd.Index(kat, dtype=dt))
        else:
            X[k] = X[k].astype("category")
    for k in F.KOLOM_NUMERIK:
        X[k] = pd.to_numeric(X[k], errors="coerce").astype("float32")
    return X


def ramal_deret(
    *,
    riwayat: list[float],
    as_of: date,
    hari: int,
    current_stock: float,
    neto_hari_terakhir: float,
    lead_time_days: float | None,
    reorder_point: float | None,
    safety_stock: float | None,
    unit_price: float | None,
    item_id: int,
    warehouse_id: int,
    category_id: int,
) -> list[float] | None:
    """
    Meramal permintaan harian untuk `hari` hari sesudah `as_of`.

    `riwayat` adalah pengeluaran harian berurutan yang BERAKHIR pada `as_of`
    (termasuk hari itu), tanpa lubang tanggal -- hari tanpa transaksi harus
    hadir sebagai nol.

    `current_stock` adalah saldo pada akhir `as_of`, dan `neto_hari_terakhir`
    pergerakan neto pada `as_of` itu sendiri; keduanya dipakai memundurkan
    saldo ke akhir T-1 sebagaimana bentuk fitur saat pelatihan.

    Mengembalikan None bila model tidak tersedia atau riwayatnya terlalu
    pendek, sehingga pemanggil berpindah ke rata-rata bergerak berbobot.
    """
    _muat()
    if _model is None:
        return None
    if hari < 1:
        return []

    penuh = [float(x or 0) for x in riwayat]
    n = len(penuh)
    if n < min_history():
        return None

    saldo_kini = float(current_stock or 0)
    saldo_sebelum = max(0.0, saldo_kini - float(neto_hari_terakhir or 0))

    keluar: list[float] = []
    for i in range(1, hari + 1):
        # Baris fitur bertanggal satu hari SEBELUM hari yang diramal; riwayat
        # yang dipakainya berakhir satu hari sebelum itu lagi. Lihat catatan
        # penyelarasan di kepala berkas.
        tanggal_baris = as_of + timedelta(days=i - 1)
        potong = penuh[: n - 1 + (i - 1)]

        if i == 1:
            stok = saldo_sebelum          # saldo akhir T-1
        elif i == 2:
            stok = saldo_kini             # saldo akhir T
        else:
            stok = max(0.0, saldo_kini - sum(keluar[: i - 2]))

        baris = F.baris_fitur(
            riwayat=potong, tanggal_target=tanggal_baris, current_stock=stok,
            lead_time_days=lead_time_days, reorder_point=reorder_point,
            safety_stock=safety_stock, unit_price=unit_price,
            item_id=item_id, warehouse_id=warehouse_id, category_id=category_id)

        nilai = max(0.0, float(_model.predict(_bingkai(baris))[0]))
        keluar.append(nilai)
        # Ramalan disambung ke riwayat supaya langkah berikutnya menghitung lag
        # dan rolling dengan cara yang sama seperti saat pelatihan.
        penuh.append(nilai)

    return keluar
