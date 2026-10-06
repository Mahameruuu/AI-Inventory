# -*- coding: utf-8 -*-
"""
Prakiraan kebutuhan stok.

Dua endpoint yang sengaja dipisah:

    GET  /api/forecasting           -> angka, tanpa menyentuh LLM sama sekali
    POST /api/forecasting/analysis  -> kalimat penjelas dari LLM

Pemisahan itu penting: grafik harus tetap muncul cepat walau layanan AI sedang
lambat atau mati. LLM juga tidak pernah menerima angka dari klien -- ia
menghitung ulang lewat mesin yang sama, sehingga mustahil disuguhi angka
karangan lalu diminta membenarkannya.
"""

import logging
from datetime import date, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from .. import decision, forecasting, i18n, llm, statistik
from ..config import APP_TZ
from ..db import readonly
from ..errors import invalid, not_found
from .. import rop
from ..ml import klasik, predict

log = logging.getLogger("inventory.forecasting")

router = APIRouter(prefix="/api/forecasting", tags=["forecasting"])

HISTORICAL_DAYS_DEFAULT = 90
HISTORICAL_DAYS_MAX = 365

# Sejauh mana jendela boleh memanjang sendiri ketika 90 hari tidak memuat
# cukup hari pengeluaran. Dua puluh tahun: sepanjang riwayat terpanjang yang
# ada di basis data ini, dan sepanjang umur pakai komponen paling awet yang
# dicatatnya. Lihat catatan pada _susun.
LOOKBACK_MAKS_HARI = 365 * 20

# Berapa banyak titik yang dikirim ke grafik. Jendela yang memanjang sampai
# beberapa tahun tetap dihitung utuh, tetapi mengirim tujuh ribu titik ke
# browser hanya menghasilkan garis yang tidak terbaca sekaligus muatan
# beberapa megabita. Angkanya dipilih supaya satu tahun terakhir selalu utuh.
MAKS_TITIK_GRAFIK = 365
FORECAST_DAYS_MAX = 90


# Sampai berapa lama jeda sesudah pergerakan terakhir masih dianggap
# keterlambatan pencatatan, bukan berhentinya pemakaian. Lihat tanggal_acuan.
TOLERANSI_JEDA_HARI = 14


def tanggal_acuan(pergerakan_terakhir: date | None, hari_ini: date) -> date:
    """
    Tanggal akhir jendela histori.

    JEDA PENDEK MENGIKUTI DATA. Sebelumnya dipakai
    `max(pergerakan_terakhir, hari_ini)`, yang membuat hari-hari setelah
    transaksi terakhir ikut masuk jendela sebagai nol. Untuk jeda pendek itu
    keliru: hari tanpa DATA bukan hari tanpa PEMAKAIAN, dan kekeliruannya tidak
    netral -- rata-rata bergerak berbobot memberi bobot terbesar pada hari
    terbaru, sehingga jeda empat hari saja menurunkan laju sekitar 8,6% dan
    jeda sebulan hampir separuh. Arah biasnya selalu meremehkan kebutuhan.

    JEDA PANJANG MENGIKUTI JAM SERVER, dan ini tambahan 1 September 2026.
    Alasan di atas berlaku untuk barang yang dipakai hampir tiap hari, tempat
    jeda beberapa hari memang hampir selalu berarti pencatatan yang tertinggal.
    Ia runtuh pada komponen yang diganti tiap beberapa tahun: pompa yang
    terakhir diganti Januari 2012 lalu berjalan mulus empat belas tahun
    membuat jendelanya berakhir di 2012 dan seluruh tahun kosong sesudahnya --
    yang justru merupakan buktinya bertahan -- hilang dari hitungan. Lajunya
    terbaca 0,091 unit/hari alih-alih 0,00014, enam ratus kali lipat, dan
    halaman Pemesanan Ulang menyatakan pompa itu butuh stok empat kali lebih
    banyak daripada filter yang diganti tiap sebelas minggu.

    Barang yang belum pernah bergerak tetap memakai hari ini: jendelanya kosong
    dan mesin akan menyatakan datanya belum cukup.
    """
    if pergerakan_terakhir is None:
        return hari_ini
    if (hari_ini - pergerakan_terakhir).days <= TOLERANSI_JEDA_HARI:
        return pergerakan_terakhir
    return hari_ini


def _jadwal_penggantian(nilai, satuan, terakhir: date | None, hari_ini: date):
    """
    Jadwal penggantian dari umur pakai komponen -- bukan dari prakiraan.

    UNTUK SIAPA INI ADA. Komponen yang diganti sekali dalam dua puluh tahun
    tidak akan pernah punya cukup riwayat untuk diramal: satu penggantian tidak
    membentuk satu pun selang, dan tidak ada model yang dapat menyimpulkan
    selang dari satu titik. Halaman yang hanya menjawab "data belum cukup"
    untuk barang seperti itu menyembunyikan hal yang justru diketahui dengan
    pasti -- kapan ia dipasang, dan berapa lama ia dirancang bertahan.

    TANGGAL JATUH TEMPO HANYA UNTUK SATUAN TAHUN, dan itu bukan kelalaian.
    Mengubah "12.500 jam" menjadi tanggal menuntut satu angka yang tidak
    dimiliki basis data ini: berapa jam mesin benar-benar beroperasi sehari.
    Dengan satu shift angkanya lebih dari empat kali lipat berbeda dari operasi
    terus-menerus, dan migrasi 029 sengaja menolak menanam asumsi sebesar itu
    diam-diam. Umur pakainya tetap diterbitkan apa adanya; yang tidak
    diterbitkan hanya kesimpulan yang belum boleh ditarik.
    """
    if nilai is None or satuan is None:
        return None
    jadwal = {
        "value": float(nilai),
        "unit": satuan,
        "last_replacement": terakhir.isoformat() if terakhir else None,
        "due_date": None,
        "days_remaining": None,
    }
    if satuan == "tahun" and terakhir is not None:
        jatuh = terakhir + timedelta(days=round(float(nilai) * 365))
        jadwal["due_date"] = jatuh.isoformat()
        jadwal["days_remaining"] = (jatuh - hari_ini).days
    return jadwal


