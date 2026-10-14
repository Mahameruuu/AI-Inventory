/**
 * Optimizer rute picking untuk tata letak virtual gudang.
 *
 * APA YANG DIHITUNG, DAN DASARNYA
 *   Pengguna memilih barang + jumlah. Setiap barang berada pada satu slot rak
 *   VIRTUAL (lib/twin.ts: rak = kategori; skema belum menyimpan rak/bin), dan
 *   diambil dari lorong DI DEPAN rak itu (sisi menuju dock). Pekerja berjalan
 *   hanya pada graf lorong: lorong antar baris rak, dua koridor sisi, dan
 *   jalan pendek dari pintu dock. Rak tidak dapat ditembus.
 *
 * ALGORITMA
 *   1. Jarak terpendek antar titik pada graf (Dijkstra).
 *   2. Urutan kunjungan = soal TSP berujung tetap (awal dan akhir ditentukan):
 *        - sampai MAKS_EKSAK titik: Held-Karp, EKSAK -- optimal terhadap graf
 *          yang dimodelkan (bukan terhadap gudang fisik);
 *        - lebih banyak: tetangga terdekat + 2-opt + or-opt, HEURISTIK -- tidak
 *          dijamin optimal, dan hasilnya diberi label demikian.
 *   3. Pembanding: urutan sesuai yang dimasukkan pengguna.
 *
 * YANG TIDAK DIMODELKAN (dinyatakan di layar): tinggi tingkat rak, lalu lintas
 * forklift, kapasitas keranjang, aturan satu arah, dan waktu tunggu. Waktu =
 * jarak / kecepatan jalan + waktu per baris + waktu per unit; ketiga angkanya
 * ASUMSI yang dapat diubah pengguna, bukan hasil pengukuran.
 *
 * MURNI: tidak menyentuh stok, API, maupun WebGL. Menjalankannya tidak
 * mengubah apa pun.
 */

import {
  BarisTwin, Dock, TataLetak, Titik, jalurGudang, layoutDock, titikParkir,
} from "@/lib/twin";

export const MAKS_EKSAK = 12;

export interface Asumsi {
  /** meter per detik */
  kecepatan: number;
  detikPerBaris: number;
  detikPerUnit: number;
}
export const ASUMSI_BAWAAN: Asumsi = { kecepatan: 1.2, detikPerBaris: 15, detikPerUnit: 2 };

export interface Blokir {
  /** indeks lorong yang ditutup (0 = terdepan) */
  lorong: number[];
  koridorKiri: boolean;
  koridorKanan: boolean;
}
export const TANPA_BLOKIR: Blokir = { lorong: [], koridorKiri: false, koridorKanan: false };

export interface BarisPesanan { itemId: number; qty: number }

export interface LangkahRute {
  urut: number;
  itemId: number;
  sku: string;
  nama: string;
  qty: number;
  satuan: string;
  rakKode: string;
  /** posisi slot di dunia 3D: untuk penanda angka */
  slot: [number, number, number];
  /** jarak (m) dari titik sebelumnya sepanjang graf */
  jarakDari: number;
}

export interface RuteHitung {
  urutan: LangkahRute[];
  jalur: Titik[];
  jarak: number;
}

export interface HasilRute extends RuteHitung {
  pembanding: RuteHitung;
  /** pecahan 0..1 jarak yang dihemat dibanding pembanding; bisa 0 */
  hemat: number;
  metode: "eksak" | "heuristik";
  /** true hanya bila terbukti optimal pada graf (eksak) */
  optimal: boolean;
  waktu: { jalan: number; ambil: number; total: number };
  waktuPembanding: { jalan: number; ambil: number; total: number };
  asumsi: Asumsi;
  awal: Titik;
  akhir: Titik;
  /** masukan yang menghasilkan rute ini; dipakai menghitung ulang pada layout lain (what-if) */
  masukan: { pesanan: BarisPesanan[]; bayAwal: number; bayAkhir: number; blokir: Blokir; asumsi: Asumsi };
}

export interface Graf {
  titik: Titik[];
  tetangga: { ke: number; w: number }[][];
  kunci: Map<string, number>;
}

const r3 = (v: number) => Math.round(v * 1000) / 1000;
const kunci = (a: number | string, x: number) => `${a}|${r3(x).toFixed(3)}`;

/** Indeks baris rak (0 = terdepan) menurut z unik rak. */
export function barisRak(tata: TataLetak): Map<string, number> {
  const zs = [...new Set(tata.rak.map((r) => r3(r.z)))].sort((a, b) => a - b);
  return new Map(tata.rak.map((r) => [r.id, zs.indexOf(r3(r.z))]));
}

