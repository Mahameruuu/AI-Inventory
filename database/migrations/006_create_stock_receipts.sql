-- 006: stock_receipts
-- HEADER transaksi barang masuk dari supplier.

CREATE TABLE stock_receipts (
    id               BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    receipt_number   VARCHAR(50)  NOT NULL,
    supplier_id      BIGINT       NOT NULL,
    warehouse_id     BIGINT       NOT NULL,
    receipt_date     TIMESTAMPTZ  NOT NULL,
    reference_number VARCHAR(100) NULL,
    status           VARCHAR(30)  NOT NULL DEFAULT 'completed',
    notes            TEXT         NULL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT stock_receipts_receipt_number_unique UNIQUE (receipt_number),
    CONSTRAINT stock_receipts_supplier_id_fkey  FOREIGN KEY (supplier_id)  REFERENCES suppliers (id),
    CONSTRAINT stock_receipts_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
);

CREATE INDEX idx_stock_receipts_supplier_id      ON stock_receipts (supplier_id);
CREATE INDEX idx_stock_receipts_warehouse_id     ON stock_receipts (warehouse_id);
CREATE INDEX idx_stock_receipts_receipt_date     ON stock_receipts (receipt_date);
CREATE INDEX idx_stock_receipts_status           ON stock_receipts (status);
CREATE INDEX idx_stock_receipts_reference_number ON stock_receipts (reference_number);

COMMENT ON TABLE stock_receipts IS 'Header penerimaan barang';