def ml_untuk(item_id: int, warehouse_id: int):
    """
    Pembungkus model pembelajaran mesin dengan tanda tangan model klasik.

    Dipakai lapisan lain -- perhitungan ROP di app/rop.py -- yang perlu
    mengadu atau menjalankan model ML tanpa membawa serta seluruh isi _susun.
    Mengembalikan None bila model tidak termuat, sehingga pemanggilnya dapat
    memutuskan sendiri: melewatinya, bukan diam-diam menggantinya dengan model
    lain lalu melaporkan nama yang keliru.
    """
    if not predict.tersedia():
        return None

    with readonly() as cur:
        cur.execute(
            """
            SELECT it.id, it.category_id, it.unit_price, it.lead_time_days,
                   it.reorder_point, it.safety_stock,
                   COALESCE(inv.quantity, 0) AS stok
              FROM items it
              LEFT JOIN inventory inv
                     ON inv.item_id = it.id AND inv.warehouse_id = %s
             WHERE it.id = %s
            """,
            (warehouse_id, item_id),
        )
        b = cur.fetchone()
    if b is None:
        return None

    def _ml(deret, hari, acuan):
        return predict.ramal_deret(
            riwayat=list(deret), as_of=acuan, hari=hari,
            current_stock=float(b["stok"] or 0), neto_hari_terakhir=0.0,
            lead_time_days=b["lead_time_days"], reorder_point=b["reorder_point"],
            safety_stock=b["safety_stock"], unit_price=b["unit_price"],
            item_id=b["id"], warehouse_id=warehouse_id,
            category_id=b["category_id"] or 0,
        )

    return _ml


# Horizon tetap untuk seluruh perhitungan yang menjadi DASAR KEPUTUSAN --
# galat model, laju harian, dan sejak 2 September 2026 juga sasaran pengisian
# yang menentukan jumlah pesanan. Karena pemakainya tidak lagi hanya router
# ini, angkanya kini tinggal di app/decision.py dan diimpor dari sana; nama
# lamanya dipertahankan supaya pembaca modul ini tidak perlu tahu ia pindah.
HORIZON_KEPUTUSAN = decision.HORIZON_KEPUTUSAN


def _model_sah(model: str) -> str:
    """
    Kunci model yang tidak dikenal DIKEMBALIKAN ke "terbaik", bukan ditolak
    dengan galat.

    Yang mengirim kunci asing hampir selalu tautan lama atau layar versi
    sebelumnya, dan menjatuhkan seluruh halaman karena satu parameter tampilan
    adalah hukuman yang tidak sebanding. Yang dipilihnya pun tetap terlihat
    jujur: `model_used` pada jawabannya menyebut siapa yang benar-benar meramal.

    Jatuhnya ke statistik sederhana, sama seperti bawaan seluruh endpoint:
    tautan lama tidak boleh diam-diam menyalakan adu enam model.
    """
    return model if model in klasik.semua_kunci() else klasik.KUNCI_STATISTIK


def _masukan_periode(hasil: dict, forecast_days: int, aktif: bool) -> dict:
    """
    Masukan mode periode untuk lapisan keputusan, dari hasil prakiraan.

    Kekurangan dan sisanya dibaca dari BARIS TERAKHIR `daily_plan` -- sumber
    yang sama persis dengan kartu "perlu ditambah" / "sisa stok" di halaman
    Prakiraan. Mengurangkan ulang kebutuhan dari stok di sini akan cocok
    hampir selalu, lalu meleset satu unit pada pembulatan tertentu, dan satu
    unit itulah yang akan ditanyakan orang.
    """
    if not aktif:
        return {}
    rencana = hasil.get("daily_plan") or []
    akhir = rencana[-1] if rencana else None
    return {
        "periode_keputusan": forecast_days,
        "kebutuhan_periode": hasil.get("predicted_usage"),
        "kekurangan_periode": akhir["shortage_int"] if akhir else None,
        "sisa_periode": akhir["stock_int"] if akhir else None,
    }


