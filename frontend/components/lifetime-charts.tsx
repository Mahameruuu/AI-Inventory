"use client";

/**
 * Grafik Analisis Umur Pakai.
 *
 * SATU PERTANYAAN, DUA SKALA: apakah komponen bertahan sesuai standarnya.
 *
 *   GrafikUmurPakai           seluruh komponen sekaligus -- umur aktual tiap
 *                             komponen terhadap standarnya sendiri.
 *   GrafikRiwayatPenggantian  satu komponen -- umur tiap unit yang pernah
 *                             terpasang, terhadap standar dan pita wajarnya.
 *
 * TIDAK ADA RUMUS DI SINI. Simpangan, batas pita, dan status seluruhnya datang
 * jadi dari /api/lifetime; berkas ini hanya menempatkannya pada sumbu.
 */

import { Fragment, ReactNode } from "react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { LencanaStatus, Simpangan, WARNA_STATUS } from "@/components/lifetime-sections";
import { dateLabel, num } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { BarisUmurPakai, KejadianPenggantian, StatusUmur } from "@/lib/lifetime-types";

/* ------------------------------------------------------------------ */
/* Standar vs aktual, seluruh komponen                                 */
/* ------------------------------------------------------------------ */

/** Lebar sumbu paling sempit (±%): pita wajar tidak boleh memenuhi seluruh lajur. */
const SUMBU_MIN = 30;
/** Lebar sumbu paling lebar (±%); yang melampauinya ditempel di tepi. */
const SUMBU_MAKS = 100;

/**
 * Umur aktual tiap komponen sebagai SIMPANGAN dari standarnya sendiri.
 *
 * SUMBUNYA PERSEN, BUKAN HARI, dan itu yang membuat grafik ini mungkin: filter
 * oli berstandar 78 hari dan bantalan berstandar 20 tahun tidak dapat berbagi
 * sumbu hari -- yang pertama akan menjadi titik di tepi kiri. Terhadap
 * standarnya masing-masing keduanya sebanding: garis tengah adalah "tepat
 * sesuai standar" untuk setiap baris, kiri berarti diganti lebih cepat, kanan
 * berarti bertahan lebih lama. Angka harinya tetap tercetak di kanan baris.
 *
 * Pita di tengah adalah rentang wajar (± toleransi). Titik di dalamnya tidak
 * menuntut apa-apa; yang layak dibaca adalah titik di luarnya, dan seberapa
 * jauh.
 */
