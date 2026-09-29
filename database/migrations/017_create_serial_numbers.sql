-- 017: serial_numbers
-- Identitas unik tiap unit barang bernomor seri.

CREATE TABLE serial_numbers (
    id            BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id       BIGINT       NOT NULL,
    serial_number VARCHAR(100) NOT NULL,
    batch_id      BIGINT       NULL,
    warehouse_id  BIGINT       NULL,
    status        VARCHAR(30)  NOT NULL DEFAULT 'available',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT serial_numbers_serial_number_unique UNIQUE (serial_number),
    CONSTRAINT serial_numbers_item_id_fkey      FOREIGN KEY (item_id)      REFERENCES items (id),
    CONSTRAINT serial_numbers_batch_id_fkey     FOREIGN KEY (batch_id)     REFERENCES stock_batches (id),
    CONSTRAINT serial_numbers_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
);

CREATE INDEX idx_serial_numbers_item_id      ON serial_numbers (item_id);
CREATE INDEX idx_serial_numbers_batch_id     ON serial_numbers (batch_id);
CREATE INDEX idx_serial_numbers_warehouse_id ON serial_numbers (warehouse_id);
CREATE INDEX idx_serial_numbers_status       ON serial_numbers (status);

COMMENT ON TABLE  serial_numbers        IS 'Unit barang bernomor seri';
COMMENT ON COLUMN serial_numbers.status IS 'Teks bebas, bawaan available';
