-- 031: Transfer Antar Gudang
--
-- Modul ini menjawab satu pertanyaan yang selama ini tidak pernah ditanyakan
-- sistem: SEBELUM membeli, apakah barangnya sudah ada di gudang lain?
--
-- Tabel stock_transfers dan stock_transfer_items sudah lahir sejak migrasi
-- 010/011 dan sengaja TIDAK dibuat ulang di sini. Yang ditambahkan hanyalah
-- keterangan yang dituntut alur baru: koordinat gudang (supaya jarak dapat
-- dihitung), jarak/lead time yang ditetapkan tangan (supaya jarak jalan darat
-- dapat mengalahkan jarak garis lurus), dan jejak keputusan pada tiap dokumen
-- transfer (skor, alasan, jarak, cap waktu tiap tahap).
--
-- KENAPA SKOR DAN ALASAN IKUT DISIMPAN PADA DOKUMEN. Rekomendasi dihitung
-- ulang setiap kali halaman dibuka, dari stok yang berlaku SAAT ITU. Dokumen
-- yang sudah diajukan tidak boleh ikut berubah alasannya: yang perlu dijawab
-- sebulan kemudian adalah "kenapa waktu itu gudang ini yang dipilih", dan
-- jawabannya harus angka yang berlaku saat pengajuan, bukan angka hari ini.

\set ON_ERROR_STOP on

