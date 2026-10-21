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
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { WARNA_STATUS } from "@/components/lifetime-sections";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

import { dateLabel, num } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { KejadianPenggantian } from "@/lib/lifetime-types";

const SUMBU_TEKS = { fontSize: 11, fill: "var(--text-muted)" };
const WARNA_STANDAR = "var(--text-muted)";
const WARNA_AKTUAL = "var(--brand)";
/** Batas & area di luar batas: merah muda, supaya titik yang keluar langsung terlihat. */
const WARNA_BATAS = "#e11d48";
const WARNA_ZONA = "rgba(244, 114, 182, 0.16)";

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
  bawah,
  atas,
}: {
  /** terbaru lebih dulu, seperti yang dikirim backend */
  kejadian: KejadianPenggantian[];
  harapan: number;
  bawah: number;
  atas: number;
}) {
  const t = useT();
  const titik = kejadian
    .filter((e) => e.lifetime_days !== null)
    .slice()
    .reverse()
    .map((e) => ({ ...e, standar: harapan }));
  if (!titik.length) return null;

  const nilai = titik.map((e) => e.lifetime_days as number);
  const min = Math.min(bawah, ...nilai);
  const maks = Math.max(atas, ...nilai);
  const jeda = Math.max(1, (maks - min) * 0.2, harapan * 0.1);
  const yMin = Math.max(0, Math.floor(min - jeda));
  const yMaks = Math.ceil(maks + jeda);
  const keluar = (v: number) => v < bawah || v > atas;
  // Terbaru lebih dulu: yang paling baru paling perlu ditindaklanjuti.
  const peringatan = titik.filter((e) => keluar(e.lifetime_days as number)).reverse();

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
            domain={[yMin, yMaks]}
            tickFormatter={(v: number) => num(v)}
          />
          {/* Area di luar batas diarsir merah muda. */}
          <ReferenceArea y1={yMin} y2={bawah} fill={WARNA_ZONA} stroke="none" ifOverflow="hidden" />
          <ReferenceArea y1={atas} y2={yMaks} fill={WARNA_ZONA} stroke="none" ifOverflow="hidden" />
          <ReferenceLine y={bawah} stroke={WARNA_BATAS} strokeWidth={1.5} strokeDasharray="3 3" />
          <ReferenceLine y={atas} stroke={WARNA_BATAS} strokeWidth={1.5} strokeDasharray="3 3" />
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
                    <span className="h-[2px] w-3" style={{ background: WARNA_BATAS }} />
                    {num(bawah)}–{num(atas)} {t("lt.unit.days")}
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
              const luar = keluar(e.lifetime_days as number);
              return (
                <circle
                  key={e.id}
                  cx={p.cx}
                  cy={p.cy}
                  r={luar ? 6 : 4.5}
                  fill={luar ? WARNA_BATAS : e.status ? WARNA_STATUS[e.status] : WARNA_AKTUAL}
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
        <span className="inline-flex items-center gap-1.5">
          <span className="w-5 border-t-2 border-dashed" style={{ borderColor: WARNA_BATAS }} />
          {t("lt.chart.lower", { n: num(bawah) })} · {t("lt.chart.upper", { n: num(atas) })}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-5 rounded-sm" style={{ background: WARNA_ZONA, boxShadow: `inset 0 0 0 1px ${WARNA_BATAS}55` }} />
          {t("lt.chart.outside_zone")}
        </span>
      </div>
      <p className="mt-1.5 t-caption text-muted">{t("lt.chart.history_note")}</p>

      {/* Log tindak lanjut: tiap titik yang keluar batas jadi satu pesan. */}
      {peringatan.length > 0 ? (
        <div
          className="mt-3 rounded-xl px-3.5 py-3"
          style={{ background: "rgba(244, 114, 182, 0.10)", boxShadow: `inset 0 0 0 1px ${WARNA_BATAS}40` }}
        >
          <div className="flex items-center gap-1.5 t-small font-semibold" style={{ color: WARNA_BATAS }}>
            <AlertTriangle size={14} aria-hidden />
            {t("lt.alert.title", { n: num(peringatan.length) })}
          </div>
          <ul className="mt-2 max-h-48 space-y-1.5 overflow-y-auto t-small text-ink-2">
            {peringatan.map((e) => {
              const v = e.lifetime_days as number;
              const dibawah = v < bawah;
              return (
                <li key={e.id} className="flex gap-2">
                  <span className="mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: WARNA_BATAS }} />
                  {t(dibawah ? "lt.alert.below" : "lt.alert.above", {
                    date: dateLabel(e.date),
                    doc: e.document,
                    n: num(v),
                    b: num(dibawah ? bawah : atas),
                  })}
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <div className="mt-3 inline-flex items-center gap-1.5 t-small" style={{ color: WARNA_STATUS.NORMAL }}>
          <CheckCircle2 size={14} aria-hidden />
          {t("lt.alert.none")}
        </div>
      )}
    </div>
  );
}
