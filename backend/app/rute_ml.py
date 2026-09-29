# -*- coding: utf-8 -*-
"""
Rekomendasi rute (moda angkut) terbaik untuk satu kiriman antar gudang.

PERTANYAAN YANG DIJAWAB. Sumber dan tujuannya sudah ditetapkan mesin transfer
(app/transfer.py). Yang tersisa: DIANGKUT LEWAT APA -- darat, laut, atau udara?
Empat hal yang dipertimbangkan: jarak, lama di jalan, biaya, dan jumlah barang
yang benar-benar sampai.

MODEL KLASIK, BUKAN JARINGAN SARAF. Tiga regresor gradient boosting
(scikit-learn) dilatih dari riwayat transfer yang SUDAH SELESAI di perusahaan
yang sedang aktif:

    lama di jalan (hari)   <- selisih shipped_at dan received_at
    biaya angkut (rupiah)  <- shipping_cost, dilatih pada skala log
    porsi barang diterima  <- received_quantity / quantity

Fiturnya: moda, jarak moda itu, jumlah, nilai barang, bulan pengiriman
(sin/cos), dan gudang asal/tujuan. Ketiganya lalu diberi skor berbobot menurut
prioritas yang dipilih pengguna (seimbang, tercepat, termurah, terpenuh).

KEJUJURAN TENTANG DATANYA. Model hanya sebaik riwayat yang dilatihkan padanya.
Pada penyewa demo dan data contoh, riwayat itu DIBANGKITKAN
(tools/jaringan_gudang.py) dari model dunia app/logistik.py ditambah ragam
musiman dan derau; yang dibuktikannya adalah mesinnya bekerja, bukan bahwa
tarif tertentu benar. Pada perusahaan sungguhan, dokumen transfer yang
diselesaikan dengan moda, biaya, dan jumlah diterima tercatat menjadi bahan
latihnya, dan model dilatih ulang otomatis begitu jumlah riwayat berubah.

BILA RIWAYAT BELUM CUKUP (kurang dari MIN_RIWAYAT dokumen, atau scikit-learn
tidak terpasang), jawabannya memakai TARIF STANDAR dari app/logistik.py dan
jawaban menyebut itu di `model.kind` -- layar tidak pernah menyebut hasil tarif
sebagai hasil model.
"""

from __future__ import annotations

import logging
import math
import threading
from datetime import date

from . import logistik

log = logging.getLogger("inventory.rute_ml")

MIN_RIWAYAT = 30

# Bobot tiap prioritas atas empat ukuran. Jumlahnya 1.
PRIORITAS = {
    "seimbang": {"hari": 0.25, "biaya": 0.45, "terima": 0.20, "jarak": 0.10},
    "tercepat": {"hari": 0.65, "biaya": 0.15, "terima": 0.10, "jarak": 0.10},
    "termurah": {"hari": 0.10, "biaya": 0.70, "terima": 0.10, "jarak": 0.10},
    "terpenuh": {"hari": 0.10, "biaya": 0.15, "terima": 0.65, "jarak": 0.10},
}

# Pengurang skor bagi moda yang tiba SESUDAH batas waktu (mis. sesudah pesanan
# pembelian baru akan tiba): transfer yang lebih lambat daripada membeli tidak
# ada gunanya, dan skor tidak boleh menyembunyikan itu.
DENDA_TERLAMBAT = 0.25

_KUNCI_LOCK = threading.Lock()
_CACHE: dict[int, tuple[tuple, "Bundle"]] = {}


