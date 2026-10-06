"use client";

import { Package } from "lucide-react";

import MasterCrud from "@/components/master-crud";

/**
 * Master barang.
 *
 * Berbeda dari /inventory/items, yang menampilkan barang BESERTA saldo stoknya
 * untuk dibaca. Halaman ini mengurus katalognya: SKU, satuan, harga referensi,
 * dan ambang perencanaan. Pemisahan itu disengaja -- yang satu dibuka setiap
 * hari untuk melihat keadaan, yang lain sesekali untuk merapikan data induk.
 */
export default function HalamanMasterBarang() {
  return (
    <MasterCrud
      judul="md.item_title"
      labelTambah="md.item_add"
      deskripsi="md.item_desc"
      ikon={<Package size={20} />}
      jalur="/api/items"
      ruas={[
        { key: "sku", label: "md.sku", wajib: true, petunjuk: "BRG-001" },
        { key: "name", label: "md.name", wajib: true, petunjuk: "Bearing 6205 ZZ" },
        {
          key: "category_id",
          label: "md.category",
          jenis: "pilihan",
          sumber: "/api/categories",
          labelKolom: "category_name",
          wajib: true,
        },
        {
          key: "unit_id",
          label: "md.unit",
          jenis: "pilihan",
          sumber: "/api/units",
          labelDari: "code",
          labelKolom: "unit_code",
          wajib: true,
        },
        { key: "unit_price", label: "md.price", jenis: "angka", rata: "kanan" },
        {
          key: "reorder_point",
          label: "md.reorder_point",
          jenis: "angka",
          rata: "kanan",
        },
        {
          key: "minimum_stock",
          label: "md.min_stock",
          jenis: "angka",
          rata: "kanan",
          diTabel: false,
        },
        {
          key: "maximum_stock",
          label: "md.max_stock",
          jenis: "angka",
          rata: "kanan",
          diTabel: false,
        },
        {
          key: "safety_stock",
          label: "md.safety_stock",
          jenis: "angka",
          rata: "kanan",
          diTabel: false,
        },
        {
          key: "lead_time_days",
          label: "md.lead_time",
          jenis: "angka",
          rata: "kanan",
          diTabel: false,
        },
        {
          key: "usage_type",
          label: "jenis.label",
          jenis: "opsi",
          opsi: [
            { value: "berumur_pakai", label: "jenis.berumur_pakai" },
            { value: "habis_pakai", label: "jenis.habis_pakai" },
          ],
        },
        {
          key: "criticality",
          label: "md.criticality",
          diTabel: false,
          petunjuk: "critical / high / medium / low",
        },
      ]}
    />
  );
}
