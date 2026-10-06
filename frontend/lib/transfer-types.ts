/**
 * Bentuk jawaban modul Transfer Antar Gudang.
 * Shape of the inter-warehouse transfer module's responses.
 *
 * SELURUH KUANTITAS DI SINI BILANGAN BULAT, dan tipenya menyatakan itu apa
 * adanya. Backend sudah membulatkannya ke arah yang benar -- surplus ke bawah,
 * kebutuhan ke atas -- sehingga layar tidak pernah membulatkan apa pun sendiri.
 * Pembulatan kedua di frontend adalah cara paling mudah membuat dua layar
 * menyebut jumlah kiriman yang berbeda untuk satu dokumen yang sama.
 *
 * Every quantity here is an integer, and the types say so. The backend has
 * already rounded in the correct direction -- surplus down, shortfall up -- so
 * the screen never rounds anything itself.
 */

/** Keputusan akhir satu kebutuhan. */
export type KeputusanTransfer = "TRANSFER" | "TRANSFER_SEBAGIAN" | "PEMBELIAN";

/** Tahap dokumen transfer. */
export type StatusTransfer =
  | "draft"
  | "approved"
  | "in_transit"
  | "completed"
  | "cancelled";

/** Dasar pencocokan barang antar gudang. */
export type DasarCocok = "sku" | "fuzzy";

export interface KomponenSkor {
  sufficiency: number;
  surplus_ratio: number;
  distance: number;
  lead_time: number;
  name_similarity: number;
}

/**
 * Satu gudang kandidat sumber.
 *
 * Kandidat yang DITOLAK memakai bentuk yang sama, hanya `eligible` false dan
 * `rejected_reason` terisi. Disatukan dengan sengaja: layar menampilkan
 * keduanya pada tabel yang sama, dan dua tipe berbeda akan menuntut dua
 * komponen tabel yang cepat atau lambat berbeda tampilannya.
 */
export interface KandidatTransfer {
  from_warehouse_id: number;
  from_warehouse_code: string;
  from_warehouse_name: string;

  /** barang yang benar-benar dikirim; berbeda dari barang tujuan pada cocok fuzzy */
  item_id: number;
  sku: string;
  item_name: string;
  unit_code: string;

  source_stock_int: number;
  source_reorder_point_int: number;
  source_status: string;
  source_status_label: string;
  /** yang benar-benar boleh diambil, di atas titik pesan efektif gudang asal */
  surplus: number;

  distance_km: number | null;
  /** "matrix" bila ditetapkan tangan, "haversine" bila dari koordinat */
  distance_basis: "matrix" | "haversine" | null;
  lead_time_days: number | null;

  match_type: DasarCocok;
  /** hanya terisi pada cocok fuzzy */
  match_similarity: number | null;

  score: number;
  components?: KomponenSkor;
  weights?: Record<string, number>;

  eligible: boolean;
  rejected_reason: string | null;
  rejected_label: string | null;
  /** kalimat siap render; menyebut angka yang sama dengan kolom di sebelahnya */
  why: string;
}

/** Kandidat yang KEBAGIAN alokasi, beserta jumlah yang dikirimnya. */
export interface KirimanTransfer extends KandidatTransfer {
  transfer_qty: number;
  /** SATU rute terbaik (moda) menurut model; peta menggambar usulan menurut ini */
  route_ml?: {
    mode: ModaAngkut;
    predicted_days: number;
    predicted_cost: number;
    predicted_received: number;
    alternatives: number;
    /** pengiriman GABUNGAN yang dinilai: seluruh barang satu pasangan gudang */
    shipment_qty: number;
    shipment_value: number;
    shipment_items: number;
    shipment_cost: number;
    deadline_days: number | null;
  };
}

export interface BarisTransfer {
  item_id: number;
  warehouse_id: number;
  sku: string;
  item_name: string;
  unit_code: string;

  to_warehouse_id: number;
  to_warehouse_code: string;
  to_warehouse_name: string;

  available_stock_int: number;
  effective_reorder_point_int: number;
  safety_stock_int: number;
  lead_time_days_int: number | null;
  /** batas tiba: lead time pembelian atau sisa hari stok, mana yang lebih dekat */
  route_deadline_days?: number | null;
  days_of_cover_int: number | null;
  /** Periode yang dipilih dan kebutuhannya; sama dengan daftar Pemesanan Ulang. */
  decision_horizon_days: number;
  forecast_usage_int: number | null;
  action_status: string;
  action_status_label: string;
  priority: string;
  reorder_reason: string;

  /** kekurangan, DIPINJAM utuh dari mesin pemesanan ulang */
  need_qty: number | null;
  transfer_qty: number;
  /** sisa yang tetap harus dibeli; nol berarti tidak ada pembelian sama sekali */
  purchase_qty: number | null;
  decision: KeputusanTransfer;
  decision_label: string;
  reason: string;

