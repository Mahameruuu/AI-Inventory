# -*- coding: utf-8 -*-
"""Konfigurasi aplikasi -- dibaca dari .env di akar proyek."""

import os
from datetime import timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    # utf-8-sig membuang penanda BOM bila berkasnya ditulis editor Windows.
    # Tanpa itu, kunci pertama terbaca sebagai "﻿DATABASE_URL" dan
    # seluruh konfigurasi tampak kosong -- kegagalan yang sulit ditebak.
    for raw in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip().lstrip("﻿")
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

# Zona waktu transaksi dipakai saat menggabungkan received_date (tanggal saja)
# dengan jam saat permintaan diproses. Offset tetap, bukan nama zona, supaya
# tidak bergantung pada basis data tzdata sistem operasi -- WIB tidak mengenal
# daylight saving sehingga offset tetap selalu benar.
APP_TZ = timezone(timedelta(hours=float(os.getenv("APP_UTC_OFFSET_HOURS", "7"))))

# --- LLM (Ollama Cloud, atau Ollama lokal bila alamatnya diarahkan ke sana) ---
# Seluruhnya dari variabel lingkungan supaya alamat, model, dan batas waktu
# dapat diganti tanpa menyentuh kode.
#
# OLLAMA_API_KEY hanya dibaca di sini dan hanya dipakai sebagai header
# Authorization di app/llm.py. Nilainya TIDAK PERNAH masuk log, jawaban API,
# maupun berkas yang terlacak git -- .env sudah diabaikan .gitignore.
# Bila dikosongkan, aplikasi tetap jalan menghadap Ollama lokal tanpa
# autentikasi.
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "https://ollama.com").rstrip("/")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gpt-oss:120b")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120"))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.1"))

# Berapa banyak giliran percakapan lama yang ikut dikirim ke model. Dibatasi
# supaya konteks tidak membengkak dan biaya token tetap terkendali.
ASSISTANT_HISTORY_LIMIT = int(os.getenv("ASSISTANT_HISTORY_LIMIT", "12"))
# Batas putaran pemanggilan tool dalam satu pertanyaan.
ASSISTANT_MAX_TOOL_ROUNDS = int(os.getenv("ASSISTANT_MAX_TOOL_ROUNDS", "5"))
# Izin bagi asisten memanggil tool yang MENGUBAH stok. Dimatikan berarti
# asisten hanya bisa membaca.
ASSISTANT_ALLOW_WRITE = os.getenv("ASSISTANT_ALLOW_WRITE", "true").lower() == "true"

# --- Ambang minimum histori untuk prakiraan ---
# 14 hari agar prakiraan mencakup setidaknya dua siklus mingguan; di bawah itu
# pola akhir pekan belum terwakili. 3 hari dengan pengeluaran agar rata-rata
# tidak ditentukan satu kejadian tunggal.
# Dapat diturunkan saat pengujian, tetapi menurunkannya di lingkungan nyata
# berarti menerima prakiraan yang dasarnya tipis.
FORECAST_MIN_HISTORY_DAYS = int(os.getenv("FORECAST_MIN_HISTORY_DAYS", "14"))
FORECAST_MIN_OUTFLOW_DAYS = int(os.getenv("FORECAST_MIN_OUTFLOW_DAYS", "3"))

# Ambang "mendekati titik pemesanan ulang". Perkiraan sisa stok yang masih di
# atas titik pesan tetapi tidak lebih dari 25% di atasnya dianggap ATTENTION:
# masih aman hari ini, tetapi satu periode lagi akan menembusnya. Tanpa ambang
# ini, status akan melompat dari SAFE langsung ke CRITICAL tanpa peringatan.
FORECAST_ATTENTION_BAND = float(os.getenv("FORECAST_ATTENTION_BAND", "1.25"))

# --- Model prakiraan permintaan ---
# Berkas model XGBoost yang dipakai melayani permintaan. Dapat ditunjuk ke
# berkas lain lewat lingkungan tanpa menyentuh kode, misalnya saat menguji
# kandidat baru berdampingan dengan yang sedang berjalan.
FORECAST_MODEL_FILE = os.getenv(
    "FORECAST_MODEL_FILE", "production_tweedie.json")
FORECAST_MODEL_META = os.getenv(
    "FORECAST_MODEL_META", "production_tweedie_meta.json")

# Pakai salinan UBJSON (.ubj) di sebelah berkas model bila ada. Isinya model
# yang sama persis -- lihat _pilih_berkas_model() di app/ml/predict.py -- hanya
# cara membacanya yang berbeda, dan perbedaan itu bernilai 10 GB memori serta
# 25 detik waktu nyala. Disetel false untuk memaksa membaca JSON, misalnya saat
# membandingkan keduanya.
FORECAST_MODEL_PREFER_UBJ = os.getenv(
    "FORECAST_MODEL_PREFER_UBJ", "true").lower() == "true"

