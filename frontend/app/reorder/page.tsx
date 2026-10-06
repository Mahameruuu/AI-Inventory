"use client";

/**
 * Pemesanan Ulang / Reorder.
 *
 * SATU PERTANYAAN: mana saja yang perlu dipesan hari ini, dan berapa.
 *
 * Layar ini dulu menjawab untuk SATU barang pada satu waktu -- dropdown gudang,
 * dropdown barang, lalu satu panel keputusan. Jawabannya benar, tetapi
 * pertanyaannya salah: orang pengadaan tidak datang membawa satu SKU, ia datang
 * membawa satu gudang dan waktu yang terbatas. Menjawab pertanyaannya dengan
 * layar lama menuntutnya memilih barang satu per satu dari dropdown lalu
 * mengingat sendiri hasilnya, dan barang yang tidak kebetulan ia pilih tidak
 * pernah muncul sama sekali.
 *
 * KEPUTUSANNYA TIDAK BERUBAH, HANYA CAKUPANNYA. Tiap baris dihitung jalur yang
 * sama persis dengan /api/forecast, jadi satu barang menyebut status, titik
 * pesan, dan jumlah yang sama di daftar ini maupun di halaman Prakiraan.
 *
 * PERIODE DAN MODEL DIBAGI DENGAN HALAMAN PRAKIRAAN (sejak 6 Oktober 2026).
 * Dulu keduanya sengaja tidak ada: jumlah pesanan berpatokan horizon tetap 14
 * hari supaya setelan di layar sebelah tidak menggesernya diam-diam. Harganya
 * dua halaman yang menyebut dua kebutuhan untuk barang yang sama. Kini
 * kendalinya ada DI SINI JUGA, sehingga pergeserannya disengaja dan terlihat:
 *
 *   periode  Menentukan kolom Kebutuhan, Kurang / sisa, status, dan jumlah
 *            pesanan. Barang yang kurang untuk periode itu perlu dipesan, dan
 *            jumlahnya kekurangan + stok pengaman.
 *   model    Menentukan siapa yang meramal kebutuhannya; pilihan yang sama
 *            dengan Prakiraan supaya angkanya identik di kedua halaman.
 *
 * TIDAK ADA SATU PUN RUMUS DI BERKAS INI, dan tidak ada galat terskala atau
 * papan skor. Layar ini berorientasi TINDAKAN.
 */

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";

import {
  PeringatanTerpotong,
  RingkasanReorder,
  SaringanReorder,
  TabReorder,
  TabelReorder,
  TabStatus,
} from "@/components/reorder-list";
import { usePilihanModel, usePilihanPeriode } from "@/components/forecast-ui";
import { ErrorBox, PageHeader, PageSkeleton, Pager } from "@/components/ui";
import { useApi } from "@/lib/api";
import { DaftarReorder } from "@/lib/forecast-types";
import { useT } from "@/lib/i18n";

const PER_HALAMAN = 25;

export default function ReorderPage() {
  const t = useT();

  const [warehouseId, setWarehouseId] = useState("");
  const [prioritas, setPrioritas] = useState("");
  const [tab, setTab] = useState<TabStatus>("");
  const [cari, setCari] = useState("");
  const [page, setPage] = useState(1);
  // Keduanya dibagi dengan halaman Prakiraan; lihat usePilihanPeriode.
  const [days, setDays] = usePilihanPeriode();
  const [model, setModel] = usePilihanModel();

  /*
   * Pencarian DITUNDA sebelum dikirim. Tiap permintaan menjalankan rantai
   * prakiraan untuk setiap barang di gudang, jadi satu permintaan per ketukan
   * tombol akan menjalankan rantai itu berkali-kali untuk kata yang bahkan
   * belum selesai diketik.
   */
  const [cariKirim, setCariKirim] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setCariKirim(cari.trim()), 350);
    return () => clearTimeout(id);
  }, [cari]);

  /*
   * Saringan awal dari alamat: /reorder?gudang=3&cari=SKU-001. Dipakai tombol
   * "Pesan ulang" di halaman Prakiraan supaya pembaca mendarat langsung pada
   * barang yang baru saja dilihatnya, bukan pada daftar seluruh gudang.
   *
   * Dibaca di dalam efek, bukan lewat useSearchParams: halaman ini dirender
   * lebih dulu di server tanpa alamat, dan nilai awal yang berbeda antara
   * server dan peramban menghasilkan galat hidrasi pada kotak pencarian.
   */
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const g = p.get("gudang");
    const c = p.get("cari");
    if (g) setWarehouseId(g);
    if (c) {
      setCari(c);
      setCariKirim(c.trim());
    }
  }, []);

  // Mengganti saringan mengembalikan ke halaman pertama. Tanpa ini, menyaring
  // dari 40 baris menjadi 3 sementara pembaca berada di halaman 2 menghasilkan
  // layar kosong yang terbaca seolah tidak ada hasilnya.
  useEffect(() => {
    setPage(1);
  }, [warehouseId, prioritas, tab, cariKirim, days, model]);

  const { data: gudang } = useApi<any>("/api/warehouses", { page_size: 200 });

  const { data, error, loading } = useApi<DaftarReorder>("/api/reorder", {
    warehouse_id: warehouseId || undefined,
    status: tab || undefined,
    priority: prioritas || undefined,
    q: cariKirim || undefined,
    days,
    model,
    page,
    page_size: PER_HALAMAN,
  });

  if (error) return <ErrorBox message={error} />;

  return (
    <>
      <PageHeader
        icon={<RefreshCw size={20} />}
        eyebrow={t("nav.ai")}
        title={t("ro.title")}
        description={t("rl.desc")}
      >
        <SaringanReorder
          gudang={(gudang?.items ?? []) as any[]}
          warehouseId={warehouseId}
          setWarehouseId={setWarehouseId}
          prioritas={prioritas}
          setPrioritas={setPrioritas}
          cari={cari}
          setCari={setCari}
          periode={days}
          setPeriode={setDays}
          model={model}
          setModel={setModel}
        />
      </PageHeader>

      {loading && !data ? (
        <PageSkeleton tiles={4} rows={8} cols={7} />
      ) : !data ? null : (
        <div>
          <RingkasanReorder ringkas={data.summary} />

          {data.truncated && <PeringatanTerpotong batas={data.row_limit} />}

          <div className="mt-5">
            <TabReorder aktif={tab} setAktif={setTab} ringkas={data.summary} />
          </div>

          <div className="mt-3">
            <TabelReorder
              items={data.items}
              total={data.total}
              horizon={data.summary.horizon_hari}
              tab={tab}
            />
          </div>

          {data.pages > 1 && (
            <Pager page={data.page} pages={data.pages} onPage={setPage} />
          )}
        </div>
      )}
    </>
  );
}
