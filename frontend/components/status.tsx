"use client";

/**
 * SATU sumber untuk seluruh warna, ikon, dan bentuk lencana status.
 *
 * KENAPA BERKAS INI ADA. Sampai 2 September 2026 setiap layar menyimpan peta
 * statusnya sendiri, dan petanya BERSELISIH: halaman Pemesanan Ulang mewarnai
 * "Perlu pesan ulang" dengan `--status-warning` (kuning) sementara Dasbor
 * mewarnainya `--status-serious` (jingga). Satu barang karena itu berganti
 * warna saat pembacanya berpindah layar, tanpa satu pun angka yang berubah --
 * dan orang yang melihatnya wajar menyimpulkan bahwa keadaannya memburuk.
 * Tidak ada galat yang terbit dari perselisihan seperti ini; ia hanya
 * mengikis kepercayaan pada layar, sedikit demi sedikit.
 *
 * ATURAN WARNA, dan hanya ini:
 *
 *   good      keadaan yang tidak menuntut tindakan
 *   warning   menuntut tindakan terjadwal -- pesan sekarang untuk nanti
 *   serious   menyimpang dari yang diharapkan, tetapi tidak menghentikan apa pun
 *   critical  menghentikan pekerjaan bila dibiarkan
 *   neutral   tidak diketahui; BUKAN kabar baik dan bukan kabar buruk
 *
 * Merah disimpan untuk `critical` saja. Bila "perlu dipesan" dan "akan habis"
 * sama-sama merah, warna berhenti membedakan yang mendesak dari yang genting,
 * dan layar yang seluruhnya merah sama tidak berartinya dengan layar yang
 * seluruhnya abu-abu.
 *
 * WARNA TIDAK PERNAH BERDIRI SENDIRI. Setiap lencana membawa ikon DAN kata.
 * Layar gudang sering terang, sebagian pembaca tidak membedakan merah dari
 * hijau, dan yang membawa makna adalah kata "Risiko kehabisan" -- bukan
 * merahnya.
 */

import { ReactNode } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CheckCircle2,
  ArrowLeftRight,
  Ban,
  CircleHelp,
  Clock,
  FileText,
  LucideIcon,
  Minus,
  PackageCheck,
  ShoppingCart,
  Truck,
} from "lucide-react";

/** Lima tingkat semantik. Setiap status di aplikasi ini memetakan ke salah satunya. */
export type Tingkat = "good" | "warning" | "serious" | "critical" | "neutral";

export const WARNA: Record<Tingkat, string> = {
  good: "var(--status-good)",
  warning: "var(--status-warning)",
  serious: "var(--status-serious)",
  critical: "var(--status-critical)",
  neutral: "var(--status-neutral)",
};

/* ------------------------------------------------------------------ */
/* Status keputusan pemesanan (Prakiraan, Pemesanan Ulang, Dasbor)     */
/* ------------------------------------------------------------------ */

export type AksiStatusKunci =
  | "AMAN"
  | "PERLU_REORDER"
  | "RISIKO_STOCKOUT"
  /* Sumbu lama; tidak diterbitkan backend lagi. Dipetakan supaya jawaban lama
     yang masih tersimpan di peramban tidak merender komponen tanpa warna. */
  | "PANTAU"
  | "SEGERA_PESAN";

export const AKSI: Record<AksiStatusKunci, { tingkat: Tingkat; warna: string; Ikon: LucideIcon }> = {
  AMAN: { tingkat: "good", warna: WARNA.good, Ikon: CheckCircle2 },
  PERLU_REORDER: { tingkat: "warning", warna: WARNA.warning, Ikon: Clock },
  RISIKO_STOCKOUT: { tingkat: "critical", warna: WARNA.critical, Ikon: AlertTriangle },
  PANTAU: { tingkat: "warning", warna: WARNA.warning, Ikon: Clock },
  SEGERA_PESAN: { tingkat: "critical", warna: WARNA.critical, Ikon: AlertTriangle },
};

/* ------------------------------------------------------------------ */
/* Prioritas pengadaan                                                 */
/* ------------------------------------------------------------------ */

export const PRIORITAS: Record<string, Tingkat> = {
  TINGGI: "serious",
  SEDANG: "warning",
  RENDAH: "neutral",
};

/* ------------------------------------------------------------------ */
/* Status umur pakai                                                   */
/* ------------------------------------------------------------------ */

/*
 * Penggantian dini memakai `serious`, BUKAN `critical`. Ia menyimpang dari
 * spesifikasi tetapi tidak menghentikan pekerjaan hari ini -- yang berubah
 * adalah taksiran kebutuhan ke depan. Memakai merah membuat halaman ini
 * terbaca sama mendesaknya dengan stok yang akan habis besok.
 */
export const UMUR: Record<string, { tingkat: Tingkat; warna: string; Ikon: LucideIcon }> = {
  PREMATURE: { tingkat: "serious", warna: WARNA.serious, Ikon: ArrowDownRight },
  NORMAL: { tingkat: "good", warna: WARNA.good, Ikon: Minus },
  EXTENDED: { tingkat: "neutral", warna: "var(--series-3)", Ikon: ArrowUpRight },
  INSUFFICIENT: { tingkat: "neutral", warna: WARNA.neutral, Ikon: CircleHelp },
};

/* ------------------------------------------------------------------ */
/* Transfer antar gudang                                               */
/* ------------------------------------------------------------------ */

