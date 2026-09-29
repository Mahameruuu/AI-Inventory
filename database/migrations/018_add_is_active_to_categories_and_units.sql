-- 018: is_active pada categories dan units
--
-- Kedua tabel ini master data yang dirujuk items lewat foreign key NO ACTION,
-- sehingga tidak dapat dihapus setelah dipakai. Tanpa is_active, kategori atau
-- satuan yang sudah tidak terpakai akan menempel selamanya di daftar pilihan.
--
-- Menambah kolom BUKAN menambah tabel: jumlah tabel tetap 17.
--
-- ADD COLUMN dengan DEFAULT non-volatile tidak menulis ulang tabel pada
-- PostgreSQL 11 ke atas, jadi aman dijalankan walau tabelnya sudah berisi data;
-- seluruh baris lama otomatis bernilai TRUE.

ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE units      ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

COMMENT ON COLUMN categories.is_active IS 'Penanda aktif; dipakai untuk menonaktifkan kategori yang sudah pernah digunakan alih-alih menghapusnya';
COMMENT ON COLUMN units.is_active      IS 'Penanda aktif; dipakai untuk menonaktifkan satuan yang sudah pernah digunakan alih-alih menghapusnya';
