-- 011: stock_transfer_items
-- DETAIL barang yang dipindahkan.

CREATE TABLE stock_transfer_items (
    id                BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    stock_transfer_id BIGINT       NOT NULL,
    item_id           BIGINT       NOT NULL,
    quantity          DECIMAL(18,3) NOT NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT stock_transfer_items_quantity_positive CHECK (quantity > 0),
    CONSTRAINT stock_transfer_items_stock_transfer_id_fkey
        FOREIGN KEY (stock_transfer_id) REFERENCES stock_transfers (id),
    CONSTRAINT stock_transfer_items_item_id_fkey
        FOREIGN KEY (item_id) REFERENCES items (id)
);

CREATE INDEX idx_stock_transfer_items_stock_transfer_id ON stock_transfer_items (stock_transfer_id);
CREATE INDEX idx_stock_transfer_items_item_id           ON stock_transfer_items (item_id);

COMMENT ON TABLE stock_transfer_items IS 'Detail perpindahan barang antar gudang';
