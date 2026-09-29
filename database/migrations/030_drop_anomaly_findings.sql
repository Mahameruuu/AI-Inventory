-- 030: membuang tabel temuan anomali
--
-- Modul Deteksi Anomali dihapus seluruhnya pada 2 September 2026. Tempatnya
-- pada alur AI diisi Analisis Umur Pakai, yang tidak membutuhkan tabel baru
-- sama sekali: umur pakai harapan sudah ada di items (migrasi 029) dan umur
-- pakai aktual diturunkan dari riwayat pengeluaran yang sudah tercatat.
--
-- KENAPA MIGRASI BARU, BUKAN MENGHAPUS 020. Migrasi 020 sudah pernah berjalan
-- di basis data produksi, dan 026/027/028 sesudahnya menyentuh tabel yang
-- dibuatnya (company_id, indeks dedup tenant-scoped, kebijakan RLS).
-- Membuang berkas 020 hanya membuat basis data yang sudah ada dan basis data
-- yang dibangun dari nol berakhir berbeda bentuk -- yang pertama masih memuat
-- tabelnya, yang kedua tidak, dan tidak ada satu pun galat yang menunjukkannya.
-- Riwayat migrasi dibaca sebagai catatan apa yang PERNAH terjadi.
--
-- Kebijakan RLS, indeks, dan constraint ikut lenyap bersama tabelnya; tidak
-- ada yang perlu dibersihkan satu per satu. Tidak ada tabel lain yang menunjuk
-- anomaly_findings, jadi CASCADE tidak diperlukan dan sengaja tidak dipakai:
-- bila ternyata ada yang menunjuknya, perintah ini HARUS gagal dan terbaca,
-- bukan diam-diam ikut membuang tabel orang lain.

\set ON_ERROR_STOP on

DROP TABLE IF EXISTS anomaly_findings;
