-- 033: Beberapa pilihan jalur per pasangan gudang
--
-- Migrasi 032 menyimpan SATU garis per pasangan. Peta kini menampilkan sampai
-- tiga jalur (tercepat, terpendek, alternatif) supaya orang gudang dapat
-- membandingkan waktu dan jarak sebelum memilih.
--
-- Kolom `routes` berisi daftar [{points, distance_m, duration_s}, ...] dengan
-- yang tercepat di urutan pertama. `points`/`distance_m` lama tetap terisi jalur
-- tercepat, jadi baris yang belum punya `routes` (hasil migrasi 032) dianggap
-- belum tersimpan dan diambil ulang saat pertama diminta.
--
-- Durasi berasal dari OSRM: waktu tempuh jalan lengang, TANPA lalu lintas
-- langsung, dan tidak ada penilaian keamanan. Angkanya perkiraan, bukan janji.

\set ON_ERROR_STOP on

ALTER TABLE road_route_cache
    ADD COLUMN IF NOT EXISTS routes JSONB NULL;

COMMENT ON COLUMN road_route_cache.routes IS
    'Semua pilihan jalur [{points, distance_m, duration_s}], tercepat lebih dulu; NULL = baris lama dari migrasi 032';
