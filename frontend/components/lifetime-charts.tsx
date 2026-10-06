"use client";

/**
 * Grafik Analisis Umur Pakai.
 *
 * SATU PERTANYAAN, DUA SKALA: apakah komponen bertahan sesuai standarnya.
 *
 *   GrafikUmurPakai           seluruh komponen sekaligus -- dua garis, umur
 *                             standar dan umur aktual, pada satu sumbu hari.
 *   GrafikRiwayatPenggantian  satu komponen -- umur tiap unit yang pernah
 *                             terpasang, terhadap standar dan pita wajarnya.
 *
 * TIDAK ADA RUMUS DI SINI. Simpangan, batas pita, dan status seluruhnya datang
 * jadi dari /api/lifetime; berkas ini hanya menempatkannya pada sumbu (dan
 * mengurutkan komponen menurut standarnya supaya garisnya terbaca).
 */

import { ReactNode } from "react";
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

const SUMBU_TEKS = { fontSize: 11, fill: "var(--text-muted)" };
const WARNA_STANDAR = "var(--text-muted)";
const WARNA_AKTUAL = "var(--brand)";

/** Di atas nisbah ini sumbu hari memakai skala logaritmik. */
const NISBAH_LOG = 20;
const NAMA_MAKS = 18;

/**
 * Dua garis pada satu sumbu hari: umur STANDAR dan umur AKTUAL tiap komponen.
 *
 * Komponen diurutkan menurut standarnya, dari yang terpendek. Garis standar
 * karena itu selalu menanjak, dan yang dibaca adalah garis aktual terhadapnya:
 * di bawah berarti diganti lebih cepat, di atas berarti bertahan lebih lama.
 *
 * SUMBUNYA LOGARITMIK bila rentangnya lebar. Filter berstandar 78 hari dan
 * bantalan berstandar 20 tahun berbagi sumbu ini; pada skala linear yang
 * pertama rata dengan dasar grafik dan selisihnya tak terlihat. Pada skala
 * logaritmik jarak tegak yang sama berarti selisih PERSEN yang sama, di mana
 * pun letaknya.
 *
 * Komponen tanpa standar tidak digambar (tidak ada yang dibandingkan); yang
 * belum terukur hanya punya titik standar, dan garis aktualnya putus di sana.
 */
