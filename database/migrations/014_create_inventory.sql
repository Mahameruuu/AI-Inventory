-- 014: inventory
-- KONDISI STOK SAAT INI, bukan riwayat.
-- Satu kombinasi item + warehouse hanya boleh punya satu baris.

CREATE TABLE inventory (
    id                 BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id            BIGINT       NOT NULL,
    warehouse_id       BIGINT       NOT NULL,
    quantity           DECIMAL(18,3) NOT NULL DEFAULT 0,
    reserved_quantity  DECIMAL(18,3) NOT NULL DEFAULT 0,
    available_quantity DECIMAL(18,3) NOT NULL DEFAULT 0,
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT inventory_item_warehouse_unique UNIQUE (item_id, warehouse_id),
    CONSTRAINT inventory_item_id_fkey      FOREIGN KEY (item_id)      REFERENCES items (id),
    CONSTRAINT inventory_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
);

-- (item_id, warehouse_id) sudah terindeks oleh UNIQUE di atas.
-- warehouse_id perlu indeks sendiri karena bukan kolom pertama pada indeks itu.
CREATE INDEX idx_inventory_warehouse_id ON inventory (warehouse_id);

COMMENT ON TABLE  inventory                    IS 'Stok berjalan per barang per gudang';
COMMENT ON COLUMN inventory.available_quantity IS 'quantity - reserved_quantity; diisi oleh aplikasi, tanpa trigger pada tahap ini';
