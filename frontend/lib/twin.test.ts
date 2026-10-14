import { describe, expect, it } from "vitest";

import { BarisTwin, UKURAN, isiSlot, DOCK, SIKLUS_TRUK, bukaPintu, fasaTruk, jalurGudang, jarakBolakBalik, kegiatanDock, layoutDock, offsetTruk, ruteBalik, ruteBawa, jarakForklift, panjangJalur, posisiPadaJalur, kapasitasRak, ringkas, statusTerburuk, susunTataLetak } from "@/lib/twin";

const b = (i: number, kat: string, over: Partial<BarisTwin> = {}): BarisTwin => ({
  item_id: i, sku: `S${i}`, name: `Barang ${i}`, category_id: 1, category_name: kat,
  unit_code: "pcs", quantity: 10, reserved_quantity: 0, minimum_stock: 2,
  reorder_point: 5, maximum_stock: 20, status: "normal", decision: null, ...over,
});

describe("susunTataLetak", () => {
  it("mengelompokkan per kategori dan memecah rak yang penuh", () => {
    const items = [...Array.from({ length: 13 }, (_, i) => b(i, "A")), b(99, "B")];
    const t = susunTataLetak(items);
    expect(t.rak.map((r) => r.slots.length)).toEqual([12, 1, 1]);
    expect(new Set(t.rak.map((r) => r.id)).size).toBe(3);
  });
  it("tidak menumpuk rak di posisi yang sama", () => {
    const t = susunTataLetak(Array.from({ length: 5 }, (_, i) => b(i, `K${i}`)));
    expect(new Set(t.rak.map((r) => `${r.x}|${r.z}`)).size).toBe(5);
  });
  it("kosong menghasilkan nol rak", () => {
    expect(susunTataLetak([]).rak).toHaveLength(0);
  });
});

describe("status & ringkasan", () => {
  it("status rak mengikuti yang terburuk", () => {
    expect(statusTerburuk(["normal", "perhatian", "kritis"])).toBe("kritis");
    expect(statusTerburuk(["tidak_diketahui", "normal"])).toBe("normal");
    expect(statusTerburuk(["tidak_diketahui"])).toBe("tidak_diketahui");
  });
  it("kapasitas null bila tak ada stok maksimum", () => {
    const x = [b(1, "A", { maximum_stock: null }), b(2, "A", { maximum_stock: 0 })];
    expect(ringkas(x, 1).kapasitas).toBeNull();
    expect(isiSlot(x[0])).toBeNull();
  });
  it("kapasitas dipotong di maksimum dan menghitung hanya barang bermaksimum", () => {
    const x = [b(1, "A", { quantity: 40, maximum_stock: 20 }), b(2, "A", { quantity: 0, maximum_stock: 20 }),
               b(3, "A", { maximum_stock: null })];
    const r = ringkas(x, 1);
    expect(r.kapasitas).toBeCloseTo(0.5);
    expect(r.kapasitasDari).toBe(2);
    expect(r.sku).toBe(3);
  });
  it("menghitung perhatian dan kritis", () => {
    const x = [b(1, "A", { status: "kritis" }), b(2, "A", { status: "perhatian" }), b(3, "A")];
    const r = ringkas(x, 1);
    expect([r.kritis, r.perhatian]).toEqual([1, 1]);
    expect(kapasitasRak(susunTataLetak(x).rak[0]).dariTotal).toBe(3);
  });
});

describe("jalurGudang", () => {
  const tata = susunTataLetak(Array.from({ length: 40 }, (_, i) => b(i, `K${i % 7}`)));
  const j = jalurGudang(tata);
  const tembusRak = (x: number, z: number, margin: number) =>
    tata.rak.some((r) => Math.abs(x - r.x) < r.lebar / 2 + margin && Math.abs(z - r.z) < r.dalam / 2 + margin);

  it("punya baris + 1 lorong", () => {
    expect(j.lorongZ).toHaveLength(tata.baris + 1);
  });
  it("forklift dan pekerja tidak pernah menembus rak (disampel sepanjang jalur)", () => {
    const { kumulatif, total } = panjangJalur(j.forklift, true);
    for (let d = 0; d < total; d += 0.25) {
      const p = posisiPadaJalur(j.forklift, kumulatif, total, d, true);
      expect(tembusRak(p.x, p.z, 0.55)).toBe(false); // setengah lebar forklift
    }
    for (const rute of j.pekerja) {
      const k = panjangJalur(rute, false);
      for (let d = 0; d <= k.total; d += 0.25) {
        const p = posisiPadaJalur(rute, k.kumulatif, k.total, d, false);
        expect(tembusRak(p.x, p.z, 0.3)).toBe(false);
      }
    }
  });
  it("forklift dan pekerja di lorong yang sama berjarak lateral cukup", () => {
    const zf = j.forklift.filter((_, i) => j.hentiForklift.includes(i)).map((p) => p[1]);
    j.lorongZ.forEach((z, i) => {
      expect(Math.abs(j.pekerja[i][0][1] - zf[i])).toBeGreaterThan(1.0);
    });
  });
  it("satu rak tetap menghasilkan jalur valid", () => {
    const k = jalurGudang(susunTataLetak([b(1, "A")]));
    expect(k.lorongZ).toHaveLength(2);
    expect(UKURAN.lorong).toBeGreaterThan(2);
  });
});

