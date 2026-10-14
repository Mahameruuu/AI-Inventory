/**
 * What-if penempatan barang di layout virtual.
 *
 * SANDBOX MURNI. Skenario hanyalah pemetaan barang -> slot yang dihitung di
 * browser; tidak ada yang ditulis ke stok, transaksi, maupun lokasi. Layoutnya
 * sendiri virtual (rak = kategori), jadi hasilnya menjawab "bagaimana bila
 * barang ini ditaruh lebih dekat ke dock", BUKAN "berapa yang akan dihemat di
 * gudang fisik".
 *
 * Skenario hanya MENUKAR barang di antara slot yang sudah ada: jumlah slot dan
 * isi tiap rak tetap, sehingga kapasitas tidak pernah dilanggar.
 *
 * BEBAN KERJA UJI adalah pesanan simulasi: tiap pesanan memilih beberapa
 * barang berbeda, peluangnya sebanding dengan prakiraan permintaan mesin
 * Pemesanan Ulang (seragam bila tak ada prakiraan), dari PRNG ber-seed. PESANAN
 * YANG SAMA dipakai untuk kondisi awal dan skenario (perbandingan berpasangan),
 * dan jumlah per baris tetap 1 supaya waktu ambil tidak mengaburkan jarak.
 */

import {
  ASUMSI_BAWAAN, Asumsi, BarisPesanan, Blokir, TANPA_BLOKIR, adalahGalat, bangunGraf, dijkstra, hitungRute,
  barisRak,
} from "@/lib/picking";
import { BarisTwin, TataLetak, isiSlot, layoutDock, statusTerburuk } from "@/lib/twin";

export interface SlotRef { rakId: string; idx: number }
/** Pemetaan LENGKAP barang -> slot. */
export type Penempatan = Map<number, SlotRef>;

export function penempatanAwal(tata: TataLetak): Penempatan {
  const p: Penempatan = new Map();
  for (const r of tata.rak) r.slots.forEach((s, idx) => p.set(s.item.item_id, { rakId: r.id, idx }));
  return p;
}

const sama = (a: SlotRef, b: SlotRef) => a.rakId === b.rakId && a.idx === b.idx;

/** Barang yang slotnya berbeda dari kondisi awal. */
export function barangBerpindah(awal: Penempatan, skenario: Penempatan): Set<number> {
  const out = new Set<number>();
  for (const [id, ref] of skenario) { const a = awal.get(id); if (!a || !sama(a, ref)) out.add(id); }
  return out;
}

/** Menukar posisi dua barang; mengembalikan pemetaan baru (yang lama tidak diubah). */
export function tukar(p: Penempatan, a: number, b: number): Penempatan {
  const n = new Map(p);
  const sa = p.get(a), sb = p.get(b);
  if (!sa || !sb || a === b) return n;
  n.set(a, sb); n.set(b, sa);
  return n;
}

/** Salinan tata letak dengan barang dipindah menurut pemetaan; geometri slot tetap. */
export function terapkanPenempatan(tata: TataLetak, p: Penempatan): TataLetak {
  const barang = new Map<number, BarisTwin>();
  for (const r of tata.rak) for (const s of r.slots) barang.set(s.item.item_id, s.item);
  const dihuni = new Map<string, number>(); // "rakId|idx" -> itemId
  for (const [id, ref] of p) dihuni.set(`${ref.rakId}|${ref.idx}`, id);
  const rak = tata.rak.map((r) => {
    const slots = r.slots.map((s, idx) => {
      const id = dihuni.get(`${r.id}|${idx}`);
      const item = (id !== undefined ? barang.get(id) : undefined) ?? s.item;
      return { ...s, item, isi: isiSlot(item) };
    });
    return { ...r, slots, status: statusTerburuk(slots.map((s) => s.item.status)) };
  });
  return { ...tata, rak };
}

export type Bobot = Map<number, number>;

/** Bobot permintaan per barang: prakiraan pemakaian mesin; tanpa prakiraan = seragam. */
export function bobotPrakiraan(items: BarisTwin[], seragam = false): { bobot: Bobot; tanpaPrakiraan: number } {
  const bobot: Bobot = new Map();
  let tanpa = 0;
  const positif = items.map((b) => b.decision?.forecast_usage ?? 0).filter((v) => v > 0);
  const lantai = positif.length ? Math.min(...positif) : 1; // tanpa prakiraan: bobot terkecil yang ada, bukan nol
  for (const b of items) {
    const f = b.decision?.forecast_usage;
    if (seragam || f == null || !(f > 0)) { bobot.set(b.item_id, seragam ? 1 : lantai); if (!seragam) tanpa++; }
    else bobot.set(b.item_id, f);
  }
  return { bobot, tanpaPrakiraan: seragam ? 0 : tanpa };
}

/** Jarak lorong dari dock ke tiap slot; slot yang tak terjangkau diberi Infinity. */
export function jarakSlot(tata: TataLetak, bayIdx: number, blokir: Blokir = TANPA_BLOKIR): Map<string, number> {
  const g = bangunGraf(tata, blokir);
  const { d } = dijkstra(g, g.kunci.get(`dock|${bayIdx}`)!);
  const baris = barisRak(tata);
  const out = new Map<string, number>();
  for (const r of tata.rak) for (let idx = 0; idx < r.slots.length; idx++) {
    const x = Math.round((r.x + r.slots[idx].x) * 1000) / 1000;
    const node = g.kunci.get(`${baris.get(r.id)}|${x.toFixed(3)}`);
    out.set(`${r.id}|${idx}`, node === undefined ? Infinity : d[node]);
  }
  return out;
}

