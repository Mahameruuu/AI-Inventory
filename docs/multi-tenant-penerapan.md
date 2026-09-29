# Penerapan fondasi banyak-penyewa

Berkas ini berisi langkah yang **harus dijalankan operator**, karena masing-masing
menuntut keputusan atau rahasia yang tidak boleh tinggal di dalam kode.

Basis data produksi **belum disentuh**. Seluruh migrasi baru sudah diuji pada
basis data sekali pakai, dan lulus.

---

## Status: SUDAH DITERAPKAN pada 2026-08-28

Langkah 1–6 di bawah **sudah dijalankan** pada basis data produksi
(`172.16.100.41:5434/inventory`) dan kedua kontainer sudah ditukar ke image
baru. Isinya tetap ditulis lengkap sebagai catatan apa yang dikerjakan, dan
karena langkah yang sama berlaku bagi lingkungan lain.

Jalan pulang bila diperlukan:

```bash
# cadangan sebelum migrasi
pg_restore -d "$ADMIN_DATABASE_URL" --clean \
    ~/backup-inventory/inventory-sebelum-multitenant-20260828-1604.dump

# image yang berjalan sebelumnya
docker rm -f inventory-ai-backend inventory-ai-frontend
docker tag inventory-ai-backend:sebelum-multitenant  inventory-ai-backend:latest
docker tag inventory-ai-frontend:sebelum-multitenant inventory-ai-frontend:latest
```

Kredensial dipisah pada `.env`: `DATABASE_URL` menunjuk role aplikasi
`inventory_app` (non-superuser, tunduk RLS), `ADMIN_DATABASE_URL` menunjuk
`inventory_admin` dan dipakai hanya untuk migrasi serta basis data uji.
Kredensial admin **tidak ikut** masuk kontainer.

---

## Apa yang berubah

| Lapisan | Perubahan |
|---|---|
| Basis data | 5 migrasi baru (024–028): `companies`, `users`, `company_id` pada 20 tabel, keunikan per perusahaan, Row Level Security |
| Backend | `/api/auth/*` dan `/api/users/*`; seluruh router data menuntut token |
| Frontend | Halaman `/login`, gerbang sesi, menu akun, halaman `/settings/users` |
| Demo | Penyewa demo terpisah, tombol **Simulasikan Penjualan** dan **Isi Ulang** di bilah atas |
| Data induk | CRUD barang, kategori, satuan, gudang, supplier; impor CSV/Excel |
| Transaksi | Transfer antar gudang dan penyesuaian stok (tabelnya sudah ada sejak migrasi 010–013) |

Tidak ada satu pun dari 12 router data yang query-nya diubah. Penyaringan
penyewa dikerjakan basis data, bukan disalin ke setiap `SELECT`.

---

## Langkah 1 — Cadangkan basis data

Migrasi 026 dan 027 mengubah kolom dan constraint pada tabel berisi 3,1 juta
baris. Migrasi berjalan dalam satu transaksi, tetapi cadangan tetap syarat.

```bash
pg_dump "$DATABASE_URL" -Fc -f inventory-sebelum-multitenant.dump
```

## Langkah 2 — Jalankan migrasi

Untuk basis data yang **sudah berisi data** (sudah punya migrasi 001–023):

```bash
psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrate_multitenant.sql
```

`database/migrate.sql` **tidak boleh dipakai di sini**: berkas itu membangun
basis data dari nol, dan migrasi 001–023 memakai `CREATE TABLE` polos sehingga
ia berhenti pada pernyataan pertama dengan `relation "categories" already
exists`. Ia benar untuk basis data baru dan tidak pernah benar untuk yang sudah
jalan. `migrate_multitenant.sql` menjalankan 024–028 saja, dalam satu transaksi.

Waktu nyata pada basis data 1,3 GB berisi 3,1 juta baris `stock_movements`:
**4 detik**. Penambahan kolom tidak menulis ulang tabel, dan itulah yang
membuatnya secepat ini.

Seluruh data yang ada menjadi milik perusahaan `id = 1` bernama
"Perusahaan Utama". Ganti namanya bila perlu:

