/**
 * Bentuk jawaban GET /api/forecast.
 *
 * Satu endpoint melayani DUA halaman dengan pertanyaan yang berbeda:
 *
 *   Forecasting  "berapa kebutuhan barang ini pada periode mendatang?"
 *   Reorder      "kapan stok perlu dipesan, dan berapa jumlahnya?"
 *
 * Tipenya ditaruh di sini, bukan disalin ke masing-masing halaman: dua salinan
 * yang berangsur berbeda adalah cara paling mudah membuat dua layar
 * menampilkan angka yang tidak lagi sebanding padahal sumbernya satu.
 *
 * Penandaan lapisan pada komentar di bawah bukan hiasan. Field lapisan
 * prakiraan BERGERAK saat `days` diubah; field lapisan reorder berpatokan lead
 * time dan stok tersedia, sehingga halaman Reorder sengaja tidak menyediakan
 * pilihan periode sama sekali.
 *
 * DUA VERSI TIAP ANGKA, DAN HANYA SATU YANG BOLEH DIRENDER. Field bernama
 * `*_int` adalah versi tampilannya: bilangan bulat, dibulatkan backend dengan
 * satu aturan yang sama untuk seluruh halaman. Field desimal di sebelahnya
 * tetap dikirim untuk penelusuran dan pembaca API lain, tetapi TIDAK BOLEH
 * masuk ke layar -- satuan gudang diskrit, dan "45,48 PCS" hanya memberi kesan
 * presisi yang tidak pernah dimiliki prakiraan. Begitu pula kalimat
 * `*_reason` / `*_basis` / `*_label`: seluruhnya sudah jadi di backend dan
 * memakai angka bulat yang sama dengan kartunya, sehingga mustahil berselisih
 * dengan angka di sebelahnya.
 */

export type Status = "SAFE" | "ATTENTION" | "CRITICAL" | "INSUFFICIENT_DATA";

/** Sumbu status keputusan, terpisah dari `status` lama yang dipakai halaman lain. */
/**
 * Sumbu status keputusan.
 *
 * TIGA KEADAAN. PANTAU dan SEGERA_PESAN adalah sumbu LAMA; backend tidak
 * menerbitkannya lagi sejak 2 September 2026, tetapi keduanya tetap diketik di
 * sini karena jawaban lama yang tersimpan di mana pun -- cache peramban, tab
 * yang belum dimuat ulang -- masih membawanya, dan komponen yang memetakan
 * status ke warna harus tetap punya jawaban untuk keduanya alih-alih merender
 * `undefined`.
 */
export type AksiStatus =
  | "AMAN"
  | "PERLU_REORDER"
  | "RISIKO_STOCKOUT"
  | "PANTAU"
  | "SEGERA_PESAN";

/** Sumbu prioritas, terpisah dari status: yang ini menjawab "mana dulu". */
export type Prioritas = "TINGGI" | "SEDANG" | "RENDAH";

/**
 * Satu baris daftar Pemesanan Ulang, dari GET /api/reorder.
 *
 * Bentuknya SENGAJA BUKAN `Forecast`. Daftar ini hanya memuat yang benar-benar
 * dirender kolomnya; mengirim seluruh muatan prakiraan untuk empat ratus baris
 * berarti memindahkan megabyte yang tidak satu pun dibaca. Setiap field di
 * bawah dihitung jalur yang sama persis dengan /api/forecast, jadi satu barang
 * mustahil menyebut angka berbeda di daftar dan di layar detailnya.
 */
export interface BarisReorder {
  item_id: number;
  warehouse_id: number;
  sku: string;
  item_name: string;
  unit_code: string;
  warehouse_code: string;
  warehouse_name: string;

  current_stock_int: number;
  available_stock_int: number;
  reorder_point_int: number;
  effective_reorder_point_int: number;
  safety_stock_int: number;
  lead_time_days_int: number | null;
  lead_time_demand_int: number | null;

