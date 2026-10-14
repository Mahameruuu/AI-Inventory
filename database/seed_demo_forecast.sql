-- Barang demo spare part slow-moving untuk memperagakan lapisan reorder.
--
-- MENARGET TENANT DEMO INVENTORY AI (company_id 2) secara eksplisit, bukan
-- Perusahaan Utama -- tombol demo memang tidak pernah muncul di tenant asli.
-- Berkas ini terhubung sebagai inventory_admin (superuser) supaya lolos RLS
-- untuk menulis lintas pemeriksaan, dan justru karena itu app.company_id
-- HARUS disetel tangan lebih dulu: superuser tidak mendapatkannya otomatis
-- dari sesi login seperti aplikasi, dan kolom company_id pada items memakai
-- current_setting('app.company_id') sebagai bawaannya (lihat migrasi RLS).
-- Tanpa SET ini, insert pada items gagal dengan galat NOT NULL, dan pencarian
-- pemasok di bawah -- yang sengaja disaring ke tenant yang sama -- akan
-- kosong.
--
--   { echo "SET app.company_id = '2';"; cat database/seed_demo_forecast.sql; } \
--     | docker exec -i inventory-postgres psql -U inventory_admin -d inventory -f /dev/stdin
--
-- MENGAPA ADA BERKAS INI
-- ----------------------
-- Seluruh 22.155 pasangan barang/gudang pada data utama sudah berhistori
-- ratusan hari dengan pemakaian yang ramai, sehingga tidak ada satu pun contoh
-- SPARE PART SLOW-MOVING -- padahal justru itulah bentuk yang paling sering
-- ditemui di gudang perawatan, dan justru pada bentuk itu lapisan reorder
-- paling berguna. Enam barang di bawah mengisi kekosongan itu, masing-masing
-- mengarah ke satu kondisi yang berbeda supaya seluruh cabang keputusan bisa
-- dilihat berdampingan.
--
-- LAJU PEMAKAIANNYA REALISTIS, DAN ITU BUKAN DETAIL KOSMETIK
-- ----------------------------------------------------------
-- Rancangan sebelumnya memberi pompa sentrifugal industrial pemakaian ~7 unit
-- PER HARI. Angka itu mustahil: pompa sentrifugal dipasang, lalu dipakai
-- bertahun-tahun. Akibatnya bukan sekadar demo yang terasa aneh, melainkan
-- seluruh angka turunan ikut mustahil -- kebutuhan selama masa tunggu menjadi
-- 49 unit, titik pesan efektif 59 unit, dan pembaca yang mengenal barangnya
-- langsung berhenti mempercayai sisa layarnya.
--
-- Di sini setiap barang berkonsumsi ~1-5 unit PER BULAN, keluar beberapa kali
-- saja sepanjang tiga bulan, persis seperti suku cadang perawatan berkala yang
-- sebenarnya. Konsekuensinya ikut diperagakan: hari tanpa pengeluaran jauh
-- lebih banyak daripada hari dengan pengeluaran, jadi mutu datanya turun ke
-- "sedang" dan pola pemakaiannya terbaca "sekaligus" (lumpy) -- keduanya
-- penilaian yang BENAR untuk barang seperti ini, dan keduanya perlu terlihat
-- di layar demo.
--
-- Tanggalnya RELATIF terhadap hari skrip dijalankan (CURRENT_DATE), jadi
-- menjalankan ulang berkas ini selalu menghasilkan jendela histori yang benar,
-- bukan tanggal yang membeku.
--
-- Aman dijalankan berulang: seluruh jejak SKU berawalan 'BRU-' dihapus lebih
-- dulu, jadi tidak pernah menumpuk ganda.
--
-- PANJANG HISTORINYA 90 HARI, MENGIKUTI JENDELA YANG BENAR-BENAR DIBACA.
-- Endpoint prakiraan memakai historical_days=90, jadi pergerakan yang lebih
-- tua dari itu tidak ikut menghasilkan laju pemakaian. Menaruh penerimaan awal
-- di luar jendela hanya membuat saldo dan histori bercerita hal yang berbeda.

\set ON_ERROR_STOP on

BEGIN;

-- --------------------------------------------------------------------------
-- 1. Bersihkan jejak lama
-- --------------------------------------------------------------------------
CREATE TEMP TABLE demo_lama ON COMMIT DROP AS
SELECT id FROM items WHERE sku LIKE 'BRU-%';

