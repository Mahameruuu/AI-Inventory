import { BarisTransfer, KirimanTransfer } from "@/lib/transfer-types";

/** Satu barang dalam satu kiriman: barisnya beserta bagian kirimannya. */
export interface MuatanRute {
  baris: BarisTransfer;
  leg: KirimanTransfer;
}

export interface RuteTransfer {
  kunci: string;
  dariId: number;
  keId: number;
  muatan: MuatanRute[];
}

/**
 * Mengelompokkan usulan per RUTE (gudang asal -> gudang tujuan).
 *
 * Dokumen transfer memang punya satu asal dan satu tujuan tetapi BANYAK baris
 * barang, jadi barang-barang yang berangkat dari gudang yang sama ke gudang
 * yang sama cukup satu kartu dan satu dokumen -- rinciannya berupa daftar
 * barang. Kebutuhan tanpa pengirim (murni pembelian) tidak punya rute dan tetap
 * satu kartu sendiri.
 */
export function kelompokkanRute(items: BarisTransfer[]): { rute: RuteTransfer[]; beli: BarisTransfer[] } {
  const peta = new Map<string, RuteTransfer>();
  const beli: BarisTransfer[] = [];
  for (const b of items) {
    if (!b.legs.length) {
      beli.push(b);
      continue;
    }
    for (const leg of b.legs) {
      const kunci = `${leg.from_warehouse_id}>${b.to_warehouse_id}`;
      let r = peta.get(kunci);
      if (!r) {
        r = { kunci, dariId: leg.from_warehouse_id, keId: b.to_warehouse_id, muatan: [] };
        peta.set(kunci, r);
      }
      r.muatan.push({ baris: b, leg });
    }
  }
  return { rute: [...peta.values()], beli };
}
