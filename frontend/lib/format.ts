/**
 * Pemformatan angka & tanggal, dwibahasa.
 * Number & date formatting, bilingual.
 *
 * Locale aktif disimpan di modul ini dan disetel oleh LangProvider pada setiap
 * render, sehingga ratusan pemanggil (`num`, `idr`, `dateLabel`) tidak perlu
 * menerima parameter bahasa satu per satu. Mengganti bahasa memicu render ulang
 * pohon komponen, jadi seluruh angka di layar ikut berganti bentuk.
 *
 * The active locale lives in this module and is set by LangProvider on every
 * render, so the hundreds of call sites need not thread a language parameter.
 * Switching language re-renders the tree, so every figure on screen follows.
 */

export type Lang = "id" | "en";

let LOCALE: Lang = "id";

export function setFormatLocale(lang: Lang): void {
  LOCALE = lang;
}

export function formatLocale(): Lang {
  return LOCALE;
}

function intl(): string {
  return LOCALE === "id" ? "id-ID" : "en-US";
}

/**
 * Rupiah ringkas.
 * id: Rp 19,7 T / Rp 660 M / Rp 3,5 jt / Rp 12 rb
 * en: Rp 19.7T / Rp 660B / Rp 3.5M / Rp 12K
 *
 * Mata uangnya tetap rupiah pada kedua bahasa -- yang berubah hanya pemisah
 * desimal dan singkatan besarannya. "M" berarti miliar dalam bahasa Indonesia
 * tetapi million dalam bahasa Inggris, jadi keduanya dipetakan terpisah.
 */
export function idr(value: number | string | null | undefined): string {
  const n = Number(value ?? 0);
  if (!isFinite(n)) return "-";
  const abs = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const id = LOCALE === "id";
  const sp = id ? " " : "";
  const f = (v: number, d: number) => v.toLocaleString(intl(), { maximumFractionDigits: d });

  if (abs >= 1e12) return `${sign}Rp ${f(abs / 1e12, 1)}${sp}T`;
  if (abs >= 1e9) return `${sign}Rp ${f(abs / 1e9, 1)}${sp}${id ? "M" : "B"}`;
  if (abs >= 1e6) return `${sign}Rp ${f(abs / 1e6, 1)}${sp}${id ? "jt" : "M"}`;
  if (abs >= 1e3) return `${sign}Rp ${f(abs / 1e3, 0)}${sp}${id ? "rb" : "K"}`;
  return `${sign}Rp ${f(abs, 0)}`;
}

export function num(value: number | string | null | undefined, digits = 0): string {
  const n = Number(value ?? 0);
  if (!isFinite(n)) return "-";
  return n.toLocaleString(intl(), { maximumFractionDigits: digits });
}

export function days(value: number | string | null | undefined): string {
  if (value === null || value === undefined) return "-";
  const n = Number(value);
  const satuan = LOCALE === "id" ? "hari" : n === 1 ? "day" : "days";
  if (n < 1) return `< 1 ${LOCALE === "id" ? "hari" : "day"}`;
  return `${n.toLocaleString(intl(), { maximumFractionDigits: 0 })} ${satuan}`;
}

/** Kata "hari"/"day(s)" untuk kalimat yang merakit angkanya sendiri. */
export function dayWord(n: number): string {
  if (LOCALE === "id") return "hari";
  return n === 1 ? "day" : "days";
}

const MONTHS: Record<Lang, string[]> = {
  id: ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"],
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
};

export function monthLabel(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return String(iso);
  return `${MONTHS[LOCALE][d.getMonth()]} ${String(d.getFullYear()).slice(2)}`;
}

export function dateLabel(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return String(iso);
  const bulan = MONTHS[LOCALE][d.getMonth()];
  return LOCALE === "id"
    ? `${d.getDate()} ${bulan} ${d.getFullYear()}`
    : `${bulan} ${d.getDate()}, ${d.getFullYear()}`;
}

/** Tanggal ringkas tanpa tahun, untuk sumbu grafik: "5 Agu" / "Aug 5". */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return String(iso);
  const bulan = MONTHS[LOCALE][d.getMonth()];
  return LOCALE === "id" ? `${d.getDate()} ${bulan}` : `${bulan} ${d.getDate()}`;
}

/** Jam & menit untuk gelembung percakapan. */
export function timeLabel(ms: number): string {
  return new Intl.DateTimeFormat(intl(), { hour: "2-digit", minute: "2-digit" }).format(ms);
}
