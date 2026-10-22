/**
 * Tata letak virtual untuk 3D Warehouse Twin.
 *
 * TIDAK ADA LOKASI FISIK DI SINI. Basis data hanya tahu stok per barang per
 * gudang; zona, rak, dan bin tidak tercatat. Berkas ini mengelompokkan barang
 * per kategori menjadi "rak virtual" dan menaruhnya di grid -- murni agar stok
 * mudah dilihat. Posisi 3D yang dihasilkan TIDAK menyatakan letak barang di
 * gudang sebenarnya, dan layar wajib mengatakannya.
 *
 * STATUS datang dari backend (/api/warehouse-twin), yang meminjamnya dari mesin
 * Pemesanan Ulang; berkas ini tidak menghitung ulang status, hanya
 * mengagregasi hitungannya.
 */

export type StatusTwin = "normal" | "perhatian" | "kritis" | "tidak_diketahui";

export interface BarisTwin {
  item_id: number;
  sku: string;
  name: string;
  category_id: number;
  category_name: string;
  unit_code: string;
  quantity: number | string;
  reserved_quantity: number | string;
  minimum_stock: number | string;
  reorder_point: number | string | null;
  maximum_stock: number | string | null;
  status: StatusTwin;
  /** keputusan mesin Pemesanan Ulang; null bila mesin tak menilai barang ini */
  decision: KeputusanTwin | null;
  /** hasil Analisis Umur Pakai; null bila barang tidak dinilai modul itu */
  lifetime: UmurTwin | null;
}

export interface UmurTwin {
  status: "PREMATURE" | "NORMAL" | "EXTENDED" | "INSUFFICIENT";
  status_label: string;
  deviation_percentage: number | null;
  has_reference: boolean;
  basis: string;
}

export interface KeputusanTwin {
  status_label: string;
  recommended_order_qty: number | null;
  days_of_cover: number | null;
  effective_reorder_point: number | null;
  available_stock: number | null;
  forecast_usage: number | null;
  horizon_days: number;
  priority_label: string;
}

export interface JawabanTwin {
  warehouse: { id: number; code: string; name: string; location: string | null };
  items: BarisTwin[];
  truncated: boolean;
  lifetime_available: boolean;
  location_mapping: { available: boolean; source: string };
}

/** Warna dasar status; sama dengan token --status-* pada globals.css. */
export const WARNA_STATUS: Record<StatusTwin, string> = {
  normal: "#16a34a",
  perhatian: "#f97316",
  kritis: "#dc2626",
  tidak_diketahui: "#9aa5b5",
};

export const URUT_STATUS: StatusTwin[] = ["normal", "perhatian", "kritis", "tidak_diketahui"];

/** Ukuran dalam meter; satu-satunya tempat angka geometri ditetapkan. */
export const UKURAN = {
  slotW: 1.2,
  slotD: 1.0,
  // 1,35 m per tingkat: tinggi lazim satu level pallet racking (pallet + ruang angkat)
  slotH: 1.35,
  slotPerTingkat: 4,
  tingkat: 3,
  lorong: 2.6,
  jarakKolom: 0.8,
  papan: 0.08,
  tiang: 0.08,
} as const;

export interface SlotTwin {
  item: BarisTwin;
  /** posisi pusat dasar kotak, relatif terhadap pusat rak */
  x: number;
  y: number;
  tingkat: number;
  /** 0..1; null bila stok maksimum belum diisi */
  isi: number | null;
}

export interface RakTwin {
  id: string;
  kode: string;
  kategori: string;
  x: number;
  z: number;
  lebar: number;
  dalam: number;
  tinggi: number;
  slots: SlotTwin[];
  status: StatusTwin;
}

export interface TataLetak {
  rak: RakTwin[];
  lebar: number;
  dalam: number;
  /** jumlah kolom/baris rak pada grid; dipakai untuk menurunkan lorong */
  kolom: number;
  baris: number;
}

const n = (v: number | string | null | undefined) => (v == null ? 0 : Number(v));

/** Status terburuk memenangkan: kritis > perhatian > normal > tidak diketahui. */
export function statusTerburuk(daftar: StatusTwin[]): StatusTwin {
  if (daftar.includes("kritis")) return "kritis";
  if (daftar.includes("perhatian")) return "perhatian";
  if (daftar.includes("normal")) return "normal";
  return "tidak_diketahui";
}