export function GrafikUmurPakai({
  baris,
  terpilih,
  onPilih,
  rincian = null,
}: {
  /** isi yang terbuka di bawah grafik untuk komponen terpilih */
  rincian?: ReactNode;
  baris: BarisUmurPakai[];
  terpilih: string | null;
  onPilih: (b: BarisUmurPakai) => void;
}) {
  const t = useT();

  const kunci = (b: BarisUmurPakai) => `${b.item.id}-${b.warehouse.id}`;
  const titik = baris
    .filter((b) => b.expected_lifetime_days !== null)
    .slice()
    .sort((a, b) => a.expected_lifetime_days! - b.expected_lifetime_days!)
    .map((b) => ({
      kunci: kunci(b),
      standar: b.expected_lifetime_days,
      aktual: b.actual_lifetime_days,
      b,
    }));
  const tanpaStandar = baris.length - titik.length;
  const cari = (k: unknown) => titik.find((p) => p.kunci === k)?.b;

  const nilai = titik
    .flatMap((p) => [p.standar, p.aktual])
    .filter((v): v is number => v !== null && v > 0);
  const min = nilai.length ? Math.min(...nilai) : 1;
  const maks = nilai.length ? Math.max(...nilai) : 1;
  const log = maks / min > NISBAH_LOG;
  const tikLog: number[] = [];
  if (log) {
    for (let p = Math.floor(Math.log10(min)); p <= Math.ceil(Math.log10(maks)); p++) {
      for (const m of [1, 2, 5]) {
        const v = m * 10 ** p;
        if (v >= min * 0.75 && v <= maks * 1.3) tikLog.push(v);
      }
    }
  }

  const namaPendek = (k: string) => {
    const nama = cari(k)?.item.name ?? "";
    return nama.length > NAMA_MAKS ? `${nama.slice(0, NAMA_MAKS - 1)}…` : nama;
  };

  return (
    <div>
      {titik.length > 0 && (
        <ResponsiveContainer width="100%" height={380}>
          <ComposedChart
            data={titik}
            margin={{ top: 14, right: 16, bottom: 0, left: 0 }}
            style={{ cursor: "pointer" }}
            onClick={(s: any) => {
              const b = cari(s?.activeLabel);
              if (b) onPilih(b);
            }}
          >
            <CartesianGrid stroke="var(--border)" vertical={false} />
            <XAxis
              dataKey="kunci"
              tick={SUMBU_TEKS}
              tickLine={false}
              axisLine={{ stroke: "var(--border)" }}
              tickFormatter={namaPendek}
              interval={0}
              angle={-35}
              textAnchor="end"
              height={92}
              padding={{ left: 18, right: 18 }}
            />
            <YAxis
              tick={SUMBU_TEKS}
              tickLine={false}
              axisLine={false}
              width={52}
              scale={log ? "log" : "auto"}
              domain={log ? [min * 0.75, maks * 1.3] : [0, "auto"]}
              ticks={log ? tikLog : undefined}
              allowDataOverflow={log}
              tickFormatter={(v: number) => num(v)}
            />
            {terpilih && cari(terpilih) && (
              <ReferenceLine x={terpilih} stroke="var(--brand)" strokeOpacity={0.35} strokeWidth={2} />
            )}
            <Tooltip
              cursor={{ stroke: "var(--border)" }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const b = (payload[0].payload as (typeof titik)[number]).b;
                return (
                  <div
                    className="rounded-xl px-3.5 py-2.5 text-xs"
                    style={{
                      background: "var(--surface-1)",
                      boxShadow: "var(--elev-2), inset 0 0 0 1px var(--border)",
                      color: "var(--text-primary)",
                    }}
                  >
                    <div className="font-semibold">{b.item.name}</div>
                    <div className="text-muted">
                      {b.item.sku} · {b.warehouse.code}
                    </div>
                    <div className="mt-1.5 flex items-center gap-2">
                      <span className="h-[2px] w-3" style={{ background: WARNA_STANDAR }} />
                      {t("lt.chart.standard")}: {num(b.expected_lifetime_days)} {t("lt.unit.days")}
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="h-[2px] w-3" style={{ background: WARNA_AKTUAL }} />
                      {t("lt.chart.actual")}:{" "}
                      {b.actual_lifetime_days !== null
                        ? `${num(b.actual_lifetime_days)} ${t("lt.unit.days")}`
                        : t("lt.unmeasured")}
                      {b.actual_lifetime_days !== null && (
                        <Simpangan nilai={b.deviation_percentage} status={b.status} />
                      )}
                    </div>
                    <div className="mt-1.5">
                      <LencanaStatus status={b.status} label={b.status_label} />
                    </div>
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
              dot={{ r: 2.5, fill: WARNA_STANDAR, stroke: "none" }}
              activeDot={false}
            />
            <Line
              type="linear"
              dataKey="aktual"
              stroke={WARNA_AKTUAL}
              strokeWidth={2}
              isAnimationActive={false}
              dot={(p: any) => {
                if (p.cy == null || p.payload.aktual === null) return <g key={p.payload.kunci} />;
                const b = p.payload.b as BarisUmurPakai;
                return (
                  <circle
                    key={p.payload.kunci}
                    cx={p.cx}
                    cy={p.cy}
                    r={p.payload.kunci === terpilih ? 6 : 4.5}
                    fill={WARNA_STATUS[b.status]}
                    stroke="var(--surface-1)"
                    strokeWidth={2}
                  />
                );
              }}
              activeDot={{ r: 6, stroke: "var(--surface-1)", strokeWidth: 2 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      )}

      {/* --- legenda --- */}
      <div
        className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 border-t pt-3 t-caption text-ink-2"
        style={{ borderColor: "var(--border)" }}
      >
        <span className="inline-flex items-center gap-1.5">
          <span className="w-5 border-t-2 border-dashed" style={{ borderColor: WARNA_STANDAR }} />
          {t("lt.chart.legend_standard")}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="h-[2px] w-5" style={{ background: WARNA_AKTUAL }} />
          {t("lt.chart.legend_actual")}
        </span>
        {(["PREMATURE", "NORMAL", "EXTENDED"] as StatusUmur[]).map((s) => (
          <span key={s} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: WARNA_STATUS[s] }} />
            {t(`lt.status.${s}`)}
          </span>
        ))}
      </div>
      <p className="mt-2 t-caption text-muted">
        {t("lt.chart.axis_note")}
        {log ? ` ${t("lt.chart.log_note")}` : ""}
        {tanpaStandar > 0 ? ` ${t("lt.chart.omitted", { n: num(tanpaStandar) })}` : ""}
      </p>

      {terpilih && rincian && (
        <div
          className="mt-3 rounded-xl px-4 py-5 sm:px-6"
          style={{ background: "var(--surface-sunken)" }}
        >
          {rincian}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Riwayat satu komponen                                               */
/* ------------------------------------------------------------------ */

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
