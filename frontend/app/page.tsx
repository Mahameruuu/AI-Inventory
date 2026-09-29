"use client";

/**
 * Dasbor / Dashboard.
 *
 * TIGA PERTANYAAN, DAN HANYA TIGA:
 *
 *   1. Bagaimana kondisi persediaan sekarang?   -> Total SKU, Total Stok
 *   2. Apa yang membutuhkan perhatian?          -> Perlu pesan ulang, risiko habis
 *   3. Apa yang diprakirakan akan terjadi?      -> Kebutuhan horizon keputusan
 *
 * APA YANG DICABUT PADA 2 SEPTEMBER 2026, dan kenapa. Versi sebelumnya
 * menampilkan delapan kartu angka, dua grafik, dua gauge, dan dua tabel; tidak
 * satu pun dari yang berikut menjawab salah satu dari ketiga pertanyaan di
 * atas:
 *
 *   Penerimaan / Pengeluaran / Pergerakan Stok   tiga kartu berisi jumlah
 *       DOKUMEN. Tidak ada keputusan yang berubah karena jumlah dokumen naik.
 *   Arus Stok 30 Hari (donat masuk vs keluar)    dua angka yang sudah
 *       diucapkan kartu Pergerakan tepat di sebelahnya.
 *   Kesiapan Operasional (dua gauge)             persentase master data yang
 *       berstatus aktif. Bukan kondisi persediaan sama sekali.
 *   Transaksi Terakhir (10 baris)                salinan halaman Transaksi.
 *
 * DASBOR TIDAK PUNYA RUMUS SENDIRI. Sebelumnya ia memakai definisi "stok
 * menipis" miliknya sendiri sementara halaman Pemesanan Ulang memakai titik
 * pesan efektif -- dua definisi untuk satu pertanyaan, dan tidak ada satu pun
 * galat yang menunjukkan mana yang benar bila keduanya berselisih. Kini
 * seluruh angka perhatian dan kebutuhan ke depan berasal dari mesin pemesanan
 * ulang, dirakit di backend/app/routers/dashboard.py, dan layar ini hanya
 * merendernya.
 */

import Link from "next/link";
import {
  ArrowRight,
  Boxes,
  LayoutDashboard,
  Layers,
  Package,
  RefreshCw,
  TrendingUp,
  TriangleAlert,
} from "lucide-react";