export function bangunGraf(tata: TataLetak, blokir: Blokir = TANPA_BLOKIR): Graf {
  const j = jalurGudang(tata);
  const dock: Dock = layoutDock(tata);
  const xs = new Set<number>([r3(j.koridorKiri), r3(j.koridorKanan)]);
  for (const r of tata.rak) for (const s of r.slots) xs.add(r3(r.x + s.x));
  for (const b of dock.bay) xs.add(r3(b.x));
  const xUrut = [...xs].sort((a, b) => a - b);

  const titik: Titik[] = [];
  const kunciMap = new Map<string, number>();
  const tambah = (k: string, t: Titik) => { kunciMap.set(k, titik.length); titik.push(t); return titik.length - 1; };
  j.lorongZ.forEach((z, k) => xUrut.forEach((x) => tambah(kunci(k, x), [x, z])));
  dock.bay.forEach((b, i) => tambah(`dock|${i}`, titikParkir(dock, b)));

  const tetangga: Graf["tetangga"] = titik.map(() => []);
  const sambung = (a: number, b: number) => {
    const w = Math.hypot(titik[a][0] - titik[b][0], titik[a][1] - titik[b][1]);
    tetangga[a].push({ ke: b, w }); tetangga[b].push({ ke: a, w });
  };
  const tutup = new Set(blokir.lorong);
  j.lorongZ.forEach((_, k) => {
    if (tutup.has(k)) return;
    for (let i = 0; i + 1 < xUrut.length; i++) sambung(kunciMap.get(kunci(k, xUrut[i]))!, kunciMap.get(kunci(k, xUrut[i + 1]))!);
  });
  const koridor: [number, boolean][] = [[j.koridorKiri, blokir.koridorKiri], [j.koridorKanan, blokir.koridorKanan]];
  for (const [x, tertutup] of koridor) {
    if (tertutup) continue;
    for (let k = 0; k + 1 < j.lorongZ.length; k++) sambung(kunciMap.get(kunci(k, x))!, kunciMap.get(kunci(k + 1, x))!);
  }
  dock.bay.forEach((b, i) => sambung(kunciMap.get(`dock|${i}`)!, kunciMap.get(kunci(0, b.x))!));
  return { titik, tetangga, kunci: kunciMap };
}

/** Dijkstra dari satu titik; O(V^2) cukup untuk ratusan titik. */
export function dijkstra(g: Graf, dari: number): { d: number[]; prev: number[] } {
  const n = g.titik.length;
  const d = Array<number>(n).fill(Infinity), prev = Array<number>(n).fill(-1), selesai = Array<boolean>(n).fill(false);
  d[dari] = 0;
  for (let it = 0; it < n; it++) {
    let u = -1;
    for (let i = 0; i < n; i++) if (!selesai[i] && (u < 0 || d[i] < d[u])) u = i;
    if (u < 0 || d[u] === Infinity) break;
    selesai[u] = true;
    for (const { ke, w } of g.tetangga[u]) if (d[u] + w < d[ke]) { d[ke] = d[u] + w; prev[ke] = u; }
  }
  return { d, prev };
}

function jalurDari(prev: number[], ke: number): number[] {
  const p: number[] = [];
  for (let v = ke; v >= 0; v = prev[v]) p.push(v);
  return p.reverse();
}

/** Held-Karp untuk jalur berujung tetap. D: [awal, stop..., akhir]. Mengembalikan urutan indeks stop (0-based). */
export function heldKarp(D: number[][], n: number): number[] {
  if (n === 0) return [];
  const N = 1 << n;
  const dp = Array.from({ length: N }, () => Array<number>(n).fill(Infinity));
  const dari = Array.from({ length: N }, () => Array<number>(n).fill(-1));
  for (let j = 0; j < n; j++) dp[1 << j][j] = D[0][j + 1];
  for (let m = 1; m < N; m++) for (let j = 0; j < n; j++) {
    if (!(m & (1 << j)) || dp[m][j] === Infinity) continue;
    for (let k = 0; k < n; k++) {
      if (m & (1 << k)) continue;
      const nm = m | (1 << k), c = dp[m][j] + D[j + 1][k + 1];
      if (c < dp[nm][k]) { dp[nm][k] = c; dari[nm][k] = j; }
    }
  }
  let best = Infinity, akhir = -1;
  for (let j = 0; j < n; j++) { const c = dp[N - 1][j] + D[j + 1][n + 1]; if (c < best) { best = c; akhir = j; } }
  const urut: number[] = [];
  for (let m = N - 1, j = akhir; j >= 0;) { urut.push(j); const p = dari[m][j]; m &= ~(1 << j); j = p; }
  return urut.reverse();
}

export function panjangUrutan(D: number[][], urut: number[], n: number): number {
  let t = 0, prev = 0;
  for (const j of urut) { t += D[prev][j + 1]; prev = j + 1; }
  return t + D[prev][n + 1];
}

