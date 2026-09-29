# -*- coding: utf-8 -*-
"""
Titik pesan ulang dari statistik biasa: rata-rata dan simpangan baku.

KENAPA BERKAS INI ADA. Rumus titik pesan tidak pernah menuntut model prakiraan:

    ROP = permintaan harian x masa tunggu + Z x simpangan x akar(masa tunggu)

Yang dituntutnya hanya dua angka -- seberapa cepat barang terpakai, dan
seberapa tidak menentu pemakaian itu. Keduanya dapat dibaca langsung dari
riwayat pengeluaran dengan aritmetika yang muat dalam satu layar, tanpa
mengadu enam model lebih dulu.

BEDANYA DENGAN app/rop.py. Berkas itu menurunkan kedua angka dari model
prakiraan: permintaan dari ramalannya, safety stock dari galat backtest model
itu. Rantai tersebut TIDAK dibuang -- ia tetap dapat dipilih, dan pada barang
yang polanya kuat ia memang lebih tajam. Yang berubah adalah ia tidak lagi
menjadi satu-satunya jalan, karena tiga harganya nyata:

  1. Backtest menuntut riwayat panjang. app/ml/klasik.py menolak mengadu di
     bawah 28 hari (MIN_RIWAYAT_ADU), dan di bawah ambang itu safety stock
     jatuh ke nol atau ke angka master. Simpangan baku hanya menuntut dua hari.
  2. Hasilnya sulit dijelaskan. "Cadangan setebal ini karena RMSE backtest
     Croston SBA pada empat lipatan" bukan kalimat yang dapat diperiksa orang
     gudang. "Pemakaian harian naik-turun sekitar 5 unit dari rata-ratanya"
     bisa.
  3. Galat model bukan sebaran permintaan. RMSE mengukur seberapa jauh MODEL
     meleset; yang perlu ditanggung safety stock adalah seberapa jauh
     PERMINTAAN menyimpang. Pada barang yang polanya teratur, model yang tepat
     bergalat nyaris nol -- dan cadangannya ikut menghilang, padahal permintaan
     hari besok tetap tidak pasti.

SIMPANGAN BAKU SAMPEL, BUKAN POPULASI. Riwayat yang ada adalah contoh dari
pemakaian yang mungkin terjadi, bukan seluruhnya; pembagi n-1 mengakui itu.
Bedanya kecil pada 90 hari dan berarti pada 10 hari -- dan justru pada riwayat
pendek itulah meremehkan ketidakpastian paling berbahaya.

HARI NOL IKUT DIHITUNG, pada rata-rata maupun simpangan. Hari tanpa
pengeluaran adalah hari dengan permintaan nol, dan membuangnya akan menaikkan
laju seolah barang terpakai setiap hari. Jendela riwayat yang masuk ke sini
sudah dipangkas sampai pergerakan pertama oleh pemanggilnya, sehingga yang
tersisa memang hari-hari saat barang sudah ada di gudang.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import sqrt
from statistics import fmean, stdev

# Simpangan baku sampel butuh dua titik; satu hari tidak punya sebaran.
MIN_RIWAYAT_SIMPANGAN = 2


def permintaan_harian(riwayat: Sequence[float]) -> float | None:
    """
    Rata-rata pengeluaran per hari sepanjang jendela riwayat.

    None berarti tidak ada riwayat sama sekali -- pertanyaannya belum punya
    jawaban. Itu berbeda dari 0,0, yang berarti barangnya memang tidak pernah
    terpakai selama jendela itu.

    Dijepit di nol karena pengeluaran tidak pernah negatif; deret yang berisi
    minus adalah data rusak, dan laju negatif akan menghasilkan titik pesan
    negatif yang diam-diam menyatakan "tidak perlu memesan apa pun, selamanya".
    """
    nilai = [float(v) for v in riwayat]
    if not nilai:
        return None
    return max(0.0, fmean(nilai))


def simpangan_harian(riwayat: Sequence[float]) -> float | None:
    """
    Simpangan baku sampel dari pengeluaran harian: seberapa jauh pemakaian
    sehari-hari menyimpang dari rata-ratanya.

    Inilah yang menggantikan RMSE model pada perhitungan safety stock, dan
    satuannya sama -- unit barang per hari -- sehingga hasil kalinya tetap
    terbaca sebagai unit.

    None berarti riwayatnya terlalu pendek untuk punya sebaran. Pemanggilnya
    harus memperlakukan itu sebagai "belum dapat dihitung", bukan sebagai nol:
    cadangan nol berarti pernyataan bahwa permintaan pasti, dan riwayat satu
    hari tidak pernah menjadi dasar pernyataan seperti itu.
    """
    nilai = [float(v) for v in riwayat]
    if len(nilai) < MIN_RIWAYAT_SIMPANGAN:
        return None
    return stdev(nilai)


def safety_stock(*, simpangan: float | None, z: float,
                 lead_time_days: float) -> float | None:
    """
    Cadangan penyangga: Z x simpangan x akar(masa tunggu).

    KENAPA AKAR, BUKAN MASA TUNGGU LANGSUNG. Yang perlu ditanggung cadangan
    bukan simpangan SATU hari dikalikan berapa hari menunggu, melainkan
    simpangan TOTAL permintaan sepanjang masa tunggu itu. Permintaan tiap hari
    naik-turun sendiri-sendiri: hari yang di atas rata-rata sebagian ditutup
    oleh hari yang di bawahnya, dan makin panjang masa tunggunya makin besar
    peluang keduanya saling meredam. Ragam yang menumpuk itulah yang linear,
    dan simpangan adalah akar dari ragam -- sehingga simpangan total tumbuh
    menurut akar waktu.

    Bentuk linear (Z x sigma x masa tunggu) yang dipakai sebelumnya berdiri di
    atas anggapan yang berlawanan: bahwa seluruh hari dalam masa tunggu meleset
    ke arah yang sama sekaligus. Itu keadaan yang mungkin, tetapi bukan yang
    lazim, dan menagihnya sebagai bawaan berarti menahan modal untuk risiko
    yang jauh lebih jarang daripada yang diakui angkanya. Selisihnya bukan
    sedikit: pada masa tunggu 14 hari cadangannya sekitar 3,7 kali lipat, pada
    45 hari sekitar 6,7 kali lipat.

    SATU-SATUNYA TEMPAT RUMUS INI HIDUP. app/rop.py dan lapisan keputusan di
    app/routers/forecasting.py sama-sama memanggil fungsi ini, bukan menyalin
    rumusnya. Itu disengaja: dua rumus cadangan yang berbeda pada satu aplikasi
    akan membuat halaman Reorder dan endpoint /api/forecast/rop menyebut angka
    yang berlainan untuk barang yang sama, dan tidak ada apa pun di layar yang
    menjelaskan selisihnya.

    None diteruskan sebagai None: sebaran yang tidak diketahui tidak boleh
    diam-diam menjadi cadangan nol.
    """
    if simpangan is None:
        return None
    return z * simpangan * sqrt(max(0.0, float(lead_time_days or 0)))


def hitung(*, riwayat: Sequence[float], lead_time_days: float,
           z: float) -> dict:
    """
    Rantai lengkapnya, sekali jalan: rata-rata -> simpangan -> cadangan -> ROP.

    Mengembalikan angka presisi penuh beserta bahan penyusunnya, supaya
    pemanggil dapat mencetak "20/hari x 14 hari + 90" dan pembacanya dapat
    memeriksa sendiri hasilnya. Pembulatan dikerjakan lapisan penyajian, bukan
    di sini.

    Safety stock yang tidak dapat dihitung menjadi 0,0 pada ROP tetapi tetap
    dilaporkan None pada `safety_stock` -- ROP-nya masih terbit dari permintaan
    kali masa tunggu, sehingga halaman tidak kosong, sementara pembacanya tahu
    persis bahwa yang hilang adalah cadangannya.
    """
    lead = max(0.0, float(lead_time_days or 0))
    d = permintaan_harian(riwayat)
    sigma = simpangan_harian(riwayat)
    ss = safety_stock(simpangan=sigma, z=z, lead_time_days=lead)

    return {
        "permintaan_harian": d,
        "simpangan_harian": sigma,
        "lead_time_days": lead,
        "safety_stock": ss,
        "reorder_point": (d or 0.0) * lead + (ss or 0.0),
    }
