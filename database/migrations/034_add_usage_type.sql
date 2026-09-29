-- 034: jenis pemakaian barang (berumur pakai / habis pakai)
--
-- Dua jenis barang berperilaku sangat berbeda terhadap prakiraan:
--
--   berumur_pakai  komponen yang dipasang lalu diganti menurut umur pakainya
--                  (Gear Pump, Bearing, Centrifugal Pump). Pengeluarannya
--                  hitungan tahunan atau puluhan tahun, sehingga prakiraan
--                  statistik tidak punya bahan; yang menjawab pertanyaannya
--                  adalah jadwal penggantian.
--   habis_pakai    barang yang keluar rutin (grease, seal, V-belt). Deret
--                  pengeluarannya cukup rapat untuk diprakirakan.
--
-- KENAPA ATRIBUT, BUKAN DIHITUNG DARI LAJU. Barang di tengah -- Filter Oli
-- berumur 1.250 jam, sekitar 78 hari -- akan berpindah kelompok setiap kali
-- datanya bergeser bila jenisnya diturunkan dari laju. Yang tercatat stabil dan
-- dapat dikoreksi pemiliknya.
--
-- Bawaan: barang yang punya umur pakai (migrasi 029) menjadi berumur_pakai,
-- sisanya habis_pakai.

ALTER TABLE items
    ADD COLUMN IF NOT EXISTS usage_type VARCHAR(16) NOT NULL DEFAULT 'habis_pakai';

ALTER TABLE items DROP CONSTRAINT IF EXISTS items_usage_type_check;
ALTER TABLE items
    ADD CONSTRAINT items_usage_type_check
    CHECK (usage_type IN ('berumur_pakai', 'habis_pakai'));

UPDATE items SET usage_type = 'berumur_pakai'
 WHERE service_life_value IS NOT NULL AND usage_type <> 'berumur_pakai';

COMMENT ON COLUMN items.usage_type IS
    'berumur_pakai = komponen yang diganti menurut umur pakai (dijadwalkan); '
    'habis_pakai = barang yang keluar rutin (diprakirakan).';