def _susun(item_id: int, warehouse_id: int, forecast_days: int,
           historical_days: int, lang: str = i18n.BAHASA_BAWAAN,
           model: str = klasik.KUNCI_STATISTIK,
           strategi: str | None = None,
           keputusan_periode: bool = False) -> dict:
    """
    Mengambil data mentah lalu menyerahkannya ke mesin prakiraan.

    `model` memilih SIAPA yang meramal, bukan bagaimana stok diproyeksikan.
    Apa pun pilihannya, keluarannya berbentuk sama: satu deret permintaan
    harian yang diserahkan ke app/forecasting.py. Karena itu mengganti model
    tidak pernah mengubah arti satu pun angka di layar -- hanya nilainya.

    Bawaannya "statistik" -- rata-rata riwayat, dengan safety stock dari
    simpangan baku permintaan harian. Titik pesan tidak menuntut model
    prakiraan untuk berarti; ia menuntut laju pemakaian dan ketidakpastiannya,
    dan keduanya terbaca dari riwayat dengan aritmetika yang dapat diperiksa
    orang gudang. Model klasik dan pembelajaran mesin tetap dapat dipilih di
    layar untuk barang yang polanya memang kuat.

    Satu bawaan untuk seluruh pemanggil, dan itu disengaja: halaman, asisten,
    dan panel keputusan harus menyebut angka yang sama untuk barang yang sama.
    Bila salah satunya diam-diam memakai model lain, satu layar akan memuat dua
    jawaban untuk pertanyaan yang sama.

    `keputusan_periode` menyalakan MODE PERIODE lapisan keputusan: status dan
    jumlah pesanan mengikuti `forecast_days`, memakai kebutuhan dan kekurangan
    yang sama dengan yang dicetak halaman Prakiraan. Hanya daftar Pemesanan
    Ulang (dan dasbor, yang meringkasnya) yang memintanya; lihat
    decision.status_keputusan_periode.
    """
    with readonly() as cur:
        cur.execute(
            """
            SELECT it.id, it.sku, it.name, it.minimum_stock, it.reorder_point,
                   it.maximum_stock, it.is_active, u.code AS unit_code,
                   -- empat kolom terakhir hanya dipakai model prakiraan
                   it.category_id, it.unit_price, it.lead_time_days,
                   it.safety_stock,
                   -- umur pakai: tidak menggerakkan satu pun angka prakiraan,
                   -- hanya diterbitkan supaya layar dapat menyebut jadwal
                   -- penggantian barang yang riwayatnya tidak akan pernah
                   -- cukup untuk diramal
                   it.service_life_value, it.service_life_unit,
                   it.usage_type
            FROM items it JOIN units u ON u.id = it.unit_id
            WHERE it.id = %s
            """,
            (item_id,),
        )
        barang = cur.fetchone()
        if barang is None:
            raise not_found("item", item_id, "item_id")

        cur.execute(
            "SELECT id, code, name, is_active FROM warehouses WHERE id = %s",
            (warehouse_id,),
        )
        gudang = cur.fetchone()
        if gudang is None:
            raise not_found("warehouse", warehouse_id, "warehouse_id")

        cur.execute(
            """
            SELECT quantity, reserved_quantity, available_quantity
            FROM inventory WHERE item_id = %s AND warehouse_id = %s
            """,
            (item_id, warehouse_id),
        )
        stok = cur.fetchone()
        # Barang yang belum pernah masuk gudang ini tetap dilayani: stoknya nol,
        # dan mesin akan menyatakan datanya belum cukup.
        current_stock = stok["quantity"] if stok else 0
        # Stok tercadang dipisah sejak di sini supaya mesin prakiraan menerima
        # kedua basis sekaligus: yang fisik untuk grafik, yang tersedia untuk
        # menakar kekurangan.
        reserved_stock = stok["reserved_quantity"] if stok else 0
        available_stock = stok["available_quantity"] if stok else 0

        # Tanggal acuan mengikuti data, bukan jam server: bila sistem baru
        # dipakai lagi setelah lama menganggur, jendela histori tetap masuk akal.
        cur.execute(
            """
            SELECT max(movement_date)::date AS terakhir
            FROM stock_movements WHERE item_id = %s AND warehouse_id = %s
            """,
            (item_id, warehouse_id),
        )
        baris = cur.fetchone()
        hari_ini = date.today() if APP_TZ is None else date.today()
        as_of = tanggal_acuan(baris["terakhir"] if baris else None, hari_ini)
        mulai = as_of - timedelta(days=historical_days - 1)

        # JENDELA MEMANJANG SAMPAI CUKUP, TIDAK LEBIH.
        #
        # Sembilan puluh hari adalah jendela yang tepat untuk barang yang
        # keluar hampir tiap hari, dan tetap dipakai apa adanya untuk mereka --
        # perintah di bawah tidak mengubah apa pun bila hari pengeluaran
        # ketiga sudah berada di dalamnya.
        #
        # Ia salah untuk komponen yang diganti tiap sebelas minggu sampai
        # beberapa tahun. Barangnya punya riwayat dua puluh tahun berisi puluhan
        # penggantian, tetapi sembilan puluh hari terakhir memuat satu kejadian
        # atau nol, dan syarat "minimal tiga hari ada pengeluaran" menolaknya
        # sebagai data yang belum cukup. Yang kurang bukan datanya melainkan
        # panjang jendela yang menengoknya.
        #
        # Yang dicari: hari pengeluaran ke-(N+1) terbaru, dengan N ambang minimum
        # itu sendiri, lalu jendela dimulai SEHARI SESUDAHNYA.
        #
        # SATU HARI ITU BUKAN KOSMETIK. Jendela yang dimulai TEPAT pada sebuah
        # penggantian memuat N penggantian tetapi hanya membentang N-1 selang di
        # antaranya, sehingga lajunya terbaca N/(N-1) kali terlalu tinggi -- pada
        # N=3 itu 50%, dan seluruh titik pesan barang berputaran lambat ikut
        # melar sebesar itu. Terukur pada data produksi: Filter Oli yang diganti
        # tiap 78 hari terbaca 0,019 unit/hari, bukan 0,0128.
        #
        # Dengan mengambil satu kejadian lebih jauh lalu memulai sehari
        # sesudahnya, jendelanya memuat N penggantian yang membentang N selang
        # penuh, dan lajunya kembali 1/selang.
        cur.execute(
            """
            SELECT movement_date::date AS hari
              FROM stock_movements
             WHERE item_id = %s AND warehouse_id = %s
               AND quantity < 0 AND movement_date::date <= %s
             GROUP BY 1 ORDER BY 1 DESC LIMIT %s
            """,
            (item_id, warehouse_id, as_of, forecasting.MIN_OUTFLOW_DAYS + 1),
        )
        hari_keluar_terbaru = [r["hari"] for r in cur.fetchall()]
        # Penggantian terakhir = hari pengeluaran terbaru. Dibaca dari daftar
        # yang sudah ada di tangan, bukan dengan satu query lagi.
        penggantian_terakhir = hari_keluar_terbaru[0] if hari_keluar_terbaru else None
        if len(hari_keluar_terbaru) >= forecasting.MIN_OUTFLOW_DAYS:
            tertua = hari_keluar_terbaru[-1]
            # Barang yang seumur hidupnya baru bergerak persis N kali tidak punya
            # kejadian ke-(N+1) untuk dilewati. Jendelanya dimulai pada kejadian
            # tertua itu sendiri -- lajunya sedikit terlalu tinggi, tetapi itu
            # masih jauh lebih berguna daripada menolaknya sebagai data yang
            # belum cukup.
            batas = (tertua + timedelta(days=1)
                     if len(hari_keluar_terbaru) > forecasting.MIN_OUTFLOW_DAYS
                     else tertua)
            if batas < mulai:
                # Batas atas menjaga satu barang bergerak sekali seabad tidak
                # menarik jendela sejauh itu; di luar batas ini jawabannya memang
                # "datanya belum cukup".
                mulai = max(batas, as_of - timedelta(days=LOOKBACK_MAKS_HARI))

        # generate_series memastikan hari tanpa transaksi tetap muncul sebagai
        # nol. Tanpa itu, rata-rata pemakaian akan terlalu tinggi.
        cur.execute(
            """
            SELECT d.hari::date AS tanggal,
                   COALESCE(SUM(-m.quantity) FILTER (WHERE m.quantity < 0), 0) AS keluar,
                   COALESCE(SUM(m.quantity), 0) AS neto
            FROM generate_series(%s::date, %s::date, '1 day') AS d(hari)
            LEFT JOIN stock_movements m
                   ON m.movement_date::date = d.hari
                  AND m.item_id = %s AND m.warehouse_id = %s
            GROUP BY d.hari ORDER BY d.hari
            """,
            (mulai, as_of, item_id, warehouse_id),
        )
        harian = cur.fetchall()

    # Jendela histori dipangkas sampai hari pertama yang benar-benar ada
    # pergerakan. Hari-hari sebelum barang pernah masuk gudang bukan histori,
    # melainkan ketiadaan data, dan tidak boleh dihitung sebagai pemakaian nol.
    awal = next((i for i, r in enumerate(harian) if r["neto"] != 0 or r["keluar"] != 0), None)
    dipakai = harian[awal:] if awal is not None else []

    # --- prakiraan permintaan oleh model ---
    # Model meramal tiap hari terpisah; hasilnya diserahkan ke mesin prakiraan
    # untuk memproyeksikan stok. Bila model tidak tersedia, riwayatnya terlalu
    # pendek, atau ia gagal karena sebab apa pun, `ramalan` tetap None dan
    # mesin memakai rata-rata bergerak berbobot seperti sebelumnya.
    riwayat = [float(r["keluar"]) for r in dipakai]

    def _ml(deret, hari, acuan):
        """
        Model pembelajaran mesin dengan tanda tangan yang sama seperti model
        klasik, supaya ia dapat ikut diadu dengan aturan yang persis sama.
        Ditutup atas kolom barang di sekitarnya karena ia butuh lebih banyak
        keterangan daripada sekadar deret angka.
        """
        return predict.ramal_deret(
            riwayat=list(deret),
            as_of=acuan,
            hari=hari,
            current_stock=float(current_stock or 0),
            neto_hari_terakhir=float(dipakai[-1]["neto"] or 0) if dipakai else 0.0,
            lead_time_days=barang["lead_time_days"],
            reorder_point=barang["reorder_point"],
            safety_stock=barang["safety_stock"],
            unit_price=barang["unit_price"],
            item_id=barang["id"],
            warehouse_id=gudang["id"],
            category_id=barang["category_id"] or 0,
        )

    ramalan = None
    papan: list[dict] = []
    dipilih = model if model in klasik.KLASIK or model == klasik.KUNCI_ML else model
    metode = "weighted_moving_average"

    if riwayat:
        try:
            if model == klasik.KUNCI_TERBAIK:
                # Seluruh model diadu di atas riwayat barang ini sendiri; yang
                # menang itulah yang meramal. Papan skornya ikut terbit supaya
                # kata "terbaik" dapat diperiksa, bukan sekadar diklaim.
                tambahan = {klasik.KUNCI_ML: _ml} if predict.tersedia() else {}
                menang, papan = klasik.pilih_terbaik(
                    riwayat, forecast_days, as_of, tambahan)
                dipilih = menang or klasik.KUNCI_BAWAAN
            if dipilih == klasik.KUNCI_ML:
                ramalan = _ml(riwayat, forecast_days, as_of)
                metode = predict.metode()
            else:
                ramalan = klasik.ramal(dipilih, riwayat, forecast_days, as_of)
                metode = dipilih if ramalan else "weighted_moving_average"
        except Exception as e:  # noqa: BLE001 -- model bermasalah tidak boleh menjatuhkan halaman
            log.warning("Model prakiraan '%s' gagal untuk item %s gudang %s, "
                        "memakai rata-rata bergerak berbobot: %s",
                        model, item_id, warehouse_id, e)
            ramalan = None
            metode = "weighted_moving_average"
            dipilih = klasik.KUNCI_BAWAAN

    hasil = forecasting.hitung(
        as_of=as_of,
        current_stock=current_stock,
        daily_outflow=[(r["tanggal"], r["keluar"]) for r in dipakai],
        daily_net=[(r["tanggal"], r["neto"]) for r in dipakai],
        minimum_stock=barang["minimum_stock"],
        reorder_point=barang["reorder_point"],
        forecast_days=forecast_days,
        historical_days=historical_days,
        ramalan_harian=ramalan,
        metode=metode,
        available_stock=available_stock,
        lang=lang,
        maks_titik_grafik=MAKS_TITIK_GRAFIK,
    )
    # --- lapisan keputusan ---
    # Ditempel di sini, bukan di dalam hitung(), karena rumusnya butuh kolom
    # master barang (lead time, stok maksimum, satuan) yang sengaja tidak
    # diketahui mesin prakiraan -- mesin itu murni bekerja atas deret angka.
    # --- safety stock menurut strategi layanan ---
    # Z x sebaran x akar(masa tunggu); rumusnya sendiri di app/statistik.py,
    # dipanggil bukan disalin. Sebarannya diambil dari
    # papan adu yang sama dengan yang dipakai mode "terbaik", jadi tidak ada
    # pengukuran kedua yang bisa berbeda hasilnya.
    # OPT-IN, bukan bawaan. Tanpa strategi yang diminta, safety stock tetap
    # yang tercatat pada master barang -- perilaku yang sudah lama berlaku dan
    # dikunci belasan tes kasus tepi. Menjadikannya bawaan global berarti
    # setiap pemanggil lama, termasuk asisten, diam-diam berpindah dasar; dan
    # pada barang yang pemakaiannya sangat teratur galat modelnya nyaris nol,
    # sehingga cadangannya ikut menghilang tanpa ada yang memintanya.
    # Dicocokkan ke kunci yang BENAR-BENAR dikenali, bukan sekadar "ada
    # isinya". Fungsi router di aplikasi ini kerap dipanggil langsung sebagai
    # fungsi Python, dan pada pemanggilan seperti itu nilai bawaan Query milik
    # FastAPI ikut masuk apa adanya -- objek yang bernilai truthy meski tidak
    # ada strategi yang diminta siapa pun. Memakai `if strategi` di sini akan
    # menyalakan rantai untuk pemanggil yang tidak pernah memintanya.
    s_strategi = rop.STRATEGI.get(str(strategi or "").strip().lower())
    safety_strategi = None
    rmse_model = None
    dasar_sebaran = None
    laju_keputusan = None
    if s_strategi and riwayat and barang["lead_time_days"]:
        if dipilih == klasik.KUNCI_STATISTIK:
            # JALUR STATISTIK: tidak ada model yang diadu sama sekali.
            # Sebarannya simpangan baku permintaan harian -- besaran yang
            # justru lebih tepat untuk pertanyaannya, karena yang harus
            # ditanggung cadangan adalah simpangan PERMINTAAN, bukan meleset
            # MODEL. Ia juga hidup di riwayat pendek, tempat backtest menyerah
            # dan cadangan terpaksa jatuh ke angka master. Rumusnya sendiri
            # tinggal di app/statistik.py; lihat catatan konvensi di sana.
            dasar_sebaran = "demand_stdev"
            rmse_model = statistik.simpangan_harian(riwayat)
        else:
            dasar_sebaran = "model_rmse"
            tambahan = {klasik.KUNCI_ML: _ml} if predict.tersedia() else None
            # Horizon backtestnya DIPATOK, bukan mengikuti periode tampilan.
            # Galat yang diukur pada horizon berbeda menghasilkan RMSE berbeda,
            # dan lewat safety stock ia akan menggeser jumlah pesanan setiap kali
            # pengguna mengganti periode di layar -- kebocoran yang sama seperti
            # pada laju keputusan di bawah, hanya lebih halus.
            for baris in klasik.evaluasi(riwayat, HORIZON_KEPUTUSAN, as_of, tambahan):
                if baris["model"] == dipilih:
                    rmse_model = baris["rmse"]
                    break

        # Satu rumus untuk kedua jalur. Menuliskannya dua kali berarti suatu
        # hari nanti hanya satu di antaranya yang ikut diperbaiki.
        safety_strategi = statistik.safety_stock(
            simpangan=rmse_model, z=s_strategi.z,
            lead_time_days=float(barang["lead_time_days"]))

        # --- laju keputusan, DILEPAS dari horizon tampilan ---
        #
        # average_daily_outflow dirata-ratakan sepanjang forecast_days, yaitu
        # periode yang dipilih pengguna di layar. Memakainya sebagai dasar
        # keputusan berarti menggeser periode tampilan ikut menggeser jumlah
        # pesanan -- pada satu barang uji, 7 hari menghasilkan 2.079 dan 90
        # hari menghasilkan 1.738 untuk stok dan strategi yang sama persis.
        # Setelan tampilan tidak boleh mengubah keputusan pembelian.
        #
        # Yang dipakai di sini rata-rata ramalan sepanjang MASA TUNGGU, karena
        # itulah jendela yang benar-benar ditanggung keputusan reorder: berapa
        # yang akan terpakai selama menunggu kiriman datang.
        hari_lead = max(1, min(int(float(barang["lead_time_days"])), 90))
        deret_lead = (_ml(riwayat, hari_lead, as_of)
                      if dipilih == klasik.KUNCI_ML and predict.tersedia()
                      else klasik.ramal(dipilih, riwayat, hari_lead, as_of))
        if deret_lead:
            laju_keputusan = sum(deret_lead) / len(deret_lead)

    hasil.update(decision.lapisan_keputusan(
        current_stock=hasil["current_stock"],
        # Keputusan reorder berpatokan stok TERSEDIA; field lama tetap
        # berpatokan stok fisik.
        available_stock=hasil["available_stock"],
        reorder_point=hasil["reorder_point"],
        minimum_stock=hasil["minimum_stock"],
        # SAFETY STOCK DARI RANTAI STRATEGI, bukan dari master barang.
        #
        # Ini satu-satunya tempat pergantian itu perlu terjadi. Titik pesan
        # efektif, jumlah pesanan, status, seluruh kalimat keputusan, dan
        # narasi halaman semuanya turun dari angka ini -- menggantinya di sini
        # membuat satu halaman berbicara dengan satu suara, sedangkan menambal
        # tiap panel satu per satu akan membuat judul, tombol, dan kalimatnya
        # menyebut angka yang berbeda-beda.
        #
        # Angka master tetap dipakai sebagai cadangan ketika galat model belum
        # dapat diukur -- histori terlalu pendek untuk diadu. Cadangan yang
        # tidak diketahui lebih buruk daripada cadangan yang ditetapkan tangan.
        safety_stock=(safety_strategi if safety_strategi is not None
                      else barang["safety_stock"]),
        # Histori belum cukup berarti laju belum terhitung; jumlah pesanan
        # harus berbunyi "belum dapat dihitung", bukan "tidak perlu membeli".
        has_forecast=hasil["status"] != forecasting.STATUS_INSUFFICIENT,
        avg_daily_usage=(laju_keputusan if laju_keputusan is not None
                         else hasil["average_daily_outflow"]),
        keluar_harian=[r["keluar"] for r in dipakai],
        lead_time_days=barang["lead_time_days"],
        # maximum_stock TIDAK LAGI DIKIRIM: satu-satunya pemakainya adalah
        # saran_qty(), yang rumusnya `maximum_stock - current_stock` dan sudah
        # dihapus. Kolomnya tetap ada pada master barang dan tetap dilayani
        # endpoint katalog; yang berhenti adalah perannya dalam keputusan
        # pengadaan.
        forecast_days=forecast_days,
        unit_code=barang["unit_code"] or "",
        hari_histori=hasil["historical_period"]["days"],
        hari_aktif=hasil["requirements"]["actual_days_with_outflow"],
        expected_usage=hasil["predicted_usage"],
        expected_stock=hasil["predicted_remaining_stock"],
        days_until_rop=hasil["days_until_reorder_point"],
        days_until_stockout=hasil["days_until_stockout"],
        history_start=hasil["historical_period"]["start"],
        history_end=hasil["historical_period"]["end"],
        as_of=as_of.isoformat(),
        **_masukan_periode(hasil, forecast_days, keputusan_periode),
        lang=lang,
    ))

    # Mutu data pada field lama diselaraskan dengan aturan ambang yang baru.
    # Dibiarkan berbeda berarti grafik dan panel detail menampilkan dua
    # penilaian mutu yang berlainan pada layar yang sama.
    # Tingkat mutu disimpan sebagai kata kunci tetap ("rendah"/"sedang"/
    # "tinggi") supaya dapat dibandingkan; yang dikirim ke layar adalah
    # terjemahannya, karena field inilah yang benar-benar dicetak.
    hasil["data_quality"]["label"] = i18n.t(
        f"quality.{hasil['quality_level']}", lang
    )
    hasil["data_quality"]["reason"] = hasil["quality_reason"]
    # Bahasa yang dipakai menyusun seluruh kalimat pada jawaban ini.
    hasil["lang"] = i18n.normalisasi(lang)

    # Ketiganya dikirim berdampingan supaya pembaca hasil tidak perlu menebak
    # basis mana yang dipakai angka mana.
    hasil["reserved_stock"] = float(reserved_stock or 0)
    # Cadangan penyangga dari master barang, diteruskan apa adanya supaya
    # pembaca dapat memeriksa sendiri asal titik pesan efektif.
    hasil["safety_stock_value"] = float(barang["safety_stock"] or 0)
    # Waktu tunggu kiriman, juga apa adanya dari master barang. Diteruskan
    # untuk DITAMPILKAN saja -- seluruh rumus yang memakainya sudah menerima
    # nilai yang sama lewat argumen di atas, jadi tidak ada perhitungan yang
    # berubah karenanya. None berarti master barang belum mengisinya, dan itu
    # berbeda dari nol.
    hasil["lead_time_days"] = (
        float(barang["lead_time_days"]) if barang["lead_time_days"] is not None else None
    )
    hasil["item"] = {
        "id": barang["id"], "sku": barang["sku"], "name": barang["name"],
        "unit_code": barang["unit_code"], "is_active": barang["is_active"],
        # berumur_pakai / habis_pakai (migrasi 034): layar memakainya untuk
        # menyebut apakah barang ini dijadwalkan atau diprakirakan.
        "usage_type": barang["usage_type"],
    }
    hasil["warehouse"] = {
        "id": gudang["id"], "code": gudang["code"], "name": gudang["name"],
    }
    # Ditetapkan di sini, bukan hanya di dalam hitung(), karena cabang
    # "histori belum cukup" tidak mengisi kunci ini sedangkan API membacanya.
    hasil["method"] = metode
    hasil["as_of"] = as_of.isoformat()

    # --- keterangan model ---
    # `model` adalah yang DIMINTA, `model_used` yang benar-benar meramal.
    # Keduanya berbeda tepat pada dua keadaan yang harus terlihat jujur di
    # layar: saat "terbaik" memilihkan sesuatu, dan saat model pilihan gagal
    # lalu jatuh ke cadangan. Menyatukannya menjadi satu ruas akan menyembunyikan
    # keduanya.
    hasil["model"] = model
    hasil["model_used"] = dipilih
    # Deret pengeluaran harian yang menjadi masukan seluruh model. Diterbitkan
    # supaya lapisan lain -- perhitungan ROP di app/rop.py -- tidak perlu
    # mengulang pembacaan dan pengisian hari kosong yang sama; dua pembacaan
    # atas sumber yang sama cepat atau lambat akan berbeda isinya.
    hasil["riwayat_harian"] = riwayat
    hasil["umur_pakai"] = _jadwal_penggantian(
        barang["service_life_value"], barang["service_life_unit"],
        penggantian_terakhir, hari_ini)
    # Keterangan strategi, supaya layar dapat menyebut atas dasar apa cadangan
    # itu setebal itu -- dan mengakui ketika ia jatuh ke angka master.
    hasil["strategy"] = s_strategi.kunci if s_strategi else None
    hasil["strategy_z"] = s_strategi.z if s_strategi else None
    hasil["strategy_service_level"] = (s_strategi.service_level
                                       if s_strategi else None)
    hasil["strategy_rmse"] = rmse_model
    # Dasar angka di atas: galat backtest model, atau simpangan baku permintaan
    # harian. Keduanya bersatuan unit per hari sehingga rumus cadangannya sama,
    # tetapi artinya berbeda -- dan kartu yang mencetak "RMSE model" di atas
    # simpangan baku permintaan adalah keterangan yang keliru. null berarti
    # rantai strategi tidak berjalan sama sekali.
    hasil["safety_stock_basis"] = dasar_sebaran
    hasil["strategy_applied"] = safety_strategi is not None
    hasil["model_label"] = i18n.t(f"model.{dipilih}", lang)
    # Papan skor hanya terbit pada mode "terbaik": di mode lain tidak ada
    # perlombaan yang terjadi, dan menerbitkan papan kosong akan membuat layar
    # menampilkan tabel yang tidak menjelaskan apa pun.
    hasil["model_scoreboard"] = [
        {**baris, "label": i18n.t(f"model.{baris['model']}", lang)}
        for baris in papan
    ] if model == klasik.KUNCI_TERBAIK else []
    return hasil


