# -*- coding: utf-8 -*-
"""
Titik pesan ulang (ROP) dengan alur berantai model -> strategi.

ALURNYA BERANTAI, dan itu inti berkas ini. Model prakiraan yang dipilih tidak
hanya menghasilkan angka permintaan; galatnya sendiri langsung menjadi bahan
menghitung safety stock. Dua keputusan yang selama ini terpisah -- "model mana"
dan "seberapa aman" -- disambung menjadi satu rantai:

    model dipilih
      -> permintaan harian rata-rata (D)
      -> galat historis model itu (RMSE)
         + strategi layanan (Z)
           -> safety stock = Z x RMSE x akar(lead time)
              -> ROP = D x lead time + safety stock

Akibatnya safety stock menjadi DINAMIS: model yang meramal barang ini dengan
tepat menghasilkan cadangan tipis, model yang sering meleset menghasilkan
cadangan tebal. Itu jauh lebih jujur daripada safety stock tetap pada master
barang, yang tidak tahu apa-apa tentang seberapa sulit barang itu diramal.

KENAPA RMSE, BUKAN MASE. Safety stock dinyatakan dalam unit barang, dan MASE
adalah rasio tanpa satuan -- ia menjawab "model mana lebih baik", bukan
"berapa unit ia meleset". Keduanya dihitung app/ml/klasik.py dari backtest yang
sama; yang dipakai di sini yang bersatuan.

RANTAI INI BUKAN SATU-SATUNYA JALAN. Model "statistik" memotongnya: permintaan
dibaca sebagai rata-rata riwayat dan sebarannya sebagai simpangan baku
permintaan harian, tanpa backtest sama sekali --

    riwayat pengeluaran
      -> rata-rata harian (D)
      -> simpangan baku harian (sigma)
         + strategi layanan (Z)
           -> safety stock = Z x sigma x akar(lead time)
              -> ROP = D x lead time + safety stock

Rumus ROP-nya SAMA PERSIS; yang berbeda hanya dari mana D dan sebarannya
datang. Jalur itu tinggal di app/statistik.py, dan `safety_stock_basis` pada
jawaban di bawah menyebut mana yang benar-benar dipakai -- angka cadangan yang
dilaporkan tanpa menyebut dasarnya tidak dapat diperiksa siapa pun.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from . import statistik
from .ml import klasik


@dataclass(frozen=True)
class Strategi:
    kunci: str
    z: float
    service_level: float


# Tiga strategi, dan namanya sengaja menyebut KONSEKUENSINYA, bukan angkanya.
# Orang gudang memilih antara "aman" dan "hemat"; Z-score 2,05 tidak berarti
# apa-apa baginya sampai diterjemahkan menjadi "98 dari 100 kali permintaan
# tertutup".
STRATEGI: dict[str, Strategi] = {
    "aman":    Strategi("aman", 2.05, 0.98),
    "standar": Strategi("standar", 1.28, 0.90),
    "hemat":   Strategi("hemat", 0.84, 0.80),
}

STRATEGI_BAWAAN = "standar"


def strategi_sah(kunci) -> Strategi:
    """
    Strategi yang tidak dikenal jatuh ke Standar, bukan menolak permintaan.

    `str()` lebih dulu, dengan alasan yang sama seperti i18n.normalisasi:
    fungsi router di aplikasi ini kerap dipanggil LANGSUNG sebagai fungsi
    Python -- oleh app/tools.py untuk asisten, dan oleh beberapa tes -- dan
    pada pemanggilan seperti itu nilai bawaan Query milik FastAPI ikut masuk
    apa adanya, bukan sebagai string. Menuntut string murni di sini berarti
    seluruh pemanggil itu harus mengingat satu parameter tampilan yang tidak
    ada hubungannya dengan pertanyaan yang sedang mereka ajukan.
    """
    return STRATEGI.get(str(kunci or "").strip().lower(),
                        STRATEGI[STRATEGI_BAWAAN])


def hitung_rop(
    *,
    riwayat: list[float],
    lead_time_days: float,
    model: str,
    strategi: str,
    as_of: date,
    horizon: int = 7,
    tambahan: dict | None = None,
) -> dict:
    """
    Menjalankan rantai model -> galat -> safety stock -> ROP.

    `riwayat` adalah pengeluaran harian berurutan yang berakhir pada `as_of`.
    `tambahan` menyisipkan model di luar app/ml/klasik.py -- model pembelajaran
    mesin -- dengan tanda tangan yang sama.

    Mengembalikan objek ringkas: model yang dipakai, permintaan harian yang
    diramalnya, galat historis model itu, strategi yang dipilih, safety stock,
    dan ROP akhir.
    """
    s = strategi_sah(strategi)
    lead = max(0.0, float(lead_time_days or 0))

    # --- Langkah 1: model meramal permintaan harian, dan galatnya diukur ---
    kandidat = dict(tambahan or {})
    if model == klasik.KUNCI_TERBAIK:
        menang, _ = klasik.pilih_terbaik(riwayat, horizon, as_of, kandidat)
        dipakai = menang or klasik.KUNCI_BAWAAN
    else:
        dipakai = model

    if dipakai in kandidat:
        deret = kandidat[dipakai](riwayat, horizon, as_of)
    else:
        deret = klasik.ramal(dipakai, riwayat, horizon, as_of)
    if not deret:
        dipakai = klasik.KUNCI_BAWAAN
        deret = klasik.ramal(dipakai, riwayat, horizon, as_of) or [0.0]

    # Permintaan harian rata-rata sepanjang horizon ramalan. Dirata-ratakan,
    # bukan diambil hari pertama: naif musiman meramal berbeda tiap hari, dan
    # hari pertama yang kebetulan Minggu akan membuat ROP-nya runtuh.
    d_harian = sum(deret) / len(deret)

    # DUA SUMBER SEBARAN, DAN YANG DIPAKAI DISEBUT NAMANYA.
    #
    # Model statistik tidak diadu: sebarannya dibaca langsung dari simpangan
    # baku permintaan harian. Itu bukan jalan pintas melainkan besaran yang
    # lebih tepat untuk pertanyaannya -- RMSE mengukur seberapa jauh MODEL
    # meleset, sedangkan yang harus ditanggung cadangan adalah seberapa jauh
    # PERMINTAAN menyimpang. Ia juga hidup di bawah 28 hari, ambang tempat
    # backtest menyerah dan cadangan terpaksa berbunyi nol.
    #
    # Model lain tetap memakai galat backtest MODEL ITU SENDIRI, bukan galat
    # rata-rata seluruh model. Itulah yang membuat rantainya berarti: mengganti
    # model mengubah safety stock-nya juga.
    if dipakai == klasik.KUNCI_STATISTIK:
        dasar = "demand_stdev"
        sebaran = statistik.simpangan_harian(riwayat)
    else:
        dasar = "model_rmse"
        sebaran = None
        for baris in klasik.evaluasi(riwayat, horizon, as_of, kandidat):
            if baris["model"] == dipakai:
                sebaran = baris["rmse"]
                break

    # --- Langkah 2 & 3: Z dari strategi, lalu safety stock ---
    # SS = Z x sebaran x akar(lead time), dan rumus itu TIDAK ditulis di sini.
    # Ia hidup di app/statistik.py, satu-satunya tempat, karena lapisan
    # keputusan di app/routers/forecasting.py memanggil fungsi yang sama --
    # dua salinan rumus cadangan akan membuat halaman Reorder dan endpoint ini
    # berselisih angka tanpa ada apa pun yang menjelaskan selisihnya. Alasan
    # konvensi akarnya ada pada docstring fungsi itu.
    safety = statistik.safety_stock(simpangan=sebaran, z=s.z,
                                    lead_time_days=lead) or 0.0

    # --- Langkah 4: ROP ---
    rop = d_harian * lead + safety

    return {
        "selected_forecast_model": dipakai,
        "predicted_daily_demand": round(d_harian, 3),
        # Namanya tetap model_rmse demi pemakai yang sudah membacanya, tetapi
        # isinya bergantung pada dasar di bawah: galat backtest model, atau
        # simpangan baku permintaan harian. Keduanya bersatuan unit per hari,
        # jadi rumus cadangannya tidak berubah -- yang berubah artinya, dan
        # itu wajib terbaca, bukan ditebak dari nama model.
        "model_rmse": round(sebaran, 3) if sebaran is not None else None,
        "safety_stock_basis": dasar,
        "selected_strategy": s.kunci,
        "calculated_safety_stock": round(safety, 3),
        "final_reorder_point": round(rop, 3),
    }
