# -*- coding: utf-8 -*-
"""
Transfer Antar Gudang -- perhitungan murni, tanpa basis data.

PERTANYAAN YANG DIJAWAB MODUL INI, dan hanya itu:

    Gudang ini kekurangan stok. Sebelum membeli, adakah gudang lain yang
    barangnya sudah ada dan benar-benar berlebih -- dan gudang mana?

APA YANG BUKAN LINGKUPNYA, dan ini batas yang paling penting di berkas ini.
Modul ini TIDAK menghitung kebutuhan, TIDAK menghitung titik pesan, dan TIDAK
menghitung jumlah pesanan. Ketiganya sudah dijawab app/decision.py lewat jalur
yang sama dengan halaman Prakiraan dan Pemesanan Ulang, sudah tervalidasi
belasan berkas uji, dan MENGHITUNGNYA ULANG DI SINI berarti satu barang dapat
menyebut kekurangan yang berbeda di dua layar tanpa satu pun galat yang terbit.
Yang masuk ke sini adalah ANGKA JADI dari mesin itu; yang dikerjakan di sini
hanya memilih dari gudang mana kekurangan itu ditutup.

    kekurangan (dari decision.saran_qty_reorder)
        -> cari gudang yang punya barangnya
        -> buang yang stoknya tidak benar-benar berlebih
        -> pencocokan fuzzy bila nomor barangnya berbeda
        -> jarak + kecukupan + surplus + waktu tempuh
        -> peringkat
        -> alokasi, boleh menggabungkan beberapa gudang
        -> sisanya, bila ada, kembali menjadi urusan Pemesanan Ulang

FUZZY TIDAK PERNAH MENGGANTIKAN COCOK PASTI. Barang yang sama di dua gudang
memakai item_id yang sama, dan pasangan itu diambil lebih dulu, selalu, tanpa
menyentuh pencocokan nama sama sekali. Fuzzy hanya menjawab satu keadaan yang
memang ada di data nyata: satu barang fisik terlanjur terdaftar dua kali dengan
nomor berbeda -- hasil impor dari dua cabang, atau dua orang yang memasukkannya
pada hari yang berbeda. Karena tebakan seperti itu bisa salah, ia OPT-IN,
ambangnya tinggi, satuannya wajib sama, dan setiap barisnya membawa skor
kemiripannya sendiri supaya orang gudang dapat menolaknya sebelum barang
bergerak.

SELURUH KUANTITAS DI SINI BILANGAN BULAT. Bukan soal tampilan: yang dipindahkan
adalah barang fisik, dan "kirim 3,4 bearing" bukan perintah yang dapat
dijalankan siapa pun. Surplus DIBULATKAN KE BAWAH dan kebutuhan ke atas,
sehingga pembulatan tidak pernah menjanjikan barang yang tidak ada.
"""

from __future__ import annotations

import math
import re
import unicodedata
from difflib import SequenceMatcher

from . import i18n
from .config import (TRANSFER_BOBOT_JARAK, TRANSFER_BOBOT_KECUKUPAN,
                     TRANSFER_BOBOT_SURPLUS, TRANSFER_BOBOT_WAKTU,
                     TRANSFER_JARAK_MAKS_KM, TRANSFER_KEMIRIPAN_MIN,
                     TRANSFER_WAKTU_MAKS_HARI)

# --- keputusan akhir satu kebutuhan --------------------------------------
#
# Tiga kemungkinan, dan ketiganya harus dapat dibedakan oleh pembacanya.
# "Transfer sebagian" BUKAN kegagalan: memindahkan 8 dari 10 yang dibutuhkan
# tetap menutup delapan hari pemakaian, dan yang dibeli tinggal dua. Menyamakan
# ia dengan "pembelian" akan membuat orang pengadaan memesan sepuluh.
TRANSFER = "TRANSFER"
TRANSFER_SEBAGIAN = "TRANSFER_SEBAGIAN"
PEMBELIAN = "PEMBELIAN"

