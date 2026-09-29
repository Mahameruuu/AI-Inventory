# -*- coding: utf-8 -*-
"""
Rekayasa fitur untuk prakiraan permintaan.

Berkas ini adalah SATU-SATUNYA tempat definisi fitur hidup. Pelatihan memakai
jalur pandas yang tervektorisasi, penyajian memakai jalur Python biasa untuk
satu baris, dan keduanya membaca daftar kolom serta rumus yang sama dari sini.

Kalau keduanya sampai berbeda, model akan menerima susunan angka yang berbeda
dari yang dipelajarinya dan hasilnya salah tanpa satu pun galat muncul. Karena
itu ada `bandingkan_jalur()` yang menguji kedua jalur menghasilkan angka
identik; uji itu dijalankan setiap kali model dilatih.
"""

from __future__ import annotations

from datetime import date

LAGS = [1, 2, 3, 7, 14, 28]
ROLL_MEAN = [7, 14, 28]
ROLL_STD = [7, 28]

# Panjang riwayat minimum agar seluruh fitur terisi. Jendela terpanjang 28 hari,
# ditambah satu hari karena fitur dihitung dari data SEBELUM hari yang diramal.
MIN_HISTORY = max(max(LAGS), max(ROLL_MEAN), max(ROLL_STD))

KOLOM_NUMERIK = (
    [f"lag_{n}" for n in LAGS]
    + [f"roll_mean_{n}" for n in ROLL_MEAN]
    + [f"roll_std_{n}" for n in ROLL_STD]
    + [
        "roll_max_28",      # lonjakan terbesar sebulan terakhir
        "zero_ratio_28",    # seberapa sering tidak ada permintaan sama sekali
        "day_of_week",
        "day_of_month",
        "month",
        "quarter",
        "is_weekend",
        "current_stock",
        "stock_cover_days",  # stok dibagi laju pemakaian; lebih stabil lintas SKU
        "lead_time_days",
        "reorder_point",
        "safety_stock",
        "unit_price",
    ]
)

KOLOM_KATEGORI = ["item_id", "warehouse_id", "category_id"]

KOLOM_FITUR = KOLOM_NUMERIK + KOLOM_KATEGORI
TARGET = "demand_next_day"


