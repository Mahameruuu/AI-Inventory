# -*- coding: utf-8 -*-
"""
Koneksi basis data.

Satu pool dipakai bersama seluruh permintaan. Helper `transaction()` membuka
satu transaksi yang menutup sendiri: COMMIT bila blok selesai tanpa kesalahan,
ROLLBACK bila ada pengecualian apa pun. Tidak ada jalan keluar lain -- inilah
yang menjamin receipt, movement, dan inventory tidak pernah tersimpan
setengah-setengah.

PENYEWA DIPASANG DI SINI, SEKALI. Kedua pintu di bawah adalah satu-satunya
tempat query lahir di aplikasi ini, sehingga keduanya pula tempat paling tepat
untuk memberi tahu PostgreSQL sedang melayani perusahaan yang mana. Router
tidak menyentuh soal ini sama sekali: ia menulis SELECT seperti biasa, dan
policy Row Level Security (migrasi 028) yang menyaringnya.
"""

from contextlib import contextmanager

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import tenant
from .config import DATABASE_URL, POOL_MAX, POOL_MIN

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL belum diisi pada .env")
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=POOL_MIN,
            max_size=POOL_MAX,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def _pasang_penyewa(cur) -> None:
    """
    Menyalin perusahaan yang sedang aktif ke setelan sesi PostgreSQL.

    Argumen ketiga set_config bernilai TRUE: setelannya berlaku hanya sampai
    transaksi ini selesai. Itu bukan kerapian, melainkan syarat kebenaran --
    koneksi dipakai bergantian oleh banyak permintaan lewat pool, dan setelan
    yang menempel pada koneksi akan terbawa ke permintaan berikutnya yang
    kebetulan mendapat koneksi yang sama. Penyewa satu akan melihat data
    penyewa lain, dan tidak ada satu pun galat yang terbit.

    Bila tidak ada penyewa, setelannya sengaja TIDAK dipasang: policy RLS akan
    membandingkan dengan NULL dan tidak meloloskan baris apa pun. Jalur yang
    memang harus bekerja tanpa penyewa -- pemeriksaan kesehatan dan pencarian
    pengguna saat masuk -- tidak menyentuh tabel ber-RLS atau lewat fungsi
    SECURITY DEFINER yang dibuat khusus untuk itu.
    """
    p = tenant.penyewa()
    if p is None:
        return
    # app.user_id dibaca trigger jejak audit dan default kolom created_by
    # (migrasi 036). Kosong untuk pekerjaan latar: jejaknya tetap tercatat,
    # hanya tanpa nama orang.
    cur.execute(
        "SELECT set_config('app.company_id', %s, true),"
        "       set_config('app.user_id', %s, true)",
        (str(p.company_id), str(p.user_id) if p.user_id else ""),
    )


@contextmanager
def transaction():
    """
    Satu transaksi basis data.

    psycopg membuka transaksi begitu pernyataan pertama dijalankan; blok
    `with conn.transaction()` menutupnya dengan COMMIT saat blok selesai dan
    ROLLBACK saat terjadi pengecualian.
    """
    with pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                _pasang_penyewa(cur)
                yield cur


@contextmanager
def readonly():
    """
    Kursor untuk membaca saja; tetap satu transaksi, tetapi tanpa tulis.

    Transaksinya kini dibuka eksplisit. Setelan penyewa berlaku sepanjang
    transaksi, jadi ia butuh batas transaksi yang jelas -- tanpa itu, kapan
    setelannya hilang bergantung pada kapan pool kebetulan menutup transaksi
    implisitnya.
    """
    with pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                _pasang_penyewa(cur)
                yield cur


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