@router.get("")
def forecast(
    item_id: int = Query(..., gt=0),
    warehouse_id: int = Query(..., gt=0),
    forecast_days: int = Query(7, ge=1, le=FORECAST_DAYS_MAX),
    historical_days: int = Query(HISTORICAL_DAYS_DEFAULT, ge=7, le=HISTORICAL_DAYS_MAX),
    lang: str = Query(i18n.BAHASA_BAWAAN,
                      description="Bahasa kalimat penjelas: id atau en."),
    model: str = Query(klasik.KUNCI_STATISTIK,
                       description=("Model prakiraan. Bawaannya rumus statistik "
                                    "sederhana; 'best' mengadu seluruhnya.")),
) -> dict:
    return _susun(item_id, warehouse_id, forecast_days, historical_days, lang,
                  _model_sah(model))


class AnalysisIn(BaseModel):
    item_id: int = Field(..., gt=0)
    warehouse_id: int = Field(..., gt=0)
    forecast_days: int = Field(7, ge=1, le=FORECAST_DAYS_MAX)
    historical_days: int = Field(HISTORICAL_DAYS_DEFAULT, ge=7, le=HISTORICAL_DAYS_MAX)
    lang: str = Field(i18n.BAHASA_BAWAAN, description="Bahasa jawaban: id atau en.")


