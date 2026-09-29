-- 003: warehouses
-- Lokasi gudang. Dirujuk oleh seluruh transaksi dan inventory.

CREATE TABLE warehouses (
    id         BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code       VARCHAR(50)  NOT NULL,
    name       VARCHAR(150) NOT NULL,
    location   VARCHAR(255) NULL,
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT warehouses_code_unique UNIQUE (code)
);

CREATE INDEX idx_warehouses_is_active ON warehouses (is_active);

COMMENT ON TABLE warehouses IS 'Master lokasi gudang';
