-- 036: jejak audit dan stok opname
--
-- DUA BAGIAN, SATU BERKAS, karena keduanya bersandar pada hal yang sama:
-- setelan sesi app.user_id yang dipasang app/db.py di samping app.company_id.
--
-- ==========================================================================
-- 1. JEJAK AUDIT
-- ==========================================================================
--
-- KENAPA TRIGGER, BUKAN KODE DI ROUTER. Perubahan bisa datang dari router,
-- alat Asisten, pembangkit data demo, atau SQL manual. Catatan yang ditulis
-- router hanya mencakup jalan yang kebetulan diingat penulisnya; trigger
-- mencatat SETIAP perubahan baris, dari mana pun asalnya.
--
-- KENAPA APPEND-ONLY. Jejak audit yang bisa disunting oleh pelaku yang
-- diaudit bukan jejak audit. Role aplikasi hanya diberi SELECT; baris ditulis
-- oleh fungsi SECURITY DEFINER milik pemilik tabel. Bahkan aplikasi yang
-- dibobol pun tidak dapat menghapus jejaknya sendiri.
--
-- KENAPA stock_movements TIDAK DIAUDIT LEWAT TABEL INI. Ledger sudah
-- append-only dan sudah menjadi riwayat; yang kurang darinya hanya SIAPA.
-- Itu ditambal dengan kolom created_by, bukan dengan menyalin setiap baris
-- ledger ke tabel kedua.

CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id  BIGINT      NOT NULL,
    table_name  VARCHAR(63) NOT NULL,
    row_id      BIGINT      NULL,
    action      VARCHAR(6)  NOT NULL,      -- INSERT | UPDATE | DELETE
    user_id     BIGINT      NULL,          -- NULL = bukan dari permintaan pengguna (SQL manual, pekerjaan latar)
    changed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    old_data    JSONB       NULL,          -- UPDATE: hanya kolom yang berubah
    new_data    JSONB       NULL,

    CONSTRAINT audit_log_action_check CHECK (action IN ('INSERT', 'UPDATE', 'DELETE'))
);

