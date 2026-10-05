# -*- coding: utf-8 -*-
"""
Endpoint prakiraan yang dipakai halaman Forecasting.

    GET /api/forecast?warehouse_id=1&item_id=1&days=7

Bentuk jawabannya sengaja rata dan memakai penamaan yang dipakai antarmuka
(current_stock, forecast_usage, expected_stock, reorder_point) supaya angka di
kartu, grafik, dan rekomendasi datang dari satu sumber yang sama dan mustahil
berselisih.

Perhitungan sepenuhnya dilakukan mesin di app/forecasting.py. Model bahasa
hanya menerima hasil yang sudah jadi untuk dijelaskan, dan bila ia mati,
rekomendasi tetap terbit dalam bentuk yang disusun dari angka.
"""

from datetime import date

from fastapi import APIRouter, Query, Request

from .. import decision, i18n
from .. import rop
from ..limiter import limiter
from ..ml import klasik, predict
from . import forecasting as inti

router = APIRouter(tags=["forecast"])

# Hanya endpoint yang benar-benar berat -- yang menyusun riwayat dan, bila
# modelnya dipilih, memanggil inferensi XGBoost -- yang dibatasi. /models
# sengaja tidak disentuh: isinya metadata statis, tidak ada perhitungan.
# Batasnya per pengguna (lihat app/limiter.py), longgar untuk pemakaian wajar
# (beberapa barang dibuka berurutan di layar Forecasting) tapi menutup jalan
# spam otomatis atau bug retry-tanpa-henti di klien.
BATAS_BERAT = "30/minute"


@router.get("/api/forecast/rop")
@limiter.limit(BATAS_BERAT)
def titik_pesan(
    request: Request,
    warehouse_id: int = Query(..., gt=0),
    item_id: int = Query(..., gt=0),
    model: str = Query(klasik.KUNCI_STATISTIK,
                       description=("Model prakiraan yang menjadi input rantai. "
                                    "Bawaannya rumus statistik sederhana: "
                                    "rata-rata riwayat, cadangan dari simpangan "
                                    "baku permintaan harian, tanpa adu model.")),
    strategy: str = Query(rop.STRATEGI_BAWAAN,
                          description="aman (98%) | standar (90%) | hemat (80%)"),
    lead_time_days: float | None = Query(
        None, ge=0,
        description=("Masa tunggu dalam hari. Kosongkan untuk memakai yang "
                     "tercatat pada master barang; diisi untuk menguji "
                     "pemasok lain tanpa mengubah masternya."),
    ),
    lang: str = Query(i18n.BAHASA_BAWAAN),
) -> dict:
    """
    Titik pesan ulang: ROP = permintaan harian x masa tunggu + safety stock.

    DUA JALAN MENUJU KEDUA ANGKANYA, dan bawaannya yang sederhana. Pada model
    "statistik", permintaan adalah rata-rata riwayat dan cadangannya Z x masa
    tunggu x simpangan baku permintaan harian -- tanpa satu pun model diadu.
    Pada model lain, keduanya turun dari rantai model: permintaan dari
    ramalannya, cadangan dari galat backtest model itu sendiri, sehingga
    mengganti model mengubah kedua sisi rumusnya sekaligus. Lihat app/rop.py.

    `safety_stock_basis` pada jawaban menyebut jalan mana yang ditempuh, dan
    itu wajib ada: `model_rmse` berisi dua besaran yang berbeda artinya
    tergantung jalannya, dan pada mode "terbaik" pembacanya tidak dapat
    menebaknya dari model yang diminta.

    Jawabannya sengaja ringkas: tujuh ruas, tanpa lapisan keputusan lain yang
    sudah dijawab /api/forecast. Endpoint ini menjawab satu pertanyaan saja.
    """
    h = inti._susun(item_id, warehouse_id, 7, inti.HISTORICAL_DAYS_DEFAULT,
                    lang, inti._model_sah(model), strategy)
    # Model ML disertakan supaya ia benar-benar dapat dipilih pada rantai ini,
    # bukan diam-diam jatuh ke cadangan. Bila berkas modelnya tidak termuat,
    # nilainya None dan rop.py memutuskan sendiri apa yang dilaporkannya.
    ml = inti.ml_untuk(item_id, warehouse_id)
    return rop.hitung_rop(
        riwayat=h["riwayat_harian"],
        lead_time_days=(lead_time_days if lead_time_days is not None
                        else h["lead_time_days"]),
        model=inti._model_sah(model),
        strategi=strategy,
        as_of=date.fromisoformat(h["as_of"]),
        tambahan={klasik.KUNCI_ML: ml} if ml else None,
    )


