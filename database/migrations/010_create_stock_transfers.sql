-- 010: stock_transfers
-- HEADER perpindahan barang antar gudang.

CREATE TABLE stock_transfers (
    id                BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    transfer_number   VARCHAR(50) NOT NULL,
    from_warehouse_id BIGINT      NOT NULL,
    to_warehouse_id   BIGINT      NOT NULL,
    transfer_date     TIMESTAMPTZ NOT NULL,
    status            VARCHAR(30) NOT NULL DEFAULT 'completed',
    notes             TEXT        NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT stock_transfers_transfer_number_unique UNIQUE (transfer_number),
    CONSTRAINT stock_transfers_warehouse_different CHECK (from_warehouse_id <> to_warehouse_id),
    CONSTRAINT stock_transfers_from_warehouse_id_fkey
        FOREIGN KEY (from_warehouse_id) REFERENCES warehouses (id),
    CONSTRAINT stock_transfers_to_warehouse_id_fkey
        FOREIGN KEY (to_warehouse_id)   REFERENCES warehouses (id)
);

CREATE INDEX idx_stock_transfers_from_warehouse_id ON stock_transfers (from_warehouse_id);
CREATE INDEX idx_stock_transfers_to_warehouse_id   ON stock_transfers (to_warehouse_id);
CREATE INDEX idx_stock_transfers_transfer_date     ON stock_transfers (transfer_date);
CREATE INDEX idx_stock_transfers_status            ON stock_transfers (status);

COMMENT ON TABLE stock_transfers IS 'Header perpindahan barang antar gudang';