KEPUTUSAN = (TRANSFER, TRANSFER_SEBAGIAN, PEMBELIAN)

# --- alasan satu gudang TIDAK dipakai sebagai sumber ----------------------
#
# Disimpan sebagai kunci, bukan kalimat, supaya layar dapat menampilkan gudang
# yang ditolak beserta sebabnya. Daftar kandidat yang hanya memuat yang lolos
# tidak dapat menjawab pertanyaan yang paling sering muncul di depan layar:
# "gudang Jakarta kan punya barangnya, kenapa tidak dipakai?"
TOLAK_TIDAK_AMAN = "TIDAK_AMAN"        # gudang itu sendiri perlu reorder
TOLAK_TANPA_SURPLUS = "TANPA_SURPLUS"  # stoknya ada, tetapi tidak berlebih
TOLAK_NONAKTIF = "NONAKTIF"
TOLAK_SATUAN_BEDA = "SATUAN_BEDA"      # hanya mungkin pada jalur fuzzy
TOLAK_MIRIP_KURANG = "MIRIP_KURANG"

# --- dasar pencocokan ----------------------------------------------------
COCOK_SKU = "sku"      # item_id sama; pasti, tidak menebak apa pun
COCOK_FUZZY = "fuzzy"  # nomor barang berbeda, namanya sangat mirip

# Kata yang tidak membedakan satu barang dari barang lain dan karena itu
# menaikkan kemiripan tanpa alasan. "Filter Oli 10 Micron" dan "Filter Oli 40
# Micron" adalah dua barang berbeda; tanpa membuang "micron", keduanya terbaca
# 92% mirip semata-mata karena kata yang muncul di keduanya.
_KATA_UMUM = frozenset({
    "pcs", "pc", "unit", "set", "buah", "ea", "each",
    "type", "tipe", "model", "seri", "series", "no", "nomor",
})


# ==========================================================================
# Pencocokan nama barang
# ==========================================================================

def normalisasi_nama(nama: str | None) -> str:
    """
    Nama barang menjadi bentuk yang dapat dibandingkan.

    Tanda baca, huruf besar, dan urutan kata dibuang. Yang terakhir itu yang
    paling berarti pada data nyata: "Bearing Roller SKF" dan "Roller Bearing
    SKF" adalah barang yang sama yang diketik dua orang berbeda, dan
    perbandingan huruf-per-huruf membacanya sebagai 61% mirip.
    """
    if not nama:
        return ""
    teks = unicodedata.normalize("NFKD", str(nama)).encode("ascii", "ignore").decode()
    teks = re.sub(r"[^a-z0-9]+", " ", teks.lower())
    kata = [k for k in teks.split() if k and k not in _KATA_UMUM]
    return " ".join(sorted(kata))


def kemiripan(a: str | None, b: str | None) -> float:
    """
    Kemiripan dua nama barang, 0 sampai 1.

    SequenceMatcher dari pustaka standar, di atas bentuk yang sudah
    dinormalisasi. Dipilih justru karena ia sederhana dan dapat diperiksa:
    angka yang keluar dari sini menentukan apakah barang fisik dipindahkan
    antar kota, dan ukuran kemiripan yang tidak dapat dijelaskan kepada orang
    gudang tidak layak memegang keputusan itu.
    """
    na, nb = normalisasi_nama(a), normalisasi_nama(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def cocok_fuzzy(nama_a: str | None, nama_b: str | None,
                ambang: float = TRANSFER_KEMIRIPAN_MIN) -> tuple[bool, float]:
    """
    Apakah dua nama cukup mirip untuk dianggap barang yang sama.

    Mengembalikan keputusannya BESERTA skornya, keduanya sekaligus, supaya
    pemanggil tidak pernah harus menghitung ulang untuk menampilkan alasannya.
    """
    skor = kemiripan(nama_a, nama_b)
    return skor >= ambang, round(skor, 4)


# ==========================================================================
# Jarak antar gudang
# ==========================================================================

RADIUS_BUMI_KM = 6371.0088


def jarak_haversine(lat1, lon1, lat2, lon2) -> float | None:
    """
    Jarak garis lurus dua titik di permukaan bumi, dalam kilometer.

    Mengembalikan None bila ada satu saja koordinat yang kosong. Nol TIDAK
    dipakai sebagai pengganti: nol berarti "gudang yang sama persis letaknya",
    yaitu skor jarak tertinggi, dan gudang yang justru tidak diketahui
    letaknya akan memenangkan setiap peringkat.
    """
    try:
        titik = [float(v) for v in (lat1, lon1, lat2, lon2)]
    except (TypeError, ValueError):
        return None
    if any(v is None for v in (lat1, lon1, lat2, lon2)):
        return None

    p1, l1, p2, l2 = (math.radians(v) for v in titik)
    dp, dl = p2 - p1, l2 - l1
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * RADIUS_BUMI_KM * math.asin(math.sqrt(a)), 2)


