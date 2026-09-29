-- 008: stock_issues
-- HEADER transaksi barang keluar.

CREATE TABLE stock_issues (
    id               BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    issue_number     VARCHAR(50)  NOT NULL,
    warehouse_id     BIGINT       NOT NULL,
    issue_date       TIMESTAMPTZ  NOT NULL,
    purpose          VARCHAR(150) NULL,
    reference_number VARCHAR(100) NULL,
    status           VARCHAR(30)  NOT NULL DEFAULT 'completed',
    notes            TEXT         NULL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT stock_issues_issue_number_unique UNIQUE (issue_number),
    CONSTRAINT stock_issues_warehouse_id_fkey FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
);

CREATE INDEX idx_stock_issues_warehouse_id     ON stock_issues (warehouse_id);
CREATE INDEX idx_stock_issues_issue_date       ON stock_issues (issue_date);
CREATE INDEX idx_stock_issues_status           ON stock_issues (status);
CREATE INDEX idx_stock_issues_reference_number ON stock_issues (reference_number);

COMMENT ON TABLE stock_issues IS 'Header pengeluaran barang';
