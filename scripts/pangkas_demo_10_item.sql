-- Memangkas penyewa Demo Inventory AI (company_id = 2) agar berbentuk sama
-- dengan Perusahaan Utama: dua gudang, dan SEPULUH item di tiap gudang, di
-- mana satu item hanya tinggal di satu gudang.
--
-- MENGAPA "satu item satu gudang". Itulah bentuk yang sudah berlaku di
-- Perusahaan Utama sesudah pemangkasan 31 Agustus 2026: 20 item, 10 per gudang,
-- tidak beririsan, dan tidak satu pun pergerakan stok jatuh di gudang selain
-- gudang itemnya. Demo dibuat mengikuti bentuk itu supaya kedua penyewa bisa
-- dibandingkan tanpa kejutan.
--
-- CARA MEMILIH. Item dipilih dari yang riwayat pergerakannya paling panjang di
-- gudang bersangkutan -- Surabaya lebih dulu karena riwayatnya lebih tipis dan
-- akan kalah bila memilih belakangan -- sebab prakiraan permintaan menuntut
-- histori; item bersejarah pendek akan tampil "Insufficient Data" dan membuat
-- halaman AI kosong justru di penyewa yang gunanya memperagakan halaman itu.
--
-- SETIAP PERINTAH MENYEBUT company_id = 2. Row Level Security TIDAK menolong di
-- sini: berkas ini dijalankan sebagai inventory_admin, yang superuser sekaligus
-- BYPASSRLS, sehingga kebijakan penyewa tidak pernah diterapkan padanya.
-- Percobaan pertama berkas ini mengandalkan `SET app.company_id` dan diam-diam
-- ikut menghapus 3.589 pergerakan milik Perusahaan Utama. Menyandarkan
-- pemisahan penyewa pada RLS hanya sah untuk role aplikasi.
BEGIN;

-- 1. Sepuluh item untuk tiap gudang, beserta gudang tempatnya bertahan.
CREATE TEMP TABLE pilihan ON COMMIT DROP AS
WITH sby AS (
    SELECT item_id, 73::bigint AS warehouse_id
    FROM (SELECT item_id, row_number() OVER (ORDER BY count(*) DESC, item_id) AS rn
          FROM stock_movements WHERE company_id = 2 AND warehouse_id = 73
          GROUP BY item_id) p
    WHERE rn <= 10
), jkt AS (
    SELECT item_id, 72::bigint AS warehouse_id
    FROM (SELECT item_id, row_number() OVER (ORDER BY count(*) DESC, item_id) AS rn
          FROM stock_movements
          WHERE company_id = 2 AND warehouse_id = 72
            AND item_id NOT IN (SELECT item_id FROM sby)
          GROUP BY item_id) p
    WHERE rn <= 10
)
SELECT * FROM sby UNION ALL SELECT * FROM jkt;

-- Berhenti bila pilihannya tidak genap 20, atau bila ada item terpilih yang
-- ternyata tak punya baris inventory di gudangnya; lebih baik gagal daripada
-- memangkas separuh data atas dasar yang salah.
DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM pilihan;
    IF n <> 20 THEN RAISE EXCEPTION 'Pilihan item berjumlah %, seharusnya 20', n; END IF;

    SELECT count(*) INTO n FROM pilihan p
      WHERE NOT EXISTS (SELECT 1 FROM inventory i
                        WHERE i.company_id = 2 AND i.item_id = p.item_id
                          AND i.warehouse_id = p.warehouse_id);
    IF n <> 0 THEN RAISE EXCEPTION '% item terpilih tanpa baris inventory di gudangnya', n; END IF;
END $$;

-- 2. Pasangan (item, gudang) yang harus lenyap: item terbuang di gudang mana
--    pun, dan item terpilih di gudang yang bukan gudangnya. Hanya milik
--    penyewa 2 -- perhatikan kedua penyaring company_id di bawah.
CREATE TEMP TABLE buang_pasangan ON COMMIT DROP AS
SELECT i.id AS item_id, w.id AS warehouse_id
FROM items i CROSS JOIN warehouses w
WHERE i.company_id = 2 AND w.company_id = 2
  AND NOT EXISTS (SELECT 1 FROM pilihan p
                  WHERE p.item_id = i.id AND p.warehouse_id = w.id);

-- 3. Baris rinci lebih dulu, induknya menyusul.
DELETE FROM serial_numbers s USING buang_pasangan b
  WHERE s.company_id = 2 AND s.item_id = b.item_id AND s.warehouse_id = b.warehouse_id;
DELETE FROM stock_batches
  WHERE company_id = 2 AND item_id NOT IN (SELECT item_id FROM pilihan);
DELETE FROM stock_movements m USING buang_pasangan b
  WHERE m.company_id = 2 AND m.item_id = b.item_id AND m.warehouse_id = b.warehouse_id;
DELETE FROM inventory i USING buang_pasangan b
  WHERE i.company_id = 2 AND i.item_id = b.item_id AND i.warehouse_id = b.warehouse_id;

