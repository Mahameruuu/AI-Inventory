# -*- coding: utf-8 -*-
"""
Lapisan bahasa untuk kalimat yang disusun backend.

KENAPA DI SINI, BUKAN DI FRONTEND. Setiap kalimat pada halaman Prakiraan,
Pemesanan Ulang, dan Analisis Umur Pakai menyebut ANGKA YANG SAMA dengan kartu
di sebelahnya, dan angka itu disisipkan ke dalam kalimatnya saat kalimat itu
disusun. Menerjemahkannya kembali di layar berarti membongkar kalimat jadi
untuk mengambil angkanya -- rapuh terhadap setiap perubahan template, dan satu
kesalahan pola langsung menjadi angka yang salah di layar terakhir.

Yang dilakukan berkas ini: memisahkan KATA dari ANGKA. Template disimpan per
bahasa, angkanya tetap disubstitusi di tempat yang sama seperti sebelumnya.
Tidak ada satu pun perhitungan yang pindah ke sini.

WHY HERE, NOT IN THE FRONTEND. Every sentence on the Forecasting, Reorder and
Lifetime Analysis pages quotes the same figure as the card beside it, and that figure is
interpolated as the sentence is built. Re-translating on screen would mean
taking a finished sentence apart to recover its numbers -- brittle against every
template change, and one bad pattern becomes a wrong number on the final screen.

This file separates WORDS from NUMBERS. Templates live here per language; the
numbers are still substituted exactly where they always were. No calculation
moves in here.

MENAMBAH BAHASA: tambahkan kunci ketiga pada setiap entri TEKS. Tidak ada
berkas lain yang perlu disentuh selain daftar BAHASA di bawah.
"""

from __future__ import annotations

from contextvars import ContextVar
from datetime import date

BAHASA_BAWAAN = "id"
BAHASA = ("id", "en")


def normalisasi(lang: str | None) -> str:
    """
    Kode bahasa apa pun dari klien menjadi salah satu bahasa yang didukung.

    Menerima "en-US", "EN", "en_GB" -- yang dikirim peramban bukan selalu kode
    dua huruf bersih, dan menolak varian yang jelas maksudnya hanya membuat
    halaman terbaca setengah Indonesia setengah Inggris.
    """
    if not lang:
        return BAHASA_BAWAAN
    kode = str(lang).strip().lower().replace("_", "-").split("-")[0]
    return kode if kode in BAHASA else BAHASA_BAWAAN


# ==========================================================================
# Bahasa per permintaan
# ==========================================================================
#
# Pesan galat lahir jauh di dalam lapisan yang tidak tahu apa-apa tentang
# tampilan -- pemeriksa stok, pencari baris, validator tanggal. Melewatkan
# `lang` sampai ke sana berarti menambah satu parameter pada belasan fungsi
# yang tidak punya urusan dengan bahasa, hanya agar satu kalimat kegagalan
# terbaca benar.
#
# Karena itu bahasa satu permintaan disimpan sebagai nilai berkonteks: middleware
# menyetelnya sekali dari query string, dan siapa pun yang menyusun pesan galat
# membacanya tanpa perlu menerimanya. Nilainya terikat pada permintaan yang
# sedang berjalan, jadi dua permintaan berbeda bahasa yang datang bersamaan
# tidak saling menimpa.

_bahasa_permintaan: ContextVar[str] = ContextVar("bahasa_permintaan", default=BAHASA_BAWAAN)


def set_bahasa_permintaan(lang: str | None) -> None:
    _bahasa_permintaan.set(normalisasi(lang))


def bahasa_permintaan() -> str:
    return _bahasa_permintaan.get()


# ==========================================================================
# Pemformatan angka & tanggal
# ==========================================================================

def fmt_angka(nilai, lang: str = BAHASA_BAWAAN, desimal: int = 2,
              kosong: str = "—") -> str:
    """
    Angka menurut kebiasaan bahasanya.

    id: 1.234,5   en: 1,234.5

    Nol di belakang koma dipangkas -- "156" lebih mudah dibaca daripada
    "156,00", dan bilangan bulat memang tidak punya bagian pecahan untuk
    ditunjukkan.
    """
    if nilai is None or nilai == "":
        return kosong
    try:
        v = float(nilai)
    except (TypeError, ValueError):
        return kosong

    s = f"{v:,.{desimal}f}"          # selalu gaya Inggris lebih dulu
    utuh, _, pecah = s.partition(".")
    pecah = pecah.rstrip("0")

    if normalisasi(lang) == "id":
        utuh = utuh.replace(",", ".")
        return f"{utuh},{pecah}" if pecah else utuh
    return f"{utuh}.{pecah}" if pecah else utuh


