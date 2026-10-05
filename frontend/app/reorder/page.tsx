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
 * TIDAK ADA PEMILIH PERIODE DAN TIDAK ADA PEMILIH MODEL, dan keduanya
 * disengaja:
 *
 *   periode  Jumlah pesanan berpatokan HORIZON KEPUTUSAN yang dipatok backend
 *            (decision.HORIZON_KEPUTUSAN), bukan periode tampilan. Menyediakan
 *            dropdown periode di sini akan menyiratkan bahwa menggesernya
 *            mengubah jumlah pesanan -- padahal tidak, dan tidak boleh.
 *   model    Titik pesan tidak menuntut model prakiraan untuk berarti; ia
 *            menuntut laju pemakaian dan ketidakpastiannya. Dropdown model di
 *            sini hanya menawarkan pilihan yang tidak menjawab pertanyaan layar
 *            ini, lalu membuat pembacanya mengira urutan pekerjaannya
 *            bergantung padanya.
 *
 * TIDAK ADA SATU PUN RUMUS DI BERKAS INI, dan tidak ada nama model, galat
 * terskala, atau papan skor. Layar ini berorientasi TINDAKAN.
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
  }, [warehouseId, prioritas, tab, cariKirim]);

  const { data: gudang } = useApi<any>("/api/warehouses", { page_size: 200 });

  const { data, error, loading } = useApi<DaftarReorder>("/api/reorder", {
    warehouse_id: warehouseId || undefined,
    status: tab || undefined,
    priority: prioritas || undefined,
    q: cariKirim || undefined,
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
        />
      </PageHeader>

      {loading && !data ? (
        <PageSkeleton tiles={4} rows={8} cols={8} />
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
              horizon={data.items[0]?.decision_horizon_days ?? 14}
              tab={tab}
            />
          </div>

          {data.pages > 1 && (
            <Pager page={data.page} pages={data.pages} total={data.total} onPage={setPage} />
          )}
        </div>
      )}
    </>
  );
}
