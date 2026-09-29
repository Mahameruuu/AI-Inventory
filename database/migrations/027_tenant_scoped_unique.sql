-- 027: keunikan dihitung per perusahaan, bukan sedunia
--
-- Ini bagian yang paling mudah terlewat dan paling mahal bila terlewat.
--
-- items_sku_unique (sku) berarti: begitu satu klien memakai SKU "BRG-001",
-- klien mana pun sesudahnya tidak boleh memakainya lagi. Constraint yang benar
-- untuk sistem banyak-penyewa adalah (company_id, sku): dua perusahaan boleh
-- punya SKU yang sama, satu perusahaan tetap tidak boleh punya dua.
--
-- Hal yang sama berlaku untuk seluruh nomor dokumen. Nomor penerimaan,
-- pengeluaran, transfer, penyesuaian, dan PO dibangkitkan per perusahaan;
-- membiarkannya unik sedunia berarti penyewa baru mewarisi penomoran penyewa
-- lama, dan dua klien yang kebetulan memakai format nomor yang sama akan
-- saling menolak dokumen tanpa pernah tahu kenapa.
--
-- YANG SENGAJA TIDAK DIUBAH: purchase_orders_stock_receipt_id_unique. Isinya
-- id baris, bukan nomor yang ditulis manusia -- satu id penerimaan hanya
-- pernah ada di satu perusahaan, sehingga keunikan sedunia justru tepat.
--
-- Seluruh constraint di bawah kecil (paling besar stock_issues, 108 ribu
-- baris), jadi membangun ulang indeksnya berlangsung cepat.

-- --- master ---------------------------------------------------------------
ALTER TABLE categories
    DROP CONSTRAINT IF EXISTS categories_name_unique,
    ADD  CONSTRAINT categories_name_unique UNIQUE (company_id, name);

ALTER TABLE units
    DROP CONSTRAINT IF EXISTS units_name_unique,
    DROP CONSTRAINT IF EXISTS units_code_unique,
    ADD  CONSTRAINT units_name_unique UNIQUE (company_id, name),
    ADD  CONSTRAINT units_code_unique UNIQUE (company_id, code);

ALTER TABLE warehouses
    DROP CONSTRAINT IF EXISTS warehouses_code_unique,
    ADD  CONSTRAINT warehouses_code_unique UNIQUE (company_id, code);

ALTER TABLE suppliers
    DROP CONSTRAINT IF EXISTS suppliers_code_unique,
    ADD  CONSTRAINT suppliers_code_unique UNIQUE (company_id, code);

ALTER TABLE items
    DROP CONSTRAINT IF EXISTS items_sku_unique,
    ADD  CONSTRAINT items_sku_unique UNIQUE (company_id, sku);

-- --- nomor dokumen --------------------------------------------------------
ALTER TABLE stock_receipts
    DROP CONSTRAINT IF EXISTS stock_receipts_receipt_number_unique,
    ADD  CONSTRAINT stock_receipts_receipt_number_unique UNIQUE (company_id, receipt_number);

ALTER TABLE stock_issues
    DROP CONSTRAINT IF EXISTS stock_issues_issue_number_unique,
    ADD  CONSTRAINT stock_issues_issue_number_unique UNIQUE (company_id, issue_number);

ALTER TABLE stock_transfers
    DROP CONSTRAINT IF EXISTS stock_transfers_transfer_number_unique,
    ADD  CONSTRAINT stock_transfers_transfer_number_unique UNIQUE (company_id, transfer_number);

ALTER TABLE stock_adjustments
    DROP CONSTRAINT IF EXISTS stock_adjustments_adjustment_number_unique,
    ADD  CONSTRAINT stock_adjustments_adjustment_number_unique UNIQUE (company_id, adjustment_number);

ALTER TABLE purchase_orders
    DROP CONSTRAINT IF EXISTS purchase_orders_po_number_unique,
    ADD  CONSTRAINT purchase_orders_po_number_unique UNIQUE (company_id, po_number);

ALTER TABLE serial_numbers
    DROP CONSTRAINT IF EXISTS serial_numbers_serial_number_unique,
    ADD  CONSTRAINT serial_numbers_serial_number_unique UNIQUE (company_id, serial_number);

-- --- kunci gabungan yang dipakai ON CONFLICT ------------------------------
--
-- Dua constraint berikut BUKAN sekadar penjaga: keduanya disebut namanya
-- lewat daftar kolom pada klausa ON CONFLICT di app/penerimaan.py dan
-- app/jobs/scan_anomalies.py. Menambah company_id di sini mengharuskan kedua
-- klausa itu ikut menyebut company_id -- tanpa itu PostgreSQL menolak dengan
-- "no unique or exclusion constraint matching the ON CONFLICT specification".
-- Perubahan pasangannya ada di commit yang sama.
ALTER TABLE inventory
    DROP CONSTRAINT IF EXISTS inventory_item_warehouse_unique,
    ADD  CONSTRAINT inventory_item_warehouse_unique UNIQUE (company_id, item_id, warehouse_id);

ALTER TABLE stock_batches
    DROP CONSTRAINT IF EXISTS stock_batches_item_batch_unique,
    ADD  CONSTRAINT stock_batches_item_batch_unique UNIQUE (company_id, item_id, batch_number);

DROP INDEX IF EXISTS anomaly_findings_dedup;
CREATE UNIQUE INDEX anomaly_findings_dedup
    ON anomaly_findings (company_id, item_id, warehouse_id, type, event_date);