describe("gerak", () => {
  it("forklift berhenti di titik henti dan melanjutkan", () => {
    const henti = [10, 30];
    // v=2 m/s: sampai di 10 m pada t=5, berhenti 3 dtk
    expect(jarakForklift(2, 50, 2, henti, 3)).toMatchObject({ d: 4, indeks: -1, terakhir: -1 });
    const a = jarakForklift(6, 50, 2, henti, 3);
    expect(a).toMatchObject({ d: 10, indeks: 0 });
    expect(a.fase).toBeCloseTo(1 / 3);
    expect(jarakForklift(9, 50, 2, henti, 3)).toMatchObject({ d: 12, indeks: -1, terakhir: 0 });
    // satu siklus penuh kembali ke awal
    const T = 50 / 2 + 2 * 3;
    expect(jarakForklift(T, 50, 2, henti, 3).d).toBeCloseTo(0);
  });
  it("pekerja bolak-balik dalam batas lorong", () => {
    for (let t = 0; t < 120; t += 0.3) {
      const g = jarakBolakBalik(t, 10, 1.2, 1.5);
      expect(g.d).toBeGreaterThanOrEqual(-1e-9);
      expect(g.d).toBeLessThanOrEqual(10 + 1e-9);
    }
    expect(jarakBolakBalik(10 / 1.2 + 0.5, 10, 1.2, 1.5).diam).toBe(true);
  });
});

describe("dock", () => {
  const tata = susunTataLetak(Array.from({ length: 30 }, (_, i) => b(i, `K${i % 5}`)));
  const d = layoutDock(tata);
  const j = jalurGudang(tata);
  const T = SIKLUS_TRUK.datang + SIKLUS_TRUK.muat + SIKLUS_TRUK.pergi + SIKLUS_TRUK.jeda;

  it("dinding dock jauh dari lorong pertama dan kedua pintu tidak tumpang tindih", () => {
    expect(j.lorongZ[0] - d.zDinding).toBeGreaterThan(6);
    expect(d.bay[1].x - d.bay[0].x).toBeGreaterThan(DOCK.pintuLebar + 3);
  });
  it("siklus fase berurutan dan berulang", () => {
    expect(fasaTruk(0, 0).fase).toBe("datang");
    expect(fasaTruk(SIKLUS_TRUK.datang + 1, 0).fase).toBe("muat");
    expect(fasaTruk(T - 1, 0).fase).toBe("jeda");
    expect(fasaTruk(T, 0).fase).toBe("datang");
  });
  it("pintu bergantian: tidak keduanya memuat bersamaan", () => {
    for (let t = 0; t < T * 2; t += 0.5) {
      const a = fasaTruk(t, d.bay[0].mulai).fase, c = fasaTruk(t, d.bay[1].mulai).fase;
      expect(a === "muat" && c === "muat").toBe(false);
    }
  });
  it("truk berhenti tepat di dinding saat muat dan jauh saat jeda", () => {
    expect(offsetTruk("muat", 0.5)).toBe(0);
    expect(offsetTruk("datang", 1)).toBeCloseTo(0);
    expect(offsetTruk("jeda", 0)).toBeLessThan(-10);
    expect(bukaPintu("muat", 0.3)).toBe(1);
    expect(bukaPintu("jeda", 0.3)).toBe(0);
  });
  it("forklift dock tidak melompat dan tidak menembus dinding/rak sepanjang siklus", () => {
    for (const bay of d.bay) {
      let prev: { x: number; z: number } | null = null;
      for (let t = 0; t < T; t += 0.1) {
        const { fase, f } = fasaTruk(t, bay.mulai);
        const p = kegiatanDock(d, bay, fase, f);
        if (prev) expect(Math.hypot(p.x - prev.x, p.z - prev.z)).toBeLessThan(0.7);
        prev = p;
        // dinding hanya tembus lewat bukaan pintu (|x - xb| < lebar/2 - setengah forklift)
        if (Math.abs(p.z - d.zDinding) < 0.4) expect(Math.abs(p.x - bay.x)).toBeLessThan(DOCK.pintuLebar / 2 - 0.55);
        // tetap di sisi gudang lorong pertama
        expect(p.z).toBeLessThan(j.lorongZ[0] - 0.5);
        // di dalam trailer, forklift tidak keluar dari lebar dalamnya
        if (p.z < d.zDinding) expect(Math.abs(p.x - bay.x)).toBeLessThan(DOCK.trailerLebarDalam / 2 - 0.5);
        expect(tembusRakDock(p.x, p.z)).toBe(false);
      }
    }
    function tembusRakDock(x: number, z: number) {
      return tata.rak.some((r) => Math.abs(x - r.x) < r.lebar / 2 + 0.55 && Math.abs(z - r.z) < r.dalam / 2 + 0.55);
    }
  });
  it("pallet dipindah satu per perjalanan dan jumlahnya terjaga", () => {
    for (const bay of d.bay) {
      for (let f = 0; f <= 1; f += 0.01) {
        const p = kegiatanDock(d, bay, "muat", f);
        const total = p.staging.filter(Boolean).length + p.trailer.filter(Boolean).length + (p.bawa ? 1 : 0);
        expect(total).toBe(DOCK.jumlahPalet);
      }
      const awal = kegiatanDock(d, bay, "muat", 0);
      const akhir = kegiatanDock(d, bay, "muat", 0.999);
      if (bay.jenis === "keluar") {
        expect(awal.staging.every(Boolean)).toBe(true);
        expect(akhir.trailer.every(Boolean)).toBe(true);
      } else {
        expect(awal.trailer.every(Boolean)).toBe(true);
        expect(akhir.staging.every(Boolean)).toBe(true);
      }
    }
  });
  it("rute tiap perjalanan lurus pada sumbu (tidak diagonal menembus pallet)", () => {
    for (const bay of d.bay) for (let i = 0; i < DOCK.jumlahPalet; i++) {
      for (const r of [ruteBawa(d, bay, i), ruteBalik(d, bay, i)])
      for (let k = 1; k < r.length; k++) expect(r[k][0] === r[k - 1][0] || r[k][1] === r[k - 1][1]).toBe(true);
    }
  });
});