class Bundle:
    """Model terlatih beserta ukuran mutunya."""

    def __init__(self, kolom, m_hari, m_biaya, m_terima, metrik, n, rentang):
        self.kolom = kolom
        self.m_hari = m_hari
        self.m_biaya = m_biaya
        self.m_terima = m_terima
        self.metrik = metrik
        self.n = n
        self.rentang = rentang

    def prediksi(self, baris: list[dict]) -> list[dict]:
        import pandas as pd
        X = pd.DataFrame([_fitur(**b) for b in baris]).reindex(
            columns=self.kolom, fill_value=0.0)
        hari = self.m_hari.predict(X)
        biaya = self.m_biaya.predict(X)
        terima = self.m_terima.predict(X)
        return [{"hari": max(0.2, float(h)),
                 "biaya": float(math.exp(b)),
                 "terima": min(1.0, max(0.0, float(t)))}
                for h, b, t in zip(hari, biaya, terima)]


def _fitur(*, moda, jarak, jumlah, nilai, bulan, dari, ke) -> dict:
    """Satu baris fitur; dipakai sama persis untuk melatih dan meramal."""
    f = {f"m_{m}": 1.0 if moda == m else 0.0 for m in logistik.MODA}
    f["jarak"] = float(jarak)
    f["jumlah"] = float(jumlah)
    f["log_jumlah"] = math.log1p(float(jumlah))
    f["log_nilai"] = math.log1p(max(float(nilai), 0.0))
    f["bln_sin"] = math.sin(2 * math.pi * bulan / 12.0)
    f["bln_cos"] = math.cos(2 * math.pi * bulan / 12.0)
    f[f"dari_{dari}"] = 1.0
    f[f"ke_{ke}"] = 1.0
    return f


def _muat(cur) -> tuple[list[dict], dict, dict]:
    cur.execute(
        """
        SELECT t.id, t.from_warehouse_id AS dari, t.to_warehouse_id AS ke,
               t.transport_mode AS moda, t.shipping_cost AS biaya,
               t.shipped_at, t.received_at,
               SUM(ti.quantity) AS jumlah, SUM(ti.received_quantity) AS diterima,
               SUM(ti.quantity * it.unit_price) AS nilai
          FROM stock_transfers t
          JOIN stock_transfer_items ti ON ti.stock_transfer_id = t.id
          JOIN items it ON it.id = ti.item_id
         WHERE t.status = 'completed' AND t.transport_mode IS NOT NULL
           AND t.shipping_cost IS NOT NULL AND t.shipped_at IS NOT NULL
           AND t.received_at IS NOT NULL AND ti.received_quantity IS NOT NULL
         GROUP BY t.id
         ORDER BY t.id
        """)
    riwayat = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT id, code, name, latitude, longitude FROM warehouses")
    gudang = {r["id"]: dict(r) for r in cur.fetchall()}
    cur.execute("SELECT from_warehouse_id AS a, to_warehouse_id AS b, distance_km "
                "FROM warehouse_distances")
    matriks = {(r["a"], r["b"]): (float(r["distance_km"]) if r["distance_km"] is not None else None)
               for r in cur.fetchall()}
    return riwayat, gudang, matriks


def _jarak(moda, dari, ke, gudang, matriks):
    return logistik.jarak_moda(moda, gudang[dari], gudang[ke],
                               matriks.get((dari, ke)))


