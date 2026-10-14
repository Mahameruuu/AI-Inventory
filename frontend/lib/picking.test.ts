import { describe, expect, it } from "vitest";

import {
  ASUMSI_BAWAAN, MAKS_EKSAK, adalahGalat, bangunGraf, contohPesanan, dijkstra, heldKarp, heuristik,
  hitungRute, panjangUrutan, periksaPesanan, stokTersedia,
} from "@/lib/picking";
import { BarisTwin, susunTataLetak } from "@/lib/twin";

const b = (i: number, kat: string, over: Partial<BarisTwin> = {}): BarisTwin => ({
  item_id: i, sku: `S${i}`, name: `Barang ${i}`, category_id: 1, category_name: kat,
  unit_code: "pcs", quantity: 20, reserved_quantity: 2, minimum_stock: 2,
  reorder_point: 5, maximum_stock: 40, status: "normal", decision: null, lifetime: null, ...over,
});
const items = Array.from({ length: 40 }, (_, i) => b(i + 1, `K${i % 7}`));
const tata = susunTataLetak(items);

const permutasi = (a: number[]): number[][] =>
  a.length <= 1 ? [a] : a.flatMap((x, i) => permutasi([...a.slice(0, i), ...a.slice(i + 1)]).map((p) => [x, ...p]));

const panjangPoli = (j: [number, number][]) =>
  j.slice(1).reduce((s, p, i) => s + Math.hypot(p[0] - j[i][0], p[1] - j[i][1]), 0);

const tembusRak = (x: number, z: number, margin = 0.1) =>
  tata.rak.some((r) => Math.abs(x - r.x) < r.lebar / 2 + margin && Math.abs(z - r.z) < r.dalam / 2 + margin);

describe("graf dan jarak", () => {
  it("seluruh titik terhubung bila tidak ada yang ditutup", () => {
    const g = bangunGraf(tata);
    const { d } = dijkstra(g, 0);
    expect(d.every(Number.isFinite)).toBe(true);
  });
  it("jarak graf tidak pernah lebih pendek dari garis lurus", () => {
    const g = bangunGraf(tata);
    const { d } = dijkstra(g, 0);
    d.forEach((v, i) => expect(v + 1e-9).toBeGreaterThanOrEqual(Math.hypot(g.titik[i][0] - g.titik[0][0], g.titik[i][1] - g.titik[0][1])));
  });
});

describe("pemecah urutan", () => {
  // matriks jarak dari graf sungguhan: 6 stop acak
  const pilih = [3, 11, 17, 25, 31, 38];
  const g = bangunGraf(tata);
  const baris = new Map(tata.rak.map((r) => [r.id, r]));
  void baris;
  const simpul = [0, ...pilih.map((_, i) => 5 + i * 7), 1];
  const sp = simpul.map((s) => dijkstra(g, s));
  const D = simpul.map((_, i) => simpul.map((__, j) => sp[i].d[simpul[j]]));
  const n = pilih.length;

  it("Held-Karp sama dengan pencarian lengkap", () => {
    const hk = panjangUrutan(D, heldKarp(D, n), n);
    const brute = Math.min(...permutasi([...Array(n).keys()]).map((p) => panjangUrutan(D, p, n)));
    expect(hk).toBeCloseTo(brute, 9);
  });
  it("heuristik valid dan tidak lebih baik dari eksak", () => {
    const h = heuristik(D, n);
    expect([...h].sort()).toEqual([...Array(n).keys()]);
    expect(panjangUrutan(D, h, n) + 1e-9).toBeGreaterThanOrEqual(panjangUrutan(D, heldKarp(D, n), n));
  });
  it("n=0 menghasilkan urutan kosong", () => {
    expect(heldKarp(D, 0)).toEqual([]);
  });
});

