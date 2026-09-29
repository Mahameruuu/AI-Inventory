# -*- coding: utf-8 -*-
"""
Mesin prakiraan kebutuhan stok.

Metode: Weighted Moving Average atas pengeluaran harian.

Dipilih karena tiga alasan. Pertama, hasilnya dapat ditelusuri -- setiap angka
bisa dijelaskan ke pengguna tanpa menyebut "model bilang begitu". Kedua, ia
tidak butuh data pelatihan, sehingga langsung berguna sejak minggu pertama
sistem dipakai. Ketiga, bobot yang menurun ke belakang membuat perubahan pola
pemakaian terbaru lebih cepat terbaca dibanding rata-rata biasa.

Model pembelajaran mesin sengaja BELUM dipakai: dengan histori sependek ini,
model berat hanya akan menghasilkan angka yang terlihat meyakinkan tanpa dasar.

Perhitungannya dipisah dari basis data sebagai fungsi murni `hitung()` supaya
seluruh jalur status dapat diuji tanpa menyentuh data sungguhan.

LLM TIDAK PERNAH dilibatkan di sini. Angka dihitung Python; model bahasa hanya
menerjemahkan hasilnya menjadi kalimat pada endpoint terpisah.
"""

from datetime import date, timedelta
from decimal import Decimal
from statistics import pstdev

from . import i18n
from .config import (FORECAST_ATTENTION_BAND, FORECAST_MIN_HISTORY_DAYS,
                     FORECAST_MIN_OUTFLOW_DAYS)

# --- Ambang minimum histori -------------------------------------------------
# Bawaannya 14 hari rentang dan 3 hari dengan pengeluaran; alasannya ada pada
# config.py. Dibuat dapat disetel lewat lingkungan agar dapat diuji, bukan agar
# diturunkan sembarangan di lingkungan nyata.
MIN_HISTORY_DAYS = FORECAST_MIN_HISTORY_DAYS
MIN_OUTFLOW_DAYS = FORECAST_MIN_OUTFLOW_DAYS

STATUS_SAFE = "SAFE"
STATUS_ATTENTION = "ATTENTION"
STATUS_CRITICAL = "CRITICAL"
STATUS_INSUFFICIENT = "INSUFFICIENT_DATA"

# Lebar pita "mendekati titik pemesanan ulang"; alasannya ada di config.py.
ATTENTION_BAND = Decimal(str(FORECAST_ATTENTION_BAND))

# Kalimatnya sendiri tinggal di app/i18n.py; konstanta ini tetap ada karena
# dipakai kode lama, dan isinya dibaca dari kamus yang sama.
PESAN_KURANG_DATA = i18n.t("forecast.insufficient")


def _d(v) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v or 0))


def _f(v) -> float:
    """Angka untuk JSON; dibulatkan tiga desimal seperti kolom kuantitas."""
    return float(round(_d(v), 3))


def _f_laju(v) -> float:
    """
    LAJU, bukan kuantitas -- dan karena itu tidak ikut tiga desimal di atas.

    Tiga desimal benar untuk jumlah barang: kolomnya sendiri numeric(18,3), dan
    angka di belakangnya tidak ada artinya. Laju pemakaian bukan jumlah barang,
    dan pembulatan yang sama menghapusnya sama sekali: roller bearing yang
    diganti sekali tiap 2.500 hari berlaju 0,00049 unit/hari, yang pada tiga
    desimal menjadi 0,0 -- terbaca di layar sebagai barang yang tidak pernah
    dipakai, padahal ia dipakai, hanya jarang.
    """
    return float(round(_d(v), 6))