def jarak_antar(*, jarak_tetap=None, asal: dict | None = None,
                tujuan: dict | None = None) -> tuple[float | None, str | None]:
    """
    Jarak yang dipakai memeringkat, beserta DARI MANA angkanya.

    Urutannya tetap: jarak yang ditetapkan tangan menang atas haversine, karena
    yang ditempuh truk adalah jalan, bukan garis lurus. Yang kedua dari koordinat
    gudang. Bila keduanya tidak ada, jawabannya None -- dan skor jarak jatuh ke
    nilai netral, bukan ke nilai terbaik.
    """
    if jarak_tetap is not None:
        try:
            return round(float(jarak_tetap), 2), "matrix"
        except (TypeError, ValueError):
            pass
    if asal and tujuan:
        km = jarak_haversine(asal.get("latitude"), asal.get("longitude"),
                             tujuan.get("latitude"), tujuan.get("longitude"))
        if km is not None:
            return km, "haversine"
    return None, None


# ==========================================================================
# Kelayakan dan surplus satu gudang sumber
# ==========================================================================

def bulat_bawah(v) -> int:
    """Kuantitas yang DIJANJIKAN ke gudang lain; dibulatkan ke bawah."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(n):
        return 0
    return int(math.floor(n))


def bulat_atas(v) -> int:
    """Kuantitas yang DIBUTUHKAN; dibulatkan ke atas supaya tidak kurang."""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(n):
        return 0
    return int(math.ceil(n))


def surplus_gudang(tersedia, titik_pesan_efektif) -> int:
    """
    Berapa yang benar-benar boleh diambil dari satu gudang.

    PATOKANNYA TITIK PESAN EFEKTIF, bukan stok fisik dan bukan pula safety
    stock sendirian. Titik pesan efektif adalah permintaan selama masa tunggu
    DITAMBAH cadangan penyangga (app/decision.titik_pesan_efektif) -- yaitu
    persis batas di mana gudang itu sendiri harus mulai memesan. Mengambil
    sampai batas itu memindahkan masalah, bukan menyelesaikannya: gudang asal
    berubah menjadi baris berikutnya di daftar Pemesanan Ulang, dan barangnya
    sudah terlanjur di jalan.

    Dibulatkan KE BAWAH. Surplus 2,9 berarti dua unit yang benar-benar dapat
    dinaikkan ke truk.
    """
    try:
        sisa = float(tersedia) - float(titik_pesan_efektif)
    except (TypeError, ValueError):
        return 0
    return max(0, bulat_bawah(sisa))


def kelayakan_sumber(*, status_aksi: str, aktif: bool, surplus: int,
                     satuan_sama: bool = True) -> str | None:
    """
    Alasan satu gudang TIDAK boleh menjadi sumber, atau None bila ia boleh.

    Urutan pemeriksaannya menentukan alasan mana yang tampil ketika lebih dari
    satu berlaku, dan urutan ini disengaja: yang paling menjelaskan lebih dulu.
    Gudang nonaktif yang kebetulan juga kekurangan stok harus berbunyi
    "nonaktif" -- itu yang dapat ditindaklanjuti.
    """
    if not aktif:
        return TOLAK_NONAKTIF
    if not satuan_sama:
        return TOLAK_SATUAN_BEDA
    # AMAN adalah satu-satunya status yang lolos, dan itu memang ketat.
    # PERLU_REORDER berarti gudang itu sendiri sudah menyentuh titik pesannya.
    if status_aksi != "AMAN":
        return TOLAK_TIDAK_AMAN
    if surplus <= 0:
        return TOLAK_TANPA_SURPLUS
    return None


# ==========================================================================
# Skor
# ==========================================================================

# Nilai komponen ketika keterangannya memang tidak ada. Setengah, bukan nol dan
# bukan satu: gudang yang jaraknya tidak diketahui tidak boleh dihukum seolah
# ia yang terjauh, dan tidak boleh pula menang atas gudang yang jaraknya
# diketahui dekat.
NETRAL = 0.5


def _skor_menurun(nilai: float | None, maks: float) -> float:
    """Semakin kecil semakin baik: 0 -> 1, maks ke atas -> 0."""
    if nilai is None:
        return NETRAL
    if maks <= 0:
        return NETRAL
    return max(0.0, 1.0 - min(1.0, float(nilai) / maks))


def skor_kandidat(*, kebutuhan: int, surplus: int, tersedia_sumber,
                  jarak_km: float | None = None,
                  lead_time_hari: float | None = None,
                  kemiripan_nama: float = 1.0) -> dict:
    """
    Skor satu gudang kandidat, 0 sampai 100, BESERTA rinciannya.

    Rincian ikut dikembalikan karena itulah yang membuat peringkat ini dapat
    dibantah. Skor tunggal "78" tidak memberi tahu apa pun tentang apa yang
    harus diperbaiki; empat komponen yang berdampingan menunjukkan bahwa
    gudang itu menang karena dekat meski stoknya pas-pasan, dan orang yang
    tahu jalannya sedang diperbaiki dapat memutuskan sebaliknya.

    Empat komponen, dan masing-masing menjawab pertanyaan yang berbeda:

        kecukupan   Cukupkah untuk menutup kebutuhan sekali kirim? Satu
                    kiriman selalu lebih murah dan lebih cepat daripada dua.
        surplus     Seberapa dalam kelebihannya? Gudang yang 70% stoknya
                    berlebih adalah donor yang jauh lebih aman daripada yang
                    hanya lebih satu unit di atas titik pesannya.
        jarak       Semakin dekat semakin murah dan semakin cepat.
        waktu       Waktu tempuh bila diketahui; ia BUKAN jarak, karena
                    penyeberangan dan izin muat tidak terbaca dari kilometer.

    Bobotnya di app/config.py dan dapat digeser lewat lingkungan tanpa
    menyentuh berkas ini.
    """
    kebutuhan = max(0, int(kebutuhan))
    surplus = max(0, int(surplus))

    cukup = 1.0 if kebutuhan <= 0 else min(1.0, surplus / kebutuhan)

    try:
        punya = float(tersedia_sumber or 0)
    except (TypeError, ValueError):
        punya = 0.0
    rasio_surplus = min(1.0, surplus / punya) if punya > 0 else 0.0

    skor_jarak = _skor_menurun(jarak_km, TRANSFER_JARAK_MAKS_KM)
    skor_waktu = _skor_menurun(lead_time_hari, TRANSFER_WAKTU_MAKS_HARI)

    total = (TRANSFER_BOBOT_KECUKUPAN * cukup
             + TRANSFER_BOBOT_SURPLUS * rasio_surplus
             + TRANSFER_BOBOT_JARAK * skor_jarak
             + TRANSFER_BOBOT_WAKTU * skor_waktu)

    # Kemiripan nama MENGALIKAN, bukan menambah komponen kelima. Ia bukan
    # keunggulan melainkan keraguan: kandidat yang hanya "mirip 90%" harus
    # kalah dari kandidat yang cocok pasti pada keadaan lain yang sama, dan
    # perkalian melakukan persis itu tanpa menyentuh arti keempat komponen
    # di atasnya. Cocok pasti bernilai 1,0 sehingga tidak berpengaruh apa pun.
    total *= max(0.0, min(1.0, float(kemiripan_nama)))

    return {
        "score": int(round(100 * total)),
        "components": {
            "sufficiency": round(cukup, 4),
            "surplus_ratio": round(rasio_surplus, 4),
            "distance": round(skor_jarak, 4),
            "lead_time": round(skor_waktu, 4),
            "name_similarity": round(float(kemiripan_nama), 4),
        },
        "weights": {
            "sufficiency": TRANSFER_BOBOT_KECUKUPAN,
            "surplus_ratio": TRANSFER_BOBOT_SURPLUS,
            "distance": TRANSFER_BOBOT_JARAK,
            "lead_time": TRANSFER_BOBOT_WAKTU,
        },
    }


def urutan_kandidat(kandidat: dict) -> tuple:
    """
    Kunci pengurutan kandidat yang lolos.

    Skor lebih dulu, lalu tiga pemutus seri yang seluruhnya deterministik.
    Tanpa pemutus seri, dua gudang berskor sama akan berganti urutan antar
    permintaan -- dan daftar rekomendasi yang berubah urutannya tanpa ada data
    yang berubah tidak dapat dipercaya siapa pun.
    """
    jarak = kandidat.get("distance_km")
    return (
        -int(kandidat.get("score") or 0),
        # None diletakkan di belakang yang diketahui jaraknya.
        (1, 0.0) if jarak is None else (0, float(jarak)),
        -int(kandidat.get("surplus") or 0),
        str(kandidat.get("from_warehouse_code") or ""),
    )


# ==========================================================================
# Alokasi
# ==========================================================================

def alokasi(kebutuhan: int, kandidat: list[dict]) -> list[dict]:
    """
    Membagi kebutuhan ke kandidat yang sudah terurut, rakus dari yang terbaik.

    BOLEH MENGGABUNGKAN BEBERAPA GUDANG. Kandidat teratas mengambil sebanyak
    yang ia mampu, sisanya turun ke kandidat berikutnya, dan seterusnya sampai
    kebutuhan tertutup atau kandidatnya habis.

    KENAPA RAKUS, BUKAN PENCARIAN KOMBINASI TERBAIK. Yang dioptimalkan bukan
    satu angka melainkan urutan prioritas yang sudah dinyatakan bobotnya, dan
    hasil rakus di atas urutan itu selalu dapat dijelaskan satu baris per
    gudang: "yang terbaik diambil dulu sampai habis". Pencarian kombinasi dapat
    menghasilkan total sedikit lebih baik dengan memakai gudang ketiga dan
    kelima -- susunan yang benar secara aritmetika dan mustahil dipertahankan
    di depan orang gudang yang bertanya kenapa gudang kedua dilewati.

    Kandidat bersurplus nol dilewati tanpa menghasilkan baris: dokumen transfer
    berjumlah nol bukan dokumen.
    """
    sisa = max(0, int(kebutuhan))
    hasil: list[dict] = []
    for k in kandidat:
        if sisa <= 0:
            break
        tersedia = max(0, int(k.get("surplus") or 0))
        if tersedia <= 0:
            continue
        qty = min(tersedia, sisa)
        hasil.append({**k, "transfer_qty": int(qty)})
        sisa -= qty
    return hasil


def rencana(*, kebutuhan, kandidat: list[dict], ditolak: list[dict] | None = None,
            lang: str = i18n.BAHASA_BAWAAN) -> dict:
    """
    Rencana pemenuhan satu kebutuhan: berapa dari transfer, berapa harus dibeli.

    `kebutuhan` datang JADI dari app/decision.py -- ia jumlah yang disarankan
    dipesan, dan tidak dihitung ulang di sini. None berarti mesin prakiraan
    belum dapat menghitungnya (histori belum cukup); pada keadaan itu tidak ada
    rencana transfer yang boleh disusun, karena tidak ada angka yang menyatakan
    berapa yang kurang.

    Kandidat yang MASUK lewat `kandidat` adalah yang sudah lolos kelayakan dan
    sudah berskor. `ditolak` dibawa ikut BUKAN untuk dialokasikan melainkan
    untuk membedakan dua keadaan yang sama-sama berujung pembelian dan sangat
    berbeda artinya: "barang ini hanya ada di gudang ini" versus "barang ini
    ada di mana-mana dan semuanya sedang menipis". Yang kedua adalah kabar
    bahwa seluruh jaringan sedang tipis, dan menyamakan kalimatnya dengan yang
    pertama menghilangkan satu-satunya tempat kabar itu pernah muncul.
    """
    if kebutuhan is None:
        return {
            "need_qty": None,
            "transfer_qty": 0,
            "purchase_qty": None,
            "decision": PEMBELIAN,
            "legs": [],
            "reason": i18n.t("tf.reason.no_need_figure", lang),
        }

    butuh = bulat_atas(kebutuhan)
    if butuh <= 0:
        return {
            "need_qty": 0,
            "transfer_qty": 0,
            "purchase_qty": 0,
            "decision": PEMBELIAN,
            "legs": [],
            "reason": i18n.t("tf.reason.no_shortage", lang),
        }

    terurut = sorted(kandidat, key=urutan_kandidat)
    legs = alokasi(butuh, terurut)
    dipindah = sum(int(l["transfer_qty"]) for l in legs)
    sisa = max(0, butuh - dipindah)

    if dipindah <= 0:
        keputusan = PEMBELIAN
    elif sisa > 0:
        keputusan = TRANSFER_SEBAGIAN
    else:
        keputusan = TRANSFER

    return {
        "need_qty": butuh,
        "transfer_qty": dipindah,
        # Sisa yang tetap harus dibeli. Nol berarti tidak ada pembelian sama
        # sekali; inilah angka yang membuat modul ini bernilai.
        "purchase_qty": sisa,
        "decision": keputusan,
        "legs": legs,
        "reason": kalimat_keputusan(
            keputusan=keputusan, butuh=butuh, dipindah=dipindah, sisa=sisa,
            n_gudang=len(legs),
            kandidat_ada=bool(kandidat) or bool(ditolak), lang=lang),
    }


# ==========================================================================
# Kalimat penjelas
# ==========================================================================

def kalimat_kandidat(*, kandidat: dict, kebutuhan: int,
                     lang: str = i18n.BAHASA_BAWAAN) -> str:
    """
    Kenapa gudang INI berada di urutan itu, dalam satu kalimat.

    Menyebut angka yang sama dengan kolom di sebelahnya, bukan meringkasnya
    menjadi kata sifat. "Surplus 40 unit, 12 km, cukup untuk seluruh kebutuhan"
    dapat diperiksa; "kandidat terbaik" tidak.
    """
    surplus = int(kandidat.get("surplus") or 0)
    jarak = kandidat.get("distance_km")
    hari = kandidat.get("lead_time_days")

    bagian = [i18n.t("tf.why.surplus", lang, n=i18n.fmt_angka(surplus, lang, 0))]

    if surplus >= kebutuhan > 0:
        bagian.append(i18n.t("tf.why.covers_all", lang))
    elif kebutuhan > 0:
        bagian.append(i18n.t("tf.why.covers_part", lang,
                             n=i18n.fmt_angka(min(surplus, kebutuhan), lang, 0),
                             butuh=i18n.fmt_angka(kebutuhan, lang, 0)))

    if jarak is not None:
        bagian.append(i18n.t("tf.why.distance", lang,
                             km=i18n.fmt_angka(jarak, lang, 0)))
    else:
        bagian.append(i18n.t("tf.why.distance_unknown", lang))

    if hari is not None:
        bagian.append(i18n.t("tf.why.lead", lang,
                             n=i18n.fmt_angka(hari, lang, 0)))

    if kandidat.get("match_type") == COCOK_FUZZY:
        bagian.append(i18n.t("tf.why.fuzzy", lang,
                             persen=i18n.fmt_angka(
                                 100 * float(kandidat.get("match_similarity") or 0),
                                 lang, 0)))

    return "; ".join(bagian) + "."


def kalimat_keputusan(*, keputusan: str, butuh: int, dipindah: int, sisa: int,
                      n_gudang: int, kandidat_ada: bool,
                      lang: str = i18n.BAHASA_BAWAAN) -> str:
    """
    Satu kalimat yang menyatakan apa yang harus terjadi berikutnya.

    Kasus "tidak ada kandidat sama sekali" dibedakan dari "ada kandidat tetapi
    tidak satu pun layak": yang pertama berarti barangnya memang hanya ada di
    satu gudang, yang kedua berarti barangnya ada di mana-mana dan semuanya
    sedang menipis. Keduanya berujung pada pembelian, tetapi yang kedua adalah
    kabar yang jauh lebih penting.
    """
    n = lambda v: i18n.fmt_angka(v, lang, 0)  # noqa: E731

    if keputusan == TRANSFER:
        return i18n.t("tf.reason.full", lang, qty=n(dipindah), gudang=n(n_gudang))
    if keputusan == TRANSFER_SEBAGIAN:
        return i18n.t("tf.reason.partial", lang, qty=n(dipindah),
                      gudang=n(n_gudang), sisa=n(sisa), butuh=n(butuh))
    if kandidat_ada:
        return i18n.t("tf.reason.none_eligible", lang, butuh=n(butuh))
    return i18n.t("tf.reason.no_candidate", lang, butuh=n(butuh))


def label_keputusan(keputusan: str, lang: str = i18n.BAHASA_BAWAAN) -> str:
    return i18n.t(f"tf.decision.{keputusan}", lang)


def label_penolakan(alasan: str | None, lang: str = i18n.BAHASA_BAWAAN) -> str | None:
    return i18n.t(f"tf.reject.{alasan}", lang) if alasan else None


# ==========================================================================
# Alur status dokumen transfer
# ==========================================================================
#
# Perpindahan yang SAH, dan hanya itu. Ditulis sebagai peta, bukan rangkaian
# if, karena inilah satu-satunya tempat aturan ini boleh hidup: dokumen yang
# melompat dari "diajukan" langsung ke "diterima" berarti stok bertambah di
# gudang tujuan tanpa pernah berkurang di gudang asal, dan selisihnya tidak
# akan pernah terlihat sebagai galat.

DRAFT = "draft"
APPROVED = "approved"
IN_TRANSIT = "in_transit"
COMPLETED = "completed"
CANCELLED = "cancelled"

STATUS = (DRAFT, APPROVED, IN_TRANSIT, COMPLETED, CANCELLED)

PERPINDAHAN: dict[str, tuple[str, ...]] = {
    DRAFT: (APPROVED, CANCELLED),
    APPROVED: (IN_TRANSIT, CANCELLED),
    # Barang sudah di jalan. Membatalkannya bukan pembatalan melainkan
    # transfer balik, dan itu dokumen tersendiri -- bukan satu tombol yang
    # diam-diam mengembalikan stok ke gudang asal tanpa jejak pergerakan.
    IN_TRANSIT: (COMPLETED,),
    COMPLETED: (),
    CANCELLED: (),
}


def boleh_pindah(dari: str, ke: str) -> bool:
    return ke in PERPINDAHAN.get(dari, ())


def label_status(status: str, lang: str = i18n.BAHASA_BAWAAN) -> str:
    return i18n.t(f"tf.status.{status}", lang)