-- --- koordinat dan waktu tempuh gudang ------------------------------------
--
-- Boleh kosong, dan itu disengaja. Gudang tanpa koordinat tetap dapat menjadi
-- sumber transfer; yang hilang hanyalah komponen jarak pada skornya, dan
-- mesin menyatakannya apa adanya alih-alih memakai nol (yang berarti "paling
-- dekat" dan akan memenangkan gudang yang justru tidak diketahui letaknya).
ALTER TABLE warehouses
    ADD COLUMN IF NOT EXISTS latitude                DECIMAL(9,6) NULL,
    ADD COLUMN IF NOT EXISTS longitude               DECIMAL(9,6) NULL,
    ADD COLUMN IF NOT EXISTS transfer_lead_time_days INTEGER      NULL;

COMMENT ON COLUMN warehouses.latitude IS
    'Lintang desimal; dipakai menghitung jarak haversine antar gudang';
COMMENT ON COLUMN warehouses.longitude IS
    'Bujur desimal; dipakai menghitung jarak haversine antar gudang';
COMMENT ON COLUMN warehouses.transfer_lead_time_days IS
    'Waktu tempuh khas kiriman KE gudang ini dalam hari; dipakai bila pasangan gudangnya tidak ada di warehouse_distances';

ALTER TABLE warehouses
    DROP CONSTRAINT IF EXISTS warehouses_latitude_range,
    DROP CONSTRAINT IF EXISTS warehouses_longitude_range,
    DROP CONSTRAINT IF EXISTS warehouses_transfer_lead_time_non_negative,
    ADD  CONSTRAINT warehouses_latitude_range
         CHECK (latitude  IS NULL OR (latitude  BETWEEN  -90 AND  90)),
    ADD  CONSTRAINT warehouses_longitude_range
         CHECK (longitude IS NULL OR (longitude BETWEEN -180 AND 180)),
    ADD  CONSTRAINT warehouses_transfer_lead_time_non_negative
         CHECK (transfer_lead_time_days IS NULL OR transfer_lead_time_days >= 0);

-- --- jarak antar gudang yang ditetapkan tangan ----------------------------
--
-- KENAPA TABEL SENDIRI, BUKAN HANYA HAVERSINE. Jarak garis lurus Surabaya ->
-- Jakarta 660 km; jarak jalan darat yang benar-benar ditempuh truk 780 km, dan
-- lewat penyeberangan angkanya bisa berbeda jauh lagi. Selama yang diperingkat
-- adalah "gudang mana yang paling murah dan cepat mengirim", angka yang benar
-- adalah yang ditempuh, bukan yang diukur di peta.
--
-- Barisnya BERARAH: A->B tidak selalu sama dengan B->A (satu arah menanjak,
-- satu arah searah jalan tol). Yang tidak punya baris jatuh ke haversine.
CREATE TABLE IF NOT EXISTS warehouse_distances (
    id                BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    company_id        BIGINT       NOT NULL
        DEFAULT NULLIF(current_setting('app.company_id', true), '')::bigint,
    from_warehouse_id BIGINT       NOT NULL,
    to_warehouse_id   BIGINT       NOT NULL,
    distance_km       DECIMAL(10,2) NULL,
    lead_time_days    INTEGER      NULL,
    notes             TEXT         NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT warehouse_distances_pair_unique
        UNIQUE (company_id, from_warehouse_id, to_warehouse_id),
    CONSTRAINT warehouse_distances_different
        CHECK (from_warehouse_id <> to_warehouse_id),
    CONSTRAINT warehouse_distances_km_non_negative
        CHECK (distance_km IS NULL OR distance_km >= 0),
    CONSTRAINT warehouse_distances_lead_non_negative
        CHECK (lead_time_days IS NULL OR lead_time_days >= 0),
    CONSTRAINT warehouse_distances_company_id_fkey
        FOREIGN KEY (company_id) REFERENCES companies (id),
    CONSTRAINT warehouse_distances_from_warehouse_id_fkey
        FOREIGN KEY (from_warehouse_id) REFERENCES warehouses (id),
    CONSTRAINT warehouse_distances_to_warehouse_id_fkey
        FOREIGN KEY (to_warehouse_id)   REFERENCES warehouses (id)
);

CREATE INDEX IF NOT EXISTS idx_warehouse_distances_company_id
    ON warehouse_distances (company_id);
CREATE INDEX IF NOT EXISTS idx_warehouse_distances_from
    ON warehouse_distances (from_warehouse_id);
CREATE INDEX IF NOT EXISTS idx_warehouse_distances_to
    ON warehouse_distances (to_warehouse_id);

COMMENT ON TABLE warehouse_distances IS
    'Jarak dan waktu tempuh antar gudang yang ditetapkan tangan; mengalahkan haversine bila ada';

-- Row Level Security. Migrasi 028 memasang policy atas daftar tabel yang
-- TETAP; tabel yang lahir sesudahnya tidak ikut terlindungi olehnya, dan
-- tabel tanpa policy terbaca oleh SELURUH penyewa tanpa satu pun galat yang
-- terbit. Karena itu policy-nya dipasang di sini, dalam bentuk yang sama
-- persis.
ALTER TABLE warehouse_distances ENABLE ROW LEVEL SECURITY;
ALTER TABLE warehouse_distances FORCE  ROW LEVEL SECURITY;
DROP POLICY IF EXISTS warehouse_distances_penyewa ON warehouse_distances;
CREATE POLICY warehouse_distances_penyewa ON warehouse_distances
    USING      (company_id = NULLIF(current_setting('app.company_id', true), '')::bigint)
    WITH CHECK (company_id = NULLIF(current_setting('app.company_id', true), '')::bigint);

GRANT SELECT, INSERT, UPDATE, DELETE ON warehouse_distances TO inventory_app;

-- --- jejak keputusan pada dokumen transfer --------------------------------
ALTER TABLE stock_transfers
    ADD COLUMN IF NOT EXISTS source        VARCHAR(30)   NULL,
    ADD COLUMN IF NOT EXISTS score         INTEGER       NULL,
    ADD COLUMN IF NOT EXISTS reason        TEXT          NULL,
    ADD COLUMN IF NOT EXISTS distance_km   DECIMAL(10,2) NULL,
    ADD COLUMN IF NOT EXISTS approved_at   TIMESTAMPTZ   NULL,
    ADD COLUMN IF NOT EXISTS shipped_at    TIMESTAMPTZ   NULL,
    ADD COLUMN IF NOT EXISTS received_at   TIMESTAMPTZ   NULL,
    ADD COLUMN IF NOT EXISTS cancelled_at  TIMESTAMPTZ   NULL;

COMMENT ON COLUMN stock_transfers.source IS
    'Asal usul dokumen: transfer_engine bila lahir dari rekomendasi, manual bila diketik orang';
COMMENT ON COLUMN stock_transfers.score IS
    'Skor kandidat SAAT PENGAJUAN, 0-100; dibekukan supaya alasan dokumen lama tidak ikut berubah';
COMMENT ON COLUMN stock_transfers.reason IS
    'Kalimat alasan pemilihan gudang asal, dibekukan saat pengajuan';

-- --- alur status ----------------------------------------------------------
--
-- Bawaan lama 'completed' diganti 'draft'. Dokumen transfer kini punya empat
-- tahap yang benar-benar menyentuh stok pada waktu yang berbeda, dan bawaan
-- "sudah selesai" berarti satu INSERT yang lupa menyebut status menyatakan
-- barang sudah sampai padahal belum bergerak sama sekali.
--
--   draft       diajukan, belum menyentuh stok
--   approved    disetujui; stok asal DICADANGKAN (reserved_quantity naik)
--   in_transit  dikirim; stok asal benar-benar berkurang
--   completed   diterima; stok tujuan bertambah
--   cancelled   dibatalkan sebelum dikirim; cadangan dilepas
ALTER TABLE stock_transfers ALTER COLUMN status SET DEFAULT 'draft';

ALTER TABLE stock_transfers
    DROP CONSTRAINT IF EXISTS stock_transfers_status_valid,
    ADD  CONSTRAINT stock_transfers_status_valid
         CHECK (status IN ('draft', 'approved', 'in_transit', 'completed', 'cancelled'));

-- --- barang tujuan yang ditutup satu baris transfer -----------------------
--
-- Biasanya sama dengan item_id: barang yang dikirim adalah barang yang
-- dibutuhkan. Ia BERBEDA tepat ketika kandidatnya ditemukan lewat pencocokan
-- fuzzy -- dua nomor barang berbeda yang ternyata merujuk barang yang sama.
-- Yang dikirim tetap barang milik gudang asal (itu yang ada fisiknya), dan
-- kolom ini mencatat kebutuhan barang mana yang hendak ditutupnya. Tanpa
-- kolom ini, dokumennya terbaca seolah gudang tujuan meminta barang yang tidak
-- pernah dimintanya.
ALTER TABLE stock_transfer_items
    ADD COLUMN IF NOT EXISTS for_item_id      BIGINT NULL,
    ADD COLUMN IF NOT EXISTS match_type       VARCHAR(20) NULL,
    ADD COLUMN IF NOT EXISTS match_similarity DECIMAL(5,4) NULL;

ALTER TABLE stock_transfer_items
    DROP CONSTRAINT IF EXISTS stock_transfer_items_for_item_id_fkey,
    ADD  CONSTRAINT stock_transfer_items_for_item_id_fkey
         FOREIGN KEY (for_item_id) REFERENCES items (id);

COMMENT ON COLUMN stock_transfer_items.for_item_id IS
    'Barang di gudang TUJUAN yang kebutuhannya ditutup baris ini; NULL berarti sama dengan item_id';
COMMENT ON COLUMN stock_transfer_items.match_type IS
    'sku bila cocok pasti lewat nomor barang, fuzzy bila lewat kemiripan nama';
COMMENT ON COLUMN stock_transfer_items.match_similarity IS
    'Kemiripan nama 0-1 pada pencocokan fuzzy; NULL untuk cocok pasti';
