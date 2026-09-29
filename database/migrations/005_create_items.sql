-- 005: items
-- Master seluruh barang inventory.

CREATE TABLE items (
    id            BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sku           VARCHAR(50)  NOT NULL,
    name          VARCHAR(255) NOT NULL,
    category_id   BIGINT       NOT NULL,
    unit_id       BIGINT       NOT NULL,
    unit_price    DECIMAL(18,2) NOT NULL DEFAULT 0,
    minimum_stock DECIMAL(18,3) NOT NULL DEFAULT 0,
    maximum_stock DECIMAL(18,3) NULL,
    reorder_point DECIMAL(18,3) NULL,
    criticality   VARCHAR(20)  NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT items_sku_unique      UNIQUE (sku),
    CONSTRAINT items_category_id_fkey FOREIGN KEY (category_id) REFERENCES categories (id),
    CONSTRAINT items_unit_id_fkey     FOREIGN KEY (unit_id)     REFERENCES units (id)
);

CREATE INDEX idx_items_category_id ON items (category_id);
CREATE INDEX idx_items_unit_id     ON items (unit_id);
CREATE INDEX idx_items_name        ON items (name);
CREATE INDEX idx_items_is_active   ON items (is_active);

COMMENT ON TABLE  items            IS 'Master barang inventory';
COMMENT ON COLUMN items.unit_price IS 'Harga satuan referensi; harga transaksi disimpan terpisah pada stock_receipt_items';
COMMENT ON COLUMN items.criticality IS 'Teks bebas: critical / high / medium / low';
