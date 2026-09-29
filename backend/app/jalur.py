# -*- coding: utf-8 -*-
"""
Geometri jalan antar dua koordinat, untuk peta Transfer Antar Gudang.

SUMBERNYA OSRM, DAN DIA HANYA PENYEDIA GARIS. Tidak ada angka bisnis di sini:
jarak dan lead time yang menentukan peringkat transfer tetap datang dari
app/transfer.py. Berkas ini hanya menjawab "seperti apa bentuk jalan dari A ke
B" supaya peta dapat menggambar truk di atas jalan, bukan di atas busur.

HASILNYA DISIMPAN (tabel road_route_cache, migrasi 032) dan hanya keberhasilan
yang disimpan. Server demo OSRM bukan layanan produksi; menanyakannya sekali per
pasangan gudang menjaga kita tetap sopan, dan kegagalan sementara tidak boleh
membeku menjadi "tidak ada jalan" untuk selamanya.

BEBERAPA JALUR, TANPA KLAIM KEAMANAN. OSRM diminta memberi alternatif
(`alternatives=3`; jalan antarpulau biasanya hanya menghasilkan dua). Yang
diberi label hanya yang dapat diukur: tercepat menurut durasi, terpendek
menurut jarak. Tidak ada label "aman": OSRM tidak punya data itu, dan label
yang dikarang lebih berbahaya daripada tidak ada label. Durasinya perkiraan
jalan lengang tanpa lalu lintas langsung.

BILA OSRM TIDAK DAPAT DIJANGKAU, fungsi ini mengembalikan None dan peta
kembali ke busur. Rute yang tak bisa digambar mengikuti jalan tetap harus
tergambar; gambar yang salah lebih baik daripada layar kosong, dan peta
menyebutkan bahwa yang tampil adalah garis kira-kira.
"""

from __future__ import annotations

import json
import logging
import math
import re

import httpx

from .config import (BIAYA_OPERASIONAL_PER_JAM, HARGA_SOLAR_PER_LITER, JALUR_MAKS_PILIHAN,
                     JALUR_PERANTARA, OSRM_TIMEOUT_DETIK, OSRM_URL, TARIF_TOL_PER_KM, TRUK_GOLONGAN_TOL, TRUK_KM_PER_LITER)
from .db import readonly, transaction

log = logging.getLogger("inventory.jalur")

# Batas titik yang dikirim ke peta. Surabaya -> Jakarta mentah berisi ~10 ribu
# titik; itu ratusan kilobita per rute untuk detail yang tak terlihat pada zoom
# mana pun yang muat satu pulau. 600 titik tetap membelokkan garis di tikungan
# besar.
MAKS_TITIK = 600


def _bulat(x: float) -> float:
    return round(float(x), 4)