describe("hitungRute", () => {
  const pesan = (ids: number[]) => ids.map((id) => ({ itemId: id, qty: 2 }));
  const hitung = (ids: number[], extra = {}) =>
    hitungRute({ tata, items, pesanan: pesan(ids), bayAwal: 1, bayAkhir: 1, ...extra });

  it("urutan memuat tiap barang tepat sekali dan jarak sama dengan panjang jalur", () => {
    const h = hitung([4, 29, 12, 35, 7, 21]);
    if (adalahGalat(h)) throw new Error(h.pesan);
    expect(h.urutan.map((l) => l.itemId).sort((a, c) => a - c)).toEqual([4, 7, 12, 21, 29, 35]);
    expect(panjangPoli(h.jalur)).toBeCloseTo(h.jarak, 6);
    expect(h.metode).toBe("eksak");
    expect(h.optimal).toBe(true);
  });
  it("eksak tidak pernah lebih panjang dari urutan masuk dan hemat konsisten", () => {
    const h = hitung([35, 4, 29, 7, 12, 21]);
    if (adalahGalat(h)) throw new Error(h.pesan);
    expect(h.jarak).toBeLessThanOrEqual(h.pembanding.jarak + 1e-9);
    expect(h.hemat).toBeCloseTo(1 - h.jarak / h.pembanding.jarak, 9);
  });
  it("jalur tidak pernah menembus rak", () => {
    const h = hitung([4, 29, 12, 35, 7, 21, 18, 39]);
    if (adalahGalat(h)) throw new Error(h.pesan);
    for (const rute of [h.jalur, h.pembanding.jalur]) {
      for (let i = 1; i < rute.length; i++) {
        const [a, c] = [rute[i - 1], rute[i]];
        const L = Math.hypot(c[0] - a[0], c[1] - a[1]);
        for (let t = 0; t <= L; t += 0.2) {
          const f = L ? t / L : 0;
          expect(tembusRak(a[0] + (c[0] - a[0]) * f, a[1] + (c[1] - a[1]) * f)).toBe(false);
        }
      }
    }
  });
  it("lebih dari batas eksak memakai heuristik dan diberi label tidak optimal", () => {
    const ids = Array.from({ length: MAKS_EKSAK + 3 }, (_, i) => i + 1);
    const h = hitung(ids);
    if (adalahGalat(h)) throw new Error(h.pesan);
    expect(h.metode).toBe("heuristik");
    expect(h.optimal).toBe(false);
    expect(h.jarak).toBeLessThanOrEqual(h.pembanding.jarak + 1e-9);
    expect(h.urutan).toHaveLength(ids.length);
  });
  it("waktu = jarak/kecepatan + waktu ambil dari asumsi", () => {
    const h = hitung([4, 29]);
    if (adalahGalat(h)) throw new Error(h.pesan);
    expect(h.waktu.jalan).toBeCloseTo(h.jarak / ASUMSI_BAWAAN.kecepatan, 9);
    expect(h.waktu.ambil).toBe(2 * (ASUMSI_BAWAAN.detikPerBaris + ASUMSI_BAWAAN.detikPerUnit * 2));
    expect(h.waktu.total).toBeCloseTo(h.waktu.jalan + h.waktu.ambil, 9);
  });
  it("koridor ditutup memperpanjang atau mempertahankan jarak, tidak memperpendek", () => {
    const a = hitung([4, 29, 12, 35, 7, 21]);
    const c = hitung([4, 29, 12, 35, 7, 21], { blokir: { lorong: [], koridorKiri: true, koridorKanan: false } });
    if (adalahGalat(a) || adalahGalat(c)) throw new Error("tak terduga");
    expect(c.jarak + 1e-9).toBeGreaterThanOrEqual(a.jarak);
  });
  it("lorong terdepan ditutup membuat dock tak terhubung dan dilaporkan jelas", () => {
    const h = hitung([4, 29], { blokir: { lorong: [0], koridorKiri: false, koridorKanan: false } });
    expect(adalahGalat(h)).toBe(true);
    if (adalahGalat(h)) { expect(h.jenis).toBe("tak_terjangkau"); expect(h.itemIds!.length).toBeGreaterThan(0); }
  });
  it("pesanan kosong dan barang tak dikenal ditolak", () => {
    const k = hitungRute({ tata, items, pesanan: [], bayAwal: 1, bayAkhir: 1 });
    expect(adalahGalat(k) && k.jenis).toBe("kosong");
    const t = hitungRute({ tata, items, pesanan: [{ itemId: 9999, qty: 1 }], bayAwal: 1, bayAkhir: 1 });
    expect(adalahGalat(t) && t.jenis).toBe("tak_dikenal");
  });
});

describe("validasi dan contoh", () => {
  it("jumlah melebihi stok tersedia ditandai", () => {
    expect(stokTersedia(b(1, "A"))).toBe(18);
    const m = periksaPesanan([{ itemId: 1, qty: 19 }, { itemId: 2, qty: 0 }, { itemId: 3, qty: 18 }, { itemId: 99, qty: 1 }], items);
    expect(m.map((x) => x.itemId).sort((a, c) => a - c)).toEqual([1, 2, 99]);
  });
  it("contoh pesanan valid, deterministik, dan tanpa duplikat", () => {
    const c1 = contohPesanan(items, tata), c2 = contohPesanan(items, tata);
    expect(c1).toEqual(c2);
    expect(new Set(c1.map((x) => x.itemId)).size).toBe(c1.length);
    expect(periksaPesanan(c1, items)).toEqual([]);
    expect(adalahGalat(hitungRute({ tata, items, pesanan: c1, bayAwal: 1, bayAkhir: 1 }))).toBe(false);
  });
});
