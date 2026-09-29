-- 019: kolom perencanaan pada items dan suppliers
--
-- Prakiraan dan perencanaan pembelian membutuhkan tiga angka yang belum ada di
-- skema awal:
--
--   items.lead_time_days     berapa hari sejak dipesan sampai barang tiba.
--                            Tanpa ini, titik pemesanan ulang tidak dapat
--                            dihitung dari laju pemakaian.
--   items.safety_stock       cadangan untuk menyerap lonjakan permintaan dan
--                            keterlambatan kiriman. Berbeda dari minimum_stock
--                            yang dipakai sebagai ambang peringatan.
--   suppliers.lead_time_days waktu tunggu khas tiap supplier. Barang yang sama
--                            dari supplier berbeda bisa datang pada waktu yang
--                            jauh berbeda.
--
-- Hanya menambah kolom. Tidak ada tabel baru, jumlahnya tetap 17.

ALTER TABLE items
    ADD COLUMN IF NOT EXISTS lead_time_days INTEGER       NULL,
    ADD COLUMN IF NOT EXISTS safety_stock   DECIMAL(18,3) NULL;

ALTER TABLE suppliers
    ADD COLUMN IF NOT EXISTS lead_time_days INTEGER NULL;

COMMENT ON COLUMN items.lead_time_days IS
    'Waktu tunggu khas barang ini dalam hari, dari pemesanan sampai diterima';
COMMENT ON COLUMN items.safety_stock IS
    'Cadangan penyangga; berbeda dari minimum_stock yang dipakai sebagai ambang peringatan';
COMMENT ON COLUMN suppliers.lead_time_days IS
    'Waktu tunggu khas supplier ini dalam hari';
