# -*- coding: utf-8 -*-
"""
Lapisan keputusan di atas hasil prakiraan.

Mesin prakiraan (app/forecasting.py) menjawab "berapa": rata-rata pemakaian,
perkiraan sisa, dan status risiko. Berkas ini menjawab tiga pertanyaan yang
sebenarnya dibawa petugas gudang ke layar:

    perlu bertindak?   ->  action_status
    kapan?             ->  days_to_rop + days_to_rop_bucket
    berapa yang dipesan?  ->  suggested_order_qty

SATU SUMBER ANGKA. Seluruh nilai turunan dihitung di sini, bukan di frontend.
Antarmuka hanya memformat apa yang dikirim; tidak ada rumus yang hidup di dua
tempat sekaligus dan bisa berselisih diam-diam.

BILANGAN BULAT UNTUK LAYAR, DESIMAL UNTUK HITUNGAN. Satuan seperti PACK
bersifat diskrit -- tidak ada pengambilan 0,6 PACK -- sehingga SETIAP angka
yang sampai ke pengguna berupa bilangan bulat. Presisi aslinya tidak dibuang
dan tidak pula dipakai untuk memutuskan dua kali: perhitungan tetap berjalan
atas float, lalu field `*_int` di bawah menyediakan versi tampilannya. Frontend
merender field itu, tidak membulatkan sendiri.

PEMBULATAN. Nilai tampilan memakai pembulatan setengah ke atas (`bulat`), satu
aturan untuk seluruh halaman. Satu-satunya pengecualian adalah JUMLAH
PENGADAAN, yang dibulatkan KE ATAS: memesan satu unit lebih banyak berongkos
gudang, memesan satu unit lebih sedikit berongkos berhenti produksi.

STATUS DAN JUMLAH TIDAK BOLEH BERSELISIH. "Segera pesan" berarti ada jumlah
yang harus dipesan, dan sebaliknya -- invarian itu dijaga di satu tempat, pada
status_keputusan(), yang menerima jumlah pengadaan sebagai masukan.
"""

from __future__ import annotations

import math

from . import i18n

# Ambang pola pemakaian "sekaligus". Di bawah 15% hari yang ada pengeluaran,
# rata-rata harian menyembunyikan bentuk sebenarnya: barang tidak menetes tiap
# hari, melainkan diambil sekaligus dalam jumlah besar sesekali. Proyeksi garis
# lurus tetap sah sebagai perkiraan, tetapi stok nyatanya bisa menembus titik
# pesan jauh lebih cepat daripada yang digambar.
AMBANG_LUMPY = 0.15

# Batas bucket rentang waktu, dalam hari.
BUCKET_1_MINGGU = 7
BUCKET_2_MINGGU = 14
BUCKET_3_MINGGU = 21

# Dipakai saat lead_time_days belum diisi pada master barang: tanpa tahu berapa
# lama pemasok mengirim, dua minggu adalah tenggat yang cukup umum untuk mulai
# menyiapkan permintaan pembelian.
FALLBACK_HARI_PANTAU = 14

# Horizon TETAP untuk seluruh perhitungan yang menjadi dasar keputusan.
#
# Dipatok supaya mengganti periode tampilan di layar Prakiraan tidak pernah
# menggeser jumlah pesanan. Nilainya 14 karena itulah batas atas jendela uji
# pada app/ml/klasik.py. Rumahnya PINDAH KE SINI dari app/routers/
# forecasting.py: sejak jumlah pesanan ikut memakainya, konstanta ini bukan
# lagi urusan satu router melainkan bagian dari lapisan keputusan itu sendiri.
# Router mengimpornya dari sini, jadi tetap satu angka di satu tempat.
HORIZON_KEPUTUSAN = 14

STATUS_AMAN = "AMAN"
STATUS_PERLU_REORDER = "PERLU_REORDER"
STATUS_RISIKO_STOCKOUT = "RISIKO_STOCKOUT"

# PANTAU DICABUT DARI SUMBU STATUS, 2 September 2026.
#
# Sumbu lama berbunyi AMAN / PANTAU / SEGERA_PESAN. PANTAU adalah peringatan
# dini -- "titik pesan efektif akan tersentuh dalam satu kali masa tunggu" --
# dan sebagai peringatan ia benar. Yang membuatnya harus pergi adalah
# perannya pada layar daftar: dengan empat status, kolom Status berhenti
# menjawab "perlu dipesan atau tidak" dan mulai menuntut pembacanya menghafal
# tingkatan. Tiga status memetakan satu-satu ke tiga tab, dan tiap barang
# hanya punya satu tempat yang benar.
#
# INFORMASINYA TIDAK HILANG. Yang dulu disampaikan PANTAU kini terbaca dari
# dua kolom yang memang menyatakannya secara langsung: hari menuju stok habis,
# dan prioritas (lihat prioritas_reorder). Barang yang dulu PANTAU kini AMAN
# dengan sisa hari yang kecil -- pernyataan yang sama, tanpa memaksa kata
# "aman" berarti dua hal.
#
# Kuncinya sengaja dipertahankan di app/i18n.py sebagai warisan: jawaban lama
# yang tersimpan di mana pun tetap dapat dilabeli, alih-alih merender nama
# kunci mentah.
STATUS_PANTAU = "PANTAU"

# Sumbu prioritas, TERPISAH dari status.
#
# Status menjawab "apa yang harus dilakukan"; prioritas menjawab "mana dulu".
# Dua barang yang sama-sama perlu dipesan tidak sama mendesaknya bila yang satu
# masih punya cadangan penyangga utuh dan yang lain sudah memakannya.
PRIORITAS_TINGGI = "TINGGI"
PRIORITAS_SEDANG = "SEDANG"
PRIORITAS_RENDAH = "RENDAH"

_STATUS = (STATUS_AMAN, STATUS_PERLU_REORDER, STATUS_RISIKO_STOCKOUT)
_PRIORITAS = (PRIORITAS_TINGGI, PRIORITAS_SEDANG, PRIORITAS_RENDAH)

LABEL_STATUS = {k: i18n.t(f"status.label.{k}") for k in _STATUS}
LABEL_STATUS_RINGKAS = {k: i18n.t(f"status.short.{k}") for k in _STATUS}
TEKS_AKSI = {k: i18n.t(f"status.action.{k}") for k in _STATUS}
KALIMAT_AKSI = {k: i18n.t(f"action.sentence.{k}") for k in _STATUS}
LABEL_PRIORITAS = {k: i18n.t(f"priority.label.{k}") for k in _PRIORITAS}
PERINGATAN_LUMPY = i18n.t("warn.lumpy")