  /** Periode yang dipilih di layar; kebutuhannya sama dengan halaman Prakiraan. */
  decision_horizon_days: number;
  forecast_usage_int: number | null;
  /** Kebutuhan periode − stok tersedia; null bila prakiraan belum tersedia. */
  period_shortage_int: number | null;
  /** Stok tersedia − kebutuhan periode; null bila prakiraan belum tersedia. */
  period_surplus_int: number | null;
  usage_frequency_label: string;
  usage_frequency_detail: string;

  /** null berarti stok tidak bergerak, bukan "belum dihitung". */
  days_of_cover_int: number | null;
  days_to_effective_rop_int: number | null;

  action_status: AksiStatus;
  action_status_label: string;
  priority: Prioritas;
  priority_label: string;
  /** Kalimat siap render dari backend; menyebut angka yang sama dengan kolomnya. */
  reason: string;
  /** null berarti belum dapat dihitung; 0 berarti tidak perlu membeli. */
  recommended_order_qty: number | null;
  order_up_to_level_int: number | null;
  has_forecast: boolean;
}

export interface RingkasReorder {
  perlu_reorder: number;
  risiko_stockout: number;
  prioritas_tinggi: number;
  aman: number;
  total_qty: number;
  qty_belum_terhitung: number;
  total_baris: number;
  /** Periode yang dipakai menghitung seluruh daftar. */
  horizon_hari: number;
}

export interface DaftarReorder {
  items: BarisReorder[];
  summary: RingkasReorder;
  total: number;
  page: number;
  page_size: number;
  pages: number;
  /** true berarti katalognya melebihi batas dan daftar ini sebagian. */
  truncated: boolean;
  row_limit: number;
}

export interface Rekomendasi {
  status: Status;
  title: string;
  body: string;
  source: "ai" | "rule_based";
  ai_available: boolean;
  notice: string | null;
}

export interface BarisDetail {
  label: string;
  value: string;
  kind: "text" | "status" | "warning";
  raw?: number | null;
  status?: AksiStatus;
}

export interface SeksiDetail {
  key: string;
  title: string;
  rows: BarisDetail[];
}

/**
 * Cerita halaman, disusun backend. Lihat decision.kalimat_cerita.
 *
 * `dasar` hanya ada pada jawaban prakiraan/reorder: ia menyebut panjang histori
 * yang menopang seluruh angkanya. Halaman lain tidak selalu memilikinya --
 * Analisis Umur Pakai, misalnya, menyebut dasarnya per baris karena tiap
 * komponen berdiri di atas jumlah penggantian yang berbeda.
 */
export interface Narasi {
  judul: string;
  paragraf: string[];
  dasar?: string;
}

/** Satu baris papan skor perlombaan model; hanya terisi pada mode "terbaik". */
export interface SkorModel {
  model: string;
  label: string;
  /** Galat absolut terskala. Di bawah 1 berarti mengalahkan tebakan naif. */
  mase: number;
  lipatan: number;
}

/** Satu pilihan strategi layanan; datang dari endpoint yang sama. */
export interface PilihanStrategi {
  key: string;
  label: string;
  description: string;
  service_level: number;
  z: number;
}

/** Hasil rantai model -> galat -> cadangan -> titik pesan (/api/forecast/rop). */
export interface HasilRop {
  selected_forecast_model: string;
  predicted_daily_demand: number;
  model_rmse: number | null;
  selected_strategy: string;
  calculated_safety_stock: number;
  final_reorder_point: number;
}

/** Satu pilihan pada dropdown model, datang dari /api/forecast/models. */
export interface PilihanModel {
  key: string;
  label: string;
  description: string;
  available: boolean;
}

