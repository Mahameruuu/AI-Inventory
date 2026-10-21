"use client";

/**
 * Analisis Umur Pakai / Lifetime Analysis.
 *
 * SATU PERTANYAAN: apakah komponen diganti lebih cepat atau lebih lambat
 * daripada umur pakai yang diharapkan?
 *
 * Halaman ini menempati posisi Deteksi Anomali, yang dihapus pada 2 September
 * 2026. Yang dijawab modul lama adalah "apakah pola jumlah stok berubah" --
 * pertanyaan yang jawabannya hanya berdiri di atas ambang statistik yang harus
 * dikalibrasi terus-menerus. Yang dijawab halaman ini berdiri di atas angka
 * referensi yang memang tercatat di master barang (items.service_life_value),
 * sehingga "menyimpang" punya arti yang dapat ditunjuk sumbernya.
 *
 * TIGA HAL YANG TIDAK BOLEH DILAKUKAN DI LAYAR INI:
 *
 *   1. MENYEBUT SEBAB. Boleh: "diganti 30% lebih cepat daripada umur pakai
 *      harapan". Tidak boleh: "karena olinya telat diganti". Data beban, suhu,
 *      pelumasan, dan pemeliharaan tidak ada di sistem ini.
 *
 *   2. MEMPRAKIRAKAN KERUSAKAN. Ini bukan predictive maintenance. Yang diukur
 *      adalah apa yang SUDAH terjadi.
 *
 *   3. MENGUBAH PRAKIRAAN ATAU PEMESANAN ULANG. Aturan bisnis yang
 *      menghubungkan umur pakai dengan titik pesan belum ada; mengarangnya di
 *      sini akan menggerakkan uang pengadaan tanpa seorang pun menyetujuinya.
 *      Yang ada hanyalah TAUTAN ke kedua halaman itu, dan kalimat dampak yang
 *      berbunyi "berpotensi", bukan "akan".
 *
 * TIDAK ADA RUMUS DI BERKAS INI. Seluruh angka, status, dan kalimat datang
 * dari /api/lifetime.
 */

import { useEffect, useState } from "react";
import { Timer, TrendingUp, RefreshCw } from "lucide-react";
import Link from "next/link";

import { GrafikRiwayatPenggantian } from "@/components/lifetime-charts";
import {
  RingkasanUmurPakai,
  RiwayatPenggantian,
  Ruas,
  SaringanUmurPakai,
  TabelUmurPakai,
} from "@/components/lifetime-sections";
import {
  Card,
  Empty,
  ErrorBox,
  Insight,
  PageHeader,
  PageSkeleton,
  Pager,
  SkeletonRows,
} from "@/components/ui";
import { useApi } from "@/lib/api";
import { dateLabel, num } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { BarisUmurPakai, DaftarUmurPakai, DetailUmurPakai } from "@/lib/lifetime-types";

const PER_HALAMAN = 25;