```sql
UPDATE companies SET name = 'PT Nama Sebenarnya', slug = 'nama-sebenarnya' WHERE id = 1;
```

Perkiraan waktu: penambahan kolom cepat (tidak menulis ulang tabel), pembangunan
indeks pada `stock_movements` dan `stock_issue_items` memakan waktu paling lama.

## Langkah 3 — Aktifkan role aplikasi

**Ini langkah yang paling mudah terlewat dan paling mahal bila terlewat.**

PostgreSQL membebaskan superuser dari **seluruh** Row Level Security, tanpa cara
mematikannya. `inventory_admin` adalah superuser. Selama backend menyambung
sebagai dia, seluruh pemisahan penyewa **tidak aktif** — setiap halaman tetap
tampil normal, setiap query tetap berhasil, dan setiap penyewa melihat data
seluruh penyewa.

Migrasi 028 sudah membuat role `inventory_app` tanpa hak masuk. Berikan kata
sandi kuat:

```sql
ALTER ROLE inventory_app LOGIN PASSWORD '<kata sandi kuat>';
```

Lalu arahkan `DATABASE_URL` pada `.env` ke role tersebut:

```
DATABASE_URL=postgresql://inventory_app:<kata sandi>@172.16.100.41:5434/inventory
```

`inventory_admin` tetap dipakai untuk menjalankan migrasi berikutnya, tidak untuk
melayani permintaan.

Backend **menolak menyala** bila mendapati dirinya tersambung sebagai superuser,
jadi langkah ini tidak mungkin terlewat diam-diam.

## Langkah 4 — Kunci token

`JWT_SECRET` sudah dibuat acak dan ditulis ke `.env`. Bila server produksi
memakai `.env` yang berbeda, buat kunci sendiri di sana:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Mengganti kunci membatalkan seluruh token yang sudah terbit — itu memang alat
yang tepat bila kunci diduga bocor.

## Langkah 5 — Bangun ulang image

Menjalankan ulang kontainer **tidak** memuat kode baru; image harus dibangun
ulang. Ada dependensi Python baru (`PyJWT`, `bcrypt`, `email-validator`,
`python-multipart`, `openpyxl`), jadi langkah ini wajib, bukan opsional.

Pakai skripnya, jangan mengetik `docker run` sendiri:

```bash
scripts/deploy.sh              # bangun image lalu tukar kedua kontainer
scripts/deploy.sh --restart    # tukar kontainer saja, tanpa membangun ulang
```

Skrip itu menanggung tiga hal yang tidak akan terlihat bila terlupa: memasang
direktori model, menyaring keluar `ADMIN_DATABASE_URL` supaya kredensial
superuser tidak ikut masuk kontainer, dan menolak berjalan bila `DATABASE_URL`
masih menunjuk `inventory_admin`. Ia juga memberi tag `rollback-<tanggal>` pada
image yang sedang berjalan sebelum menimpanya, dan menunggu `/api/health`
menjawab sebelum menyatakan berhasil.

## Langkah 6 — Buat pengguna pertama

Data lama sudah menjadi milik perusahaan 1, tetapi perusahaan itu belum punya
seorang pun yang dapat masuk. Halaman `/login` → tab **Daftar** hanya membuat
perusahaan **baru**, jadi pengguna untuk perusahaan 1 dibuat lewat SQL:

```bash
# 1. Buat hash kata sandi
python -c "import bcrypt; print(bcrypt.hashpw(b'<kata sandi>', bcrypt.gensalt()).decode())"
```

```sql
-- 2. Pasang sebagai owner perusahaan 1
INSERT INTO users (company_id, email, full_name, password_hash, role)
VALUES (1, 'admin@perusahaan.co.id', 'Nama Admin', '<hash dari langkah 1>', 'owner');
```

Sesudahnya, pengguna berikutnya ditambahkan lewat layar **Administrasi →
Pengguna**, tidak perlu SQL lagi.

---

## Langkah 7 — Siapkan penyewa demo (opsional, tapi ini yang dipakai tim penjualan)

