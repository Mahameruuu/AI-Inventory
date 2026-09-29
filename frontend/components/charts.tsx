"use client";

/**
 * Komponen grafik / chart components.
 *
 * Kaidah yang dipegang (tetap, meski tampilannya kini berdimensi):
 *  - satu sumbu Y saja (tidak pernah dua skala pada satu plot);
 *  - grid & sumbu berupa hairline solid, tidak pernah bersaing dengan datanya;
 *  - legenda muncul bila deret >= 2; satu deret cukup diberi judul;
 *  - setiap nilai juga tersedia lewat tabel di halaman yang sama.
 *
 * KEDALAMAN DIPAKAI SEBAGAI GAYA, BUKAN SEBAGAI DATA. Ketebalan cakram,
 * kilau silinder, dan bayangan tidak pernah membawa nilai; seluruh besaran
 * tetap dibaca dari panjang, sudut, atau posisi. Dengan begitu tampilan yang
 * pantas dibawa ke ruang pitching tidak menukar ketepatan dengan kesan.
 *
 * DEPTH IS STYLING, NEVER DATA. Disc thickness, cylinder gloss and shadows
 * carry no value; every magnitude is still read from length, angle or
 * position -- so a deck-worthy look never trades accuracy for impression.
 */

import { CSSProperties, ReactNode, useId } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useT } from "@/lib/i18n";
import { dateLabel, monthLabel, num, shortDate } from "@/lib/format";

const AXIS = { fontSize: 11, fill: "var(--text-muted)" };

/** Id yang aman dipakai di url(#…) — useId membawa titik dua. */
function useGradId(prefix: string): string {
  return `${prefix}-${useId().replace(/:/g, "")}`;
}

