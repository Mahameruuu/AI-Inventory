-- 037: masuk dengan username, pendaftaran mandiri dicabut, lupa kata sandi
--
-- 1. USERNAME. Masuk kini memakai username + kata sandi, bukan email.
--    Username unik SEDUNIA (bukan per perusahaan) karena saat masuk
--    perusahaannya justru belum diketahui -- sama alasannya dengan email
--    pada migrasi 025. Email tetap disimpan bila diisi, tetapi tidak wajib.
--
-- 2. PENDAFTARAN MANDIRI DICABUT. Perusahaan baru hanya dibuat orang dalam
--    (pembangun data demo, atau SQL admin). Fungsi lama auth_daftar_perusahaan
--    yang menerima email diganti auth_buat_perusahaan yang menerima username,
--    dan tidak ada lagi endpoint yang memanggilnya.
--
-- 3. LUPA KATA SANDI LEWAT WEB. Tanpa email, pemulihan ditempuh lewat admin:
--    pengguna mengisi username di halaman masuk, permintaannya tercatat di
--    password_reset_requests, dan admin/owner perusahaannya menyetel kata
--    sandi baru dari halaman Pengguna.

-- --- 1. username ---------------------------------------------------------
ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(50) NULL;

-- Isi dari bagian depan email. Bentrokan diberi akhiran id supaya tetap unik.
UPDATE users u
   SET username = sub.calon
  FROM (
      SELECT id,
             CASE WHEN count(*) OVER (PARTITION BY dasar) > 1
                  THEN left(dasar, 40) || '-' || id
                  ELSE dasar END AS calon
        FROM (SELECT id,
                     COALESCE(NULLIF(regexp_replace(lower(split_part(email, '@', 1)),
                                                    '[^a-z0-9._-]', '', 'g'), ''),
                              'user' || id) AS dasar
                FROM users) d
  ) sub
 WHERE sub.id = u.id AND u.username IS NULL;

-- Username yang terlalu pendek untuk aturan format di bawah.
UPDATE users SET username = username || '-' || id WHERE length(username) < 3;

ALTER TABLE users ALTER COLUMN username SET NOT NULL;
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_unique;
ALTER TABLE users ADD CONSTRAINT users_username_unique UNIQUE (username);
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_format;
ALTER TABLE users ADD CONSTRAINT users_username_format
    CHECK (username ~ '^[a-z0-9._-]{3,50}$');

ALTER TABLE users ALTER COLUMN email DROP NOT NULL;

COMMENT ON COLUMN users.username IS
    'Nama masuk; huruf kecil, angka, titik, garis bawah, tanda hubung; unik sedunia';

-- Pencarian saat masuk kini lewat username. Bentuk kembaliannya berubah,
-- jadi fungsi lama dibuang lebih dulu.
DROP FUNCTION IF EXISTS auth_cari_pengguna(TEXT);
CREATE FUNCTION auth_cari_pengguna(p_username TEXT)
RETURNS TABLE (
    id            BIGINT,
    company_id    BIGINT,
    username      VARCHAR,
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
    SELECT u.id, u.company_id, u.username, u.email, u.full_name, u.password_hash,
           u.role, u.is_active, u.token_version,
           c.name, c.slug, c.is_active
      FROM users u
      JOIN companies c ON c.id = u.company_id
     WHERE u.username = lower(p_username);
$$;
REVOKE EXECUTE ON FUNCTION auth_cari_pengguna(TEXT) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'inventory_app') THEN
        GRANT EXECUTE ON FUNCTION auth_cari_pengguna(TEXT) TO inventory_app;
    END IF;
END $$;

-- --- 2. pendaftaran mandiri dicabut ---------------------------------------
DROP FUNCTION IF EXISTS auth_daftar_perusahaan(TEXT, TEXT, TEXT, TEXT, TEXT);