def _latih(riwayat, gudang, matriks) -> "Bundle | None":
    try:
        import numpy as np
        import pandas as pd
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import KFold, cross_val_predict
    except Exception as e:  # pustaka tidak terpasang
        log.warning("scikit-learn tidak tersedia: %s", e)
        return None

    baris, y_hari, y_biaya, y_terima = [], [], [], []
    for r in riwayat:
        j = _jarak(r["moda"], r["dari"], r["ke"], gudang, matriks)
        if j is None or not r["jumlah"]:
            continue
        hari = (r["received_at"] - r["shipped_at"]).total_seconds() / 86400.0
        if hari <= 0 or float(r["biaya"]) <= 0:
            continue
        baris.append(_fitur(moda=r["moda"], jarak=j, jumlah=float(r["jumlah"]),
                            nilai=float(r["nilai"] or 0), bulan=r["shipped_at"].month,
                            dari=r["dari"], ke=r["ke"]))
        y_hari.append(hari)
        y_biaya.append(math.log(float(r["biaya"])))
        y_terima.append(float(r["diterima"]) / float(r["jumlah"]))
    if len(baris) < MIN_RIWAYAT:
        return None

    X = pd.DataFrame(baris).fillna(0.0)
    kolom = list(X.columns)
    y_h, y_b, y_t = map(np.asarray, (y_hari, y_biaya, y_terima))

    def model():
        return GradientBoostingRegressor(
            n_estimators=160, max_depth=3, learning_rate=0.07, subsample=0.9,
            random_state=0)

    kf = KFold(n_splits=5, shuffle=True, random_state=0)
    metrik = {}
    for nama, y in (("hari", y_h), ("biaya", y_b), ("terima", y_t)):
        pred = cross_val_predict(model(), X, y, cv=kf)
        if nama == "hari":
            metrik["hari_mae"] = float(np.mean(np.abs(pred - y)))
        elif nama == "biaya":
            metrik["biaya_mape"] = float(np.mean(np.abs(np.exp(pred) - np.exp(y)) / np.exp(y)))
        else:
            metrik["terima_mae"] = float(np.mean(np.abs(pred - y)))

    m_h, m_b, m_t = model().fit(X, y_h), model().fit(X, y_b), model().fit(X, y_t)
    tgl = [r["shipped_at"].date() for r in riwayat]
    return Bundle(kolom, m_h, m_b, m_t, metrik, len(baris),
                  {"dari": str(min(tgl)), "sampai": str(max(tgl))})


def bundel(cur) -> tuple["Bundle | None", dict, dict, int]:
    """Model terlatih untuk perusahaan aktif (di-cache; dilatih ulang bila riwayat berubah)."""
    cur.execute("SELECT NULLIF(current_setting('app.company_id', true), '')::bigint AS c")
    cid = int(cur.fetchone()["c"] or 0)
    riwayat, gudang, matriks = _muat(cur)
    kunci = (len(riwayat), riwayat[-1]["id"] if riwayat else 0)
    with _KUNCI_LOCK:
        tersimpan = _CACHE.get(cid)
        if tersimpan and tersimpan[0] == kunci:
            return tersimpan[1], gudang, matriks, len(riwayat)
        b = _latih(riwayat, gudang, matriks)
        if b is not None:
            _CACHE[cid] = (kunci, b)
        else:
            _CACHE.pop(cid, None)
        return b, gudang, matriks, len(riwayat)


def _terhadap_terbaik(nilai: list[float], kecil_lebih_baik: bool = True) -> list[float]:
    """Skala 0..1 RELATIF terhadap yang terbaik (bukan min-max): selisih kecil tetap kecil."""
    if kecil_lebih_baik:
        terbaik = min(nilai)
        return [terbaik / v if v > 1e-12 else 1.0 for v in nilai]
    terbaik = max(nilai)
    return [v / terbaik if terbaik > 1e-12 else 1.0 for v in nilai]


