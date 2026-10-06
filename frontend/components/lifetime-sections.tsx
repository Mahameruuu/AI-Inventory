"use client";

/**
 * Bagian-bagian halaman Analisis Umur Pakai.
 *
 * SATU ATURAN YANG MENGIKAT SELURUH BERKAS INI: tidak ada kalimat yang
 * menyebut SEBAB. Halaman ini boleh mengatakan bahwa satu komponen diganti
 * lebih cepat daripada umur pakai harapannya; ia tidak boleh mengatakan
 * kenapa. Data beban, suhu, pelumasan, dan jadwal pemeliharaan tidak ada di
 * sistem ini, dan menyimpulkan sebab dari satu-satunya angka yang kebetulan
 * tersedia adalah menuduh tanpa bukti. (Panel "Faktor pendukung" yang dulu
 * mencetak hal itu dihapus atas permintaan pengguna pada 6 Oktober 2026;
 * larangannya tetap berlaku.)
 *
 * WARNA HANYA UNTUK STATUS. Tiga kategori, tiga warna, dan tiap warna selalu
 * didampingi ikon dan label teks -- warna sendirian bukan informasi bagi
 * pembaca yang tidak membedakannya.
 */

import { Fragment, ReactNode } from "react";
import {
  ArrowDownRight,
  ArrowUpRight,
  CircleHelp,
  LineChart,
  Minus,
  TrendingDown,
  TrendingUp,
} from "lucide-react";

import { Field, Select, StatTile, Table, Td, TextInput, Th, useUrutTabel } from "@/components/ui";
import { PillUmur, UMUR } from "@/components/status";
import { useT } from "@/lib/i18n";
import { dateLabel, num } from "@/lib/format";
import { BarisUmurPakai, StatusUmur } from "@/lib/lifetime-types";

/*
 * Peta warna dan ikon status umur pakai PINDAH ke components/status.tsx pada
 * 2 September 2026, bersama peta status pemesanan. Alasannya sama: selama tiap
 * layar menyimpan petanya sendiri, dua layar yang menampilkan hal yang sama
 * bisa mewarnainya berbeda tanpa satu pun galat yang menunjukkannya.
 */
export const WARNA_STATUS: Record<StatusUmur, string> = {
  PREMATURE: UMUR.PREMATURE.warna,
  NORMAL: UMUR.NORMAL.warna,
  EXTENDED: UMUR.EXTENDED.warna,
  INSUFFICIENT: UMUR.INSUFFICIENT.warna,
};

export function LencanaStatus({ status, label }: { status: StatusUmur; label: string }) {
  return <PillUmur status={status} label={label} padat />;
}

/* ------------------------------------------------------------------ */
/* Bentuk angka                                                        */
/* ------------------------------------------------------------------ */

/**
 * Umur pakai harapan dalam SATUAN ASLINYA, dengan hari sebagai keterangan.
 *
 * "12.500 jam" adalah angka yang dikenali orang yang membaca spesifikasi
 * pabrikan; "781 hari" adalah angka yang membuat perbandingan dengan riwayat
 * mungkin. Menampilkan yang kedua saja menyembunyikan asumsi jam operasi di
 * balik satu angka yang terlihat pasti -- karena itu keduanya tampil, dan
 * asumsinya sendiri tercetak di kepala halaman.
 */
export function UmurHarapan({ baris }: { baris: BarisUmurPakai }) {
  const t = useT();
  if (!baris.has_reference) return <span className="text-muted">—</span>;

  const satuan = baris.expected_unit === "tahun" ? t("lt.unit.years") : t("lt.unit.hours");
  return (
    <div className="leading-tight">
      <span className="tnum font-medium text-ink">
        {num(baris.expected_value)} {satuan}
      </span>
      <span className="tnum ml-1.5 t-caption text-muted">
        ≈ {num(baris.expected_lifetime_days)} {t("lt.unit.days")}
      </span>
    </div>
  );
}

/**
 * Simpangan terhadap umur harapan; tandanya selalu ikut tercetak.
 *
 * DESIMALNYA DIPATOK SATU, tidak memakai `num()`. `num()` memangkas nol di
 * belakang, sehingga satu kolom angka rata kanan berisi campuran "+5,8%" dan
 * "-4%" -- titik desimalnya tidak lagi sebaris, dan mata yang memindai kolom
 * kehilangan satu-satunya patokan yang dipunyainya.
 */