def wma(nilai: list[Decimal]) -> Decimal:
    """
    Rata-rata bergerak berbobot. Hari terbaru berbobot paling besar.

    Bobotnya linear (1, 2, 3, ... n) -- cukup untuk menangkap tren tanpa
    membuat hasilnya melompat karena satu hari yang tidak biasa.
    """
    if not nilai:
        return Decimal("0")
    total_bobot = Decimal(len(nilai) * (len(nilai) + 1) // 2)
    jumlah = sum(_d(v) * Decimal(i + 1) for i, v in enumerate(nilai))
    return jumlah / total_bobot


def _mutu_data(rentang_hari: int, hari_keluar: int, keluar: list[Decimal]) -> dict:
    """
    Seberapa layak angka ini dipercaya.

    Tiga hal yang menentukan: panjang histori, banyaknya hari yang benar-benar
    ada pengeluaran, dan seberapa stabil pemakaian hariannya. Pemakaian yang
    naik-turun tajam membuat rata-rata apa pun kurang berarti.
    """
    skor_rentang = min(1.0, rentang_hari / 30) * 0.5
    skor_kejadian = min(1.0, hari_keluar / 10) * 0.3

    positif = [float(v) for v in keluar if v > 0]
    if len(positif) >= 2:
        rata = sum(positif) / len(positif)
        cv = (pstdev(positif) / rata) if rata else 0.0
    else:
        cv = 1.0
    skor_stabil = (1 / (1 + cv)) * 0.2

    skor = round(skor_rentang + skor_kejadian + skor_stabil, 2)
    label = "tinggi" if skor >= 0.7 else "sedang" if skor >= 0.4 else "rendah"
    return {
        "score": skor,
        "label": label,
        "history_days": rentang_hari,
        "days_with_outflow": hari_keluar,
        "usage_variability": round(cv, 2),
    }


def hitung(
    *,
    as_of: date,
    current_stock,
    daily_outflow: list[tuple[date, Decimal]],
    daily_net: list[tuple[date, Decimal]],
    minimum_stock,
    reorder_point,
    forecast_days: int,
    historical_days: int,
    ramalan_harian: list[float] | None = None,
    metode: str = "weighted_moving_average",
    available_stock=None,
    lang: str = i18n.BAHASA_BAWAAN,
    maks_titik_grafik: int | None = None,
) -> dict:
    """
    Fungsi murni: dari deret pergerakan harian menjadi hasil prakiraan.

    `daily_outflow` dan `daily_net` harus memuat SETIAP hari pada jendela
    histori, termasuk hari tanpa transaksi (nilai nol). Hari kosong ikut
    menurunkan rata-rata, dan itu memang benar -- barang yang hanya keluar
    seminggu sekali tidak boleh dianggap keluar tiap hari.

    `ramalan_harian` berisi permintaan per hari hasil model pembelajaran mesin.
    Bila diisi, angka itulah yang dipakai untuk memproyeksikan stok, dan
    rata-rata bergerak berbobot hanya menjadi pembanding. Bila kosong, seluruh
    perhitungan memakai rata-rata bergerak berbobot seperti semula.

    Kedua jalur menghasilkan bentuk keluaran yang sama persis, sehingga
    endpoint dan dashboard tidak perlu tahu metode mana yang sedang dipakai.

    DUA BASIS STOK, sengaja dibedakan:

        current_stock    stok FISIK di gudang (inventory.quantity). Dipakai
                         grafik, deret proyeksi, expected_stock, dan hari
                         menuju habis -- semuanya menggambarkan barang yang
                         benar-benar ada di rak.

        available_stock  stok yang BENAR-BENAR BISA DIPAKAI, yaitu fisik
                         dikurangi yang sudah dikomitmenkan keluar
                         (inventory.available_quantity). Dipakai
                         projected_shortage, karena barang yang sudah
                         dijanjikan keluar tidak akan menyerap permintaan
                         baru.

    Bila `available_stock` tidak diisi, ia mengikuti `current_stock` -- maka
    seluruh pemanggil lama dan seluruh baris tanpa stok tercadang menghasilkan
    angka yang sama persis seperti sebelumnya.
    """
    stok = _d(current_stock)
    # None berarti "tidak ada informasi stok tercadang", bukan "tersedia nol".
    tersedia = _d(available_stock) if available_stock is not None else stok
    min_stok = _d(minimum_stock)
    # reorder_point boleh kosong pada master barang; minimum_stock jadi cadangan
    titik_pesan = _d(reorder_point) if reorder_point not in (None, "") else min_stok

    keluar = [_d(v) for _, v in daily_outflow]
    hari_keluar = sum(1 for v in keluar if v > 0)
    rentang = len(daily_outflow)

    # --- histori: rekonstruksi saldo mundur dari stok saat ini ---
    # Saldo akhir hari sebelumnya = saldo hari ini dikurangi pergerakan hari ini.
    #
    # `maks_titik_grafik` memotong deret yang DIKIRIM, bukan yang dihitung.
    # Rekonstruksinya tetap berjalan mundur melewati SELURUH jendela -- kalau
    # tidak, saldo pada titik tertua akan salah sebesar seluruh pergerakan yang
    # dilewati. Yang dibuang hanya ekor terjauhnya, sesudah saldonya benar.
    saldo = stok
    historis: list[dict] = []
    for tanggal, gerak in reversed(daily_net):
        historis.append({"date": tanggal.isoformat(), "stock": _f(saldo), "type": "historical"})
        saldo = saldo - _d(gerak)
    if maks_titik_grafik and len(historis) > maks_titik_grafik:
        historis = historis[:maks_titik_grafik]
    historis.reverse()

    mutu = _mutu_data(rentang, hari_keluar, keluar)

    # --- histori tidak cukup: berhenti di sini, jangan menebak ---
    if rentang < MIN_HISTORY_DAYS or hari_keluar < MIN_OUTFLOW_DAYS:
        return {
            "status": STATUS_INSUFFICIENT,
            "message": i18n.t("forecast.insufficient", lang),
            "current_stock": _f(stok),
            "available_stock": _f(tersedia),
            "average_daily_outflow": None,
            "historical_period": {
                "days": rentang,
                "start": daily_net[0][0].isoformat() if daily_net else None,
                "end": as_of.isoformat(),
                "requested_days": historical_days,
            },
            "forecast_days": forecast_days,
            "predicted_usage": None,
            "predicted_remaining_stock": None,
            # Tanpa perkiraan pemakaian, besar kekurangan tidak punya jawaban.
            # None, bukan 0 -- nol berarti "tidak kurang", dan itu klaim yang
            # belum boleh dibuat di sini.
            "projected_shortage": None,
            "days_until_reorder_point": None,
            "reorder_crossing_date": None,
            "days_until_stockout": None,
            "reorder_point": _f(titik_pesan),
            "minimum_stock": _f(min_stok),
            "data_quality": mutu,
            "requirements": {
                "min_history_days": MIN_HISTORY_DAYS,
                "min_days_with_outflow": MIN_OUTFLOW_DAYS,
                "actual_history_days": rentang,
                "actual_days_with_outflow": hari_keluar,
            },
            "historical_data": historis,
            "forecast_data": [],
        }

    # --- prakiraan ---
    rata_wma = wma(keluar)
    if ramalan_harian:
        # Model meramal tiap hari secara terpisah, jadi pemakaian kumulatif
        # tidak lagi lurus. Rata-rata hariannya diturunkan dari ramalan itu
        # sendiri supaya angka yang ditampilkan konsisten dengan grafiknya.
        harian = [_d(x) for x in ramalan_harian[:forecast_days]]
        while len(harian) < forecast_days:
            harian.append(harian[-1] if harian else rata_wma)
        rata = sum(harian) / Decimal(len(harian))
    else:
        harian = [rata_wma] * forecast_days
        rata = rata_wma

    pemakaian = sum(harian)
    sisa = stok - pemakaian

    # Besar kekurangan diambil SEBELUM sisa dipangkas ke nol. `sisa` sengaja
    # tetap dipangkas karena kartu dan grafik sudah membacanya sebagai stok
    # tersisa, dan stok tersisa tidak pernah negatif. Tetapi pemangkasan itu
    # membuang besaran defisitnya: butuh 1.000 dengan stok 400 dan butuh 500
    # dengan stok 400 sama-sama menghasilkan sisa nol. Selisihnya disimpan
    # terpisah supaya pertanyaan "kurang berapa" punya angka, bukan cuma
    # "stok akan habis".
    # Basisnya stok TERSEDIA, bukan stok fisik: barang yang sudah dikomitmenkan
    # keluar tidak akan menyerap permintaan baru, jadi menghitungnya sebagai
    # penutup kebutuhan akan meremehkan kekurangan. Tanpa stok tercadang,
    # `tersedia` sama dengan `stok` dan hasilnya identik dengan sebelumnya.
    kekurangan = pemakaian - tersedia
    if kekurangan < 0:
        kekurangan = Decimal("0")

    if sisa < 0:
        sisa = Decimal("0")

    prakiraan: list[dict] = []
    lewat_titik_pesan = None
    habis = None
    berjalan = stok
    for i in range(1, forecast_days + 1):
        berjalan = berjalan - harian[i - 1]
        proyeksi = berjalan if berjalan > 0 else Decimal("0")
        prakiraan.append({
            "date": (as_of + timedelta(days=i)).isoformat(),
            "stock": _f(proyeksi),
            "type": "forecast",
        })
        if lewat_titik_pesan is None and proyeksi <= titik_pesan:
            lewat_titik_pesan = i
        if habis is None and proyeksi <= 0:
            habis = i

    # Status ditentukan angka, bukan kalimat AI.
    #
    # CRITICAL  perkiraan sisa sudah menyentuh atau menembus titik pesan, atau
    #           stok habis sebelum periode berakhir, atau stok sekarang sudah
    #           di bawah stok minimum.
    # ATTENTION sisa masih di atas titik pesan, tetapi hanya tipis -- satu
    #           periode lagi akan menembusnya.
    # SAFE      selain itu.
    #
    # "Mendekati" diukur dua cara, diambil yang lebih longgar:
    #   - persentase di atas titik pesan, berguna saat pemakaian sangat kecil;
    #   - setengah periode pemakaian lagi, yang jauh lebih bermakna bagi
    #     petugas gudang: sisa segini akan menembus titik pesan sebelum periode
    #     berikutnya selesai.
    # Persentase saja tidak cukup -- pada titik pesan 5 unit, pita 25% hanya
    # selebar 1,25 unit dan praktis tidak pernah memberi peringatan dini.
    ambang_persen = titik_pesan * ATTENTION_BAND
    ambang_pemakaian = titik_pesan + rata * Decimal(forecast_days) / Decimal(2)
    ambang_perhatian = max(ambang_persen, ambang_pemakaian)

    if stok <= min_stok or habis is not None or sisa <= titik_pesan:
        status = STATUS_CRITICAL
    elif sisa <= ambang_perhatian:
        status = STATUS_ATTENTION
    else:
        status = STATUS_SAFE

    return {
        "status": status,
        "method": metode,
        # Rata-rata bergerak berbobot selalu ikut dilaporkan sebagai pembanding,
        # walau yang dipakai memproyeksikan stok adalah metode di atas.
        "baseline_daily_outflow": _f(rata_wma),
        "message": None,
        "current_stock": _f(stok),
        "available_stock": _f(tersedia),
        "average_daily_outflow": _f_laju(rata),
        "historical_period": {
            "days": rentang,
            "start": daily_net[0][0].isoformat() if daily_net else None,
            "end": as_of.isoformat(),
            "requested_days": historical_days,
        },
        "forecast_days": forecast_days,
        "predicted_usage": _f(pemakaian),
        "predicted_remaining_stock": _f(sisa),
        # Perkiraan pemakaian dikurangi stok TERSEDIA; nol bila mencukupi.
        # Perhatikan: expected_stock berbasis stok FISIK, jadi identitas
        # "expected - shortage" hanya berlaku saat tidak ada stok tercadang.
        "projected_shortage": _f(kekurangan),
        "days_until_reorder_point": lewat_titik_pesan,
        # Tanggal saat garis proyeksi memotong titik pesan. Diambil dari deret
        # prakiraan yang sama dengan yang digambar grafik, supaya penanda pada
        # grafik mustahil meleset dari angkanya.
        "reorder_crossing_date": (
            prakiraan[lewat_titik_pesan - 1]["date"] if lewat_titik_pesan else None
        ),
        "days_until_stockout": habis,
        "reorder_point": _f(titik_pesan),
        "minimum_stock": _f(min_stok),
        "data_quality": mutu,
        "requirements": {
            "min_history_days": MIN_HISTORY_DAYS,
            "min_days_with_outflow": MIN_OUTFLOW_DAYS,
            "actual_history_days": rentang,
            "actual_days_with_outflow": hari_keluar,
        },
        "historical_data": historis,
        "forecast_data": prakiraan,
    }