Demo hidup di **perusahaan terpisah**, bukan di perusahaan pelanggan. Itu yang
membuat tombol "Isi Ulang" aman: yang dihapusnya hanya isi penyewa demo, dan
backend menolak menjalankannya pada perusahaan mana pun yang tidak bertanda
demo.

```bash
python -m app.jobs.buat_demo \
    --email demo@inventoryai.id \
    --sandi 'Demo2026Inventory' \
    --nama "Demo Inventory AI"
```

**Sudah dijalankan pada 2026-08-28.** Akun demonya:

| | |
|---|---|
| Email | `demo@inventoryai.id` |
| Kata sandi | `Demo2026Inventory` |

Kredensial ini sengaja sederhana dan boleh disebut di depan calon pelanggan —
isinya data bangkitan, dan tidak ada jalan dari penyewa demo ke data penyewa
mana pun.

Perintah ini berjalan dengan `DATABASE_URL` yang sama seperti aplikasi — tidak
menuntut kredensial admin basis data. Aman dijalankan ulang: bila emailnya sudah
terdaftar, perusahaannya dipakai kembali dan isinya disegarkan.

Masuk dengan akun itu, dan dua tombol muncul di bilah atas:

- **Simulasikan Penjualan** — mencatat penjualan hari ini pada seluruh gudang.
  Transaksinya sungguhan, jadi stok turun, daftar stok menipis bertambah,
  prakiraan bergeser, dan rekomendasi pemesanan menyesuaikan diri. Seluruh angka
  di layar ikut ditarik ulang tanpa memuat ulang halaman.
- **Isi Ulang** (ikon putar) — mengosongkan demo dan membangkitkannya kembali.
  Hanya untuk owner dan admin, dan selalu meminta konfirmasi.

Isi yang dibangkitkan: 36 barang di 6 kategori, 3 gudang, 4 supplier, dan 90
hari riwayat penerimaan serta pengeluaran dengan pola mingguan (Sabtu setengah
hari, Minggu nyaris berhenti). Angkanya sama setiap kali — benih acaknya tetap,
supaya yang mendemokan tahu apa yang akan muncul sebelum menekan tombolnya.

Sekitar seperempat baris stok berada di bawah titik pesan. Itu disetel, bukan
kebetulan: tanpa ada yang menipis, halaman Stok Menipis dan Pemesanan Ulang
kosong; bila hampir semuanya menipis, gudangnya terbaca kacau **dan** tombol
simulasi tidak menggerakkan apa pun karena semua sudah merah sejak awal.

**Pengguna demo tidak boleh memakai email yang sama dengan pengguna sungguhan.**
Email unik secara global, dan `buat_demo` menolak mengisi perusahaan yang tidak
bertanda demo — tetapi lebih baik tidak sampai ke sana.

---

## Mengisi data pelanggan baru

Tidak ada langkah penerapan tambahan untuk bagian ini — tidak ada migrasi baru,
dan endpoint-nya ikut menyala begitu image dibangun ulang. Yang berikut ini
urutan kerja bagi orang yang mengisi data, bukan bagi operator.

**Menu Data Induk hanya muncul untuk owner dan admin.** Itu berlaku di navigasi
maupun di backend: staf dan peninjau menerima 403 sekalipun membuka alamatnya
langsung. Alasannya bukan kehati-hatian umum — satu SKU yang salah atau satu
satuan yang diubah artinya menjalar ke setiap transaksi, laporan, dan prakiraan
yang menyebutnya, tanpa satu pun layar menampilkan galat.

Urutannya mengikuti ketergantungan datanya:

1. **Kategori** dan **Satuan** — dibutuhkan setiap barang.
2. **Gudang** — setiap saldo stok melekat pada satu gudang.
3. **Supplier** — waktu tunggu di sini dipakai perhitungan pemesanan ulang.
4. **Barang**, satu per satu lewat formulir, atau sekaligus lewat **Impor Data**.

### Impor CSV/Excel