  legs: KirimanTransfer[];
  candidates: KandidatTransfer[];
  rejected: KandidatTransfer[];
  candidate_count: number;
}

export interface RingkasTransfer {
  total_baris: number;
  dapat_transfer: number;
  transfer_sebagian: number;
  harus_beli: number;
  total_qty_transfer: number;
  total_qty_beli: number;
  memakai_fuzzy: boolean;
  ambang_kemiripan: number;
}

export interface DaftarTransfer {
  items: BarisTransfer[];
  summary: RingkasTransfer;
  horizon_days: number;
  total: number;
  page: number;
  page_size: number;
  pages: number;
  truncated: boolean;
  row_limit: number;
}

/** Satu dokumen transfer pada daftar dokumen. */
export interface DokumenTransfer {
  id: number;
  transfer_number: string;
  transfer_date: string;
  status: StatusTransfer;
  status_label: string;
  notes: string | null;
  source: string | null;
  score: number | null;
  reason: string | null;
  distance_km: string | number | null;
  /** moda yang dipilih, biaya sesungguhnya, dan janji lama tempuh (migrasi 035) */
  transport_mode: ModaAngkut | null;
  shipping_cost: string | number | null;
  planned_days: string | number | null;
  approved_at: string | null;
  shipped_at: string | null;
  received_at: string | null;
  cancelled_at: string | null;

  from_warehouse_id: number;
  from_warehouse_code: string;
  from_warehouse_name: string;
  to_warehouse_id: number;
  to_warehouse_code: string;
  to_warehouse_name: string;

  /*
   * Letak kedua gudang, untuk peta rute pada layar Dokumen.
   *
   * BOLEH null, DAN null BERARTI BELUM DIISI -- bukan nol. Gudang yang
   * koordinatnya kosong tidak digambar sama sekali; peta ini tidak pernah
   * menaruh gudang pada titik yang ditebaknya sendiri, karena rute yang
   * berangkat dari kota yang salah terbaca persis sama meyakinkannya dengan
   * rute yang benar.
   */
  from_latitude: number | null;
  from_longitude: number | null;
  to_latitude: number | null;
  to_longitude: number | null;

  line_count: number;
  total_quantity: number;
  /** tahap yang sah dari status sekarang; layar tidak menebaknya sendiri */
  next_statuses: StatusTransfer[];
}

/** Satu baris barang pada dokumen transfer; dibaca saat rinciannya dibuka. */
export interface BarisBarangDokumen {
  id: number;
  item_id: number;
  sku: string;
  item_name: string;
  unit_code: string;
  quantity: number;
  /** barang tujuan yang kebutuhannya ditutup baris ini; berbeda hanya pada cocok fuzzy */
  for_item_id: number | null;
  for_sku: string | null;
  for_item_name: string | null;
  match_type: DasarCocok | null;
  match_similarity: number | null;
  /** yang benar-benar sampai; null = belum diterima atau tidak dicatat */
  received_quantity: number | null;
}

/** GET /api/transfers/{id} */
export interface DetailDokumenTransfer {
  transfer: DokumenTransfer;
  lines: BarisBarangDokumen[];
  summary: { line_count: number; total_quantity: number };
}

export interface DaftarDokumenTransfer {
  items: DokumenTransfer[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

/* ------------------------------------------------------------------ */
/* Rekomendasi rute (model ML klasik)                                  */
/* ------------------------------------------------------------------ */

export type ModaAngkut = "darat" | "laut" | "udara";
export type PrioritasRute = "seimbang" | "tercepat" | "termurah" | "terpenuh";

export interface OpsiRute {
  mode: ModaAngkut;
  label: { id: string; en: string };
  distance_km: number;
  predicted_days: number;
  predicted_cost: number;
  cost_per_unit: number;
  predicted_received: number;
  predicted_received_ratio: number;
  /** nilai barang yang diperkirakan rusak/hilang (rupiah) */
  expected_loss_value: number;
  /** ongkos + nilai kerugian */
  total_cost: number;
  /** tiba sesudah batas waktu (mis. sesudah pembelian baru tiba) */
  late: boolean;
  score: number;
  rank: number;
  badges: ("tercepat" | "termurah" | "terpenuh" | "terdekat")[];
}

export interface ModelRute {
  kind: "ml" | "tarif_standar";
  algorithm?: string;
  n_train: number;
  min_history: number;
  range?: { dari: string; sampai: string };
  metrics?: { hari_mae: number; biaya_mape: number; terima_mae: number };
}

/** GET /api/transfer/rute-ml */
export interface RekomendasiRute {
  from_warehouse_id?: number;
  to_warehouse_id?: number;
  quantity?: number;
  priority?: PrioritasRute;
  deadline_days?: number | null;
  options: OpsiRute[];
  recommended_mode: ModaAngkut | null;
  model: ModelRute;
}
