-- 028: Row Level Security
--
-- Penyaringan penyewa dipasang di BASIS DATA, bukan di setiap query.
--
-- KENAPA BUKAN "WHERE company_id = ?" DI SETIAP QUERY. Ada belasan router dan
-- ratusan query, dan jumlahnya akan bertambah begitu modul input dikerjakan.
-- Satu WHERE yang terlupa pada satu query di antaranya berarti data satu klien
-- tampil di layar klien lain -- kegagalan yang tidak menimbulkan galat, tidak
-- muncul di log, dan baru ketahuan saat pelanggan yang melaporkannya. Aturan
-- yang hanya perlu ditulis sekali dan tidak bisa dilupakan jauh lebih murah
-- daripada disiplin yang harus diulang setiap kali seseorang menulis SELECT.
--
-- CARA KERJANYA. Aplikasi menyetel app.company_id sekali di awal setiap
-- transaksi (lihat app/db.py). Seluruh policy di bawah membandingkan kolom
-- company_id dengan setelan itu. Bila setelannya tidak ada, hasilnya NULL,
-- perbandingan menjadi NULL, dan TIDAK ADA baris yang lolos. Lupa menyetel
-- penyewa menghasilkan halaman kosong -- bukan data milik orang lain.
--
-- NULLIF BUKAN HIASAN. Setelan yang dipasang set_config(..., true) kembali
-- ke nilai sebelumnya saat transaksi selesai, dan untuk setelan buatan
-- sendiri nilai itu STRING KOSONG, bukan tidak ada. Tanpa NULLIF,
-- ''''::bigint melempar galat alih-alih menghasilkan NULL, dan karena
-- koneksi dipakai bergantian lewat pool, galatnya baru muncul pada
-- permintaan KEDUA di koneksi yang sama. Lihat catatan sama di migrasi 026.
--
-- KENAPA ADA ROLE BARU. PostgreSQL membebaskan superuser dari seluruh RLS,
-- tanpa kecuali dan tanpa cara mematikannya. inventory_admin -- pemilik tabel
-- yang dipakai menjalankan migrasi ini -- adalah superuser, sehingga selama
-- aplikasi tetap menyambung sebagai dia, seluruh policy di berkas ini tidak
-- berpengaruh apa pun. Aplikasi harus menyambung sebagai inventory_app.
--
-- LANGKAH YANG HARUS DIJALANKAN OPERATOR SETELAH MIGRASI INI. Role di bawah
-- dibuat TANPA hak masuk dan tanpa kata sandi -- sebuah migrasi yang terlacak
-- git bukan tempat menyimpan kata sandi. Aktifkan sendiri:
--
--     ALTER ROLE inventory_app LOGIN PASSWORD '<kata sandi kuat>';
--
-- lalu arahkan DATABASE_URL pada .env ke role tersebut. app/main.py menolak
-- menyala bila mendapati dirinya tersambung sebagai superuser, supaya langkah
-- ini tidak mungkin terlewat diam-diam.

-- --- role aplikasi --------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'inventory_app') THEN
        CREATE ROLE inventory_app NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO inventory_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO inventory_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO inventory_app;

-- Tabel dan sequence yang lahir dari migrasi berikutnya ikut terjangkau tanpa
-- perlu mengulang GRANT di setiap berkas.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO inventory_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO inventory_app;

-- --- policy per tabel -----------------------------------------------------
DO $$
DECLARE
    tabel  TEXT;
    kolom  TEXT;
    daftar TEXT[] := ARRAY[
        'categories', 'units', 'warehouses', 'suppliers', 'items',
        'stock_receipts', 'stock_issues', 'stock_transfers',
        'stock_adjustments', 'purchase_orders',
        'stock_receipt_items', 'stock_issue_items', 'stock_transfer_items',
        'stock_adjustment_items', 'purchase_order_items',
        'inventory', 'stock_movements', 'stock_batches', 'serial_numbers',
        'anomaly_findings',
        -- users ikut dilindungi: daftar pengguna satu perusahaan tidak boleh
        -- terbaca perusahaan lain. Pencarian saat MASUK terjadi sebelum
        -- penyewa diketahui, jadi ia lewat fungsi khusus di bawah.
        'users',
        -- companies disaring lewat kolom id, bukan company_id; ditangani
        -- terpisah setelah loop ini.
        'companies'
    ];
BEGIN
    FOREACH tabel IN ARRAY daftar LOOP
        kolom := CASE WHEN tabel = 'companies' THEN 'id' ELSE 'company_id' END;

        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', tabel);
        -- FORCE membuat pemilik tabel ikut tunduk. Hari ini pemiliknya
        -- superuser sehingga tetap bebas, tetapi begitu kepemilikan berpindah
        -- ke role biasa, perlindungannya sudah terpasang lebih dulu.
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', tabel);

        EXECUTE format('DROP POLICY IF EXISTS %I ON %I',
                       tabel || '_penyewa', tabel);
        EXECUTE format(
            'CREATE POLICY %I ON %I '
            'USING (%I = NULLIF(current_setting(''app.company_id'', true), '''')::bigint) '
            'WITH CHECK (%I = NULLIF(current_setting(''app.company_id'', true), '''')::bigint)',
            tabel || '_penyewa', tabel, kolom, kolom);
    END LOOP;
END $$;

-- --- jalur yang harus bekerja SEBELUM penyewa diketahui -------------------
--
-- Halaman masuk hanya punya email. Perusahaannya justru yang sedang dicari,
-- sehingga app.company_id belum bisa disetel dan policy users_penyewa akan
-- menolak seluruh baris. Kedua fungsi berikut adalah satu-satunya lubang yang
-- disengaja, dan keduanya sempit: yang pertama membaca tepat satu baris
-- berdasarkan email, yang kedua hanya menulis perusahaan baru beserta
-- pemiliknya.
--
-- SECURITY DEFINER berarti isinya berjalan dengan hak pemilik fungsi, yaitu
-- pemilik tabel, sehingga bebas dari RLS. search_path dikunci pada tiap fungsi
-- -- tanpa itu, pemanggil dapat menyelipkan skema berisi tabel "users" palsu
-- dan membuat fungsi ini membaca dari sana.

CREATE OR REPLACE FUNCTION auth_cari_pengguna(p_email TEXT)
RETURNS TABLE (
    id            BIGINT,
    company_id    BIGINT,
    email         VARCHAR,
    full_name     VARCHAR,
    password_hash VARCHAR,
    role          VARCHAR,
    is_active     BOOLEAN,
    token_version INTEGER,
    company_name  VARCHAR,
    company_slug  VARCHAR,
    company_aktif BOOLEAN
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
    SELECT u.id, u.company_id, u.email, u.full_name, u.password_hash,
           u.role, u.is_active, u.token_version,
           c.name, c.slug, c.is_active
      FROM users u
      JOIN companies c ON c.id = u.company_id
     WHERE u.email = lower(p_email);
$$;

CREATE OR REPLACE FUNCTION auth_daftar_perusahaan(
    p_nama_perusahaan TEXT,
    p_slug            TEXT,
    p_email           TEXT,
    p_nama_lengkap    TEXT,
    p_password_hash   TEXT
)
RETURNS TABLE (company_id BIGINT, user_id BIGINT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_company_id BIGINT;
    v_user_id    BIGINT;
BEGIN
    INSERT INTO companies (name, slug)
    VALUES (p_nama_perusahaan, p_slug)
    RETURNING companies.id INTO v_company_id;

    -- Pendaftar selalu menjadi owner: sebuah perusahaan tanpa owner tidak
    -- punya siapa pun yang berhak mengangkat pengguna berikutnya.
    INSERT INTO users (company_id, email, full_name, password_hash, role)
    VALUES (v_company_id, lower(p_email), p_nama_lengkap, p_password_hash, 'owner')
    RETURNING users.id INTO v_user_id;

    RETURN QUERY SELECT v_company_id, v_user_id;
END;
$$;

-- Fungsi SECURITY DEFINER dapat dieksekusi PUBLIC secara bawaan. Dicabut
-- lebih dulu, lalu diberikan hanya kepada role aplikasi.
REVOKE EXECUTE ON FUNCTION auth_cari_pengguna(TEXT) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION auth_daftar_perusahaan(TEXT, TEXT, TEXT, TEXT, TEXT) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION auth_cari_pengguna(TEXT) TO inventory_app;
GRANT  EXECUTE ON FUNCTION auth_daftar_perusahaan(TEXT, TEXT, TEXT, TEXT, TEXT) TO inventory_app;

COMMENT ON FUNCTION auth_cari_pengguna(TEXT)
    IS 'Pencarian pengguna saat masuk; satu-satunya pembacaan users yang berjalan sebelum penyewa diketahui';
COMMENT ON FUNCTION auth_daftar_perusahaan(TEXT, TEXT, TEXT, TEXT, TEXT)
    IS 'Pendaftaran perusahaan baru beserta pengguna owner-nya';
