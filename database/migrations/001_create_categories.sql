-- 001: categories
-- Kategori barang. Induk dari items.

CREATE TABLE categories (
    id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    description TEXT         NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT categories_name_unique UNIQUE (name)
);

COMMENT ON TABLE categories IS 'Master kategori barang';