# Saklar darurat. Disetel false bila model bermasalah di lingkungan nyata;
# prakiraan langsung kembali memakai rata-rata bergerak berbobot tanpa perlu
# menghapus berkas model atau menurunkan versi.
FORECAST_USE_MODEL = os.getenv("FORECAST_USE_MODEL", "true").lower() == "true"

# Model dimuat di latar saat proses menyala; tanpa ini, permintaan pertama yang
# menanggung waktu bukanya.
FORECAST_MODEL_PRELOAD = os.getenv(
    "FORECAST_MODEL_PRELOAD", "true").lower() == "true"

# Direktori tempat berkas model berada. Kosong berarti backend/models/ di
# sebelah kode, seperti sebelumnya.
#
# KENAPA BISA DIPINDAH. Berkas modelnya 757 MB, dan isinya tidak berubah setiap
# kali kode berubah. Menaruhnya di dalam image berarti setiap build dan setiap
# pengiriman image memindahkan ulang berkas yang sama -- dan setiap versi image
# yang disimpan sebagai jalan pulang membawa salinannya sendiri. Ditunjuk ke
# direktori yang dipasang dari luar (docker -v), image mengecil beberapa giga
# dan mengganti model kandidat tidak lagi menuntut build ulang.
FORECAST_MODEL_DIR = os.getenv("FORECAST_MODEL_DIR", "").strip()

# --- Analisis Umur Pakai ---
#
# Dua angka, dan keduanya PUNYA SUMBER. Modul Analisis Umur Pakai sengaja
# tidak memiliki ambang bisnis lain: ambang tanpa sumber data adalah tebakan
# yang menyamar sebagai aturan.

# Berapa jam mesin benar-benar beroperasi tiap hari.
#
# Migrasi 029 menolak menyimpan umur pakai dalam satu satuan justru karena
# angka ini: sebagian komponen dinyatakan dalam jam operasi, sebagian dalam
# tahun kalender, dan selisih antara satu shift dan operasi terus-menerus
# lebih dari empat kali lipat. Menanamnya diam-diam di dalam kolom akan
# membuat setiap perbandingan salah tanpa satu pun galat yang menunjuk
# sebabnya.
#
# 16 = dua shift, dipilih pengguna pada 1 September 2026. Angka yang sama
# dipakai tools/histori_umur_pakai.py saat MEMBANGUN riwayat penggantiannya,
# dan berkas itu mengimpor dari sini -- satu sumber, bukan dua angka yang bisa
# berselisih setelah salah satunya diubah.
OPERATING_HOURS_PER_DAY = float(os.getenv("OPERATING_HOURS_PER_DAY", "16"))

# Lebar pita "masih sesuai spesifikasi" di sekitar umur pakai harapan.
#
# 0.15 bukan angka pilihan selera: riwayat penggantian perusahaan ini dibangun
# dengan ragam +-15% terhadap umur pakai spesifikasi
# (tools/histori_umur_pakai.py, `acak.uniform(0.85, 1.15)`). Itulah sebaran
# yang memang dinyatakan untuk data ini, sehingga itu pula yang memisahkan
# "wajar" dari "menyimpang".
#
# Bila kelak SME memberikan batas bawah/atas per komponen, angka ini digantikan
# oleh kolom masternya -- lihat lifetime.batas().
LIFETIME_TOLERANSI = float(os.getenv("LIFETIME_TOLERANSI", "0.15"))

# Sesedikit-sedikitnya jarak antar penggantian sebelum arah tren boleh disebut.
# Menamai arah atas dua atau tiga angka berarti menamai kebetulan.
LIFETIME_MIN_INTERVAL_TREN = int(os.getenv("LIFETIME_MIN_INTERVAL_TREN", "6"))

# --- Transfer Antar Gudang ------------------------------------------------
#
# BOBOT PERINGKAT KANDIDAT. Empat angka, dijumlahkan menjadi satu supaya skor
# selalu berada di 0-100 apa pun yang digeser. Kalau salah satu dinaikkan,
# turunkan yang lain -- app/transfer.py sengaja TIDAK menormalkan ulang, karena
# normalisasi diam-diam akan menyembunyikan setelan yang salah ketik.
#
# Kecukupan mendapat bobot terbesar karena satu kiriman selalu lebih murah dan
# lebih cepat daripada dua: gudang yang sanggup menutup seluruh kebutuhan
# sekali jalan menghemat satu dokumen, satu truk, dan satu penerimaan.
TRANSFER_BOBOT_KECUKUPAN = float(os.getenv("TRANSFER_BOBOT_KECUKUPAN", "0.40"))
TRANSFER_BOBOT_JARAK = float(os.getenv("TRANSFER_BOBOT_JARAK", "0.25"))
TRANSFER_BOBOT_SURPLUS = float(os.getenv("TRANSFER_BOBOT_SURPLUS", "0.20"))
TRANSFER_BOBOT_WAKTU = float(os.getenv("TRANSFER_BOBOT_WAKTU", "0.15"))