_PROMPT_ANALISIS = """Kamu analis persediaan. Kamu menerima hasil prakiraan yang SUDAH DIHITUNG sistem.

Aturan mutlak:
- JANGAN menghitung ulang, mengubah, membulatkan, atau menambah angka apa pun. Pakai persis angka yang diberikan.
- Seluruh angka sudah berupa bilangan bulat. JANGAN pernah menulis angka berkoma; bila terasa perlu, berarti Anda sedang menghitung sendiri, dan itu dilarang.
- JANGAN menyebut angka yang tidak ada pada data.
{BAHASA}
- Sebutkan kondisi stok saat ini, laju pemakaian, perkiraan sisa pada akhir periode, dan posisinya terhadap titik pemesanan ulang. Bila menyebut titik pemesanan ulang, pakai yang efektif — yang master hanya disebut bila memang perlu dibandingkan, dan bedanya harus dijelaskan.
- Bila potensi_kekurangan lebih besar dari nol, sebutkan angkanya persis sebagai potensi kekurangan pada periode itu. Bila nol, nyatakan stok diperkirakan mencukupi periode tersebut.
- Tutup dengan satu saran tindakan yang selaras dengan status.
- Jangan memakai tabel, daftar berpoin, maupun judul. Tulis paragraf mengalir.
- Jangan menyebut nama tool, endpoint, atau istilah teknis internal."""


