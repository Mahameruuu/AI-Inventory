-- 015: stock_movements
-- Riwayat seluruh pergerakan stok (historical inventory ledger).

CREATE TABLE stock_movements (
    id            BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id       BIGINT       NOT NULL,
    warehouse_id  BIGINT       NOT NULL,
    movement_type VARCHAR(30)  NOT NULL,
    reference_id  BIGINT       NULL,
    movement_date TIMESTAMPTZ  NOT NULL,
    quantity      DECIMAL(18,3) NOT NULL,
    unit_price    DECIMAL(18,2) NULL,
    batch_number  VARCHAR(100) NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT stock_movements_item_id_fkey      FOREIGN KEY (item_id)      REFERENCES items (id),
    CONSTRAINT stock_movements_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
);

CREATE INDEX idx_stock_movements_item_id       ON stock_movements (item_id);
CREATE INDEX idx_stock_movements_warehouse_id  ON stock_movements (warehouse_id);
CREATE INDEX idx_stock_movements_movement_date ON stock_movements (movement_date);
CREATE INDEX idx_stock_movements_movement_type ON stock_movements (movement_type);
CREATE INDEX idx_stock_movements_reference_id  ON stock_movements (reference_id);
CREATE INDEX idx_stock_movements_batch_number  ON stock_movements (batch_number);
-- pola baca paling sering: pergerakan satu barang di satu gudang secara kronologis
CREATE INDEX idx_stock_movements_item_warehouse_date
    ON stock_movements (item_id, warehouse_id, movement_date);

COMMENT ON TABLE  stock_movements               IS 'Buku besar pergerakan stok';
COMMENT ON COLUMN stock_movements.quantity      IS 'Bertanda: masuk/transfer_in positif, keluar/transfer_out negatif, adjustment bisa keduanya';
COMMENT ON COLUMN stock_movements.reference_id  IS 'ID transaksi sumber; jenis sumbernya ditentukan movement_type, sengaja tanpa foreign key';
COMMENT ON COLUMN stock_movements.movement_type IS 'Teks bebas: stock_in / stock_out / transfer_in / transfer_out / adjustment / return';