export function isiSlot(b: BarisTwin): number | null {
  const mx = n(b.maximum_stock);
  if (mx <= 0) return null;
  return Math.min(1, Math.max(0, n(b.quantity) / mx));
}

const KAP = UKURAN.slotPerTingkat * UKURAN.tingkat;

export function susunTataLetak(items: BarisTwin[]): TataLetak {
  const perKategori = new Map<string, BarisTwin[]>();
  for (const b of items) {
    const k = b.category_name;
    if (!perKategori.has(k)) perKategori.set(k, []);
    perKategori.get(k)!.push(b);
  }

  const lebarRak = UKURAN.slotW * UKURAN.slotPerTingkat;
  const tinggiRak = UKURAN.slotH * UKURAN.tingkat + UKURAN.papan;
  const rak: RakTwin[] = [];
  let no = 1;
  for (const [kategori, isi] of [...perKategori.entries()].sort((a, b) => a[0].localeCompare(b[0]))) {
    for (let mulai = 0; mulai < isi.length; mulai += KAP) {
      const potong = isi.slice(mulai, mulai + KAP);
      const slots: SlotTwin[] = potong.map((item, i) => {
        const tingkat = Math.floor(i / UKURAN.slotPerTingkat);
        const kolom = i % UKURAN.slotPerTingkat;
        return {
          item,
          tingkat,
          x: (kolom - (UKURAN.slotPerTingkat - 1) / 2) * UKURAN.slotW,
          y: tingkat * UKURAN.slotH + UKURAN.papan,
          isi: isiSlot(item),
        };
      });
      rak.push({
        id: `R${no}`,
        kode: `VR-${String(no).padStart(2, "0")}`,
        kategori,
        x: 0,
        z: 0,
        lebar: lebarRak,
        dalam: UKURAN.slotD,
        tinggi: tinggiRak,
        slots,
        status: statusTerburuk(slots.map((s) => s.item.status)),
      });
      no++;
    }
  }

  // Grid mendekati persegi; baris dipisah lorong.
  const kolom = Math.max(1, Math.ceil(Math.sqrt(rak.length * 1.6)));
  const baris = Math.ceil(rak.length / kolom) || 1;
  const stepX = lebarRak + UKURAN.jarakKolom;
  const stepZ = UKURAN.slotD + UKURAN.lorong;
  rak.forEach((r, i) => {
    r.x = ((i % kolom) - (kolom - 1) / 2) * stepX;
    r.z = (Math.floor(i / kolom) - (baris - 1) / 2) * stepZ;
  });
  return {
    rak,
    lebar: kolom * stepX + UKURAN.lorong,
    dalam: baris * stepZ + UKURAN.lorong,
    kolom,
    baris,
  };
}

export interface RingkasanTwin {
  sku: number;
  kuantitas: number;
  rak: number;
  perhatian: number;
  kritis: number;
  /** null bila TIDAK ADA barang yang punya stok maksimum */
  kapasitas: number | null;
  /** barang yang ikut dalam hitungan kapasitas */
  kapasitasDari: number;
}

export function ringkas(items: BarisTwin[], jumlahRak: number): RingkasanTwin {
  let kuantitas = 0, perhatian = 0, kritis = 0, sum = 0, mx = 0, dari = 0;
  for (const b of items) {
    kuantitas += n(b.quantity);
    if (b.status === "perhatian") perhatian++;
    if (b.status === "kritis") kritis++;
    if (n(b.maximum_stock) > 0) {
      // stok di atas maksimum tidak boleh menutupi barang lain: dipotong di 100%
      sum += Math.min(n(b.quantity), n(b.maximum_stock));
      mx += n(b.maximum_stock);
      dari++;
    }
  }
  return {
    sku: items.length,
    kuantitas,
    rak: jumlahRak,
    perhatian,
    kritis,
    kapasitas: mx > 0 ? sum / mx : null,
    kapasitasDari: dari,
  };
}

export function kapasitasRak(r: RakTwin): { persen: number | null; dari: number; dariTotal: number } {
  const r2 = ringkas(r.slots.map((s) => s.item), 1);
  return { persen: r2.kapasitas, dari: r2.kapasitasDari, dariTotal: r.slots.length };
}

export function hitungStatus(items: BarisTwin[]): Record<StatusTwin, number> {
  const h: Record<StatusTwin, number> = { normal: 0, perhatian: 0, kritis: 0, tidak_diketahui: 0 };
  for (const b of items) h[b.status]++;
  return h;
}