Alurnya tiga langkah, dan langkah tengahnya tidak bisa dilewati tanpa sadar:
unduh berkas contoh, pilih berkas, **periksa dulu**. Tombol "Impor Sekarang"
baru muncul setelah pemeriksaan selesai dan melaporkan berapa baris akan
dibuat, berapa diperbarui, dan baris ke berapa yang bermasalah beserta
alasannya.

Yang diurus sendiri oleh pembacanya, karena berkas yang dikirim orang tidak
pernah serapi contoh:

- Judul kolom berbahasa Indonesia atau Inggris (`SKU`/`Kode Barang`,
  `Harga`/`Unit Price`, dan seterusnya); kolom asing diabaikan, tidak membuat
  berkasnya ditolak.
- Pemisah koma, titik koma, atau tab — Excel berbahasa Indonesia menyimpan CSV
  dengan titik koma.
- Angka bergaya Indonesia maupun Inggris: `1.250.000`, `1250000,50`,
  `Rp 1.250.000`, `1,250,000.50`.

Dua perilaku yang perlu diketahui sebelum dipakai:

- **Baris yang sah tetap masuk meski ada yang bermasalah.** Menolak seluruh
  berkas karena tiga baris cacat memaksa orang mengunggah ulang delapan ratus
  baris berkali-kali. Mengunggah ulang berkas yang sama tidak menggandakan apa
  pun — barang dicocokkan berdasarkan SKU.
- **Sel yang dikosongkan tidak menghapus nilai yang sudah ada.** Berkas impor
  ulang biasanya hanya mengisi kolom yang ingin diubah; memperlakukan sel
  kosong sebagai "kosongkan" akan menghapus titik pesan seluruh katalog pada
  unggahan yang dimaksudkan untuk memperbaiki harga saja.

Kategori dan satuan yang belum terdaftar dilaporkan sebagai **kesalahan**, bukan
dibuat diam-diam. Centang "Buat kategori dan satuan yang belum ada" untuk
membuatnya sekaligus — berguna saat mengisi data pertama kali, dan sengaja tidak
menjadi bawaan supaya "Sparepart Mesn" tidak menjadi kategori keempat yang
tampak sah selamanya.

### Menghapus vs menonaktifkan

Master data yang sudah dirujuk transaksi **tidak bisa dihapus** — menghapusnya
berarti riwayat transaksi kehilangan artinya. Sistem menolaknya dengan kalimat
yang menyebut berapa data yang merujuknya, dan menyarankan menonaktifkan.

Data yang belum tersentuh apa pun **boleh** dihapus. Itu bukan kemewahan: saat
mengisi data awal, salah ketik satu baris lalu terpaksa hidup dengan "SATAUN"
selamanya di daftar pilihan adalah pengalaman yang membuat orang berhenti
mengisi.

### Transfer dan penyesuaian stok

Keduanya ada di menu **Transaksi**, terbuka untuk staf ke atas.

- **Transfer** memindahkan stok antar gudang. Keluar dan masuk ditulis dalam
  satu transaksi: tidak pernah ada saat di mana barangnya tidak berada di gudang
  mana pun.
- **Penyesuaian** menyelaraskan catatan dengan hasil pencacahan fisik. Yang
  dimasukkan adalah **hasil hitungan**, bukan selisihnya — selisih yang diketik
  manusia hanya benar bila ia dan sistem sepakat tentang angka awalnya, dan
  seluruh alasan penyesuaian ada justru karena keduanya tidak sepakat. Barang
  yang dihitung dan ternyata cocok tetap tercatat sebagai bukti sudah dihitung,
  tanpa menghasilkan pergerakan stok.

---

## Berkas model tidak lagi ikut ke dalam image

Sejak 2026-08-28, `backend/models/` **dipasang dari host**, bukan disalin ke
dalam image.

| | Sebelum | Sesudah |
|---|---|---|
| Image backend | 4,2 GB | **1,98 GB** |
| Model di dalam image | 1,7 GB | tidak ada |