DELETE FROM stock_movements  WHERE item_id IN (SELECT id FROM demo_lama);
DELETE FROM stock_receipt_items WHERE item_id IN (SELECT id FROM demo_lama);
DELETE FROM stock_issue_items   WHERE item_id IN (SELECT id FROM demo_lama);
DELETE FROM stock_receipts WHERE reference_number LIKE 'DEMO-BRU-%';
DELETE FROM stock_issues   WHERE reference_number LIKE 'DEMO-BRU-%';
DELETE FROM inventory      WHERE item_id IN (SELECT id FROM demo_lama);
DELETE FROM items          WHERE id IN (SELECT id FROM demo_lama);

-- --------------------------------------------------------------------------
-- 2. Rancangan keenam barang
-- --------------------------------------------------------------------------
-- hari_mulai   : berapa hari lalu barang pertama kali diterima; sekaligus
--                menentukan panjang histori (hari_mulai + 1 hari).
-- keluar_hari  : hari ke berapa SEJAK penerimaan awal terjadi pengeluaran.
-- keluar_qty   : jumlah pada masing-masing hari itu, sejajar dengan larik di
--                sebelahnya.
--
-- DUA LARIK JARANG, BUKAN SATU LARIK PADAT. Rancangan sebelumnya menulis
-- pengeluaran sebagai satu nilai per hari, yang masih terbaca untuk histori
-- tujuh hari tetapi berubah menjadi delapan puluh sembilan angka -- hampir
-- seluruhnya nol -- begitu historinya menjadi tiga bulan. Bentuk jarang di
-- bawah menyebut hanya hari yang benar-benar ada transaksinya, sehingga pola
-- "diambil sekali tiap dua sampai empat pekan" terbaca langsung dari
-- rancangannya. Hari yang tidak disebut tetap dihitung sebagai nol oleh mesin
-- prakiraan, sebagaimana mestinya.
--
-- Kolom stok_akhir menyatakan saldo yang DIKEHENDAKI setelah seluruh
-- pengeluaran; jumlah penerimaan awal diturunkan darinya, bukan sebaliknya --
-- itulah yang membuat tiap barang mendarat di kondisi yang dirancang.
--
-- KATEGORI DAN SATUAN DITULIS SEBAGAI NAMA/KODE, BUKAN ID. Versi sebelumnya
-- menulis id tetap (1, 7, 85, ...) yang hanya berlaku di Perusahaan Utama;
-- pada tenant Demo id itu menunjuk kategori milik perusahaan lain, RLS
-- menyembunyikannya, dan keenam barang jadi tak dapat dinilai mesin reorder.
-- Kini nama dicari PADA TENANT YANG SEDANG AKTIF (app.company_id).
CREATE TEMP TABLE demo_rancangan AS
SELECT t.*, c.id AS category_id, u.id AS unit_id,
       -- Penerimaan awal = saldo yang dikehendaki + seluruh yang keluar.
       t.stok_akhir + (SELECT COALESCE(SUM(q), 0)
                       FROM unnest(t.keluar_qty) AS q) AS qty_masuk
