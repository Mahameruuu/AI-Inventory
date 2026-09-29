-- 035: moda angkut, biaya, dan jumlah diterima pada transfer antar gudang
--
-- Bahan bagi rekomendasi rute berbasis riwayat (app/rute_ml.py): apa yang
-- DIPILIH (moda), apa yang TERJADI (biaya, lama di jalan, jumlah yang sampai).
-- Lama di jalan tidak disimpan sebagai kolom: ia selisih shipped_at dan
-- received_at, yang sudah ada sejak migrasi 031.
--
--   transport_mode      darat | laut | udara
--   shipping_cost       biaya angkut sesungguhnya (rupiah)
--   planned_days        janji lama tempuh saat dokumen diajukan
--   received_quantity   jumlah yang benar-benar diterima; selisihnya dengan
--                       quantity adalah rusak/hilang di jalan
--
-- Hanya menambah kolom, semuanya boleh kosong: dokumen lama tetap sah.

ALTER TABLE stock_transfers
    ADD COLUMN IF NOT EXISTS transport_mode VARCHAR(10)    NULL,
    ADD COLUMN IF NOT EXISTS shipping_cost  DECIMAL(16,2)  NULL,
    ADD COLUMN IF NOT EXISTS planned_days   DECIMAL(6,2)   NULL;

ALTER TABLE stock_transfers DROP CONSTRAINT IF EXISTS stock_transfers_transport_mode_check;
ALTER TABLE stock_transfers
    ADD CONSTRAINT stock_transfers_transport_mode_check
    CHECK (transport_mode IS NULL OR transport_mode IN ('darat', 'laut', 'udara'));

ALTER TABLE stock_transfers DROP CONSTRAINT IF EXISTS stock_transfers_shipping_cost_check;
ALTER TABLE stock_transfers
    ADD CONSTRAINT stock_transfers_shipping_cost_check
    CHECK (shipping_cost IS NULL OR shipping_cost >= 0);

ALTER TABLE stock_transfer_items
    ADD COLUMN IF NOT EXISTS received_quantity DECIMAL(18,3) NULL;

ALTER TABLE stock_transfer_items DROP CONSTRAINT IF EXISTS stock_transfer_items_received_check;
ALTER TABLE stock_transfer_items
    ADD CONSTRAINT stock_transfer_items_received_check
    CHECK (received_quantity IS NULL OR (received_quantity >= 0 AND received_quantity <= quantity));

COMMENT ON COLUMN stock_transfers.transport_mode IS 'darat | laut | udara';
COMMENT ON COLUMN stock_transfers.shipping_cost IS 'Biaya angkut sesungguhnya (rupiah)';
COMMENT ON COLUMN stock_transfers.planned_days IS 'Janji lama tempuh saat diajukan (hari)';
COMMENT ON COLUMN stock_transfer_items.received_quantity IS
    'Jumlah yang benar-benar diterima; NULL = belum diterima atau tidak dicatat';