/* ------------------------------------------------------------------ */
/* Jalur kendaraan dan pekerja                                          */
/* ------------------------------------------------------------------ */

export type Titik = [number, number]; // [x, z]

export interface JalurGudang {
  /** garis tengah tiap lorong (z), dari yang terdepan; selalu baris + 1 buah */
  lorongZ: number[];
  /** koridor samping kiri/kanan (x), di luar deretan rak */
  koridorKiri: number;
  koridorKanan: number;
  /** rute tertutup forklift; berkelok melewati seluruh lorong */
  forklift: Titik[];
  /** titik henti forklift (indeks ke `forklift`) tempat garpu naik-turun */
  hentiForklift: number[];
  /** rute pekerja, masing-masing bolak-balik di satu lorong */
  pekerja: Titik[][];
}

const LEBAR_FORKLIFT = 1.1;

/**
 * Menurunkan jalur dari tata letak. SEMUANYA melewati ruang kosong: lorong
 * antar baris rak dan koridor di sisi luar. Pekerja dan forklift memakai jalur
 * lateral yang berbeda di lorong yang sama (forklift ke sisi -z, pekerja ke
 * sisi +z) sehingga tidak saling menembus.
 */
export function jalurGudang(tata: TataLetak): JalurGudang {
  const stepZ = UKURAN.slotD + UKURAN.lorong;
  const stepX = UKURAN.slotW * UKURAN.slotPerTingkat + UKURAN.jarakKolom;
  const ekstensiX = tata.kolom * stepX - UKURAN.jarakKolom;
  const koridorKanan = ekstensiX / 2 + 1.2;
  const koridorKiri = -koridorKanan;

  const zPertama = -((tata.baris - 1) / 2) * stepZ;
  // lorong di depan baris pertama, di antara baris, dan di belakang baris terakhir
  const lorongZ = Array.from({ length: tata.baris + 1 }, (_, i) => zPertama - stepZ / 2 + i * stepZ);

  const geserForklift = -0.45;
  const geserPekerja = 0.75;

  // serpentine melewati tiap lorong, lalu kembali lewat koridor sisi awal
  const fork: Titik[] = [];
  const henti: number[] = [];
  lorongZ.forEach((z, i) => {
    const [a, b] = i % 2 === 0 ? [koridorKiri, koridorKanan] : [koridorKanan, koridorKiri];
    const zz = z + geserForklift;
    fork.push([a, zz]);
    henti.push(fork.length); // henti di tengah lorong
    fork.push([(a + b) / 2, zz]);
    fork.push([b, zz]);
  });
  const sisiAkhir = fork[fork.length - 1][0];
  // kembali ke titik awal lewat koridor sisi akhir lalu sisi awal di luar lorong
  fork.push([sisiAkhir, lorongZ[0] + geserForklift]);

  const pekerja: Titik[][] = lorongZ.map((z) => [
    [koridorKiri + 1.5, z + geserPekerja],
    [koridorKanan - 1.5, z + geserPekerja],
  ]);
  return { lorongZ, koridorKiri, koridorKanan, forklift: fork, hentiForklift: henti, pekerja };
}

/** Panjang kumulatif sepanjang polyline tertutup/terbuka; dipakai untuk posisi per jarak. */
export function panjangJalur(titik: Titik[], tertutup: boolean): { kumulatif: number[]; total: number } {
  const kum = [0];
  const n = titik.length;
  const ruas = tertutup ? n : n - 1;
  for (let i = 0; i < ruas; i++) {
    const a = titik[i], b = titik[(i + 1) % n];
    kum.push(kum[i] + Math.hypot(b[0] - a[0], b[1] - a[1]));
  }
  return { kumulatif: kum, total: kum[kum.length - 1] };
}

/** Posisi dan arah (radian, 0 = +z) pada jarak `d` sepanjang jalur. */
export function posisiPadaJalur(
  titik: Titik[], kumulatif: number[], total: number, d: number, tertutup: boolean,
): { x: number; z: number; arah: number } {
  const n = titik.length;
  const dd = total > 0 ? ((d % total) + total) % total : 0;
  let i = 0;
  while (i < kumulatif.length - 2 && kumulatif[i + 1] < dd) i++;
  const a = titik[i], b = titik[(i + 1) % n];
  const len = kumulatif[i + 1] - kumulatif[i] || 1;
  const f = (dd - kumulatif[i]) / len;
  return {
    x: a[0] + (b[0] - a[0]) * f,
    z: a[1] + (b[1] - a[1]) * f,
    arah: Math.atan2(b[0] - a[0], b[1] - a[1]),
  };
}

