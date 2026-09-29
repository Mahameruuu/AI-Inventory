-- 002: units
-- Satuan barang (UNIT, PCS, KG, LITER, BOX). Induk dari items.

CREATE TABLE units (
    id         BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    code       VARCHAR(20)  NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT units_name_unique UNIQUE (name),
    CONSTRAINT units_code_unique UNIQUE (code)
);

COMMENT ON TABLE units IS 'Master satuan barang';
