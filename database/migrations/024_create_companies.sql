-- 024: companies
--
-- Tabel penyewa (tenant). Mulai berkas ini, setiap baris data di seluruh
-- sistem dimiliki oleh tepat satu perusahaan, dan tidak ada satu pun jalur
-- baca yang boleh menyeberang antar perusahaan.
--
-- KENAPA SEKARANG, BUKAN NANTI. Menambahkan kepemilikan setelah modul input
-- bertambah berarti membongkar ulang setiap query yang ditulis di antaranya.
-- Saat ini seluruh data masih milik satu pemakai, sehingga pembagiannya cukup
-- satu baris INSERT -- kelak ia menjadi pekerjaan migrasi data yang sebenarnya.
--
-- BARIS PERTAMA WAJIB ADA. Seluruh data yang sudah terlanjur ada di basis data
-- ini dinyatakan milik perusahaan id = 1 oleh migrasi 026. Tabel ini kosong
-- saat dibuat, dan kolom identity dimulai dari 1, sehingga INSERT di bawah
-- selalu menghasilkan id = 1. Migrasi 026 tetap memeriksanya sebelum bekerja
-- daripada memercayai urutan.

CREATE TABLE IF NOT EXISTS companies (
    id         BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,

    -- Pengenal pendek untuk URL dan subdomain. Dipisahkan dari nama karena
    -- nama perusahaan boleh diganti kapan saja tanpa mengubah alamat yang
    -- sudah disebar ke pengguna.
    slug       VARCHAR(80)  NOT NULL,

    -- Penanda tenant demo. Tenant demo boleh dikosongkan dan diisi ulang oleh
    -- tombol reset; tenant biasa TIDAK PERNAH boleh. Kolomnya lahir di sini,
    -- bukan menunggu modul demo dibuat, supaya tidak ada tabel yang perlu
    -- diubah lagi saat modul itu datang.
    is_demo    BOOLEAN      NOT NULL DEFAULT FALSE,

    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT companies_slug_unique  UNIQUE (slug),
    CONSTRAINT companies_slug_bentuk  CHECK (slug ~ '^[a-z0-9][a-z0-9-]*$')
);

CREATE INDEX IF NOT EXISTS idx_companies_is_active ON companies (is_active);

-- Pemilik seluruh data yang sudah ada. Namanya sengaja umum: ganti lewat
-- UPDATE setelah migrasi bila perusahaan sebenarnya sudah diketahui.
INSERT INTO companies (name, slug)
SELECT 'Perusahaan Utama', 'utama'
WHERE NOT EXISTS (SELECT 1 FROM companies);

COMMENT ON TABLE  companies         IS 'Penyewa sistem; setiap baris data di seluruh tabel dimiliki satu perusahaan';
COMMENT ON COLUMN companies.slug    IS 'Pengenal pendek untuk URL/subdomain; boleh berbeda dari nama';
COMMENT ON COLUMN companies.is_demo IS 'TRUE berarti isinya boleh dihapus dan diisi ulang oleh modul demo';
