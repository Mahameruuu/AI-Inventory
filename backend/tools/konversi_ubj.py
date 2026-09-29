# -*- coding: utf-8 -*-
"""
Membuat salinan UBJSON dari berkas model JSON, lalu MEMBUKTIKAN keduanya sama.

    python -m tools.konversi_ubj                 # konversi + verifikasi
    python -m tools.konversi_ubj --hanya-uji     # verifikasi saja

Dijalankan dari direktori backend/, sekali setiap kali berkas model produksi
diganti. Hasilnya, models/production_tweedie.ubj, adalah berkas yang benar-benar
dibaca aplikasi saat menyala.


MENGAPA BERKAS INI ADA
----------------------
Berkas model JSON berukuran 925 MB. Membacanya memaksa xgboost membangun pohon
dokumen sementara -- satu objek kecil untuk tiap angka di tiap simpul dari 1.850
pohon -- yang memuncak di 11,6 GB. Sampah itu dibebaskan, tetapi glibc menahannya
di arena-nya sendiri, sehingga proses backend menetap di 11,7 GB RSS selamanya
padahal modelnya sendiri hanya sekitar 90 MB.

UBJSON adalah bentuk biner resmi xgboost untuk model yang sama. Deretan angka
disimpan sebagai larik bertipe, bukan sebagai daftar objek, sehingga pembacaannya
memuncak di 1,7 GB dan selesai dalam setengah detik alih-alih 26 detik.

Konversi ini TIDAK menyentuh model: tidak ada pelatihan ulang, tidak ada
parameter yang berubah, tidak ada pembulatan. Nilai pemisah cabang sudah float32
di kedua bentuk. Karena itu verifikasi di bawah menuntut kesamaan BIT DEMI BIT,
bukan sekadar "cukup dekat" -- selisih sekecil apa pun berarti ada yang salah
dipahami tentang konversi ini, dan lebih baik ketahuan di sini.
"""

from __future__ import annotations

import argparse
import ctypes
import gc
import json
import sys
import time
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1] / "models"
BAKU_JSON = MODEL_DIR / "production_tweedie.json"
BAKU_META = MODEL_DIR / "production_tweedie_meta.json"

# Jumlah baris uji. 20.000 sudah menyentuh ribuan jalur pohon yang berbeda;
# menambahnya hanya memperlama tanpa menambah keyakinan.
N_UJI = 20_000


def _trim() -> None:
    """Kembalikan sisa penguraian ke kernel supaya langkah berikutnya lega."""
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError):
        pass


def _rss_gb() -> float:
    try:
        with open("/proc/self/status", encoding="ascii") as f:
            for baris in f:
                if baris.startswith("VmHWM:"):
                    return int(baris.split()[1]) / 1048576
    except OSError:
        pass
    return 0.0


def _contoh_fitur(meta: dict):
    """
    Menyusun baris uji acak yang bentuknya persis seperti yang dilihat model.

    Kolom kategori WAJIB memakai tipe indeks yang sama dengan saat pelatihan;
    xgboost menolak permintaan bila berbeda, dan itu memang yang diinginkan --
    lihat _tentukan_dtype_kategori() di app/ml/predict.py.
    """
    import numpy as np
    import pandas as pd

    kat = meta["categories"]
    rng = np.random.default_rng(7)
    X = pd.DataFrame({k: rng.gamma(1.5, 6.0, N_UJI).astype("float32")
                      for k in meta["numeric_features"]})
    for k, lo, hi in (("day_of_week", 0, 7), ("day_of_month", 1, 32),
                      ("month", 1, 13), ("quarter", 1, 5), ("is_weekend", 0, 2)):
        X[k] = rng.integers(lo, hi, N_UJI).astype("float32")
    X["zero_ratio_28"] = rng.random(N_UJI).astype("float32")
    X["current_stock"] = rng.gamma(2, 200, N_UJI).astype("float32")
    X["stock_cover_days"] = rng.uniform(0, 999, N_UJI).astype("float32")

    for k in meta["categorical_features"]:
        X[k] = rng.choice(kat[k], N_UJI)
    return X, kat


def _siapkan_kategori(X, kat, meta, dt: str):
    import pandas as pd

    Y = X.copy()
    for k in meta["categorical_features"]:
        Y[k] = pd.Categorical(Y[k].astype(dt),
                              categories=pd.Index(kat[k], dtype=dt))
    return Y[meta["features"]]


def _ramal(path: Path, X):
    """Muat model, ramal, lalu lepaskan seluruh memorinya sebelum kembali."""
    from xgboost import XGBRegressor

    t0 = time.time()
    m = XGBRegressor(enable_categorical=True)
    m.load_model(path)
    detik = time.time() - t0
    nama = list(m.get_booster().feature_names)
    p = m.predict(X)
    del m
    _trim()
    return p, nama, detik


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=BAKU_JSON)
    ap.add_argument("--meta", type=Path, default=BAKU_META)
    ap.add_argument("--hanya-uji", action="store_true",
                    help="jangan menulis ulang .ubj, hanya bandingkan yang ada")
    a = ap.parse_args()

    import numpy as np
    from xgboost import XGBRegressor

    ubj = a.json.with_suffix(".ubj")
    meta = json.loads(a.meta.read_text(encoding="utf-8"))

    if not a.hanya_uji:
        print(f"membaca {a.json.name} ({a.json.stat().st_size/1048576:.0f} MB) ...")
        t0 = time.time()
        m = XGBRegressor(enable_categorical=True)
        m.load_model(a.json)
        print(f"  selesai dalam {time.time()-t0:.1f} detik, "
              f"puncak memori {_rss_gb():.1f} GB")
        m.save_model(ubj)
        del m
        _trim()
        print(f"ditulis {ubj.name} ({ubj.stat().st_size/1048576:.0f} MB)")

    if not ubj.exists():
        print(f"GAGAL: {ubj} tidak ada", file=sys.stderr)
        return 1

    print(f"menguji {N_UJI} baris pada kedua bentuk berkas ...")
    Xm, kat = _contoh_fitur(meta)

    # Tipe indeks kategori ditentukan lewat percobaan, bukan ditebak -- alasan
    # yang sama seperti di app/ml/predict.py.
    for dt in ("int32", "int64"):
        try:
            X = _siapkan_kategori(Xm, kat, meta, dt)
            pj, nj, tj = _ramal(a.json, X)
            break
        except Exception:  # noqa: BLE001 -- tipe berikutnya yang dicoba
            continue
    else:
        print("GAGAL: model menolak kedua tipe indeks kategori", file=sys.stderr)
        return 1

    pu, nu, tu = _ramal(ubj, X)

    sama_fitur = nj == nu
    sama_ramal = np.array_equal(pj, pu)
    print(f"  waktu muat        : json {tj:.1f}s  ubj {tu:.1f}s")
    print(f"  nama fitur sama   : {sama_fitur}")
    print(f"  ramalan identik   : {sama_ramal} "
          f"(selisih maks {np.max(np.abs(pj.astype('float64') - pu.astype('float64'))):.3e})")

    if not (sama_fitur and sama_ramal):
        print("GAGAL: .ubj TIDAK setara dengan .json -- jangan dipakai",
              file=sys.stderr)
        return 1
    print("LULUS: .ubj setara bit demi bit dengan .json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