CREATE INDEX IF NOT EXISTS idx_audit_log_company_waktu ON audit_log (company_id, changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_baris         ON audit_log (table_name, row_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_user          ON audit_log (user_id);

COMMENT ON TABLE audit_log IS
    'Jejak perubahan baris; diisi trigger audit_catat(), hanya-baca bagi aplikasi';

ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS audit_log_penyewa ON audit_log;
CREATE POLICY audit_log_penyewa ON audit_log
    USING (company_id = NULLIF(current_setting('app.company_id', true), '')::bigint);

-- Default privileges dari migrasi 028 memberi aplikasi hak tulis atas setiap
-- tabel baru. Untuk tabel ini justru itulah yang tidak boleh.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'inventory_app') THEN
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON audit_log FROM inventory_app;
        GRANT SELECT ON audit_log TO inventory_app;
    END IF;
END $$;

-- Kolom yang tidak pernah boleh masuk jejak (rahasia), dan kolom yang
-- berubah sendiri tanpa makna bisnis (perubahan yang hanya menyentuh kolom
-- ini tidak dicatat sama sekali).
CREATE OR REPLACE FUNCTION audit_catat()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    rahasia  TEXT[] := ARRAY['password_hash'];
    abaikan  TEXT[] := ARRAY['updated_at', 'last_login_at', 'token_version'];
    v_lama   JSONB;
    v_baru   JSONB;
    v_beda_l JSONB := '{}'::jsonb;
    v_beda_b JSONB := '{}'::jsonb;
    k        TEXT;
    v_baris  JSONB;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN v_lama := to_jsonb(OLD) - rahasia; END IF;
    IF TG_OP IN ('UPDATE', 'INSERT') THEN v_baru := to_jsonb(NEW) - rahasia; END IF;

    IF TG_OP = 'UPDATE' THEN
        FOR k IN SELECT jsonb_object_keys(v_baru) LOOP
            IF k <> ALL (abaikan) AND (v_baru -> k) IS DISTINCT FROM (v_lama -> k) THEN
                v_beda_l := v_beda_l || jsonb_build_object(k, v_lama -> k);
                v_beda_b := v_beda_b || jsonb_build_object(k, v_baru -> k);
            END IF;
        END LOOP;
        IF v_beda_b = '{}'::jsonb THEN
            RETURN NULL;
        END IF;
        v_lama := v_beda_l;
        v_baru := v_beda_b;
    END IF;

    v_baris := COALESCE(to_jsonb(NEW), to_jsonb(OLD));

    INSERT INTO audit_log (company_id, table_name, row_id, action, user_id, old_data, new_data)
    VALUES (
        (v_baris ->> 'company_id')::bigint,
        TG_TABLE_NAME,
        (v_baris ->> 'id')::bigint,
        TG_OP,
        NULLIF(current_setting('app.user_id', true), '')::bigint,
        v_lama,
        v_baru
    );
    RETURN NULL;
END;
$$;

REVOKE EXECUTE ON FUNCTION audit_catat() FROM PUBLIC;

DO $$
DECLARE
    tabel  TEXT;
    daftar TEXT[] := ARRAY[
        'categories', 'units', 'warehouses', 'suppliers', 'items', 'users',
        'stock_receipts', 'stock_issues', 'stock_transfers',
        'stock_adjustments', 'stock_adjustment_items', 'purchase_orders'
    ];
BEGIN
    FOREACH tabel IN ARRAY daftar LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I', tabel || '_audit', tabel);
        EXECUTE format(
            'CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON %I '
            'FOR EACH ROW EXECUTE FUNCTION audit_catat()',
            tabel || '_audit', tabel);
    END LOOP;
END $$;

-- --- SIAPA, pada ledger dan dokumen --------------------------------------
-- Default membaca setelan sesi, jadi tidak satu pun INSERT yang sudah ada
-- perlu disunting untuk mengisinya.
DO $$
DECLARE
    tabel  TEXT;
    daftar TEXT[] := ARRAY[
        'stock_movements', 'stock_receipts', 'stock_issues',
        'stock_transfers', 'stock_adjustments', 'purchase_orders'
    ];
BEGIN
    FOREACH tabel IN ARRAY daftar LOOP
        EXECUTE format(
            'ALTER TABLE %I ADD COLUMN IF NOT EXISTS created_by BIGINT NULL '
            'DEFAULT NULLIF(current_setting(''app.user_id'', true), '''')::bigint',
            tabel);
    END LOOP;
END $$;

-- ==========================================================================
-- 2. STOK OPNAME
-- ==========================================================================
--
-- Tabel stock_adjustments (012/013) dipakai ulang sebagai dokumen opname.
-- Alurnya: draft (stok sistem dibekukan, hitungan diisi) -> completed
-- (disetujui admin, selisih masuk ledger sebagai 'adjustment') atau
-- cancelled. Dokumen lama berstatus 'completed' tetap sah.
--
-- actual_quantity boleh kosong selama draft: kosong berarti BELUM DIHITUNG,
-- yang berbeda dengan dihitung dan ternyata nol.

ALTER TABLE stock_adjustment_items ALTER COLUMN actual_quantity     DROP NOT NULL;
ALTER TABLE stock_adjustment_items ALTER COLUMN difference_quantity DROP NOT NULL;
ALTER TABLE stock_adjustment_items
    ADD COLUMN IF NOT EXISTS note       VARCHAR(255) NULL,
    ADD COLUMN IF NOT EXISTS counted_by BIGINT       NULL,
    ADD COLUMN IF NOT EXISTS counted_at TIMESTAMPTZ  NULL;

ALTER TABLE stock_adjustments
    ADD COLUMN IF NOT EXISTS approved_by BIGINT      NULL,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ NULL;

ALTER TABLE stock_adjustments DROP CONSTRAINT IF EXISTS stock_adjustments_status_check;
ALTER TABLE stock_adjustments
    ADD CONSTRAINT stock_adjustments_status_check
    CHECK (status IN ('draft', 'completed', 'cancelled'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_adjustment_items_dok_barang
    ON stock_adjustment_items (stock_adjustment_id, item_id);

COMMENT ON COLUMN stock_adjustment_items.actual_quantity IS
    'Hasil hitung fisik; NULL = belum dihitung';
COMMENT ON COLUMN stock_adjustment_items.system_quantity IS
    'Stok sistem: dibekukan saat draft dibuat, diperbarui ke nilai saat posting';