/** Tetangga terdekat + 2-opt + or-opt; tidak dijamin optimal. */
export function heuristik(D: number[][], n: number): number[] {
  const sisa = new Set(Array.from({ length: n }, (_, i) => i));
  const urut: number[] = [];
  let kini = 0;
  while (sisa.size) {
    let b = -1;
    for (const j of sisa) if (b < 0 || D[kini][j + 1] < D[kini][b + 1]) b = j;
    urut.push(b); sisa.delete(b); kini = b + 1;
  }
  let membaik = true, lintasan = 0;
  while (membaik && lintasan++ < 100) {
    membaik = false;
    const cost = () => panjangUrutan(D, urut, n);
    let kini2 = cost();
    for (let i = 0; i < n - 1; i++) for (let k = i + 1; k < n; k++) { // 2-opt
      const cand = [...urut.slice(0, i), ...urut.slice(i, k + 1).reverse(), ...urut.slice(k + 1)];
      const c = panjangUrutan(D, cand, n);
      if (c + 1e-9 < kini2) { urut.splice(0, n, ...cand); kini2 = c; membaik = true; }
    }
    for (let i = 0; i < n; i++) for (let k = 0; k < n; k++) { // or-opt: pindahkan satu titik
      if (i === k) continue;
      const cand = [...urut]; const [x] = cand.splice(i, 1); cand.splice(k, 0, x);
      const c = panjangUrutan(D, cand, n);
      if (c + 1e-9 < kini2) { urut.splice(0, n, ...cand); kini2 = c; membaik = true; }
    }
  }
  return urut;
}

export interface Galat { jenis: "kosong" | "tak_terjangkau" | "tak_dikenal"; pesan: string; itemIds?: number[] }

/** Stok tersedia = jumlah - tercadang (angka yang sama dengan yang dipakai mesin). */
export function stokTersedia(b: BarisTwin): number {
  return Math.max(0, Number(b.quantity) - Number(b.reserved_quantity));
}

/** Pemeriksaan pesanan SEBELUM dihitung; mengembalikan daftar masalah per item. */
export interface MasalahPesanan { itemId: number; kode: "tak_ada" | "jumlah" | "lebih"; maks?: number }

export function periksaPesanan(baris: BarisPesanan[], items: BarisTwin[]): MasalahPesanan[] {
  const peta = new Map(items.map((b) => [b.item_id, b]));
  const out: MasalahPesanan[] = [];
  for (const p of baris) {
    const b = peta.get(p.itemId);
    if (!b) { out.push({ itemId: p.itemId, kode: "tak_ada" }); continue; }
    if (!(p.qty > 0)) out.push({ itemId: p.itemId, kode: "jumlah" });
    else if (p.qty > stokTersedia(b) + 1e-9) out.push({ itemId: p.itemId, kode: "lebih", maks: stokTersedia(b) });
  }
  return out;
}

export interface Masukan {
  tata: TataLetak;
  items: BarisTwin[];
  pesanan: BarisPesanan[];
  /** indeks bay dock (lihat layoutDock) sebagai titik awal dan akhir */
  bayAwal: number;
  bayAkhir: number;
  blokir?: Blokir;
  asumsi?: Asumsi;
}

