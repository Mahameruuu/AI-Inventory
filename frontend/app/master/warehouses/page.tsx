"use client";

import { Warehouse } from "lucide-react";

import MasterCrud from "@/components/master-crud";

export default function HalamanGudang() {
  return (
    <MasterCrud
      judul="md.wh_title"
      labelTambah="md.wh_add"
      deskripsi="md.wh_desc"
      ikon={<Warehouse size={20} />}
      jalur="/api/warehouses"
      kolomPemakaian={{ key: "item_count", label: "md.used_by" }}
      ruas={[
        { key: "code", label: "md.code", wajib: true, petunjuk: "WH-JKT" },
        { key: "name", label: "md.name", wajib: true, petunjuk: "Gudang Pusat Jakarta" },
        { key: "location", label: "md.location", petunjuk: "Cakung, Jakarta Timur" },
        /*
         * Koordinat TIDAK ikut ke tabel daftar, dan itu disengaja: kolom
         * angka pada tabel ini dicetak tanpa desimal, sehingga lintang
         * -7,2575 akan tampil sebagai "-7" -- sebuah titik empat puluh
         * kilometer dari gudang yang dimaksud. Nilainya tetap terbaca dan
         * tersunting pada formulir.
         */
        { key: "latitude", label: "md.latitude", jenis: "angka", diTabel: false,
          petunjuk: "-7.2575", keterangan: "md.coord_hint" },
        { key: "longitude", label: "md.longitude", jenis: "angka", diTabel: false,
          petunjuk: "112.7521" },
        { key: "transfer_lead_time_days", label: "md.transfer_lead", jenis: "angka",
          rata: "kanan", petunjuk: "2", keterangan: "md.transfer_lead_hint" },
      ]}
    />
  );
}