# Jarak yang sudah tidak perlu dibedakan lagi. Di atas angka ini skor jaraknya
# nol: selisih antara 1.100 km dan 1.400 km tidak mengubah keputusan siapa pun,
# sedangkan selisih 20 km dan 320 km mengubah segalanya. 1.000 km kira-kira
# Surabaya-Jakarta pulang pergi -- di luar itu transfer sudah bersaing langsung
# dengan pembelian.
TRANSFER_JARAK_MAKS_KM = float(os.getenv("TRANSFER_JARAK_MAKS_KM", "1000"))

# Hal yang sama untuk waktu tempuh. Dua minggu adalah masa tunggu pembelian
# yang khas pada data ini; transfer yang lebih lama dari itu tidak lagi lebih
# cepat daripada memesan baru.
TRANSFER_WAKTU_MAKS_HARI = float(os.getenv("TRANSFER_WAKTU_MAKS_HARI", "14"))

# Ambang kemiripan nama sebelum dua nomor barang berbeda boleh dianggap barang
# yang sama.
#
# TINGGI, DAN SENGAJA. Yang ditanggung kesalahan di sini bukan angka yang
# meleset melainkan barang fisik yang salah dinaikkan ke truk antar kota, lalu
# tercatat sebagai stok yang tidak pernah dibutuhkan gudang penerima. 0,88 di
# atas bentuk yang sudah dinormalisasi berarti praktis hanya perbedaan ejaan,
# tanda baca, dan urutan kata yang lolos -- "Gear Pump ABB 29805" dan "Gear
# Pump Bosch 93252" berada jauh di bawahnya, dan memang harus.
TRANSFER_KEMIRIPAN_MIN = float(os.getenv("TRANSFER_KEMIRIPAN_MIN", "0.88"))

# Pencocokan fuzzy MENYALA atau tidak secara bawaan.
#
# Mati. Perusahaan yang katalognya bersih tidak punya barang kembar sama
# sekali, dan bagi mereka fuzzy hanya menambah kemungkinan salah tanpa
# menambah satu pun kandidat. Yang katalognya memang memuat barang kembar
# menyalakannya sendiri -- lewat centang di layar per permintaan, atau lewat
# variabel ini bila itu keadaan tetap perusahaannya.
TRANSFER_FUZZY_BAWAAN = os.getenv("TRANSFER_FUZZY_BAWAAN", "false").lower() == "true"

# Sebanyak-banyaknya pasangan barang/gudang yang dihitung dalam satu permintaan
# daftar transfer. Sama alasannya dengan BATAS_BARIS pada Pemesanan Ulang: tiap
# pasangan menjalankan rantai prakiraan penuh.
TRANSFER_BATAS_BARIS = int(os.getenv("TRANSFER_BATAS_BARIS", "400"))

# Penyedia geometri jalan untuk peta transfer (app/jalur.py). Bawaannya server
# demo publik OSRM: cukup untuk beberapa pasang gudang karena hasilnya
# disimpan, tetapi bukan layanan produksi. Arahkan ke OSRM milik sendiri bila
# jumlah pasangan gudang bertambah.
OSRM_URL = os.getenv("OSRM_URL", "https://router.project-osrm.org").rstrip("/")
OSRM_TIMEOUT_DETIK = float(os.getenv("OSRM_TIMEOUT_DETIK", "8"))

# Kota perantara untuk jalur alternatif (app/jalur.py). OSRM sering hanya
# memberi SATU jalan antara dua kota, jadi koridor lain (mis. jalur selatan
# Jawa) dicari dengan memaksa rute lewat kota di sisi lain garis lurus. Daftar
# ini sengaja pendek dan hanya Jawa; kota di luar jangkauan tidak dipakai
# karena tak ada yang lolos saringan sisi/pengalihan. Tambahkan sendiri bila
# gudang berada di pulau lain.
JALUR_PERANTARA = [
    ("Bandung", -6.9175, 107.6191),
    ("Cirebon", -6.7320, 108.5523),
    ("Tasikmalaya", -7.3274, 108.2207),
    ("Purwokerto", -7.4242, 109.2396),
    ("Semarang", -6.9667, 110.4167),
    ("Yogyakarta", -7.7956, 110.3695),
    ("Solo", -7.5666, 110.8167),
    ("Madiun", -7.6298, 111.5239),
    ("Kediri", -7.8480, 112.0178),
    ("Malang", -7.9666, 112.6326),
    ("Bojonegoro", -7.1502, 111.8816),
]
JALUR_MAKS_PILIHAN = int(os.getenv("JALUR_MAKS_PILIHAN", "4"))