export default function LifetimePage() {
  const t = useT();

  const [warehouseId, setWarehouseId] = useState("");
  const [status, setStatus] = useState("");
  const [cari, setCari] = useState("");
  const [page, setPage] = useState(1);
  const [terpilih, setTerpilih] = useState<BarisUmurPakai | null>(null);

  // Pencarian ditunda sebelum dikirim: tiap ketukan tombol yang langsung
  // menjadi permintaan berarti backend mengelompokkan ulang seluruh riwayat
  // penggantian untuk kata yang belum selesai diketik.
  const [cariKirim, setCariKirim] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setCariKirim(cari.trim()), 350);
    return () => clearTimeout(id);
  }, [cari]);

  // Mengganti saringan mengembalikan ke halaman pertama, dan menutup panel
  // detail: baris yang sedang dibuka bisa saja tidak lagi ada di hasil.
  useEffect(() => {
    setPage(1);
    setTerpilih(null);
  }, [warehouseId, status, cariKirim]);

  const { data: gudang } = useApi<any>("/api/warehouses", { page_size: 200 });

  const { data, error, loading, refreshing } = useApi<DaftarUmurPakai>("/api/lifetime", {
    warehouse_id: warehouseId || undefined,
    status: status || undefined,
    q: cariKirim || undefined,
    page,
    page_size: PER_HALAMAN,
  });

  const kunciDetail = terpilih ? `/api/lifetime/${terpilih.item.id}/${terpilih.warehouse.id}` : null;
  const { data: detail, loading: memuatDetail } = useApi<DetailUmurPakai>(kunciDetail);

  if (error) return <ErrorBox message={error} />;

  const kepala = (
    <PageHeader
      icon={<Timer size={20} />}
      eyebrow={t("nav.ai")}
      title={t("lt.title")}
      description={t("lt.desc")}
    >
      <SaringanUmurPakai
        gudang={(gudang?.items ?? []) as any[]}
        warehouseId={warehouseId}
        setWarehouseId={setWarehouseId}
        status={status}
        setStatus={setStatus}
        cari={cari}
        setCari={setCari}
      />
    </PageHeader>
  );

  if (loading && !data) {
    return (
      <>
        {kepala}
        <PageSkeleton />
      </>
    );
  }

  const d = data!;
  // Menekan baris yang sedang terbuka menutupnya kembali.
  const pilih = (b: BarisUmurPakai) =>
    setTerpilih((kini) =>
      kini && kini.item.id === b.item.id && kini.warehouse.id === b.warehouse.id ? null : b,
    );
  /*
   * SELURUH katalog tanpa umur pakai referensi -- keadaan penyewa yang belum
   * mengisi kolomnya sama sekali. Barisnya TETAP ada (dua puluh baris berisi
   * tanda hubung), jadi cabang `items.length === 0` tidak pernah tercapai dan
   * panduan perbaikannya tidak pernah terbit. Diperiksa dari ringkasannya,
   * bukan dari panjang daftar halaman ini.
   */
  const tanpaReferensi =
    d.summary.total_items > 0 && d.summary.without_reference === d.summary.total_items;

  return (
    <>
      {kepala}

      {/* Catatan asumsi (jam operasi, lebar pita) dihapus atas permintaan
          pengguna; yang tersisa hanya panduan saat belum ada standar sama sekali. */}
      {tanpaReferensi && <Insight tone="neutral">{t("lt.no_reference")}</Insight>}

      <RingkasanUmurPakai ringkas={d.summary} />

      {/*
        TABEL DULU, GRAFIK PER BARIS. Tiap komponen punya grafiknya sendiri
        (standar vs aktual), dibuka dari kolom "Grafik" dan tampil tepat di
        bawah barisnya bersama rinciannya.
      */}
      <div className="mt-4">
        <Card
          icon={<Timer size={15} />}
          title={t("lt.chart.title")}
          subtitle={t("lt.chart.subtitle")}
          dim={refreshing}
          delay={80}
        >
          {d.items.length ? (
            <>
              <TabelUmurPakai
                baris={d.items}
                total={d.total}
                terpilih={terpilih ? `${terpilih.item.id}-${terpilih.warehouse.id}` : null}
                onPilih={pilih}
                rincian={
                  !terpilih ? null : memuatDetail && !detail ? (
                    <SkeletonRows rows={4} cols={3} />
                  ) : detail ? (
                    <PanelDetail detail={detail} />
                  ) : null
                }
              />
              <Pager page={d.page} pages={d.pages} onPage={setPage} />
            </>
          ) : (
            <Empty message={tanpaReferensi ? t("lt.empty_all") : t("lt.empty")} />
          )}
        </Card>
      </div>
    </>
  );
}

/**
 * Isi panel detail satu komponen.
 *
 * Grafik standar vs aktual di kiri, angka dan kalimat dampaknya di kanan.
 */