@router.get("/api/forecast/models")
def daftar_model(
    lang: str = Query(i18n.BAHASA_BAWAAN, description="Bahasa nama model."),
) -> dict:
    """
    Daftar model yang boleh dipilih, berikut namanya di layar.

    Diterbitkan sebagai endpoint, BUKAN disalin ke kamus frontend. Daftar yang
    hidup di dua tempat akan berbeda isinya cepat atau lambat, dan yang
    terlihat pengguna adalah pilihan yang justru ditolak backend. Di sini
    urutannya pun ikut ditentukan backend, sehingga menambah model kelak cukup
    disentuh di satu berkas.
    """
    return {
        "items": [
            {
                "key": k,
                "label": i18n.t(f"model.{k}", lang),
                "description": i18n.t(f"model.desc.{k}", lang),
                # Model pembelajaran mesin bergantung pada berkas model yang
                # dipasang saat deploy. Bila ia tidak termuat, pilihannya tetap
                # disebut tetapi ditandai supaya layar dapat menonaktifkannya
                # alih-alih membiarkan pengguna memilih sesuatu yang diam-diam
                # jatuh ke cadangan.
                "available": predict.tersedia() if k == klasik.KUNCI_ML else True,
            }
            for k in klasik.semua_kunci()
        ],
        "default": klasik.KUNCI_STATISTIK,
        # Strategi ikut di sini, bukan di endpoint sendiri: keduanya adalah
        # "pilihan yang tersedia untuk layar prakiraan", dan layar itu hanya
        # perlu satu perjalanan untuk memuat kedua dropdownnya.
        "strategies": [
            {
                "key": k,
                "label": i18n.t(f"strategi.{k}", lang),
                "description": i18n.t(f"strategi.desc.{k}", lang),
                "service_level": v.service_level,
                "z": v.z,
            }
            for k, v in rop.STRATEGI.items()
        ],
        "strategy_default": rop.STRATEGI_BAWAAN,
    }


