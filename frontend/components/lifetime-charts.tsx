"use client";

/**
 * Grafik Analisis Umur Pakai: SATU KOMPONEN, DUA GARIS.
 *
 * Grafik ini dibuka per baris dari tabel (kolom "Grafik"). Perbandingan lintas
 * komponen dibaca dari tabelnya; menggabungkan semua komponen ke satu grafik
 * pernah dicoba (6 Oktober 2026) dan dibatalkan -- yang ingin dilihat adalah
 * riwayat tiap barang, masing-masing.
 *
 * TIDAK ADA RUMUS DI SINI. Umur tiap unit, standar, dan status seluruhnya
 * datang jadi dari /api/lifetime; berkas ini hanya menempatkannya pada sumbu.
 */

import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { WARNA_STATUS } from "@/components/lifetime-sections";
import { dateLabel, num } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { KejadianPenggantian } from "@/lib/lifetime-types";

const SUMBU_TEKS = { fontSize: 11, fill: "var(--text-muted)" };
const WARNA_STANDAR = "var(--text-muted)";
const WARNA_AKTUAL = "var(--brand)";

/**
 * Umur standar dan umur aktual tiap unit yang pernah terpasang, berurutan
 * waktu.
 *
 * Garis STANDAR datar: standarnya satu angka untuk komponen itu. Garis AKTUAL
 * punya satu titik per penggantian, tingginya = berapa hari unit yang
 * digantikan itu bertahan. Di bawah garis standar berarti unit itu diganti
 * lebih cepat, di atasnya berarti bertahan lebih lama.
 *
 * Kejadian pertama tidak digambar: ia tidak punya pendahulu, jadi umurnya
 * tidak diketahui -- bukan nol.
 */
export function GrafikRiwayatPenggantian({
  kejadian,
  harapan,
}: {
  /** terbaru lebih dulu, seperti yang dikirim backend */
  kejadian: KejadianPenggantian[];
  harapan: number;
}) {
  const t = useT();
  const titik = kejadian
    .filter((e) => e.lifetime_days !== null)
    .slice()
    .reverse()
    .map((e) => ({ ...e, standar: harapan }));
  if (!titik.length) return null;

  const nilai = titik.map((e) => e.lifetime_days as number);
  const min = Math.min(harapan, ...nilai);
  const maks = Math.max(harapan, ...nilai);
  const jeda = Math.max(1, (maks - min) * 0.2, harapan * 0.1);

  return (
    <div>
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={titik} margin={{ top: 14, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="date"
            tick={SUMBU_TEKS}
            tickLine={false}
            axisLine={{ stroke: "var(--border)" }}
            tickFormatter={(v: string) => dateLabel(v)}
            minTickGap={28}
            padding={{ left: 14, right: 14 }}
          />
          <YAxis
            tick={SUMBU_TEKS}
            tickLine={false}
            axisLine={false}
            width={48}
            domain={[Math.max(0, Math.floor(min - jeda)), Math.ceil(maks + jeda)]}
            tickFormatter={(v: number) => num(v)}
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
                  <div className="mt-1.5 flex items-center gap-2">
                    <span className="h-[2px] w-3" style={{ background: WARNA_STANDAR }} />
                    {t("lt.chart.standard")}: {num(harapan)} {t("lt.unit.days")}
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="h-[2px] w-3" style={{ background: WARNA_AKTUAL }} />
                    {t("lt.chart.actual")}: {num(e.lifetime_days)} {t("lt.unit.days")}
                  </div>
                  {e.status_label && <div className="mt-1 text-muted">{e.status_label}</div>}
                </div>
              );
            }}
          />
          <Line
            type="linear"
            dataKey="standar"
            stroke={WARNA_STANDAR}
            strokeWidth={2}
            strokeDasharray="5 4"
            isAnimationActive={false}
            dot={false}
            activeDot={false}
          />
          <Line
            type="linear"
            dataKey="lifetime_days"
            stroke={WARNA_AKTUAL}
            strokeWidth={2}
            isAnimationActive={false}
            dot={(p: any) => {
              const e = p.payload as KejadianPenggantian;
              return (
                <circle
                  key={e.id}
                  cx={p.cx}
                  cy={p.cy}
                  r={4.5}
                  fill={e.status ? WARNA_STATUS[e.status] : WARNA_AKTUAL}
                  stroke="var(--surface-1)"
                  strokeWidth={2}
                />
              );
            }}
            activeDot={{ r: 6, stroke: "var(--surface-1)", strokeWidth: 2 }}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1.5 t-caption text-ink-2">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-5 border-t-2 border-dashed" style={{ borderColor: WARNA_STANDAR }} />
          {t("lt.chart.legend_standard", { n: num(harapan) })}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-[2px] w-5" style={{ background: WARNA_AKTUAL }} />
          {t("lt.chart.legend_actual")}
        </span>
      </div>
      <p className="mt-1.5 t-caption text-muted">{t("lt.chart.history_note")}</p>
    </div>
  );
}