/**
 * Usulan penempatan: barang berbobot terbesar ke slot terdekat dock. Dengan
 * ketidaksamaan penataan ulang, ini meminimalkan jumlah (bobot x jarak dock-slot)
 * di antara semua penukaran slot.
 */
export function usulanPenempatan(tata: TataLetak, items: BarisTwin[], bobot: Bobot, bayIdx: number, blokir: Blokir = TANPA_BLOKIR): Penempatan {
  const jarak = jarakSlot(tata, bayIdx, blokir);
  const slot: SlotRef[] = [];
  for (const r of tata.rak) r.slots.forEach((_, idx) => slot.push({ rakId: r.id, idx }));
  slot.sort((a, b) => (jarak.get(`${a.rakId}|${a.idx}`)! - jarak.get(`${b.rakId}|${b.idx}`)!) || a.rakId.localeCompare(b.rakId) || a.idx - b.idx);
  const ada = new Set(slot.length ? [...penempatanAwal(tata).keys()] : []);
  const urut = items.filter((b) => ada.has(b.item_id))
    .sort((a, b) => ((bobot.get(b.item_id) ?? 0) - (bobot.get(a.item_id) ?? 0)) || a.sku.localeCompare(b.sku));
  const p: Penempatan = new Map();
  urut.forEach((b, i) => p.set(b.item_id, slot[i]));
  return p;
}

/** Biaya harapan satu pengambilan tunggal: sum(bobot x jarak dock-slot). */
export function biayaHarapan(tata: TataLetak, p: Penempatan, bobot: Bobot, bayIdx: number): number {
  const jarak = jarakSlot(tata, bayIdx);
  let t = 0;
  for (const [id, ref] of p) t += (bobot.get(id) ?? 0) * jarak.get(`${ref.rakId}|${ref.idx}`)!;
  return t;
}

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Pesanan simulasi: deterministik untuk seed yang sama, tanpa barang ganda dalam satu pesanan. */
export function buatPesananSimulasi(
  ids: number[], bobot: Bobot, jumlah: number, barisPerPesanan: number, seed: number,
): BarisPesanan[][] {
  const rnd = mulberry32(seed);
  const k = Math.min(barisPerPesanan, ids.length);
  const out: BarisPesanan[][] = [];
  for (let o = 0; o < jumlah; o++) {
    const sisa = [...ids];
    const pesan: BarisPesanan[] = [];
    for (let i = 0; i < k; i++) {
      const total = sisa.reduce((a, id) => a + (bobot.get(id) ?? 0), 0);
      let r = rnd() * total, pilih = 0;
      for (let j = 0; j < sisa.length; j++) { r -= bobot.get(sisa[j]) ?? 0; if (r <= 0) { pilih = j; break; } pilih = j; }
      pesan.push({ itemId: sisa[pilih], qty: 1 });
      sisa.splice(pilih, 1);
    }
    out.push(pesan);
  }
  return out;
}

export interface RingkasanLayout {
  pesanan: number;
  gagal: number;
  jarakTotal: number;
  jarakRata: number;
  waktuRata: number;
}

export interface Evaluasi {
  awal: RingkasanLayout;
  skenario: RingkasanLayout;
  /** pecahan 0..1 penghematan jarak rata-rata; negatif bila skenario lebih buruk */
  hemat: number;
  berpindah: number;
}

function ringkasLayout(
  tata: TataLetak, items: BarisTwin[], pesanan: BarisPesanan[][], bayAwal: number, bayAkhir: number,
  blokir: Blokir, asumsi: Asumsi,
): RingkasanLayout {
  let jarak = 0, waktu = 0, ok = 0, gagal = 0;
  for (const p of pesanan) {
    const h = hitungRute({ tata, items, pesanan: p, bayAwal, bayAkhir, blokir, asumsi });
    if (adalahGalat(h)) { gagal++; continue; }
    jarak += h.jarak; waktu += h.waktu.total; ok++;
  }
  return { pesanan: ok, gagal, jarakTotal: jarak, jarakRata: ok ? jarak / ok : 0, waktuRata: ok ? waktu / ok : 0 };
}

/** Membandingkan kondisi awal dan skenario pada pesanan yang SAMA. */
export function bandingkan(
  tata: TataLetak, items: BarisTwin[], skenario: Penempatan, pesanan: BarisPesanan[][],
  opsi: { bayAwal: number; bayAkhir: number; blokir?: Blokir; asumsi?: Asumsi },
): Evaluasi {
  const blokir = opsi.blokir ?? TANPA_BLOKIR, asumsi = opsi.asumsi ?? ASUMSI_BAWAAN;
  const tataSkenario = terapkanPenempatan(tata, skenario);
  const awal = ringkasLayout(tata, items, pesanan, opsi.bayAwal, opsi.bayAkhir, blokir, asumsi);
  const sken = ringkasLayout(tataSkenario, items, pesanan, opsi.bayAwal, opsi.bayAkhir, blokir, asumsi);
  return {
    awal, skenario: sken,
    hemat: awal.jarakRata > 0 ? (awal.jarakRata - sken.jarakRata) / awal.jarakRata : 0,
    berpindah: barangBerpindah(penempatanAwal(tata), skenario).size,
  };
}

export const bayKeluar = (tata: TataLetak): number =>
  Math.max(0, layoutDock(tata).bay.findIndex((b) => b.jenis === "keluar"));
