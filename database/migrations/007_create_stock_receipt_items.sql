-- 007: stock_receipt_items
-- DETAIL barang pada satu penerimaan.

CREATE TABLE stock_receipt_items (
    id               BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stock_receipt_id BIGINT       NOT NULL,
    item_id          BIGINT       NOT NULL,
    quantity         DECIMAL(18,3) NOT NULL,
    unit_price       DECIMAL(18,2) NOT NULL,
    batch_number     VARCHAR(100) NULL,
    serial_number    VARCHAR(100) NULL,
    received_date    DATE         NOT NULL,
    expiry_date      DATE         NULL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT stock_receipt_items_quantity_positive CHECK (quantity > 0),
    CONSTRAINT stock_receipt_items_stock_receipt_id_fkey
        FOREIGN KEY (stock_receipt_id) REFERENCES stock_receipts (id),
    CONSTRAINT stock_receipt_items_item_id_fkey
        FOREIGN KEY (item_id) REFERENCES items (id)
);

CREATE INDEX idx_stock_receipt_items_stock_receipt_id ON stock_receipt_items (stock_receipt_id);
CREATE INDEX idx_stock_receipt_items_item_id          ON stock_receipt_items (item_id);
CREATE INDEX idx_stock_receipt_items_received_date    ON stock_receipt_items (received_date);
CREATE INDEX idx_stock_receipt_items_batch_number     ON stock_receipt_items (batch_number);
CREATE INDEX idx_stock_receipt_items_expiry_date      ON stock_receipt_items (expiry_date);

COMMENT ON TABLE  stock_receipt_items            IS 'Detail penerimaan barang';
COMMENT ON COLUMN stock_receipt_items.unit_price IS 'Harga saat diterima; dapat berbeda dari items.unit_price';