# Asumsi biaya kiriman untuk rekomendasi jalur (app/jalur.py: analisis). SEMUA
# ANGKA INI ASUMSI, bukan data: tidak satu pun datang dari sistem lain. Isilah
# dengan angka armada sendiri; peta menampilkan asumsi yang dipakai di samping
# hasilnya supaya tak seorang pun mengira itu tarif resmi.
#
# Bawaannya truk box CDD (tol Golongan II).
#   TRUK_KM_PER_LITER   konsumsi solar, km per liter (muatan rata-rata)
#   HARGA_SOLAR_PER_LITER  rupiah per liter; ISI DENGAN HARGA YANG BERLAKU
#   TARIF_TOL_PER_KM    rata-rata rupiah per km tol. Tarif tol sebenarnya per
#                       ruas dan per gerbang; ini hanya rata-rata pendekatan.
#   BIAYA_OPERASIONAL_PER_JAM  sopir, kernet, penyusutan: nilai satu jam tempuh
TRUK_GOLONGAN_TOL = os.getenv("TRUK_GOLONGAN_TOL", "II")
TRUK_KM_PER_LITER = float(os.getenv("TRUK_KM_PER_LITER", "7"))
HARGA_SOLAR_PER_LITER = float(os.getenv("HARGA_SOLAR_PER_LITER", "13000"))
TARIF_TOL_PER_KM = float(os.getenv("TARIF_TOL_PER_KM", "1600"))
BIAYA_OPERASIONAL_PER_JAM = float(os.getenv("BIAYA_OPERASIONAL_PER_JAM", "75000"))

# Level log aplikasi (namespace "inventory"). INFO menampilkan tool yang
# dipanggil asisten beserta waktu penyusunan jawaban -- keterangan yang tidak
# lagi ditampilkan di antarmuka, sehingga log adalah satu-satunya tempat
# menelusurinya. Setel WARNING untuk membuatnya senyap.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Dashboard sering dibuka lewat alamat jaringan saat demo, bukan localhost.
CORS_ORIGIN_REGEX = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"^https?://(localhost|127\.0\.0\.1|"
    r"10\.\d+\.\d+\.\d+|"
    r"172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|"
    r"192\.168\.\d+\.\d+)(:\d+)?$",
)

# --- Autentikasi dan penyewa ----------------------------------------------
# Kunci penanda tangan token. TIDAK ADA nilai bawaan yang aman: kunci bawaan
# yang ikut terlacak git berarti siapa pun yang pernah melihat kode ini dapat
# menerbitkan token atas nama pengguna mana pun. Aplikasi menolak menyala bila
# kunci ini kosong -- lihat app/main.py.
#
# Membuat kunci baru:
#     python -c "import secrets; print(secrets.token_urlsafe(48))"
#
# Mengganti kunci ini membuat seluruh token yang sudah terbit tidak berlaku;
# semua pengguna harus masuk kembali. Itu memang alat yang tepat saat kunci
# diduga bocor.
JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
JWT_ALGORITHM = "HS256"

# Umur token akses. Token bersifat mandiri sehingga tidak bisa ditarik kembali
# satu per satu; umurnya yang membatasi kerugian bila ia sempat bocor. 12 jam
# dipilih supaya satu hari kerja tidak terputus di tengah, tetapi token yang
# tertinggal di komputer bersama tidak berlaku keesokan harinya.
JWT_TTL_HOURS = float(os.getenv("JWT_TTL_HOURS", "12"))

# Penjaga: menolak menyala bila aplikasi tersambung sebagai superuser
# PostgreSQL. Superuser dibebaskan dari SELURUH Row Level Security tanpa cara
# mematikannya, sehingga seluruh pemisahan penyewa pada migrasi 028 menjadi
# hiasan tanpa ada satu pun galat yang terbit. Ini persis jenis kesalahan
# konfigurasi yang tidak mungkin ditemukan dengan menguji aplikasi, jadi
# pemeriksaannya dilakukan saat menyala.
#
# Disetel false HANYA untuk pengembangan lokal, dan berarti menerima bahwa
# pemisahan penyewa sedang tidak aktif.
DB_TOLAK_SUPERUSER = os.getenv("DB_TOLAK_SUPERUSER", "true").lower() == "true"
