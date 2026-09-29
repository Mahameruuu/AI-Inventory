# -*- coding: utf-8 -*-
"""
Model dunia logistik antar gudang: moda angkut, jarak per moda, dan tarif standar.

DUA PEMAKAI, SATU SUMBER. Rekomendasi rute berbasis riwayat (app/rute_ml.py)
memakai berkas ini untuk (a) menyusun kandidat moda bagi satu pasangan gudang
dan (b) menjawab dengan TARIF STANDAR bila riwayat belum cukup untuk melatih
model. Pembangkit riwayat (tools/jaringan_gudang.py) memakai tarif yang sama
sebagai dasar, lalu menaburkan ragam nyata di atasnya. Dua salinan rumus akan
berselisih diam-diam.

APA YANG DIMODELKAN, DAN APA YANG TIDAK.

  darat   truk; hanya bila kedua gudang berada di pulau yang sama.
  laut    kapal kargo/kontainer; menunggu jadwal pelayaran dan bongkar-muat.
  udara   kargo udara; cepat, mahal, dan mahalnya menanjak menurut jumlah barang.

Angka tarifnya PERKIRAAN wajar untuk rute Indonesia, bukan kutipan harga
perusahaan pelayaran tertentu. Perusahaan sungguhan menggantinya dengan tarif
kontraknya; yang tetap berlaku adalah bentuk rumusnya: biaya tetap + jarak x
(tarif per km + jumlah x tarif per unit-km) + asuransi atas nilai barang.
"""

from __future__ import annotations

import math
from typing import Iterable

MODA = ("darat", "laut", "udara")

LABEL_MODA = {
    "darat": {"id": "Darat (truk)", "en": "Road (truck)"},
    "laut": {"id": "Laut (kapal kargo)", "en": "Sea (cargo ship)"},
    "udara": {"id": "Udara (kargo)", "en": "Air (cargo)"},
}

# Parameter tarif standar per moda.
#   tetap        biaya tetap per kiriman (rupiah): surat jalan, muat, dokumen
#   per_km       tarif per kilometer (rupiah)
#   per_unit_km  tambahan per unit barang per kilometer (rupiah)
#   kecepatan    kilometer per hari menempuh jalan/laut/udara
#   tunggu       hari menunggu keberangkatan (jadwal pelayaran, slot kargo)
#   muat         hari bongkar-muat di kedua ujung
#   rugi         porsi barang rusak/hilang dasar
#   asuransi     porsi nilai barang yang dibayar sebagai premi
PARAMETER = {
    "darat": dict(tetap=1_200_000, per_km=6_800, per_unit_km=3.0,
                  kecepatan=650.0, tunggu=0.5, muat=0.5,
                  rugi=0.010, asuransi=0.002),
    "laut": dict(tetap=1_800_000, per_km=2_600, per_unit_km=0.9,
                 kecepatan=800.0, tunggu=3.0, muat=3.0,
                 rugi=0.025, asuransi=0.004),
    "udara": dict(tetap=2_400_000, per_km=4_500, per_unit_km=90.0,
                  kecepatan=1_200.0, tunggu=0.3, muat=0.7,
                  rugi=0.005, asuransi=0.003),
}

# Pengali jarak dari garis lurus (haversine) ke jarak tempuh nyata per moda.
FAKTOR_LAUT = 1.18
FAKTOR_DARAT_TANPA_MATRIKS = 1.30
# Kargo udara tidak dipakai untuk jarak pendek; truk menang telak di sana.
JARAK_UDARA_MIN_KM = 250.0

# Kotak kasar Pulau Jawa. Cukup untuk membedakan "satu pulau" dari "seberang".
_JAWA = (-8.9, -5.8, 105.0, 115.0)   # lintang min, maks; bujur min, maks


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp = p2 - p1
    dl = math.radians(float(lon2) - float(lon1))
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def pulau(lat, lon) -> str:
    """'jawa' atau 'lain'; koordinat kosong dianggap 'lain' (tanpa jalan darat)."""
    if lat is None or lon is None:
        return "lain"
    lat, lon = float(lat), float(lon)
    la0, la1, lo0, lo1 = _JAWA
    return "jawa" if (la0 <= lat <= la1 and lo0 <= lon <= lo1) else "lain"


def jarak_moda(moda: str, gudang_asal: dict, gudang_tujuan: dict,
               jarak_darat_km: float | None = None) -> float | None:
    """
    Jarak tempuh (km) untuk satu moda, atau None bila moda itu tidak tersedia.

    `gudang_*` berisi latitude/longitude. `jarak_darat_km` adalah jarak jalan
    yang ditetapkan tangan (warehouse_distances); bila kosong dipakai haversine
    dikali FAKTOR_DARAT_TANPA_MATRIKS.
    """
    if None in (gudang_asal.get("latitude"), gudang_asal.get("longitude"),
                gudang_tujuan.get("latitude"), gudang_tujuan.get("longitude")):
        return None
    garis = haversine_km(gudang_asal["latitude"], gudang_asal["longitude"],
                         gudang_tujuan["latitude"], gudang_tujuan["longitude"])
    if moda == "darat":
        if pulau(gudang_asal["latitude"], gudang_asal["longitude"]) != \
           pulau(gudang_tujuan["latitude"], gudang_tujuan["longitude"]):
            return None
        return float(jarak_darat_km) if jarak_darat_km else round(
            garis * FAKTOR_DARAT_TANPA_MATRIKS, 1)
    if moda == "laut":
        return round(max(garis * FAKTOR_LAUT, 100.0), 1)
    if moda == "udara":
        return round(garis, 1) if garis >= JARAK_UDARA_MIN_KM else None
    raise ValueError(f"moda tidak dikenal: {moda!r}")


def moda_tersedia(gudang_asal: dict, gudang_tujuan: dict,
                  jarak_darat_km: float | None = None) -> dict[str, float]:
    """{moda: jarak km} untuk seluruh moda yang tersedia pada pasangan ini."""
    hasil = {}
    for m in MODA:
        j = jarak_moda(m, gudang_asal, gudang_tujuan, jarak_darat_km)
        if j is not None:
            hasil[m] = j
    return hasil


def tarif_standar(moda: str, jarak_km: float, jumlah: float, nilai: float = 0.0
                  ) -> dict:
    """
    Perkiraan tanpa riwayat: lama tempuh (hari), biaya (rupiah), dan porsi
    barang yang diterima (0..1).
    """
    p = PARAMETER[moda]
    hari = p["tunggu"] + p["muat"] + jarak_km / p["kecepatan"]
    biaya = (p["tetap"] + jarak_km * (p["per_km"] + jumlah * p["per_unit_km"])
             + p["asuransi"] * max(nilai, 0.0))
    rugi = p["rugi"] * (1.0 + jumlah / 600.0 + jarak_km / 4000.0)
    return {"hari": hari, "biaya": biaya, "terima": max(0.0, 1.0 - rugi)}


def janji_hari(moda: str, jarak_km: float) -> float:
    """Lama tempuh yang DIJANJIKAN saat dokumen diajukan: tarif standar, dibulatkan ke atas."""
    return float(math.ceil(tarif_standar(moda, jarak_km, 0)["hari"]))


def jarak_pasangan(gudang: Iterable[dict]) -> dict:
    """Utilitas: indeks gudang menurut id."""
    return {g["id"]: g for g in gudang}
