-- Menjalankan HANYA migrasi fondasi banyak-penyewa (024-028).
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/migrate_multitenant.sql
--
-- KENAPA BERKAS SENDIRI, BUKAN database/migrate.sql. Berkas itu membangun
-- basis data DARI NOL: migrasi 001-023 memakai CREATE TABLE polos, sehingga
-- menjalankannya pada basis data yang sudah berisi data akan berhenti pada
-- pernyataan pertama dengan "relation already exists". Ia benar untuk basis
-- data baru dan tidak pernah benar untuk yang sudah jalan.
--
-- Berkas ini untuk basis data yang sudah berisi 001-023 dan perlu menerima
-- selisihnya saja.
--
-- SATU TRANSAKSI. Bila salah satu langkah gagal -- termasuk saat membangun
-- indeks pada tabel berisi jutaan baris -- seluruhnya dibatalkan dan basis
-- data kembali persis seperti sebelum perintah ini dijalankan. Tidak ada
-- keadaan setengah jadi yang harus dibereskan manual.

\set ON_ERROR_STOP on

BEGIN;

\ir migrations/024_create_companies.sql
\ir migrations/025_create_users.sql
\ir migrations/026_add_company_id.sql
\ir migrations/027_tenant_scoped_unique.sql
\ir migrations/028_row_level_security.sql

COMMIT;

\echo 'Fondasi banyak-penyewa terpasang.'