DELETE FROM stock_receipt_items ri USING stock_receipts r, buang_pasangan b
  WHERE ri.company_id = 2 AND ri.stock_receipt_id = r.id
    AND ri.item_id = b.item_id AND r.warehouse_id = b.warehouse_id;
DELETE FROM stock_issue_items ii USING stock_issues s, buang_pasangan b
  WHERE ii.company_id = 2 AND ii.stock_issue_id = s.id
    AND ii.item_id = b.item_id AND s.warehouse_id = b.warehouse_id;
DELETE FROM purchase_order_items pi USING purchase_orders po, buang_pasangan b
  WHERE pi.company_id = 2 AND pi.purchase_order_id = po.id
    AND pi.item_id = b.item_id AND po.warehouse_id = b.warehouse_id;
DELETE FROM stock_adjustment_items ai USING stock_adjustments adj, buang_pasangan b
  WHERE ai.company_id = 2 AND ai.stock_adjustment_id = adj.id
    AND ai.item_id = b.item_id AND adj.warehouse_id = b.warehouse_id;
DELETE FROM stock_transfer_items ti USING stock_transfers t, buang_pasangan b
  WHERE ti.company_id = 2 AND ti.stock_transfer_id = t.id AND ti.item_id = b.item_id
    AND (t.from_warehouse_id = b.warehouse_id OR t.to_warehouse_id = b.warehouse_id);

-- 4. Dokumen yang kehilangan seluruh barisnya. Pesanan pembelian didahulukan
--    karena ia menunjuk ke penerimaan; dan penerimaan yang masih ditunjuk
--    pesanan yang bertahan dilepas tautannya dulu, kalau tidak penghapusannya
--    ditolak kunci asing.
DELETE FROM purchase_orders po WHERE po.company_id = 2
  AND NOT EXISTS (SELECT 1 FROM purchase_order_items pi WHERE pi.purchase_order_id = po.id);
UPDATE purchase_orders po SET stock_receipt_id = NULL
  WHERE po.company_id = 2 AND stock_receipt_id IS NOT NULL
    AND NOT EXISTS (SELECT 1 FROM stock_receipt_items ri WHERE ri.stock_receipt_id = po.stock_receipt_id);
DELETE FROM stock_receipts r WHERE r.company_id = 2
  AND NOT EXISTS (SELECT 1 FROM stock_receipt_items ri WHERE ri.stock_receipt_id = r.id);
DELETE FROM stock_issues s WHERE s.company_id = 2
  AND NOT EXISTS (SELECT 1 FROM stock_issue_items ii WHERE ii.stock_issue_id = s.id);
DELETE FROM stock_adjustments adj WHERE adj.company_id = 2
  AND NOT EXISTS (SELECT 1 FROM stock_adjustment_items ai WHERE ai.stock_adjustment_id = adj.id);
DELETE FROM stock_transfers t WHERE t.company_id = 2
  AND NOT EXISTS (SELECT 1 FROM stock_transfer_items ti WHERE ti.stock_transfer_id = t.id);

-- 5. Barulah itemnya sendiri.
DELETE FROM items WHERE company_id = 2 AND id NOT IN (SELECT item_id FROM pilihan);

-- 6. Pemeriksaan penutup. Bila salah satu meleset, seluruh transaksi digugurkan.
--    Dua yang terakhir menjaga Perusahaan Utama: ia harus keluar dari berkas ini
--    persis seperti ia masuk.
DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM items WHERE company_id = 2;
    IF n <> 20 THEN RAISE EXCEPTION 'Item demo tersisa %, seharusnya 20', n; END IF;

    SELECT count(*) INTO n FROM inventory WHERE company_id = 2 AND warehouse_id = 72;
    IF n <> 10 THEN RAISE EXCEPTION 'Inventory Gudang Pusat Jakarta % baris, seharusnya 10', n; END IF;

    SELECT count(*) INTO n FROM inventory WHERE company_id = 2 AND warehouse_id = 73;
    IF n <> 10 THEN RAISE EXCEPTION 'Inventory Gudang Surabaya % baris, seharusnya 10', n; END IF;

    SELECT count(*) INTO n FROM stock_movements m WHERE m.company_id = 2
      AND NOT EXISTS (SELECT 1 FROM inventory i WHERE i.company_id = 2
                      AND i.item_id = m.item_id AND i.warehouse_id = m.warehouse_id);
    IF n <> 0 THEN RAISE EXCEPTION '% pergerakan tertinggal di gudang yang bukan gudang itemnya', n; END IF;

    SELECT count(*) INTO n FROM items WHERE company_id = 1;
    IF n <> 20 THEN RAISE EXCEPTION 'Item Perusahaan Utama menjadi %, seharusnya tetap 20', n; END IF;

    SELECT count(*) INTO n FROM stock_movements WHERE company_id = 1;
    IF n <> 5448 THEN RAISE EXCEPTION 'Pergerakan Perusahaan Utama menjadi %, seharusnya tetap 5448', n; END IF;
END $$;

COMMIT;