def _jarak_ke_ruas(p, a, b) -> float:
    """Jarak p ke ruas a-b dalam derajat datar (cukup untuk memilah titik)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def sederhanakan(titik: list[list[float]], maks: int = MAKS_TITIK) -> list[list[float]]:
    """
    Douglas-Peucker iteratif, dengan ambang dinaikkan sampai jumlah titiknya
    muat. Iteratif, bukan rekursif: 10 ribu titik pada jalan lurus panjang
    melampaui batas rekursi Python.
    """
    if len(titik) <= maks:
        return titik

    def dp(eps: float) -> list[list[float]]:
        simpan = [False] * len(titik)
        simpan[0] = simpan[-1] = True
        tumpukan = [(0, len(titik) - 1)]
        while tumpukan:
            i, j = tumpukan.pop()
            if j <= i + 1:
                continue
            jauh, idx = -1.0, -1
            for k in range(i + 1, j):
                d = _jarak_ke_ruas(titik[k], titik[i], titik[j])
                if d > jauh:
                    jauh, idx = d, k
            if jauh > eps:
                simpan[idx] = True
                tumpukan.append((i, idx))
                tumpukan.append((idx, j))
        return [p for p, s in zip(titik, simpan) if s]

    eps = 0.0002  # ~22 m
    hasil = dp(eps)
    while len(hasil) > maks:
        eps *= 1.6
        hasil = dp(eps)
    return hasil


_POLA_TOL = re.compile(r"\b(tol|toll)\b", re.IGNORECASE)


def _ukur_tol(rute: dict) -> tuple[int, bool]:
    """
    Panjang ruas tol (meter) dan ada-tidaknya penyeberangan feri pada satu rute.

    TOL DIKENALI DARI NAMA RUAS ("Jalan Tol Cikopo-Palimanan"), karena server
    OSRM publik tidak menyediakan penanda tol. Konsekuensinya jujur: ruas tol
    yang namanya tidak memuat kata "tol" tidak terhitung, jadi angkanya bisa
    lebih rendah dari sebenarnya, tidak pernah lebih tinggi.
    """
    tol = 0.0
    feri = False
    for leg in rute.get("legs", []):
        for st in leg.get("steps", []):
            if st.get("mode") == "ferry":
                feri = True
            if _POLA_TOL.search(st.get("name") or ""):
                tol += float(st.get("distance") or 0)
    return int(tol), feri


def beri_label(opsi: list[dict]) -> list[dict]:
    """
    Menandai jalur tercepat dan terpendek. Satu jalur boleh memegang keduanya,
    dan bila hanya ada satu jalur, ia tidak diberi pembanding apa pun.
    """
    if not opsi:
        return opsi
    tercepat = min(range(len(opsi)), key=lambda i: opsi[i]["duration_s"])
    terpendek = min(range(len(opsi)), key=lambda i: opsi[i]["distance_m"])
    for i, o in enumerate(opsi):
        o["tercepat"] = i == tercepat
        o["terpendek"] = i == terpendek
    return opsi


def _opsi_dari_rute(rute: dict, dari, ke, via: str | None) -> dict | None:
    # GeoJSON berurutan [lon, lat]; peta memakai [lat, lon].
    titik = [[c[1], c[0]] for c in rute["geometry"]["coordinates"]]
    if len(titik) < 2:
        return None
    pts = sederhanakan(titik)
    # Ujungnya dipaksa tepat pada gudang: OSRM menempelkannya ke jalan
    # terdekat, dan garis yang berhenti 300 m dari penanda gudang
    # terlihat seperti rute yang meleset.
    pts[0] = [dari[0], dari[1]]
    pts[-1] = [ke[0], ke[1]]
    tol_m, feri = _ukur_tol(rute)
    return {
        "points": pts,
        "distance_m": int(rute.get("distance") or 0),
        "duration_s": int(rute.get("duration") or 0),
        "tol_m": tol_m,
        "feri": feri,
        "via": via,
    }


def _panggil_osrm(koordinat: list[tuple[float, float]], alternatif: bool):
    """Daftar rute mentah OSRM untuk urutan titik (lat, lon), atau None."""
    url = (f"{OSRM_URL}/route/v1/driving/"
           + ";".join(f"{lon},{lat}" for lat, lon in koordinat))
    try:
        r = httpx.get(
            url,
            params={"overview": "full", "geometries": "geojson",
                    "alternatives": "3" if alternatif else "false", "steps": "true"},
            timeout=OSRM_TIMEOUT_DETIK,
            headers={"User-Agent": "inventory-ai/1.0"},
        )
        r.raise_for_status()
        j = r.json()
        if j.get("code") != "Ok" or not j.get("routes"):
            return None
        return j["routes"]
    except (httpx.HTTPError, ValueError, KeyError) as e:
        log.warning("OSRM gagal untuk %s: %s", koordinat, e)
        return None


def _datar(p, ref) -> tuple[float, float]:
    """Titik (lat, lon) -> km datar terhadap ref; cukup untuk memilah kota."""
    return ((p[1] - ref[1]) * 111.32 * math.cos(math.radians(ref[0])),
            (p[0] - ref[0]) * 110.57)


def pilih_perantara(dari, ke, kota=None, per_sisi: int = 3) -> list[tuple[str, float, float]]:
    """
    Kota perantara untuk mencari koridor lain, sedikit di tiap sisi garis lurus.

    Syaratnya: berada di antara kedua ujung (15-85% panjang garis), menyimpang
    dari garis sedikitnya 8% panjangnya (di bawah itu jalannya sama saja dengan
    jalan langsung), dan memperpanjang tempuh tidak lebih dari 40%. Di tiap
    sisi dipakai yang paling kecil pengalihannya, dengan jarak antar kota
    sedikitnya 15% panjang garis.
    """
    kota = JALUR_PERANTARA if kota is None else kota
    bx, by = _datar(ke, dari)
    d = math.hypot(bx, by)
    if d < 1:
        return []
    sisi: dict[int, list[tuple[float, float, tuple[str, float, float]]]] = {1: [], -1: []}
    for nama, lat, lon in kota:
        x, y = _datar((lat, lon), dari)
        sepanjang = (x * bx + y * by) / (d * d)
        samping = (bx * y - by * x) / d
        if not (0.15 <= sepanjang <= 0.85) or abs(samping) < 0.08 * d:
            continue
        alih = (math.hypot(x, y) + math.hypot(bx - x, by - y)) / d
        if alih > 1.4:
            continue
        sisi[1 if samping > 0 else -1].append((alih, sepanjang, (nama, lat, lon)))
    hasil = []
    for daftar in sisi.values():
        daftar.sort(key=lambda t: t[0])
        # Menyebar sepanjang garis: dua kota yang berdekatan menghasilkan
        # koridor yang sama, dan panggilan keduanya terbuang.
        pilih: list[tuple[float, tuple[str, float, float]]] = []
        for _, pos, k in daftar:
            if all(abs(pos - q) >= 0.15 for q, _ in pilih):
                pilih.append((pos, k))
            if len(pilih) == per_sisi:
                break
        hasil += [k for _, k in pilih]
    return hasil


def _tumpang_tindih(kandidat: list[list[float]], lain: list[list[float]], radius_km: float = 4.0) -> float:
    """Bagian titik kandidat yang berada dalam radius_km dari garis `lain`."""
    if len(kandidat) < 2 or len(lain) < 2:
        return 0.0
    ref = lain[0]
    l = [_datar(p, ref) for p in lain]
    langkah = max(1, len(kandidat) // 40)
    sampel = [_datar(p, ref) for p in kandidat[::langkah]]
    dekat = 0
    for p in sampel:
        if min(_jarak_ke_ruas(p, l[i], l[i + 1]) for i in range(len(l) - 1)) <= radius_km:
            dekat += 1
    return dekat / len(sampel)


def gabung_pilihan(opsi: list[dict], maks: int = 0) -> list[dict]:
    """
    Membuang jalur yang hampir berimpit dengan jalur yang lebih dulu ada, lalu
    memangkas ke `maks`. Urutan masuk = prioritas, jadi jalur langsung dari
    OSRM menang atas jalur via yang menyusurinya.
    """
    maks = maks or JALUR_MAKS_PILIHAN
    terpilih: list[dict] = []
    for o in opsi:
        if any(_tumpang_tindih(o["points"], t["points"]) > 0.8 for t in terpilih):
            continue
        terpilih.append(o)
    terpilih = terpilih[:maks]
    terpilih.sort(key=lambda o: o["duration_s"])
    return terpilih


def _dari_osrm(dari: tuple[float, float], ke: tuple[float, float]):
    rutes = _panggil_osrm([dari, ke], alternatif=True)
    if rutes is None:
        return None
    opsi = [o for r in rutes[:3] if (o := _opsi_dari_rute(r, dari, ke, None))]
    if not opsi:
        return None
    # Koridor lain lewat kota perantara. Kegagalan satu kota tidak membatalkan
    # yang lain: jalur langsungnya sudah di tangan.
    for nama, lat, lon in pilih_perantara(dari, ke):
        r = _panggil_osrm([dari, (lat, lon), ke], alternatif=False)
        if r and (o := _opsi_dari_rute(r[0], dari, ke, nama)):
            opsi.append(o)
    return beri_label(gabung_pilihan(opsi))


def jalur(dari: tuple[float, float], ke: tuple[float, float]):
    """
    Daftar pilihan jalur (tercepat lebih dulu), atau None bila jalannya tidak
    dapat diperoleh. Tiap pilihan: points, distance_m, duration_s, tercepat,
    terpendek.
    """
    k = (_bulat(dari[0]), _bulat(dari[1]), _bulat(ke[0]), _bulat(ke[1]))

    with readonly() as cur:
        cur.execute(
            "SELECT routes FROM road_route_cache "
            "WHERE from_lat=%s AND from_lon=%s AND to_lat=%s AND to_lon=%s",
            k,
        )
        baris = cur.fetchone()
    # Baris lama (migrasi 032, sebelum tol diukur, atau sebelum jalur via
    # kota perantara ada) dianggap tidak ada dan diambil ulang.
    if baris and baris["routes"] and "via" in baris["routes"][0]:
        return baris["routes"]

    opsi = _dari_osrm(dari, ke)
    if opsi is None:
        return None

    with transaction() as cur:
        cur.execute(
            "INSERT INTO road_route_cache (from_lat, from_lon, to_lat, to_lon, "
            "points, distance_m, routes) VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s::jsonb) "
            "ON CONFLICT (from_lat, from_lon, to_lat, to_lon) DO UPDATE SET "
            "points = EXCLUDED.points, distance_m = EXCLUDED.distance_m, "
            "routes = EXCLUDED.routes, fetched_at = now()",
            (*k, json.dumps(opsi[0]["points"]), opsi[0]["distance_m"], json.dumps(opsi)),
        )
    return opsi


# --------------------------------------------------------------------------
# Rekomendasi
# --------------------------------------------------------------------------

def asumsi() -> dict:
    """Asumsi biaya yang berlaku, dikirim ke layar bersama hasilnya."""
    return {
        "golongan_tol": TRUK_GOLONGAN_TOL,
        "km_per_liter": TRUK_KM_PER_LITER,
        "harga_solar_per_liter": HARGA_SOLAR_PER_LITER,
        "tarif_tol_per_km": TARIF_TOL_PER_KM,
        "biaya_per_jam": BIAYA_OPERASIONAL_PER_JAM,
    }


def _ribuan(x: float) -> int:
    # Dibulatkan ke ribuan: menampilkan Rp 812.437 untuk perkiraan tarif tol
    # rata-rata adalah ketelitian yang tidak dimiliki angkanya.
    return int(round(x / 1000.0) * 1000)


def analisis(opsi: list[dict]) -> dict:
    """
    Biaya tiap jalur dan jalur yang paling sepadan.

    total = bahan bakar + tol + (lama tempuh x biaya operasional per jam)

    Tiap komponen dikalikan ASUMSI dari config, dan seluruhnya deterministik:
    jalur yang sama dengan asumsi yang sama selalu menghasilkan jawaban yang
    sama, dan setiap kalimat alasan disusun dari angka yang tampil di kartu.

    Yang dipilih adalah total terendah; bila sama, yang lebih cepat.
    Penyeberangan feri TIDAK dihitung tarifnya (tidak ada sumbernya) dan
    ditandai pada jalurnya; jalur berferi tidak diam-diam tampak lebih murah.
    """
    a = asumsi()
    for o in opsi:
        km = o["distance_m"] / 1000.0
        liter = km / a["km_per_liter"]
        bbm = liter * a["harga_solar_per_liter"]
        tol = o["tol_m"] / 1000.0 * a["tarif_tol_per_km"]
        waktu = o["duration_s"] / 3600.0 * a["biaya_per_jam"]
        o["biaya"] = {
            "liter": round(liter, 1),
            "bbm": _ribuan(bbm),
            "tol": _ribuan(tol),
            "waktu": _ribuan(waktu),
            "total": _ribuan(bbm + tol + waktu),
            "_mentah": bbm + tol + waktu,
        }

    idx = min(range(len(opsi)), key=lambda i: (opsi[i]["biaya"]["_mentah"], opsi[i]["duration_s"]))
    for o in opsi:
        del o["biaya"]["_mentah"]

    pilih = opsi[idx]
    cepat = next(i for i, o in enumerate(opsi) if o["tercepat"])
    alasan: list[dict] = []
    if len(opsi) == 1:
        alasan.append({"kode": "satu_jalur"})
    elif idx == cepat:
        murah_kedua = [i for i in range(len(opsi)) if i != idx]
        # Dibandingkan dengan jalur yang paling dekat total biayanya.
        lain = min(murah_kedua, key=lambda i: opsi[i]["biaya"]["total"])
        alasan.append({
            "kode": "tercepat_dan_hemat" if opsi[lain]["biaya"]["total"] >= pilih["biaya"]["total"] else "tercepat",
            "lawan": lain,
            "hemat_rp": max(0, opsi[lain]["biaya"]["total"] - pilih["biaya"]["total"]),
            "hemat_detik": opsi[lain]["duration_s"] - pilih["duration_s"],
        })
    else:
        alasan.append({
            "kode": "hemat_walau_lebih_lama",
            "lawan": cepat,
            "hemat_rp": opsi[cepat]["biaya"]["total"] - pilih["biaya"]["total"],
            "lebih_lama_detik": pilih["duration_s"] - opsi[cepat]["duration_s"],
        })
    if pilih["tol_m"] != min(o["tol_m"] for o in opsi):
        alasan.append({"kode": "tol_lebih_banyak"})
    if any(o["feri"] for o in opsi):
        alasan.append({"kode": "ada_feri"})
    return {"index": idx, "alasan": alasan}
