-- 013: stock_adjustment_items
-- DETAIL hasil penyesuaian stok.

CREATE TABLE stock_adjustment_items (
    id                  BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stock_adjustment_id BIGINT       NOT NULL,
    item_id             BIGINT       NOT NULL,
    system_quantity     DECIMAL(18,3) NOT NULL,
    actual_quantity     DECIMAL(18,3) NOT NULL,
    difference_quantity DECIMAL(18,3) NOT NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT stock_adjustment_items_stock_adjustment_id_fkey
        FOREIGN KEY (stock_adjustment_id) REFERENCES stock_adjustments (id),
    CONSTRAINT stock_adjustment_items_item_id_fkey
        FOREIGN KEY (item_id) REFERENCES items (id)
);

CREATE INDEX idx_stock_adjustment_items_stock_adjustment_id ON stock_adjustment_items (stock_adjustment_id);
CREATE INDEX idx_stock_adjustment_items_item_id             ON stock_adjustment_items (item_id);

COMMENT ON TABLE  stock_adjustment_items                     IS 'Detail penyesuaian stok';
COMMENT ON COLUMN stock_adjustment_items.difference_quantity IS 'actual_quantity - system_quantity; diisi oleh aplikasi, tidak dipaksa constraint';
