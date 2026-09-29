-- 012: stock_adjustments
-- HEADER penyesuaian stok (stock opname, koreksi selisih fisik).

CREATE TABLE stock_adjustments (
    id                BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    adjustment_number VARCHAR(50)  NOT NULL,
    warehouse_id      BIGINT       NOT NULL,
    adjustment_date   TIMESTAMPTZ  NOT NULL,
    reason            VARCHAR(200) NOT NULL,
    status            VARCHAR(30)  NOT NULL DEFAULT 'completed',
    notes             TEXT         NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT stock_adjustments_adjustment_number_unique UNIQUE (adjustment_number),
    CONSTRAINT stock_adjustments_warehouse_id_fkey
        FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
);

CREATE INDEX idx_stock_adjustments_warehouse_id    ON stock_adjustments (warehouse_id);
CREATE INDEX idx_stock_adjustments_adjustment_date ON stock_adjustments (adjustment_date);
CREATE INDEX idx_stock_adjustments_status          ON stock_adjustments (status);

COMMENT ON TABLE stock_adjustments IS 'Header penyesuaian stok';
