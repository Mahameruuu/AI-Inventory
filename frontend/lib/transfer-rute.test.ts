import { describe, expect, it } from "vitest";

import { kelompokkanRute } from "@/lib/transfer-rute";
import { BarisTransfer, KirimanTransfer } from "@/lib/transfer-types";

// Hanya kolom yang dibaca kelompokkanRute; sisanya sengaja tidak diisi.
function leg(dari: number, item = 1, qty = 10): KirimanTransfer {
  return { from_warehouse_id: dari, item_id: item, transfer_qty: qty } as KirimanTransfer;
}

function baris(item: number, ke: number, legs: KirimanTransfer[]): BarisTransfer {
  return { item_id: item, warehouse_id: ke, to_warehouse_id: ke, legs } as BarisTransfer;
}

describe("kelompokkanRute", () => {
  it("menggabungkan barang dengan asal dan tujuan sama menjadi satu rute", () => {
    const { rute, beli } = kelompokkanRute([
      baris(1, 2, [leg(1, 1)]),
      baris(2, 2, [leg(1, 2)]),
    ]);
    expect(rute).toHaveLength(1);
    expect(rute[0].muatan.map((m) => m.baris.item_id)).toEqual([1, 2]);
    expect(beli).toEqual([]);
  });

  it("memisahkan dua arah berlawanan menjadi dua rute", () => {
    const { rute } = kelompokkanRute([
      baris(1, 2, [leg(1, 1)]), // 1 -> 2
      baris(2, 1, [leg(2, 2)]), // 2 -> 1
    ]);
    expect(rute.map((r) => r.kunci)).toEqual(["1>2", "2>1"]);
    expect(rute.map((r) => [r.dariId, r.keId])).toEqual([[1, 2], [2, 1]]);
  });

  it("satu barang dengan dua gudang pengirim masuk ke dua rute", () => {
    const b = baris(1, 3, [leg(1, 1, 5), leg(2, 1, 7)]);
    const { rute } = kelompokkanRute([b]);
    expect(rute).toHaveLength(2);
    expect(rute.map((r) => r.muatan[0].leg.transfer_qty)).toEqual([5, 7]);
    expect(rute.every((r) => r.muatan[0].baris === b)).toBe(true);
  });

  it("barang tanpa pengirim tidak punya rute dan masuk ke daftar beli", () => {
    const murniBeli = baris(9, 2, []);
    const { rute, beli } = kelompokkanRute([baris(1, 2, [leg(1)]), murniBeli]);
    expect(rute).toHaveLength(1);
    expect(beli).toEqual([murniBeli]);
  });

  it("daftar kosong menghasilkan rute dan beli kosong", () => {
    expect(kelompokkanRute([])).toEqual({ rute: [], beli: [] });
  });

  it("mempertahankan urutan kemunculan rute", () => {
    const { rute } = kelompokkanRute([
      baris(1, 2, [leg(3)]),
      baris(2, 2, [leg(1)]),
      baris(3, 2, [leg(3)]),
    ]);
    expect(rute.map((r) => r.kunci)).toEqual(["3>2", "1>2"]);
    expect(rute[0].muatan).toHaveLength(2);
  });
});