def prompt_analisis(lang: str) -> str:
    """
    Prompt sistem dengan satu baris yang menentukan bahasa jawabannya.

    Bahasanya disisipkan, bukan ditulis dua kali: seluruh aturan lain -- larangan
    menghitung ulang, larangan angka berkoma -- harus berlaku sama persis pada
    kedua bahasa, dan menyalin prompt berarti membuka pintu bagi keduanya untuk
    perlahan berbeda.
    """
    return _PROMPT_ANALISIS.replace("{BAHASA}", i18n.t("rec.prompt.lang", lang))


def _rekomendasi_tanpa_ai(h: dict, lang: str = i18n.BAHASA_BAWAAN) -> dict:
    """
    Rekomendasi cadangan yang disusun dari angka, tanpa model bahasa.

    Dipakai bila layanan AI mati. Isinya lebih kaku, tetapi tetap benar --
    lebih baik daripada membuat seluruh halaman gagal hanya karena AI padam.

    Angkanya dibulatkan seperti kartu di layar. Panel ini duduk tepat di bawah
    kartu keputusan; menyebut "45,48 PCS" di situ sementara kartunya berbunyi
    "45 PCS" membuat pembaca menduga keduanya menghitung hal yang berbeda.
    """
    satuan = h["item"]["unit_code"]
    sisa = decision.bulat(h["predicted_remaining_stock"])
    rop = decision.bulat(h["reorder_point"])
    hari = h["forecast_days"]

    if h["status"] == forecasting.STATUS_CRITICAL:
        judul = i18n.t("rec.critical.title", lang)
        if h["days_until_stockout"]:
            # Laju harian disebut lewat label frekuensi, bukan pecahan: laju di
            # bawah satu unit per hari dibulatkan menjadi nol dan kalimatnya
            # berubah menjadi salah.
            isi = i18n.t("rec.critical.body_stockout", lang,
                         laju=h["usage_frequency_label"],
                         detail=h["usage_frequency_detail"],
                         n=h["days_until_stockout"], hari=hari)
        else:
            isi = i18n.t("rec.critical.body_rop", lang,
                         sisa=sisa, rop=rop, u=satuan, hari=hari)
    elif h["status"] == forecasting.STATUS_ATTENTION:
        judul = i18n.t("rec.attention.title", lang)
        isi = i18n.t("rec.attention.body", lang, sisa=sisa, rop=rop, u=satuan)
    else:
        judul = i18n.t("rec.safe.title", lang)
        isi = i18n.t("rec.safe.body", lang, sisa=sisa, rop=rop, u=satuan)

    return {
        "status": h["status"],
        "title": judul,
        "body": isi,
        "source": "rule_based",
        "ai_available": False,
        "notice": i18n.t("rec.notice.ai_off", lang),
    }