import {
  Card,
  Empty,
  ErrorBox,
  Insight,
  PageHeader,
  SkeletonChart,
  SkeletonTable,
  SkeletonTiles,
  StatTile,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { HBar } from "@/components/charts";
import { AKSI, PillAksi } from "@/components/status";
import { useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { idr, num } from "@/lib/format";

interface Dashboard {
  condition: { warehouses: number; items: number; stock: number; value: number };
  stock_by_warehouse: { code: string; name: string; total_stock: number; stock_value: number }[];
  attention: {
    need_reorder: number;
    stockout_risk: number;
    high_priority: number;
    healthy: number;
    rows: {
      sku: string;
      item_name: string;
      warehouse_code: string;
      unit_code: string | null;
      current_stock: number;
      reorder_point: number;
      days_of_cover: number | null;
      recommended_order_qty: number | null;
      status: string;
      status_label: string;
      priority: string;
      priority_label: string;
    }[];
  };
  forecast: {
    horizon_days: number | null;
    forecast_usage: number;
    recommended_order_qty: number;
    qty_unknown: number;
    projected_stockout: number;
    without_forecast: number;
  };
  state: { text: string; level: string };
  value_basis: string;
  truncated: boolean;
}

/*
 * Warna status TIDAK LAGI DIDEFINISIKAN DI SINI.
 *
 * Komentar yang berdiri di tempat ini dulu berbunyi "nilainya sama persis
 * dengan yang dipakai halaman Pemesanan Ulang" -- dan itu tidak benar:
 * "Perlu pesan ulang" tertulis `--status-serious` di sini dan
 * `--status-warning` di sana. Satu barang berganti warna saat pembacanya
 * berpindah layar, tanpa satu pun angkanya berubah. Komentar tidak dapat
 * menjaga dua salinan tetap sama; hanya satu salinan yang bisa.
 */

const NADA: Record<string, "neutral" | "warning"> = {
  good: "neutral",
  info: "neutral",
  warning: "warning",
};

export default function DashboardPage() {
  const { t } = useI18n();
  const { data, error, loading } = useApi<Dashboard>("/api/dashboard");

  if (error) return <ErrorBox message={error} />;

  /*
   * Kepala halaman berdiri di LUAR cabang memuat: judul dan kalimat
   * pengantarnya tidak bergantung pada data, jadi menahannya sampai data tiba
   * hanya membuat layar kosong lebih lama.
   */
  const kepala = (
    <PageHeader
      icon={<LayoutDashboard size={20} />}
      eyebrow={t("brand.name")}
      title={t("dash.title")}
      description={t("dash.desc")}
    />
  );

  if (loading && !data) {
    return (
      <>
        {kepala}
        <SkeletonTiles count={4} />
        <div className="mt-4 grid gap-4 xl:grid-cols-3">
          <SkeletonChart className="xl:col-span-2" height={168} delay={90} />
          <SkeletonChart height={168} delay={150} />
        </div>
        <div className="mt-4">
          <SkeletonTable rows={6} cols={5} delay={220} />
        </div>
      </>
    );
  }

  const d = data!;
  const a = d.attention;
  const f = d.forecast;
  const total = a.healthy + a.need_reorder + a.stockout_risk;

  return (
    <>
      {kepala}

      {/* SATU kalimat kondisi, bukan daftar berbutir. Kalimatnya sudah menyebut
          tindakannya, dan angkanya sudah ada di kartu tepat di bawahnya. */}
      <Insight tone={NADA[d.state.level] ?? "neutral"}>{d.state.text}</Insight>

      {/* ---------- 1 & 2: kondisi sekarang, lalu yang perlu perhatian ---------- */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label={t("dash.kpi.items")}
          value={num(d.condition.items)}
          hint={t("dash.kpi.items_hint")}
          icon={<Package size={15} />}
          delay={0}
        />
        <StatTile
          label={t("dash.kpi.stock")}
          value={num(d.condition.stock)}
          hint={t("dash.kpi.stock_hint", { n: num(d.condition.warehouses) })}
          icon={<Layers size={15} />}
          delay={60}
        />
        <StatTile
          label={t("dash.kpi.reorder")}
          value={num(a.need_reorder)}
          hint={a.need_reorder > 0 ? t("dash.kpi.reorder_hint") : t("dash.kpi.reorder_ok")}
          icon={<RefreshCw size={15} />}
          accent={a.need_reorder > 0 ? AKSI.PERLU_REORDER.warna : AKSI.AMAN.warna}
          delay={120}
        />
        <StatTile
          label={t("dash.kpi.stockout")}
          value={num(a.stockout_risk)}
          hint={
            a.stockout_risk > 0
              ? t("dash.kpi.stockout_hint", { n: num(a.high_priority) })
              : t("dash.kpi.stockout_ok")
          }
          icon={<TriangleAlert size={15} />}
          accent={a.stockout_risk > 0 ? AKSI.RISIKO_STOCKOUT.warna : AKSI.AMAN.warna}
          delay={180}
        />
      </div>

      {/* ---------- komposisi status dan sebaran stok ---------- */}
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Card
          icon={<Boxes size={15} />}
          title={t("dash.status")}
          subtitle={t("dash.status_sub")}
          delay={80}
        >
          {total ? (
            <HBar
              data={[
                {
                  label: t("dash.status.stockout"),
                  value: a.stockout_risk,
                  color: AKSI.RISIKO_STOCKOUT.warna,
                },
                {
                  label: t("dash.status.reorder"),
                  value: a.need_reorder,
                  color: AKSI.PERLU_REORDER.warna,
                },
                { label: t("dash.status.healthy"), value: a.healthy, color: AKSI.AMAN.warna },
              ]}
              height={124}
              labelWidth={140}
              valueWidth={64}
              colorKey
            />
          ) : (
            <Empty message={t("dash.empty_stock")} />
          )}
        </Card>

        <Card
          icon={<Layers size={15} />}
          title={t("dash.by_warehouse")}
          subtitle={t("dash.by_warehouse_sub")}
          delay={140}
        >
          {d.stock_by_warehouse.length ? (
            <HBar
              data={d.stock_by_warehouse.map((w) => ({
                label: w.code,
                value: Number(w.total_stock),
                display: `${num(w.total_stock)} ${t("dash.units")} · ${idr(w.stock_value)}`,
              }))}
              height={124}
              labelWidth={84}
              valueWidth={200}
            />
          ) : (
            <Empty message={t("dash.empty_stock")} />
          )}
        </Card>
      </div>

      {/* ---------- tabel: yang perlu ditangani ---------- */}
      <div className="mt-4">
        <Card
          icon={<TriangleAlert size={15} />}
          title={t("dash.attention")}
          subtitle={t("dash.attention_sub")}
          right={
            <Link
              href="/reorder"
              className="inline-flex items-center gap-1 text-xs font-semibold"
              style={{ color: "var(--brand)" }}
            >
              {t("dash.attention_all")}
              <ArrowRight size={12} />
            </Link>
          }
          delay={80}
        >
          {a.rows.length ? (
            <Table kartuPonsel>
              <thead>
                <tr>
                  <Th>{t("c.item")}</Th>
                  <Th>{t("c.warehouse")}</Th>
                  {/* Judul kolom yang SAMA PERSIS dengan halaman Pemesanan
                      Ulang, karena isinya memang angka yang sama: stok
                      tersedia, yaitu yang dibandingkan mesin terhadap titik
                      pesan efektif di kolom sebelahnya. */}
                  <Th align="right">{t("rl.col.stock")}</Th>
                  <Th align="right">{t("rl.col.rop")}</Th>
                  <Th align="right">{t("rl.col.qty")}</Th>
                  <Th>{t("c.status")}</Th>
                </tr>
              </thead>
              <tbody>
                {a.rows.map((r) => (
                  <tr key={`${r.sku}-${r.warehouse_code}`}>
                    <Td>
                      <div className="font-medium text-ink">{r.item_name}</div>
                      <div className="text-xs text-muted">{r.sku}</div>
                    </Td>
                    <Td>{r.warehouse_code}</Td>
                    <Td align="right" numeric>
                      <span
                        className="font-semibold"
                        style={{ color: AKSI[r.status as keyof typeof AKSI]?.warna ?? "var(--text-primary)" }}
                      >
                        {num(r.current_stock)}
                      </span>
                    </Td>
                    <Td align="right" numeric>
                      {num(r.reorder_point)}
                    </Td>
                    <Td align="right" numeric>
                      {/* null berarti belum dapat dihitung, bukan nol -- nol
                          akan berbunyi "tidak perlu dipesan". */}
                      {r.recommended_order_qty === null ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <span className="font-semibold text-ink">
                          {num(r.recommended_order_qty)}
                          {r.unit_code ? ` ${r.unit_code}` : ""}
                        </span>
                      )}
                    </Td>
                    <Td>
                      <PillAksi status={r.status} label={r.status_label} padat />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <Empty message={t("dash.attention_empty")} />
          )}
        </Card>
      </div>

      {/* ---------- 3: apa yang diprakirakan terjadi ---------- */}
      {f.horizon_days !== null && (
        <div className="mt-4">
          <Card
            icon={<TrendingUp size={15} />}
            title={t("dash.forecast", { n: num(f.horizon_days) })}
            subtitle={t("dash.forecast_sub")}
            right={
              <Link
                href="/forecasting"
                className="inline-flex items-center gap-1 text-xs font-semibold"
                style={{ color: "var(--brand)" }}
              >
                {t("dash.forecast_open")}
                <ArrowRight size={12} />
              </Link>
            }
            delay={80}
          >
            <div className="grid gap-5 sm:grid-cols-3">
              <AngkaPrakiraan label={t("dash.forecast.usage")} nilai={num(f.forecast_usage)} />
              <AngkaPrakiraan
                label={t("dash.forecast.qty")}
                nilai={num(f.recommended_order_qty)}
              />
              <AngkaPrakiraan
                label={t("dash.forecast.stockout", { n: num(f.horizon_days) })}
                nilai={num(f.projected_stockout)}
                warna={f.projected_stockout > 0 ? AKSI.RISIKO_STOCKOUT.warna : undefined}
              />
            </div>
            {/* Barang yang belum dapat diprakirakan disebutkan, tidak
                dibulatkan menjadi nol di dalam angka-angka di atas. */}
            {f.without_forecast > 0 && (
              <p className="mt-4 text-xs text-muted">
                {t("dash.forecast.unknown", { n: num(f.without_forecast) })}
              </p>
            )}
          </Card>
        </div>
      )}

      <p className="mt-4 text-xs text-muted">{d.value_basis}</p>
      {d.truncated && (
        <p className="mt-1 text-xs" style={{ color: "var(--status-serious)" }}>
          {t("dash.truncated")}
        </p>
      )}
    </>
  );
}

function AngkaPrakiraan({
  label,
  nilai,
  warna,
}: {
  label: string;
  nilai: string;
  warna?: string;
}) {
  return (
    <div>
      <div className="t-micro font-semibold uppercase tracking-[0.07em] text-muted">
        {label}
      </div>
      <div
        className="stat-figure mt-1.5 text-[22px] font-bold leading-none"
        style={{ color: warna ?? "var(--text-primary)" }}
      >
        {nilai}
      </div>
    </div>
  );
}