/**
 * Jarak tempuh forklift pada waktu `t` (detik), dengan henti `tHenti` detik di
 * tiap titik henti. Murni, supaya dapat diuji tanpa WebGL.
 *
 * `henti` = jarak (meter) tiap titik henti, terurut. `indeks` adalah henti yang
 * sedang berlangsung (atau -1); `terakhir` adalah henti terakhir yang SUDAH
 * selesai (atau -1). Keduanya menentukan apakah garpu sedang membawa pallet.
 */
export function jarakForklift(
  t: number, total: number, v: number, henti: number[], tHenti: number,
): { d: number; indeks: number; terakhir: number; fase: number } {
  const siklus = total / v + henti.length * tHenti;
  let sisa = ((t % siklus) + siklus) % siklus;
  let prev = 0;
  for (let i = 0; i < henti.length; i++) {
    const tempuh = (henti[i] - prev) / v;
    if (sisa < tempuh) return { d: prev + v * sisa, indeks: -1, terakhir: i - 1, fase: 0 };
    sisa -= tempuh;
    if (sisa < tHenti) return { d: henti[i], indeks: i, terakhir: i - 1, fase: sisa / tHenti };
    sisa -= tHenti;
    prev = henti[i];
  }
  return { d: prev + v * sisa, indeks: -1, terakhir: henti.length - 1, fase: 0 };
}

/** Bolak-balik sepanjang `panjang` dengan jeda `jeda` detik di tiap ujung. */
export function jarakBolakBalik(
  t: number, panjang: number, v: number, jeda: number,
): { d: number; maju: boolean; diam: boolean } {
  const lintas = panjang / v;
  const siklus = 2 * (lintas + jeda);
  const s = ((t % siklus) + siklus) % siklus;
  if (s < lintas) return { d: s * v, maju: true, diam: false };
  if (s < lintas + jeda) return { d: panjang, maju: true, diam: true };
  if (s < 2 * lintas + jeda) return { d: panjang - (s - lintas - jeda) * v, maju: false, diam: false };
  return { d: 0, maju: false, diam: true };
}

/* ------------------------------------------------------------------ */
/* Dock penerimaan/pengeluaran, truk, dan forklift dock                 */
/* ------------------------------------------------------------------ */

/** Ukuran dock dalam meter; satu-satunya tempat angkanya ditetapkan. */
export const DOCK = {
  jarakDindingKeLorong: 8.0, // dinding dock ke garis lorong pertama
  pintuLebar: 3.4,
  pintuTinggi: 3.2,
  dindingTinggi: 8.5, // = GEDUNG.tinggi (bangunan.tsx)
  trailerPanjang: 7.4,
  trailerLebarDalam: 2.4,
  jalanDalam: 28,
  jumlahPalet: 3,
  jarakPalet: 1.15,
  lebarLantaiMin: 14,
} as const;

export type JenisBay = "terima" | "keluar";

export interface BayDock {
  x: number;
  jenis: JenisBay;
  /** detik; menggeser siklus agar kedua pintu tidak sibuk bersamaan */
  mulai: number;
}

export interface Dock {
  zDinding: number;
  /** z bagian belakang trailer saat berhenti (sedikit di luar dinding) */
  zTruk: number;
  zMaks: number;
  pusatZ: number;
  lebarLantai: number;
  /** panjang pandang yang perlu dibingkai kamera */
  bentang: number;
  bay: BayDock[];
}

export function layoutDock(tata: TataLetak): Dock {
  const j = jalurGudang(tata);
  const zDinding = j.lorongZ[0] - DOCK.jarakDindingKeLorong;
  const zMaks = tata.dalam / 2 + 1;
  const lebarLantai = Math.max(tata.lebar + 2, DOCK.lebarLantaiMin);
  const xb = Math.max(3.6, lebarLantai / 4);
  return {
    zDinding,
    zTruk: zDinding - 0.15,
    zMaks,
    pusatZ: (zDinding + zMaks) / 2,
    lebarLantai,
    bentang: Math.max(lebarLantai, zMaks - zDinding + 10),
    bay: [
      { x: -xb, jenis: "terima", mulai: 0 },
      { x: xb, jenis: "keluar", mulai: 20 },
    ],
  };
}