Isinya 1,7 GB, dan yang benar-benar dimuat saat melayani hanya satu berkas:
`production_tweedie.ubj` (757 MB). Sisanya bentuk JSON dari model yang sama
(926 MB) beserta berkas hasil eksperimen — tidak satu pun disentuh saat
berjalan, dan tidak satu pun berubah ketika kode berubah. Membawanya ke dalam
image berarti setiap build dan setiap versi yang disimpan sebagai jalan pulang
menggandakan berkas yang sama.

Cara kerjanya: `FORECAST_MODEL_DIR` menunjuk direktori model. Kosong berarti
`backend/models/` di sebelah kode, seperti sebelumnya — menjalankan dari sumber
di host tidak berubah sama sekali. Kontainer menyetelnya ke `/models` dan
memasangnya **read-only**; aplikasi hanya pernah membaca berkas itu.

**Jebakan yang ditutup lebih dulu.** Model yang hilang dulu hanya menghasilkan
satu baris peringatan di log, lalu sistem melanjutkan dengan rata-rata bergerak
berbobot. Setiap halaman tetap terisi, setiap angka tetap masuk akal, dan tidak
ada yang terlihat rusak — yang berubah hanyalah bahwa seluruh prakiraan menjadi
lebih buruk, diam-diam. Begitu berkasnya pindah ke mount, kemungkinan itu
menjadi nyata: satu tanda `-v` yang salah ketik sudah cukup.

`app/main.py` karena itu **menolak menyala** bila `FORECAST_USE_MODEL` menyala
tetapi berkasnya tidak ada, dan pesan gagalnya menyebutkan perintah `docker run`
yang benar. Untuk sengaja berjalan tanpa model, setel `FORECAST_USE_MODEL=false`
— itulah yang membedakan "tidak dipakai" dari "hilang".

**Mengganti model tidak lagi menuntut build ulang.** Salin berkas kandidat ke
`backend/models/`, arahkan `FORECAST_MODEL_FILE` ke sana, lalu
`scripts/deploy.sh --restart`.

---

## Hal yang perlu diketahui

**Pemindai anomali sudah tidak ada lagi.** Modul Deteksi Anomali beserta
pemindaian batch hariannya dihapus pada 2 September 2026; tempatnya diisi
Analisis Umur Pakai, yang menghitung langsung dari riwayat pengeluaran saat
halamannya dibuka dan karena itu tidak menjadwalkan apa pun. Crontab yang
sudah terpasang dibersihkan pada tanggal yang sama:

```bash
crontab -l | grep -v scan_anomalies | crontab -
```

Penyaringnya memakai nama modul, BUKAN kata "anomaly", dan itu bukan selera:
crontab mesin ini juga memuat `docker exec pv-anomaly-v2 ...` milik proyek PV
v2 yang tidak ada hubungannya dengan repositori ini. `grep -v anomaly` akan
ikut membuangnya, dan hilangnya satu baris cron tidak menimbulkan gejala apa
pun sampai ada yang menyadari datanya berhenti terisi.

**Token disimpan di `localStorage`, bukan cookie `httpOnly`.** Alasannya
tercatat pada `frontend/lib/token.ts`: dashboard dibuka lewat alamat IP yang
berganti-ganti saat demo, sehingga syarat cookie berkredensial tidak terpenuhi
hari ini. Ini keputusan, bukan kelalaian, dan berkas itu mencatat apa yang harus
berubah lebih dulu bila kelak ingin dipindahkan.

**Pengujian memakai role dan basis data sendiri.** `pytest` membuat
`inventory_uji_penyewa` dan role `inventory_app_uji`; keduanya tidak pernah
menyentuh basis data maupun kredensial produksi.

```bash
.venv/bin/python -m pytest backend/tests -q
```

**Saran pengerasan tambahan** (di luar lingkup, tetapi murah):

```sql
REVOKE CONNECT ON DATABASE inventory FROM PUBLIC;
GRANT  CONNECT ON DATABASE inventory TO inventory_app, inventory_admin;
```

Secara bawaan setiap role di kluster boleh menyambung ke setiap basis data.
Mencabutnya membuat role yang tidak berkepentingan tidak dapat membuka koneksi
sama sekali.
