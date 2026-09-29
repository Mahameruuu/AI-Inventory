-- 004: suppliers
-- Master supplier. Induk dari stock_receipts.

CREATE TABLE suppliers (
    id         BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code       VARCHAR(50)  NOT NULL,
    name       VARCHAR(200) NOT NULL,
    phone      VARCHAR(30)  NULL,
    email      VARCHAR(255) NULL,
    address    TEXT         NULL,
    is_active  BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT suppliers_code_unique UNIQUE (code)
);

CREATE INDEX idx_suppliers_name      ON suppliers (name);
CREATE INDEX idx_suppliers_is_active ON suppliers (is_active);

COMMENT ON TABLE suppliers IS 'Master supplier';