FROM (VALUES
  -- Pompa sentrifugal: ~1 unit per bulan. Dipasang lalu dipakai bertahun-
  -- tahun, jadi yang keluar hanyalah unit pengganti sesekali.
  -- Stok 12 jauh di atas titik pesan efektif -> STOK AMAN.
  ('BRU-000001', 'Pompa Sentrifugal Grundfos G-2200', 'Sparepart Mesin', 'PCS',
   18500000::numeric, 2::numeric, 6::numeric, 21, 3::numeric, 24::numeric,
   89, ARRAY[12,41,68,86], ARRAY[1,1,1,1]::numeric[], 12::numeric,
   'AMAN — stok jauh di atas titik pesan efektif'),

  -- Bearing: ~5 PCS per bulan, barang perawatan berkala yang paling sering
  -- diganti di antara keenamnya.
  -- Stok 5 sudah DI BAWAH titik pesan efektif -> SEGERA PESAN, jumlahnya > 0.
  ('BRU-000002', 'Bearing SKF 6312-2RS1',             'Sparepart Mesin', 'PCS',
   1250000::numeric,  6::numeric, 12::numeric, 14, 8::numeric, 60::numeric,
   89, ARRAY[8,19,33,47,61,74,88], ARRAY[2,2,2,2,2,3,2]::numeric[], 5::numeric,
   'SEGERA PESAN — stok di bawah titik pesan efektif'),

  -- Filter oli: ~4 unit per bulan.
  -- Stok 11 masih di atas titik pesan efektif tetapi sudah menyentuh titik
  -- pesan MASTER (14) -> PERLU DIPANTAU tanpa jumlah yang perlu dipesan.
  ('BRU-000003', 'Filter Oli Parker P-9540',          'Sparepart Mesin', 'BOX',
   485000::numeric,   4::numeric, 14::numeric, 10, 2::numeric, 48::numeric,
   89, ARRAY[10,25,38,52,66,80,87], ARRAY[2,1,2,2,2,1,2]::numeric[], 11::numeric,
   'PANTAU — di bawah titik pesan master, di atas yang efektif'),

  -- V-belt: barang yang BARU masuk gudang dua pekan lalu, ~4 unit per bulan.
  -- Jendela historinya berakhir pada pengeluaran TERAKHIR, bukan pada hari ini
  -- (lihat tanggal_acuan() pada routers/forecasting.py), jadi rentangnya 12
  -- hari dan baru dua hari yang ada pengeluaran -- keduanya di bawah ambang
  -- minimum mesin prakiraan -> DATA BELUM CUKUP. Stok dan parameter masternya
  -- tetap tampil; yang kosong hanya lapisan yang bersandar pada laju pemakaian.
  ('BRU-000004', 'V-Belt Mitsuboshi B-75',            'Sparepart Mesin', 'PCS',
   320000::numeric,   4::numeric,  8::numeric,  7, 2::numeric, 40::numeric,
   13, ARRAY[4,11], ARRAY[1,1]::numeric[], 20::numeric,
   'DATA BELUM CUKUP — baru dua kali keluar'),

  -- Kabel NYY: ~3 METER per bulan, masa tunggu impor 40 hari.
  -- Stok 11 masih di atas kedua ambang, tetapi titik pesan efektif tersentuh
  -- dalam waktu lebih pendek dari satu kali masa tunggu -> PERLU DIPANTAU
  -- sebagai peringatan dini. Titik pesan masternya (6) sendiri lebih rendah
  -- daripada yang efektif, jadi barang ini sekaligus memperagakan kartu
  -- "kecukupan titik pesan master: perlu dikalibrasi".
  ('BRU-000005', 'Kabel NYY Supreme 4x25mm',          'Alat Listrik', 'MTR',
   285000::numeric,   3::numeric,  6::numeric, 40, 4::numeric, 40::numeric,
   89, ARRAY[14,30,45,59,73,84,89], ARRAY[1,1,2,1,1,2,1]::numeric[], 11::numeric,
   'PANTAU — titik pesan efektif tersentuh dalam satu masa tunggu'),

  -- Selang hidrolik: ~2 METER per bulan, keluar sekaligus tiap ~4 pekan.
  -- Hanya tiga hari berpengeluaran dari sembilan puluh, jadi pola pemakaiannya
  -- terbaca "sekaligus" dan peringatan lumpy ikut tampil -- penilaian yang
  -- benar untuk barang seperti ini. Stoknya sendiri -> STOK AMAN.
  ('BRU-000006', 'Selang Hidrolik Gates 4SP-19',      'Sparepart Mesin', 'MTR',
   1750000::numeric,  4::numeric, 10::numeric, 45, 5::numeric, 40::numeric,
   89, ARRAY[22,51,80], ARRAY[2,2,2]::numeric[], 18::numeric,
   'AMAN — pola pengambilan sekaligus (lumpy)')
) AS t(sku, nama, kategori_nama, satuan_kode, unit_price, minimum_stock,
       reorder_point, lead_time_days, safety_stock, maximum_stock,
       hari_mulai, keluar_hari, keluar_qty, stok_akhir, target_kondisi)
LEFT JOIN categories c ON c.name = t.kategori_nama
                      AND c.company_id = current_setting('app.company_id')::bigint
LEFT JOIN units u      ON u.code = t.satuan_kode
                      AND u.company_id = current_setting('app.company_id')::bigint;

