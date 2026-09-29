# -*- coding: utf-8 -*-
"""
Model prakiraan klasik, beserta pemilih model terbaik.

KENAPA KLASIK, BUKAN HANYA MODEL BESAR. Permintaan barang gudang berbentuk
intermiten: banyak hari nol, sesekali melonjak, dan deretnya pendek. Pada
bentuk seperti itu metode klasik sering mengungguli model pembelajaran mesin --
bukan karena modelnya lemah, melainkan karena tidak ada cukup sinyal untuk
dipelajari, sedangkan metode klasik membawa asumsinya sendiri yang kebetulan
cocok. Croston dirancang persis untuk deret berlubang; naif musiman menang
telak pada barang yang mengikuti irama minggu kerja.

Yang penting bukan memilih model terpandai, melainkan MENGETAHUI mana yang
cocok untuk deret ini. Karena itu berkas ini menyediakan dua hal sekaligus:
sekumpulan model, dan cara mengadu mereka di atas riwayat barang itu sendiri.

KONTRAKNYA SATU. Setiap model menerima riwayat pengeluaran harian yang
berakhir pada `as_of` dan mengembalikan ramalan `hari` hari sesudahnya. Bentuk
itu sama persis dengan yang dihasilkan app/ml/predict.py, sehingga mesin
prakiraan di app/forecasting.py tidak perlu tahu model mana yang sedang
dipakai -- ia hanya menerima deret angka.

TIDAK ADA KETERGANTUNGAN BARU. Seluruhnya aritmetika pustaka standar. Menambah
statsmodels atau sktime untuk lima rumus di bawah berarti menambah ratusan
megabyte pada image demi kode yang muat dalam satu berkas.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from .. import statistik

log = logging.getLogger("inventory.klasik")

# Riwayat minimum sebelum sebuah model boleh diadu. Di bawah ini, pemenang
# lomba hanya mencerminkan keberuntungan pada beberapa titik.
MIN_RIWAYAT_ADU = 28

# Panjang jendela uji pada tiap lipatan, dan banyaknya lipatan.
LIPATAN = 4

KUNCI_TERBAIK = "best"
KUNCI_BAWAAN = "wma"

# Rumus statistik biasa: rata-rata riwayat, datar sepanjang horizon. Terdaftar
# sebagai model penuh -- bukan cabang khusus di router -- supaya ia ikut
# dropdown, ikut papan adu, dan menempuh jalur yang persis sama dengan model
# lain. Perhitungannya sendiri tinggal di app/statistik.py, satu-satunya
# tempat rata-rata dan simpangan baku harian didefinisikan.
KUNCI_STATISTIK = "statistik"

# Kunci model pembelajaran mesin. Ditaruh di sini, bukan di router, supaya
# SELURUH daftar kunci model -- klasik maupun bukan -- terbaca dari satu
# tempat oleh API, kamus bahasa, dan dropdown di layar. Daftar yang tersebar
# di tiga berkas akan berbeda isinya cepat atau lambat, dan yang terlihat
# pengguna adalah pilihan yang ditolak backend.
KUNCI_ML = "xgboost_tweedie"


# ==========================================================================
# Model
# ==========================================================================

def _bersih(x: float) -> float:
    """Permintaan tidak pernah negatif; model yang menghasilkan minus dipotong."""
    return x if x > 0 else 0.0


def rata_rata(riwayat: Sequence[float], hari: int,
              as_of: date) -> list[float]:
    """
    Rata-rata aritmetika seluruh jendela riwayat, diramalkan datar.

    Model paling sederhana yang masih menjawab pertanyaannya, dan sengaja
    demikian: titik pesan hanya membutuhkan BERAPA BANYAK terpakai selama masa
    tunggu, bukan terpakai pada hari yang mana. Rata-rata sepanjang jendela
    menjawab itu tanpa satu pun parameter yang harus dicari lebih dulu.

    Bedanya dengan wma() di bawah: bobotnya rata, bukan menanjak ke hari
    terbaru. Itu membuatnya lebih tenang pada deret yang berlubang -- satu
    lonjakan kemarin tidak mengangkat seluruh ramalan -- dengan harga tidak
    secepat wma membaca perubahan pola yang sungguhan.
    """
    d = statistik.permintaan_harian(riwayat)
    return [_bersih(d if d is not None else 0.0)] * hari


def wma(riwayat: Sequence[float], hari: int, as_of: date) -> list[float]:
    """
    Rata-rata bergerak berbobot linear (1, 2, 3, ... n).

    Bobot linear cukup menangkap arah tanpa membuat hasilnya melompat karena
    satu hari yang tidak biasa. Rumusnya sama persis dengan cadangan lama pada
    app/forecasting.py -- ia dijadikan pilihan tersendiri di sini supaya
    perilaku yang selama ini menjadi cadangan diam-diam dapat dipilih dan
    diadu secara terbuka.
    """
    if not riwayat:
        return [0.0] * hari
    n = len(riwayat)
    bobot = n * (n + 1) / 2
    nilai = sum(v * (i + 1) for i, v in enumerate(riwayat)) / bobot
    return [_bersih(nilai)] * hari


def ses(riwayat: Sequence[float], hari: int, as_of: date) -> list[float]:
    """
    Pemulusan eksponensial sederhana; alpha dicari, bukan ditebak.

    Alpha disapu pada kisi 0,05-0,95 dan yang dipilih adalah yang paling kecil
    jumlah kuadrat galatnya pada riwayat itu sendiri. Alpha tetap -- 0,3,
    misalnya -- akan terlalu lamban untuk barang yang berubah cepat dan
    terlalu gelisah untuk barang yang tenang, dan tidak ada satu angka yang
    benar untuk delapan ribu barang sekaligus.
    """
    if not riwayat:
        return [0.0] * hari

    terbaik_alpha, terbaik_sse = 0.3, None
    for i in range(1, 20):
        alpha = i * 0.05
        level = riwayat[0]
        sse = 0.0
        for v in riwayat[1:]:
            sse += (v - level) ** 2
            level = alpha * v + (1 - alpha) * level
        if terbaik_sse is None or sse < terbaik_sse:
            terbaik_alpha, terbaik_sse = alpha, sse

    level = riwayat[0]
    for v in riwayat[1:]:
        level = terbaik_alpha * v + (1 - terbaik_alpha) * level
    return [_bersih(level)] * hari


def croston_sba(riwayat: Sequence[float], hari: int, as_of: date) -> list[float]:
    """
    Croston dengan koreksi Syntetos-Boylan (SBA).

    Dirancang khusus untuk permintaan intermiten, dan itulah bentuk sebagian
    besar barang di gudang. Alih-alih memuluskan deret yang penuh nol -- yang
    menarik seluruh ramalan mendekati nol -- ia memisahkan dua hal yang memang
    berbeda: SEBERAPA BANYAK sekali ambil, dan SEBERAPA SERING diambil.
    Keduanya dimuluskan sendiri-sendiri, lalu ramalan hariannya adalah ukuran
    dibagi jarak.

    Faktor SBA (1 - alpha/2) meredam bias naik yang sudah lama diketahui pada
    Croston asli: rasio dua besaran yang dimuluskan tidak menghasilkan rata-rata
    yang benar, dan tanpa koreksi ini stok cenderung dipesan berlebih.
    """
    kejadian = [(i, v) for i, v in enumerate(riwayat) if v > 0]
    if len(kejadian) < 2:
        # Satu kejadian atau tidak sama sekali: tidak ada jarak yang dapat
        # dimuluskan. Rata-rata sederhana lebih jujur daripada rumus yang
        # berpura-pura punya pola.
        rata = (sum(riwayat) / len(riwayat)) if riwayat else 0.0
        return [_bersih(rata)] * hari

    alpha = 0.1  # nilai yang lazim dipakai pada literatur Croston
    ukuran = kejadian[0][1]
    jarak = float(kejadian[1][0] - kejadian[0][0])
    for k in range(1, len(kejadian)):
        idx, v = kejadian[k]
        selisih = float(idx - kejadian[k - 1][0])
        ukuran = alpha * v + (1 - alpha) * ukuran
        jarak = alpha * selisih + (1 - alpha) * jarak

    if jarak <= 0:
        return [_bersih(ukuran)] * hari
    laju = (1 - alpha / 2) * (ukuran / jarak)
    return [_bersih(laju)] * hari


def musiman_mingguan(riwayat: Sequence[float], hari: int,
                     as_of: date) -> list[float]:
    """
    Naif musiman mingguan: tiap hari diramal dari hari yang sama minggu-minggu
    sebelumnya.

    Satu-satunya model di sini yang ramalannya BERBEDA tiap hari. Gudang
    mengikuti irama minggu kerja -- Sabtu setengah hari, Minggu nyaris berhenti
    -- dan model yang meratakan seluruh hari akan meramalkan pengeluaran pada
    hari yang sebenarnya tutup, lalu memperkirakan stok habis lebih cepat
    daripada kenyataan.

    Dipakai rata-rata seluruh kemunculan hari itu, bukan minggu terakhir saja:
    satu Senin yang tidak biasa tidak boleh menjadi ramalan seluruh Senin
    berikutnya.
    """
    if not riwayat:
        return [0.0] * hari

    n = len(riwayat)
    per_hari: dict[int, list[float]] = {}
    for i, v in enumerate(riwayat):
        tanggal = as_of - timedelta(days=n - 1 - i)
        per_hari.setdefault(tanggal.weekday(), []).append(v)

    rata_umum = sum(riwayat) / n
    hasil = []
    for j in range(1, hari + 1):
        dow = (as_of + timedelta(days=j)).weekday()
        contoh = per_hari.get(dow)
        # Hari yang belum pernah muncul pada riwayat memakai rata-rata umum,
        # bukan nol: ketiadaan data bukan bukti tidak ada pemakaian.
        hasil.append(_bersih(sum(contoh) / len(contoh) if contoh else rata_umum))
    return hasil


def theta(riwayat: Sequence[float], hari: int, as_of: date) -> list[float]:
    """
    Metode Theta, pemenang kompetisi M3 dan masih sulit dikalahkan.

    Gagasannya sederhana: deret dipecah menjadi dua garis theta. Theta-0 adalah
    garis regresi linear -- arah jangka panjangnya. Theta-2 melebih-lebihkan
    kelengkungan jangka pendek, dan dimuluskan dengan pemulusan eksponensial.
    Ramalannya rata-rata keduanya, sehingga arah tetap terbawa tanpa membuat
    ramalan meluncur jauh mengikuti tren yang belum tentu berlanjut.
    """
    n = len(riwayat)
    if n < 3:
        return wma(riwayat, hari, as_of)

    # Theta-0: regresi linear terhadap indeks waktu.
    x_rata = (n - 1) / 2
    y_rata = sum(riwayat) / n
    pembilang = sum((i - x_rata) * (v - y_rata) for i, v in enumerate(riwayat))
    penyebut = sum((i - x_rata) ** 2 for i in range(n))
    kemiringan = (pembilang / penyebut) if penyebut else 0.0
    potongan = y_rata - kemiringan * x_rata

    # Theta-2: 2*deret - garis, lalu dimuluskan. Titik akhirnya yang dipakai.
    garis2 = [2 * v - (potongan + kemiringan * i) for i, v in enumerate(riwayat)]
    level = ses(garis2, 1, as_of)[0] if garis2 else 0.0

    hasil = []
    for j in range(1, hari + 1):
        theta0 = potongan + kemiringan * (n - 1 + j)
        hasil.append(_bersih((theta0 + level) / 2))
    return hasil


# ==========================================================================
# Daftar model
# ==========================================================================

@dataclass(frozen=True)
class Model:
    kunci: str
    ramal: Callable[[Sequence[float], int, date], list[float]]


# Urutannya adalah urutan tampil pada dropdown. Statistik sederhana lebih dulu
# karena itulah yang cukup untuk kebanyakan barang dan yang paling mudah
# dipertanggungjawabkan angkanya; sisanya menyusul dengan yang paling cocok
# untuk permintaan intermiten di depan.
KLASIK: dict[str, Model] = {
    KUNCI_STATISTIK:    Model(KUNCI_STATISTIK, rata_rata),
    "croston_sba":      Model("croston_sba", croston_sba),
    "theta":            Model("theta", theta),
    "ses":              Model("ses", ses),
    "seasonal_naive":   Model("seasonal_naive", musiman_mingguan),
    "wma":              Model("wma", wma),
}


def semua_kunci(dengan_ml: bool = True) -> list[str]:
    """
    Seluruh pilihan model, berurutan seperti yang tampil di layar.

    "Terbaik" ditaruh paling depan karena itulah yang seharusnya dipakai
    kebanyakan orang; sisanya untuk yang ingin membandingkan sendiri.
    """
    kunci = [KUNCI_TERBAIK, *KLASIK.keys()]
    if dengan_ml:
        kunci.append(KUNCI_ML)
    return kunci


def ramal(kunci: str, riwayat: Sequence[float], hari: int,
          as_of: date) -> list[float] | None:
    """Ramalan satu model klasik, atau None bila kuncinya bukan model klasik."""
    m = KLASIK.get(kunci)
    if m is None:
        return None
    return m.ramal(riwayat, hari, as_of)


# ==========================================================================
# Adu model
# ==========================================================================

def _mase(aktual: Sequence[float], ramalan: Sequence[float],
          latih: Sequence[float]) -> float | None:
    """
    Galat absolut terskala (MASE).

    BUKAN MAPE, dan itu keputusan yang menentukan. MAPE membagi dengan nilai
    aktual, sedangkan deret di sini penuh hari bernilai nol -- pembagian yang
    tak terdefinisi tepat pada mayoritas titiknya. MASE membagi dengan galat
    metode naif pada data latih, sehingga tetap terdefinisi dan sekaligus dapat
    dibandingkan antar barang: nilai di bawah 1 berarti mengalahkan tebakan
    "besok sama seperti hari ini".
    """
    if not aktual or not ramalan:
        return None
    skala = (sum(abs(latih[i] - latih[i - 1]) for i in range(1, len(latih)))
             / (len(latih) - 1)) if len(latih) > 1 else 0.0
    galat = sum(abs(a - r) for a, r in zip(aktual, ramalan)) / len(aktual)
    if skala <= 0:
        # Deret latih yang datar sempurna (mis. seluruhnya nol) tidak punya
        # skala. Galat mentahnya tetap dilaporkan supaya model tidak semuanya
        # bernilai sama dan pemenangnya ditentukan urutan abjad.
        return galat
    return galat / skala


def _rmse(aktual: Sequence[float], ramalan: Sequence[float]) -> float | None:
    """
    Akar rata-rata galat kuadrat, dalam SATUAN BARANG -- bukan terskala.

    Dipakai menghitung safety stock, dan di sanalah satuannya penting: safety
    stock harus dinyatakan dalam unit yang sama dengan stok. MASE tidak dapat
    dipakai untuk itu karena ia rasio tanpa satuan; ia menjawab "model mana
    yang lebih baik", bukan "berapa unit meleset".

    Kuadrat, bukan nilai mutlak, juga disengaja: safety stock melindungi dari
    meleset yang BESAR, dan pengkuadratan memberi bobot lebih pada meleset
    besar itu -- persis risiko yang sedang ditanggung.
    """
    if not aktual or not ramalan:
        return None
    n = min(len(aktual), len(ramalan))
    return (sum((aktual[i] - ramalan[i]) ** 2 for i in range(n)) / n) ** 0.5


def evaluasi(riwayat: Sequence[float], hari: int, as_of: date,
             tambahan: dict[str, Callable[[Sequence[float], int, date],
                                          list[float] | None]] | None = None
             ) -> list[dict]:
    """
    Mengadu seluruh model pada riwayat barang itu sendiri.

    Caranya asal-usul bergulir (rolling origin): riwayat dipotong pada beberapa
    titik, tiap model meramal ke depan dari potongan itu, lalu ramalannya
    dibandingkan dengan yang benar-benar terjadi. Satu potongan saja tidak
    cukup -- pemenangnya akan mencerminkan satu minggu yang kebetulan, bukan
    kecocokan model dengan deretnya.

    `tambahan` memungkinkan model di luar berkas ini -- model pembelajaran
    mesin -- ikut diadu dengan aturan yang sama persis. Ia boleh mengembalikan
    None bila gagal; model yang gagal tidak menang tanpa bertanding.
    """
    n = len(riwayat)
    if n < MIN_RIWAYAT_ADU:
        return []

    h = max(1, min(hari, 14))
    lipatan = min(LIPATAN, (n - MIN_RIWAYAT_ADU) // h + 1)
    if lipatan < 1:
        return []

    kandidat: dict[str, Callable] = {k: m.ramal for k, m in KLASIK.items()}
    if tambahan:
        kandidat.update(tambahan)

    galat: dict[str, list[float]] = {k: [] for k in kandidat}
    galat_unit: dict[str, list[float]] = {k: [] for k in kandidat}
    for f in range(lipatan):
        potong = n - (lipatan - f) * h
        if potong < MIN_RIWAYAT_ADU:
            continue
        latih = list(riwayat[:potong])
        uji = list(riwayat[potong:potong + h])
        if len(uji) < h:
            continue
        as_of_latih = as_of - timedelta(days=n - potong)
        for kunci, fn in kandidat.items():
            try:
                r = fn(latih, h, as_of_latih)
            except Exception as e:  # noqa: BLE001
                log.warning("Model %s gagal saat diadu: %s", kunci, e)
                r = None
            if not r:
                continue
            nilai = _mase(uji, r, latih)
            if nilai is not None:
                galat[kunci].append(nilai)
            unit = _rmse(uji, r)
            if unit is not None:
                galat_unit[kunci].append(unit)

    hasil = [
        {"model": kunci,
         "mase": round(sum(v) / len(v), 4),
         # RMSE dirata-ratakan antar lipatan, bukan digabung menjadi satu
         # kuadrat besar: tiap lipatan mewakili satu kesempatan meramal, dan
         # keduanya sama beratnya.
         "rmse": round(sum(galat_unit[kunci]) / len(galat_unit[kunci]), 4)
                 if galat_unit[kunci] else None,
         "lipatan": len(v)}
        for kunci, v in galat.items() if v
    ]
    hasil.sort(key=lambda x: x["mase"])
    return hasil


def pilih_terbaik(riwayat: Sequence[float], hari: int, as_of: date,
                  tambahan: dict | None = None) -> tuple[str | None, list[dict]]:
    """
    Model dengan galat terskala terkecil, beserta seluruh papan skornya.

    Papan skornya ikut dikembalikan, bukan hanya pemenangnya. Pengguna yang
    melihat "Terbaik: Croston" berhak tahu ia menang atas apa dan seberapa
    jauh -- tanpa itu, kata "terbaik" hanya klaim.
    """
    papan = evaluasi(riwayat, hari, as_of, tambahan)
    if not papan:
        return None, []
    return papan[0]["model"], papan