def _angka(v) -> float | None:
    """Nilai apa pun dari basis data menjadi float, atau None bila kosong."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def bulat(v) -> int | None:
    """
    Versi TAMPILAN sebuah angka: bilangan bulat, setengah dibulatkan ke atas.

    Dipakai untuk seluruh angka yang sampai ke layar -- stok, kuantitas, dan
    jumlah hari. Satuan gudang bersifat diskrit dan panjang waktu pun dibaca
    per hari, jadi "45,48 PCS" dan "5,7 hari" hanya memberi kesan presisi yang
    tidak pernah dimiliki prakiraan.

    Ini pemformatan, BUKAN perhitungan: nilai float aslinya tetap dipakai
    seluruh rumus di berkas ini dan tetap dikirim pada field non-`_int`.

    None tetap None -- "belum dapat dihitung" tidak boleh berubah menjadi nol.
    """
    x = _angka(v)
    if x is None:
        return None
    return int(math.floor(x + 0.5))


def hari_menuju_titik_pesan(
    current_stock, reorder_point, avg_daily_usage
) -> float | None:
    """
    Berapa hari lagi stok menyentuh titik pemesanan ulang.

    None berarti pertanyaannya tidak punya jawaban: tanpa pemakaian, stok tidak
    bergerak dan tidak akan pernah menyentuh titik pesan. Itu berbeda dari nol,
    yang berarti titik pesan SUDAH tersentuh -- dan membedakan keduanya penting,
    karena yang satu tidak butuh tindakan sedangkan yang lain butuh segera.

    INILAH SUMBER UTAMA untuk pertanyaan "berapa hari lagi perlu pesan".
    Mesin prakiraan juga mengeluarkan `days_until_reorder_point`, tetapi angka
    itu dibatasi panjang periode prakiraan: None di sana berarti "tidak
    tercapai dalam horizon", bukan "tidak akan pernah tercapai". Barang yang
    menyentuh titik pesan pada hari ke-39 akan berbunyi None pada horizon 30
    hari, sedangkan fungsi ini tetap menjawab 39. Untuk keputusan, pakai yang
    ini; yang satunya untuk menandai grafik.
    """
    stok = _angka(current_stock) or 0.0
    titik = _angka(reorder_point) or 0.0
    laju = _angka(avg_daily_usage)

    if stok <= titik:
        return 0.0
    if not laju or laju <= 0:
        return None
    return (stok - titik) / laju


def bucket_hari(hari: float | None, sudah_tersentuh: bool = False,
                *, lang: str = i18n.BAHASA_BAWAAN) -> str:
    """
    Rentang kasar, bukan angka presisi.

    "±2 minggu" jujur terhadap ketelitian yang sebenarnya dimiliki prakiraan;
    "13,4 hari" memberi kesan presisi yang tidak pernah ada. Dibulatkan KE BAWAH
    supaya 7,9 hari masuk ke "±1 minggu" -- sisi yang membuat pengguna bertindak
    lebih awal.
    """
    if sudah_tersentuh:
        return i18n.t("bucket.touched", lang)
    if hari is None:
        return "—"
    h = math.floor(hari)
    if h <= BUCKET_1_MINGGU:
        return i18n.t("bucket.1w", lang)
    if h <= BUCKET_2_MINGGU:
        return i18n.t("bucket.2w", lang)
    if h <= BUCKET_3_MINGGU:
        return i18n.t("bucket.3w", lang)
    return i18n.t("bucket.gt3w", lang)


# ==========================================================================
# Lapisan reorder
# ==========================================================================
#
# TIGA LAPIS YANG SENGAJA DIPISAH, karena masing-masing menjawab pertanyaan
# yang berbeda dan memakai patokan waktu yang berbeda:
#
#   Forecasting          "berapa kebutuhan selama horizon yang dipilih?"
#                        patokan: forecast_days -- parameter TAMPILAN.
#
#   Keputusan reorder    "apakah perlu bertindak sekarang?"
#   Rekomendasi reorder  "berapa yang sebaiknya dipesan?"
#                        patokan: lead_time_days -- parameter OPERASIONAL.
#
# Karena itu tidak satu pun fungsi di bawah ini boleh menyentuh forecast_days,
# projected_shortage, atau days_until_stockout: ketiganya bergerak saat
# pengguna mengubah pilihan periode pada layar, dan urgensi pembelian tidak
# boleh ikut bergerak karenanya.
#
# BASIS STOKNYA STOK TERSEDIA, bukan stok fisik. Barang yang sudah
# dikomitmenkan keluar tidak akan menyerap permintaan baru, jadi menghitungnya
# sebagai penutup kebutuhan akan meremehkan urgensi.
#
# SATU PERBANDINGAN MENGHASILKAN DUA JAWABAN. Stok tersedia terhadap titik
# pesan efektif menentukan sekaligus APAKAH perlu memesan dan BERAPA yang
# dipesan. Selama keduanya lahir dari perbandingan yang sama, keduanya tidak
# dapat berselisih -- dan berselisihnya itulah cacat yang diperbaiki di sini:
# layar berbunyi "Segera pesan" sementara blok pengadaan berbunyi "Belum ada
# jumlah yang perlu diadakan" untuk barang yang sama.


def masa_tunggu(lead_time_days) -> float | None:
    """
    Waktu tunggu kiriman yang benar-benar dapat dipakai menghitung, atau None.

    `items.lead_time_days` berarti BERAPA HARI SEJAK DIPESAN SAMPAI BARANG
    TIBA. Itu rentang waktu yang berlalu, jadi nol sah -- pemasok yang mengirim
    di hari yang sama -- tetapi negatif tidak: barang tidak tiba sebelum
    dipesan. Nilai negatif adalah master data yang rusak, bukan masa tunggu
    yang sangat singkat.

    SATU TEMPAT UNTUK SATU ATURAN. Sebelumnya penolakan nilai negatif hanya
    hidup di dalam permintaan_selama_lead(), sehingga kebutuhan masa tunggu
    berbunyi None (tidak diketahui) sementara status_keputusan() tetap memakai
    angka rusak yang sama sebagai ambang peringatan dini -- dan karena tidak
    ada jarak yang pernah lebih kecil dari bilangan negatif, barang yang tinggal
    setengah hari dari titik pesan efektif justru berstatus "Stok aman".
    Barang yang lead time-nya belum diisi sama sekali, pada keadaan yang sama
    persis, berstatus "Perlu dipantau". Master data yang rusak jadi menghasilkan
    peringatan yang LEBIH lemah daripada master data yang kosong.

    Dikembalikan sebagai None supaya nilai rusak menempuh jalur yang sama
    dengan kolom yang belum diisi: seluruh lapisan yang bersandar pada masa
    tunggu berbunyi "belum dapat dihitung", bukan diam-diam menghitung dengan
    angka yang mustahil.
    """
    lead = _angka(lead_time_days)
    if lead is None or lead < 0:
        return None
    return lead


def permintaan_selama_lead(avg_daily_usage, lead_time_days) -> float | None:
    """
    Berapa banyak terpakai selama menunggu kiriman datang.

    Laju pemakaian harian dikali lama menunggu: inilah yang habis terpakai di
    antara saat pesanan dibuat dan saat kiriman tiba, yaitu jumlah yang harus
    sudah ada di rak pada saat pesanan dibuat.

    None berarti pertanyaannya tidak punya jawaban -- laju atau masa tunggunya
    tidak diketahui. Itu berbeda dari nol, yang berarti memang tidak ada yang
    terpakai selama masa tunggu.

    LEAD TIME NOL ADALAH ANGKA, BUKAN KEKOSONGAN. Pemasok yang mengirim di hari
    yang sama memang menghasilkan kebutuhan masa tunggu nol, dan itu jawaban
    yang sah: titik pesan efektifnya menjadi safety stock saja. Sebelumnya nol
    diperlakukan sama seperti kolom yang belum diisi, sehingga barang dengan
    lead time nol kehilangan seluruh lapisan reorder-nya.
    """
    laju = _angka(avg_daily_usage)
    lead = masa_tunggu(lead_time_days)
    if laju is None or lead is None:
        return None
    return max(0.0, laju) * lead


def titik_pesan_efektif(reorder_point, lead_time_demand, safety_stock) -> float:
    """
    Titik pesan hasil perhitungan: kebutuhan masa tunggu + cadangan penyangga.

    DUA ANGKA YANG BERBEDA, DAN KEDUANYA TETAP DITAMPILKAN. Titik pesan pada
    master barang adalah ambang yang DITETAPKAN petugas; titik pesan efektif
    adalah ambang yang DIHITUNG dari laju pemakaian, lead time, dan safety
    stock. Yang menentukan mendesak atau tidak adalah yang dihitung, karena
    hanya angka itu yang tahu berapa lama kiriman ditunggu dan seberapa cepat
    barang terpakai.

    `max()` DIKEMBALIKAN, 2 September 2026. Ambangnya kini yang tertinggi di
    antara keduanya: ambang yang ditetapkan petugas tidak boleh diam-diam
    diturunkan oleh perhitungan, karena ia sering membawa pengetahuan yang
    tidak dimiliki basis data -- pemasok yang tidak dapat diandalkan, kemasan
    yang hanya dijual per palet, musim yang belum tercermin di histori.

    KENAPA DULU DICABUT, DAN KENAPA SEKARANG AMAN. `max()` sempat dibuang
    karena pada barang dengan titik pesan master jauh di atas kebutuhan nyata,
    status berbunyi "segera pesan" berdampingan dengan jumlah pengadaan NOL --
    sasaran pengisian waktu itu (titik efektif + kebutuhan masa tunggu) bisa
    berada di bawah stok yang sudah ada. Yang memperbaikinya bukan pencabutan
    max(), melainkan sasaran pengisian: target_pengadaan() kini tidak pernah
    lebih rendah daripada titik pesan efektif, sehingga setiap barang yang
    menyentuh ambang selalu punya jumlah yang lebih besar dari nol.

    Bila kebutuhan masa tunggu tidak diketahui -- lead time belum diisi atau
    laju belum terhitung -- titik pesan master dipakai sendirian. Menghitung
    ambang dari angka yang tidak ada hanya akan menghasilkan peringatan palsu.
    """
    master = _angka(reorder_point) or 0.0
    if lead_time_demand is None:
        return master
    return max(master, lead_time_demand + (_angka(safety_stock) or 0.0))


def titik_pesan_memadai(reorder_point, lead_time_demand, safety_stock) -> bool | None:
    """
    Apakah titik pesan pada master barang sudah menutup masa tunggu.

    False berarti menunggu sampai titik pesan MASTER tersentuh lalu memesan
    akan terlambat: kiriman tiba setelah stok habis. Itu cacat MASTER DATA,
    bukan cacat stok -- barangnya mungkin baik-baik saja hari ini, tetapi
    ambangnya perlu dikalibrasi ulang.

    Sistem sendiri tidak terlambat karenanya: urgensi memakai titik pesan
    efektif, bukan yang master. Field ini menjawab pertanyaan yang berbeda --
    seberapa layak ambang pada master barang dipercaya oleh siapa pun yang
    membacanya di luar layar ini.

    None berarti belum dapat dinilai karena kebutuhan masa tunggu tidak
    diketahui. Field ini TIDAK BOLEH dipakai sendirian untuk menentukan
    urgensi; ia keterangan mutu data, bukan tingkat kegawatan.
    """
    if lead_time_demand is None:
        return None
    return (_angka(reorder_point) or 0.0) >= lead_time_demand + (_angka(safety_stock) or 0.0)


def hari_menuju_titik_pesan_efektif(
    available_stock, effective_reorder_point, avg_daily_usage
) -> float | None:
    """
    Berapa hari lagi stok tersedia menyentuh titik pesan efektif.

    Sama bentuknya dengan hari_menuju_titik_pesan(), tetapi memakai stok
    TERSEDIA dan titik pesan EFEKTIF. None berarti tidak akan pernah tersentuh
    karena tidak ada pemakaian; nol berarti sudah tersentuh.
    """
    tersedia = _angka(available_stock) or 0.0
    titik = _angka(effective_reorder_point) or 0.0
    laju = _angka(avg_daily_usage)

    if tersedia <= titik:
        return 0.0
    if not laju or laju <= 0:
        return None
    return (tersedia - titik) / laju


def hari_sampai_habis(available_stock, avg_daily_usage) -> float | None:
    """
    Berapa hari lagi stok tersedia habis sama sekali.

    TIDAK ADA RUMUS BARU DI SINI. Habis adalah titik pesan efektif yang
    ambangnya nol, jadi pertanyaannya diserahkan apa adanya ke
    hari_menuju_titik_pesan_efektif() -- satu rumus, satu tempat, dan angka ini
    mustahil berselisih dengan angka menuju titik pesan yang tercetak di
    sebelahnya.

    Berbeda dari `days_until_stockout` milik mesin prakiraan, yang dibatasi
    panjang periode prakiraan: None di sana berarti "tidak habis DI DALAM
    horizon", sedangkan None di sini berarti tidak ada pemakaian sama sekali,
    sehingga stok tidak bergerak dan tidak akan pernah habis.
    """
    return hari_menuju_titik_pesan_efektif(available_stock, 0, avg_daily_usage)


def kebutuhan_horizon_keputusan(avg_daily_usage) -> float | None:
    """
    Perkiraan pemakaian sepanjang HORIZON_KEPUTUSAN, bukan sepanjang periode
    yang sedang dipilih di layar.

    Inilah `forecast_usage` versi keputusan. Nama field yang sama pada jawaban
    /api/forecast mengikuti `days` yang diminta layar -- 7, 30, atau 90 hari --
    dan memakainya sebagai dasar jumlah pesanan berarti kuantitas pengadaan
    melompat tiga kali lipat hanya karena seseorang menggeser dropdown periode
    pada halaman Prakiraan. Pilihan itu bahkan dibagi antar kedua halaman lewat
    localStorage, jadi lompatannya terjadi tanpa satu pun kendali yang terlihat
    di layar Pemesanan Ulang.

    Horizonnya dipatok, lajunya tidak: laju harian tetap datang dari prakiraan,
    sehingga jumlah pesanan tetap mengikuti model yang dipakai dan tetap
    konsisten dengan angka di halaman Prakiraan.
    """
    laju = _angka(avg_daily_usage)
    if laju is None:
        return None
    return max(0.0, laju) * HORIZON_KEPUTUSAN


def target_pengadaan(effective_reorder_point, avg_daily_usage,
                     safety_stock) -> float | None:
    """
    Sampai berapa stok diisi ketika pengadaan dilakukan (level "S").

    Titik pesan efektif menjawab KAPAN memesan; angka ini menjawab SAMPAI MANA
    mengisi.

        target = max(titik pesan efektif,
                     kebutuhan horizon keputusan + stok pengaman)

    Suku kedua adalah rumus yang diminta: sediakan kebutuhan ke depan, lalu
    sisakan cadangan penyangga di belakangnya. Ia menggantikan sasaran lama
    (titik efektif + kebutuhan masa tunggu), yang menjawab pertanyaan yang
    lebih sempit dan tidak pernah menyebut kebutuhan mendatang sama sekali.

    SUKU PERTAMA ADALAH PENJAGA INVARIAN, dan tanpa itu modul ini menerbitkan
    kontradiksi. Sejak titik pesan efektif kembali memakai max() terhadap titik
    pesan master, ambangnya bisa berada DI ATAS kebutuhan horizon ditambah
    cadangan -- misalnya masa tunggu 30 hari dengan laju 1/hari dan cadangan
    10: ambangnya 40, sedangkan kebutuhan horizon + cadangan hanya 24. Stok 30
    lalu berstatus "perlu reorder" dengan jumlah pesanan nol, karena sasarannya
    sudah terlampaui. Mengisi sampai ambang pemicunya sendiri adalah batas
    terendah yang masih masuk akal: di bawah itu, barang yang baru datang
    langsung memicu pemesanan berikutnya di hari yang sama.

    None berarti belum dapat dihitung -- lajunya tidak diketahui.
    """
    kebutuhan = kebutuhan_horizon_keputusan(avg_daily_usage)
    if kebutuhan is None:
        return None
    return max(effective_reorder_point, kebutuhan + (_angka(safety_stock) or 0.0))


def saran_qty_reorder(effective_reorder_point, avg_daily_usage, safety_stock,
                      available_stock, punya_forecast: bool = True) -> int | None:
    """
    Berapa unit yang perlu dipesan sekarang.

        target      = target_pengadaan(...)
        kebutuhan   = max(0, target - stok tersedia)
        jumlah      = ceil(kebutuhan)

    NOL BILA STOK MASIH DI ATAS TITIK PESAN EFEKTIF, apa pun isi prakiraan.
    Inilah yang membuat "prakiraan tinggi" tidak dengan sendirinya berarti
    pengadaan: kebutuhan besar pada barang yang stoknya masih tebal tetap
    dijawab nol, karena tidak ada yang perlu ditutup hari ini.

    TIDAK PERNAH NEGATIF. Selisih dijepit di nol sebelum dibulatkan, sehingga
    stok yang melampaui sasaran menghasilkan 0 dan bukan angka minus yang
    kemudian terbaca sebagai "kembalikan ke pemasok".

    None berarti belum dapat dihitung, dan itu BERBEDA dari nol. Nol menyatakan
    "tidak perlu membeli"; None menyatakan "belum tahu" -- histori belum cukup
    atau laju belum terhitung. Menyamakan keduanya akan menampilkan "tidak
    perlu pesan" untuk barang yang sebenarnya belum pernah dinilai.

    MASA TUNGGU YANG KOSONG TIDAK LAGI MENGHAPUS JUMLAHNYA. Rumus lama
    bersandar pada kebutuhan masa tunggu dan karena itu mengembalikan None
    begitu `lead_time_days` belum diisi; rumus ini hanya menuntut laju
    pemakaian, yang selalu ada bila prakiraannya ada. Barang yang masa
    tunggunya belum dicatat kini tetap mendapat jumlah, dan yang belum
    diketahui -- kapan harus memesannya -- dinyatakan di tempat lain.

    Dibulatkan KE ATAS. Skema ini belum memuat jumlah pesanan minimum maupun
    kelipatan kemasan, jadi tidak ada pembulatan lain yang boleh diterapkan
    tanpa mengarang aturan.
    """
    if not punya_forecast:
        return None
    sasaran = target_pengadaan(effective_reorder_point, avg_daily_usage,
                               safety_stock)
    if sasaran is None:
        return None

    tersedia = _angka(available_stock) or 0.0
    if tersedia > effective_reorder_point:
        return 0

    kebutuhan = max(0.0, sasaran - tersedia)

    # BATAS PERSIS DI AMBANG. Stok yang duduk TEPAT pada titik pesan efektif
    # menghasilkan kebutuhan nol ketika sasarannya juga persis di situ -- yaitu
    # saat titik pesan master yang menang dan ia sudah menutup kebutuhan
    # horizon. Memesan nol di titik itu berarti ambangnya tidak pernah
    # terlepas: besok barang tetap di ambang, statusnya tetap perlu reorder,
    # dan layar mencetak "perlu reorder, pesan 0" setiap hari selamanya.
    #
    # Yang dipesan adalah kebutuhan SATU HORIZON KEPUTUSAN: sebanyak yang akan
    # benar-benar terpakai sebelum keadaan ini ditinjau lagi. Bukan angka
    # karangan, dan bukan pula pembulatan ke atas yang sewenang-wenang.
    #
    # Pada barang yang TIDAK ADA pemakaiannya, kebutuhan horizonnya nol dan
    # jumlahnya tetap nol -- dan itu jawaban yang benar: tidak ada yang akan
    # terpakai, jadi tidak ada yang perlu diganti. Satu-satunya keadaan di mana
    # "perlu reorder" berdampingan dengan nol.
    if kebutuhan <= 0:
        kebutuhan = kebutuhan_horizon_keputusan(avg_daily_usage) or 0.0

    return max(0, math.ceil(kebutuhan))


def stok_habis_sebelum_kiriman(available_stock, avg_daily_usage,
                               lead_time_days) -> bool:
    """
    Apakah stok diproyeksikan habis SEBELUM kiriman berikutnya tiba.

    Inilah satu-satunya keadaan yang benar-benar gawat pada modul ini: memesan
    hari ini pun tidak menolong, karena barangnya sudah nol sebelum pesanan
    sampai. Keadaan lain menuntut tindakan; yang ini menuntut tindakan DAN
    menerima bahwa sebagian kerugiannya sudah tidak dapat dihindari.

    STOK NOL SELALU MASUK, dengan atau tanpa pemakaian. Barang yang rak-nya
    sudah kosong tidak menjadi kurang gawat karena kebetulan tidak ada
    pengeluaran tercatat -- yang tidak tercatat justru pengeluaran yang tidak
    dapat dilayani.

    Tanpa masa tunggu, pertanyaannya tidak punya tenggat dan jawabannya False:
    yang belum diketahui tidak boleh diterbitkan sebagai kegawatan. Stok yang
    memang sudah nol tetap tertangkap oleh cabang di atas.
    """
    tersedia = _angka(available_stock) or 0.0
    if tersedia <= 0:
        return True

    lead = masa_tunggu(lead_time_days)
    if lead is None:
        return False

    hari = hari_sampai_habis(tersedia, avg_daily_usage)
    # None berarti tidak ada pemakaian sama sekali: stok tidak bergerak, jadi
    # ia tidak akan habis sebelum kiriman mana pun.
    return hari is not None and hari <= lead


def status_keputusan(
    available_stock,
    effective_reorder_point,
    avg_daily_usage,
    lead_time_days,
) -> str:
    """
    Tiga keadaan, dan hanya tiga.

        stok habis sebelum kiriman tiba      -> RISIKO_STOCKOUT
        stok tersedia <= titik pesan efektif -> PERLU_REORDER
        selain itu                           -> AMAN

    URUTANNYA MENGIKAT. Barang yang akan habis sebelum kiriman tiba hampir
    selalu juga berada di bawah titik pesan efektif; bila PERLU_REORDER
    diperiksa lebih dulu, tidak akan pernah ada satu pun barang berstatus
    risiko stockout.

    TIDAK MENYENTUH PRAKIRAAN PERIODE. Tidak ada `forecast_days`,
    `projected_shortage`, maupun `days_until_stockout` di sini: ketiganya
    bergerak saat pengguna menggeser periode di layar Prakiraan, dan urgensi
    pembelian tidak boleh ikut bergerak karenanya. Kebutuhan mendatang memang
    ikut menentukan BERAPA yang dipesan (lihat target_pengadaan), tetapi tidak
    pernah menentukan APAKAH perlu dipesan -- prakiraan setinggi apa pun pada
    barang yang stoknya masih di atas ambang tetap berstatus AMAN.

    JUMLAH PENGADAAN TIDAK LAGI MENJADI MASUKAN. Invarian "status mendesak
    berarti ada yang dipesan" dulu dijaga di sini dengan memeriksa `order_qty`;
    ia kini dijaga lebih awal dan lebih murah, pada target_pengadaan(), yang
    tidak pernah menghasilkan sasaran di bawah titik pesan efektif. Menjaganya
    di sini berarti status bergantung pada jumlah dan jumlah bergantung pada
    status -- lingkaran yang harus diputus di salah satu ujungnya.

    AMAN TIDAK PERNAH BERARTI "hampir bermasalah". Barang yang tinggal beberapa
    hari dari ambang tetap AMAN, dan kedekatannya dinyatakan kolom hari menuju
    habis serta prioritasnya -- bukan dengan melemahkan arti kata "aman".
    """
    if stok_habis_sebelum_kiriman(available_stock, avg_daily_usage,
                                  lead_time_days):
        return STATUS_RISIKO_STOCKOUT

    tersedia = _angka(available_stock) or 0.0
    if tersedia <= (_angka(effective_reorder_point) or 0.0):
        return STATUS_PERLU_REORDER

    return STATUS_AMAN


def status_keputusan_periode(
    available_stock,
    effective_reorder_point,
    avg_daily_usage,
    lead_time_days,
    kekurangan_periode,
) -> str:
    """
    Status pada MODE PERIODE: halaman Pemesanan Ulang, sejak 6 Oktober 2026.

        stok habis sebelum kiriman tiba        -> RISIKO_STOCKOUT
        stok kurang untuk periode yang dipilih -> PERLU_REORDER
        stok <= titik pesan efektif            -> PERLU_REORDER
        selain itu                             -> AMAN

    Aturan kedua adalah yang baru, dan ia sengaja memakai angka yang SAMA
    dengan kartu "perlu ditambah" di halaman Prakiraan: barang yang di sana
    terbaca kurang, di sini terbaca perlu dipesan. Dua halaman yang membaca
    periode yang sama tidak boleh menjawab berbeda untuk barang yang sama.

    ATURAN KETIGA TETAP ADA, sebagai jaring pengaman. Periode yang lebih
    pendek daripada masa tunggu -- 7 hari pada barang yang kirimannya 30 hari
    -- akan menyatakan "cukup" untuk barang yang harus dipesan hari ini juga
    supaya tidak kosong bulan depan. Titik pesan menangkap barang itu, dan
    kalimat alasannya menyebut terang-terangan bahwa pemicunya titik pesan.

    status_keputusan() TIDAK DIUBAH dan tetap dipakai pemanggil yang tidak
    meminta mode ini (asisten, transfer antar gudang).
    """
    if stok_habis_sebelum_kiriman(available_stock, avg_daily_usage,
                                  lead_time_days):
        return STATUS_RISIKO_STOCKOUT

    if (_angka(kekurangan_periode) or 0.0) > 0:
        return STATUS_PERLU_REORDER

    tersedia = _angka(available_stock) or 0.0
    if tersedia <= (_angka(effective_reorder_point) or 0.0):
        return STATUS_PERLU_REORDER

    return STATUS_AMAN


def target_pengadaan_periode(effective_reorder_point, kebutuhan_periode,
                             safety_stock) -> float | None:
    """
    Sasaran pengisian pada mode periode.

        target = max(titik pesan efektif, kebutuhan periode + stok pengaman)

    Bentuknya sama dengan target_pengadaan(); yang berganti hanya suku
    kebutuhannya -- jumlah prakiraan sepanjang periode yang dipilih, bukan
    laju x HORIZON_KEPUTUSAN. Suku pertamanya menjaga invarian yang sama:
    sasaran tidak pernah berada di bawah ambang pemicunya sendiri.
    """
    kebutuhan = _angka(kebutuhan_periode)
    if kebutuhan is None:
        return None
    return max(_angka(effective_reorder_point) or 0.0,
               max(0.0, kebutuhan) + (_angka(safety_stock) or 0.0))


def saran_qty_periode(status: str, effective_reorder_point, kebutuhan_periode,
                      safety_stock, available_stock,
                      punya_forecast: bool = True) -> int | None:
    """
    Berapa yang dipesan pada mode periode: sasaran dikurangi stok tersedia.

    Untuk barang yang kurang, itu sama dengan KEKURANGAN + STOK PENGAMAN --
    kalimat yang dapat diucapkan di depan tabelnya. Lebih besar hanya bila
    titik pesan efektif yang menang sebagai sasaran.

    NOL BILA AMAN, None bila belum dapat dihitung; keduanya berarti sama
    seperti pada saran_qty_reorder(). Statusnya menjadi masukan di sini karena
    pada mode ini pemicunya dua (kekurangan periode ATAU titik pesan), dan
    memeriksa ulang keduanya di dua tempat adalah undangan untuk berselisih.
    """
    if not punya_forecast:
        return None
    sasaran = target_pengadaan_periode(effective_reorder_point,
                                       kebutuhan_periode, safety_stock)
    if sasaran is None:
        return None
    if status == STATUS_AMAN:
        return 0

    tersedia = _angka(available_stock) or 0.0
    kebutuhan = max(0.0, sasaran - tersedia)
    # Sama seperti saran_qty_reorder(): stok yang duduk tepat di ambang, dengan
    # sasaran yang juga tepat di situ, memesan kebutuhan satu periode supaya
    # ambangnya terlepas.
    if kebutuhan <= 0:
        kebutuhan = max(0.0, _angka(kebutuhan_periode) or 0.0)
    return max(0, math.ceil(kebutuhan))


def prioritas_reorder(status: str, available_stock, safety_stock) -> str:
    """
    Mana yang dikerjakan lebih dulu di antara barang yang sama-sama perlu
    dipesan.

    Status menjawab APA yang harus dilakukan; kolom ini menjawab URUTANNYA.
    Tanpa itu, daftar berisi tiga puluh baris "perlu reorder" tidak memberi
    satu pun petunjuk mana yang disentuh lebih dulu, dan yang paling mendesak
    bisa berada di halaman ketiga.

    TIDAK ADA MASUKAN BARU. Ambangnya stok pengaman, yang sudah ada pada master
    barang: cadangan penyangga memang dibuat untuk menyerap keterlambatan, jadi
    barang yang sudah memakannya kehilangan justru penyangga itu.

        RISIKO_STOCKOUT                          -> tinggi
        PERLU_REORDER, stok <= stok pengaman     -> tinggi
        PERLU_REORDER lainnya                    -> sedang
        AMAN                                     -> rendah
    """
    if status == STATUS_RISIKO_STOCKOUT:
        return PRIORITAS_TINGGI
    if status == STATUS_PERLU_REORDER:
        cadangan = _angka(safety_stock) or 0.0
        tersedia = _angka(available_stock) or 0.0
        return PRIORITAS_TINGGI if tersedia <= cadangan else PRIORITAS_SEDANG
    return PRIORITAS_RENDAH


def label_frekuensi(avg_daily_usage, unit_code: str = "",
                    hari_histori: int | None = None,
                    belum_terhitung: bool = False,
                    *, lang: str = i18n.BAHASA_BAWAAN) -> dict:
    """
    Laju pemakaian dalam bentuk yang bisa dibayangkan.

    "0,082 PACK per hari" tidak berarti apa-apa bagi petugas gudang. Yang
    berarti adalah "±1 PACK per 12 hari" -- kalimat yang bisa dicocokkan dengan
    ingatannya sendiri tentang seberapa sering barang itu diambil. Karena itu
    laju di bawah satu unit per hari dibalik menjadi "berapa hari sekali",
    bukan dipaksakan sebagai pecahan.
    """
    satuan = f" {unit_code}".rstrip()
    laju = _angka(avg_daily_usage)

    # Barang yang PERNAH diambil tetapi datanya belum memenuhi syarat berbeda
    # dari barang yang memang tidak pernah diambil. Menyamakan keduanya membuat
    # kartu berbunyi "Tidak ada pemakaian" untuk barang yang jelas-jelas ada
    # pengeluarannya -- keliru, dan justru pada barang yang paling perlu
    # diperhatikan karena datanya tipis.
    if belum_terhitung:
        return {
            "label": i18n.t("freq.uncomputed.label", lang),
            "detail": i18n.t("freq.uncomputed.detail", lang),
            "quantity": None,
            "per_days": None,
            "no_usage": False,
        }

    if laju is None or laju <= 0:
        return {
            "label": i18n.t("freq.none.label", lang),
            "detail": (i18n.t("freq.none.detail.days", lang, n=hari_histori)
                       if hari_histori else i18n.t("freq.none.detail.generic", lang)),
            "quantity": 0,
            "per_days": None,
            "no_usage": True,
        }

    if laju >= 1:
        jumlah = max(1, round(laju))
        return {
            "label": f"±{jumlah}{satuan}",
            "detail": i18n.t("freq.per_day", lang),
            "quantity": jumlah,
            "per_days": 1,
            "no_usage": False,
        }

    setiap = max(1, round(1 / laju))
    return {
        "label": f"±1{satuan}",
        "detail": i18n.t("freq.per_days", lang, n=setiap),
        "quantity": 1,
        "per_days": setiap,
        "no_usage": False,
    }


# saran_qty() DIHAPUS, 2 September 2026.
#
# Rumusnya `maximum_stock - current_stock`: pesan sampai gudang penuh. Itu
# bukan keputusan pengadaan melainkan keputusan pengisian rak, dan ia tidak
# pernah menanyakan satu pun hal yang menentukan -- berapa cepat barang
# terpakai, berapa lama kiriman ditunggu, berapa cadangan yang harus tersisa.
# Pada barang dengan stok maksimum yang besar ia memesan berlipat-lipat dari
# yang dibutuhkan; pada barang yang stok maksimumnya kosong ia diam-diam jatuh
# ke rumus kedua, sehingga satu field membawa dua arti tanpa satu pun tanda.
#
# Keluarannya, `suggested_order_qty`, ternyata TIDAK PERNAH DIRENDER: layar
# Pemesanan Ulang membaca `recommended_order_qty`, dan tidak ada pembaca lain.
# Field-nya tetap diterbitkan sebagai alias demi pembaca API di luar repositori
# ini -- lihat lapisan_keputusan -- tetapi rumusnya tidak ada lagi.


def deteksi_lumpy(keluar_harian: list, total_hari: int | None = None) -> bool:
    """
    Apakah pemakaiannya berupa pengambilan sekaligus, bukan tetesan harian.

    Barang tanpa pengeluaran sama sekali TIDAK dianggap lumpy walau rasionya
    nol: ia bukan barang yang diambil sekaligus, melainkan barang yang sedang
    tidak dipakai. Menyamakan keduanya akan memunculkan peringatan "pengambilan
    sekaligus" pada barang yang tidak pernah diambil.
    """
    nilai = [_angka(v) or 0.0 for v in (keluar_harian or [])]
    total = total_hari if total_hari is not None else len(nilai)
    if not total or total <= 0:
        return False
    n_event = sum(1 for v in nilai if v > 0)
    if n_event == 0:
        return False
    return (n_event / total) < AMBANG_LUMPY


def rata_per_pengambilan(keluar_harian: list) -> float | None:
    """Rata-rata besar satu kali pengambilan; None bila belum pernah diambil."""
    nilai = [_angka(v) or 0.0 for v in (keluar_harian or []) if (_angka(v) or 0.0) > 0]
    if not nilai:
        return None
    return sum(nilai) / len(nilai)


def sisa_pengambilan(current_stock, keluar_harian: list) -> int | None:
    """
    Stok saat ini cukup untuk berapa kali pengambilan lagi.

    Dibulatkan KE BAWAH -- pengambilan yang hanya terpenuhi separuh bukan
    pengambilan.
    """
    rata = rata_per_pengambilan(keluar_harian)
    if not rata or rata <= 0:
        return None
    stok = _angka(current_stock) or 0.0
    return max(0, math.floor(stok / rata))


# ==========================================================================
# Kalimat siap render untuk halaman Reorder
# ==========================================================================
#
# Disusun di sini, bukan di frontend, karena setiap kalimat menyebut ANGKA
# YANG SAMA dengan yang tercetak pada kartu di sebelahnya. Menyusunnya di dua
# tempat berarti dua pembulatan yang bisa berselisih -- persis jenis
# kontradiksi yang sedang dibereskan.


def label_hari_menuju(hari: float | None, sudah_tersentuh: bool,
                      ada_pemakaian: bool,
                      *, lang: str = i18n.BAHASA_BAWAAN) -> str:
    """
    "16 hari", "Sudah melewati titik pesan", atau "Tidak ada konsumsi terdeteksi".

    Tiga kalimat untuk tiga keadaan yang benar-benar berbeda. Tanpa pemakaian,
    pembagiannya tidak terdefinisi -- dan jawabannya bukan "0 hari" maupun
    "tidak pernah", melainkan bahwa pertanyaannya tidak berlaku.
    """
    if sudah_tersentuh:
        return i18n.t("days_to.touched", lang)
    if not ada_pemakaian:
        return i18n.t("days_to.no_usage", lang)
    if hari is None:
        return "—"
    return i18n.t("days_to.days", lang, n=bulat(hari))


def kalimat_titik_pesan_efektif(*, lead_time_demand, safety_stock,
                                titik_efektif, titik_master, unit: str,
                                lang: str = i18n.BAHASA_BAWAAN) -> str:
    """Dari mana titik pesan efektif berasal, dan mengapa berbeda dari master."""
    u = f" {unit}".rstrip()
    if lead_time_demand is None:
        return i18n.t("erop.master_only", lang)

    dasar = i18n.t("erop.basis", lang, ld=bulat(lead_time_demand),
                   ss=bulat(safety_stock), e=bulat(titik_efektif), u=u)

    m, e = bulat(titik_master), bulat(titik_efektif)
    if m == e:
        return i18n.t("erop.same", lang, dasar=dasar)
    arah = i18n.t("erop.lower" if e < m else "erop.higher", lang)
    return i18n.t("erop.diff", lang, dasar=dasar, arah=arah, m=m, u=u)


def kalimat_status_reorder(*, action_status: str, tersedia, titik_efektif,
                           titik_master, unit: str,
                           lang: str = i18n.BAHASA_BAWAAN) -> str:
    """Satu kalimat perbandingan yang menjelaskan status, memakai angka layar."""
    u = f" {unit}".rstrip()
    s, e, m = bulat(tersedia), bulat(titik_efektif), bulat(titik_master)

    if action_status == STATUS_RISIKO_STOCKOUT:
        # Alasannya menyebut apa yang membuatnya gawat, bukan sekadar
        # perbandingan terhadap ambang: yang menentukan di sini adalah stok
        # habis lebih dulu daripada kiriman tiba, dan itulah yang harus
        # terbaca. Rak yang sudah kosong disebut apa adanya.
        if (_angka(tersedia) or 0.0) <= 0:
            return i18n.t("reorder.reason.stockout.empty", lang)
        return i18n.t("reorder.reason.stockout.before_lead", lang, s=s, u=u)
    if action_status == STATUS_PERLU_REORDER:
        return i18n.t("reorder.reason.perlu", lang, s=s, e=e, u=u)
    return i18n.t("reorder.reason.aman", lang, s=s, e=e, u=u)


def kalimat_status_periode(*, action_status: str, tersedia, titik_efektif,
                           kebutuhan, kekurangan, hari: int, masa_tunggu_hari,
                           unit: str, lang: str = i18n.BAHASA_BAWAAN) -> str:
    """
    Kalimat alasan pada mode periode. Menyebut periodenya dan angka yang sama
    dengan kolom Kebutuhan dan Kurang/Sisa di sebelahnya.

    Barang yang CUKUP untuk periodenya tetapi sudah menyentuh titik pesan
    mendapat kalimatnya sendiri: tanpa itu barisnya terbaca "sisa 7, perlu
    pesan" dan tidak ada yang menjelaskan sebabnya.
    """
    u = f" {unit}".rstrip()
    s, e = bulat(tersedia), bulat(titik_efektif)
    k, b = bulat(kekurangan) or 0, bulat(kebutuhan)

    if action_status == STATUS_RISIKO_STOCKOUT:
        if (_angka(tersedia) or 0.0) <= 0:
            return i18n.t("reorder.reason.stockout.empty", lang)
        return i18n.t("reorder.reason.stockout.before_lead", lang, s=s, u=u)
    if action_status == STATUS_PERLU_REORDER:
        if k > 0:
            return i18n.t("reorder.reason.periode.kurang", lang,
                          n=hari, b=b, s=s, k=k, u=u)
        lead = bulat(masa_tunggu(masa_tunggu_hari))
        if lead:
            return i18n.t("reorder.reason.periode.titik_pesan", lang,
                          n=hari, e=e, l=lead, u=u)
        return i18n.t("reorder.reason.periode.titik_pesan_tanpa_lead", lang,
                      n=hari, e=e, u=u)
    if b is None:
        return i18n.t("reorder.reason.periode.belum", lang)
    if b <= 0:
        return i18n.t("reorder.reason.periode.diam", lang, n=hari)
    return i18n.t("reorder.reason.periode.cukup", lang, n=hari, b=b, s=s, u=u)


def kalimat_pengadaan(*, qty: int | None, titik_efektif, sasaran,
                      tersedia, lead_time_demand, unit: str,
                      lang: str = i18n.BAHASA_BAWAAN) -> tuple[str, str]:
    """
    Judul dan alasan blok "Pengadaan Berikutnya".

    Judulnya menyebut TINDAKAN dan jumlahnya sekaligus ("Pesan 20 PCS"), supaya
    tidak ada keadaan di mana pengguna membaca status mendesak lalu harus
    menebak berapa yang dimaksud.
    """
    u = f" {unit}".rstrip()

    if qty is None:
        return (i18n.t("order.na.title", lang), i18n.t("order.na.body", lang))
    if qty == 0:
        return (
            i18n.t("order.none.title", lang),
            i18n.t("order.none.body", lang, t=bulat(tersedia),
                   e=bulat(titik_efektif), u=u),
        )
    return (
        i18n.t("order.some.title", lang, qty=qty, u=u),
        i18n.t("order.some.body", lang, t=bulat(tersedia),
               e=bulat(titik_efektif), s=bulat(sasaran),
               ld=bulat(lead_time_demand), u=u),
    )


def _kapital(kalimat: str) -> str:
    """Huruf pertama menjadi kapital; sisanya tidak disentuh."""
    return kalimat[:1].upper() + kalimat[1:] if kalimat else kalimat


def kalimat_saran(
    *,
    action_status: str,
    hari_habis: float | None,
    hari_menuju: float | None,
    titik_efektif,
    unit: str = "",
    sudah_tersentuh: bool,
    ada_pemakaian: bool,
    is_lumpy: bool,
    lang: str = i18n.BAHASA_BAWAAN,
) -> str:
    """
    Panel saran, disusun dari template berkondisi.

    Sengaja TIDAK memanggil model bahasa. Kalimat ini muncul pada setiap render
    halaman; menggantungkannya pada layanan luar berarti panel bisa kosong atau
    lambat justru saat dibutuhkan, dan menghabiskan kuota untuk mengulang
    kalimat yang bentuknya selalu sama. Rekomendasi bernuansa dari model tetap
    tersedia terpisah pada panel AI Recommendation.

    Patokannya TITIK PESAN EFEKTIF atas stok tersedia -- angka yang sama dengan
    kartu keputusan di atasnya. Sebelumnya kalimat ini memakai titik pesan
    master atas stok fisik, sehingga satu layar memuat dua jawaban berbeda
    untuk pertanyaan "berapa hari lagi".

    SATU SATUAN UNTUK KEDUA UKURAN WAKTU: HARI. Ketahanan stok dulu disebut
    sebagai "cukup untuk +-21 kali pengambilan lagi" sementara jarak ke titik
    pesan disebut dalam hari, jadi satu kalimat memuat dua satuan yang tidak
    dapat dibandingkan -- pembaca yang menyandingkan "21" dengan "14" mengira
    keduanya sejenis, padahal yang satu banyaknya kejadian dan yang lain
    panjang waktu. Keduanya kini dinyatakan dalam hari, masing-masing dengan
    label yang menyebut peristiwanya sendiri ("sampai habis", "menyentuh titik
    pesan efektif"), dan titik pesan efektifnya ikut disebut berikut satuannya
    supaya angka 14 hari itu punya sasaran yang jelas.

    Banyaknya sisa pengambilan TIDAK hilang dari sistem; ia tetap terbit pada
    field `remaining_pickups` bagi pembaca API yang sudah memakainya. Yang
    berubah hanya kalimat yang dibaca manusia.
    """
    bagian: list[str] = []
    u = f" {unit}".rstrip()
    e = bulat(titik_efektif)

    # Inti kalimat waktu ditulis berhuruf kecil di kamus, karena ia bisa
    # berdiri sendiri ATAU menjadi anak kalimat setelah ketahanan stok.
    # Kapitalisasinya diputuskan di sini, sekali, bukan lewat dua salinan
    # kalimat yang sama di kamus.
    if sudah_tersentuh:
        inti = i18n.t("advice.touched", lang, e=e, u=u)
    elif not ada_pemakaian:
        inti = i18n.t("advice.no_usage", lang)
    elif hari_menuju is None:
        inti = i18n.t("advice.no_trend", lang)
    else:
        inti = i18n.t("advice.eta", lang, n=bulat(hari_menuju), e=e, u=u)

    if hari_habis is None:
        bagian.append(_kapital(inti))
    else:
        bagian.append(i18n.t("advice.cover", lang, n=bulat(hari_habis), inti=inti))

    kunci = action_status if action_status in _STATUS else STATUS_AMAN
    bagian.append(i18n.t(f"action.sentence.{kunci}", lang))

    if is_lumpy:
        bagian.append(i18n.t("warn.lumpy", lang))

    return " ".join(bagian)


def kalimat_cerita(hasil: dict, lang: str = i18n.BAHASA_BAWAAN) -> dict | None:
    """
    Halaman AI yang BERCERITA, bukan yang sekadar memajang angka.

    Kartu angka menjawab "berapa"; ia tidak pernah menjawab "jadi apa".
    Pembaca yang belum hafal arti titik pesan efektif melihat empat belas angka
    benar dan tetap tidak tahu harus berbuat apa. Tiga kalimat di bawah ini
    menyusun urutan yang sama seperti orang menjelaskannya secara lisan: apa
    yang terjadi selama ini, ke mana arahnya, lalu apa tindakannya.

    MEMBACA JAWABAN YANG SUDAH JADI, bukan keadaan dalam. Argumennya adalah
    respons /api/forecast yang sudah dirakit utuh, sehingga setiap angka dalam
    kalimat ini dijamin angka yang sama dengan yang tercetak di kartu -- bukan
    hasil pembacaan kedua atas sumber yang bisa bergeser.

    TIDAK ADA PERHITUNGAN DI SINI. Kalimat tindakan dan penutupnya bahkan tidak
    ditulis ulang: keduanya memakai `order_qty_reason` dan `confidence_note`
    yang sudah dipakai panel keputusan, supaya satu kesimpulan tidak pernah
    punya dua rumusan yang bisa berbeda bunyi setelah salah satunya diubah.

    Mengembalikan None bila histori belum cukup. Halaman sudah punya blok
    sendiri untuk keadaan itu, dan cerita yang dirakit di atas laju pemakaian
    yang belum ada hanya akan terdengar yakin tanpa dasar.
    """
    if not hasil.get("has_forecast"):
        return None

    hari_histori = (hasil.get("data_quality") or {}).get("history_days")
    if not hari_histori:
        return None

    u = f" {(hasil.get('item') or {}).get('unit_code') or ''}".rstrip()
    nama = (hasil.get("item") or {}).get("name") or ""
    gudang = (hasil.get("warehouse") or {}).get("name") or ""
    laju = hasil.get("average_daily_usage")

    if laju:
        situasi = i18n.t("cerita.situasi.pakai", lang, hari=hari_histori,
                         nama=nama, gudang=gudang,
                         laju=i18n.fmt_angka(laju, lang, desimal=1), u=u)
    else:
        situasi = i18n.t("cerita.situasi.diam", lang, hari=hari_histori,
                         nama=nama, gudang=gudang)

    umum = dict(stok=hasil["available_stock_int"], u=u,
                hari=hasil["forecast_days"], sisa=hasil["expected_stock_int"],
                e=hasil["effective_reorder_point_int"])
    if hasil.get("effective_reorder_point_reached"):
        arah = i18n.t("cerita.arah.tersentuh", lang, **umum)
    elif hasil.get("days_to_effective_rop_int") is None:
        arah = i18n.t("cerita.arah.tanpa_eta", lang, **umum)
    else:
        arah = i18n.t("cerita.arah.eta", lang,
                      n=hasil["days_to_effective_rop_int"], **umum)

    paragraf = [situasi, arah]
    if hasil.get("order_qty_reason"):
        paragraf.append(hasil["order_qty_reason"])

    # --- pendamaian dua lapisan ---
    #
    # Lapisan prakiraan dan lapisan keputusan menjawab pertanyaan yang berbeda,
    # dan pada barang tertentu jawabannya terdengar bertentangan: "belum perlu
    # pengadaan" berdampingan dengan stok yang diperkirakan habis sebelum
    # periode yang dipilih berakhir. Keduanya benar -- yang satu bicara tentang
    # HARI INI dengan patokan masa tunggu, yang lain tentang SELURUH PERIODE --
    # tetapi pembaca yang melihat "Stok aman" di atas grafik yang menyentuh nol
    # tidak punya cara menebak bahwa keduanya menjawab hal berbeda, dan yang
    # ia simpulkan adalah salah satunya keliru.
    #
    # Karena itu selisihnya disebut di sini, bukan dibiarkan disimpulkan
    # sendiri: kapan stok habis, berapa kurangnya, dan bahwa pemesanannya
    # memang perlu -- hanya belum hari ini.
    habis = hasil.get("days_until_stockout")
    kurang = hasil.get("projected_shortage_int") or 0
    if not hasil.get("recommended_order_qty") and (habis is not None or kurang > 0):
        u = f" {(hasil.get('item') or {}).get('unit_code') or ''}".rstrip()
        if habis is not None and kurang > 0:
            paragraf.append(i18n.t("cerita.beda_lapisan.habis_kurang", lang,
                                   hari=hasil["forecast_days"], n=bulat(habis),
                                   k=bulat(kurang), u=u))
        elif habis is not None:
            paragraf.append(i18n.t("cerita.beda_lapisan.habis", lang,
                                   hari=hasil["forecast_days"], n=bulat(habis)))
        else:
            paragraf.append(i18n.t("cerita.beda_lapisan.kurang", lang,
                                   hari=hasil["forecast_days"],
                                   k=bulat(kurang), u=u))

    return {
        "judul": hasil.get("order_qty_title") or hasil.get("action_status_label") or "",
        "paragraf": paragraf,
        "dasar": hasil.get("confidence_note") or "",
    }


def kalimat_keyakinan(*, tingkat: str, alasan: str, sebab_lemah: str,
                      subjek: str = "reorder",
                      lang: str = i18n.BAHASA_BAWAAN) -> str:
    """
    Catatan tingkat keyakinan untuk SELURUH angka turunan lapisan reorder.

    Mutu histori sudah lama dihitung (mutu_data) dan sudah lama dipakai, tetapi
    hanya sampai sebagai lencana kecil di samping satu angka. Padahal panjang
    histori itulah yang menghasilkan laju pemakaian, dan laju pemakaian itulah
    yang menghasilkan kebutuhan selama masa tunggu, titik pesan efektif, dan
    hari menuju titik pesan -- ketiganya mewarisi keterbatasan yang sama.
    Kalimat ini menyatakan pewarisan itu sekali, di tingkat halaman.

    TIDAK ADA AMBANG BARU. Tingkat dan alasannya datang apa adanya dari
    mutu_data(), penandaan lemahnya dari alasan_estimasi_lemah().

    `subjek` memilih DAFTAR ANGKA yang disebut namanya. Lapisan reorder dan
    lapisan prakiraan menghasilkan angka yang berbeda walau lahir dari histori
    yang sama, dan catatan yang menyebut daftar keliru akan menunjuk angka yang
    tidak ada pada jawaban tempatnya dicetak.
    """
    daftar = i18n.t(f"conf.subject.{subjek}", lang)
    if sebab_lemah:
        return i18n.t("conf.note.low", lang, subjek=daftar,
                      reason=alasan, sebab=sebab_lemah)
    return i18n.t("conf.note.ok", lang, subjek=daftar, reason=alasan)


def lapisan_keputusan(
    *,
    current_stock,
    reorder_point,
    minimum_stock,
    avg_daily_usage,
    available_stock=None,
    safety_stock=None,
    has_forecast: bool = True,
    keluar_harian: list,
    lead_time_days,
    forecast_days: int,
    unit_code: str = "",
    hari_histori: int | None = None,
    hari_aktif: int = 0,
    expected_usage=None,
    expected_stock=None,
    days_until_rop=None,
    days_until_stockout=None,
    history_start=None,
    history_end=None,
    as_of: str = "",
    periode_keputusan: int | None = None,
    kebutuhan_periode=None,
    kekurangan_periode=None,
    sisa_periode=None,
    lang: str = i18n.BAHASA_BAWAAN,
) -> dict:
    """
    Menyusun seluruh field turunan yang dipakai kartu keputusan.

    MODE PERIODE (opt-in lewat `periode_keputusan`). Bila diisi, status dan
    jumlah pesanan mengikuti periode itu: `kebutuhan_periode` adalah jumlah
    prakiraan sepanjang periode, `kekurangan_periode` dan `sisa_periode`
    selisihnya terhadap stok tersedia -- ketiganya angka yang sama dengan tiga
    kartu halaman Prakiraan. Tanpa itu seluruh perilaku lama berlaku apa
    adanya, dan itulah yang tetap dikunci tes kasus tepi.

    Dipanggil untuk SETIAP hasil prakiraan, termasuk yang datanya belum cukup:
    pada kasus itu laju pemakaiannya None, dan bucket-nya jujur berbunyi "—"
    alih-alih menghilang dari jawaban. Frontend jadi tidak perlu menangani dua
    bentuk jawaban yang berbeda.
    """
    stok = _angka(current_stock) or 0.0
    titik = _angka(reorder_point) or 0.0
    minimum = _angka(minimum_stock) or 0.0
    # Stok tersedia jadi basis keputusan reorder. Bila tidak dikirim, ia
    # mengikuti stok fisik -- maka pemanggil lama dan seluruh baris tanpa stok
    # tercadang menghasilkan angka yang sama persis seperti sebelumnya.
    tersedia = _angka(available_stock)
    if tersedia is None:
        tersedia = stok

    # --- lapisan reorder: patokannya lead time, bukan horizon prakiraan ---
    permintaan_lead = permintaan_selama_lead(avg_daily_usage, lead_time_days)
    titik_efektif = titik_pesan_efektif(titik, permintaan_lead, safety_stock)
    memadai = titik_pesan_memadai(titik, permintaan_lead, safety_stock)
    mode_periode = bool(periode_keputusan)
    if mode_periode:
        hari_keputusan = int(periode_keputusan)
        kebutuhan_horizon = _angka(kebutuhan_periode)
        sasaran_isi = target_pengadaan_periode(titik_efektif, kebutuhan_horizon,
                                               safety_stock)
    else:
        hari_keputusan = HORIZON_KEPUTUSAN
        sasaran_isi = target_pengadaan(titik_efektif, avg_daily_usage,
                                       safety_stock)
        kebutuhan_horizon = kebutuhan_horizon_keputusan(avg_daily_usage)
    hari_efektif = hari_menuju_titik_pesan_efektif(
        tersedia, titik_efektif, avg_daily_usage
    )
    # Ketahanan stok, dalam satuan yang sama dengan baris di atas: HARI.
    # Dipakai kalimat saran supaya kedua ukuran waktu pada satu kalimat dapat
    # dibandingkan langsung.
    hari_habis = hari_sampai_habis(tersedia, avg_daily_usage)
    # Status LEBIH DULU, lalu jumlahnya menyesuaikan. Urutannya terbalik dari
    # sebelumnya: invarian "status mendesak berarti ada yang dipesan" kini
    # dijaga oleh target_pengadaan(), bukan dengan menyuapkan jumlah ke dalam
    # status -- lihat catatan pada status_keputusan.
    punya_laju = has_forecast and _angka(avg_daily_usage) is not None
    if mode_periode:
        status = status_keputusan_periode(
            available_stock=tersedia,
            effective_reorder_point=titik_efektif,
            avg_daily_usage=avg_daily_usage,
            lead_time_days=lead_time_days,
            kekurangan_periode=kekurangan_periode,
        )
        qty_reorder = saran_qty_periode(
            status, titik_efektif, kebutuhan_horizon, safety_stock, tersedia,
            punya_forecast=punya_laju,
        )
    else:
        status = status_keputusan(
            available_stock=tersedia,
            effective_reorder_point=titik_efektif,
            avg_daily_usage=avg_daily_usage,
            lead_time_days=lead_time_days,
        )
        qty_reorder = saran_qty_reorder(
            titik_efektif, avg_daily_usage, safety_stock, tersedia,
            punya_forecast=punya_laju,
        )
    prioritas = prioritas_reorder(status, tersedia, safety_stock)
    # AMAN berarti nol, tanpa kecuali. saran_qty_reorder() sudah menjawab nol
    # untuk stok di atas ambang; penjepitan ini menutup satu-satunya celah yang
    # tersisa -- RISIKO_STOCKOUT karena stok nol pada barang yang tidak punya
    # laju pemakaian, yang jumlahnya belum dapat dihitung dan bukan nol.
    if status == STATUS_AMAN and qty_reorder is not None:
        qty_reorder = 0
    laju_ada = (_angka(avg_daily_usage) or 0.0) > 0
    tersentuh_efektif = tersedia <= titik_efektif

    # Field lama tetap dihitung atas stok FISIK dan titik pesan MASTER supaya
    # nilainya tidak bergeser bagi pembaca yang sudah ada.
    tersentuh = stok <= titik
    hari = hari_menuju_titik_pesan(stok, titik, avg_daily_usage)
    bucket = bucket_hari(hari, sudah_tersentuh=tersentuh, lang=lang)
    lumpy = deteksi_lumpy(keluar_harian, hari_histori)
    # Laju kosong PADAHAL ada pengeluaran berarti mesin prakiraan menolak
    # menghitung (histori belum cukup), bukan berarti barangnya diam.
    ada_pengeluaran = any((_angka(v) or 0.0) > 0 for v in (keluar_harian or []))
    frekuensi = label_frekuensi(
        avg_daily_usage, unit_code, hari_histori,
        belum_terhitung=(_angka(avg_daily_usage) is None and ada_pengeluaran),
        lang=lang,
    )
    n_ambil = sisa_pengambilan(stok, keluar_harian)

    judul_pengadaan, alasan_pengadaan = kalimat_pengadaan(
        qty=qty_reorder, titik_efektif=titik_efektif, sasaran=sasaran_isi,
        tersedia=tersedia, lead_time_demand=permintaan_lead, unit=unit_code,
        lang=lang,
    )

    if mode_periode and qty_reorder is not None and kebutuhan_horizon is not None:
        # Alasan jumlahnya menyebut periode; kalimat bawaan di atas menyebut
        # masa tunggu, yang pada mode ini bukan lagi dasar jumlahnya.
        u_ = f" {unit_code}".rstrip()
        alasan_pengadaan = i18n.t(
            "order.periode.some.body" if qty_reorder > 0
            else "order.periode.none.body",
            lang, t=bulat(tersedia), n=hari_keputusan,
            b=bulat(kebutuhan_horizon), s=bulat(sasaran_isi), u=u_)

    hari_hist = int(hari_histori or 0)
    tingkat, alasan = mutu_data(hari_hist, hari_aktif, lang=lang)
    sebab_lemah = alasan_estimasi_lemah(hari, hari_hist, tingkat, lang=lang)
    lemah = bool(sebab_lemah)

    detail = susun_detail_perhitungan(
        current_stock=stok, reorder_point=titik, minimum_stock=minimum,
        forecast_days=forecast_days, history_days=hari_hist,
        history_start=history_start, history_end=history_end,
        active_days=hari_aktif, avg_usage=avg_daily_usage,
        expected_usage=expected_usage, expected_stock=expected_stock,
        days_to_rop=hari, bucket=bucket,
        days_until_rop=days_until_rop, days_until_stockout=days_until_stockout,
        action_status=status, is_lumpy=lumpy,
        quality_level=tingkat, quality_reason=alasan,
        low_confidence=lemah, low_confidence_reason=sebab_lemah,
        as_of=as_of, unit_code=unit_code,
        usage_label=frekuensi["label"], usage_detail=frekuensi["detail"],
        lang=lang,
    )

    return {
        "quality_level": tingkat,
        "quality_reason": alasan,
        "low_confidence_estimate": lemah,
        "low_confidence_reason": sebab_lemah,
        # Mutu histori, dinaikkan menjadi keterangan tingkat HALAMAN: seluruh
        # angka turunan lapisan reorder lahir dari laju pemakaian, dan laju
        # pemakaian lahir dari histori yang mutunya dinilai di sini.
        "confidence_level": tingkat,
        "confidence_label": i18n.t(f"quality.{tingkat}", lang),
        "confidence_note": kalimat_keyakinan(
            tingkat=tingkat, alasan=alasan, sebab_lemah=sebab_lemah,
            subjek="reorder", lang=lang,
        ),
        # Catatan yang sama untuk pembaca lapisan PRAKIRAAN: historinya satu
        # dan sama, hanya angka yang disebut namanya berbeda.
        "confidence_note_forecast": kalimat_keyakinan(
            tingkat=tingkat, alasan=alasan, sebab_lemah=sebab_lemah,
            subjek="forecast", lang=lang,
        ),
        "calculation_detail": detail,
        "action_status": status,
        "action_status_label": i18n.t(f"status.label.{status}", lang),
        "action_text": i18n.t(f"status.action.{status}", lang),
        # Sumber utama waktu menuju titik pesan: kontinu, tidak dibatasi
        # panjang periode prakiraan.
        "days_to_rop": round(hari, 2) if hari is not None else None,
        "days_to_rop_bucket": bucket,
        "reorder_point_reached": tersentuh,
        # Menjawab pertanyaan yang berbeda dari days_to_rop: apakah titik pesan
        # tersentuh DI DALAM periode prakiraan. Dipisahkan sebagai boolean
        # supaya None pada days_until_reorder_point tidak perlu ditafsirkan --
        # dan tidak bisa lagi salah dibaca sebagai "tidak akan pernah".
        "reorder_point_within_horizon": days_until_rop is not None,

        # --- lapisan reorder ---
        # Seluruhnya berpatokan lead time dan stok tersedia; tidak satu pun
        # bergerak saat forecast_days diubah.
        "available_stock_used": round(tersedia, 3),
        "lead_time_demand": (round(permintaan_lead, 3)
                             if permintaan_lead is not None else None),
        "effective_reorder_point": round(titik_efektif, 3),
        "days_to_effective_rop": (round(hari_efektif, 2)
                                  if hari_efektif is not None else None),
        # Ketahanan stok sampai habis. TIDAK dibatasi horizon prakiraan --
        # bandingkan days_until_stockout, yang berhenti di ujung periode.
        "days_of_cover": (round(hari_habis, 2)
                          if hari_habis is not None else None),
        # Sampai berapa stok diisi saat pengadaan dilakukan (level "S").
        "order_up_to_level": (round(sasaran_isi, 3)
                              if sasaran_isi is not None else None),
        # Keterangan mutu master data, BUKAN tingkat kegawatan.
        "reorder_point_adequate": memadai,
        # None berarti belum dapat dihitung; nol berarti tidak perlu membeli.
        "recommended_order_qty": qty_reorder,
        "effective_reorder_point_reached": tersentuh_efektif,

        # --- versi tampilan: bilangan bulat, satu aturan pembulatan ---
        # Frontend merender field ini apa adanya. Nilai desimal di atas tetap
        # dikirim untuk penelusuran dan pembaca API lain.
        "available_stock_int": bulat(tersedia),
        "lead_time_demand_int": bulat(permintaan_lead),
        "effective_reorder_point_int": bulat(titik_efektif),
        "days_to_effective_rop_int": bulat(hari_efektif),
        "days_of_cover_int": bulat(hari_habis),
        "order_up_to_level_int": bulat(sasaran_isi),
        "safety_stock_int": bulat(safety_stock) or 0,
        # Lewat masa_tunggu() supaya angka yang DITAMPILKAN adalah angka yang
        # benar-benar DIPAKAI menghitung. Masa tunggu rusak berbunyi None --
        # sama seperti yang belum diisi -- bukan "-5 hari" di kartu.
        "lead_time_days_int": bulat(masa_tunggu(lead_time_days)),

        # --- kalimat siap render, memakai angka bulat yang sama ---
        "days_to_effective_rop_label": label_hari_menuju(
            hari_efektif, tersentuh_efektif, laju_ada, lang=lang
        ),
        "reorder_status_reason": (
            kalimat_status_periode(
                action_status=status, tersedia=tersedia,
                titik_efektif=titik_efektif, kebutuhan=kebutuhan_horizon,
                kekurangan=kekurangan_periode, hari=hari_keputusan,
                masa_tunggu_hari=lead_time_days, unit=unit_code, lang=lang,
            ) if mode_periode else
            kalimat_status_reorder(
                action_status=status, tersedia=tersedia,
                titik_efektif=titik_efektif, titik_master=titik,
                unit=unit_code, lang=lang,
            )
        ),
        "effective_reorder_point_basis": kalimat_titik_pesan_efektif(
            lead_time_demand=permintaan_lead, safety_stock=safety_stock,
            titik_efektif=titik_efektif, titik_master=titik, unit=unit_code,
            lang=lang,
        ),
        "order_qty_title": judul_pengadaan,
        "order_qty_reason": alasan_pengadaan,

        "usage_frequency_label": frekuensi["label"],
        "usage_frequency_detail": frekuensi["detail"],
        "usage_frequency": frekuensi,
        # ALIAS WARISAN. Dulu keluaran saran_qty() (`maximum_stock -
        # current_stock`); rumus itu sudah dihapus. Field-nya dipertahankan
        # karena ia bagian permukaan /api/forecast, dan kini membawa jumlah
        # yang sama dengan recommended_order_qty -- satu jawaban, bukan dua
        # yang berselisih. None dipetakan ke 0 supaya tipenya tetap bilangan
        # bagi pembaca lama; yang perlu membedakan "nol" dari "belum dapat
        # dihitung" membaca recommended_order_qty.
        "suggested_order_qty": qty_reorder or 0,

        # --- sumbu prioritas, terpisah dari status ---
        "priority": prioritas,
        "priority_label": i18n.t(f"priority.label.{prioritas}", lang),
        # Kebutuhan pada horizon KEPUTUSAN yang dipatok, bukan pada periode
        # yang dipilih di layar. Dasar sasaran pengisian; diterbitkan supaya
        # panel detail dapat menunjukkan asal jumlah pesanan tanpa menghitung
        # ulang di frontend.
        "decision_horizon_days": hari_keputusan,
        # "period" bila status dan jumlah mengikuti periode yang dipilih;
        # "lead_time" pada perilaku lama. Layar tidak menebaknya sendiri.
        "decision_basis": "period" if mode_periode else "lead_time",
        # Selisih kebutuhan periode terhadap stok tersedia, bilangan bulat yang
        # sama dengan kartu Prakiraan. None di luar mode periode dan pada
        # barang yang prakiraannya belum tersedia.
        "period_shortage_int": (bulat(kekurangan_periode)
                                if mode_periode else None),
        "period_surplus_int": (bulat(sisa_periode) if mode_periode else None),
        "decision_horizon_usage": (round(kebutuhan_horizon, 3)
                                   if kebutuhan_horizon is not None else None),
        "decision_horizon_usage_int": bulat(kebutuhan_horizon),
        "is_lumpy": lumpy,
        "stock_below_minimum": stok < minimum,
        "minimum_stock_int": bulat(minimum),
        "current_stock_int": bulat(stok),
        "reorder_point_int": bulat(titik),
        "advice_text": kalimat_saran(
            action_status=status,
            hari_habis=hari_habis,
            hari_menuju=hari_efektif,
            titik_efektif=titik_efektif,
            unit=unit_code,
            sudah_tersentuh=tersentuh_efektif,
            ada_pemakaian=laju_ada,
            is_lumpy=lumpy,
            lang=lang,
        ),
        # Tetap diterbitkan bagi pembaca API yang sudah memakainya; ia hanya
        # tidak lagi ikut menyusun kalimat saran.
        "remaining_pickups": n_ambil,
    }


# ==========================================================================
# Mutu data & keandalan estimasi
# ==========================================================================

# Ambang panjang histori. Nilai tetap dan eksplisit, bukan skor gabungan:
# "rendah karena histori hanya 8 hari" bisa ditindaklanjuti, sedangkan
# "skor 0,47" tidak memberi tahu apa yang harus diperbaiki.
MUTU_MIN_SEDANG = 14
MUTU_MIN_TINGGI = 30

# Di bawah rasio ini, histori memang panjang tetapi sebagian besar harinya
# kosong -- rata-rata hariannya bersandar pada sedikit kejadian, jadi mutunya
# diturunkan satu tingkat.
MUTU_RASIO_AKTIF = 0.30

# Estimasi yang menjangkau lebih jauh dari 1,5x panjang histori berarti
# meramalkan lebih lama daripada yang pernah diamati. Angkanya tetap disajikan,
# tetapi ditandai supaya tidak dibaca sebagai kepastian.
BATAS_EKSTRAPOLASI = 1.5

_URUT_MUTU = ["rendah", "sedang", "tinggi"]


def mutu_data(history_days: int, active_days: int,
              *, lang: str = i18n.BAHASA_BAWAAN) -> tuple[str, str]:
    """
    Tingkat mutu histori beserta ALASANNYA.

    Alasan ikut dikembalikan karena tingkat tanpa sebab tidak dapat
    ditindaklanjuti: pengguna yang membaca "rendah" perlu tahu apakah yang
    kurang itu panjang historinya atau seringnya barang bergerak.
    """
    hari = int(history_days or 0)
    aktif = int(active_days or 0)

    # TINGKATNYA tetap kata kunci Indonesia ("rendah"/"sedang"/"tinggi")
    # apa pun bahasanya: ia dipakai untuk MEMBANDINGKAN di beberapa tempat
    # (alasan_estimasi_lemah, urutan penurunan mutu), dan nilai yang ikut
    # berganti bahasa akan diam-diam membatalkan perbandingan itu. Yang
    # diterjemahkan hanya ALASANNYA -- dan tingkatnya sendiri baru
    # diterjemahkan saat hendak ditampilkan.
    if hari < MUTU_MIN_SEDANG:
        tingkat = "rendah"
        alasan = i18n.t("quality.reason.short", lang, n=hari)
    elif hari < MUTU_MIN_TINGGI:
        tingkat = "sedang"
        alasan = i18n.t("quality.reason.normal", lang, n=hari)
    else:
        tingkat = "tinggi"
        alasan = i18n.t("quality.reason.normal", lang, n=hari)

    rasio = (aktif / hari) if hari else 0.0
    if hari and rasio < MUTU_RASIO_AKTIF:
        turun = _URUT_MUTU.index(tingkat) - 1
        if turun >= 0:
            tingkat = _URUT_MUTU[turun]
            alasan = i18n.t("quality.reason.ratio", lang, a=aktif, b=hari)

    return tingkat, alasan


def estimasi_lemah(days_to_rop: float | None, history_days: int,
                   quality_level: str) -> bool:
    """Estimasi menjangkau terlalu jauh, atau bersandar pada histori tipis."""
    return bool(alasan_estimasi_lemah(days_to_rop, history_days, quality_level))


def alasan_estimasi_lemah(days_to_rop: float | None, history_days: int,
                          quality_level: str,
                          *, lang: str = i18n.BAHASA_BAWAAN) -> str:
    """
    Sebab estimasi ditandai lemah, atau string kosong bila tidak ditandai.

    Ditulis tanpa pecahan ("satu setengah kali", bukan "1,5×") karena kalimat
    ini ikut terbaca di layar Reorder, tempat seluruh angka bulat.

    Ada DUA pemicu yang berbeda, dan keduanya butuh kalimat sendiri: menjangkau
    lebih jauh daripada yang pernah diamati bukan hal yang sama dengan histori
    yang terlalu pendek. Satu kalimat untuk dua sebab akan menyampaikan hal
    yang tidak benar pada separuh kasusnya.
    """
    if (days_to_rop is not None and history_days
            and days_to_rop > history_days * BATAS_EKSTRAPOLASI):
        return i18n.t("weak.extrapolation", lang)
    if quality_level == "rendah":
        return i18n.t("weak.short_history", lang)
    return ""


# ==========================================================================
# Pemformatan angka
# ==========================================================================

def fmt(nilai, desimal: int = 2, kosong: str = "—",
        *, lang: str = i18n.BAHASA_BAWAAN) -> str:
    """
    Angka menurut kebiasaan bahasanya (id: 1.234,5 — en: 1,234.5).

    Nol di belakang koma dipangkas -- "156" lebih mudah dibaca daripada
    "156,00", dan bilangan bulat memang tidak punya bagian pecahan untuk
    ditunjukkan. Dilakukan di backend, bukan di frontend, supaya seluruh
    substitusi angka pada panel perhitungan memakai pembulatan yang persis
    sama dengan hasil yang ditampilkan di sebelahnya.
    """
    return i18n.fmt_angka(_angka(nilai), lang, desimal=desimal, kosong=kosong)


def fmt_int(nilai, kosong: str = "—", *, lang: str = i18n.BAHASA_BAWAAN) -> str:
    """
    Angka tanpa bagian pecahan sama sekali.

    Dipakai seluruh baris panel detail. Kuantitas gudang dan jumlah hari
    ditampilkan bulat di kartu; menampilkannya berdesimal di panel yang berada
    tepat di bawahnya hanya memunculkan dua angka berbeda untuk hal yang sama.
    """
    return fmt(bulat(nilai), desimal=0, kosong=kosong, lang=lang)


def _baris(label: str, value: str, raw=None, kind: str = "text", **tambahan) -> dict:
    b = {"label": label, "value": value, "kind": kind}
    if raw is not None:
        b["raw"] = raw
    b.update(tambahan)
    return b


def susun_detail_perhitungan(
    *,
    current_stock, reorder_point, minimum_stock,
    forecast_days: int, history_days: int, history_start, history_end,
    active_days: int, avg_usage, expected_usage, expected_stock,
    days_to_rop: float | None, bucket: str,
    days_until_rop, days_until_stockout,
    action_status: str, is_lumpy: bool,
    quality_level: str, quality_reason: str,
    low_confidence: bool, as_of: str, unit_code: str = "",
    low_confidence_reason: str = "",
    usage_label: str = "", usage_detail: str = "",
    lang: str = i18n.BAHASA_BAWAAN,
) -> dict:
    """
    Panel detail sebagai ALUR DERIVASI, bukan daftar properti.

    Empat seksi berurutan menjawab satu rantai: apa yang diketahui (masukan),
    apa yang dilakukan terhadapnya (perhitungan), apa artinya (kesimpulan),
    dan seberapa jauh itu boleh dipercaya (keandalan). Daftar datar yang lama
    memuat seluruh angka yang sama tetapi tidak pernah menunjukkan bahwa yang
    satu berasal dari yang lain.

    ANGKA BULAT, TANPA RUMUS BERSUBSTITUSI. Versi sebelumnya mencetak
    "(71 − 32) ÷ 4,64 = 8,4 hari" supaya dapat diperiksa dengan kalkulator di
    tempat. Begitu seluruh angka layar dibulatkan, substitusi itu justru
    menjadi sumber keraguan baru: "1 × 90 = 104" terbaca sebagai salah hitung,
    padahal yang terjadi hanya operan yang dibulatkan. Yang ditampilkan kini
    adalah masukan dan hasilnya sebagai baris terpisah -- nilai desimal
    penuhnya tetap ikut pada field `raw` setiap baris bagi siapa pun yang
    perlu menelusurinya.

    Seluruh string sudah jadi di sini. Frontend merender, tidak menyusun.
    """
    u = f" {unit_code}".rstrip()
    f_stok = fmt_int(current_stock, lang=lang)
    f_rop = fmt_int(reorder_point, lang=lang)
    f_min = fmt_int(minimum_stock, lang=lang)
    f_pakai = fmt_int(expected_usage, lang=lang)
    f_sisa = fmt_int(expected_stock, lang=lang)

    ada_laju = _angka(avg_usage) is not None and (_angka(avg_usage) or 0) > 0

    # --- Seksi 1: data masukan ---
    periode = ""
    if history_start and history_end:
        periode = f" ({history_start} – {history_end})"
    masukan = [
        _baris(i18n.t("detail.current_stock", lang), f"{f_stok}{u}",
               raw=_angka(current_stock)),
        # Disebut "master" secara eksplisit: ada titik pesan kedua -- yang
        # efektif, hasil perhitungan -- dan halaman Reorder menampilkannya
        # berdampingan. Dua angka berbeda dengan satu nama adalah cara paling
        # cepat membuat pembaca menyangka salah satunya keliru.
        _baris(i18n.t("detail.rop_master", lang),
               i18n.t("detail.rop_master.value", lang, rop=f_rop, min=f_min, u=u),
               raw=_angka(reorder_point)),
        _baris(i18n.t("detail.forecast_period", lang),
               i18n.t("days_to.days", lang, n=forecast_days), raw=forecast_days),
        _baris(i18n.t("detail.history", lang),
               i18n.t("detail.history.value", lang, n=history_days,
                      periode=periode, a=active_days),
               raw=history_days),
    ]

    # --- Seksi 2: perhitungan ---
    # Keterangan metode ditulis netral dan benar untuk KEDUA jalur perhitungan.
    # Menyebut satu nama metode akan keliru pada jalur yang lain, dan nama
    # mesinnya sendiri bukan sesuatu yang dapat ditindaklanjuti pengguna.
    #
    # Laju harian tidak dicetak sebagai pecahan. Pada barang yang keluar
    # seminggu sekali, "0,14 PCS/hari" dibulatkan menjadi "0 PCS/hari" -- salah
    # dan menyesatkan. Label frekuensi membalik pertanyaannya menjadi "±1 PCS
    # per 7 hari", yang tetap bulat sekaligus tetap benar.
    laju_teks = (f"{usage_label} {usage_detail}".strip()
                 if usage_label
                 else i18n.t("detail.avg_usage.raw", lang,
                             v=fmt_int(avg_usage, lang=lang), u=u))
    hitung = [
        _baris(i18n.t("detail.avg_usage", lang),
               i18n.t("detail.avg_usage.value", lang, teks=laju_teks),
               raw=_angka(avg_usage)),
        _baris(i18n.t("detail.expected_usage", lang, n=forecast_days),
               f"{f_pakai}{u}" if ada_laju else "—",
               raw=_angka(expected_usage)),
        _baris(i18n.t("detail.expected_stock", lang),
               f"{f_sisa}{u}" if ada_laju else "—",
               raw=_angka(expected_stock)),
        _baris(i18n.t("detail.days_to_rop", lang),
               i18n.t("detail.days_to_rop.value", lang,
                      n=fmt_int(days_to_rop, lang=lang), bucket=bucket)
               if ada_laju and days_to_rop is not None
               else i18n.t("detail.days_to_rop.none", lang, bucket=bucket),
               raw=days_to_rop),
    ]

    # --- Seksi 3: kesimpulan ---
    def _dalam_periode(n):
        return (i18n.t("detail.in_period", lang, n=n) if n
                else i18n.t("detail.not_in_period", lang))

    kesimpulan = [
        _baris(i18n.t("detail.hits_rop", lang), _dalam_periode(days_until_rop),
               raw=days_until_rop),
        _baris(i18n.t("detail.stockout", lang), _dalam_periode(days_until_stockout),
               raw=days_until_stockout),
        # Satu status saja. Field status lama tetap dikirim API untuk
        # kecocokan mundur, tetapi TIDAK ikut dirender -- dua status pada satu
        # panel akan saling meragukan.
        _baris(i18n.t("detail.status", lang),
               i18n.t(f"status.short.{action_status}", lang),
               kind="status", status=action_status),
    ]

    # --- Seksi 4: keandalan data ---
    keandalan = [
        _baris(i18n.t("detail.usage_pattern", lang),
               i18n.t("detail.usage_pattern.lumpy" if is_lumpy
                      else "detail.usage_pattern.regular", lang)),
        _baris(i18n.t("detail.quality", lang),
               i18n.t("detail.quality.value", lang,
                      level=i18n.t(f"quality.{quality_level}", lang).capitalize(),
                      reason=quality_reason)),
        _baris(i18n.t("detail.as_of", lang), str(as_of)),
    ]
    if low_confidence:
        keandalan.append(
            _baris(i18n.t("detail.note", lang), low_confidence_reason, kind="warning")
        )

    return {
        "sections": [
            {"key": "input",
             "title": i18n.t("detail.section.input", lang), "rows": masukan},
            {"key": "calculation",
             "title": i18n.t("detail.section.calculation", lang), "rows": hitung},
            {"key": "conclusion",
             "title": i18n.t("detail.section.conclusion", lang), "rows": kesimpulan},
            {"key": "reliability",
             "title": i18n.t("detail.section.reliability", lang), "rows": keandalan},
        ]
    }