-- Nama kategori/satuan harus ada pada tenant ini; kalau tidak, berhenti dengan
-- pesan yang menyebut barangnya, bukan memasukkan barang tanpa kategori.
DO $$
DECLARE hilang text;
BEGIN
  SELECT string_agg(sku || ' (' || kategori_nama || '/' || satuan_kode || ')', ', ') INTO hilang
  FROM demo_rancangan
  WHERE category_id IS NULL OR unit_id IS NULL;
  IF hilang IS NOT NULL THEN
    RAISE EXCEPTION 'kategori/satuan tidak ditemukan pada tenant ini untuk: %', hilang;
  END IF;
END $$;

-- Kedua larik harus sejajar; kalau tidak, sebagian pengeluaran diam-diam
-- hilang dan saldo yang terbentuk tidak lagi sesuai rancangan.
DO $$
DECLARE hilang text;
BEGIN
  SELECT string_agg(sku, ', ') INTO hilang
  FROM demo_rancangan
  WHERE array_length(keluar_hari, 1) IS DISTINCT FROM array_length(keluar_qty, 1)
     OR (SELECT max(h) FROM unnest(keluar_hari) AS h) > hari_mulai;
  IF hilang IS NOT NULL THEN
    RAISE EXCEPTION 'larik keluar_hari/keluar_qty tidak sejajar atau melewati hari_mulai untuk: %', hilang;
  END IF;
END $$;

-- --------------------------------------------------------------------------
-- 3. Master barang
-- --------------------------------------------------------------------------
-- Stok maksimum ditulis eksplisit pada rancangan, bukan diturunkan dari jumlah
-- penerimaan: ia ikut menentukan angka `suggested_order_qty` yang lama, dan
-- "dua kali penerimaan pertama" bukan aturan gudang mana pun.
INSERT INTO items (sku, name, category_id, unit_id, unit_price, minimum_stock,
                   maximum_stock, reorder_point, criticality, is_active,
                   lead_time_days, safety_stock)
SELECT sku, nama, category_id, unit_id, unit_price, minimum_stock,
       maximum_stock, reorder_point, 'medium', true,
       lead_time_days, safety_stock
FROM demo_rancangan;

-- --------------------------------------------------------------------------
-- 4. Dokumen, pergerakan, dan saldo
-- --------------------------------------------------------------------------
DO $$
DECLARE
  r          record;
  gudang     bigint;
  pemasok    bigint;
  barang     bigint;
  id_terima  bigint;
  id_keluar  bigint;
  hari       date;
  waktu      timestamptz;
  qty        numeric;
  i          int;
  urut       int := 0;