@router.get("/api/forecast")
@limiter.limit(BATAS_BERAT)
def forecast(
    request: Request,
    warehouse_id: int = Query(..., gt=0),
    item_id: int = Query(..., gt=0),
    days: int = Query(7, ge=1, le=inti.FORECAST_DAYS_MAX),
    historical_days: int = Query(
        inti.HISTORICAL_DAYS_DEFAULT, ge=7, le=inti.HISTORICAL_DAYS_MAX
    ),
    include_recommendation: bool = Query(
        True,
        description=(
            "Sertakan rekomendasi. Setel false untuk memuat kartu dan grafik "
            "lebih dulu tanpa menunggu layanan AI."
        ),
    ),
    lang: str = Query(
        i18n.BAHASA_BAWAAN,
        description=(
            "Bahasa seluruh kalimat penjelas pada jawaban ini: id atau en. "
            "Angkanya sendiri tidak berubah."
        ),
    ),
    model: str = Query(
        klasik.KUNCI_STATISTIK,
        description=(
            "Model prakiraan yang dipakai. Bawaannya 'statistik' -- rata-rata "
            "riwayat, tanpa model apa pun. 'best' mengadu seluruh model di "
            "atas riwayat barang ini lalu memakai pemenangnya, dan papan "
            "skornya ikut terbit pada model_scoreboard."
        ),
    ),
    strategy: str | None = Query(
        None,
        description=(
            "Strategi layanan yang menentukan safety stock: aman (98%), "
            "standar (90%), hemat (80%). Ia menggerakkan titik pesan efektif, "
            "jumlah pesanan, status, dan seluruh kalimat keputusan sekaligus."
        ),
    ),
) -> dict:
    h = inti._susun(item_id, warehouse_id, days, historical_days, lang,
                    inti._model_sah(model), strategy)
    cukup = h["status"] != inti.forecasting.STATUS_INSUFFICIENT

    hasil = {
        "warehouse": h["warehouse"],
        "item": h["item"],
        "current_stock": h["current_stock"],
        # Tiga basis stok, dinyatakan terpisah supaya tidak tertukar:
        # fisik di rak, yang sudah dikomitmenkan keluar, dan yang benar-benar
        # bisa dipakai. `current_stock` tetap berarti stok fisik seperti semula.
        "reserved_stock": h["reserved_stock"],
        "available_stock": h["available_stock"],
        "forecast_days": h["forecast_days"],
        "average_daily_usage": h["average_daily_outflow"],
        "forecast_usage": h["predicted_usage"],
        # Nama yang dipakai antarmuka: stok yang diperkirakan tersisa di akhir
        # periode, yaitu current_stock dikurangi forecast_usage.
        "expected_stock": h["predicted_remaining_stock"],
        # Berapa unit yang KURANG bila forecast_usage melampaui stok TERSEDIA.
        # `expected_stock` berhenti di nol, jadi besaran defisitnya hanya
        # terbaca di sini. Nol berarti mencukupi; null berarti histori belum
        # cukup untuk menghitungnya.
        #
        # Basisnya available_stock, sedangkan expected_stock berbasis stok
        # fisik. Tanpa stok tercadang keduanya sama dan angkanya identik
        # dengan sebelum perubahan ini.
        "projected_shortage": h["projected_shortage"],
        "reorder_point": h["reorder_point"],
        "minimum_stock": h["minimum_stock"],
        # Jadwal penggantian dari umur pakai komponen. Berdiri sendiri, tidak
        # menggerakkan satu pun angka di atas -- dan justru paling berguna
        # ketika seluruh angka di atas kosong, yaitu pada komponen yang diganti
        # sekali dalam beberapa tahun dan karena itu tidak akan pernah punya
        # cukup riwayat untuk diramal. null bila umur pakainya belum dicatat.
        "service_life": h["umur_pakai"],

        # --- versi tampilan lapisan prakiraan ---
        # Pembulatan dilakukan DI SINI, pada lapisan penyajian, bukan pada
        # mesin prakiraan: `hitung()` tetap bekerja dan melaporkan dengan
        # presisi penuh di field non-`_int` di atas, dan seluruh keputusan di
        # bawah tetap memakai angka penuh itu. Yang berubah hanya apa yang
        # dibaca mata. Satuan gudang diskrit dan prakiraan tidak pernah
        # seteliti dua angka di belakang koma.
        # current_stock_int / available_stock_int / minimum_stock_int /
        # reorder_point_int datang dari lapisan keputusan di bawah; hanya yang
        # belum punya versi bulat yang ditambahkan di sini.
        "reserved_stock_int": decision.bulat(h["reserved_stock"]),
        "forecast_usage_int": decision.bulat(h["predicted_usage"]),
        "expected_stock_int": decision.bulat(h["predicted_remaining_stock"]),
        "projected_shortage_int": decision.bulat(h["projected_shortage"]),

        "status": h["status"],
        "message": h["message"],
        # Terbatas horizon: null berarti "tidak tercapai dalam periode
        # prakiraan", BUKAN "tidak akan pernah tercapai". Untuk keputusan
        # pakai days_to_rop pada lapisan keputusan di bawah.
        "days_until_reorder_point": h["days_until_reorder_point"],
        "reorder_point_within_horizon": h["reorder_point_within_horizon"],
        "reorder_crossing_date": h["reorder_crossing_date"],
        "days_until_stockout": h["days_until_stockout"],
        "historical": h["historical_data"],
        "forecast": h["forecast_data"],
        # Pemakaian per hari dalam bilangan bulat. Jumlah kolom pemakaiannya
        # tepat sama dengan forecast_usage_int, dan baris terakhirnya memuat
        # sisa stok serta kekurangan pada akhir periode -- layar membaca
        # ketiganya dari sini supaya "stok - kebutuhan = kurang" selalu genap
        # di mata pembacanya, tanpa selisih satu akibat tiga pembulatan
        # terpisah.
        "daily_plan": h.get("daily_plan", []),
        "data_quality": h["data_quality"],
        "requirements": h["requirements"],
        "method": h["method"],
        # Model yang diminta, yang benar-benar meramal, namanya di layar, dan
        # papan skor perlombaannya bila mode "terbaik" yang dipilih.
        "model": h["model"],
        "model_used": h["model_used"],
        "model_label": h["model_label"],
        "model_scoreboard": h["model_scoreboard"],
        # Keterangan strategi. `strategy_applied` false berarti safety stock
        # pada jawaban ini masih dari master barang -- entah karena tidak ada
        # strategi yang diminta, entah karena galat model belum dapat diukur.
        # Layar memakainya untuk memilih label kartu: menyebut "strategi Aman"
        # di atas angka yang sebenarnya datang dari master adalah kekeliruan
        # yang tidak akan pernah disadari siapa pun.
        "strategy": h["strategy"],
        "strategy_z": h["strategy_z"],
        "strategy_service_level": h["strategy_service_level"],
        "strategy_rmse": h["strategy_rmse"],
        # Dasar `strategy_rmse`: "demand_stdev" berarti simpangan baku
        # permintaan harian (jalur statistik), "model_rmse" berarti galat
        # backtest model. Satuannya sama, artinya tidak -- dan kartu yang
        # menyebut dasar yang keliru adalah keterangan yang tidak akan pernah
        # disadari siapa pun. null berarti rantai strategi tidak berjalan.
        "safety_stock_basis": h["safety_stock_basis"],
        "strategy_applied": h["strategy_applied"],
        # Laju harian versi rata-rata bergerak berbobot selalu ikut dikirim
        # sebagai pembanding, walau yang memproyeksikan stok adalah model.
        # Bernilai null saat histori belum cukup.
        "baseline_daily_usage": h.get("baseline_daily_outflow"),
        "as_of": h["as_of"],
        "historical_period": h["historical_period"],

        # --- lapisan keputusan ---
        # Field lama di atas TIDAK diubah; ini tambahan. Halaman lain yang
        # sudah membaca bentuk lama tetap berjalan tanpa disentuh.
        "action_status": h["action_status"],
        "action_status_label": h["action_status_label"],
        "action_text": h["action_text"],
        "days_to_rop": h["days_to_rop"],
        "days_to_rop_bucket": h["days_to_rop_bucket"],
        "reorder_point_reached": h["reorder_point_reached"],
        "usage_frequency_label": h["usage_frequency_label"],
        "usage_frequency_detail": h["usage_frequency_detail"],
        "usage_frequency": h["usage_frequency"],
        # ALIAS WARISAN, dan komentar di tempat ini dulu KELIRU: ia berbunyi
        # "pengisian sampai batas stok maksimum gudang", yaitu rumus
        # `maximum_stock - current_stock` yang sudah dihapus. Sejak itu field
        # ini membawa angka yang sama persis dengan recommended_order_qty --
        # satu jawaban, bukan dua yang berselisih -- dengan None dipetakan ke 0
        # supaya tipenya tetap bilangan bagi pembaca lama. Yang perlu
        # membedakan "nol" dari "belum dapat dihitung" membaca
        # recommended_order_qty. Lihat catatan pada decision.lapisan_keputusan.
        "suggested_order_qty": h["suggested_order_qty"],

        # --- lapisan reorder ---
        # Patokannya lead time dan stok tersedia, bukan horizon prakiraan.
        # Tidak satu pun field ini bergerak saat `days` diubah.
        "lead_time_demand": h["lead_time_demand"],
        "effective_reorder_point": h["effective_reorder_point"],
        "days_to_effective_rop": h["days_to_effective_rop"],
        # Ketahanan stok sampai habis, TIDAK dibatasi horizon prakiraan --
        # bandingkan days_until_stockout di atas, yang berhenti di ujung
        # periode dan berbunyi null bila stok bertahan lebih lama dari itu.
        "days_of_cover": h["days_of_cover"],
        "order_up_to_level": h["order_up_to_level"],
        "reorder_point_adequate": h["reorder_point_adequate"],
        # null berarti belum dapat dihitung; 0 berarti tidak perlu membeli.
        "recommended_order_qty": h["recommended_order_qty"],
        "effective_reorder_point_reached": h["effective_reorder_point_reached"],
        "safety_stock": h["safety_stock_value"],

        # --- versi tampilan lapisan reorder + kalimat siap render ---
        # Halaman Reorder merender field ini apa adanya. Tidak ada rumus dan
        # tidak ada pembulatan yang hidup di frontend, sehingga status dan
        # angka yang menyertainya mustahil berasal dari dua perhitungan
        # berbeda.
        "available_stock_int": h["available_stock_int"],
        "lead_time_demand_int": h["lead_time_demand_int"],
        "effective_reorder_point_int": h["effective_reorder_point_int"],
        "days_to_effective_rop_int": h["days_to_effective_rop_int"],
        "days_of_cover_int": h["days_of_cover_int"],
        "days_to_effective_rop_label": h["days_to_effective_rop_label"],
        "order_up_to_level_int": h["order_up_to_level_int"],
        "safety_stock_int": h["safety_stock_int"],
        "lead_time_days_int": h["lead_time_days_int"],
        "reorder_status_reason": h["reorder_status_reason"],
        "effective_reorder_point_basis": h["effective_reorder_point_basis"],
        "order_qty_title": h["order_qty_title"],
        "order_qty_reason": h["order_qty_reason"],
        # Sumbu prioritas, terpisah dari status: status menjawab APA yang harus
        # dilakukan, prioritas menjawab MANA DULU. Dipakai kolom dan saringan
        # pada daftar Pemesanan Ulang.
        "priority": h["priority"],
        "priority_label": h["priority_label"],
        # Horizon tetap yang menjadi dasar jumlah pesanan, beserta kebutuhan
        # sepanjang horizon itu. Diterbitkan supaya panel detail dapat
        # menunjukkan asal jumlahnya tanpa menghitung ulang di layar -- dan
        # supaya terlihat bahwa angka ini TIDAK mengikuti `days` yang diminta.
        "decision_horizon_days": h["decision_horizon_days"],
        "decision_horizon_usage": h["decision_horizon_usage"],
        "decision_horizon_usage_int": h["decision_horizon_usage_int"],
        # Waktu tunggu kiriman dari master barang, untuk ditampilkan pada
        # blok kondisi persediaan. null berarti belum diisi.
        "lead_time_days": h["lead_time_days"],
        "is_lumpy": h["is_lumpy"],
        "stock_below_minimum": h["stock_below_minimum"],
        "current_stock_int": h["current_stock_int"],
        "minimum_stock_int": h["minimum_stock_int"],
        "reorder_point_int": h["reorder_point_int"],
        "advice_text": h["advice_text"],
        "remaining_pickups": h["remaining_pickups"],
        "quality_level": h["quality_level"],
        "quality_reason": h["quality_reason"],
        "low_confidence_estimate": h["low_confidence_estimate"],
        "low_confidence_reason": h["low_confidence_reason"],
        # Mutu histori sebagai keterangan tingkat HALAMAN, bukan lencana satu
        # kartu: seluruh angka lapisan reorder mewarisi keterbatasan yang sama.
        "confidence_level": h["confidence_level"],
        "confidence_label": h["confidence_label"],
        "confidence_note": h["confidence_note"],
        "confidence_note_forecast": h["confidence_note_forecast"],
        "calculation_detail": h["calculation_detail"],
        # Bahasa yang benar-benar dipakai menyusun kalimat di atas; berguna
        # bagi klien untuk memastikan permintaannya memang dipenuhi.
        "lang": h["lang"],
    }

    if include_recommendation:
        hasil["recommendation"] = inti._rekomendasi(h, h["lang"])
    else:
        hasil["recommendation"] = None

    hasil["has_forecast"] = cukup

    # Cerita halaman, disusun SETELAH seluruh angka jadi -- lihat
    # decision.kalimat_cerita. Ia membaca `hasil` yang sudah utuh, jadi angka
    # di dalam kalimatnya dijamin angka yang sama dengan yang tercetak di
    # kartu, bukan hasil pembacaan kedua atas sumber yang bisa bergeser.
    hasil["narasi"] = decision.kalimat_cerita(hasil, h["lang"])

    return hasil


@router.post("/api/forecast/recommendation")
@limiter.limit(BATAS_BERAT)
def recommendation(
    request: Request,
    warehouse_id: int = Query(..., gt=0),
    item_id: int = Query(..., gt=0),
    days: int = Query(7, ge=1, le=inti.FORECAST_DAYS_MAX),
    historical_days: int = Query(
        inti.HISTORICAL_DAYS_DEFAULT, ge=7, le=inti.HISTORICAL_DAYS_MAX
    ),
    lang: str = Query(i18n.BAHASA_BAWAAN,
                      description="Bahasa rekomendasi: id atau en."),
) -> dict:
    """
    Rekomendasi saja.

    Dipakai antarmuka setelah kartu dan grafik tampil, supaya halaman tidak
    menunggu layanan AI. Angkanya dihitung ulang di sini, bukan diterima dari
    klien, sehingga model tidak mungkin disuguhi angka karangan.
    """
    h = inti._susun(item_id, warehouse_id, days, historical_days, lang)
    return {"recommendation": inti._rekomendasi(h, h["lang"]),
            "status": h["status"]}