def _rekomendasi(h: dict, lang: str = i18n.BAHASA_BAWAAN) -> dict:
    """Rekomendasi dari model bahasa; jatuh ke versi tanpa AI bila gagal."""
    if h["status"] == forecasting.STATUS_INSUFFICIENT:
        return {
            "status": h["status"],
            "title": i18n.t("rec.insufficient.title", lang),
            "body": i18n.t("rec.insufficient.body", lang),
            "source": "rule_based",
            "ai_available": False,
            "notice": None,
        }

    dasar = _konteks(h)
    try:
        jawaban = llm.chat([
            {"role": "system", "content": prompt_analisis(lang)},
            {"role": "user", "content": f"Hasil prakiraan:\n{dasar}"},
        ])
        teks = llm.bersihkan(jawaban.get("content"))
        if not teks:
            raise ValueError("jawaban model kosong")
        cadangan = _rekomendasi_tanpa_ai(h, lang)
        return {
            "status": h["status"],
            "title": cadangan["title"],   # judul tetap dari angka, bukan karangan model
            "body": teks,
            "source": "ai",
            "ai_available": True,
            "notice": None,
        }
    except Exception as e:  # noqa: BLE001 -- AI padam tidak boleh menjatuhkan halaman
        log.warning("Rekomendasi AI gagal, memakai versi tanpa AI: %s", e)
        return _rekomendasi_tanpa_ai(h, lang)