/*
 * KEPUTUSAN, bukan tingkat kegawatan. "Beli baru" berwarna netral dan itu
 * disengaja: ia bukan kegagalan melainkan jawaban yang benar ketika tidak ada
 * gudang yang berlebih. Mewarnainya merah akan membuat setiap barang yang
 * memang harus dibeli terbaca seolah ada yang salah.
 *
 * "Transfer sebagian" berwarna kuning karena ia MENUNTUT DUA TINDAKAN --
 * satu kiriman dan satu pesanan -- dan itulah yang paling mudah terlewat
 * separuhnya.
 */
export const KEPUTUSAN: Record<string, { tingkat: Tingkat; warna: string; Ikon: LucideIcon }> = {
  TRANSFER: { tingkat: "good", warna: WARNA.good, Ikon: ArrowLeftRight },
  TRANSFER_SEBAGIAN: { tingkat: "warning", warna: WARNA.warning, Ikon: ArrowLeftRight },
  PEMBELIAN: { tingkat: "neutral", warna: WARNA.neutral, Ikon: ShoppingCart },
};

/*
 * Tahap dokumen. Ketiga tahap di tengah memakai deret warna GRAFIK, bukan
 * token status: tidak satu pun di antaranya menyatakan sesuatu yang baik atau
 * buruk, hanya seberapa jauh dokumennya berjalan. Memakai kuning untuk
 * "disetujui" akan membuat dokumen yang berjalan normal terbaca sebagai
 * peringatan.
 */
export const TAHAP: Record<string, { tingkat: Tingkat; warna: string; Ikon: LucideIcon }> = {
  draft: { tingkat: "neutral", warna: WARNA.neutral, Ikon: FileText },
  approved: { tingkat: "neutral", warna: "var(--series-1)", Ikon: CheckCircle2 },
  in_transit: { tingkat: "neutral", warna: "var(--series-3)", Ikon: Truck },
  completed: { tingkat: "good", warna: WARNA.good, Ikon: PackageCheck },
  cancelled: { tingkat: "neutral", warna: WARNA.neutral, Ikon: Ban },
};

/* ------------------------------------------------------------------ */
/* Lencana                                                             */
/* ------------------------------------------------------------------ */

/**
 * SATU bentuk lencana status untuk seluruh aplikasi.
 *
 * Sebelumnya ada tiga: `Badge` di ui.tsx, satu rakitan `color-mix` sebaris di
 * reorder-list.tsx, dan satu lagi di lifetime-sections.tsx -- ketiganya
 * berbeda tinggi, jari-jari, dan tebal cincinnya, dan ketiganya pernah tampil
 * pada satu layar yang sama di Dasbor.
 *
 * `padat` untuk lencana di dalam sel tabel: sedikit lebih rapat supaya baris
 * tabel tidak ikut meninggi.
 */
export function StatusPill({
  label,
  warna,
  Ikon,
  padat = false,
  title,
}: {
  label: string;
  warna: string;
  Ikon?: LucideIcon;
  padat?: boolean;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-medium ${
        padat ? "px-2 py-0.5 t-caption" : "px-2.5 py-1 t-small"
      }`}
      style={{
        color: "var(--text-primary)",
        background: `color-mix(in srgb, ${warna} 13%, transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${warna} 32%, transparent)`,
      }}
    >
      {Ikon ? (
        <Ikon size={padat ? 11 : 12} aria-hidden style={{ color: warna }} />
      ) : (
        <span
          aria-hidden
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: warna }}
        />
      )}
      {label}
    </span>
  );
}

/** Lencana untuk status keputusan pemesanan; petanya sudah dipilihkan. */
export function PillAksi({
  status,
  label,
  padat = false,
}: {
  status: string;
  label: string;
  padat?: boolean;
}) {
  const { warna, Ikon } = AKSI[status as AksiStatusKunci] ?? AKSI.AMAN;
  return <StatusPill label={label} warna={warna} Ikon={Ikon} padat={padat} />;
}

/** Lencana untuk status umur pakai. */
export function PillUmur({
  status,
  label,
  padat = false,
}: {
  status: string;
  label: string;
  padat?: boolean;
}) {
  const { warna, Ikon } = UMUR[status] ?? UMUR.INSUFFICIENT;
  return <StatusPill label={label} warna={warna} Ikon={Ikon} padat={padat} />;
}

/** Lencana untuk keputusan transfer; petanya sudah dipilihkan. */
export function PillKeputusan({
  keputusan,
  label,
  padat = false,
}: {
  keputusan: string;
  label: string;
  padat?: boolean;
}) {
  const { warna, Ikon } = KEPUTUSAN[keputusan] ?? KEPUTUSAN.PEMBELIAN;
  return <StatusPill label={label} warna={warna} Ikon={Ikon} padat={padat} />;
}

/** Lencana untuk tahap dokumen transfer. */
export function PillTahap({
  tahap,
  label,
  padat = false,
}: {
  tahap: string;
  label: string;
  padat?: boolean;
}) {
  const { warna, Ikon } = TAHAP[tahap] ?? TAHAP.draft;
  return <StatusPill label={label} warna={warna} Ikon={Ikon} padat={padat} />;
}

/** Titik status polos, untuk tempat yang tidak muat menampung lencana penuh. */
export function TitikStatus({ warna, label }: { warna: string; label: string }): ReactNode {
  return (
    <span
      aria-label={label}
      title={label}
      className="inline-block h-2 w-2 shrink-0 rounded-full align-middle"
      style={{ background: warna }}
    />
  );
}
