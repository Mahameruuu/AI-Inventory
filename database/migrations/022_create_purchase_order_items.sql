-- 022: purchase_order_items
-- DETAIL barang pada satu pesanan pembelian.

CREATE TABLE purchase_order_items (
    id                BIGINT        GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    purchase_order_id BIGINT        NOT NULL,
    item_id           BIGINT        NOT NULL,
    quantity          DECIMAL(18,3) NOT NULL,
    unit_price        DECIMAL(18,2) NOT NULL,
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),

    CONSTRAINT purchase_order_items_quantity_positive CHECK (quantity > 0),
    CONSTRAINT purchase_order_items_purchase_order_id_fkey
        FOREIGN KEY (purchase_order_id) REFERENCES purchase_orders (id),
    CONSTRAINT purchase_order_items_item_id_fkey
        FOREIGN KEY (item_id) REFERENCES items (id)
);

CREATE INDEX idx_purchase_order_items_purchase_order_id ON purchase_order_items (purchase_order_id);
CREATE INDEX idx_purchase_order_items_item_id           ON purchase_order_items (item_id);

COMMENT ON TABLE  purchase_order_items            IS 'Detail pesanan pembelian';
COMMENT ON COLUMN purchase_order_items.unit_price IS 'Harga saat PO dibuat; disalin dari items.unit_price bila tidak diisi';