def _konteks(h: dict) -> dict:
    """
    Angka yang diserahkan ke model bahasa.

    SELURUHNYA BILANGAN BULAT, sama seperti yang tercetak di kartu. Model
    dilarang keras menghitung ulang atau membulatkan sendiri, jadi apa pun yang
    dikirim ke sini akan muncul apa adanya pada paragrafnya -- dan paragraf itu
    duduk tepat di bawah kartu yang menampilkan angka yang sama. Mengirim
    "1,16" ke sini berarti menempatkan "1,16 PCS per hari" di sebelah kartu
    yang berbunyi "±1 PCS per hari".

    Laju harian dikirim sebagai LABEL, bukan angka: barang yang keluar seminggu
    sekali berlaju 0,14, dan membulatkannya menjadi 0 mengubah kalimat model
    menjadi "tidak ada pemakaian".
    """
    b = decision.bulat
    return {
        "barang": f"{h['item']['sku']} - {h['item']['name']}",
        "gudang": h["warehouse"]["name"],
        "satuan": h["item"]["unit_code"],
        "stok_saat_ini": b(h["current_stock"]),
        "rata_pemakaian": f"{h['usage_frequency_label']} {h['usage_frequency_detail']}".strip(),
        "periode_prakiraan_hari": h["forecast_days"],
        "perkiraan_pemakaian": b(h["predicted_usage"]),
        "perkiraan_sisa_stok": b(h["predicted_remaining_stock"]),
        # Nol berarti stok mencukupi periode ini. Dikirim apa adanya supaya
        # model tidak perlu -- dan tidak boleh -- menghitung selisihnya sendiri.
        "potensi_kekurangan": b(h["projected_shortage"]),
        "titik_pemesanan_ulang_master": b(h["reorder_point"]),
        "titik_pemesanan_ulang_efektif": h["effective_reorder_point_int"],
        "stok_minimum": b(h["minimum_stock"]),
        "hari_sampai_titik_pesan": h["days_until_reorder_point"],
        "hari_sampai_habis": h["days_until_stockout"],
        "status_reorder": h["action_status_label"],
        "jumlah_yang_perlu_dipesan": h["recommended_order_qty"],
        "status": h["status"],
        "mutu_data": h["data_quality"]["label"],
        "panjang_histori_hari": h["data_quality"]["history_days"],
    }


@router.post("/analysis")
def analysis(payload: AnalysisIn) -> dict:
    """
    Penjelasan bahasa alami atas hasil prakiraan.

    Angkanya dihitung ulang di sini, bukan diterima dari klien, supaya model
    tidak mungkin diberi angka palsu untuk dibenarkan.
    """
    lang = i18n.normalisasi(payload.lang)
    hasil = _susun(
        payload.item_id, payload.warehouse_id, payload.forecast_days,
        payload.historical_days, lang,
    )

    if hasil["status"] == forecasting.STATUS_INSUFFICIENT:
        raise invalid(i18n.t("err.analysis_insufficient", lang), "historical_days")

    ringkas = _konteks(hasil)

    jawaban = llm.chat([
        {"role": "system", "content": prompt_analisis(lang)},
        {"role": "user", "content": f"Hasil prakiraan:\n{ringkas}"},
    ])
    teks = llm.bersihkan(jawaban.get("content"))
    return {
        "analysis": teks,
        "runtime": llm.RUNTIME,
        "based_on": ringkas,
    }