CREATE OR REPLACE FUNCTION auth_buat_perusahaan(
    p_nama_perusahaan TEXT,
    p_slug            TEXT,
    p_username        TEXT,
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

    INSERT INTO users (company_id, username, full_name, password_hash, role)
    VALUES (v_company_id, lower(p_username), p_nama_lengkap, p_password_hash, 'owner')
    RETURNING users.id INTO v_user_id;

    RETURN QUERY SELECT v_company_id, v_user_id;
END;
$$;
-- Diberikan ke inventory_app karena pembangun data demo (app/jobs/buat_demo.py)
-- berjalan dengan role itu. TIDAK ADA endpoint yang memanggilnya: perusahaan
-- baru hanya lahir dari skrip yang dijalankan operator di server.
REVOKE EXECUTE ON FUNCTION auth_buat_perusahaan(TEXT, TEXT, TEXT, TEXT, TEXT) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'inventory_app') THEN
        GRANT EXECUTE ON FUNCTION auth_buat_perusahaan(TEXT, TEXT, TEXT, TEXT, TEXT)
            TO inventory_app;
    END IF;
END $$;
COMMENT ON FUNCTION auth_buat_perusahaan(TEXT, TEXT, TEXT, TEXT, TEXT)
    IS 'Membuat perusahaan beserta owner-nya; dipanggil skrip operator, tidak lewat endpoint';

-- --- 3. permintaan setel ulang kata sandi --------------------------------
CREATE TABLE IF NOT EXISTS password_reset_requests (
    id           BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id   BIGINT      NOT NULL
                 DEFAULT NULLIF(current_setting('app.company_id', true), '')::bigint,
    user_id      BIGINT      NOT NULL REFERENCES users (id),
    status       VARCHAR(10) NOT NULL DEFAULT 'pending',
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    handled_by   BIGINT      NULL REFERENCES users (id),
    handled_at   TIMESTAMPTZ NULL,

    CONSTRAINT password_reset_requests_status_check
        CHECK (status IN ('pending', 'done', 'dismissed'))
);
-- Paling banyak satu permintaan menunggu per pengguna: menekan tombol
-- berkali-kali tidak boleh membanjiri daftar admin.
CREATE UNIQUE INDEX IF NOT EXISTS uq_reset_satu_menunggu
    ON password_reset_requests (user_id) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_reset_company_status
    ON password_reset_requests (company_id, status);

ALTER TABLE password_reset_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE password_reset_requests FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS password_reset_requests_penyewa ON password_reset_requests;
CREATE POLICY password_reset_requests_penyewa ON password_reset_requests
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::bigint)
    WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::bigint);

-- Permintaan datang SEBELUM masuk, jadi penyewa belum diketahui. Fungsi ini
-- satu-satunya jalan menulisnya dari luar, dan ia tidak mengembalikan apa pun:
-- jawaban yang sama untuk username yang ada maupun tidak, supaya halaman
-- lupa-sandi tidak bisa dipakai menebak username mana yang terdaftar.
CREATE OR REPLACE FUNCTION auth_minta_reset_sandi(p_username TEXT)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_user    BIGINT;
    v_company BIGINT;
BEGIN
    SELECT u.id, u.company_id INTO v_user, v_company
      FROM users u JOIN companies c ON c.id = u.company_id
     WHERE u.username = lower(p_username) AND u.is_active AND c.is_active;
    IF v_user IS NULL THEN
        RETURN;
    END IF;
    INSERT INTO password_reset_requests (company_id, user_id)
    VALUES (v_company, v_user)
    ON CONFLICT (user_id) WHERE status = 'pending' DO NOTHING;
END;
$$;
REVOKE EXECUTE ON FUNCTION auth_minta_reset_sandi(TEXT) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'inventory_app') THEN
        GRANT EXECUTE ON FUNCTION auth_minta_reset_sandi(TEXT) TO inventory_app;
    END IF;
END $$;

DROP TRIGGER IF EXISTS password_reset_requests_audit ON password_reset_requests;
CREATE TRIGGER password_reset_requests_audit
    AFTER INSERT OR UPDATE OR DELETE ON password_reset_requests
    FOR EACH ROW EXECUTE FUNCTION audit_catat();