export function hitungRute(m: Masukan): HasilRute | Galat {
  const asumsi = m.asumsi ?? ASUMSI_BAWAAN;
  const pesanan = m.pesanan.filter((p) => p.qty > 0);
  if (!pesanan.length) return { jenis: "kosong", pesan: "Pilih minimal satu barang" };

  const g = bangunGraf(m.tata, m.blokir ?? TANPA_BLOKIR);
  const baris = barisRak(m.tata);
  const peta = new Map(m.items.map((b) => [b.item_id, b]));
  const lokasi = new Map<number, { rak: string; kode: string; slot: [number, number, number]; node: number }>();
  for (const r of m.tata.rak) for (const s of r.slots) {
    const k = baris.get(r.id)!;
    const node = g.kunci.get(kunci(k, r.x + s.x));
    if (node !== undefined) lokasi.set(s.item.item_id, { rak: r.id, kode: r.kode, slot: [r.x + s.x, s.y + 0.55, r.z], node });
  }

  const tidakAda = pesanan.filter((p) => !lokasi.has(p.itemId) || !peta.has(p.itemId)).map((p) => p.itemId);
  if (tidakAda.length) return { jenis: "tak_dikenal", pesan: "Ada barang yang tidak punya lokasi di tata letak", itemIds: tidakAda };

  const nAwal = g.kunci.get(`dock|${m.bayAwal}`)!, nAkhir = g.kunci.get(`dock|${m.bayAkhir}`)!;
  const stop = pesanan.map((p) => ({ ...p, ...lokasi.get(p.itemId)! }));
  const simpul = [nAwal, ...stop.map((s) => s.node), nAkhir];
  const sp = simpul.map((s) => dijkstra(g, s));
  const D = simpul.map((_, i) => simpul.map((__, j) => sp[i].d[simpul[j]]));
  const n = stop.length;

  const tak = stop.filter((_, i) => !Number.isFinite(D[0][i + 1]) || !Number.isFinite(D[i + 1][n + 1]));
  if (tak.length) return { jenis: "tak_terjangkau", pesan: "Barang tak terjangkau dari titik awal/akhir dengan lorong yang tersedia", itemIds: tak.map((s) => s.itemId) };

  const eksak = n <= MAKS_EKSAK;
  const urutOpt = eksak ? heldKarp(D, n) : heuristik(D, n);
  const urutAsal = stop.map((_, i) => i);

  const susun = (urut: number[]): RuteHitung => {
    const simpulJalur: number[] = [nAwal];
    const urutan: LangkahRute[] = [];
    let prev = 0, total = 0;
    urut.forEach((j, i) => {
      simpulJalur.push(...jalurDari(sp[prev].prev, simpul[j + 1]).slice(1));
      const s = stop[j], b = peta.get(s.itemId)!;
      const dj = D[prev][j + 1];
      total += dj;
      urutan.push({ urut: i + 1, itemId: s.itemId, sku: b.sku, nama: b.name, qty: s.qty, satuan: b.unit_code, rakKode: s.kode, slot: s.slot, jarakDari: dj });
      prev = j + 1;
    });
    simpulJalur.push(...jalurDari(sp[prev].prev, nAkhir).slice(1));
    total += D[prev][n + 1];
    // buang titik berulang berurutan
    const jalur: Titik[] = [];
    for (const v of simpulJalur) {
      const t = g.titik[v], l = jalur[jalur.length - 1];
      if (!l || Math.abs(l[0] - t[0]) > 1e-6 || Math.abs(l[1] - t[1]) > 1e-6) jalur.push(t);
    }
    return { urutan, jalur, jarak: total };
  };
  const awalXZ = g.titik[nAwal], akhirXZ = g.titik[nAkhir];
  const opt = susun(urutOpt), asal = susun(urutAsal);

  const waktu = (r: RuteHitung) => {
    const jalan = r.jarak / asumsi.kecepatan;
    const ambil = r.urutan.reduce((a, l) => a + asumsi.detikPerBaris + asumsi.detikPerUnit * l.qty, 0);
    return { jalan, ambil, total: jalan + ambil };
  };
  // pembanding tidak boleh lebih baik dari hasil eksak; pada heuristik, pakai yang terpendek dari keduanya
  const terbaik = !eksak && asal.jarak < opt.jarak ? asal : opt;
  return {
    ...terbaik,
    pembanding: asal,
    hemat: asal.jarak > 0 ? Math.max(0, (asal.jarak - terbaik.jarak) / asal.jarak) : 0,
    metode: eksak ? "eksak" : "heuristik",
    optimal: eksak,
    waktu: waktu(terbaik),
    waktuPembanding: waktu(asal),
    asumsi,
    awal: awalXZ,
    akhir: akhirXZ,
    masukan: { pesanan, bayAwal: m.bayAwal, bayAkhir: m.bayAkhir, blokir: m.blokir ?? TANPA_BLOKIR, asumsi },
  };
}

export const adalahGalat = (h: HasilRute | Galat): h is Galat => "jenis" in h;

/** Contoh pesanan DEMO yang tersebar di rak; deterministik, hanya barang yang punya stok tersedia. */
export function contohPesanan(items: BarisTwin[], tata: TataLetak, n = 6): BarisPesanan[] {
  const ada = new Set<number>();
  const kandidat: BarisTwin[] = [];
  for (const r of tata.rak) for (const s of r.slots) {
    const b = items.find((x) => x.item_id === s.item.item_id);
    if (b && stokTersedia(b) > 0 && !ada.has(b.item_id)) { ada.add(b.item_id); kandidat.push(b); }
  }
  if (kandidat.length <= n) return kandidat.map((b) => ({ itemId: b.item_id, qty: Math.min(2, stokTersedia(b)) }));
  const langkah = kandidat.length / n;
  // urutan sengaja diacak deterministik: pembanding "urutan masuk" mewakili pesanan nyata yang tak terurut
  const pilih = Array.from({ length: n }, (_, i) => kandidat[Math.floor(i * langkah + (i % 2 ? langkah / 2 : 0))]);
  return pilih.map((b, i) => ({ itemId: b.item_id, qty: Math.min(1 + (i % 3), stokTersedia(b)) }))
    .sort((a, b) => ((a.itemId * 7919) % 101) - ((b.itemId * 7919) % 101));
}