export const SIKLUS_TRUK = { datang: 8, muat: 18, pergi: 8, jeda: 6 } as const;
export type FaseTruk = "datang" | "muat" | "pergi" | "jeda";

export function fasaTruk(t: number, mulai: number): { fase: FaseTruk; f: number } {
  const T = SIKLUS_TRUK.datang + SIKLUS_TRUK.muat + SIKLUS_TRUK.pergi + SIKLUS_TRUK.jeda;
  let s = (((t + mulai) % T) + T) % T;
  for (const k of ["datang", "muat", "pergi", "jeda"] as const) {
    if (s < SIKLUS_TRUK[k]) return { fase: k, f: s / SIKLUS_TRUK[k] };
    s -= SIKLUS_TRUK[k];
  }
  return { fase: "jeda", f: 1 };
}

const mulus = (f: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, f)), 3);

/** Offset z truk dari titik berhenti (negatif = menjauh dari dinding). */
export function offsetTruk(fase: FaseTruk, f: number): number {
  const JAUH = -(DOCK.jalanDalam - 6);
  if (fase === "datang") return JAUH * (1 - mulus(f));
  if (fase === "pergi") return JAUH * mulus(f * f);
  return fase === "muat" ? 0 : JAUH;
}

/** Seberapa terbuka pintu, 0..1. Terbuka saat truk dekat atau sedang dimuat. */
export function bukaPintu(fase: FaseTruk, f: number): number {
  if (fase === "muat") return 1;
  if (fase === "datang") return Math.min(1, Math.max(0, (f - 0.55) / 0.3));
  if (fase === "pergi") return Math.min(1, Math.max(0, 1 - f / 0.3));
  return 0;
}

const Z_STAGING_PALET = 2.0; // dari dinding, ke arah gudang
const Z_BERDIRI_STAGING = 3.2; // forklift berdiri saat menjangkau pallet staging
const Z_MUNDUR = 4.8; // titik belok setelah mundur dari staging

/** z tengah pallet pada slot trailer `j` (0 = terdekat pintu). */
export function zPaletTrailer(d: Dock, j: number): number {
  return d.zDinding - 1.5 - j * DOCK.jarakPalet;
}
export function xSlotStaging(x: number, s: number): number {
  return x + (s - 1) * 1.35;
}
export function zPaletStaging(d: Dock): number {
  return d.zDinding + Z_STAGING_PALET;
}

function slotTrailer(jenis: JenisBay, trip: number): number {
  return jenis === "keluar" ? DOCK.jumlahPalet - 1 - trip : trip;
}

/** Rute satu perjalanan membawa pallet, dari tempat ambil ke tempat taruh. */
export function ruteBawa(d: Dock, bay: BayDock, trip: number): Titik[] {
  const s = trip;
  const j = slotTrailer(bay.jenis, trip);
  const xs = xSlotStaging(bay.x, s);
  const zStag = d.zDinding + Z_BERDIRI_STAGING;
  const zBelok = d.zDinding + Z_MUNDUR;
  const zTrail = zPaletTrailer(d, j) + 1.2;
  const staging: Titik[] = [[xs, zStag], [xs, zBelok], [bay.x, zBelok], [bay.x, zStag]];
  const trailer: Titik[] = [[bay.x, zTrail]];
  // keluar: staging -> trailer. terima: trailer -> staging (urutan dibalik)
  return bay.jenis === "keluar"
    ? [...staging, ...trailer]
    : [...trailer, ...[...staging].reverse()];
}

export interface PoseDock {
  x: number;
  z: number;
  /** radian; 0 = +z */
  arah: number;
  /** 0..1 tinggi garpu relatif */
  garpu: number;
  bawa: boolean;
  /** slot staging dan trailer yang terisi pallet */
  staging: boolean[];
  trailer: boolean[];
}

/**
 * Rute kembali (tanpa muatan) dari tempat taruh ke AWAL perjalanan berikutnya,
 * bukan ke awal perjalanan yang sama -- supaya forklift tidak melompat antar
 * perjalanan. Pada perjalanan terakhir, tujuannya awalnya sendiri.
 */
