-- Menjalankan seluruh migration secara berurutan.
--
--   psql -h <host> -p <port> -U <user> -d <db> -f database/migrate.sql
--
-- Dijalankan dalam SATU transaksi: bila ada satu pernyataan yang gagal,
-- seluruhnya dibatalkan dan basis data kembali seperti semula. Tidak ada
-- kondisi setengah jadi.
--
-- Urutannya mengikuti arah foreign key: master lebih dulu, lalu transaksi,
-- lalu inventory. Nomor 017 harus setelah 016 karena serial_numbers merujuk
-- stock_batches.
--
-- Untuk membuat ulang dari nol, jalankan database/reset.sql terlebih dahulu.

\set ON_ERROR_STOP on

BEGIN;

\ir migrations/001_create_categories.sql
\ir migrations/002_create_units.sql
\ir migrations/003_create_warehouses.sql
\ir migrations/004_create_suppliers.sql
\ir migrations/005_create_items.sql
\ir migrations/006_create_stock_receipts.sql
\ir migrations/007_create_stock_receipt_items.sql
\ir migrations/008_create_stock_issues.sql
\ir migrations/009_create_stock_issue_items.sql
\ir migrations/010_create_stock_transfers.sql
\ir migrations/011_create_stock_transfer_items.sql
\ir migrations/012_create_stock_adjustments.sql
\ir migrations/013_create_stock_adjustment_items.sql
\ir migrations/014_create_inventory.sql
\ir migrations/015_create_stock_movements.sql
\ir migrations/016_create_stock_batches.sql
\ir migrations/017_create_serial_numbers.sql

-- Perubahan setelah skema awal. Nomor 001-017 sengaja tidak diubah supaya
-- riwayatnya tetap terbaca dan basis data yang sudah jalan cukup menerima
-- selisihnya saja.
\ir migrations/018_add_is_active_to_categories_and_units.sql
\ir migrations/019_add_planning_columns.sql
\ir migrations/020_create_anomaly_findings.sql
\ir migrations/021_create_purchase_orders.sql
\ir migrations/022_create_purchase_order_items.sql
\ir migrations/023_link_purchase_order_to_receipt.sql

-- Fondasi banyak-penyewa. Urutannya mengikat: 024 melahirkan perusahaan
-- pertama, 025 pengguna, 026 menempelkan pemilik pada seluruh tabel data, 027
-- membuat keunikan dihitung per perusahaan, dan 028 memasang penyaringnya di
-- basis data. Menjalankan salah satunya di luar urutan ini akan gagal.
\ir migrations/024_create_companies.sql
\ir migrations/025_create_users.sql
\ir migrations/026_add_company_id.sql
\ir migrations/027_tenant_scoped_unique.sql
\ir migrations/028_row_level_security.sql

-- Atribut master yang berdiri sendiri: umur pakai komponen. Tidak menyentuh
-- satu pun kolom yang sudah ada, jadi letaknya bebas selama setelah 005.
\ir migrations/029_add_service_life.sql
\ir migrations/030_drop_anomaly_findings.sql

-- Transfer Antar Gudang. Menyentuh warehouses, stock_transfers, dan
-- stock_transfer_items yang seluruhnya sudah ada, serta melahirkan satu tabel
-- jarak; letaknya harus SETELAH 028 karena policy RLS tabel barunya menyalin
-- bentuk yang dipasang di sana, dan setelah 026 karena kolom company_id-nya
-- memakai setelan sesi yang sama.
\ir migrations/031_transfer_antar_gudang.sql

-- Jenis pemakaian barang. Hanya menambah kolom pada items.
\ir migrations/034_add_usage_type.sql

-- Moda angkut, biaya, dan jumlah diterima pada transfer.
\ir migrations/035_transfer_moda_biaya.sql

-- Jejak audit (trigger + audit_log hanya-baca) dan alur stok opname.
-- Harus SETELAH 028: ia mencabut hak tulis yang diberikan default privileges.
\ir migrations/036_audit_dan_opname.sql

COMMIT;

\echo 'Migration selesai.'