function TooltipBox({ children }: { children: ReactNode }) {
  return (
    <div
      className="rounded-xl px-3.5 py-2.5 text-xs"
      style={{
        background: "var(--surface-1)",
        boxShadow: "var(--elev-2), inset 0 0 0 1px var(--border)",
        color: "var(--text-primary)",
      }}
    >
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Batang horizontal 3D                                                */
/* ------------------------------------------------------------------ */

/**
 * Satu deret, batang membulat bergradien -- terbaca sebagai silinder: kilau di
 * sisi atas, bayangan di sisi bawah, dan bayang jatuh tipis di bawah batang.
 * Panjangnya tetap satu-satunya pembawa nilai.
 *
 * Warna per baris hanya dipakai bila kategorinya BERURUTAN (ramp ordinal),
 * bukan untuk membedakan identitas.
 */
export function HBar({
  data,
  height = 260,
  valueFormatter = (v: number) => num(v),
  colorKey,
  labelWidth = 150,
  valueWidth = 96,
  showRank = false,
}: {
  /** `display` menimpa teks nilai -- dipakai bila angka perlu membawa tanda +/− */
  data: { label: string; value: number; color?: string; display?: string }[];
  height?: number;
  valueFormatter?: (v: number) => string;
  colorKey?: boolean;
  labelWidth?: number;
  /** lebar kolom nilai; perlu dilebarkan bila teksnya panjang */
  valueWidth?: number;
  /** nomor urut di kiri label; berguna saat daftarnya memang peringkat */
  showRank?: boolean;
}) {
  const max = Math.max(1, ...data.map((d) => Number(d.value) || 0));

  return (
    <div className="flex flex-col gap-3" style={{ minHeight: height }}>
      {data.map((d, i) => {
        const warna = colorKey && d.color ? d.color : "var(--series-1)";
        const lebar = Math.max(1.5, (Number(d.value) / max) * 100);
        return (
          <div key={d.label} className="group flex items-center gap-3">
            {showRank && (
              <span
                aria-hidden
                className="tnum flex h-5 w-5 shrink-0 items-center justify-center rounded-lg t-micro font-bold"
                style={{
                  background: "var(--surface-sunken)",
                  color: "var(--text-muted)",
                }}
              >
                {i + 1}
              </span>
            )}
            <div
              className="shrink-0 truncate text-xs font-medium text-ink-2"
              style={{ width: labelWidth }}
              title={d.label}
            >
              {d.label}
            </div>

            <div className="bar-track relative h-3.5 flex-1">
              <div
                className="bar3d h-3.5"
                style={
                  {
                    width: `${lebar}%`,
                    "--bar-color": warna,
                    animationDelay: `${i * 70}ms`,
                  } as CSSProperties
                }
              />
            </div>

            <div
              className="tnum shrink-0 whitespace-nowrap text-right text-xs font-semibold text-ink"
              style={{ width: valueWidth }}
            >
              {d.display ?? valueFormatter(Number(d.value) || 0)}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Cakram 3D / 3D donut                                                */
/* ------------------------------------------------------------------ */

export interface Segmen {
  label: string;
  value: number;
  color: string;
}

/**
 * Cakram berlapis yang dimiringkan.
 *
 * Ketebalannya dibentuk dari belasan salinan cincin yang dipisahkan pada sumbu
 * Z, lalu seluruh tumpukan dimiringkan sekali. Yang paling atas berwarna
 * penuh, lapisan di bawahnya digelapkan sehingga terbaca sebagai dinding
 * samping cakram.
 *
 * Nilainya sendiri tetap dibaca dari SUDUT, dan setiap segmen selalu disertai
 * label serta angka di legenda -- ketebalan tidak pernah ikut bicara.
 */
export function Donut3D({
  segments,
  size = 200,
  thickness = 26,
  depth = 16,
  tilt = 56,
  centerValue,
  centerLabel,
}: {
  segments: Segmen[];
  size?: number;
  /** tebal cincin (jari-jari luar dikurangi dalam) */
  thickness?: number;
  /** tinggi ekstrusi dalam piksel */
  depth?: number;
  /** kemiringan pandang dalam derajat */
  tilt?: number;
  centerValue?: string;
  centerLabel?: string;
}) {
  const total = segments.reduce((a, s) => a + Math.max(0, s.value), 0);
  const r = (size - thickness) / 2;
  const keliling = 2 * Math.PI * r;

  // Tanpa data, cincin digambar sebagai lingkaran netral: piringan kosong
  // lebih jujur daripada satu segmen penuh berwarna yang tidak mewakili apa pun.
  const potongan =
    total > 0
      ? segments
      : [{ label: "", value: 1, color: "var(--gridline)" }];
  const jumlah = total > 0 ? total : 1;

  let jalan = 0;
  const arcs = potongan.map((s, i) => {
    const panjang = (Math.max(0, s.value) / jumlah) * keliling;
    const offset = -jalan;
    jalan += panjang;
    return { ...s, panjang, offset, i };
  });

  const lapisan = Array.from({ length: depth }, (_, i) => i);

  /*
   * Tinggi TAMPAK cakram setelah dimiringkan, bukan tinggi SVG-nya.
   *
   * Lingkaran selebar `size` yang dimiringkan sejauh `tilt` hanya menempati
   * size × cos(tilt) piksel di layar. Bila kotaknya tetap setinggi `size`,
   * separuh ruang di atas cakram menganga kosong sementara sisi bawahnya
   * menabrak legenda. Karena itu kotaknya dipotong ke tinggi tampak, dan
   * lapisan SVG-nya digeser ke atas sebanyak selisihnya.
   */
  const cos = Math.cos((tilt * Math.PI) / 180);
  const tinggiTampak = size * cos;
  const geser = (size - tinggiTampak) / 2;

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: tinggiTampak + depth + 10 }}>
        <div
          className="absolute inset-x-0 overflow-visible"
          style={{ perspective: "900px", height: size, top: -geser }}
        >
          <div
            className="relative"
            style={{
              width: size,
              height: size,
              transform: `rotateX(${tilt}deg)`,
              transformStyle: "preserve-3d",
            }}
          >
            {lapisan.map((z) => {
              const atas = z === depth - 1;
              return (
                <svg
                  key={z}
                  width={size}
                  height={size}
                  viewBox={`0 0 ${size} ${size}`}
                  className="absolute inset-0"
                  style={{ transform: `translateZ(${z * (depth / 14)}px)` }}
                  aria-hidden={!atas}
                >
                  <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
                    {arcs.map((a) => (
                      <circle
                        key={`${a.label}-${a.i}`}
                        cx={size / 2}
                        cy={size / 2}
                        r={r}
                        fill="none"
                        stroke={
                          atas
                            ? a.color
                            : `color-mix(in srgb, ${a.color} ${52 + (z / depth) * 26}%, #000)`
                        }
                        strokeWidth={thickness}
                        strokeDasharray={`${a.panjang} ${keliling - a.panjang}`}
                        strokeDashoffset={a.offset}
                      />
                    ))}
                  </g>
                </svg>
              );
            })}
          </div>
        </div>

        {/* Angka pusat berdiri TEGAK di luar tumpukan yang dimiringkan --
            teks yang ikut miring adalah hal pertama yang membuat grafik
            berdimensi terasa murahan sekaligus sulit dibaca. */}
        {(centerValue || centerLabel) && (
          <div
            className="pointer-events-none absolute inset-x-0 top-0 flex flex-col items-center justify-center"
            style={{ height: tinggiTampak }}
          >
            {centerValue && (
              <span className="stat-figure text-[21px] font-bold leading-none text-ink">
                {centerValue}
              </span>
            )}
            {centerLabel && (
              <span className="mt-1 t-micro font-semibold uppercase tracking-[0.08em] text-muted">
                {centerLabel}
              </span>
            )}
          </div>
        )}
      </div>

      {total > 0 && (
        <ul className="mt-3 flex flex-wrap justify-center gap-x-5 gap-y-2">
          {segments.map((s) => (
            <li key={s.label} className="flex items-center gap-2 text-xs">
              <span
                aria-hidden
                className="h-2.5 w-2.5 shrink-0 rounded-sm"
                style={{
                  background: s.color,
                  boxShadow: `0 2px 5px -2px ${s.color}, inset 0 1px 0 rgba(255,255,255,.45)`,
                }}
              />
              <span className="text-ink-2">{s.label}</span>
              <span className="tnum font-semibold text-ink">{num(s.value)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Meteran melengkung / arc gauge                                      */
/* ------------------------------------------------------------------ */

/**
 * Meteran setengah lingkaran.
 *
 * Alurnya cekung (bayangan ke dalam), jarumnya cembung dan bergradien --
 * pembacaan tetap dari PANJANG BUSUR, bayangannya hanya memisahkan jarum dari
 * alurnya supaya keduanya tidak menyatu saat diproyeksikan.
 */
export function Gauge3D({
  value,
  max = 100,
  label,
  caption,
  color = "var(--brand)",
  size = 190,
}: {
  value: number;
  max?: number;
  /** teks besar di tengah; bila kosong dipakai persentase */
  label?: string;
  caption?: string;
  color?: string;
  size?: number;
}) {
  const gid = useGradId("gauge");
  const rasio = max > 0 ? Math.min(1, Math.max(0, value / max)) : 0;
  const r = size / 2 - 16;
  const busur = Math.PI * r; // setengah lingkaran
  const tinggi = size / 2 + 26;

  return (
    <div className="flex flex-col items-center" style={{ width: size }}>
      <svg width={size} height={tinggi} viewBox={`0 0 ${size} ${tinggi}`} role="img">
        <defs>
          <linearGradient id={gid} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={`color-mix(in srgb, ${color} 55%, #fff)`} />
            <stop offset="100%" stopColor={color} />
          </linearGradient>
          <filter id={`${gid}-glow`} x="-30%" y="-30%" width="160%" height="160%">
            <feDropShadow dx="0" dy="4" stdDeviation="4" floodColor={color} floodOpacity="0.45" />
          </filter>
        </defs>

        {/* alur */}
        <path
          d={`M ${16} ${size / 2} A ${r} ${r} 0 0 1 ${size - 16} ${size / 2}`}
          fill="none"
          stroke="var(--surface-sunken)"
          strokeWidth={16}
          strokeLinecap="round"
        />
        <path
          d={`M ${16} ${size / 2} A ${r} ${r} 0 0 1 ${size - 16} ${size / 2}`}
          fill="none"
          stroke="var(--border)"
          strokeWidth={16}
          strokeLinecap="round"
          opacity={0.5}
        />

        {/* jarum */}
        <path
          d={`M ${16} ${size / 2} A ${r} ${r} 0 0 1 ${size - 16} ${size / 2}`}
          fill="none"
          stroke={`url(#${gid})`}
          strokeWidth={16}
          strokeLinecap="round"
          strokeDasharray={`${busur * rasio} ${busur}`}
          filter={`url(#${gid}-glow)`}
          style={{
            transition: "stroke-dasharray 900ms cubic-bezier(.16,1,.3,1)",
          }}
        />

        <text
          x={size / 2}
          y={size / 2 - 6}
          textAnchor="middle"
          className="stat-figure"
          style={{ fill: "var(--text-primary)", fontSize: 26, fontWeight: 700 }}
        >
          {label ?? `${Math.round(rasio * 100)}%`}
        </text>
        {caption && (
          <text
            x={size / 2}
            y={size / 2 + 14}
            textAnchor="middle"
            style={{
              fill: "var(--text-muted)",
              fontSize: 10.5,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
            }}
          >
            {caption}
          </text>
        )}
      </svg>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Saldo stok: histori + prakiraan, dengan garis titik pemesanan ulang  */
/* ------------------------------------------------------------------ */

export function StockForecastChart({
  historical,
  forecast,
  reorderPoint,
  unit = "",
  crossingDate = null,
  crossingLabel = "",
}: {
  historical: { date: string; stock: number }[];
  forecast: { date: string; stock: number }[];
  reorderPoint: number;
  unit?: string;
  /** tanggal saat proyeksi memotong titik pesan; dihitung backend */
  crossingDate?: string | null;
  /** mis. "±5 hari lagi" -- ditempel pada penanda perpotongan */
  crossingLabel?: string;
}) {
  const t = useT();
  const gid = useGradId("sf");

  // Titik terakhir histori disalin ke deret prakiraan supaya kedua garis
  // bersambung; tanpa itu akan tampak jeda di batas hari ini.
  const sambung = historical.length ? historical[historical.length - 1] : null;

  /*
   * Prakiraan dipecah dua di titik perpotongan dengan garis titik pesan.
   *
   * Setelah stok menembus titik pesan, proyeksi meneruskan pola pemakaian yang
   * sama seolah tidak ada yang bertindak -- padahal justru di situlah pesanan
   * seharusnya dibuat. Bagian itu digambar lebih pudar sebagai pengakuan bahwa
   * ia perkiraan yang paling lemah dasarnya, bukan ramalan setara.
   */
  const rows = [
    ...historical.map((h) => ({ label: h.date, aktual: h.stock })),
    ...(sambung && forecast.length ? [{ label: sambung.date, prakiraan: sambung.stock }] : []),
    ...forecast.map((f) => {
      if (!crossingDate) return { label: f.date, prakiraan: f.stock };
      if (f.date < crossingDate) return { label: f.date, prakiraan: f.stock };
      if (f.date === crossingDate)
        return { label: f.date, prakiraan: f.stock, lanjutan: f.stock };
      return { label: f.date, lanjutan: f.stock };
    }),
  ];

  // Gabungkan baris dengan tanggal sama supaya titik sambungan tidak dobel
  const gabung: any[] = [];
  rows.forEach((r) => {
    const ada = gabung.find((x) => x.label === r.label);
    if (ada) Object.assign(ada, r);
    else gabung.push({ ...r });
  });

  const batas = sambung?.date;

  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={gabung} margin={{ top: 16, right: 18, left: 4, bottom: 4 }}>
        <defs>
          {/* Isian gradien di bawah garis aktual: memberi bobot pada bagian
              yang benar-benar tercatat, tanpa menambah satu pun sumbu baru. */}
          <linearGradient id={`${gid}-area`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.34} />
            <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0} />
          </linearGradient>
          <filter id={`${gid}-glow`} x="-20%" y="-40%" width="140%" height="200%">
            <feDropShadow
              dx="0"
              dy="5"
              stdDeviation="5"
              floodColor="var(--series-1)"
              floodOpacity="0.35"
            />
          </filter>
          <filter id={`${gid}-glow2`} x="-20%" y="-40%" width="140%" height="200%">
            <feDropShadow
              dx="0"
              dy="5"
              stdDeviation="5"
              floodColor="var(--series-2)"
              floodOpacity="0.3"
            />
          </filter>
        </defs>

        <CartesianGrid stroke="var(--gridline)" strokeWidth={1} vertical={false} />
        <XAxis
          dataKey="label"
          tick={AXIS}
          tickLine={false}
          axisLine={{ stroke: "var(--axis)" }}
          minTickGap={28}
          tickFormatter={(v: string) => shortDate(v)}
        />
        {/* allowDecimals={false}: pada barang bersatuan kecil, recharts
            menyusun tik sumbu sendiri dan bisa menghasilkan "0,75" -- satu-
            satunya angka pecahan yang tersisa di halaman ini, dan justru yang
            paling tidak masuk akal (tidak ada setengah PCS di rak). */}
        <YAxis
          tick={AXIS}
          tickLine={false}
          axisLine={false}
          width={54}
          allowDecimals={false}
          tickFormatter={(v: number) => num(v)}
        />
        <Tooltip
          cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            const a = payload.find((p) => p.dataKey === "aktual");
            const f =
              payload.find((p) => p.dataKey === "prakiraan") ??
              payload.find((p) => p.dataKey === "lanjutan");
            return (
              <TooltipBox>
                <div className="font-semibold">{dateLabel(label as string)}</div>
                {a?.value != null && (
                  <div className="mt-1.5 flex items-center gap-2 text-ink-2">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: "var(--series-1)" }}
                    />
                    {t("fc.chart.actual_stock")}: {num(a.value as number)} {unit}
                  </div>
                )}
                {f?.value != null && (
                  <div className="mt-1 flex items-center gap-2 text-ink-2">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ background: "var(--series-2)" }}
                    />
                    {t("fc.chart.forecast_stock")}: {num(f.value as number)} {unit}
                  </div>
                )}
                <div className="mt-1.5 border-t pt-1.5 text-muted" style={{ borderColor: "var(--border)" }}>
                  {t("fc.chart.rop_short")}: {num(reorderPoint)} {unit}
                </div>
              </TooltipBox>
            );
          }}
        />
        <Legend
          height={28}
          iconType="plainline"
          wrapperStyle={{ fontSize: 11, color: "var(--text-secondary)" }}
        />

        <ReferenceLine
          y={reorderPoint}
          stroke="var(--status-critical)"
          strokeDasharray="4 4"
          strokeWidth={1.5}
          label={{
            value: t("fc.chart.rop_master", {
              v: `${num(reorderPoint)}${unit ? ` ${unit}` : ""}`,
            }),
            position: "insideTopRight",
            fontSize: 10.5,
            fontWeight: 600,
            fill: "var(--status-critical)",
          }}
        />
        {crossingDate && (
          <ReferenceDot
            x={crossingDate}
            y={reorderPoint}
            r={5.5}
            fill="var(--status-critical)"
            stroke="var(--surface-1)"
            strokeWidth={2.5}
            label={{
              value: crossingLabel,
              position: "top",
              offset: 12,
              fontSize: 10.5,
              fontWeight: 600,
              fill: "var(--status-critical)",
            }}
          />
        )}
        {/* Garis pembatas HARI INI, dan ia harus benar-benar terbaca sebagai
            pembatas. Sebelumnya garis tipis setipis gridline dengan label
            huruf kecil: pada layar penuh ia hilang di antara garis-garis
            bantu, sehingga batas antara yang TERCATAT dan yang DIRAMAL --
            satu-satunya pembagian yang menentukan seberapa jauh grafik ini
            boleh dipercaya -- tidak terlihat sama sekali. Putus-putus dan
            sewarna sumbu penuh membuatnya menonjol dari gridline tanpa
            bersaing dengan garis titik pesan yang merah. */}
        {batas && (
          <ReferenceLine
            x={batas}
            stroke="var(--text-muted)"
            strokeWidth={1.5}
            strokeDasharray="3 3"
            label={{
              value: t("fc.chart.today"),
              position: "top",
              fontSize: 10.5,
              fontWeight: 600,
              fill: "var(--text-secondary)",
            }}
          />
        )}

        <Area
          type="monotone"
          dataKey="aktual"
          stroke="none"
          fill={`url(#${gid}-area)`}
          legendType="none"
          isAnimationActive
          animationDuration={900}
          connectNulls={false}
          name={t("fc.chart.actual")}
        />
        <Line
          type="monotone"
          dataKey="aktual"
          name={t("fc.chart.actual")}
          stroke="var(--series-1)"
          strokeWidth={2.5}
          dot={false}
          filter={`url(#${gid}-glow)`}
          isAnimationActive
          animationDuration={1000}
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="prakiraan"
          name={t("fc.chart.forecast")}
          stroke="var(--series-2)"
          strokeWidth={2.5}
          strokeDasharray="5 4"
          dot={{ r: 2.5, strokeWidth: 0, fill: "var(--series-2)" }}
          filter={`url(#${gid}-glow2)`}
          isAnimationActive
          animationDuration={1100}
          connectNulls={false}
        />
        <Line
          type="monotone"
          dataKey="lanjutan"
          name={t("fc.chart.after_rop")}
          stroke="var(--series-2)"
          strokeOpacity={0.45}
          strokeWidth={2.5}
          strokeDasharray="5 4"
          dot={{ r: 2.5, strokeWidth: 0, fill: "var(--series-2)", fillOpacity: 0.45 }}
          isAnimationActive
          animationDuration={1200}
          connectNulls={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/* ------------------------------------------------------------------ */
/* Histori + ramalan -- dua deret, legenda wajib                        */
/* ------------------------------------------------------------------ */

export function ForecastChart({
  history,
  forecast,
}: {
  history: { period: string; qty: number }[];
  forecast: {
    period: string;
    forecast_qty: number;
    lower_bound: number;
    upper_bound: number;
  }[];
}) {
  const t = useT();
  const gid = useGradId("fc");

  const rows: any[] = history.map((h) => ({
    label: monthLabel(h.period),
    aktual: h.qty,
  }));
  // sambungkan garis: titik terakhir histori juga menjadi awal ramalan
  if (history.length && forecast.length) {
    rows[rows.length - 1].ramalan = history[history.length - 1].qty;
    rows[rows.length - 1].band = [
      history[history.length - 1].qty,
      history[history.length - 1].qty,
    ];
  }
  forecast.forEach((f) =>
    rows.push({
      label: monthLabel(f.period),
      ramalan: f.forecast_qty,
      band: [f.lower_bound, f.upper_bound],
    })
  );

  return (
    <ResponsiveContainer width="100%" height={280}>
      <ComposedChart data={rows} margin={{ top: 16, right: 18, left: 4, bottom: 4 }}>
        <defs>
          <linearGradient id={`${gid}-area`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--series-1)" stopOpacity={0.3} />
            <stop offset="100%" stopColor="var(--series-1)" stopOpacity={0} />
          </linearGradient>
          <filter id={`${gid}-glow`} x="-20%" y="-40%" width="140%" height="200%">
            <feDropShadow
              dx="0"
              dy="5"
              stdDeviation="5"
              floodColor="var(--series-1)"
              floodOpacity="0.35"
            />
          </filter>
        </defs>

        <CartesianGrid stroke="var(--gridline)" strokeWidth={1} vertical={false} />
        <XAxis
          dataKey="label"
          tick={AXIS}
          tickLine={false}
          axisLine={{ stroke: "var(--axis)" }}
          minTickGap={16}
        />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={50} />
        <Tooltip
          cursor={{ stroke: "var(--axis)", strokeWidth: 1 }}
          content={({ active, payload, label }) => {
            if (!active || !payload?.length) return null;
            const a = payload.find((p) => p.dataKey === "aktual");
            const f = payload.find((p) => p.dataKey === "ramalan");
            return (
              <TooltipBox>
                <div className="font-semibold">{label}</div>
                {a?.value != null && (
                  <div className="mt-1.5 text-ink-2">
                    {t("fc.chart.demand_actual")}: {num(a.value as number)}
                  </div>
                )}
                {f?.value != null && (
                  <div className="mt-1 text-ink-2">
                    {t("fc.chart.demand_forecast")}: {num(f.value as number)}
                  </div>
                )}
              </TooltipBox>
            );
          }}
        />
        <Legend
          height={28}
          iconType="plainline"
          wrapperStyle={{ fontSize: 11, color: "var(--text-secondary)" }}
        />
        {history.length > 0 && forecast.length > 0 && (
          <ReferenceLine
            x={monthLabel(history[history.length - 1].period)}
            stroke="var(--axis)"
            strokeWidth={1}
          />
        )}
        <Area
          dataKey="band"
          stroke="none"
          fill="var(--series-2)"
          fillOpacity={0.16}
          isAnimationActive
          animationDuration={900}
          legendType="none"
          name={t("fc.chart.band")}
        />
        <Area
          type="monotone"
          dataKey="aktual"
          stroke="none"
          fill={`url(#${gid}-area)`}
          legendType="none"
          isAnimationActive
          animationDuration={900}
          name={t("fc.chart.demand_actual")}
        />
        <Line
          type="monotone"
          dataKey="aktual"
          name={t("fc.chart.demand_actual")}
          stroke="var(--series-1)"
          strokeWidth={2.5}
          dot={false}
          filter={`url(#${gid}-glow)`}
          isAnimationActive
          animationDuration={1000}
        />
        <Line
          type="monotone"
          dataKey="ramalan"
          name={t("fc.chart.demand_forecast")}
          stroke="var(--series-2)"
          strokeWidth={2.5}
          strokeDasharray="5 4"
          dot={{ r: 3, strokeWidth: 2, stroke: "var(--surface-1)", fill: "var(--series-2)" }}
          isAnimationActive
          animationDuration={1100}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