export function ruteBalik(d: Dock, bay: BayDock, trip: number): Titik[] {
  const r = ruteBawa(d, bay, trip).slice().reverse();
  const awalBerikut = ruteBawa(d, bay, Math.min(trip + 1, DOCK.jumlahPalet - 1))[0];
  if (bay.jenis === "keluar") {
    r[3] = [awalBerikut[0], r[3][1]];
    r[4] = awalBerikut;
  } else {
    r[r.length - 1] = awalBerikut;
  }
  return r;
}

/** Titik parkir forklift dock: di antara slot staging, menghadap dinding. */
export function titikParkir(d: Dock, bay: BayDock): Titik {
  return [bay.x, d.zDinding + Z_MUNDUR];
}

/** Rute dari titik parkir ke awal rute perjalanan `trip` (lurus pada sumbu). */
export function ruteMasuk(d: Dock, bay: BayDock, trip: number): Titik[] {
  const park = titikParkir(d, bay);
  const awal = ruteBawa(d, bay, trip)[0];
  return bay.jenis === "keluar"
    ? [park, [awal[0], park[1]], awal]
    : [park, awal];
}

const FRAC_MASUK = 0.1;
const FRAC_KELUAR = 0.1;

/**
 * Pose forklift dock dan isi pallet pada saat truk berada di fase `fase`,
 * kemajuan `f`. Murni: tidak menyentuh WebGL.
 *
 * Urutan pada fase "muat": masuk dari parkir, tiga perjalanan, keluar ke
 * parkir. Di luar fase itu forklift diam di parkir, sehingga posisinya
 * kontinu di seluruh siklus.
 */
export function kegiatanDock(d: Dock, bay: BayDock, fase: FaseTruk, f: number): PoseDock {
  const N = DOCK.jumlahPalet;
  const semua = (v: boolean) => Array.from({ length: N }, () => v);
  const park = titikParkir(d, bay);
  const keluarJenis = bay.jenis === "keluar";

  const isi = (fs: FaseTruk): { staging: boolean[]; trailer: boolean[] } => {
    if (fs === "jeda") return { staging: semua(false), trailer: semua(false) };
    // datang: keluar -> pallet siap di staging; terima -> truk datang bermuatan
    if (fs === "datang") return { staging: semua(keluarJenis), trailer: semua(!keluarJenis) };
    // pergi: keluar -> truk pergi bermuatan; terima -> staging berisi hasil bongkar
    return { staging: semua(!keluarJenis), trailer: semua(keluarJenis) };
  };

  if (fase !== "muat") {
    return { x: park[0], z: park[1], arah: Math.PI, garpu: 0, bawa: false, ...isi(fase) };
  }

  const jalur = (r: Titik[], s: number, balik: boolean) => {
    const { kumulatif, total } = panjangJalur(r, false);
    const p = posisiPadaJalur(r, kumulatif, total, (balik ? 1 - s : s) * total, false);
    return { x: p.x, z: p.z, arah: balik ? p.arah + Math.PI : p.arah };
  };

  if (f < FRAC_MASUK) {
    const p = jalur(ruteMasuk(d, bay, 0), f / FRAC_MASUK, false);
    return { ...p, garpu: 0, bawa: false, ...isi("datang") };
  }
  if (f >= 1 - FRAC_KELUAR) {
    const p = jalur(ruteMasuk(d, bay, N - 1), (f - (1 - FRAC_KELUAR)) / FRAC_KELUAR, true);
    return { ...p, garpu: 0, bawa: false, ...isi("pergi") };
  }

  const g = ((f - FRAC_MASUK) / (1 - FRAC_MASUK - FRAC_KELUAR)) * N;
  const trip = Math.min(N - 1, Math.floor(g));
  const u = g - trip;
  const rute = ruteBawa(d, bay, trip);
  const { kumulatif, total } = panjangJalur(rute, false);
  const awal = rute[0];
  const akhir = rute[rute.length - 1];

  let x = awal[0], z = awal[1], arah = Math.PI, garpu = 0, bawa = false;
  let sudahDiambil = false, sudahDitaruh = false;
  if (u < 0.1) {
    garpu = u / 0.1; bawa = u > 0.05; sudahDiambil = bawa;
  } else if (u < 0.55) {
    const s = (u - 0.1) / 0.45;
    const p = posisiPadaJalur(rute, kumulatif, total, s * total, false);
    x = p.x; z = p.z; garpu = 0.35; bawa = true; sudahDiambil = true;
    // ruas pertama ditempuh MUNDUR dengan muatan: garpu tetap menghadap -z
    // (seluruh ruas yang bergerak ke +z dengan muatan ditempuh mundur)
    arah = Math.abs(p.arah) < 0.1 ? Math.PI : p.arah;
  } else if (u < 0.65) {
    const v = (u - 0.55) / 0.1;
    x = akhir[0]; z = akhir[1]; garpu = 0.35 * (1 - v);
    bawa = v < 0.5; sudahDiambil = true; sudahDitaruh = !bawa;
    arah = Math.PI;
  } else {
    const s = (u - 0.65) / 0.35;
    const balik = ruteBalik(d, bay, trip);
    const kb = panjangJalur(balik, false);
    const p = posisiPadaJalur(balik, kb.kumulatif, kb.total, s * kb.total, false);
    x = p.x; z = p.z; garpu = 0; arah = p.arah; sudahDiambil = sudahDitaruh = true;
  }

  const staging = semua(false), trailer = semua(false);
  for (let i = 0; i < N; i++) {
    const j = slotTrailer(bay.jenis, i);
    const selesai = i < trip;
    const ini = i === trip;
    if (keluarJenis) {
      staging[i] = !selesai && !(ini && sudahDiambil);
      trailer[j] = selesai || (ini && sudahDitaruh);
    } else {
      trailer[j] = !selesai && !(ini && sudahDiambil);
      staging[i] = selesai || (ini && sudahDitaruh);
    }
  }
  return { x, z, arah, garpu, bawa, staging, trailer };
}