export function GrafikUmurPakai({
  baris,
  toleransi,
  terpilih,
  onPilih,
  rincian = null,
}: {
  /** isi yang terbuka tepat di bawah baris terpilih */
  rincian?: ReactNode;
  baris: BarisUmurPakai[];
  /** setengah lebar pita wajar, dalam persen (15 berarti ±15%) */
  toleransi: number;
  terpilih: string | null;
  onPilih: (b: BarisUmurPakai) => void;
}) {
  const t = useT();

  const terjauh = Math.max(
    0,
    ...baris.map((b) => Math.abs(b.deviation_percentage ?? 0)),
  );
  const sumbu = Math.min(
    SUMBU_MAKS,
    Math.max(SUMBU_MIN, Math.ceil((terjauh + 5) / 10) * 10),
  );
  const pos = (persen: number) =>
    50 + (Math.max(-sumbu, Math.min(sumbu, persen)) / sumbu) * 50;
  const tik = [-sumbu, -sumbu / 2, 0, sumbu / 2, sumbu];

  const kisi = "grid items-center gap-x-5 sm:grid-cols-[minmax(0,14rem)_minmax(0,1fr)_9.5rem_9.5rem]";

  return (
    <div>
      {/* --- kepala sumbu --- */}
      <div className={`${kisi} pb-1`}>
        <div className="hidden sm:block" />
        <div>
          <div className="flex justify-between t-caption text-muted">
            <span>← {t("lt.chart.faster")}</span>
            <span>{t("lt.chart.longer")} →</span>
          </div>
          <div className="relative mt-1 h-4">
            {tik.map((v) => (
              <span
                key={v}
                className="tnum absolute -translate-x-1/2 whitespace-nowrap t-caption"
                style={{
                  left: `${pos(v)}%`,
                  color: v === 0 ? "var(--text-secondary)" : "var(--text-muted)",
                  fontWeight: v === 0 ? 600 : 400,
                  // Label tepi ditarik ke dalam supaya tidak terpotong.
                  transform:
                    v === -sumbu ? "translateX(0)" : v === sumbu ? "translateX(-100%)" : undefined,
                }}
              >
                {v === 0 ? t("lt.chart.standard") : `${v > 0 ? "+" : "−"}${Math.abs(v)}%`}
              </span>
            ))}
          </div>
        </div>
        <div className="hidden sm:col-span-2 sm:block" />
      </div>

      {/* --- satu lajur per komponen --- */}
      <div>
        {baris.map((b) => {
          const kunci = `${b.item.id}-${b.warehouse.id}`;
          const dev = b.deviation_percentage;
          const terukur = dev !== null && b.actual_lifetime_days !== null;
          const warna = WARNA_STATUS[b.status];
          const keluar = terukur && Math.abs(dev!) > sumbu;
          const x = terukur ? pos(dev!) : 50;

          return (
            <Fragment key={kunci}>
            <button
              type="button"
              onClick={() => onPilih(b)}
              title={b.basis}
              aria-pressed={terpilih === kunci}
              className={`${kisi} w-full rounded-lg border-t px-2 py-2 text-left transition hover:bg-[var(--surface-sunken)]`}
              style={{
                borderColor: "var(--border)",
                background:
                  terpilih === kunci
                    ? "color-mix(in srgb, var(--brand) 7%, transparent)"
                    : undefined,
              }}
            >
              <div className="min-w-0">
                <div className="truncate font-medium text-ink">{b.item.name}</div>
                <div className="truncate text-xs text-muted">
                  {b.item.sku} · {b.warehouse.code}
                </div>
              </div>

              {/* lajur */}
              <div
                className="relative my-1 h-8 overflow-hidden rounded-md sm:my-0"
                style={{ background: "color-mix(in srgb, var(--text-muted) 7%, transparent)" }}
              >
                {/* pita wajar */}
                <div
                  className="absolute inset-y-0"
                  style={{
                    left: `${pos(-toleransi)}%`,
                    width: `${pos(toleransi) - pos(-toleransi)}%`,
                    background: `color-mix(in srgb, ${WARNA_STATUS.NORMAL} 13%, transparent)`,
                  }}
                />
                {/* garis bantu */}
                {[-sumbu / 2, sumbu / 2].map((v) => (
                  <div
                    key={v}
                    className="absolute inset-y-0 w-px"
                    style={{ left: `${pos(v)}%`, background: "var(--border)" }}
                  />
                ))}
                {/* standar */}
                <div
                  className="absolute inset-y-0 w-[2px] -translate-x-1/2"
                  style={{ left: "50%", background: "var(--text-muted)" }}
                />
                {terukur ? (
                  <>
                    {/* tangkai: dari standar ke aktual */}
                    <div
                      className="absolute top-1/2 h-[4px] -translate-y-1/2 rounded-full"
                      style={{
                        left: `${Math.min(50, x)}%`,
                        width: `${Math.abs(x - 50)}%`,
                        background: warna,
                        opacity: 0.55,
                      }}
                    />
                    {/* aktual */}
                    <span
                      className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full"
                      style={{
                        left: `${x}%`,
                        background: warna,
                        boxShadow: "0 0 0 2px var(--surface-1)",
                      }}
                    />
                    {/* di luar sumbu: titiknya di tepi, panahnya mengakuinya */}
                    {keluar && (
                      <span
                        className="absolute top-1/2 -translate-y-1/2 t-caption font-bold"
                        style={{ [dev! > 0 ? "right" : "left"]: "10px", color: warna }}
                        aria-hidden
                      >
                        {dev! > 0 ? "»" : "«"}
                      </span>
                    )}
                  </>
                ) : (
                  <span
                    className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded px-1.5 t-caption text-muted"
                    style={{ background: "var(--surface-1)" }}
                  >
                    {t("lt.unmeasured")}
                  </span>
                )}
              </div>

              {/* angka: aktual, standar, simpangan */}
              <div className="sm:text-right">
                {terukur ? (
                  <div className="leading-tight">
                    <span className="tnum font-semibold text-ink">
                      {num(b.actual_lifetime_days)} {t("lt.unit.days")}
                    </span>{" "}
                    <Simpangan nilai={dev} status={b.status} />
                    <div className="tnum t-caption text-muted">
                      {t("lt.chart.of_standard", { n: num(b.expected_lifetime_days) })}
                    </div>
                  </div>
                ) : (
                  <div className="tnum t-caption text-muted">
                    {b.has_reference
                      ? t("lt.chart.of_standard", { n: num(b.expected_lifetime_days) })
                      : t("lt.chart.no_standard")}
                  </div>
                )}
              </div>
              <div className="mt-1 sm:mt-0">
                <LencanaStatus status={b.status} label={b.status_label} />
              </div>
            </button>
            {terpilih === kunci && rincian && (
              <div
                className="mb-2 rounded-xl px-4 py-5 sm:px-6"
                style={{ background: "var(--surface-sunken)" }}
              >
                {rincian}
              </div>
            )}
            </Fragment>
          );
        })}
      </div>

      {/* --- legenda --- */}
      <div
        className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t pt-3 t-caption text-ink-2"
        style={{ borderColor: "var(--border)" }}
      >
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-[2px]" style={{ background: "var(--text-muted)" }} />
          {t("lt.chart.legend_standard")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span
            className="h-3 w-5 rounded-sm"
            style={{ background: `color-mix(in srgb, ${WARNA_STATUS.NORMAL} 22%, transparent)` }}
          />
          {t("lt.chart.legend_band", { n: num(toleransi) })}
        </span>
        {(["PREMATURE", "NORMAL", "EXTENDED"] as StatusUmur[]).map((s) => (
          <span key={s} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: WARNA_STATUS[s] }} />
            {t(`lt.status.${s}`)}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Riwayat satu komponen                                               */
/* ------------------------------------------------------------------ */

const SUMBU_TEKS = { fontSize: 11, fill: "var(--text-muted)" };

/**
 * Umur tiap unit yang pernah terpasang, berurutan waktu.
 *
 * Satu titik = satu penggantian, tingginya = berapa hari unit yang digantikan
 * itu bertahan. Garis putus-putus adalah standarnya dan pita di sekitarnya
 * rentang wajar, jadi tiga hal terbaca sekaligus: unit mana yang gugur dini,
 * seberapa jauh, dan apakah arahnya memburuk dari waktu ke waktu.
 *
 * Kejadian pertama tidak digambar: ia tidak punya pendahulu, jadi umurnya
 * tidak diketahui -- bukan nol.
 */
export function GrafikRiwayatPenggantian({
  kejadian,
  bawah,
  harapan,
  atas,
}: {
  /** terbaru lebih dulu, seperti yang dikirim backend */
  kejadian: KejadianPenggantian[];
  bawah: number;
  harapan: number;
  atas: number;
}) {
  const t = useT();
  const titik = kejadian
    .filter((e) => e.lifetime_days !== null)
    .slice()
    .reverse();
  if (!titik.length) return null;

  const nilai = titik.map((e) => e.lifetime_days as number);
  const min = Math.min(bawah, ...nilai);
  const maks = Math.max(atas, ...nilai);
  const jeda = Math.max(1, (maks - min) * 0.12);

  return (
    <div>
      <ResponsiveContainer width="100%" height={210}>
        <ComposedChart data={titik} margin={{ top: 14, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="date"
            tick={SUMBU_TEKS}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
            tickFormatter={(v: string) => String(new Date(v).getFullYear())}
            minTickGap={28}
            padding={{ left: 14, right: 14 }}
          />
          <YAxis
            tick={SUMBU_TEKS}
            tickLine={false}
            axisLine={false}
            width={44}
            domain={[Math.max(0, Math.floor(min - jeda)), Math.ceil(maks + jeda)]}
            tickFormatter={(v: number) => num(v)}
          />
          <ReferenceArea
            y1={bawah}
            y2={atas}
            fill={WARNA_STATUS.NORMAL}
            fillOpacity={0.12}
            stroke="none"
          />
          <ReferenceLine
            y={harapan}
            stroke="var(--text-secondary)"
            strokeDasharray="4 4"
            strokeWidth={1.5}
            label={{
              value: t("lt.chart.standard_days", { n: num(harapan) }),
              position: "insideTopRight",
              fontSize: 10.5,
              fontWeight: 600,
              fill: "var(--text-secondary)",
            }}
          />
          <Tooltip
            cursor={{ stroke: "var(--border)" }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const e = payload[0].payload as KejadianPenggantian;
              return (
                <div
                  className="rounded-xl px-3.5 py-2.5 text-xs"
                  style={{
                    background: "var(--surface-1)",
                    boxShadow: "var(--elev-2), inset 0 0 0 1px var(--border)",
                    color: "var(--text-primary)",
                  }}
                >
                  <div className="font-semibold">{dateLabel(e.date)}</div>
                  <div className="mt-1 flex items-center gap-2">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: e.status ? WARNA_STATUS[e.status] : "var(--text-muted)" }}
                    />
                    {t("lt.detail.col_lifetime")}: {num(e.lifetime_days)} {t("lt.unit.days")}
                  </div>
                  <div className="mt-1 text-muted">
                    {t("lt.chart.standard_days", { n: num(harapan) })}
                    {e.status_label ? ` · ${e.status_label}` : ""}
                  </div>
                </div>
              );
            }}
          />
          <Line
            type="linear"
            dataKey="lifetime_days"
            stroke="var(--text-muted)"
            strokeWidth={1.5}
            isAnimationActive={false}
            dot={(p: any) => {
              const e = p.payload as KejadianPenggantian;
              return (
                <circle
                  key={e.id}
                  cx={p.cx}
                  cy={p.cy}
                  r={4.5}
                  fill={e.status ? WARNA_STATUS[e.status] : "var(--text-muted)"}
                  stroke="var(--surface-1)"
                  strokeWidth={2}
                />
              );
            }}
            activeDot={{ r: 6, stroke: "var(--surface-1)", strokeWidth: 2 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="mt-1 t-caption text-muted">{t("lt.chart.history_note")}</p>
    </div>
  );
}