BEGIN
  -- Gudang Pusat Jakarta pada tenant Demo. Dan supplier-nya DISARING ke
  -- company_id yang sama: berjalan sebagai superuser berarti RLS tidak
  -- menyaringnya sendiri, dan "ORDER BY id LIMIT 1" tanpa saringan akan
  -- mengambil supplier tenant lain begitu saja -- lolos secara teknis
  -- (tidak ada FK yang menolaknya) tapi salah secara data: barang tenant
  -- Demo akan menunjuk pemasok Perusahaan Utama.
  SELECT id INTO gudang FROM warehouses
   WHERE code = 'WH-JKT'
     AND company_id = NULLIF(current_setting('app.company_id', true), '')::bigint;
  SELECT id INTO pemasok FROM suppliers
   WHERE company_id = NULLIF(current_setting('app.company_id', true), '')::bigint
   ORDER BY id LIMIT 1;
  IF gudang IS NULL OR pemasok IS NULL THEN
    RAISE EXCEPTION 'gudang WH-JKT atau data pemasok tidak ditemukan untuk app.company_id=% -- pastikan sudah di-SET sebelum menjalankan berkas ini',
      current_setting('app.company_id', true);
  END IF;

  FOR r IN SELECT * FROM demo_rancangan ORDER BY sku LOOP
    SELECT id INTO barang FROM items WHERE sku = r.sku;
    urut := urut + 1;
    hari  := CURRENT_DATE - r.hari_mulai;
    -- Pukul 03:00 UTC (10:00 WIB). Jauh dari tengah malam supaya pergeseran
    -- zona waktu apa pun tidak memindahkan transaksi ke tanggal sebelahnya.
    waktu := hari::timestamptz + interval '3 hours';

    -- --- penerimaan awal ---
    INSERT INTO stock_receipts (receipt_number, supplier_id, warehouse_id,
                                receipt_date, reference_number, status, notes)
    VALUES (format('GR-%s-9%s', to_char(hari, 'YYYYMMDD'), lpad(urut::text, 4, '0')),
            pemasok, gudang, waktu,
            format('DEMO-BRU-%s', lpad(urut::text, 4, '0')),
            'completed', 'Penerimaan awal spare part')
    RETURNING id INTO id_terima;

    INSERT INTO stock_receipt_items (stock_receipt_id, item_id, quantity,
                                     unit_price, received_date)
    VALUES (id_terima, barang, r.qty_masuk, r.unit_price, hari);

    INSERT INTO stock_movements (item_id, warehouse_id, movement_type,
                                 reference_id, movement_date, quantity, unit_price)
    VALUES (barang, gudang, 'stock_in', id_terima, waktu, r.qty_masuk, r.unit_price);

    -- --- pengeluaran, hanya pada hari yang benar-benar ada transaksinya ---
    FOR i IN 1 .. array_length(r.keluar_hari, 1) LOOP
      qty := r.keluar_qty[i];
      CONTINUE WHEN qty <= 0;

      hari  := CURRENT_DATE - r.hari_mulai + r.keluar_hari[i];
      waktu := hari::timestamptz + interval '3 hours';

      INSERT INTO stock_issues (issue_number, warehouse_id, issue_date,
                                purpose, reference_number, status)
      VALUES (format('ISS-%s-9%s', to_char(hari, 'YYYYMMDD'), lpad(urut::text, 4, '0')),
              gudang, waktu, 'Perawatan berkala',
              format('DEMO-BRU-%s-%s', lpad(urut::text, 4, '0'), lpad(i::text, 2, '0')),
              'completed')
      RETURNING id INTO id_keluar;

      INSERT INTO stock_issue_items (stock_issue_id, item_id, quantity)
      VALUES (id_keluar, barang, qty);

      -- Kuantitas pada stock_movements bertanda: keluar selalu negatif.
      -- Mesin prakiraan membaca tanda itu, bukan movement_type.
      INSERT INTO stock_movements (item_id, warehouse_id, movement_type,
                                   reference_id, movement_date, quantity, unit_price)
      VALUES (barang, gudang, 'stock_out', id_keluar, waktu, -qty, r.unit_price);
    END LOOP;

    -- --- saldo ---
    -- Dihitung dari pergerakan, bukan ditulis ulang dari rancangan: kalau
    -- keduanya pernah berselisih, angkanya harus ikut pergerakan.
    INSERT INTO inventory (item_id, warehouse_id, quantity,
                           reserved_quantity, available_quantity)
    SELECT barang, gudang, COALESCE(SUM(quantity), 0), 0, COALESCE(SUM(quantity), 0)
    FROM stock_movements WHERE item_id = barang AND warehouse_id = gudang;
  END LOOP;
END $$;

COMMIT;

-- --------------------------------------------------------------------------
-- 5. Ringkasan hasil
-- --------------------------------------------------------------------------
-- Laju pemakaian di sini adalah rata-rata SEDERHANA atas jendela histori,
-- dicetak semata-mata agar realistis-tidaknya rancangan dapat diperiksa
-- sekilas. Angka yang dipakai sistem berbeda -- ia berbobot ke hari terbaru,
-- dan dapat berasal dari model prakiraan -- jadi kolom ini tidak boleh dibaca
-- sebagai nilai yang akan tampil di layar Reorder.
SELECT it.sku, it.name,
       inv.quantity AS stok,
       it.reorder_point AS titik_pesan_master,
       it.safety_stock, it.lead_time_days AS lead_time,
       d.hari_mulai + 1 AS rentang_hari,
       array_length(d.keluar_hari, 1) AS hari_keluar,
       (SELECT SUM(q) FROM unnest(d.keluar_qty) AS q) AS total_keluar,
       round((SELECT SUM(q) FROM unnest(d.keluar_qty) AS q)
             * 30.0 / (d.hari_mulai + 1), 1) AS perkiraan_per_bulan,
       d.target_kondisi AS kondisi_diharapkan
FROM items it
JOIN demo_rancangan d ON d.sku = it.sku
JOIN inventory inv ON inv.item_id = it.id
WHERE it.sku LIKE 'BRU-%'
ORDER BY it.sku;
