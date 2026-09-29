import { describe, expect, it } from "vitest";

import { MAKS_KENDARAAN_PER_BUSUR, rencanaKendaraan } from "@/lib/peta";
import { StatusTransfer } from "@/lib/transfer-types";

describe("rencanaKendaraan", () => {
  it("hanya dokumen Dikirim yang punya kendaraan bergerak", () => {
    const r = rencanaKendaraan("in_transit", 1);
    expect(r.posisi).toHaveLength(1);
    expect(r.bergerak).toBe(true);
  });

  it("Diajukan, Diterima, dan Dibatalkan tidak punya kendaraan sama sekali", () => {
    for (const s of ["draft", "completed", "cancelled"] as StatusTransfer[]) {
      expect(rencanaKendaraan(s, 5)).toEqual({ posisi: [], bergerak: false });
    }
  });

  it("Disetujui: satu kendaraan terparkir di gudang asal dan tidak bergerak", () => {
    const r = rencanaKendaraan("approved", 4);
    expect(r.posisi).toHaveLength(1);
    expect(r.posisi[0]).toBeLessThan(0.1);
    expect(r.bergerak).toBe(false);
  });

  it("satu kendaraan per dokumen Dikirim, tersebar rata dan dibatasi", () => {
    expect(rencanaKendaraan("in_transit", 2).posisi).toEqual([0, 0.5]);
    const banyak = rencanaKendaraan("in_transit", 40);
    expect(banyak.posisi).toHaveLength(MAKS_KENDARAAN_PER_BUSUR);
    // tidak ada dua kendaraan pada titik yang sama
    expect(new Set(banyak.posisi).size).toBe(banyak.posisi.length);
  });

  it("gerak dikurangi: kendaraan Dikirim diam, tersebar di tengah jalan", () => {
    const r = rencanaKendaraan("in_transit", 2, true);
    expect(r.bergerak).toBe(false);
    expect(r.posisi.every((p) => p > 0 && p < 1)).toBe(true);
  });

  it("tanpa dokumen tidak ada kendaraan", () => {
    expect(rencanaKendaraan("in_transit", 0).posisi).toEqual([]);
  });
});
