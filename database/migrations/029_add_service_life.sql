-- 029: umur pakai komponen pada items
--
-- Berapa lama satu unit komponen bertahan sebelum harus diganti. Angka ini
-- datang dari spesifikasi pabrikan atau dari catatan pemeliharaan, BUKAN dari
-- pergerakan stok, sehingga tidak ada satu pun tabel transaksi yang dapat
-- menurunkannya sendiri -- ia harus dicatat sebagai atribut master.
--
-- KENAPA BUKAN MENUMPANG PADA lead_time_days. Keduanya sama-sama "durasi" dan
-- karena itu justru mudah tertukar, sedangkan artinya berjauhan:
--
--   lead_time_days       berapa lama menunggu KIRIMAN datang dari pemasok.
--                        Menggerakkan titik pesan lewat D x lead time dan
--                        Z x sigma x akar(lead time).
--   service_life_value   berapa lama satu unit BERTAHAN setelah terpasang.
--                        Tidak menggerakkan apa pun hari ini.
--
-- Mengisi lead_time_days dengan 12.500 jam akan membuat titik pesan meledak
-- menjadi puluhan ribu unit dan setiap barang berstatus "Segera pesan" --
-- tanpa satu pun galat yang menunjuk sebabnya. Kolom terpisah menutup jalan
-- itu secara permanen.
--
-- SATUANNYA IKUT DISIMPAN, TIDAK DINORMALKAN KE JAM. Sebagian komponen
-- dinyatakan dalam jam operasi (12.500 jam), sebagian dalam tahun kalender
-- (20 tahun), dan mengubah yang kedua menjadi yang pertama menuntut satu angka
-- yang tidak dimiliki basis data ini: berapa jam mesin benar-benar beroperasi
-- setiap tahun. Dengan 24 jam sehari, 20 tahun menjadi 175.200 jam; dengan satu
-- shift kerja, 40.000 jam. Selisihnya lebih dari empat kali lipat, dan asumsi
-- sebesar itu tidak boleh tertanam diam-diam di dalam kolom. Yang menyimpannya
-- apa adanya membiarkan keputusan itu diambil kelak oleh yang mengetahuinya.
--
-- Hanya menambah kolom. Tidak ada tabel baru.

ALTER TABLE items
    ADD COLUMN IF NOT EXISTS service_life_value DECIMAL(18,3) NULL,
    ADD COLUMN IF NOT EXISTS service_life_unit  VARCHAR(8)    NULL;

-- Satuannya dibatasi di basis data, bukan hanya di aplikasi: kolom teks bebas
-- akan berisi "jam", "Jam", "hours", dan "hr" dalam setahun, dan tidak satu
-- pun laporan yang membacanya dapat menjumlahkan apa pun.
ALTER TABLE items DROP CONSTRAINT IF EXISTS items_service_life_unit_check;
ALTER TABLE items
    ADD CONSTRAINT items_service_life_unit_check
    CHECK (service_life_unit IS NULL OR service_life_unit IN ('jam', 'tahun'));

-- Angka tanpa satuan tidak berarti apa-apa, dan satuan tanpa angka tidak
-- menerangkan apa-apa. Keduanya wajib berjalan bersama.
ALTER TABLE items DROP CONSTRAINT IF EXISTS items_service_life_lengkap_check;
ALTER TABLE items
    ADD CONSTRAINT items_service_life_lengkap_check
    CHECK ((service_life_value IS NULL) = (service_life_unit IS NULL));

-- Umur pakai nol atau negatif adalah komponen yang habis sebelum dipasang.
ALTER TABLE items DROP CONSTRAINT IF EXISTS items_service_life_positif_check;
ALTER TABLE items
    ADD CONSTRAINT items_service_life_positif_check
    CHECK (service_life_value IS NULL OR service_life_value > 0);

COMMENT ON COLUMN items.service_life_value IS
    'Umur pakai satu unit komponen sebelum harus diganti. Satuannya pada '
    'service_life_unit dan TIDAK dinormalkan; jangan bandingkan dua baris '
    'tanpa memeriksa satuannya lebih dulu.';

COMMENT ON COLUMN items.service_life_unit IS
    'Satuan service_life_value: jam operasi atau tahun kalender. Bukan '
    'satuan barang, dan tidak ada hubungannya dengan tabel units.';