/* ------------------------------------------------------------------ */
/* Lapisan risiko                                                       */
/* ------------------------------------------------------------------ */

/**
 * Tiga lapisan, SEMUANYA dipinjam dari modul yang sudah ada -- tidak ada model
 * atau ambang baru di sini:
 *
 *   reorder  status mesin Pemesanan Ulang (sama dengan dasbor)
 *   habis    sisa hari stok menurut mesin yang sama, dibandingkan dengan
 *            horizon keputusannya sendiri (`habis_dalam_horizon` pada dasbor):
 *              <= horizon      kritis   (diproyeksikan habis dalam horizon)
 *              <= 2 x horizon  perhatian
 *              selebihnya      normal
 *   umur     Analisis Umur Pakai:
 *              PREMATURE  kritis    (diganti lebih cepat dari umur harapan)
 *              EXTENDED   perhatian (bertahan lebih lama dari umur harapan)
 *              NORMAL     normal
 *              selain itu tidak_diketahui (belum ada referensi / data kurang)
 *
 * "Berpotensi", bukan "akan": modul umur pakai sendiri tidak menyebut sebab
 * dan tidak meramalkan kerusakan, dan lapisan ini tidak boleh melampauinya.
 */
export type LapisRisiko = "reorder" | "habis" | "umur";
export const URUT_LAPIS: LapisRisiko[] = ["reorder", "habis", "umur"];

export function statusLapis(b: BarisTwin, lapis: LapisRisiko): StatusTwin {
  if (lapis === "reorder") return b.status;
  if (lapis === "habis") {
    const d = b.decision;
    if (!d || d.days_of_cover == null || !d.horizon_days) return "tidak_diketahui";
    if (d.days_of_cover <= d.horizon_days) return "kritis";
    if (d.days_of_cover <= 2 * d.horizon_days) return "perhatian";
    return "normal";
  }
  const u = b.lifetime;
  if (!u) return "tidak_diketahui";
  if (u.status === "PREMATURE") return "kritis";
  if (u.status === "EXTENDED") return "perhatian";
  if (u.status === "NORMAL") return "normal";
  return "tidak_diketahui";
}

/** Salinan barang dengan `status` diganti menurut lapisan; scene dan panel tak perlu tahu lapisan. */
export function terapkanLapis(items: BarisTwin[], lapis: LapisRisiko): BarisTwin[] {
  if (lapis === "reorder") return items;
  return items.map((b) => ({ ...b, status: statusLapis(b, lapis) }));
}

/** Horizon keputusan (hari) yang dipakai lapisan "habis"; diambil dari barang pertama yang punya keputusan. */
export function horizonHari(items: BarisTwin[]): number | null {
  for (const b of items) if (b.decision?.horizon_days) return b.decision.horizon_days;
  return null;
}