function PanelDetail({ detail }: { detail: DetailUmurPakai }) {
  const t = useT();
  const punyaPita =
    detail.lower_lifetime_days !== null &&
    detail.expected_lifetime_days !== null &&
    detail.upper_lifetime_days !== null;
  const adaGrafik = punyaPita && detail.events.some((e) => e.lifetime_days !== null);

  // Dua kolom di layar lebar -- grafik di kiri, angka di kanan; satu kolom
  // dengan urutan yang sama di layar sempit.
  return (
    <div className="grid gap-x-10 gap-y-5 lg:grid-cols-2">
      <div className="min-w-0 space-y-5">
      <div>
        <div className="font-display t-lead font-semibold leading-snug text-ink">
          {detail.item.name}
        </div>
        <p className="mt-1.5 t-body leading-relaxed text-ink-2">{detail.basis}</p>
      </div>

      {punyaPita && (
        <div className="grid grid-cols-3 gap-4">
          <Ruas label={t("lt.detail.lower")}>
            {num(detail.lower_lifetime_days)} {t("lt.unit.days")}
          </Ruas>
          <Ruas label={t("lt.chart.standard")}>
            {num(detail.expected_lifetime_days)} {t("lt.unit.days")}
          </Ruas>
          <Ruas label={t("lt.detail.upper")}>
            {num(detail.upper_lifetime_days)} {t("lt.unit.days")}
          </Ruas>
        </div>
      )}

      {/*
       * Tanggal penggantian terakhir berdiri SENDIRI, di luar syarat "umurnya
       * sudah terukur". Komponen yang baru sekali diganti tidak punya jarak
       * untuk diukur -- tetapi tanggal pemasangannya justru satu-satunya hal
       * yang diketahui pasti tentangnya, dan menyembunyikannya bersama ruas
       * lain membuat panelnya kosong untuk barang yang datanya justru ada.
       */}
      {detail.last_replacement_date && (
        <div className="grid grid-cols-3 gap-4">
          {detail.actual_lifetime_days !== null && (
            <>
              <Ruas label={t("lt.detail.shortest")}>
                {num(detail.shortest_lifetime_days)} {t("lt.unit.days")}
              </Ruas>
              <Ruas label={t("lt.detail.longest")}>
                {num(detail.longest_lifetime_days)} {t("lt.unit.days")}
              </Ruas>
            </>
          )}
          <Ruas label={t("lt.detail.last")}>{dateLabel(detail.last_replacement_date)}</Ruas>
        </div>
      )}

      {/*
       * Kalimat dampak, disusun backend. Ia berbunyi "berpotensi" dan tidak
       * pernah menyebut jumlah pesanan: yang diketahui adalah pola yang sudah
       * terjadi, bukan permintaan yang pasti datang.
       */}
      {detail.inventory_impact && (
        <div
          className="rounded-xl px-3.5 py-3 t-body leading-relaxed"
          style={{ background: "var(--surface-sunken)", color: "var(--text-secondary)" }}
        >
          {detail.inventory_impact}
          <div className="mt-2.5 flex flex-wrap gap-3 t-small">
            <Link
              href={`/forecasting?item_id=${detail.item.id}&warehouse_id=${detail.warehouse.id}`}
              className="inline-flex items-center gap-1 font-semibold"
              style={{ color: "var(--brand)" }}
            >
              <TrendingUp size={12} />
              {t("lt.link.forecast")}
            </Link>
            <Link
              href="/reorder"
              className="inline-flex items-center gap-1 font-semibold"
              style={{ color: "var(--brand)" }}
            >
              <RefreshCw size={12} />
              {t("lt.link.reorder")}
            </Link>
          </div>
        </div>
      )}

      </div>
      {/* Grafik lebih dulu: untuk itulah baris ini dibuka. */}
      <div className="min-w-0 space-y-5 lg:order-first">
      {!adaGrafik && (
        <p className="t-small text-muted">{t("lt.chart.no_data")}</p>
      )}
      {detail.events.length > 0 && (
        <div>
          <div className="mb-2 t-micro font-semibold uppercase tracking-[0.07em] text-muted">
            {adaGrafik ? t("lt.chart.history_title") : t("lt.detail.events")}
          </div>
          {adaGrafik ? (
            <>
              <GrafikRiwayatPenggantian
                kejadian={detail.events}
                harapan={detail.expected_lifetime_days!}
                bawah={detail.lower_lifetime_days!}
                atas={detail.upper_lifetime_days!}
              />
              {/* Tabelnya tetap ada, tertutup: nomor dokumen dan tanggal
                  persisnya hanya terbaca di sana. */}
              <details className="mt-3">
                <summary className="cursor-pointer t-small font-semibold" style={{ color: "var(--brand)" }}>
                  {t("lt.chart.events_table")}
                </summary>
                <div className="mt-2">
                  <RiwayatPenggantian kejadian={detail.events} total={detail.events_total} />
                </div>
              </details>
            </>
          ) : (
            <RiwayatPenggantian kejadian={detail.events} total={detail.events_total} />
          )}
        </div>
      )}

      </div>
    </div>
  );
}
