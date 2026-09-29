/**
 * Bentuk jawaban /api/lifetime.
 *
 * SELURUH KALIMAT SUDAH JADI SAAT SAMPAI DI SINI. `status_label`, `basis`,
 * `inventory_impact`, dan `replacement_trend_label` disusun backend bersama
 * angkanya (backend/app/lifetime.py). Halaman tidak boleh merangkainya ulang:
 * satu kesimpulan yang punya dua rumusan akan berselisih bunyi setelah salah
 * satunya diubah, dan yang lebih buruk, bisa berselisih angka.
 *
 * Yang null berarti TIDAK DIKETAHUI, bukan nol. `deviation_percentage: null`
 * pada komponen tanpa umur pakai referensi berbeda artinya dari `0`, yang
 * berarti persis sesuai harapan.
 */

export type StatusUmur = "PREMATURE" | "NORMAL" | "EXTENDED" | "INSUFFICIENT";
export type TrenPenggantian = "increasing" | "stable" | "decreasing";

export interface BarisUmurPakai {
  item: { id: number; sku: string; name: string; unit_code: string | null };
  warehouse: { id: number; code: string; name: string };

  /** apa adanya menurut master barang: 12500 "jam" atau 20 "tahun" */
  expected_value: number | null;
  expected_unit: "jam" | "tahun" | null;
  /** hasil konversi ke hari kalender; null bila referensinya belum ada */
  expected_lifetime_days: number | null;
  lower_lifetime_days: number | null;
  upper_lifetime_days: number | null;
  has_reference: boolean;

  replacement_count: number;
  interval_count: number;
  /** median jarak antar penggantian */
  actual_lifetime_days: number | null;
  last_actual_lifetime_days: number | null;
  shortest_lifetime_days: number | null;
  longest_lifetime_days: number | null;
  last_replacement_date: string | null;

  deviation_percentage: number | null;
  status: StatusUmur;
  status_label: string;
  replacement_trend: TrenPenggantian | null;
  replacement_trend_label: string | null;
  replacements_per_year: number | null;

  basis: string;
  inventory_impact: string | null;
}

export interface KejadianPenggantian {
  id: number;
  date: string;
  document: string;
  quantity: number;
  /** umur unit yang DIAKHIRI kejadian ini; null pada kejadian pertama */
  lifetime_days: number | null;
  deviation_percentage: number | null;
  status: StatusUmur | null;
  status_label: string | null;
}

export interface FaktorPendukung {
  key: string;
  label: string;
  /** selalu false hari ini; lihat backend/app/lifetime.py */
  available: boolean;
}

export interface DetailUmurPakai extends BarisUmurPakai {
  events: KejadianPenggantian[];
  events_total: number;
  contributing_factors: FaktorPendukung[];
  contributing_factors_note: string;
}

export interface DaftarUmurPakai {
  items: BarisUmurPakai[];
  summary: {
    total_items: number;
    premature: number;
    normal: number;
    extended: number;
    insufficient: number;
    /** bagian dari `insufficient` yang sebabnya master barang, bukan waktu */
    without_reference: number;
    total_replacements: number;
    trend_increasing: number;
  };
  total: number;
  page: number;
  page_size: number;
  pages: number;
  /** asumsi yang menopang seluruh halaman; ditampilkan, tidak disembunyikan */
  assumptions: {
    operating_hours_per_day: number;
    tolerance_percentage: number;
    note: string;
  };
}