_BULAN = {
    "id": ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
           "Jul", "Agu", "Sep", "Okt", "Nov", "Des"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def fmt_tanggal_pendek(d, lang: str = BAHASA_BAWAAN) -> str:
    """Tanggal ringkas tanpa tahun: "5 Agu" / "Aug 5"."""
    if isinstance(d, str):
        try:
            d = date.fromisoformat(d)
        except ValueError:
            return d
    if d is None:
        return ""
    bulan = _BULAN[normalisasi(lang)][d.month - 1]
    return f"{d.day} {bulan}" if normalisasi(lang) == "id" else f"{bulan} {d.day}"


# ==========================================================================
# Kamus
# ==========================================================================
#
# Kunci ditulis sebagai jalur bertitik supaya asal-usulnya terbaca dari
# namanya sendiri: "reorder.reason.*" jelas milik kalimat status pemesanan.

TEKS: dict[str, dict[str, str]] = {

    # ---------------- status keputusan ----------------
    #
    # TIGA STATUS, dan kata-katanya dipilih supaya tidak saling mengaburkan.
    # "Perlu reorder" berarti PESAN SEKARANG UNTUK KEBUTUHAN KE DEPAN -- bukan
    # bahwa stok sudah habis; itu pekerjaan "Risiko stockout". Label lama
    # "Segera pesan" dibuang justru karena kata "segera" membuat keduanya
    # terdengar sama mendesak.
    "status.label.AMAN": {"id": "Stok aman", "en": "Stock healthy"},
    "status.label.PERLU_REORDER": {"id": "Perlu reorder", "en": "Needs reorder"},
    "status.label.RISIKO_STOCKOUT": {"id": "Risiko stockout", "en": "Stockout risk"},

    "status.short.AMAN": {"id": "AMAN", "en": "HEALTHY"},
    "status.short.PERLU_REORDER": {"id": "PERLU REORDER", "en": "NEEDS REORDER"},
    "status.short.RISIKO_STOCKOUT": {"id": "RISIKO STOCKOUT", "en": "STOCKOUT RISK"},

    "status.action.AMAN": {"id": "Belum perlu pengadaan", "en": "No procurement needed"},
    "status.action.PERLU_REORDER": {
        "id": "Pesan sekarang untuk kebutuhan ke depan",
        "en": "Order now to cover upcoming demand",
    },
    "status.action.RISIKO_STOCKOUT": {
        "id": "Pesan hari ini dan cari penutup sementara",
        "en": "Order today and arrange a stopgap",
    },

    "action.sentence.AMAN": {
        "id": "Belum perlu pengadaan; stok tersedia masih di atas titik pesan efektif.",
        "en": "No procurement needed; available stock is still above the effective reorder point.",
    },
    "action.sentence.PERLU_REORDER": {
        "id": "Buat pesanan sekarang untuk menutup kebutuhan ke depan; stoknya belum habis, tetapi menunggu lebih lama berarti kiriman datang terlambat.",
        "en": "Raise the order now to cover upcoming demand; stock has not run out, but waiting longer means the delivery arrives too late.",
    },
    "action.sentence.RISIKO_STOCKOUT": {
        "id": "Stok diperkirakan habis sebelum kiriman tiba. Pesan hari ini, dan siapkan penutup sementara untuk selisih waktunya.",
        "en": "Stock is projected to run out before any delivery arrives. Order today, and arrange a stopgap for the gap.",
    },

    # Warisan sumbu status lama (AMAN/PANTAU/SEGERA_PESAN). PANTAU tidak
    # diterbitkan lagi -- lihat catatan pada app/decision.py -- tetapi kuncinya
    # dipertahankan supaya jawaban lama yang tersimpan di mana pun tetap dapat
    # dilabeli alih-alih merender nama kunci mentah.
    "status.label.PANTAU": {"id": "Perlu dipantau", "en": "Watch closely"},
    "status.short.PANTAU": {"id": "PERLU DIPANTAU", "en": "WATCH CLOSELY"},
    "status.action.PANTAU": {
        "id": "Belum perlu pengadaan, siapkan rencana",
        "en": "No procurement yet, prepare a plan",
    },
    "action.sentence.PANTAU": {
        "id": "Belum ada jumlah yang perlu dipesan hari ini, tetapi titik pesan sudah dekat — siapkan rencana pengadaannya.",
        "en": "Nothing needs ordering today, but the reorder point is close — prepare the procurement plan.",
    },
    "status.label.SEGERA_PESAN": {"id": "Segera pesan", "en": "Order now"},
    "status.short.SEGERA_PESAN": {"id": "SEGERA PESAN", "en": "ORDER NOW"},
    "status.action.SEGERA_PESAN": {"id": "Buat pesanan sekarang", "en": "Raise the order now"},
    "action.sentence.SEGERA_PESAN": {
        "id": "Buat pesanan pembelian sekarang; menunda berarti stok berisiko habis sebelum kiriman datang.",
        "en": "Raise the purchase order now; delaying risks running out before the delivery arrives.",
    },

    # ---------------- prioritas ----------------
    "priority.label.TINGGI": {"id": "Tinggi", "en": "High"},
    "priority.label.SEDANG": {"id": "Sedang", "en": "Medium"},
    "priority.label.RENDAH": {"id": "Rendah", "en": "Low"},

    "warn.lumpy": {
        "id": "Pola pemakaian barang ini berupa pengambilan sekaligus, stok dapat menembus batas lebih cepat dari proyeksi.",
        "en": "This item is drawn in bulk, so stock can cross the threshold faster than projected.",
    },

    # ---------------- rentang hari ----------------
    "bucket.touched": {"id": "Sudah tersentuh", "en": "Already reached"},
    "bucket.1w": {"id": "±1 minggu", "en": "±1 week"},
    "bucket.2w": {"id": "±2 minggu", "en": "±2 weeks"},
    "bucket.3w": {"id": "±3 minggu", "en": "±3 weeks"},
    "bucket.gt3w": {"id": "> 3 minggu", "en": "> 3 weeks"},

    # ---------------- laju pemakaian ----------------
    "freq.uncomputed.label": {"id": "Belum dapat dihitung", "en": "Not computable yet"},
    "freq.uncomputed.detail": {
        "id": "histori belum memenuhi syarat",
        "en": "history does not meet the threshold",
    },
    "freq.none.label": {"id": "Tidak ada pemakaian", "en": "No consumption"},
    "freq.none.detail.days": {
        "id": "dalam {n} hari terakhir",
        "en": "in the last {n} days",
    },
    "freq.none.detail.generic": {
        "id": "pada periode histori",
        "en": "across the history period",
    },
    "freq.per_day": {"id": "per hari", "en": "per day"},
    "freq.per_days": {"id": "per {n} hari", "en": "every {n} days"},

    # ---------------- menuju titik pesan ----------------
    "days_to.touched": {
        "id": "Sudah melewati titik pesan",
        "en": "Reorder point already passed",
    },
    "days_to.no_usage": {
        "id": "Tidak ada konsumsi terdeteksi",
        "en": "No consumption detected",
    },
    "days_to.days": {"id": "{n} hari", "en": "{n} days"},

    # ---------------- titik pesan efektif ----------------
    "erop.master_only": {
        "id": "Mengikuti titik pesan master — kebutuhan masa tunggu belum dapat dihitung, jadi ambang ini belum diturunkan dari laju pemakaian.",
        "en": "Follows the master reorder point — lead time demand cannot be computed yet, so this threshold is not yet derived from the consumption rate.",
    },
    "erop.basis": {
        "id": "Kebutuhan masa tunggu {ld}{u} + safety stock {ss}{u} = {e}{u}.",
        "en": "Lead time demand {ld}{u} + safety stock {ss}{u} = {e}{u}.",
    },
    "erop.same": {
        "id": "{dasar} Sama dengan titik pesan master.",
        "en": "{dasar} Identical to the master reorder point.",
    },
    "erop.diff": {
        "id": "{dasar} Angka ini {arah} dari titik pesan master ({m}{u}) karena dihitung dari laju pemakaian dan lead time yang sebenarnya, bukan dari ambang yang ditetapkan pada master barang.",
        "en": "{dasar} It is {arah} than the master reorder point ({m}{u}) because it is derived from the actual consumption rate and lead time, not from the threshold set on the item master.",
    },
    "erop.lower": {"id": "lebih rendah", "en": "lower"},
    "erop.higher": {"id": "lebih tinggi", "en": "higher"},

    # ---------------- alasan status pemesanan ----------------
    # Kalimat alasan menyebut PERBANDINGAN yang menghasilkan statusnya, bukan
    # mengulang labelnya. Pembaca yang bertanya "kenapa barang ini muncul di
    # sini" mendapat jawabannya dalam satu baris, dengan angka yang sama persis
    # dengan kolom di sebelahnya.
    "reorder.reason.perlu": {
        "id": "Stok tersedia {s}{u} sudah berada pada atau di bawah titik pesan efektif {e}{u} — pesan sekarang agar kiriman tiba sebelum stok menipis.",
        "en": "Available stock {s}{u} is at or below the effective reorder point {e}{u} — order now so the delivery lands before stock runs thin.",
    },
    "reorder.reason.stockout.before_lead": {
        "id": "Stok tersedia {s}{u} diperkirakan habis sebelum kiriman berikutnya tiba.",
        "en": "Available stock {s}{u} is projected to run out before the next delivery arrives.",
    },
    "reorder.reason.stockout.empty": {
        "id": "Stok tersedia sudah habis.",
        "en": "Available stock has run out.",
    },
    # Warisan sumbu status lama; tidak dipakai lagi oleh kode yang berjalan.
    "reorder.reason.segera": {
        "id": "Stok tersedia {s}{u} sudah berada pada atau di bawah titik pesan efektif.",
        "en": "Available stock {s}{u} is at or below the effective reorder point.",
    },
    # Mode periode (halaman Pemesanan Ulang): alasannya menyebut periode yang
    # dipilih dan angka yang sama dengan kolom Kebutuhan dan Kurang/Sisa.
    "reorder.reason.periode.kurang": {
        "id": "Kebutuhan {n} hari {b}{u}, stok tersedia {s}{u} — kurang {k}{u}.",
        "en": "{n}-day need is {b}{u}, available stock {s}{u} — short by {k}{u}.",
    },
    "reorder.reason.periode.titik_pesan": {
        "id": "Stok cukup untuk {n} hari, tetapi sudah menyentuh titik pesan {e}{u} — kiriman butuh {l} hari, jadi pesan sekarang.",
        "en": "Stock covers {n} days but has reached the reorder point {e}{u} — delivery takes {l} days, so order now.",
    },
    "reorder.reason.periode.titik_pesan_tanpa_lead": {
        "id": "Stok cukup untuk {n} hari, tetapi sudah menyentuh titik pesan {e}{u}.",
        "en": "Stock covers {n} days but has reached the reorder point {e}{u}.",
    },
    "reorder.reason.periode.cukup": {
        "id": "Kebutuhan {n} hari {b}{u}, stok tersedia {s}{u} — cukup.",
        "en": "{n}-day need is {b}{u}, available stock {s}{u} — enough.",
    },
    "reorder.reason.periode.diam": {
        "id": "Tidak ada pemakaian yang diprakirakan dalam {n} hari.",
        "en": "No usage is forecast over the next {n} days.",
    },
    "reorder.reason.periode.belum": {
        "id": "Prakiraan belum tersedia; status dinilai dari titik pesan saja.",
        "en": "No forecast yet; status is judged from the reorder point alone.",
    },
    "reorder.reason.aman": {
        "id": "Stok tersedia {s}{u} masih di atas titik pesan efektif.",
        "en": "Available stock {s}{u} is still above the effective reorder point.",
    },

    # ---------------- pengadaan ----------------
    "order.na.title": {
        "id": "Jumlah pengadaan belum dapat dihitung",
        "en": "Order quantity cannot be computed yet",
    },
    "order.na.body": {
        "id": "Laju pemakaian atau waktu tunggu kiriman belum diketahui. Lengkapi lead time pada master barang agar angka ini terbit.",
        "en": "The consumption rate or the supplier lead time is unknown. Fill in the lead time on the item master for this figure to appear.",
    },
    "order.none.title": {"id": "Belum perlu pengadaan", "en": "No procurement needed"},
    "order.none.body": {
        "id": "Stok tersedia {t}{u} masih di atas titik pesan efektif, jadi tidak ada kekurangan yang perlu ditutup hari ini.",
        "en": "Available stock {t}{u} is still above the effective reorder point, so there is no shortfall to cover today.",
    },
    # Mode periode: alasan jumlahnya menyebut periode, bukan masa tunggu.
    "order.periode.none.body": {
        "id": "Stok tersedia {t}{u} cukup untuk kebutuhan {n} hari ({b}{u}), jadi belum ada yang perlu dipesan.",
        "en": "Available stock {t}{u} covers the {n}-day need ({b}{u}), so nothing needs ordering yet.",
    },
    "order.periode.some.body": {
        "id": "Sasaran pengisian {s}{u} — kebutuhan {n} hari ({b}{u}) ditambah stok pengaman, tidak pernah di bawah titik pesan efektif — dikurangi stok tersedia {t}{u}.",
        "en": "Order-up-to level {s}{u} — the {n}-day need ({b}{u}) plus safety stock, never below the effective reorder point — minus available stock {t}{u}.",
    },
    "order.some.title": {"id": "Pesan {qty}{u}", "en": "Order {qty}{u}"},
    # Kalimat pembukanya DIHAPUS: "stok tersedia sekian sudah menyentuh titik
    # pesan efektif sekian" adalah kalimat yang sama persis dengan sub-headline
    # panel keputusan (reorder.reason.segera), dan keduanya berdiri pada satu
    # gulungan layar. Yang tersisa di sini justru bagian yang tidak diucapkan
    # di tempat lain: dari mana angka pengisiannya datang.
    "order.some.body": {
        "id": "Pengisian diarahkan sampai {s}{u} — titik pesan efektif ditambah satu kali kebutuhan masa tunggu ({ld}{u}) — supaya stok tidak langsung menyentuh titik pesan lagi begitu kiriman datang.",
        "en": "Replenishment targets {s}{u} — the effective reorder point plus one lead time demand ({ld}{u}) — so stock does not fall straight back to the threshold once the delivery lands.",
    },

    # ---------------- panel saran ----------------
    # SATU SATUAN UNTUK KEDUA UKURAN WAKTU: HARI. Ketahanan stok dulu berbunyi
    # "cukup untuk ±21 kali pengambilan lagi" sementara jarak ke titik pesan
    # berbunyi "dalam 14 hari" -- dua satuan yang tidak sebanding pada satu
    # kalimat, dan pembaca yang menyandingkan 21 dengan 14 mengira keduanya
    # sejenis. Keduanya kini hari, masing-masing dengan label yang menyebut
    # peristiwanya sendiri.
    #
    # Kalimat inti ("menyentuh titik pesan efektif ...") ditulis BERHURUF KECIL
    # karena ia bisa berdiri sendiri atau menjadi anak kalimat setelah
    # ketahanan stok; kapitalisasinya diputuskan pemanggil, sekali, bukan lewat
    # dua salinan kalimat yang sama di sini.
    "advice.cover": {
        "id": "Stok bertahan ±{n} hari sampai habis; {inti}",
        "en": "Stock lasts roughly {n} days until it runs out; {inti}",
    },
    "advice.touched": {
        "id": "stok tersedia sudah berada di titik pesan efektif ({e}{u}) atau di bawahnya.",
        "en": "available stock is at or below the effective reorder point ({e}{u}).",
    },
    "advice.no_usage": {
        "id": "tidak ada konsumsi terdeteksi, sehingga waktu menuju titik pesan efektif tidak dapat diperkirakan.",
        "en": "no consumption detected, so the time to the effective reorder point cannot be estimated.",
    },
    "advice.no_trend": {
        "id": "belum ada tren pemakaian, sehingga waktu menuju titik pesan efektif belum dapat diperkirakan.",
        "en": "no consumption trend yet, so the time to the effective reorder point cannot be estimated.",
    },
    "advice.eta": {
        "id": "menyentuh titik pesan efektif ({e}{u}) dalam ±{n} hari.",
        "en": "reaching the effective reorder point ({e}{u}) in roughly {n} days.",
    },
    # ---- Strategi layanan pada rantai ROP ---------------------------------
    # Namanya menyebut KONSEKUENSINYA, bukan Z-score-nya. "Z = 2,05" tidak
    # berarti apa-apa bagi orang gudang sampai diterjemahkan menjadi "98 dari
    # 100 kali permintaan tertutup" -- dan itulah yang sebenarnya sedang ia
    # putuskan.
    "strategi.aman": {"id": "Aman", "en": "Safe"},
    "strategi.standar": {"id": "Standar", "en": "Standard"},
    "strategi.hemat": {"id": "Hemat", "en": "Lean"},
    "strategi.desc.aman": {
        "id": "Menutup 98 dari 100 kali permintaan. Cadangan paling tebal, risiko kehabisan paling kecil, modal tertahan paling banyak.",
        "en": "Covers 98 out of 100 demand occasions. Thickest buffer, lowest stockout risk, most capital tied up.",
    },
    "strategi.desc.standar": {
        "id": "Menutup 90 dari 100 kali permintaan. Titik tengah yang lazim dipakai untuk barang yang penting tetapi bukan penghenti produksi.",
        "en": "Covers 90 out of 100 demand occasions. The common middle ground for items that matter but do not halt production.",
    },
    "strategi.desc.hemat": {
        "id": "Menutup 80 dari 100 kali permintaan. Modal paling hemat, tetapi kehabisan akan lebih sering terjadi.",
        "en": "Covers 80 out of 100 demand occasions. Leanest on capital, but stockouts will happen more often.",
    },

    # ---- Nama model prakiraan ---------------------------------------------
    # Namanya disebut apa adanya, bukan diterjemahkan menjadi istilah karangan.
    # "Croston" dan "Theta" adalah nama metode yang dapat dicari orang di luar
    # sana; menggantinya menjadi "Metode Selang Permintaan" hanya memutus
    # pengguna dari seluruh literaturnya. Yang diterjemahkan keterangannya.
    "model.best": {"id": "Terbaik (otomatis)", "en": "Best (automatic)"},
    "model.statistik": {"id": "Statistik Sederhana", "en": "Simple Statistics"},
    "model.croston_sba": {"id": "Croston SBA", "en": "Croston SBA"},
    "model.theta": {"id": "Theta", "en": "Theta"},
    "model.ses": {"id": "Pemulusan Eksponensial", "en": "Exponential Smoothing"},
    "model.seasonal_naive": {"id": "Naif Musiman (mingguan)",
                             "en": "Seasonal Naive (weekly)"},
    "model.wma": {"id": "Rata-rata Bergerak Berbobot",
                  "en": "Weighted Moving Average"},
    "model.xgboost_tweedie": {"id": "XGBoost Tweedie", "en": "XGBoost Tweedie"},
    "model.weighted_moving_average": {"id": "Rata-rata Bergerak Berbobot",
                                      "en": "Weighted Moving Average"},

    "model.desc.statistik": {
        "id": "Rata-rata pemakaian harian dari riwayat, dengan cadangan dari simpangan bakunya. Tanpa model apa pun -- angkanya dapat dihitung ulang dengan tangan.",
        "en": "Average daily usage from history, with a buffer from its standard deviation. No model at all -- the numbers can be recomputed by hand.",
    },
    "model.desc.best": {
        "id": "Seluruh model diadu di atas riwayat barang ini, lalu yang galatnya terkecil dipakai meramal.",
        "en": "Every model is scored against this item's own history, and the one with the smallest error does the forecasting.",
    },
    "model.desc.croston_sba": {
        "id": "Untuk permintaan yang berlubang: ukuran sekali ambil dan jarak antar pengambilan dimuluskan terpisah.",
        "en": "For intermittent demand: pick size and the gap between picks are smoothed separately.",
    },
    "model.desc.theta": {
        "id": "Menggabungkan arah jangka panjang dengan tingkat terkini; kuat pada deret yang menanjak atau menurun.",
        "en": "Combines the long-run trend with the current level; strong on rising or falling series.",
    },
    "model.desc.ses": {
        "id": "Rata-rata yang memberi bobot menurun pada hari yang makin lama; tenang pada permintaan yang stabil.",
        "en": "An average weighting recent days more heavily; calm on stable demand.",
    },
    "model.desc.seasonal_naive": {
        "id": "Meramal tiap hari dari hari yang sama pada minggu-minggu sebelumnya; mengikuti irama minggu kerja.",
        "en": "Forecasts each day from the same weekday in previous weeks; follows the working-week rhythm.",
    },
    "model.desc.wma": {
        "id": "Rata-rata berbobot linear pada seluruh jendela histori; sederhana dan sulit dibuat keliru.",
        "en": "A linearly weighted average over the whole history window; simple and hard to get wrong.",
    },
    "model.desc.xgboost_tweedie": {
        "id": "Model pembelajaran mesin yang dilatih lintas barang; menangkap pola yang tidak terlihat pada satu deret saja.",
        "en": "A machine-learning model trained across items; catches patterns invisible in a single series.",
    },

    # ---- Cerita halaman AI ----------------------------------------------
    # Tiga kalimat berurutan: apa yang terjadi, ke mana arahnya, apa
    # tindakannya. Kalimat ketiga dan penutupnya TIDAK ditulis ulang di sini --
    # keduanya memakai kalimat keputusan yang sudah ada (order_qty_reason,
    # confidence_note), supaya satu kesimpulan tidak punya dua rumusan yang
    # bisa berbeda bunyi setelah salah satu diubah.
    "cerita.situasi.pakai": {
        "id": "Selama {hari} hari terakhir, {nama} di {gudang} terpakai rata-rata {laju}{u} per hari.",
        "en": "Over the last {hari} days, {nama} at {gudang} was consumed at an average of {laju}{u} per day.",
    },
    "cerita.situasi.diam": {
        "id": "Selama {hari} hari terakhir, {nama} di {gudang} tidak tercatat keluar sama sekali.",
        "en": "Over the last {hari} days, {nama} at {gudang} recorded no outflow at all.",
    },
    "cerita.arah.eta": {
        "id": "Dari {stok}{u} yang ada hari ini, {hari} hari ke depan diperkirakan menyisakan {sisa}{u}, dan titik pesan efektif tersentuh dalam ±{n} hari.",
        "en": "From the {stok}{u} on hand today, the next {hari} days are expected to leave {sisa}{u}, reaching the effective reorder point in roughly {n} days.",
    },
    "cerita.arah.tersentuh": {
        "id": "Dari {stok}{u} yang ada hari ini, {hari} hari ke depan diperkirakan menyisakan {sisa}{u} — stoknya sudah berada di titik pesan efektif atau di bawahnya.",
        "en": "From the {stok}{u} on hand today, the next {hari} days are expected to leave {sisa}{u} — stock is already at or below the effective reorder point.",
    },
    "cerita.arah.tanpa_eta": {
        "id": "Dari {stok}{u} yang ada hari ini, {hari} hari ke depan diperkirakan menyisakan {sisa}{u}; jarak menuju titik pesan efektif belum dapat diperkirakan.",
        "en": "From the {stok}{u} on hand today, the next {hari} days are expected to leave {sisa}{u}; the distance to the effective reorder point cannot be estimated yet.",
    },

    "cerita.beda_lapisan.habis_kurang": {
        "id": "Meski begitu, pada periode {hari} hari yang sedang ditampilkan stok diperkirakan habis dalam ±{n} hari dan kurang {k}{u} di ujungnya — pemesanan tetap perlu dilakukan, hanya belum hari ini.",
        "en": "Even so, over the {hari}-day period on screen the stock is expected to run out in about {n} days and fall {k}{u} short at the end — an order will still be needed, just not today.",
    },
    "cerita.beda_lapisan.habis": {
        "id": "Meski begitu, pada periode {hari} hari yang sedang ditampilkan stok diperkirakan habis dalam ±{n} hari — pemesanan tetap perlu dilakukan, hanya belum hari ini.",
        "en": "Even so, over the {hari}-day period on screen the stock is expected to run out in about {n} days — an order will still be needed, just not today.",
    },
    "cerita.beda_lapisan.kurang": {
        "id": "Meski begitu, pada periode {hari} hari yang sedang ditampilkan stok diperkirakan kurang {k}{u} di ujungnya — pemesanan tetap perlu dilakukan, hanya belum hari ini.",
        "en": "Even so, over the {hari}-day period on screen the stock is expected to fall {k}{u} short at the end — an order will still be needed, just not today.",
    },

    # Dua bentuk lama disimpan karena `remaining_pickups` masih terbit di API
    # dan pembaca lain boleh saja masih menyusun kalimatnya sendiri. Keduanya
    # tidak lagi dipakai halaman Reorder.
    "advice.pickups": {
        "id": "Stok cukup untuk ±{n} kali pengambilan lagi.",
        "en": "Stock covers roughly {n} more pickings.",
    },
    "advice.pickups_one": {
        "id": "Stok cukup untuk ±{n} kali pengambilan lagi.",
        "en": "Stock covers roughly {n} more picking.",
    },

    # ---------------- mutu data ----------------
    "quality.rendah": {"id": "rendah", "en": "low"},
    "quality.sedang": {"id": "sedang", "en": "medium"},
    "quality.tinggi": {"id": "tinggi", "en": "high"},
    "quality.reason.short": {"id": "histori hanya {n} hari", "en": "only {n} days of history"},
    "quality.reason.normal": {"id": "histori {n} hari", "en": "{n} days of history"},
    "quality.reason.ratio": {
        "id": "hanya {a} dari {b} hari ada pengeluaran",
        "en": "only {a} of {b} days had any outflow",
    },

    # ---------------- tingkat keyakinan halaman Reorder ----------------
    # Mutu histori sudah lama dihitung, tetapi hanya sampai sebagai lencana
    # kecil di samping satu angka. Kalimat di bawah menaikkannya menjadi
    # keterangan tingkat halaman, karena SELURUH angka turunan lapisan reorder
    # lahir dari laju pemakaian, dan laju pemakaian lahir dari histori yang
    # sama. Ketiga angka disebut namanya satu per satu, bukan diringkas jadi
    # "angka di halaman ini", supaya pembaca tahu persis apa yang terpengaruh.
    # Subjeknya disebut namanya satu per satu, bukan diringkas menjadi "angka
    # di halaman ini": pembaca perlu tahu persis apa yang terpengaruh. Dua
    # daftar karena dua lapisan menghasilkan angka yang berbeda -- keduanya
    # lahir dari histori yang sama, tetapi menyebut daftar yang salah membuat
    # catatannya menunjuk angka yang tidak ada pada jawaban itu.
    "conf.subject.reorder": {
        "id": "Kebutuhan selama lead time, titik pesan efektif, dan hari menuju titik pesan",
        "en": "Lead time demand, the effective reorder point, and the days to that point",
    },
    # "Potensi kekurangan" DICABUT dari daftar ini, 2 September 2026.
    #
    # Daftar ini gunanya menunjuk angka mana yang mewarisi keterbatasan histori,
    # jadi ia hanya berguna bila setiap angka yang disebutnya benar-benar dapat
    # ditemukan pembacanya. projected_shortage tidak dirender di satu layar pun
    # sejak kartunya dibuang, sehingga menyebutnya mengirim pembaca mencari
    # angka yang tidak ada. Penggantinya, perkiraan kapan stok habis, adalah
    # kartu keempat pada halaman Prakiraan -- dan sama-sama lahir dari laju
    # pemakaian yang sama.
    #
    # Kekurangan itu sendiri tetap tercakup: ia selisih antara dua angka
    # pertama, jadi peringatan yang berlaku bagi keduanya berlaku pula baginya.
    "conf.subject.forecast": {
        "id": "Perkiraan kebutuhan periode, perkiraan sisa stok, dan perkiraan kapan stok habis",
        "en": "Period demand, the expected remaining stock, and the projected stockout date",
    },
    "conf.note.low": {
        "id": "{subjek} seluruhnya dihitung dari {reason}, sehingga bisa kurang akurat: {sebab}.",
        "en": "{subjek} are all computed from {reason}, so they may be less accurate: {sebab}.",
    },
    "conf.note.ok": {
        "id": "{subjek} seluruhnya dihitung dari {reason}.",
        "en": "{subjek} are all computed from {reason}.",
    },

    "weak.extrapolation": {
        "id": "estimasi melebihi satu setengah kali panjang histori — gunakan sebagai indikasi kasar",
        "en": "the estimate reaches beyond one and a half times the history length — treat it as a rough indication",
    },
    "weak.short_history": {
        "id": "histori masih terlalu pendek untuk diandalkan — gunakan sebagai indikasi kasar",
        "en": "history is still too short to rely on — treat it as a rough indication",
    },

    # ---------------- panel detail perhitungan ----------------
    "detail.section.input": {"id": "Data Masukan", "en": "Inputs"},
    "detail.section.calculation": {"id": "Perhitungan", "en": "Calculation"},
    "detail.section.conclusion": {"id": "Kesimpulan", "en": "Conclusion"},
    "detail.section.reliability": {"id": "Keandalan Data", "en": "Data Reliability"},

    "detail.current_stock": {"id": "Stok saat ini", "en": "Current stock"},
    "detail.rop_master": {"id": "Titik pesan ulang (master)", "en": "Reorder point (master)"},
    "detail.rop_master.value": {
        "id": "{rop}{u} (minimum: {min}{u})",
        "en": "{rop}{u} (minimum: {min}{u})",
    },
    "detail.forecast_period": {"id": "Periode prakiraan", "en": "Forecast period"},
    "detail.history": {"id": "Histori dianalisis", "en": "History analysed"},
    "detail.history.value": {
        "id": "{n} hari{periode} · {a} hari ada pengeluaran",
        "en": "{n} days{periode} · {a} days with outflow",
    },
    "detail.avg_usage": {"id": "Rata-rata pemakaian", "en": "Average consumption"},
    "detail.avg_usage.value": {
        "id": "{teks} — dihitung dari histori pengeluaran harian",
        "en": "{teks} — derived from the daily outflow history",
    },
    "detail.avg_usage.raw": {"id": "{v}{u}/hari", "en": "{v}{u}/day"},
    "detail.expected_usage": {
        "id": "Perkiraan pemakaian {n} hari",
        "en": "Projected consumption over {n} days",
    },
    "detail.expected_stock": {"id": "Perkiraan sisa stok", "en": "Projected stock left"},
    "detail.days_to_rop": {
        "id": "Hari menuju titik pesan (master)",
        "en": "Days to reorder point (master)",
    },
    "detail.days_to_rop.value": {"id": "{n} hari → {bucket}", "en": "{n} days → {bucket}"},
    "detail.days_to_rop.none": {
        "id": "— (tidak ada tren pemakaian) → {bucket}",
        "en": "— (no consumption trend) → {bucket}",
    },
    "detail.hits_rop": {"id": "Menyentuh titik pesan", "en": "Reaches reorder point"},
    "detail.stockout": {"id": "Perkiraan stok habis", "en": "Projected stockout"},
    "detail.in_period": {
        "id": "Dalam periode ini (hari ke-{n})",
        "en": "Within this period (day {n})",
    },
    "detail.not_in_period": {
        "id": "Tidak dalam periode prakiraan",
        "en": "Not within the forecast period",
    },
    "detail.status": {"id": "Status", "en": "Status"},
    "detail.usage_pattern": {"id": "Pola pemakaian", "en": "Consumption pattern"},
    "detail.usage_pattern.lumpy": {"id": "Terkonsentrasi (lumpy)", "en": "Bulk-drawn (lumpy)"},
    "detail.usage_pattern.regular": {"id": "Menyebar (reguler)", "en": "Spread out (regular)"},
    "detail.quality": {"id": "Mutu data", "en": "Data quality"},
    "detail.quality.value": {"id": "{level} — {reason}", "en": "{level} — {reason}"},
    "detail.as_of": {"id": "Data per", "en": "Data as of"},
    "detail.note": {"id": "Catatan", "en": "Note"},

    # ---------------- panel rekomendasi ----------------
    "rec.critical.title": {
        "id": "Perlu segera melakukan replenishment",
        "en": "Replenishment needed immediately",
    },
    "rec.critical.body_stockout": {
        "id": "Dengan pemakaian rata-rata {laju} {detail}, stok diperkirakan habis dalam {n} hari — sebelum periode {hari} hari selesai. Ajukan penerimaan barang sekarang.",
        "en": "At an average consumption of {laju} {detail}, stock is projected to run out in {n} days — before the {hari}-day period ends. Raise a receipt now.",
    },
    "rec.critical.body_rop": {
        "id": "Perkiraan sisa stok {sisa} {u} pada akhir periode {hari} hari sudah menyentuh titik pemesanan ulang {rop} {u}. Ajukan penerimaan barang.",
        "en": "Projected stock of {sisa} {u} at the end of the {hari}-day period already touches the reorder point of {rop} {u}. Raise a receipt.",
    },
    "rec.attention.title": {"id": "Stok perlu dipantau", "en": "Stock needs watching"},
    "rec.attention.body": {
        "id": "Perkiraan sisa stok {sisa} {u} masih di atas titik pemesanan ulang {rop} {u}, tetapi jaraknya tipis. Siapkan rencana pembelian sebelum periode berikutnya.",
        "en": "Projected stock of {sisa} {u} is still above the reorder point of {rop} {u}, but the margin is thin. Prepare a purchase plan before the next period.",
    },
    "rec.safe.title": {"id": "Stok masih aman", "en": "Stock is healthy"},
    "rec.safe.body": {
        "id": "Belum diperlukan restock. Estimasi stok akhir {sisa} {u}, masih di atas titik pemesanan ulang {rop} {u}.",
        "en": "No restock needed. Projected closing stock is {sisa} {u}, still above the reorder point of {rop} {u}.",
    },
    "rec.notice.ai_off": {
        "id": "Forecast berhasil dihitung, tetapi AI Recommendation sedang tidak tersedia.",
        "en": "The forecast computed successfully, but the AI recommendation is unavailable.",
    },
    "rec.insufficient.title": {
        "id": "Forecast belum tersedia",
        "en": "Forecast not available yet",
    },
    "rec.insufficient.body": {
        "id": "Histori transaksi belum cukup untuk menghasilkan prediksi yang dapat diandalkan.",
        "en": "Transaction history is not yet long enough for a dependable prediction.",
    },
    # Instruksi bahasa untuk model; ditambahkan pada prompt sistem.
    "rec.prompt.lang": {
        "id": "- Jelaskan dalam 2 sampai 4 kalimat, bahasa Indonesia yang wajar dan profesional.",
        "en": "- Explain in 2 to 4 sentences of natural, professional English.",
    },

    # ---------------- mesin prakiraan ----------------
    "forecast.insufficient": {
        "id": "Data histori belum cukup untuk menghasilkan forecast yang dapat diandalkan.",
        "en": "History is not yet sufficient to produce a dependable forecast.",
    },

    # ---------------- analisis umur pakai ----------------
    # KALIMATNYA TIDAK BOLEH MENYEBUT SEBAB. Halaman ini melaporkan bahwa
    # komponen diganti lebih cepat atau lebih lambat daripada spesifikasinya;
    # kenapa demikian menuntut data beban, suhu, dan pemeliharaan yang tidak
    # dimiliki basis data ini. Kalimat seperti "karena oli telat diganti"
    # menuduh berdasarkan satu-satunya angka yang kebetulan tersedia.
    "lt.status.PREMATURE": {"id": "Penggantian dini", "en": "Premature replacement"},
    "lt.status.NORMAL": {"id": "Wajar", "en": "Normal"},
    "lt.status.EXTENDED": {"id": "Umur lebih panjang", "en": "Extended lifetime"},
    "lt.status.INSUFFICIENT": {"id": "Belum cukup data", "en": "Not enough data"},

    "lt.trend.increasing": {
        "id": "Frekuensi penggantian meningkat",
        "en": "Replacement frequency increasing",
    },
    "lt.trend.stable": {
        "id": "Frekuensi penggantian tetap",
        "en": "Replacement frequency stable",
    },
    "lt.trend.decreasing": {
        "id": "Frekuensi penggantian menurun",
        "en": "Replacement frequency decreasing",
    },

    "lt.basis": {
        "id": "Dihitung dari {n} penggantian ({interval} jarak antar penggantian).",
        "en": "Computed from {n} replacements ({interval} intervals between them).",
    },
    "lt.basis.no_reference": {
        "id": "Umur pakai harapan belum diisi pada Master Barang, sehingga tidak ada pembanding untuk riwayat penggantiannya.",
        "en": "No expected lifetime is recorded on the item master, so its replacement history has nothing to be compared against.",
    },
    "lt.basis.single": {
        "id": "Baru {n} penggantian tercatat; jarak antar penggantian belum terbentuk.",
        "en": "Only {n} replacement recorded so far; no interval between replacements exists yet.",
    },

    # "berpotensi", bukan "akan". Yang diketahui adalah pola yang sudah
    # terjadi; permintaan yang datang bukan miliknya untuk dijanjikan.
    "lt.impact.higher": {
        "id": "Berpotensi menaikkan kebutuhan sparepart ke depan.",
        "en": "Potentially higher future sparepart demand.",
    },
    "lt.impact.lower": {
        "id": "Berpotensi menurunkan kebutuhan sparepart ke depan.",
        "en": "Potentially lower future sparepart demand.",
    },
    "lt.impact.stable": {
        "id": "Kebutuhan sparepart ke depan cenderung tetap.",
        "en": "Future sparepart demand is likely to stay level.",
    },

    "lt.assumption": {
        "id": ("Umur pakai bersatuan jam dikonversi memakai {jam} jam operasi "
               "per hari. Pita wajar adalah \u00b1{persen}% terhadap umur pakai "
               "harapan."),
        "en": ("Lifetimes stated in hours are converted using {jam} operating "
               "hours per day. The normal band is \u00b1{persen}% around the "
               "expected lifetime."),
    },

    "lt.err.status": {
        "id": "Saringan status hanya menerima: {sah}.",
        "en": "The status filter accepts only: {sah}.",
    },

    # --- faktor pendukung ---
    # Tidak satu pun tersedia hari ini. Daftar ini ADA justru untuk mengatakan
    # itu; menghapusnya membuat halaman diam soal apa yang tidak diketahuinya.
    "lt.factor.operating_hours": {"id": "Jam operasi", "en": "Operating hours"},
    "lt.factor.maintenance_interval": {"id": "Interval pemeliharaan", "en": "Maintenance interval"},
    "lt.factor.oil_change_interval": {"id": "Interval penggantian oli", "en": "Oil replacement interval"},
    "lt.factor.temperature": {"id": "Suhu", "en": "Temperature"},
    "lt.factor.vibration": {"id": "Getaran", "en": "Vibration"},
    "lt.factor.load": {"id": "Beban", "en": "Load"},
    "lt.factor.contamination": {"id": "Kontaminasi", "en": "Contamination"},
    "lt.factor.none": {
        "id": ("Data faktor pendukung belum tersedia, sehingga penyebab "
               "penyimpangan umur pakai tidak dapat disimpulkan dari sistem ini."),
        "en": ("Contributing factor data is unavailable, so the cause of a "
               "lifetime deviation cannot be concluded from this system."),
    },

    # ---------------- asisten ----------------
    "as.example.1": {
        "id": "Bagaimana kondisi inventory saat ini?",
        "en": "How does the inventory look right now?",
    },
    "as.example.2": {
        "id": "Berapa stok PMP-TEST-001?",
        "en": "What is the stock level of PMP-TEST-001?",
    },
    "as.example.3": {
        "id": "Apa saja barang yang low stock?",
        "en": "Which items are running low?",
    },
    "as.example.4": {
        "id": "Bandingkan barang masuk dan keluar.",
        "en": "Compare inbound against outbound movement.",
    },
    "as.example.5": {
        "id": "Apakah stok PMP-TEST-001 cukup untuk 30 hari ke depan?",
        "en": "Will PMP-TEST-001 last the next 30 days?",
    },
    "as.example.6": {
        "id": "Tampilkan aktivitas inventory terbaru.",
        "en": "Show the latest inventory activity.",
    },
    # Dua contoh terakhir sengaja berbunyi "perlu order" dan "berapa yang
    # dipesan", bukan "berapa stoknya": itulah pertanyaan yang dijawab lapisan
    # reorder, dan contoh yang pertama dibaca pengguna baru menentukan bentuk
    # pertanyaan berikutnya yang ia ajukan. Tanpa keduanya, pengguna bertanya
    # soal stok mentah lalu menyimpulkan sendiri perlu-tidaknya memesan --
    # persis kesimpulan yang modul Reorder ada untuk menggantikannya.
    "as.example.7": {
        "id": "Apakah saya perlu order BRU-000001?",
        "en": "Do I need to order BRU-000001?",
    },
    "as.example.8": {
        "id": "Berapa yang sebaiknya dipesan untuk BRU-000002?",
        "en": "How much should I order for BRU-000002?",
    },
    "as.prompt.lang": {
        "id": "Jawab dalam bahasa Indonesia yang natural, profesional, dan mudah dipahami.",
        "en": "Answer in natural, professional English that is easy to follow.",
    },

    # ---------------- pesan galat ----------------
    "err.entity.item": {"id": "Barang", "en": "Item"},
    "err.entity.warehouse": {"id": "Gudang", "en": "Warehouse"},
    "err.entity.supplier": {"id": "Supplier", "en": "Supplier"},
    "err.entity.receipt": {"id": "Penerimaan", "en": "Receipt"},
    "err.entity.issue": {"id": "Pengeluaran", "en": "Issue"},
    "err.entity.user": {"id": "Pengguna", "en": "User"},
    "err.entity.category": {"id": "Kategori", "en": "Category"},
    "err.entity.unit": {"id": "Satuan", "en": "Unit"},
    "err.entity.adjustment": {"id": "Penyesuaian", "en": "Adjustment"},
    "err.entity.transfer": {"id": "Transfer", "en": "Transfer"},

    # --- Master data -----------------------------------------------------
    "err.master.duplicate": {
        "id": "{entitas} dengan {kolom} '{nilai}' sudah ada.",
        "en": "{entitas} with {kolom} '{nilai}' already exists.",
    },
    "err.master.in_use": {
        "id": "{entitas} '{nama}' sudah dipakai oleh {jumlah} data lain dan tidak dapat dihapus. Nonaktifkan saja bila sudah tidak dipakai lagi.",
        "en": "{entitas} '{nama}' is referenced by {jumlah} other records and cannot be deleted. Deactivate it instead.",
    },
    "err.master.no_change": {
        "id": "Tidak ada perubahan yang dikirim.",
        "en": "No changes were submitted.",
    },
    "err.master.self_transfer": {
        "id": "Gudang asal dan tujuan tidak boleh sama.",
        "en": "Source and destination warehouse cannot be the same.",
    },
    "err.master.count_negative": {
        "id": "Hasil pencacahan tidak boleh negatif.",
        "en": "Counted quantity cannot be negative.",
    },

    # --- Impor -----------------------------------------------------------
    "err.import.empty": {
        "id": "Berkas tidak berisi satu baris data pun.",
        "en": "The file contains no data rows.",
    },
    "err.import.columns": {
        "id": "Kolom wajib belum ada: {kolom}.",
        "en": "Required columns are missing: {kolom}.",
    },
    "err.import.unreadable": {
        "id": "Berkas tidak dapat dibaca. Pastikan formatnya CSV atau Excel (.xlsx).",
        "en": "The file could not be read. Make sure it is CSV or Excel (.xlsx).",
    },
    "err.import.too_big": {
        "id": "Berkas terlalu besar. Batasnya {batas} baris per unggahan.",
        "en": "The file is too large. The limit is {batas} rows per upload.",
    },

    # --- Masuk, token, dan hak akses -------------------------------------
    # Email salah dan kata sandi salah SENGAJA memakai kalimat yang sama.
    # Membedakannya berarti memberi tahu penebak bahwa satu email terdaftar --
    # separuh pekerjaan pembobolan selesai sebelum kata sandi pertama dicoba.
    "err.auth.credentials_invalid": {
        "id": "Email atau kata sandi salah.",
        "en": "Incorrect email or password.",
    },
    "err.auth.token_missing": {
        "id": "Anda belum masuk. Silakan masuk terlebih dahulu.",
        "en": "You are not signed in. Please sign in first.",
    },
    "err.auth.token_invalid": {
        "id": "Sesi tidak berlaku. Silakan masuk kembali.",
        "en": "Session is not valid. Please sign in again.",
    },
    "err.auth.token_expired": {
        "id": "Sesi Anda sudah berakhir. Silakan masuk kembali.",
        "en": "Your session has expired. Please sign in again.",
    },
    "err.auth.user_inactive": {
        "id": "Akun Anda dinonaktifkan. Hubungi admin perusahaan Anda.",
        "en": "Your account has been deactivated. Contact your company admin.",
    },
    "err.auth.company_inactive": {
        "id": "Langganan perusahaan ini sedang tidak aktif.",
        "en": "This company's subscription is not active.",
    },
    "err.auth.forbidden": {
        "id": "Peran Anda ({peran}) tidak berhak melakukan tindakan ini.",
        "en": "Your role ({peran}) is not allowed to perform this action.",
    },
    "err.auth.email_taken": {
        "id": "Email {email} sudah terdaftar.",
        "en": "Email {email} is already registered.",
    },
    "err.auth.slug_taken": {
        "id": "Pengenal perusahaan '{slug}' sudah dipakai.",
        "en": "Company identifier '{slug}' is already taken.",
    },
    "err.auth.signup_disabled": {
        "id": "Pendaftaran mandiri sedang ditutup.",
        "en": "Self-service sign-up is currently closed.",
    },
    "err.auth.password_weak": {
        "id": "Kata sandi minimal {minimal} karakter.",
        "en": "Password must be at least {minimal} characters.",
    },
    "err.auth.password_wrong": {
        "id": "Kata sandi lama salah.",
        "en": "Current password is incorrect.",
    },
    "err.auth.owner_terakhir": {
        "id": "Pemilik perusahaan tidak dapat dinonaktifkan atau diturunkan perannya.",
        "en": "The company owner cannot be deactivated or demoted.",
    },
    "err.auth.diri_sendiri": {
        "id": "Anda tidak dapat mengubah peran atau status akun Anda sendiri.",
        "en": "You cannot change your own role or account status.",
    },
    "err.not_found": {
        "id": "{entitas} dengan id {id} tidak ditemukan.",
        "en": "{entitas} with id {id} was not found.",
    },
    "err.inactive": {
        "id": "{entitas} '{nama}' sudah tidak aktif dan tidak dapat dipakai.",
        "en": "{entitas} '{nama}' is inactive and cannot be used.",
    },
    "err.insufficient_stock": {
        "id": "Stok {sku} di {gudang} tidak mencukupi. Diminta {diminta}, tersedia {tersedia}.",
        "en": "Stock of {sku} at {gudang} is insufficient. Requested {diminta}, available {tersedia}.",
    },
    "err.date_future_receipt": {
        "id": "received_date tidak boleh melewati tanggal hari ini.",
        "en": "received_date cannot be later than today.",
    },
    "err.date_future_issue": {
        "id": "issue_date tidak boleh melewati tanggal hari ini.",
        "en": "issue_date cannot be later than today.",
    },
    "err.analysis_insufficient": {
        "id": "Analisis AI belum dapat dibuat karena histori pergerakan stok belum cukup.",
        "en": "The AI analysis cannot be produced yet: stock movement history is not sufficient.",
    },

    # ---------------- dasbor ----------------
    # SATU kalimat kondisi, empat kemungkinan, dan tiap kalimat menyebut
    # TINDAKANNYA. "3 baris stok di bawah ambang" hanya melaporkan; "3 barang
    # perlu dipesan" memberi tahu pembacanya apa yang harus terjadi berikutnya.
    "dash.state.no_items": {
        "id": "Belum ada barang terdaftar. Mulai dari halaman Master Barang.",
        "en": "No items registered yet. Start from the Item Master page.",
    },
    "dash.state.stockout": {
        "id": "{n} barang berisiko kehabisan stok dan {reorder} perlu dipesan ulang. Tangani yang berisiko lebih dulu.",
        "en": "{n} items are at risk of running out and {reorder} need reordering. Handle the at-risk ones first.",
    },
    "dash.state.reorder": {
        "id": "{n} barang sudah menyentuh titik pesan dan perlu dipesan ulang. Tidak ada yang berisiko kehabisan.",
        "en": "{n} items have reached their reorder point and need reordering. None is at risk of running out.",
    },
    "dash.state.clear": {
        "id": "Seluruh {n} barang berada di atas titik pesannya. Tidak ada yang menuntut tindakan hari ini.",
        "en": "All {n} items sit above their reorder point. Nothing requires action today.",
    },
    "dash.value_basis": {
        "id": "Nilai persediaan memakai harga referensi pada master barang (items.unit_price).",
        "en": "Inventory value uses the reference price on the item master (items.unit_price).",
    },
    # ---------------- transfer antar gudang ----------------
    #
    # KALIMATNYA MENYEBUT ANGKA, bukan kata sifat. Yang dibaca orang gudang
    # sebelum menaikkan barang ke truk adalah berapa yang berlebih dan berapa
    # jauh jalannya; "kandidat terbaik" tidak dapat diperiksa siapa pun.

    "tf.decision.TRANSFER": {"id": "Transfer", "en": "Transfer"},
    "tf.decision.TRANSFER_SEBAGIAN": {"id": "Transfer sebagian", "en": "Partial transfer"},
    "tf.decision.PEMBELIAN": {"id": "Beli baru", "en": "Purchase"},

    "tf.status.draft": {"id": "Diajukan", "en": "Proposed"},
    "tf.status.approved": {"id": "Disetujui", "en": "Approved"},
    "tf.status.in_transit": {"id": "Dikirim", "en": "Shipped"},
    "tf.status.completed": {"id": "Diterima", "en": "Received"},
    "tf.status.cancelled": {"id": "Dibatalkan", "en": "Cancelled"},

    "tf.reject.TIDAK_AMAN": {
        "id": "Gudang ini sendiri sudah menyentuh titik pesannya",
        "en": "This warehouse has itself reached its reorder point",
    },
    "tf.reject.TANPA_SURPLUS": {
        "id": "Stoknya ada, tetapi tidak ada yang berlebih di atas titik pesan efektif",
        "en": "Stock exists, but nothing sits above the effective reorder point",
    },
    "tf.reject.NONAKTIF": {"id": "Gudang nonaktif", "en": "Warehouse is inactive"},
    "tf.reject.SATUAN_BEDA": {
        "id": "Satuannya berbeda, jadi jumlahnya tidak dapat dibandingkan",
        "en": "Different unit of measure, so the quantities are not comparable",
    },
    "tf.reject.MIRIP_KURANG": {
        "id": "Namanya belum cukup mirip untuk dianggap barang yang sama",
        "en": "The names are not similar enough to be treated as the same item",
    },

    "tf.why.surplus": {"id": "surplus {n} unit", "en": "{n} units spare"},
    "tf.why.covers_all": {
        "id": "cukup menutup seluruh kebutuhan",
        "en": "enough to cover the whole shortfall",
    },
    "tf.why.covers_part": {
        "id": "menutup {n} dari {butuh} yang dibutuhkan",
        "en": "covers {n} of the {butuh} needed",
    },
    "tf.why.distance": {"id": "jarak {km} km", "en": "{km} km away"},
    "tf.why.distance_unknown": {
        "id": "jaraknya belum diketahui, jadi komponen jarak dinilai netral",
        "en": "distance unknown, so the distance component scores neutral",
    },
    "tf.why.lead": {"id": "perkiraan tempuh {n} hari", "en": "about {n} days in transit"},
    "tf.why.fuzzy": {
        "id": "dicocokkan lewat kemiripan nama {persen}%, bukan nomor barang",
        "en": "matched on {persen}% name similarity, not on the item number",
    },

    "tf.reason.full": {
        "id": "Seluruh kekurangan {qty} unit dapat ditutup transfer dari {gudang} gudang; tidak perlu membeli.",
        "en": "The full {qty}-unit shortfall can be covered by transfers from {gudang} warehouse(s); no purchase needed.",
    },
    "tf.reason.partial": {
        "id": "{qty} dari {butuh} unit dapat ditutup transfer dari {gudang} gudang; sisa {sisa} unit tetap harus dibeli.",
        "en": "{qty} of {butuh} units can be covered by transfers from {gudang} warehouse(s); the remaining {sisa} still needs purchasing.",
    },
    "tf.reason.none_eligible": {
        "id": "Gudang lain memang punya barang ini, tetapi tidak satu pun berlebih; seluruh {butuh} unit harus dibeli.",
        "en": "Other warehouses do hold this item, but none has any to spare; all {butuh} units must be purchased.",
    },
    "tf.reason.no_candidate": {
        "id": "Tidak ada gudang lain yang menyimpan barang ini; seluruh {butuh} unit harus dibeli.",
        "en": "No other warehouse stocks this item; all {butuh} units must be purchased.",
    },
    "tf.reason.no_shortage": {
        "id": "Gudang ini tidak sedang kekurangan; tidak ada yang perlu dipindahkan.",
        "en": "This warehouse is not short; there is nothing to move.",
    },
    "tf.reason.no_need_figure": {
        "id": "Kekurangannya belum dapat dihitung karena histori pemakaian belum cukup.",
        "en": "The shortfall cannot be computed yet: usage history is not sufficient.",
    },

    "err.transfer.bad_status": {
        "id": "Transfer berstatus \"{dari}\" tidak dapat dipindahkan ke \"{ke}\".",
        "en": "A transfer in \"{dari}\" cannot move to \"{ke}\".",
    },
    "err.transfer.same_warehouse": {
        "id": "Gudang asal dan gudang tujuan tidak boleh sama.",
        "en": "Source and destination warehouse must differ.",
    },
    "err.transfer.no_surplus": {
        "id": "Gudang {gudang} hanya punya {tersedia} unit {sku} yang tersedia, sedangkan yang diminta {diminta}.",
        "en": "Warehouse {gudang} has only {tersedia} units of {sku} available; {diminta} were requested.",
    },
    "err.entity.transfer": {"id": "transfer", "en": "transfer"},

    "reports.value_basis": {
        "id": "Harga referensi master barang (items.unit_price).",
        "en": "Item master reference price (items.unit_price).",
    },
}


def t(kunci: str, lang: str = BAHASA_BAWAAN, **nilai) -> str:
    """
    Satu kalimat dalam bahasa yang diminta, angkanya disubstitusi.

    Kunci yang belum diterjemahkan mengembalikan kuncinya sendiri, bukan string
    kosong: layar yang kehilangan kalimat jauh lebih sulit dilacak daripada
    layar yang menampilkan nama kuncinya.
    """
    entri = TEKS.get(kunci)
    if entri is None:
        return kunci
    teks = entri.get(normalisasi(lang)) or entri[BAHASA_BAWAAN]
    return teks.format(**nilai) if nilai else teks