# --------------------------------------------------------------------------
# Jalur penyajian: satu baris, dari riwayat permintaan sebuah deret
# --------------------------------------------------------------------------
def baris_fitur(
    *,
    riwayat: list[float],
    tanggal_target: date,
    current_stock: float,
    lead_time_days: float | None,
    reorder_point: float | None,
    safety_stock: float | None,
    unit_price: float | None,
    item_id: int,
    warehouse_id: int,
    category_id: int,
) -> dict:
    """
    Menyusun satu baris fitur.

    `riwayat` adalah permintaan harian berurutan yang BERAKHIR pada hari
    sebelum `tanggal_target`. Elemen terakhir adalah lag_1.
    """
    n = len(riwayat)
    fitur: dict = {}

    for lag in LAGS:
        fitur[f"lag_{lag}"] = float(riwayat[-lag]) if n >= lag else 0.0

    for jendela in ROLL_MEAN:
        potong = riwayat[-jendela:] if n >= 1 else []
        fitur[f"roll_mean_{jendela}"] = (sum(potong) / len(potong)) if potong else 0.0

    for jendela in ROLL_STD:
        potong = riwayat[-jendela:] if n >= 2 else []
        if len(potong) >= 2:
            rata = sum(potong) / len(potong)
            var = sum((x - rata) ** 2 for x in potong) / len(potong)
            fitur[f"roll_std_{jendela}"] = var ** 0.5
        else:
            fitur[f"roll_std_{jendela}"] = 0.0

    potong28 = riwayat[-28:]
    fitur["roll_max_28"] = float(max(potong28)) if potong28 else 0.0
    fitur["zero_ratio_28"] = (
        sum(1 for x in potong28 if x <= 0) / len(potong28) if potong28 else 1.0
    )

    fitur["day_of_week"] = float(tanggal_target.weekday())
    fitur["day_of_month"] = float(tanggal_target.day)
    fitur["month"] = float(tanggal_target.month)
    fitur["quarter"] = float((tanggal_target.month - 1) // 3 + 1)
    fitur["is_weekend"] = 1.0 if tanggal_target.weekday() >= 5 else 0.0

    stok = float(current_stock or 0)
    laju = fitur["roll_mean_28"]
    fitur["current_stock"] = stok
    # Dibatasi supaya barang yang nyaris tidak pernah keluar tidak menghasilkan
    # angka raksasa yang menutupi fitur lain.
    fitur["stock_cover_days"] = min(stok / laju, 999.0) if laju > 0 else 999.0

    fitur["lead_time_days"] = float(lead_time_days or 0)
    fitur["reorder_point"] = float(reorder_point or 0)
    fitur["safety_stock"] = float(safety_stock or 0)
    fitur["unit_price"] = float(unit_price or 0)

    fitur["item_id"] = int(item_id)
    fitur["warehouse_id"] = int(warehouse_id)
    fitur["category_id"] = int(category_id)
    return fitur


# --------------------------------------------------------------------------
# Jalur pelatihan: tervektorisasi atas seluruh deret sekaligus
# --------------------------------------------------------------------------
def bangun_frame(df):
    """
    Menambahkan seluruh kolom fitur dan target ke DataFrame permintaan harian.

    `df` wajib berisi kolom: item_id, warehouse_id, category_id, date,
    demand_quantity, net_quantity, lead_time_days, reorder_point, safety_stock,
    unit_price -- dan sudah terurut per deret menurut tanggal.
    """
    import numpy as np

    g = df.groupby(["item_id", "warehouse_id"], sort=False, observed=True)
    d = df["demand_quantity"]

    for lag in LAGS:
        df[f"lag_{lag}"] = g["demand_quantity"].shift(lag)

    # closed="left" membuat jendela berhenti SEBELUM hari berjalan, sehingga
    # permintaan hari ini tidak pernah bocor ke fiturnya sendiri.
    for jendela in ROLL_MEAN:
        df[f"roll_mean_{jendela}"] = g["demand_quantity"].transform(
            lambda s, w=jendela: s.rolling(w, min_periods=1, closed="left").mean())
    for jendela in ROLL_STD:
        df[f"roll_std_{jendela}"] = g["demand_quantity"].transform(
            lambda s, w=jendela: s.rolling(w, min_periods=2, closed="left").std(ddof=0))

    df["roll_max_28"] = g["demand_quantity"].transform(
        lambda s: s.rolling(28, min_periods=1, closed="left").max())
    df["zero_ratio_28"] = g["demand_quantity"].transform(
        lambda s: (s <= 0).rolling(28, min_periods=1, closed="left").mean())

    tgl = df["date"]
    df["day_of_week"] = tgl.dt.dayofweek.astype("float32")
    df["day_of_month"] = tgl.dt.day.astype("float32")
    df["month"] = tgl.dt.month.astype("float32")
    df["quarter"] = tgl.dt.quarter.astype("float32")
    df["is_weekend"] = (tgl.dt.dayofweek >= 5).astype("float32")

    # Stok berjalan direkonstruksi dari pergerakan neto: saldo akhir hari
    # sebelumnya, bukan hari berjalan, supaya tidak membocorkan masa depan.
    df["current_stock"] = (g["net_quantity"].cumsum() - df["net_quantity"]).astype("float32")
    laju = df["roll_mean_28"].fillna(0.0)
    df["stock_cover_days"] = np.where(
        laju > 0, np.minimum(df["current_stock"] / laju.replace(0, np.nan), 999.0), 999.0)

    df[TARGET] = g["demand_quantity"].shift(-1)

    for k in [f"lag_{n}" for n in LAGS] + [f"roll_std_{n}" for n in ROLL_STD]:
        df[k] = df[k].fillna(0.0)
    for k in [f"roll_mean_{n}" for n in ROLL_MEAN] + ["roll_max_28"]:
        df[k] = df[k].fillna(0.0)
    df["zero_ratio_28"] = df["zero_ratio_28"].fillna(1.0)
    df["stock_cover_days"] = df["stock_cover_days"].fillna(999.0)
    for k in ("lead_time_days", "reorder_point", "safety_stock", "unit_price"):
        df[k] = df[k].fillna(0.0)
    return df


def bandingkan_jalur(df, contoh: int = 200) -> list[str]:
    """
    Membuktikan jalur pandas dan jalur satu-baris menghasilkan angka yang sama.

    Dijalankan saat pelatihan. Ketidakcocokan berarti model akan menerima fitur
    yang berbeda saat melayani permintaan, dan itu gagal tanpa suara.
    """
    import numpy as np

    beda: list[str] = []
    kandidat = df[df["lag_28"] > 0].sample(
        min(contoh, len(df[df["lag_28"] > 0])), random_state=7)

    for _, baris in kandidat.iterrows():
        deret = df[(df["item_id"] == baris["item_id"])
                   & (df["warehouse_id"] == baris["warehouse_id"])
                   & (df["date"] < baris["date"])]
        riwayat = deret["demand_quantity"].tolist()
        if len(riwayat) < MIN_HISTORY:
            continue
        acuan = baris_fitur(
            riwayat=riwayat,
            tanggal_target=baris["date"].date(),
            current_stock=baris["current_stock"],
            lead_time_days=baris["lead_time_days"],
            reorder_point=baris["reorder_point"],
            safety_stock=baris["safety_stock"],
            unit_price=baris["unit_price"],
            item_id=baris["item_id"], warehouse_id=baris["warehouse_id"],
            category_id=baris["category_id"])
        for k in KOLOM_NUMERIK:
            a, b = float(acuan[k]), float(baris[k])
            if not np.isclose(a, b, rtol=1e-6, atol=1e-6):
                beda.append(f"{k}: satu-baris={a:.6f} pandas={b:.6f}")
    return beda