export interface Forecast {
  narasi: Narasi | null;
  /** Yang DIMINTA; berbeda dari model_used saat "terbaik" memilihkan. */
  model: string;
  model_used: string;
  model_label: string;
  model_scoreboard: SkorModel[];
  /* Keterangan strategi layanan. `strategy_applied` false berarti safety
     stock-nya masih dari master barang -- entah karena tidak ada strategi yang
     diminta, entah karena galat model belum dapat diukur. */
  strategy: string | null;
  strategy_z: number | null;
  strategy_service_level: number | null;
  strategy_rmse: number | null;
  /* Dasar strategy_rmse. "demand_stdev" berarti simpangan baku permintaan
     harian (jalur statistik sederhana), "model_rmse" berarti galat backtest
     model. Satuannya sama, artinya tidak. null berarti rantai strategi tidak
     berjalan.

     TIDAK ADA KOMPONEN YANG BERCABANG ATASNYA lagi: halaman Pemesanan Ulang
     tidak mengirim parameter model, jadi jawabannya selalu "demand_stdev" dan
     label-labelnya ditulis tetap. Ruas ini tetap diketik di sini karena API
     memang menerbitkannya -- dan karena inilah yang harus diperiksa lebih
     dulu bila pemilih model kelak dikembalikan ke layar itu. */
  safety_stock_basis: "model_rmse" | "demand_stdev" | null;
  strategy_applied: boolean;
  warehouse: { id: number; code: string; name: string };
  item: {
    id: number;
    sku: string;
    name: string;
    unit_code: string;
    /** berumur_pakai = dijadwalkan; habis_pakai = diprakirakan (migrasi 034) */
    usage_type?: JenisPemakaian;
  };

  // --- stok & master barang (dipakai halaman Reorder) ---
  current_stock: number;
  reserved_stock: number;
  available_stock: number;
  reorder_point: number;
  minimum_stock: number;

  // --- lapisan prakiraan: SELURUHNYA mengikuti forecast_days ---
  forecast_days: number;
  average_daily_usage: number | null;
  forecast_usage: number | null;
  expected_stock: number | null;
  /** Nol berarti mencukupi; null berarti belum dapat dihitung. */
  projected_shortage: number | null;

  /** versi tampilan lapisan prakiraan -- INI yang dirender, bukan yang di atas */
  forecast_usage_int: number | null;
  expected_stock_int: number | null;
  projected_shortage_int: number | null;
  reserved_stock_int: number;
  days_until_reorder_point: number | null;
  days_until_stockout: number | null;
  historical: { date: string; stock: number }[];
  forecast: { date: string; stock: number }[];
  /**
   * Pemakaian PER HARI dalam bilangan bulat. Jumlah `usage_int` tepat sama
   * dengan forecast_usage_int; baris terakhir memuat sisa stok dan kekurangan
   * pada akhir periode. Basis stoknya available_stock_int. Kosong bila
   * histori belum cukup.
   */
  daily_plan: { day: number; date: string; usage_int: number; stock_int: number; shortage_int: number }[];
  reorder_crossing_date: string | null;
  historical_period: { days: number; start: string | null; end: string };
  baseline_daily_usage: number | null;
  method: string;

  // --- kecukupan data ---
  status: Status;
  message: string | null;
  has_forecast: boolean;
  data_quality: { label: string; history_days: number; days_with_outflow: number };
  requirements: {
    min_history_days: number;
    min_days_with_outflow: number;
    actual_history_days: number;
    actual_days_with_outflow: number;
  };
  /*
   * Jadwal penggantian dari umur pakai komponen, berdiri sendiri di luar
   * seluruh angka prakiraan. `due_date` hanya terisi untuk umur pakai bersatuan
   * tahun: mengubah "12.500 jam" menjadi tanggal menuntut jam operasi per hari,
   * dan angka itu tidak dimiliki basis data. null bila umur pakainya belum
   * dicatat pada master barang.
   */
  service_life: {
    value: number;
    unit: "jam" | "tahun";
    last_replacement: string | null;
    due_date: string | null;
    days_remaining: number | null;
  } | null;
  quality_level: string;
  quality_reason: string;
  low_confidence_estimate: boolean;
  low_confidence_reason: string;
  /*
   * TIDAK ADA FIELD confidence_* DI SINI, DAN ITU DISENGAJA.
   *
   * `lapisan_keputusan()` pada backend memang menghitung confidence_level,
   * confidence_label, dan confidence_note, tetapi /api/forecast menyusun
   * jawabannya dari daftar kunci pilihan dan ketiganya tidak termasuk. Selama
   * ketiganya dideklarasikan di sini sebagai `string`, TypeScript menjamin
   * sesuatu yang tidak pernah dikirim: layar lalu mencetak `ro.conf.undefined`
   * -- nama kunci kamus, bukan kalimat -- dan keterangannya kosong. Itulah
   * yang dulu terbaca sebagai "Confidence Level: undefined".
   *
   * Bila suatu saat ketiganya benar-benar diteruskan forecast_api.py,
   * kembalikan deklarasinya BERSAMA perubahan backend itu, bukan sebelumnya.
   *
   * `confidence_note_forecast` adalah pengecualiannya, dan sudah diperiksa:
   * forecast_api.py memang mencantumkannya pada jawaban. Ia kembaran
   * confidence_note untuk lapisan PRAKIRAAN -- histori yang sama, tetapi
   * menyebut angka yang benar-benar ada di halaman ini (kebutuhan periode,
   * sisa stok, potensi kekurangan) alih-alih angka lapisan reorder.
   */
  confidence_note_forecast: string;
  as_of: string;

