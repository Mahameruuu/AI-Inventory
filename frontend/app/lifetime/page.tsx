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
 *      pelumasan, dan pemeliharaan tidak ada di sistem ini, dan panel Faktor
 *      Pendukung tercetak justru untuk mengatakan itu.
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
import { BarChart3, Table2, Timer, TrendingUp, RefreshCw, X } from "lucide-react";
import Link from "next/link";

import { GrafikRiwayatPenggantian, GrafikUmurPakai } from "@/components/lifetime-charts";
import {
  FaktorPendukung,
  PitaUmurPakai,
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
  // Grafik adalah tampilan utama; tabelnya tetap ada bagi yang ingin
  // mengurutkan kolom atau membaca angka per angka.
  const [tampilan, setTampilan] = useState<"grafik" | "tabel">("grafik");

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
  const samping = tampilan === "tabel";
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

      {/*
       * ASUMSI DICETAK, TIDAK DISEMBUNYIKAN. Konversi jam operasi dan lebar
       * pita toleransi menentukan setiap angka di bawahnya; menyembunyikannya
       * membuat halaman ini terlihat lebih pasti daripada yang sebenarnya.
       */}
      <Insight tone="neutral">
        {tanpaReferensi ? t("lt.no_reference") : d.assumptions.note}
      </Insight>

      <RingkasanUmurPakai ringkas={d.summary} />

      {/*
        GRAFIK MEMAKAI SELURUH LEBAR, dan rinciannya terbuka DI BAWAHNYA untuk
        komponen yang dipilih: dua puluh lima nama komponen pada sumbu datar
        tidak muat di kolom 3/5. Tampilan tabel tetap memakai panel samping.
      */}
      <div className={samping ? "mt-4 grid gap-4 xl:grid-cols-5" : "mt-4"}>
        <Card
          className={samping ? "xl:col-span-3" : ""}
          icon={<Timer size={15} />}
          title={t("lt.chart.title")}
          subtitle={t("lt.chart.subtitle")}
          meta={`${num(d.total)} ${t("c.rows_label")}`}
          right={
            <div
              role="tablist"
              className="inline-flex gap-1 rounded-lg p-0.5"
              style={{ background: "var(--surface-sunken)" }}
            >
              {(["grafik", "tabel"] as const).map((v) => {
                const on = v === tampilan;
                const Ikon = v === "grafik" ? BarChart3 : Table2;
                return (
                  <button
                    key={v}
                    role="tab"
                    aria-selected={on}
                    onClick={() => setTampilan(v)}
                    className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 t-caption font-semibold transition"
                    style={{
                      background: on ? "var(--surface-1)" : "transparent",
                      color: on ? "var(--text-primary)" : "var(--text-secondary)",
                      boxShadow: on ? "var(--elev-1)" : "none",
                    }}
                  >
                    <Ikon size={12} />
                    {t(v === "grafik" ? "lt.view.chart" : "lt.view.table")}
                  </button>
                );
              })}
            </div>
          }
          dim={refreshing}
          delay={80}
        >
          {d.items.length ? (
            <>
              {tampilan === "grafik" ? (
                <GrafikUmurPakai
                  baris={d.items}
                  terpilih={terpilih ? `${terpilih.item.id}-${terpilih.warehouse.id}` : null}
                  onPilih={pilih}
                  rincian={
                    !terpilih ? null : memuatDetail && !detail ? (
                      <SkeletonRows rows={4} cols={3} />
                    ) : detail ? (
                      <PanelDetail detail={detail} lebar />
                    ) : null
                  }
                />
              ) : (
                <TabelUmurPakai
                  baris={d.items}
                  total={d.total}
                  terpilih={terpilih ? `${terpilih.item.id}-${terpilih.warehouse.id}` : null}
                  onPilih={setTerpilih}
                />
              )}
              <Pager page={d.page} pages={d.pages} total={d.total} onPage={setPage} />
            </>
          ) : (
            <Empty message={tanpaReferensi ? t("lt.empty_all") : t("lt.empty")} />
          )}
        </Card>

        {/* ---------- panel detail (tampilan tabel) ---------- */}
        {samping && (
        <div className="xl:col-span-2">
          <Card
            icon={<RefreshCw size={15} />}
            title={t("lt.detail.title")}
            subtitle={terpilih ? `${terpilih.item.sku} · ${terpilih.warehouse.code}` : undefined}
            right={
              terpilih ? (
                <button
                  onClick={() => setTerpilih(null)}
                  title={t("lt.detail.close")}
                  aria-label={t("lt.detail.close")}
                  className="rounded-lg p-1 text-muted transition hover:bg-surface-2"
                >
                  <X size={14} />
                </button>
              ) : undefined
            }
            delay={140}
          >
            {!terpilih ? (
              <Empty message={t("lt.detail.empty")} />
            ) : memuatDetail && !detail ? (
              <SkeletonRows rows={6} cols={3} />
            ) : detail ? (
              <PanelDetail detail={detail} />
            ) : null}
          </Card>
        </div>
        )}
      </div>
    </>
  );
}

