"use client";

/**
 * Perkakas tampilan bersama / shared UI primitives.
 *
 * TIDAK ADA EMOJI DI SELURUH BERKAS INI. Setiap penanda visual berupa ikon
 * vektor (lucide) yang mewarisi warna status dan ukuran teks di sekitarnya,
 * sehingga tampil sama di semua sistem operasi dan tetap tajam saat layar
 * diproyeksikan pada presentasi.
 *
 * NO EMOJI ANYWHERE IN THIS FILE. Every marker is a vector icon that inherits
 * its status color and surrounding text size, so it renders identically on any
 * operating system and stays crisp on a projector.
 */

import {
  AlertTriangle,
  ArrowUpDown,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Inbox,
  Info,
  Loader2,
  Minus,
  MoveDownRight,
  MoveUpRight,
} from "lucide-react";
import { CSSProperties, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useT } from "@/lib/i18n";
import { num } from "@/lib/format";

/* ------------------------------------------------------------------ */
/* Kalimat temuan utama halaman / page headline finding                */
/* ------------------------------------------------------------------ */

/**
 * Satu halaman punya satu pesan. Ditaruh paling atas supaya pembaca tahu
 * kesimpulannya sebelum menelusuri angka -- bukan sebaliknya.
 */
export function Insight({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "warning" | "critical";
}) {
  const color =
    tone === "critical"
      ? "var(--status-critical)"
      : tone === "warning"
        ? "var(--status-serious)"
        : "var(--brand)";
  const Ikon = tone === "neutral" ? Info : AlertTriangle;

  return (
    <div
      className="rise mb-5 flex items-start gap-3 overflow-hidden rounded-xl px-4 py-3.5 sm:gap-3.5 sm:px-5 sm:py-4"
      style={{
        background: `linear-gradient(115deg, color-mix(in srgb, ${color} 10%, var(--surface-1)) 0%, var(--surface-1) 62%)`,
        boxShadow: `inset 4px 0 0 0 ${color}, inset 0 0 0 1px var(--border), var(--elev-1)`,
      }}
    >
      <span
        aria-hidden
        className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
        style={{ background: `color-mix(in srgb, ${color} 16%, transparent)` }}
      >
        <Ikon size={15} style={{ color }} />
      </span>
      <div className="min-w-0 t-base leading-relaxed text-ink">{children}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Bagian yang dapat dilipat / collapsible section                     */
/* ------------------------------------------------------------------ */

/**
 * Bagian detail yang tertutup secara bawaan.
 *
 * Ringkasannya saja yang tampil; detail dibuka bila memang mau ditelusuri.
 * Memakai <details> asli agar tetap ramah keyboard dan pembaca layar.
 */
export function Section({
  title,
  subtitle,
  children,
  meta,
  defaultOpen = false,
  id,
  open,
  onOpenChange,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  meta?: ReactNode;
  defaultOpen?: boolean;
  /** dipakai agar panel prioritas bisa menggulir ke bagian ini */
  id?: string;
  /** bila diisi, bagian ini dikendalikan dari luar */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  return (
    <details
      id={id}
      open={open ?? defaultOpen}
      onToggle={(e) => onOpenChange?.((e.target as HTMLDetailsElement).open)}
      className="surface-card group mt-3 overflow-hidden"
    >
      <summary className="flex cursor-pointer select-none items-center justify-between gap-3 px-4 py-4 transition sm:gap-4 sm:px-5">
        {/* `min-w-0` supaya judul panjang menyusut alih-alih mendorong ikon
            lipat keluar layar pada ponsel. */}
        <div className="min-w-0">
          <h2 className="font-display t-base font-semibold text-ink">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
        </div>
        <span className="flex shrink-0 items-center gap-3 text-xs text-muted">
          {meta}
          <span
            className="flex h-6 w-6 items-center justify-center rounded-lg"
            style={{ background: "var(--surface-sunken)" }}
          >
            <ChevronDown
              size={14}
              className="transition-transform duration-200 group-open:rotate-180"
            />
          </span>
        </span>
      </summary>
      <div
        className="border-t px-4 pb-5 pt-4 sm:px-5"
        style={{ borderColor: "var(--border)" }}
      >
        {children}
      </div>
    </details>
  );
}

/* ------------------------------------------------------------------ */
/* Kartu / card                                                        */
/* ------------------------------------------------------------------ */

export function Card({
  title,
  subtitle,
  right,
  meta,
  children,
  className = "",
  dim = false,
  icon,
  delay = 0,
}: {
  title?: string;
  subtitle?: string;
  right?: ReactNode;
  /** keterangan ringkas di kanan judul, mis. jumlah baris */
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
  dim?: boolean;
  /** ikon kecil di kiri judul; vektor, tidak pernah emoji */
  icon?: ReactNode;
  /** jeda animasi masuk, agar kartu sebaris muncul berurutan (ms) */
  delay?: number;
}) {
  return (
    <section
      className={`surface-card surface-card-hover rise relative ${className}`}
      style={{ "--d": `${delay}ms` } as CSSProperties}
      aria-busy={dim || undefined}
    >
      <div>
      {/*
        `flex-wrap` pada kepala kartu: kendali di kanan (pencarian, tautan)
        TURUN ke barisnya sendiri di ponsel alih-alih memeras judul sampai
        tersisa dua kata.
      */}
      {(title || right || meta) && (
        <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-4 pb-2 pt-4 sm:px-5">
          <div className="flex min-w-0 items-start gap-2.5">
            {icon && (
              <span
                aria-hidden
                className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg"
                style={{
                  background: "color-mix(in srgb, var(--brand) 12%, transparent)",
                  color: "var(--brand)",
                }}
              >
                {icon}
              </span>
            )}
            <div className="min-w-0">
              {title && (
                <h2 className="font-display t-base font-semibold text-ink">{title}</h2>
              )}
              {subtitle && <p className="mt-0.5 text-xs leading-relaxed text-muted">{subtitle}</p>}
            </div>
          </div>
          {right ?? (meta ? <span className="shrink-0 text-xs text-muted">{meta}</span> : null)}
        </header>
      )}
      <div className="px-4 pb-5 pt-1 sm:px-5">{children}</div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Kartu angka / stat tile                                             */
/* ------------------------------------------------------------------ */

/**
 * Kartu angka.
 *
 * Angka besar memakai figur display dengan spasi rapat; tabular-nums hanya
 * untuk kolom tabel yang harus lurus ke bawah. Garis aksen di tepi atas
 * membawa warna status, dan warnanya SELALU didampingi kalimat petunjuk --
 * tidak pernah menjadi satu-satunya pembawa makna.
 */
export function StatTile({
  label,
  value,
  hint,
  accent,
  icon,
  delay = 0,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: string;
  icon?: ReactNode;
  delay?: number;
}) {
  const warna = accent ?? "var(--brand)";
  return (
    <div
      className="surface-card surface-card-hover rise group relative overflow-hidden px-4 pb-3.5 pt-4"
      style={{ "--d": `${delay}ms` } as CSSProperties}
    >
      {/* Garis aksen atas: tipis, penuh lebar, bergradien ke transparan. */}
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-[3px]"
        style={{
          background: `linear-gradient(90deg, ${warna}, color-mix(in srgb, ${warna} 15%, transparent))`,
        }}
      />
      {/* Cahaya sudut, muncul saat kartu disentuh tetikus. */}
      <span
        aria-hidden
        className="pointer-events-none absolute -right-10 -top-10 h-24 w-24 rounded-full opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{ background: `radial-gradient(circle, ${warna}, transparent 68%)`, filter: "blur(18px)" }}
      />

      <div className="flex items-center gap-2">
        <span className="t-caption font-semibold uppercase tracking-[0.06em] text-ink-2">
          {label}
        </span>
        {icon && (
          <span
            aria-hidden
            className="ml-auto flex h-7 w-7 items-center justify-center rounded-lg"
            style={{
              background: `color-mix(in srgb, ${warna} 13%, transparent)`,
              color: warna,
            }}
          >
            {icon}
          </span>
        )}
      </div>

      <div className="stat-figure mt-2 text-[26px] font-bold leading-none text-ink">{value}</div>
      {hint && <div className="mt-1.5 t-caption leading-relaxed text-muted">{hint}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Lencana / badges                                                    */
/* ------------------------------------------------------------------ */

/** Lencana status: warna SELALU didampingi ikon vektor + label teks. */
export function Badge({
  label,
  color,
  icon,
  title,
}: {
  label: string;
  color: string;
  /** ikon vektor; bila kosong dipakai titik netral */
  icon?: ReactNode;
  title?: string;
}) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full py-0.5 pl-1.5 pr-2.5 t-caption font-medium"
      style={{
        color: "var(--text-primary)",
        background: `color-mix(in srgb, ${color} 13%, transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${color} 30%, transparent)`,
      }}
    >
      <span aria-hidden className="flex h-4 w-4 items-center justify-center" style={{ color }}>
        {icon ?? <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />}
      </span>
      {label}
    </span>
  );
}

/** Lencana "aktif / nonaktif" — dipakai daftar gudang dan barang. */
export function ActiveBadge({ active }: { active: boolean }) {
  const t = useT();
  return active ? (
    <Badge label={t("c.active")} color="var(--status-good)" icon={<Check size={12} />} />
  ) : (
    <Badge label={t("c.inactive")} color="var(--status-neutral)" icon={<Minus size={12} />} />
  );
}

/** Lencana "aman / menipis" — dipakai daftar stok. */
export function StockBadge({ low }: { low: boolean }) {
  const t = useT();
  return low ? (
    <Badge
      label={t("c.low")}
      color="var(--status-serious)"
      icon={<AlertTriangle size={11.5} />}
    />
  ) : (
    <Badge label={t("c.safe")} color="var(--status-good)" icon={<Check size={12} />} />
  );
}

/** Lencana arah pergerakan stok. Masuk hijau, keluar jingga. */
export function MovementBadge({ type }: { type: string }) {
  const t = useT();
  const masuk = type === "stock_in" || type === "transfer_in";
  const label =
    type === "stock_in"
      ? t("c.movement_in")
      : type === "stock_out"
        ? t("c.movement_out")
        : type.replace(/_/g, " ");
  return (
    <Badge
      label={label}
      color={masuk ? "var(--status-good)" : "var(--status-serious)"}
      icon={masuk ? <MoveDownRight size={12} /> : <MoveUpRight size={12} />}
    />
  );
}

/* ------------------------------------------------------------------ */
/* Kolom isian / form controls                                         */
/* ------------------------------------------------------------------ */

export function Field({
  label,
  children,
  galat,
  wajib = false,
  petunjuk,
}: {
  label: string;
  children: ReactNode;
  /** kalimat penolakan dari backend untuk ruas INI */
  galat?: string | null;
  wajib?: boolean;
  petunjuk?: string;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="t-micro font-semibold uppercase text-muted" style={{ letterSpacing: "0.07em" }}>
        {label}
        {wajib && (
          <span aria-hidden className="ml-1" style={{ color: "var(--status-critical)" }}>
            *
          </span>
        )}
      </span>
      {children}
      {/*
       * Kalimat penolakan berdiri DI BAWAH kolomnya, bukan sebagai spanduk di
       * atas formulir. Backend sudah menyebut ruas mana yang ditolaknya
       * (`error.field`); membuang keterangan itu dan menampilkan kalimatnya di
       * kepala formulir memaksa pembaca dengan delapan kolom menebak sendiri
       * kolom mana yang harus diperbaiki.
       */}
      {galat ? (
        <span
          role="alert"
          className="t-caption leading-relaxed"
          style={{ color: "var(--status-critical)" }}
        >
          {galat}
        </span>
      ) : petunjuk ? (
        <span className="t-caption leading-relaxed text-muted">{petunjuk}</span>
      ) : null}
    </label>
  );
}

/**
 * Dialog konfirmasi untuk tindakan yang tidak dapat dibatalkan.
 *
 * MENGGANTIKAN `window.confirm`. Yang bawaan peramban tidak dapat diberi
 * gaya, tidak dapat menyebut akibat dalam lebih dari satu baris, muncul di
 * tempat yang berbeda pada tiap sistem operasi, dan -- yang paling
 * menentukan -- tampil identik untuk "hapus barang" dan "keluar dari
 * halaman". Pengguna yang melihat kotak yang sama sepuluh kali sehari
 * berhenti membacanya.
 *
 * Ditutup oleh Esc, oleh klik di luar, dan oleh tombol Batal. Tombol yang
 * membawa akibat TIDAK pernah menjadi tombol yang terpilih lebih dulu.
 */
export function DialogKonfirmasi({
  terbuka,
  judul,
  pesan,
  labelLanjut,
  labelBatal,
  onLanjut,
  onBatal,
  sibuk = false,
  merusak = true,
}: {
  terbuka: boolean;
  judul: string;
  pesan: ReactNode;
  labelLanjut: string;
  labelBatal: string;
  onLanjut: () => void;
  onBatal: () => void;
  sibuk?: boolean;
  /** tindakannya menghapus atau menimpa data */
  merusak?: boolean;
}) {
  useEffect(() => {
    if (!terbuka) return;
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onBatal();
    };
    document.addEventListener("keydown", esc);
    // Latar tidak boleh ikut menggulir di belakang dialog.
    const sebelum = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", esc);
      document.body.style.overflow = sebelum;
    };
  }, [terbuka, onBatal]);

  /*
   * DIPORTALKAN KE <body>, dan itu bukan kerapian melainkan keharusan.
   *
   * Dua pemanggil dialog ini -- menu akun dan bilah demo -- tinggal di dalam
   * bilah atas, dan bilah atas memakai `backdrop-filter` (kelas .glass-bar).
   * Ancestor yang punya filter/backdrop-filter/transform menjadi CONTAINING
   * BLOCK bagi keturunannya yang `position: fixed`; tanpa portal, `inset-0`
   * di bawah ini mengukur diri terhadap bilah setinggi 52px, bukan terhadap
   * layar -- dan dialog konfirmasi keluar akan terjepit di dalam bilah atas.
   *
   * Gejalanya hanya muncul pada dua pemanggil itu; dialog hapus di halaman
   * Master tampil benar. Cacat yang benar di sebagian tempat justru yang
   * paling lama bertahan.
   */
  const [terpasang, setTerpasang] = useState(false);
  useEffect(() => setTerpasang(true), []);

  if (!terbuka || !terpasang) return null;

  const warna = merusak ? "var(--status-critical)" : "var(--brand)";
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center px-5"
      style={{ background: "color-mix(in srgb, var(--text-primary) 45%, transparent)" }}
      onClick={onBatal}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="dlg-judul"
        className="w-full max-w-sm rounded-[var(--r-lg)] p-5"
        style={{
          background: "var(--surface-1)",
          boxShadow: "var(--elev-3), inset 0 0 0 1px var(--border)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-3">
          <span
            aria-hidden
            className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--r-md)]"
            style={{ background: `color-mix(in srgb, ${warna} 14%, transparent)`, color: warna }}
          >
            <AlertTriangle size={16} />
          </span>
          <div className="min-w-0">
            <h2 id="dlg-judul" className="font-display t-lead font-bold leading-snug text-ink">
              {judul}
            </h2>
            <div className="mt-1.5 t-body leading-relaxed text-ink-2">{pesan}</div>
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <Button onClick={onBatal} disabled={sibuk}>
            {labelBatal}
          </Button>
          <Button color={warna} onClick={onLanjut} disabled={sibuk}>
            {sibuk ? <Loader2 size={13} className="animate-spin" aria-hidden /> : null}
            {labelLanjut}
          </Button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

const KONTROL =
  "h-9 rounded-lg border bg-surface px-3 t-body text-ink outline-none transition focus:border-[var(--brand)] focus:shadow-[0_0_0_3px_color-mix(in_srgb,var(--brand)_14%,transparent)]";

export function Select({
  value,
  onChange,
  options,
  className = "",
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
  className?: string;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`${KONTROL} cursor-pointer pr-8 ${className}`}
      style={{ borderColor: "var(--border)" }}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

export function TextInput({
  value,
  onChange,
  placeholder,
  className = "",
  onEnter,
  type = "text",
  autoComplete,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
  /** dipanggil saat Enter ditekan */
  onEnter?: () => void;
  /**
   * "password" menyembunyikan isian, "email" memunculkan papan ketik yang
   * tepat di ponsel. Bawaannya tetap "text" sehingga seluruh pemakaian yang
   * sudah ada tidak berubah sama sekali.
   */
  type?: "text" | "password" | "email" | "number";
  /**
   * Petunjuk bagi pengelola kata sandi peramban. Tanpa ini, halaman masuk
   * tidak dikenali sebagai halaman masuk dan kata sandi tersimpan tidak pernah
   * ditawarkan -- yang dalam praktiknya mendorong orang memilih kata sandi
   * yang mudah diingat, bukan yang kuat.
   */
  autoComplete?: string;
}) {
  return (
    <input
      type={type}
      autoComplete={autoComplete}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Enter" && onEnter) onEnter();
      }}
      placeholder={placeholder}
      className={`${KONTROL} placeholder:text-muted ${className}`}
      style={{ borderColor: "var(--border)" }}
    />
  );
}

/** Kolom tanggal, disamakan bentuknya dengan kontrol lain. */
export function DateInput({
  value,
  onChange,
  className = "",
}: {
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  return (
    <input
      type="date"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`${KONTROL} ${className}`}
      style={{ borderColor: "var(--border)" }}
    />
  );
}

export function Button({
  children,
  onClick,
  variant = "ghost",
  color,
  disabled,
  title,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  /**
   * Kelas tambahan, untuk tombol yang harus memenuhi lebar induknya atau
   * meninggi menjadi sasaran sentuh utama sebuah layar -- mis. tombol Masuk.
   * Tinggi bawaan 32px benar untuk tombol baris tabel dan terlalu pendek untuk
   * satu-satunya tombol pada sebuah formulir yang diisi dengan ibu jari.
   */
  className?: string;
  variant?: "ghost" | "solid";
  /**
   * Warna status untuk tombol yang membawa akibat, mis. var(--status-critical).
   * Mengalahkan `variant`.
   *
   * TIDAK dicat penuh dengan teks putih. Token status punya nilai yang BERBEDA
   * pada tema terang dan gelap -- hijau #16a34a menjadi #22c55e, kuning #f59e0b
   * menjadi #fbbf24 -- dan teks putih di atas kuning terang tema gelap nyaris
   * tidak terbaca. Yang dipakai di sini latar bertintasi, cincin sewarna, dan
   * teks yang DICAMPUR ke arah warna teks tema, sehingga kontrasnya terjaga di
   * kedua tema tanpa satu pun nilai warna ditulis dua kali.
   */
  color?: string;
  disabled?: boolean;
  title?: string;
}) {
  const solid = variant === "solid";
  const dasar =
    "inline-flex h-8 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 text-xs font-semibold transition disabled:opacity-40";

  if (color) {
    return (
      <button
        onClick={onClick}
        disabled={disabled}
        title={title}
        className={`${dasar} hover:brightness-105 ${className}`}
        style={{
          background: `color-mix(in srgb, ${color} 15%, var(--surface-1))`,
          color: `color-mix(in srgb, ${color} 70%, var(--text-primary))`,
          boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${color} 48%, transparent)`,
        }}
      >
        {children}
      </button>
    );
  }

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`${dasar} ${solid ? "btn-brand" : "border hover:bg-surface-2"} ${className}`}
      style={
        solid
          ? undefined
          : { borderColor: "var(--border)", background: "var(--surface-1)", color: "var(--text-secondary)" }
      }
    >
      {children}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Navigasi halaman / pagination                                       */
/* ------------------------------------------------------------------ */

export function Pager({
  page,
  pages,
  onPage,
}: {
  page: number;
  pages: number;
  onPage: (p: number) => void;
}) {
  const t = useT();
  return (
    <div
      className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t pt-3"
      style={{ borderColor: "var(--border)" }}
    >
      <span className="text-xs text-muted">
        {t("c.page_only", { page: num(page), pages: num(pages) })}
      </span>
      <div className="flex gap-2">
        <Button onClick={() => onPage(Math.max(1, page - 1))} disabled={page <= 1}>
          <ChevronLeft size={13} />
          {t("c.prev")}
        </Button>
        <Button onClick={() => onPage(page + 1)} disabled={page >= pages}>
          {t("c.next")}
          <ChevronRight size={13} />
        </Button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Keadaan / states                                                    */
/* ------------------------------------------------------------------ */

export function ErrorBox({ message }: { message: string }) {
  const t = useT();
  return (
    <div
      className="rise flex items-start gap-3 rounded-xl px-5 py-4 text-sm"
      style={{
        background: "color-mix(in srgb, var(--status-critical) 8%, var(--surface-1))",
        boxShadow: "inset 4px 0 0 0 var(--status-critical), inset 0 0 0 1px var(--border)",
      }}
    >
      <AlertTriangle
        size={17}
        className="mt-0.5 shrink-0"
        style={{ color: "var(--status-critical)" }}
      />
      <div>
        <strong className="font-display font-semibold text-ink">{t("err.title")}</strong>{" "}
        <span className="text-ink-2">{message}</span>
        <div className="mt-1 text-xs text-muted">{t("err.hint")}</div>
      </div>
    </div>
  );
}

export function Empty({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-12 text-center">
      <span
        aria-hidden
        className="flex h-11 w-11 items-center justify-center rounded-xl"
        style={{ background: "var(--surface-sunken)", color: "var(--text-muted)" }}
      >
        <Inbox size={19} />
      </span>
      <p className="text-sm text-muted">{message}</p>
    </div>
  );
}

export function Loading({ label }: { label?: string }) {
  const t = useT();
  return (
    <div className="flex items-center justify-center gap-2.5 py-14 text-sm text-muted">
      <Loader2 size={16} className="animate-spin" style={{ color: "var(--brand)" }} />
      {label ?? t("c.loading")}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Rangka muat / loading skeletons                                     */
/* ------------------------------------------------------------------ */

/**
 * Balok abu berkilau seukuran isi yang akan menggantikannya.
 *
 * KENAPA BUKAN PEMUTAR TUNGGAL DI TENGAH LAYAR. Pemutar tidak menjanjikan
 * apa-apa tentang bentuk halaman, jadi begitu data tiba seluruh tata letak
 * muncul sekaligus dan mendorong layar -- kedipan yang dibaca mata sebagai
 * "halaman melompat". Rangka yang seukuran isinya membuat kedatangan data
 * hanya mengganti warna, bukan menggeser posisi.
 *
 * A skeleton the size of what replaces it means arriving data swaps color, not
 * position; a lone spinner promises nothing about the layout, so the finished
 * page lands all at once and the screen jumps.
 */
export function Skeleton({
  w = "100%",
  h = 12,
  radius = 6,
  className = "",
}: {
  w?: number | string;
  h?: number | string;
  radius?: number;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={`skeleton block ${className}`}
      style={{ width: w, height: h, borderRadius: radius }}
    />
  );
}

/** Sebaris kartu angka. */
export function SkeletonTiles({ count = 4 }: { count?: number }) {
  return (
    <div
      className={`grid gap-3 sm:grid-cols-2 ${count >= 4 ? "xl:grid-cols-4" : "xl:grid-cols-3"}`}
    >
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="surface-card rise px-4 pb-3.5 pt-4" style={{ "--d": `${i * 55}ms` } as CSSProperties}>
          <Skeleton w={92} h={9} />
          <Skeleton w={128} h={24} radius={8} className="mt-3" />
          <Skeleton w={104} h={9} className="mt-3" />
        </div>
      ))}
    </div>
  );
}

/** Kartu berisi tabel: kepala, lalu sejumlah baris. */
export function SkeletonTable({
  rows = 8,
  cols = 6,
  delay = 0,
}: {
  rows?: number;
  cols?: number;
  delay?: number;
}) {
  return (
    <div
      className="surface-card rise px-5 pb-5 pt-4"
      style={{ "--d": `${delay}ms` } as CSSProperties}
    >
      <Skeleton w={168} h={13} />
      <Skeleton w={232} h={9} className="mt-2" />

      <div className="mt-5">
        <SkeletonRows rows={rows} cols={cols} />
      </div>
    </div>
  );
}

/**
 * Baris-baris rangka saja, tanpa kartu.
 *
 * Dipakai di DALAM kartu yang judulnya sudah tampil — mis. "Riwayat
 * penerimaan" — supaya judul dan kotak pencariannya tetap terbaca selagi
 * barisnya dimuat, dan tidak ada kartu bersarang di dalam kartu.
 */
export function SkeletonRows({ rows = 8, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <div className="flex flex-col gap-3.5">
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="flex items-center gap-4">
          {Array.from({ length: cols }, (_, c) => (
            <Skeleton
              key={c}
              h={10}
              // Kolom pertama paling lebar, sisanya menyempit -- meniru bentuk
              // tabel sesungguhnya: nama barang lalu deretan angka.
              w={c === 0 ? "26%" : `${Math.max(8, 16 - c)}%`}
              className={r === 0 ? "opacity-70" : undefined}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Kartu berisi grafik. */
export function SkeletonChart({
  height = 200,
  delay = 0,
  className = "",
}: {
  height?: number;
  delay?: number;
  className?: string;
}) {
  return (
    <div
      className={`surface-card rise px-5 pb-5 pt-4 ${className}`}
      style={{ "--d": `${delay}ms` } as CSSProperties}
    >
      <Skeleton w={148} h={13} />
      <Skeleton w={208} h={9} className="mt-2" />
      <Skeleton h={height} radius={10} className="mt-4" />
    </div>
  );
}

/**
 * Rangka satu halaman penuh.
 *
 * Dipakai menggantikan <Loading /> pada halaman yang sudah menampilkan kepala
 * halamannya lebih dulu, sehingga judul dan penyaring tetap terbaca — dan
 * dapat langsung dipakai — selagi tabelnya berdatangan.
 */
export function PageSkeleton({
  tiles = 4,
  rows = 8,
  cols = 6,
  charts = 0,
}: {
  /** jumlah kartu angka; 0 berarti halaman ini tidak punya */
  tiles?: number;
  rows?: number;
  cols?: number;
  /** jumlah kartu grafik yang berdampingan sebelum tabel */
  charts?: number;
}) {
  return (
    <>
      {tiles > 0 && <SkeletonTiles count={tiles} />}
      {charts > 0 && (
        <div className={`mt-4 grid gap-4 ${charts > 1 ? "xl:grid-cols-2" : ""}`}>
          {Array.from({ length: charts }, (_, i) => (
            <SkeletonChart key={i} height={150} delay={80 + i * 60} />
          ))}
        </div>
      )}
      <div className="mt-4">
        <SkeletonTable rows={rows} cols={cols} delay={charts ? 200 : 120} />
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Tabel / tables                                                      */
/* ------------------------------------------------------------------ */

/** Tabel dasar; semua kolom angka memakai .tnum agar lurus ke bawah. */
/**
 * Pengurutan tabel di sisi layar.
 *
 * BATASNYA DISENGAJA DAN PENTING. Daftar Pemesanan Ulang dan Umur Pakai
 * dipaginasi DI BACKEND: layar hanya memegang dua puluh lima dari sekian
 * ratus baris. Mengurutkan yang dipegang layar lalu menamainya "urut menurut
 * simpangan" adalah kebohongan yang rapi -- pembaca menyimpulkan bahwa baris
 * teratas adalah yang tertinggi di seluruh katalog, padahal ia hanya yang
 * tertinggi di antara dua puluh lima yang kebetulan sedang tampil, dan tidak
 * ada satu pun yang menunjukkan bedanya.
 *
 * Karena itu `aktif` HANYA benar ketika seluruh hasil memang muat pada satu
 * halaman (`total <= jumlah baris yang dipegang`). Saat tidak, kepala kolom
 * tetap kepala kolom biasa: tidak ada tombol yang menjanjikan sesuatu yang
 * tidak dapat ditepatinya.
 *
 * Mengurutkan lintas halaman menuntut satu parameter `sort` pada endpoint-nya
 * -- perubahan API, bukan perubahan tampilan.
 */
export function useUrutTabel<T>(
  baris: T[],
  total: number,
  ambil: Record<string, (b: T) => number | string | null>,
) {
  const [kolom, setKolom] = useState<string | null>(null);
  const [arah, setArah] = useState<"naik" | "turun">("turun");

  const aktif = total <= baris.length;

  const terurut = useMemo(() => {
    if (!aktif || !kolom || !ambil[kolom]) return baris;
    const f = ambil[kolom];
    return [...baris].sort((a, b) => {
      const x = f(a);
      const y = f(b);
      // Nilai yang tidak diketahui SELALU turun ke bawah, ke arah mana pun
      // urutannya. Ia bukan nol dan bukan tak hingga; menaruhnya di puncak
      // daftar "simpangan terbesar" akan menyorot baris yang justru tidak
      // menyatakan apa-apa.
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      const c = typeof x === "number" && typeof y === "number"
        ? x - y
        : String(x).localeCompare(String(y));
      return arah === "naik" ? c : -c;
    });
  }, [baris, kolom, arah, aktif, ambil]);

  function urutkan(k: string) {
    if (k === kolom) setArah((a) => (a === "naik" ? "turun" : "naik"));
    else {
      setKolom(k);
      setArah("turun");
    }
  }

  return {
    baris: terurut,
    aktif,
    /** diteruskan ke <Th urut=...> */
    arah: (k: string) => (kolom === k ? arah : null),
    /** diteruskan ke <Th onUrut=...>; undefined saat pengurutan tidak sah */
    handler: (k: string) => (aktif ? () => urutkan(k) : undefined),
  };
}

/**
 * Pembungkus tabel.
 *
 * `lekat` MEMBEKUKAN BARIS KEPALA saat isinya digulir. Tanpa itu, tabel
 * dua puluh lima baris kehilangan nama kolomnya begitu pembaca menggulir --
 * dan kolom angka tanpa nama adalah deretan angka, bukan data. Tingginya
 * dibatasi `tinggiMaks` supaya pembekuannya punya arti; tanpa batas tinggi
 * tidak ada yang digulir di dalamnya.
 */
export function Table({
  children,
  lekat = false,
  tinggiMaks,
  label,
  minLebar,
  kartuPonsel = false,
}: {
  children: ReactNode;
  /** bekukan baris kepala saat isi digulir */
  lekat?: boolean;
  /** tinggi maksimum area gulir, mis. "60vh" */
  tinggiMaks?: string;
  /** nama tabel untuk pembaca layar, bila judul kartunya tidak cukup */
  label?: string;
  /**
   * Lebar minimum isi tabel, mis. "62rem".
   *
   * WAJIB pada tabel berkolom banyak DI LAYAR LEBAR. Tanpa itu, delapan kolom
   * tidak menggulir melainkan MEMAMPAT: tiap sel menyusut sampai angkanya
   * membungkus jadi tiga baris dan nama barang terpenggal per suku kata.
   *
   * Di bawah `md` lebar ini DIBATALKAN bila `kartuPonsel` menyala, karena di
   * sana tabelnya sudah tidak berbentuk tabel lagi.
   */
  minLebar?: string;
  /**
   * Di bawah `md`, tabel ini berhenti menjadi tabel dan menjadi setumpuk
   * kartu: satu kartu per baris, satu baris "NAMA KOLOM ..... nilai" per sel.
   *
   * KENAPA BUKAN SEKADAR MENGGULIR MENDATAR, yang sudah dipasang sebelumnya.
   * Gulir mendatar memindahkan seluruh beban ke pembacanya. Delapan kolom
   * selebar 62rem di layar 360px berarti ia melihat seperlima tabel sekali
   * pandang, harus menggeser untuk setiap kolom, dan -- ini yang menentukan --
   * KEHILANGAN NAMA KOLOMNYA begitu ia menggeser, karena kolom pertama yang
   * memuat nama barang ikut hilang ke kiri. Yang tersisa di layar adalah
   * deretan angka tanpa keterangan tentang barang apa pun.
   *
   * Nama kolom untuk tiap sel TIDAK ditulis ulang di tempat pemakaian. Ia
   * disalin dari <th> pada kolom yang sama, sehingga tabel yang kelak menambah
   * atau menukar kolom tidak pernah bisa menampilkan label yang salah -- dan
   * tidak ada yang perlu ingat memperbaruinya di dua tempat.
   */
  kartuPonsel?: boolean;
}) {
  const tabel = useRef<HTMLTableElement | null>(null);

  /*
   * Tanpa daftar kebergantungan DENGAN SENGAJA: label harus ikut benar setelah
   * pengurutan menukar baris, penyaringan mengganti isinya, dan bahasa
   * berganti. Menyebutkan kebergantungannya satu per satu berarti setiap
   * penyebab baru yang lupa didaftarkan menghasilkan tabel berlabel usang yang
   * hanya terlihat di ponsel. Biayanya satu penelusuran DOM per render pada
   * tabel berisi paling banyak beberapa puluh baris.
   */
  useEffect(() => {
    if (!kartuPonsel || !tabel.current) return;
    const judul = Array.from(tabel.current.querySelectorAll(":scope > thead th")).map((th) =>
      (th.textContent ?? "").trim(),
    );
    tabel.current.querySelectorAll(":scope > tbody > tr").forEach((baris) => {
      Array.from(baris.children).forEach((sel, i) => {
        // Sel yang membentang seluruh kolom (baris detail yang dapat dibuka)
        // tidak berpasangan dengan satu kolom mana pun.
        if (sel.hasAttribute("colspan")) return;
        const nama = judul[i];
        // Kolom tanpa judul -- kolom tombol hapus, misalnya -- tidak diberi
        // label, dan CSS-nya menyembunyikan label kosong itu.
        if (nama) sel.setAttribute("data-kolom", nama);
        else sel.removeAttribute("data-kolom");
      });
    });
  });
  /*
   * `overscroll-x-contain`: menggeser tabel sampai mentok ke kanan TIDAK boleh
   * diteruskan ke peramban. Tanpa itu, di ponsel geseran yang melewati ujung
   * tabel diartikan sebagai gestur "kembali", dan orang yang sedang membaca
   * kolom terakhir mendadak berada di halaman sebelumnya.
   */
  return (
    <div
      className="-mx-1 overflow-x-auto overscroll-x-contain"
      style={tinggiMaks ? { maxHeight: tinggiMaks, overflowY: "auto" } : undefined}
      // Wilayah yang dapat digulir harus dapat dicapai papan ketik, kalau tidak
      // isi yang meluber ke kanan mustahil dilihat tanpa tetikus.
      tabIndex={0}
      role="region"
      aria-label={label}
    >
      {/*
        Lebar minimumnya lewat VARIABEL CSS, bukan `min-width` sebaris. Gaya
        sebaris tidak dapat dibatalkan oleh media query mana pun tanpa
        `!important`, dan tabel berbentuk kartu justru harus melepasnya.
      */}
      <table
        ref={tabel}
        className={`row-hover w-full border-collapse t-body ${lekat ? "tabel-lekat" : ""} ${
          minLebar ? "tabel-lebar" : ""
        } ${kartuPonsel ? "tabel-kartu" : ""}`}
        style={minLebar ? ({ "--tabel-min": minLebar } as CSSProperties) : undefined}
      >
        {children}
      </table>
    </div>
  );
}

export function Th({
  children,
  align = "left",
  width,
  /** arah urut saat kolom ini yang sedang mengurutkan; untuk pembaca layar */
  urut,
  onUrut,
}: {
  children: ReactNode;
  align?: "left" | "right" | "center";
  width?: string;
  urut?: "naik" | "turun" | null;
  onUrut?: () => void;
}) {
  const isi = onUrut ? (
    <button
      type="button"
      onClick={onUrut}
      className="inline-flex items-center gap-1 rounded transition-colors hover:text-ink"
      style={{ color: urut ? "var(--text-primary)" : "inherit" }}
    >
      {children}
      <ArrowUpDown
        size={11}
        aria-hidden
        style={{ opacity: urut ? 1 : 0.35, color: urut ? "var(--brand)" : "inherit" }}
      />
    </button>
  ) : (
    children
  );

  return (
    <th
      // `scope` menghubungkan tiap sel dengan nama kolomnya. Tanpa itu pembaca
      // layar membacakan tabel sebagai deretan angka tanpa keterangan.
      scope="col"
      aria-sort={urut ? (urut === "naik" ? "ascending" : "descending") : undefined}
      className="t-micro border-b bg-[var(--surface-1)] px-3 py-2.5 font-semibold uppercase text-muted"
      style={{
        borderColor: "var(--border)",
        textAlign: align,
        width,
        letterSpacing: "0.07em",
      }}
    >
      {isi}
    </th>
  );
}

export function Td({
  children,
  align = "left",
  numeric = false,
  className = "",
}: {
  children: ReactNode;
  align?: "left" | "right" | "center";
  numeric?: boolean;
  className?: string;
}) {
  return (
    <td
      // angka tidak boleh terpenggal jadi dua baris ("Rp 845,9 M" -> "Rp 845,9" / "M")
      className={`border-b px-3 py-2.5 text-ink-2 ${
        numeric ? "tnum whitespace-nowrap" : ""
      } ${className}`}
      style={{ borderColor: "var(--border)", textAlign: align }}
    >
      {children}
    </td>
  );
}

/* ------------------------------------------------------------------ */
/* Kepala halaman / page header                                        */
/* ------------------------------------------------------------------ */

export function PageHeader({
  title,
  description,
  children,
  eyebrow,
  icon,
}: {
  title: string;
  description?: string;
  children?: ReactNode;
  /** label kecil di atas judul, mis. nama modul */
  eyebrow?: string;
  icon?: ReactNode;
}) {
  return (
    <div className="rise mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-4 sm:mb-6">
      <div className="flex min-w-0 items-start gap-3 sm:gap-3.5">
        {icon && (
          <span
            aria-hidden
            className="brand-mark flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-white sm:h-11 sm:w-11"
          >
            {icon}
          </span>
        )}
        <div className="min-w-0">
          {eyebrow && (
            <div className="mb-1 t-micro font-semibold uppercase tracking-[0.12em] text-muted">
              {eyebrow}
            </div>
          )}
          {/* 26px adalah ukuran yang benar di layar lebar dan terlalu besar di
              ponsel: judul terpanjang ("Analisis Umur Pakai") memakan dua baris
              penuh sebelum satu angka pun terlihat. */}
          <h1 className="font-display text-[21px] font-bold leading-tight text-ink sm:text-[26px]">
            {title}
          </h1>
          {description && (
            <p className="mt-1.5 max-w-2xl t-body leading-relaxed text-ink-2">
              {description}
            </p>
          )}
        </div>
      </div>
      {children}
    </div>
  );
}
