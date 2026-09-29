-- 023: purchase_orders.stock_receipt_id
--
-- Menghubungkan PO dengan penerimaan barang yang lahir darinya.
--
-- Tanpa kolom ini, "PO ini sudah diterima" hanya berupa kata pada kolom status
-- dan tidak dapat ditelusuri ke barang yang benar-benar masuk rak. Dengan kolom
-- ini, setiap PO berstatus received menunjuk tepat satu GR, dan pertanyaan
-- "penerimaan ini asalnya PO mana" punya jawaban yang tidak perlu ditebak dari
-- nomor referensi.
--
-- NULL sampai PO benar-benar diterima; UNIQUE karena satu penerimaan tidak
-- boleh diklaim oleh dua PO sekaligus.

ALTER TABLE purchase_orders
    ADD COLUMN stock_receipt_id BIGINT NULL,
    ADD CONSTRAINT purchase_orders_stock_receipt_id_fkey
        FOREIGN KEY (stock_receipt_id) REFERENCES stock_receipts (id),
    ADD CONSTRAINT purchase_orders_stock_receipt_id_unique UNIQUE (stock_receipt_id);

COMMENT ON COLUMN purchase_orders.stock_receipt_id
    IS 'Penerimaan barang yang lahir dari PO ini; NULL selama belum diterima';
