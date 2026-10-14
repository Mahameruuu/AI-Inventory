-- Memperbaiki 6 barang demo BRU-* yang menunjuk kategori/satuan milik
-- Perusahaan Utama (company 1) padahal barangnya milik tenant Demo (company 2).
--
-- AKIBATNYA, tanpa perbaikan ini: RLS menyembunyikan kategori/satuannya, mesin
-- Pemesanan Ulang tidak dapat menilai barangnya (status "Unknown" di 3D), dan
-- halaman yang memakai INNER JOIN ke kategori/satuan diam-diam membuang barisnya.
--
-- SUMBER MASALAH: database/seed_demo_forecast.sql menulis category_id/unit_id
-- tetap (1, 7, 85, ...) yang hanya valid di company 1. Perbaiki juga seed itu
-- (cari id lewat nama pada company 2) sebelum menjalankannya ulang.
--
-- BELUM DIJALANKAN. Jalankan sebagai inventory_admin setelah ditinjau:
--   docker exec -i inventory-postgres psql -U inventory_admin -d inventory \
--     -v ON_ERROR_STOP=1 -f /dev/stdin < database/fix_demo_bru_kategori.sql
--
-- Cadangan nilai lama (jalankan SEBELUM update bila ingin bisa dikembalikan):
--   \copy (select id, sku, category_id, unit_id from items
--          where sku like 'BRU-%') to 'bru_sebelum.csv' csv header

BEGIN;

UPDATE items
   SET category_id = CASE sku WHEN 'BRU-000005' THEN 189  -- Alat Listrik (kabel)
                              ELSE 187 END,                -- Sparepart Mesin
       unit_id     = CASE sku WHEN 'BRU-000005' THEN 84    -- MTR
                              WHEN 'BRU-000006' THEN 84    -- MTR (selang)
                              WHEN 'BRU-000003' THEN 82    -- BOX (pack)
                              ELSE 81 END,                 -- PCS
       updated_at  = now()
 WHERE sku LIKE 'BRU-%'
   AND company_id = 2
   AND category_id IN (SELECT id FROM categories WHERE company_id <> 2);

-- Harus 0 baris: tidak ada lagi barang yang kategorinya milik tenant lain.
SELECT count(*) AS masih_rusak
  FROM items it JOIN categories c ON c.id = it.category_id
 WHERE c.company_id <> it.company_id;

COMMIT;