def rekomendasi(cur, *, dari_id: int, ke_id: int, jumlah: float, nilai: float = 0.0,
                prioritas: str = "seimbang", tanggal: date | None = None,
                batas_hari: float | None = None, konteks=None) -> dict:
    """
    Seluruh moda yang tersedia pada pasangan ini, diperingkat menurut prioritas.

    `konteks` (hasil bundel(cur)) boleh diberikan pemanggil yang meminta banyak
    rekomendasi sekaligus: model dan riwayatnya cukup dimuat SEKALI.
    """
    if prioritas not in PRIORITAS:
        raise ValueError(f"prioritas harus salah satu dari: {', '.join(PRIORITAS)}")
    tanggal = tanggal or date.today()
    b, gudang, matriks, n_riwayat = konteks if konteks is not None else bundel(cur)
    if dari_id not in gudang or ke_id not in gudang:
        raise KeyError("gudang tidak ditemukan")

    tersedia = logistik.moda_tersedia(gudang[dari_id], gudang[ke_id],
                                      matriks.get((dari_id, ke_id)))
    if not tersedia:
        return {"options": [], "recommended_mode": None,
                "model": _info(b, n_riwayat)}

    moda_list = list(tersedia)
    if b is not None:
        pred = b.prediksi([
            dict(moda=m, jarak=tersedia[m], jumlah=jumlah, nilai=nilai,
                 bulan=tanggal.month, dari=dari_id, ke=ke_id) for m in moda_list])
    else:
        pred = [logistik.tarif_standar(m, tersedia[m], jumlah, nilai)
                for m in moda_list]

    hari = [p["hari"] for p in pred]
    biaya = [p["biaya"] for p in pred]
    terima = [p["terima"] for p in pred]
    jarak = [tersedia[m] for m in moda_list]
    per_unit = nilai / jumlah if jumlah else 0.0
    # Biaya TOTAL: ongkos ditambah nilai barang yang diperkirakan rusak/hilang.
    # Moda murah yang sering merusak barang mahal tidak boleh tampak murah.
    rugi_rp = [(1.0 - t) * jumlah * per_unit for t in terima]
    total = [b + r for b, r in zip(biaya, rugi_rp)]
    w = PRIORITAS[prioritas]
    s_hari = _terhadap_terbaik(hari)
    s_biaya = _terhadap_terbaik(total)
    s_terima = _terhadap_terbaik(terima, kecil_lebih_baik=False)
    s_jarak = _terhadap_terbaik(jarak)
    opsi = []
    for i, m in enumerate(moda_list):
        utilitas = (w["hari"] * s_hari[i] + w["biaya"] * s_biaya[i]
                    + w["terima"] * s_terima[i] + w["jarak"] * s_jarak[i])
        terlambat = batas_hari is not None and hari[i] > batas_hari
        if terlambat:
            utilitas -= DENDA_TERLAMBAT
        opsi.append({
            "mode": m,
            "label": logistik.LABEL_MODA[m],
            "distance_km": round(jarak[i], 1),
            "predicted_days": round(hari[i], 1),
            "predicted_cost": round(biaya[i], -3),
            "cost_per_unit": round(biaya[i] / max(jumlah, 1), -2),
            "predicted_received": int(round(jumlah * terima[i])),
            "predicted_received_ratio": round(terima[i], 4),
            "expected_loss_value": round(rugi_rp[i], -3),
            "total_cost": round(total[i], -3),
            "late": bool(terlambat),
            "score": max(0, round(100 * utilitas)),
        })
    opsi.sort(key=lambda o: (-o["score"], o["total_cost"]))
    for r, o in enumerate(opsi, start=1):
        o["rank"] = r
        o["badges"] = []
    if len(opsi) > 1:
        def tandai(kunci, nama, terbesar=False):
            pilih = (max if terbesar else min)(opsi, key=lambda o: o[kunci])
            pilih["badges"].append(nama)
        tandai("predicted_days", "tercepat")
        tandai("predicted_cost", "termurah")
        tandai("predicted_received", "terpenuh", terbesar=True)
        tandai("distance_km", "terdekat")
    return {
        "from_warehouse_id": dari_id, "to_warehouse_id": ke_id,
        "quantity": jumlah, "priority": prioritas, "deadline_days": batas_hari,
        "options": opsi,
        "recommended_mode": opsi[0]["mode"],
        "model": _info(b, n_riwayat),
    }


def _info(b: "Bundle | None", n_riwayat: int) -> dict:
    if b is None:
        return {"kind": "tarif_standar", "n_train": n_riwayat,
                "min_history": MIN_RIWAYAT}
    return {"kind": "ml", "algorithm": "GradientBoostingRegressor",
            "n_train": b.n, "min_history": MIN_RIWAYAT,
            "range": b.rentang, "metrics": {k: round(v, 4) for k, v in b.metrik.items()}}