export function Simpangan({ nilai, status }: { nilai: number | null; status: StatusUmur }) {
  const t = useT();
  if (nilai === null) return <span className="text-muted">—</span>;
  const warna = status === "NORMAL" ? "var(--text-secondary)" : WARNA_STATUS[status];
  const angka = nilai.toLocaleString(undefined, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return (
    <span className="tnum font-semibold" style={{ color: warna }} title={t("lt.col.deviation")}>
      {nilai > 0 ? "+" : ""}
      {angka}%
    </span>
  );
}

/**
 * Arah tren, bila memang ada cukup jarak penggantian untuk menyebutnya.
 *
 * `hanyaPerubahan` UNTUK TABEL. Pada data nyata hampir setiap komponen
 * berfrekuensi tetap, sehingga kolom "umur aktual" terisi baris kedua
 * "Frekuensi penggantian tetap" di hampir seluruh tabel -- dua puluh baris
 * yang mengucapkan hal yang sama dan tak satu pun mengubah keputusan
 * pembacanya. Yang layak menyita ruang di daftar hanya arah yang BERUBAH.
 * Di panel detail "tetap" tetap tercetak: di sana ia jawaban atas pertanyaan
 * yang memang sedang dibaca, bukan derau di antara sembilan belas baris lain.
 */
export function Tren({
  baris,
  hanyaPerubahan = false,
}: {
  baris: BarisUmurPakai;
  hanyaPerubahan?: boolean;
}) {
  if (!baris.replacement_trend || !baris.replacement_trend_label) return null;
  if (hanyaPerubahan && baris.replacement_trend === "stable") return null;
  const naik = baris.replacement_trend === "increasing";
  const turun = baris.replacement_trend === "decreasing";
  const warna = naik ? "var(--status-serious)" : turun ? "var(--series-3)" : "var(--text-muted)";
  const Ikon = naik ? TrendingUp : turun ? TrendingDown : Minus;
  return (
    <span className="inline-flex items-center gap-1 t-caption" style={{ color: warna }}>
      <Ikon size={12} aria-hidden />
      {baris.replacement_trend_label}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Kartu ringkas                                                       */
/* ------------------------------------------------------------------ */

export function RingkasanUmurPakai({
  ringkas,
}: {
  ringkas: {
    premature: number;
    normal: number;
    extended: number;
    insufficient: number;
    without_reference: number;
  };
}) {
  const t = useT();
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile
        label={t("lt.kpi.premature")}
        value={num(ringkas.premature)}
        hint={t("lt.kpi.premature_hint")}
        icon={<ArrowDownRight size={15} />}
        accent={WARNA_STATUS.PREMATURE}
        delay={0}
      />
      <StatTile
        label={t("lt.kpi.normal")}
        value={num(ringkas.normal)}
        hint={t("lt.kpi.normal_hint")}
        icon={<Minus size={15} />}
        accent={WARNA_STATUS.NORMAL}
        delay={60}
      />
      <StatTile
        label={t("lt.kpi.extended")}
        value={num(ringkas.extended)}
        hint={t("lt.kpi.extended_hint")}
        icon={<ArrowUpRight size={15} />}
        accent={WARNA_STATUS.EXTENDED}
        delay={120}
      />
      {/*
       * Kartu keempat menyebut BERAPA di antaranya yang tertahan oleh master
       * barang, bukan oleh waktu. Yang pertama dapat diperbaiki hari ini oleh
       * orang yang mengetahui umur pakainya; yang kedua tidak dapat diperbaiki
       * oleh siapa pun. Menyatukannya menjadi satu angka "belum cukup data"
       * membuat pekerjaan yang bisa dilakukan tidak terlihat.
       */}
      <StatTile
        label={t("lt.kpi.insufficient")}
        value={num(ringkas.insufficient)}
        hint={t("lt.kpi.insufficient_hint", { n: num(ringkas.without_reference) })}
        icon={<CircleHelp size={15} />}
        accent={WARNA_STATUS.INSUFFICIENT}
        delay={180}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Saringan                                                            */
/* ------------------------------------------------------------------ */

export function SaringanUmurPakai({
  gudang,
  warehouseId,
  setWarehouseId,
  status,
  setStatus,
  cari,
  setCari,
}: {
  gudang: { id: number; code: string; name: string }[];
  warehouseId: string;
  setWarehouseId: (v: string) => void;
  status: string;
  setStatus: (v: string) => void;
  cari: string;
  setCari: (v: string) => void;
}) {
  const t = useT();
  return (
    <div className="baris-saring flex flex-wrap items-end gap-3">
      <Field label={t("lt.filter.warehouse")}>
        <Select
          value={warehouseId}
          onChange={setWarehouseId}
          options={[
            { value: "", label: t("lt.filter.all_warehouses") },
            ...gudang.map((w) => ({ value: String(w.id), label: `${w.code} — ${w.name}` })),
          ]}
          className="min-w-[190px]"
        />
      </Field>
      <Field label={t("lt.filter.status")}>
        <Select
          value={status}
          onChange={setStatus}
          options={[
            { value: "", label: t("lt.filter.all") },
            { value: "PREMATURE", label: t("lt.status.PREMATURE") },
            { value: "NORMAL", label: t("lt.status.NORMAL") },
            { value: "EXTENDED", label: t("lt.status.EXTENDED") },
            { value: "INSUFFICIENT", label: t("lt.status.INSUFFICIENT") },
          ]}
          className="min-w-[170px]"
        />
      </Field>
      <Field label={t("lt.filter.search")}>
        <TextInput value={cari} onChange={setCari} placeholder={t("lt.filter.search_hint")} />
      </Field>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tabel                                                               */
/* ------------------------------------------------------------------ */

/** Kunci pengurutan -> nilai yang dibandingkan. Lihat catatan pada useUrutTabel. */
const URUT_UMUR: Record<string, (b: BarisUmurPakai) => number | string | null> = {
  komponen: (b) => b.item.name,
  harapan: (b) => b.expected_lifetime_days,
  aktual: (b) => b.actual_lifetime_days,
  // Diurutkan menurut BESARNYA simpangan, bukan tandanya: yang dicari pembaca
  // adalah "mana yang paling jauh dari spesifikasi", ke arah mana pun.
  simpangan: (b) => (b.deviation_percentage === null ? null : Math.abs(b.deviation_percentage)),
  penggantian: (b) => b.replacement_count || null,
};

export function TabelUmurPakai({
  baris,
  total,
  terpilih,
  onPilih,
  rincian = null,
}: {
  baris: BarisUmurPakai[];
  /** jumlah SELURUH hasil; menentukan boleh-tidaknya diurutkan di layar */
  total: number;
  terpilih: string | null;
  onPilih: (b: BarisUmurPakai) => void;
  /** grafik + rincian komponen terpilih; terbuka tepat di bawah barisnya */
  rincian?: ReactNode;
}) {
  const t = useT();
  const urut = useUrutTabel(baris, total, URUT_UMUR);
  return (
    <Table lekat minLebar="44rem" kartuPonsel>
      <thead>
        <tr>
          <Th urut={urut.arah("komponen")} onUrut={urut.handler("komponen")}>
            {t("lt.col.component")}
          </Th>
          <Th urut={urut.arah("harapan")} onUrut={urut.handler("harapan")}>
            {t("lt.col.expected")}
          </Th>
          <Th urut={urut.arah("aktual")} onUrut={urut.handler("aktual")}>
            {t("lt.col.actual")}
          </Th>
          <Th align="right" urut={urut.arah("simpangan")} onUrut={urut.handler("simpangan")}>
            {t("lt.col.deviation")}
          </Th>
          <Th align="right" urut={urut.arah("penggantian")} onUrut={urut.handler("penggantian")}>
            {t("lt.col.replacements")}
          </Th>
          <Th>{t("lt.col.status")}</Th>
          <Th align="right">{t("lt.col.chart")}</Th>
        </tr>
      </thead>
      <tbody>
        {urut.baris.map((b) => {
          const kunci = `${b.item.id}-${b.warehouse.id}`;
          const buka = terpilih === kunci;
          return (
            <Fragment key={kunci}>
            <tr
              onClick={() => onPilih(b)}
              className="cursor-pointer"
              style={
                terpilih === kunci
                  ? { background: "color-mix(in srgb, var(--brand) 7%, transparent)" }
                  : undefined
              }
            >
              <Td>
                <div className="font-medium text-ink">{b.item.name}</div>
                <div className="text-xs text-muted">
                  {b.item.sku} · {b.warehouse.code}
                </div>
              </Td>
              <Td>
                <UmurHarapan baris={b} />
              </Td>
              <Td>
                {b.actual_lifetime_days === null ? (
                  <span className="t-small text-muted">{t("lt.unmeasured")}</span>
                ) : (
                  <div className="leading-tight">
                    <span className="tnum font-medium text-ink">
                      {num(b.actual_lifetime_days)} {t("lt.unit.days")}
                    </span>
                    <div className="mt-0.5">
                      <Tren baris={b} hanyaPerubahan />
                    </div>
                  </div>
                )}
              </Td>
              <Td align="right" numeric>
                <Simpangan nilai={b.deviation_percentage} status={b.status} />
              </Td>
              <Td align="right" numeric>
                {b.replacement_count ? (
                  <div className="leading-tight">
                    <span className="tnum text-ink">{t("lt.times", { n: num(b.replacement_count) })}</span>
                    {b.replacements_per_year !== null && (
                      <div className="tnum t-caption text-muted">
                        {/* Dua desimal di bawah satu: komponen yang diganti
                            sekali tiap tujuh tahun berfrekuensi 0,14 -- yang
                            dibulatkan menjadi "0,1" kehilangan sepertiga
                            nilainya, dan angka inilah yang berbicara langsung
                            tentang kebutuhan sparepart setahun. */}
                        {t("lt.per_year", {
                          n: num(b.replacements_per_year, b.replacements_per_year < 1 ? 2 : 1),
                        })}
                      </div>
                    )}
                  </div>
                ) : (
                  <span className="text-muted">—</span>
                )}
              </Td>
              <Td>
                <LencanaStatus status={b.status} label={b.status_label} />
              </Td>
              <Td align="right">
                {/* Klik pada baris pun membukanya; tombol ini ada supaya
                    caranya terlihat, bukan harus ditebak. */}
                <button
                  type="button"
                  aria-expanded={buka}
                  className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg border px-2.5 py-1 t-caption font-semibold transition hover:bg-[var(--surface-sunken)]"
                  style={{
                    borderColor: buka ? "var(--brand)" : "var(--border)",
                    color: "var(--brand)",
                  }}
                >
                  <LineChart size={13} />
                  {t(buka ? "lt.chart.close" : "lt.chart.open")}
                </button>
              </Td>
            </tr>
            {buka && rincian && (
              <tr>
                <td
                  colSpan={7}
                  className="border-b px-4 py-5 sm:px-6"
                  style={{ borderColor: "var(--border)", background: "var(--surface-sunken)" }}
                >
                  {rincian}
                </td>
              </tr>
            )}
            </Fragment>
          );
        })}
      </tbody>
    </Table>
  );
}

/* ------------------------------------------------------------------ */
/* Pita umur pakai                                                     */
/* ------------------------------------------------------------------ */

/**
 * Batas bawah — harapan — batas atas, dengan umur aktual ditandai di atasnya.
 *
 * Menjawab dalam satu pandangan apa yang butuh tiga angka untuk dikatakan:
 * seberapa jauh umur aktual dari pitanya, dan ke arah mana -- dalam HARI,
 * untuk satu komponen. Perbandingan lintas komponen dan riwayat tiap unit
 * digambar components/lifetime-charts.tsx (sejak 6 Oktober 2026).
 */
export function PitaUmurPakai({
  bawah,
  harapan,
  atas,
  aktual,
  status,
}: {
  bawah: number;
  harapan: number;
  atas: number;
  aktual: number | null;
  status: StatusUmur;
}) {
  const t = useT();

  // Sumbu dilebarkan melewati pita supaya nilai di luar pita tetap punya
  // tempat untuk digambar, dan supaya pitanya tidak memenuhi seluruh lebar.
  const bentang = atas - bawah;
  const min = Math.min(bawah - bentang * 0.6, aktual ?? Infinity);
  const maks = Math.max(atas + bentang * 0.6, aktual ?? -Infinity);
  const pos = (v: number) => ((v - min) / (maks - min)) * 100;

  return (
    <div className="pt-1">
      <div className="relative h-11">
        {/* rentang penuh */}
        <div
          className="absolute inset-x-0 top-5 h-1.5 rounded-full"
          style={{ background: "var(--surface-sunken)" }}
        />
        {/* pita wajar */}
        <div
          className="absolute top-5 h-1.5 rounded-full"
          style={{
            left: `${pos(bawah)}%`,
            width: `${pos(atas) - pos(bawah)}%`,
            background: `color-mix(in srgb, ${WARNA_STATUS.NORMAL} 45%, transparent)`,
          }}
        />
        {/* umur harapan */}
        <div
          className="absolute top-[14px] h-5 w-[2px] rounded"
          style={{ left: `${pos(harapan)}%`, background: "var(--text-secondary)" }}
        />
        {/* umur aktual */}
        {aktual !== null && (
          <div
            className="absolute top-[11px] flex -translate-x-1/2 flex-col items-center"
            style={{ left: `${pos(aktual)}%` }}
          >
            <span
              className="h-[11px] w-[11px] rounded-full"
              style={{
                background: WARNA_STATUS[status],
                boxShadow: "0 0 0 2.5px var(--surface-1)",
              }}
            />
            <span className="tnum mt-1 whitespace-nowrap t-caption font-semibold text-ink">
              {num(aktual)} {t("lt.unit.days")}
            </span>
          </div>
        )}
      </div>
      {/*
       * TIAP LABEL BERDIRI DI BAWAH TITIKNYA, bukan dibagi rata dengan
       * justify-between. Sumbunya sengaja dilebarkan 60% melewati pita di
       * kedua sisi, sehingga batas bawah sebenarnya berada di sekitar 27% dan
       * batas atas di 73% -- membariskan labelnya di 0% dan 100% membuat
       * pitanya terbaca membentang penuh, dan pembaca yang menaksir jarak
       * titik aktual terhadap tepinya akan keliru setiap kali.
       */}
      <div className="relative mt-1 h-4">
        {[
          { v: bawah, label: t("lt.detail.lower") },
          { v: harapan, label: t("lt.detail.expected") },
          { v: atas, label: t("lt.detail.upper") },
        ].map((x) => (
          <span
            key={x.label}
            className="tnum absolute -translate-x-1/2 whitespace-nowrap t-caption text-muted"
            style={{ left: `${pos(x.v)}%` }}
          >
            {x.label} {num(x.v)}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Riwayat kejadian                                                    */
/* ------------------------------------------------------------------ */

export function RiwayatPenggantian({
  kejadian,
  total,
}: {
  kejadian: {
    id: number;
    date: string;
    document: string;
    lifetime_days: number | null;
    deviation_percentage: number | null;
    status: StatusUmur | null;
    status_label: string | null;
  }[];
  total: number;
}) {
  const t = useT();
  return (
    <>
      <Table kartuPonsel>
        <thead>
          <tr>
            <Th>{t("lt.detail.col_date")}</Th>
            <Th>{t("lt.detail.col_document")}</Th>
            <Th align="right">{t("lt.detail.col_lifetime")}</Th>
            <Th align="right">{t("lt.col.deviation")}</Th>
            <Th>{t("lt.col.status")}</Th>
          </tr>
        </thead>
        <tbody>
          {kejadian.map((e) => (
            <tr key={e.id}>
              <Td>{dateLabel(e.date)}</Td>
              <Td>
                <span className="text-xs text-muted">{e.document}</span>
              </Td>
              <Td align="right" numeric>
                {e.lifetime_days === null ? (
                  // Kejadian pertama tidak punya pendahulu untuk diukur. Nol
                  // akan berbunyi "bertahan nol hari"; yang benar adalah tidak
                  // diketahui.
                  <span className="text-muted" title={t("lt.detail.first_event")}>
                    —
                  </span>
                ) : (
                  <span className="tnum text-ink">
                    {num(e.lifetime_days)} {t("lt.unit.days")}
                  </span>
                )}
              </Td>
              <Td align="right" numeric>
                {e.status ? (
                  <Simpangan nilai={e.deviation_percentage} status={e.status} />
                ) : (
                  <span className="text-muted">—</span>
                )}
              </Td>
              <Td>
                {/*
                 * Kejadian pertama tidak punya status. Kalimat penjelasnya --
                 * enam puluh karakter -- dulu dicetak DI DALAM sel ini dan
                 * memaksa seluruh kolom melebar demi satu baris yang tidak
                 * menyatakan apa-apa. Kini ia tinggal di tooltip saja.
                 */}
                {e.status && e.status_label ? (
                  <LencanaStatus status={e.status} label={e.status_label} />
                ) : (
                  <span className="text-muted" title={t("lt.detail.first_event")}>
                    —
                  </span>
                )}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
      {total > kejadian.length && (
        <p className="mt-3 text-xs text-muted">
          {t("lt.detail.events_note", { n: num(kejadian.length), total: num(total) })}
        </p>
      )}
    </>
  );
}

/** Sepasang label/nilai pada panel detail. */
export function Ruas({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="t-micro font-semibold uppercase tracking-[0.07em] text-muted">
        {label}
      </div>
      <div className="mt-1 t-base font-medium text-ink">{children}</div>
    </div>
  );
}