  // --- lapisan keputusan, seluruhnya dihitung backend ---
  action_status: AksiStatus;
  action_status_label: string;
  action_text: string;
  days_to_rop: number | null;
  days_to_rop_bucket: string;
  reorder_point_reached: boolean;
  usage_frequency_label: string;
  usage_frequency_detail: string;
  /** Alias warisan; sejak rumus stok maksimum dihapus ia sama dengan
      recommended_order_qty, dengan null dipetakan ke 0. */
  suggested_order_qty: number;
  priority: Prioritas;
  priority_label: string;
  /** Horizon TETAP dasar jumlah pesanan; tidak mengikuti `days` yang diminta. */
  decision_horizon_days: number;
  decision_horizon_usage: number | null;
  decision_horizon_usage_int: number | null;

  // --- lapisan reorder: berpatokan lead time, BUKAN forecast_days ---
  lead_time_days: number | null;
  safety_stock: number;
  lead_time_demand: number | null;
  /** kebutuhan masa tunggu + safety stock; boleh berbeda dari reorder_point master */
  effective_reorder_point: number;
  days_to_effective_rop: number | null;
  /*
   * days_of_cover / days_of_cover_int juga TIDAK ADA di sini, dengan sebab yang
   * sama: dihitung backend, tidak pernah diteruskan /api/forecast. Ketahanan
   * stok pada layar Reorder dinyatakan dalam kali pengambilan
   * (`remaining_pickups`), yang memang dikirim.
   */
  /** sampai berapa stok diisi saat pengadaan dilakukan (level "S") */
  order_up_to_level: number | null;
  /** null berarti belum dapat dinilai (kebutuhan masa tunggu tidak diketahui). */
  reorder_point_adequate: boolean | null;
  /**
   * null berarti belum dapat dihitung; 0 berarti tidak perlu membeli.
   * Selaras dengan action_status: SEGERA_PESAN tidak pernah berpasangan
   * dengan 0, dan 0 tidak pernah berpasangan dengan SEGERA_PESAN.
   */
  recommended_order_qty: number | null;
  effective_reorder_point_reached: boolean;

  /** versi tampilan lapisan reorder -- INI yang dirender */
  available_stock_int: number;
  lead_time_demand_int: number | null;
  effective_reorder_point_int: number;
  days_to_effective_rop_int: number | null;
  order_up_to_level_int: number | null;
  safety_stock_int: number;
  lead_time_days_int: number | null;

  /** kalimat siap render, disusun backend dari angka bulat yang sama */
  days_to_effective_rop_label: string;
  reorder_status_reason: string;
  effective_reorder_point_basis: string;
  order_qty_title: string;
  order_qty_reason: string;

  is_lumpy: boolean;
  stock_below_minimum: boolean;
  current_stock_int: number;
  minimum_stock_int: number;
  reorder_point_int: number;
  advice_text: string;
  remaining_pickups: number | null;
  recommendation: Rekomendasi | null;
  calculation_detail: { sections: SeksiDetail[] };
}

/** Jenis pemakaian barang (items.usage_type). */
export type JenisPemakaian = "berumur_pakai" | "habis_pakai";
