# -*- coding: utf-8 -*-
"""
Kendali penyewa demo dari antarmuka.

Dua endpoint, dan seluruhnya hanya berlaku pada perusahaan bertanda demo --
penjagaannya ada di app/demo.py dan berlaku sekalipun endpoint ini dipanggil
langsung tanpa lewat layar.

KENAPA MENULIS KE BASIS DATA, BUKAN MENGHITUNG SAJA. Simulasi yang tidak
menyimpan apa pun hanya bisa menjawab "kalau dijual 500, sisanya berapa" --
sebuah kalkulator. Yang menjual sistem ini bukan angka itu, melainkan seluruh
sistem yang ikut bergerak sesudahnya: kartu di dasbor berubah, halaman stok
menipis terisi, prakiraan bergeser, rekomendasi pemesanan menyesuaikan diri.
Itu hanya terjadi bila transaksinya benar-benar tercatat.

Yang membuatnya aman bukan karena tidak menulis, melainkan karena yang ditulis
berada di penyewa terpisah yang boleh dikosongkan kapan saja.
"""

from fastapi import APIRouter, Depends, Query

from .. import tenant
from ..auth import pengguna_saat_ini, wajib_admin
from ..db import readonly, transaction
from .. import demo

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.get("/status")
def status(_: tenant.Penyewa = Depends(pengguna_saat_ini)) -> dict:
    """
    Apakah perusahaan ini penyewa demo, dan seberapa terisi.

    Dibuka untuk seluruh peran, termasuk viewer: antarmuka memakainya untuk
    memutuskan menampilkan tombol demo atau tidak, dan pertanyaan itu sendiri
    tidak membocorkan apa-apa. Yang dibatasi peran adalah tombolnya, bukan
    pengetahuan bahwa ia ada.
    """
    with readonly() as cur:
        cur.execute("SELECT id, name, slug, is_demo FROM companies")
        perusahaan = cur.fetchone()
        if not perusahaan or not perusahaan["is_demo"]:
            return {"is_demo": False}

        cur.execute("SELECT count(*) AS n FROM items")
        barang = cur.fetchone()["n"]
        cur.execute("SELECT count(*) AS n FROM stock_issues")
        pengeluaran = cur.fetchone()["n"]
        cur.execute(
            """
            SELECT count(*) AS n
              FROM inventory inv JOIN items it ON it.id = inv.item_id
             WHERE it.reorder_point IS NOT NULL
               AND inv.available_quantity <= it.reorder_point
            """
        )
        menipis = cur.fetchone()["n"]

    return {
        "is_demo": True,
        "company": {"id": perusahaan["id"], "name": perusahaan["name"]},
        "terisi": barang > 0,
        "barang": barang,
        "pengeluaran": pengeluaran,
        "barang_menipis": menipis,
    }


@router.post("/reset", dependencies=[Depends(wajib_admin)])
def setel_ulang(
    hari: int = Query(demo.HARI_RIWAYAT, ge=14, le=365,
                      description="Panjang riwayat yang dibangkitkan"),
) -> dict:
    """
    Mengosongkan perusahaan demo lalu mengisinya kembali dari nol.

    Satu transaksi, sehingga demo tidak pernah tertangkap dalam keadaan
    setengah terisi. Bila pengisian gagal di tengah, ROLLBACK mengembalikan
    data demo yang lama -- lebih baik daripada perusahaan kosong sepuluh menit
    sebelum presentasi.
    """
    with transaction() as cur:
        terhapus = demo.kosongkan(cur)
        ringkas = demo.isi(cur, hari)
    return {"terhapus": terhapus, "terisi": ringkas}
