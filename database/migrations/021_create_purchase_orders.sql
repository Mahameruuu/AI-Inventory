-- 021: purchase_orders
-- HEADER pesanan pembelian.
--
-- PESANAN, BUKAN PENERIMAAN. Tabel ini mencatat niat membeli; ia tidak pernah
-- menyentuh inventory maupun stock_movements. Stok baru berubah ketika barang
-- benar-benar datang, dan itu urusan stock_receipts. Memisahkan keduanya
-- adalah alasan tabel ini ada: tanpa itu, satu-satunya cara mencatat pembelian
-- adalah membuat penerimaan, yang berarti menaikkan stok barang yang belum
-- dikirim.
--
-- supplier_id SENGAJA BOLEH KOSONG. PO yang lahir dari panel Reorder hanya tahu
-- gudang, barang, dan jumlahnya -- master barang tidak menyimpan pemasok, jadi
-- tidak ada pemasok yang dapat dipilih sistem tanpa mengarang. PO berstatus
-- draft berdiri sah tanpa pemasok; pemasoknya diisi saat PO benar-benar
-- diterbitkan.

CREATE TABLE purchase_orders (
    id            BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    po_number     VARCHAR(50)  NOT NULL,
    warehouse_id  BIGINT       NOT NULL,
    supplier_id   BIGINT       NULL,
    order_date    DATE         NOT NULL,
    expected_date DATE         NULL,
    status        VARCHAR(30)  NOT NULL DEFAULT 'draft',
    source        VARCHAR(30)  NULL,
    notes         TEXT         NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT purchase_orders_po_number_unique UNIQUE (po_number),
    CONSTRAINT purchase_orders_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES warehouses (id),
    CONSTRAINT purchase_orders_supplier_id_fkey  FOREIGN KEY (supplier_id)  REFERENCES suppliers (id)
);

CREATE INDEX idx_purchase_orders_warehouse_id ON purchase_orders (warehouse_id);
CREATE INDEX idx_purchase_orders_supplier_id  ON purchase_orders (supplier_id);
CREATE INDEX idx_purchase_orders_order_date   ON purchase_orders (order_date);
CREATE INDEX idx_purchase_orders_status       ON purchase_orders (status);

COMMENT ON TABLE  purchase_orders               IS 'Header pesanan pembelian; tidak pernah mengubah stok';
COMMENT ON COLUMN purchase_orders.supplier_id   IS 'Boleh kosong pada PO draft; master barang tidak menyimpan pemasok';
COMMENT ON COLUMN purchase_orders.expected_date IS 'Perkiraan lengkap: order_date + lead time terpanjang di antara barangnya';
COMMENT ON COLUMN purchase_orders.source        IS 'Asal PO, mis. reorder_panel';
