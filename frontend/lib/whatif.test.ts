import { describe, expect, it } from "vitest";

import { adalahGalat, hitungRute } from "@/lib/picking";
import { BarisTwin, susunTataLetak } from "@/lib/twin";
import {
  barangBerpindah, bandingkan, biayaHarapan, bobotPrakiraan, buatPesananSimulasi, jarakSlot, penempatanAwal,
  terapkanPenempatan, tukar, usulanPenempatan,
} from "@/lib/whatif";

const dec = (f: number | null) => f == null ? null : ({
  status_label: "x", recommended_order_qty: null, days_of_cover: 30, effective_reorder_point: 1,
  available_stock: 1, forecast_usage: f, horizon_days: 14, priority_label: "x",
});
const b = (i: number, kat: string, f: number | null): BarisTwin => ({
  item_id: i, sku: `S${String(i).padStart(3, "0")}`, name: `Barang ${i}`, category_id: 1, category_name: kat,
  unit_code: "pcs", quantity: 20, reserved_quantity: 0, minimum_stock: 2, reorder_point: 5, maximum_stock: 40,
  status: "normal", decision: dec(f), lifetime: null,
});
// barang dengan permintaan tinggi sengaja berada di rak PALING JAUH (kategori terakhir secara alfabet)
const items = Array.from({ length: 36 }, (_, i) => b(i + 1, `K${String(Math.floor(i / 6)).padStart(2, "0")}`, i >= 30 ? 100 : 1));
const tata = susunTataLetak(items);
const awal = penempatanAwal(tata);
const { bobot } = bobotPrakiraan(items);

describe("penempatan", () => {
  it("penempatan awal memetakan tiap barang tepat sekali dan layoutnya identik", () => {
    expect(awal.size).toBe(items.length);
    const t = terapkanPenempatan(tata, awal);
    expect(t.rak.map((r) => r.slots.map((s) => s.item.item_id))).toEqual(tata.rak.map((r) => r.slots.map((s) => s.item.item_id)));
    expect(barangBerpindah(awal, awal).size).toBe(0);
  });
  it("tukar memindahkan dua barang saja, simetris, dan tidak mengubah masukan", () => {
    const salinan = new Map(awal);
    const p = tukar(awal, 1, 36);
    expect(barangBerpindah(awal, p)).toEqual(new Set([1, 36]));
    expect(p.get(1)).toEqual(awal.get(36));
    expect(p.get(36)).toEqual(awal.get(1));
    expect(awal).toEqual(salinan);
    expect(tukar(p, 1, 36)).toEqual(awal);
    expect(tukar(awal, 1, 1)).toEqual(awal);
  });
  it("terapkan: geometri slot tetap, tiap barang tepat sekali, data asal tidak berubah", () => {
    const sebelum = JSON.stringify(tata.rak.map((r) => r.slots.map((s) => s.item.item_id)));
    const t = terapkanPenempatan(tata, tukar(awal, 1, 36));
    expect(t.rak.map((r) => r.slots.map((s) => [s.x, s.y]))).toEqual(tata.rak.map((r) => r.slots.map((s) => [s.x, s.y])));
    const ids = t.rak.flatMap((r) => r.slots.map((s) => s.item.item_id)).sort((x, y) => x - y);
    expect(ids).toEqual(items.map((i) => i.item_id));
    expect(JSON.stringify(tata.rak.map((r) => r.slots.map((s) => s.item.item_id)))).toBe(sebelum);
  });
});

describe("usulan penempatan", () => {
  it("memetakan semua barang ke slot unik", () => {
    const u = usulanPenempatan(tata, items, bobot, 1);
    expect(u.size).toBe(items.length);
    expect(new Set([...u.values()].map((r) => `${r.rakId}|${r.idx}`)).size).toBe(items.length);
  });
  it("biaya harapan tidak pernah lebih buruk dari kondisi awal (ketidaksamaan penataan ulang)", () => {
    const u = usulanPenempatan(tata, items, bobot, 1);
    expect(biayaHarapan(tata, u, bobot, 1)).toBeLessThanOrEqual(biayaHarapan(tata, awal, bobot, 1) + 1e-9);
  });
  it("tidak ada penukaran acak yang mengalahkan usulan", () => {
    const u = usulanPenempatan(tata, items, bobot, 1);
    const terbaik = biayaHarapan(tata, u, bobot, 1);
    for (let a = 1; a <= 36; a += 5) for (let c = 2; c <= 36; c += 7) {
      expect(biayaHarapan(tata, tukar(u, a, c), bobot, 1)).toBeGreaterThanOrEqual(terbaik - 1e-9);
    }
  });
  it("barang paling laku mendapat slot terdekat dock", () => {
    const u = usulanPenempatan(tata, items, bobot, 1);
    const jarak = jarakSlot(tata, 1);
    const dJarak = (id: number) => jarak.get(`${u.get(id)!.rakId}|${u.get(id)!.idx}`)!;
    const min = Math.min(...[...u.keys()].map(dJarak));
    expect([31, 32, 33, 34, 35, 36].some((id) => dJarak(id) === min)).toBe(true);
  });
});

