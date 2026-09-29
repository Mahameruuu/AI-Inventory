-- Temuan pemantauan pola kuantitas stok.
--
-- LINGKUP: modul ini hanya mengamati JUMLAH BARANG -- pemakaian, penerimaan,
-- laju, dan interval antar pengambilan. Ia TIDAK mengaudit selisih fisik
-- terhadap sistem, tidak menghitung kehilangan, dan tidak menyentuh nilai
-- rupiah. Batas itu disengaja: kesimpulan audit menuntut bukti pencacahan
-- fisik yang tidak dimiliki tabel ini, dan menyajikannya seolah-olah ada
-- akan menuduh tanpa dasar.
--
-- Tabel transaksi TIDAK disentuh. Seluruh penandaan hidup di sini, sehingga
-- riwayat transaksi tetap menjadi catatan apa yang terjadi, bukan campuran
-- antara kejadian dan pendapat sistem tentang kejadian itu.

-- Tanpa BEGIN/COMMIT sendiri. Berkas ini dijalankan lewat \ir dari
-- database/migrate.sql, yang sudah membungkus SELURUH migrasi dalam satu
-- transaksi. BEGIN di sini hanya menghasilkan peringatan "there is already
-- a transaction in progress" dan diabaikan, tetapi COMMIT-nya BENAR-BENAR
-- menutup transaksi pembungkus itu -- sehingga seluruh migrasi sesudahnya
-- berjalan tanpa perlindungan rollback sama sekali. Kegagalan di migrasi
-- 026 akan meninggalkan basis data setengah jadi alih-alih kembali utuh.
\set ON_ERROR_STOP on

CREATE TABLE IF NOT EXISTS anomaly_findings (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    item_id                 bigint NOT NULL REFERENCES items(id),
    warehouse_id            bigint NOT NULL REFERENCES warehouses(id),

    -- Lapis 1 (kepastian salah): qty_negative, qty_exceeds_stock,
    -- qty_impossible, duplicate_entry
    -- Lapis 2 (pola): spike, stop, rate_shift, dead_stock
    type                    varchar(30)  NOT NULL,
    severity                varchar(10)  NOT NULL,
    status                  varchar(30)  NOT NULL DEFAULT 'detected',

    detected_at             timestamptz  NOT NULL DEFAULT now(),
    -- Tanggal KEJADIAN yang ditemukan, bukan tanggal ia ditemukan. Dedup
    -- bersandar pada kolom ini supaya menjalankan ulang pemindaian tidak
    -- memunculkan temuan yang sama dua kali.
    event_date              date         NOT NULL,

    -- Angka-angka untuk menyusun kalimat deskripsi. Disimpan sebagai angka,
    -- bukan kalimat jadi: kalimatnya dapat diperbaiki kapan saja tanpa
    -- menulis ulang isi tabel, dan bahasa lain dapat ditambahkan nanti.
    description_params      jsonb        NOT NULL DEFAULT '{}'::jsonb,

    related_transaction_ids bigint[]     NOT NULL DEFAULT '{}',

    confirmed_by            varchar(120),
    confirmed_at            timestamptz,
    resolution_note         text,

    created_at              timestamptz  NOT NULL DEFAULT now(),
    updated_at              timestamptz  NOT NULL DEFAULT now(),

    CONSTRAINT anomaly_findings_type_valid CHECK (type IN (
        'qty_negative', 'qty_exceeds_stock', 'qty_impossible', 'duplicate_entry',
        'spike', 'stop', 'rate_shift', 'dead_stock'
    )),
    CONSTRAINT anomaly_findings_severity_valid CHECK (severity IN (
        'HIGH', 'MEDIUM', 'LOW'
    )),
    CONSTRAINT anomaly_findings_status_valid CHECK (status IN (
        'detected', 'confirmed_normal', 'flagged_input_error', 'resolved'
    ))
);

-- Kunci dedup. Satu jenis temuan untuk satu barang di satu gudang pada satu
-- tanggal kejadian hanya boleh ada SATU baris -- inilah yang menjamin temuan
-- yang sudah dikonfirmasi tidak terbit lagi sebagai temuan baru pada
-- pemindaian berikutnya.
CREATE UNIQUE INDEX IF NOT EXISTS anomaly_findings_dedup
    ON anomaly_findings (item_id, warehouse_id, type, event_date);

-- Jalur baca halaman: daftar temuan satu gudang, disaring status, diurutkan
-- severity.
CREATE INDEX IF NOT EXISTS idx_anomaly_findings_wh_status_sev
    ON anomaly_findings (warehouse_id, status, severity);

-- Jalur baca per barang, dipakai saat menelusuri riwayat satu SKU.
CREATE INDEX IF NOT EXISTS idx_anomaly_findings_item_status
    ON anomaly_findings (item_id, status);

-- Kartu "menunggu konfirmasi lebih dari 3 hari" dan "selesai 30 hari
-- terakhir" menyaring berdasarkan waktu.
CREATE INDEX IF NOT EXISTS idx_anomaly_findings_detected_at
    ON anomaly_findings (detected_at);