/**
 * Isi panel detail satu komponen.
 *
 * Urutannya disengaja: kesimpulan (pita + status) lebih dulu, riwayat yang
 * menopangnya sesudahnya, batas pengetahuan (faktor pendukung) paling akhir.
 * Pembaca yang berhenti di layar pertama tetap membawa pulang kesimpulan yang
 * benar; yang menggulir sampai bawah tahu persis apa yang TIDAK diketahui
 * sistem ini.
 */
function PanelDetail({ detail, lebar = false }: { detail: DetailUmurPakai; lebar?: boolean }) {
  const t = useT();
  const punyaPita =
    detail.lower_lifetime_days !== null &&
    detail.expected_lifetime_days !== null &&
    detail.upper_lifetime_days !== null;

  // `lebar`: dua kolom -- kesimpulan di kiri, riwayat di kanan. Sempit: satu
  // kolom dengan urutan yang sama.
  return (
    <div className={lebar ? "grid gap-x-10 gap-y-5 lg:grid-cols-2" : "space-y-5"}>
      <div className="min-w-0 space-y-5">
      <div>
        <div className="font-display t-lead font-semibold leading-snug text-ink">
          {detail.item.name}
        </div>
        <p className="mt-1.5 t-body leading-relaxed text-ink-2">{detail.basis}</p>
      </div>

      {/* Pada tampilan lebar pitanya sudah tergambar pada grafik riwayat di
          sebelahnya, jadi yang dicetak di sini cukup ketiga batasnya dalam
          hari. */}
      {punyaPita && lebar && (
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
      {punyaPita && !lebar && (
        <div>
          <div className="t-micro font-semibold uppercase tracking-[0.07em] text-muted">
            {t("lt.detail.band")}
          </div>
          <PitaUmurPakai
            bawah={detail.lower_lifetime_days!}
            harapan={detail.expected_lifetime_days!}
            atas={detail.upper_lifetime_days!}
            aktual={detail.actual_lifetime_days}
            status={detail.status}
          />
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
        <div className="grid grid-cols-2 gap-4">
          {detail.actual_lifetime_days !== null && (
            <>
              <Ruas label={t("lt.detail.shortest")}>
                {num(detail.shortest_lifetime_days)} {t("lt.unit.days")}
              </Ruas>
              <Ruas label={t("lt.detail.longest")}>
                {num(detail.longest_lifetime_days)} {t("lt.unit.days")}
              </Ruas>
              <Ruas label={t("lt.detail.frequency")}>
                {detail.replacements_per_year !== null
                  ? t("lt.per_year", {
                      n: num(
                        detail.replacements_per_year,
                        detail.replacements_per_year < 1 ? 2 : 1,
                      ),
                    })
                  : "—"}
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
      <div className="min-w-0 space-y-5">
      {detail.events.length > 0 && (
        <div>
          <div className="mb-2 t-micro font-semibold uppercase tracking-[0.07em] text-muted">
            {punyaPita ? t("lt.chart.history_title") : t("lt.detail.events")}
          </div>
          {punyaPita ? (
            <>
              <GrafikRiwayatPenggantian
                kejadian={detail.events}
                bawah={detail.lower_lifetime_days!}
                harapan={detail.expected_lifetime_days!}
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

      <div>
        <div className="mb-2 t-micro font-semibold uppercase tracking-[0.07em] text-muted">
          {t("lt.factors")}
        </div>
        <FaktorPendukung
          faktor={detail.contributing_factors}
          catatan={detail.contributing_factors_note}
        />
      </div>
      </div>
    </div>
  );
}