describe("pesanan simulasi", () => {
  const ids = items.map((i) => i.item_id);
  it("deterministik untuk seed yang sama dan berbeda untuk seed lain", () => {
    expect(buatPesananSimulasi(ids, bobot, 20, 5, 7)).toEqual(buatPesananSimulasi(ids, bobot, 20, 5, 7));
    expect(buatPesananSimulasi(ids, bobot, 20, 5, 7)).not.toEqual(buatPesananSimulasi(ids, bobot, 20, 5, 8));
  });
  it("tanpa barang ganda dalam satu pesanan dan jumlah baris sesuai", () => {
    for (const p of buatPesananSimulasi(ids, bobot, 50, 6, 3)) {
      expect(p).toHaveLength(6);
      expect(new Set(p.map((x) => x.itemId)).size).toBe(6);
    }
  });
  it("barang berbobot tinggi muncul jauh lebih sering", () => {
    const semua = buatPesananSimulasi(ids, bobot, 300, 4, 11).flat().map((x) => x.itemId);
    const tinggi = semua.filter((id) => id > 30).length / 6;
    const rendah = semua.filter((id) => id <= 30).length / 30;
    expect(tinggi).toBeGreaterThan(rendah * 3);
  });
  it("bobot tanpa prakiraan memakai bobot terkecil yang ada, bukan nol", () => {
    const x = [b(1, "A", 5), b(2, "A", null), b(3, "A", 9)];
    const r = bobotPrakiraan(x);
    expect(r.bobot.get(2)).toBe(5);
    expect(r.tanpaPrakiraan).toBe(1);
    expect(bobotPrakiraan(x, true).bobot.get(3)).toBe(1);
  });
});

describe("bandingkan", () => {
  const ids = items.map((i) => i.item_id);
  const pesanan = buatPesananSimulasi(ids, bobot, 40, 5, 42);
  it("skenario identik menghasilkan hasil identik (hemat 0)", () => {
    const e = bandingkan(tata, items, awal, pesanan, { bayAwal: 1, bayAkhir: 1 });
    expect(e.hemat).toBe(0);
    expect(e.berpindah).toBe(0);
    expect(e.skenario.jarakTotal).toBeCloseTo(e.awal.jarakTotal, 9);
    expect(e.awal.pesanan).toBe(40);
  });
  it("mendekatkan barang laku ke dock memperpendek rute rata-rata", () => {
    const u = usulanPenempatan(tata, items, bobot, 1);
    const e = bandingkan(tata, items, u, pesanan, { bayAwal: 1, bayAkhir: 1 });
    expect(e.skenario.jarakRata).toBeLessThan(e.awal.jarakRata);
    expect(e.hemat).toBeGreaterThan(0);
    expect(e.berpindah).toBeGreaterThan(0);
  });
  it("memindahkan barang laku menjauh dari dock memperburuk, dan itu dilaporkan negatif", () => {
    // kondisi awal sudah menaruh barang laku (31-36) jauh; tukar ke slot terdekat lalu balikkan arahnya
    const u = usulanPenempatan(tata, items, bobot, 1);
    const e = bandingkan(tata, items, awal, pesanan, { bayAwal: 1, bayAkhir: 1 });
    const balik = bandingkan(terapkanPenempatan(tata, u), items, awal, pesanan, { bayAwal: 1, bayAkhir: 1 });
    expect(e.hemat).toBe(0);
    expect(balik.hemat).toBeLessThan(0);
  });
  it("rute pesanan pengguna pada layout skenario memakai lokasi baru", () => {
    const u = usulanPenempatan(tata, items, bobot, 1);
    const t2 = terapkanPenempatan(tata, u);
    const pesan = [{ itemId: 36, qty: 1 }, { itemId: 35, qty: 1 }];
    const a = hitungRute({ tata, items, pesanan: pesan, bayAwal: 1, bayAkhir: 1 });
    const c = hitungRute({ tata: t2, items, pesanan: pesan, bayAwal: 1, bayAkhir: 1 });
    if (adalahGalat(a) || adalahGalat(c)) throw new Error("tak terduga");
    expect(c.jarak).toBeLessThan(a.jarak);
    expect(a.masukan.pesanan).toEqual(pesan);
  });
});
