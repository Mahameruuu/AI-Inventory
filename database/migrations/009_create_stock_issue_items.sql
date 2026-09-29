-- 009: stock_issue_items
-- DETAIL barang yang keluar.

CREATE TABLE stock_issue_items (
    id             BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stock_issue_id BIGINT       NOT NULL,
    item_id        BIGINT       NOT NULL,
    quantity       DECIMAL(18,3) NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT stock_issue_items_quantity_positive CHECK (quantity > 0),
    CONSTRAINT stock_issue_items_stock_issue_id_fkey
        FOREIGN KEY (stock_issue_id) REFERENCES stock_issues (id),
    CONSTRAINT stock_issue_items_item_id_fkey
        FOREIGN KEY (item_id) REFERENCES items (id)
);

CREATE INDEX idx_stock_issue_items_stock_issue_id ON stock_issue_items (stock_issue_id);
CREATE INDEX idx_stock_issue_items_item_id        ON stock_issue_items (item_id);

COMMENT ON TABLE  stock_issue_items          IS 'Detail pengeluaran barang';
COMMENT ON COLUMN stock_issue_items.quantity IS 'Selalu positif; arah keluar dicatat di stock_movements';
