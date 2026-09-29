-- Mengosongkan skema agar migrate.sql dapat dijalankan ulang dari nol.
--
--   psql -h <host> -p <port> -U <user> -d <db> -f database/reset.sql
--
-- PERINGATAN: seluruh tabel beserta isinya dihapus.
-- Urutan drop adalah kebalikan dari urutan migration.

\set ON_ERROR_STOP on

BEGIN;

DROP TABLE IF EXISTS serial_numbers;
DROP TABLE IF EXISTS stock_batches;
DROP TABLE IF EXISTS stock_movements;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS stock_adjustment_items;
DROP TABLE IF EXISTS stock_adjustments;
DROP TABLE IF EXISTS stock_transfer_items;
DROP TABLE IF EXISTS stock_transfers;
DROP TABLE IF EXISTS stock_issue_items;
DROP TABLE IF EXISTS stock_issues;
DROP TABLE IF EXISTS stock_receipt_items;
DROP TABLE IF EXISTS stock_receipts;
DROP TABLE IF EXISTS items;
DROP TABLE IF EXISTS suppliers;
DROP TABLE IF EXISTS warehouses;
DROP TABLE IF EXISTS units;
DROP TABLE IF EXISTS categories;

COMMIT;

\echo 'Reset selesai. Skema kosong.'
