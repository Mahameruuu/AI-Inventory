-- 026: company_id pada seluruh tabel data
--
-- Inilah migrasi yang mengubah sistem satu-pemakai menjadi banyak-penyewa.
-- Setiap tabel data menerima satu kolom pemilik, dan seluruh baris yang sudah
-- ada dinyatakan milik perusahaan id = 1.
--
-- KENAPA TABEL BARIS RINCIAN IKUT DIBERI KOLOM. stock_receipt_items sudah
-- menunjuk stock_receipts yang punya pemilik, jadi pemiliknya bisa dicari
-- lewat join. Tetapi Row Level Security (migrasi 028) bekerja per tabel, bukan
-- per join: query yang membaca tabel rincian secara langsung -- dan beberapa
-- laporan memang begitu -- tidak akan terlindungi bila tabelnya sendiri tidak
-- tahu siapa pemiliknya. Kolomnya ada di semua tabel supaya tidak ada satu pun
-- jalur baca yang lolos.
--
-- KENAPA TIDAK ADA TABEL YANG DITULIS ULANG. ADD COLUMN dengan DEFAULT berupa
-- nilai tetap tidak menyentuh isi tabel pada PostgreSQL 11 ke atas; nilainya
-- disimpan sekali di katalog. Ini yang membuat stock_movements dengan 3,1 juta
-- baris selesai dalam hitungan detik, bukan menit.
--
-- KENAPA DEFAULT-NYA DIGANTI SETELAHNYA. Setelah baris lama terisi, default
-- tetap 1 justru berbahaya: satu INSERT yang lupa menyebut pemilik akan diam-
-- diam masuk ke perusahaan 1. Diganti menjadi pembacaan setelan sesi, kolom
-- ini terisi sendiri dari penyewa yang sedang aktif -- itulah sebabnya 12
-- router yang sudah ada tidak perlu diubah satu baris pun. Bila setelan itu
-- tidak ada, hasilnya NULL dan INSERT ditolak NOT NULL. Gagal, bukan salah
-- tulis ke penyewa lain.
--
-- KENAPA ADA NULLIF. Setelan yang dipasang dengan set_config(..., true)
-- dikembalikan ke nilai sebelumnya saat transaksi selesai, dan untuk
-- setelan buatan sendiri yang belum pernah ada di tingkat sesi, nilai
-- "sebelumnya" itu adalah STRING KOSONG -- bukan tidak ada. Akibatnya
-- current_setting mengembalikan '''' pada transaksi kedua di koneksi yang
-- sama, dan ''''::bigint bukan NULL melainkan galat. Karena koneksi dipakai
-- bergantian lewat pool, permintaan PERTAMA berhasil dan permintaan
-- berikutnya di koneksi yang sama gagal -- kegagalan yang tidak muncul
-- sama sekali saat diuji satu permintaan. NULLIF yang mengubahnya kembali
-- menjadi NULL.

-- Penjaga. Migrasi ini menyatakan seluruh data lama milik id = 1; bila baris
-- itu tidak ada, foreign key di bawah akan gagal dengan pesan yang jauh lebih
-- sulit dibaca daripada kalimat ini.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM companies WHERE id = 1) THEN
        RAISE EXCEPTION
            'companies id = 1 belum ada. Jalankan migrasi 024 lebih dulu.';
    END IF;
END $$;

DO $$
DECLARE
    -- Seluruh tabel data. Yang TIDAK ada di sini: companies (ia sendiri
    -- pemiliknya) dan users (sudah punya company_id sejak lahir di 025).
    tabel TEXT;
    daftar TEXT[] := ARRAY[
        -- master
        'categories', 'units', 'warehouses', 'suppliers', 'items',
        -- kepala transaksi
        'stock_receipts', 'stock_issues', 'stock_transfers',
        'stock_adjustments', 'purchase_orders',
        -- baris rincian
        'stock_receipt_items', 'stock_issue_items', 'stock_transfer_items',
        'stock_adjustment_items', 'purchase_order_items',
        -- keadaan stok dan turunannya
        'inventory', 'stock_movements', 'stock_batches', 'serial_numbers',
        'anomaly_findings'
    ];
BEGIN
    FOREACH tabel IN ARRAY daftar LOOP
        -- Satu: kolomnya ada, seluruh baris lama menjadi milik perusahaan 1.
        EXECUTE format(
            'ALTER TABLE %I ADD COLUMN IF NOT EXISTS company_id BIGINT NOT NULL DEFAULT 1',
            tabel);

        -- Dua: default berpindah ke setelan sesi, sehingga INSERT berikutnya
        -- mengikuti penyewa yang sedang aktif, bukan perusahaan 1.
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN company_id '
            'SET DEFAULT NULLIF(current_setting(''app.company_id'', true), '''')::bigint',
            tabel);

        -- Tiga: pemiliknya harus benar-benar ada.
        EXECUTE format(
            'ALTER TABLE %I ADD CONSTRAINT %I '
            'FOREIGN KEY (company_id) REFERENCES companies (id)',
            tabel, tabel || '_company_id_fkey');

        -- Empat: setiap pembacaan disaring kolom ini oleh RLS, jadi ia berada
        -- di jalur panas setiap query tanpa kecuali.
        EXECUTE format(
            'CREATE INDEX IF NOT EXISTS %I ON %I (company_id)',
            'idx_' || tabel || '_company_id', tabel);

        EXECUTE format(
            'COMMENT ON COLUMN %I.company_id IS %L',
            tabel, 'Perusahaan pemilik baris; diisi otomatis dari setelan sesi app.company_id');
    END LOOP;
END $$;
