-- 016: stock_batches
-- Informasi batch/lot barang.

CREATE TABLE stock_batches (
    id            BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id       BIGINT       NOT NULL,
    batch_number  VARCHAR(100) NOT NULL,
    received_date DATE         NOT NULL,
    expiry_date   DATE         NULL,
    quantity      DECIMAL(18,3) NOT NULL DEFAULT 0,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT stock_batches_item_batch_unique UNIQUE (item_id, batch_number),
    CONSTRAINT stock_batches_item_id_fkey FOREIGN KEY (item_id) REFERENCES items (id)
);

-- item_id sudah menjadi kolom pertama pada UNIQUE di atas, jadi tidak diindeks ulang.
CREATE INDEX idx_stock_batches_batch_number  ON stock_batches (batch_number);
CREATE INDEX idx_stock_batches_received_date ON stock_batches (received_date);
CREATE INDEX idx_stock_batches_expiry_date   ON stock_batches (expiry_date);

COMMENT ON TABLE stock_batches IS 'Batch/lot barang beserta tanggal terima dan kedaluwarsa';
