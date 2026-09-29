-- 025: users
--
-- Pengguna yang masuk ke sistem. Satu pengguna milik tepat satu perusahaan;
-- perusahaan itulah yang menentukan data apa yang terlihat olehnya.
--
-- EMAIL UNIK SECARA GLOBAL, BUKAN PER PERUSAHAAN. Halaman masuk hanya meminta
-- email dan kata sandi -- tidak ada kolom "perusahaan" yang harus diisi lebih
-- dulu. Supaya itu mungkin, satu email harus menunjuk tepat satu pengguna di
-- seluruh sistem. Harganya: satu orang yang bekerja di dua perusahaan butuh
-- dua email. Itu pertukaran yang disengaja, dan mengubahnya nanti berarti
-- menambah satu langkah pada layar pertama yang dilihat setiap pengguna.
--
-- KATA SANDI TIDAK PERNAH DISIMPAN. Yang tersimpan hanya hash bcrypt beserta
-- garamnya; kolom ini tidak pernah masuk jawaban API mana pun.
--
-- token_version ADALAH SATU-SATUNYA CARA MENCABUT TOKEN. Token akses bersifat
-- mandiri (JWT) sehingga tidak bisa "dihapus" dari sisi server. Menaikkan
-- angka ini membuat seluruh token lama milik pengguna tersebut ditolak pada
-- permintaan berikutnya -- inilah yang menjalankan "keluar dari semua
-- perangkat" dan pencabutan akses saat kata sandi diganti.

CREATE TABLE IF NOT EXISTS users (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    -- DEFAULT-nya sama persis dengan seluruh tabel data pada migrasi 026:
    -- pemilik baris dibaca dari penyewa yang sedang aktif. Tanpa ini,
    -- endpoint yang menambah pengguna harus menyebut company_id sendiri --
    -- satu-satunya tabel yang diperlakukan berbeda, dan karena itu satu-
    -- satunya tempat kebiasaan yang benar di tabel lain justru salah.
    -- NULLIF-nya wajib; alasannya ada pada migrasi 026.
    company_id    BIGINT       NOT NULL
                  DEFAULT NULLIF(current_setting('app.company_id', true), '')::bigint,

    email         VARCHAR(255) NOT NULL,
    full_name     VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,

    -- owner  : pemilik tenant, tidak bisa dihapus dan tidak bisa diturunkan
    --          oleh siapa pun selain dirinya sendiri
    -- admin  : mengelola pengguna dan master data
    -- staff  : mencatat transaksi (penerimaan, pengeluaran, PO)
    -- viewer : hanya membaca
    role          VARCHAR(20)  NOT NULL DEFAULT 'staff',

    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    token_version INTEGER      NOT NULL DEFAULT 1,
    last_login_at TIMESTAMPTZ  NULL,

    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT users_email_unique     UNIQUE (email),
    CONSTRAINT users_email_bentuk     CHECK (email = lower(email) AND position('@' IN email) > 1),
    CONSTRAINT users_role_valid       CHECK (role IN ('owner', 'admin', 'staff', 'viewer')),
    CONSTRAINT users_company_id_fkey  FOREIGN KEY (company_id) REFERENCES companies (id)
);

CREATE INDEX IF NOT EXISTS idx_users_company_id ON users (company_id);
CREATE INDEX IF NOT EXISTS idx_users_is_active  ON users (is_active);

-- Setiap perusahaan harus punya tepat satu owner. Indeks parsial ini yang
-- menjaganya: menaikkan pengguna kedua menjadi owner akan ditolak basis data,
-- bukan hanya oleh pemeriksaan di aplikasi yang bisa terlewat.
CREATE UNIQUE INDEX IF NOT EXISTS users_owner_tunggal
    ON users (company_id) WHERE role = 'owner';

COMMENT ON TABLE  users               IS 'Pengguna sistem; satu pengguna milik satu perusahaan';
COMMENT ON COLUMN users.password_hash IS 'Hash bcrypt; kata sandi asli tidak pernah disimpan dan tidak pernah dikembalikan API';
COMMENT ON COLUMN users.role          IS 'owner | admin | staff | viewer';
COMMENT ON COLUMN users.token_version IS 'Dinaikkan untuk membatalkan seluruh token yang sudah terlanjur terbit bagi pengguna ini';
