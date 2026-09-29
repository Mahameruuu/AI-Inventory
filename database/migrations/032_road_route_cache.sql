-- 032: Cache geometri jalan untuk peta Transfer Antar Gudang
--
-- Peta menggambar tiap rute mengikuti jalan raya, bukan busur. Geometrinya
-- diminta SEKALI per pasangan koordinat ke OSRM, lalu disimpan di sini: rute
-- Surabaya -> Jakarta tidak berubah dari satu layar ke layar berikutnya, dan
-- menanyakannya ulang setiap kali peta dibuka hanya membebani server publik
-- yang bukan milik kita.
--
-- TIDAK ADA company_id DAN TIDAK ADA RLS, dan itu disengaja: baris ini hanya
-- berisi bentuk jalan di antara dua titik di bumi. Tidak ada nama perusahaan,
-- gudang, barang, atau jumlah di dalamnya; dua penyewa yang gudangnya kebetulan
-- berada di titik yang sama memang boleh berbagi jawaban yang sama.
--
-- Koordinat dibulatkan empat desimal (~11 m) pada kuncinya supaya gudang yang
-- koordinatnya digeser sedikit tidak melahirkan baris baru.

\set ON_ERROR_STOP on

CREATE TABLE IF NOT EXISTS road_route_cache (
    from_lat   NUMERIC(8,4) NOT NULL,
    from_lon   NUMERIC(8,4) NOT NULL,
    to_lat     NUMERIC(8,4) NOT NULL,
    to_lon     NUMERIC(8,4) NOT NULL,
    -- [[lat, lon], ...] sudah disederhanakan; lihat app/jalur.py
    points     JSONB        NOT NULL,
    distance_m INTEGER      NULL,
    fetched_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (from_lat, from_lon, to_lat, to_lon)
);

COMMENT ON TABLE road_route_cache IS
    'Geometri jalan hasil OSRM per pasangan koordinat; bukan data penyewa, tanpa RLS';

GRANT SELECT, INSERT, UPDATE, DELETE ON road_route_cache TO inventory_app;
