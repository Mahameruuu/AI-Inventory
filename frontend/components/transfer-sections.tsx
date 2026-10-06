"use client";

/**
 * Transfer Antar Gudang / Inter-warehouse transfer.
 *
 * BERORIENTASI TINDAKAN, sama seperti daftar Pemesanan Ulang. Yang dibawa
 * orang gudang ke depan layar ini satu pertanyaan: barang mana yang tidak
 * perlu dibeli hari ini karena sudah ada di gudang sebelah, dan dari gudang
 * mana persisnya.
 *
 * TIDAK ADA SATU PUN RUMUS DI BERKAS INI. Kekurangan, surplus, jarak, skor,
 * dan seluruh kalimat alasannya datang jadi dari GET /api/transfer. Angka
 * kekurangannya sendiri DIPINJAM mesin pemesanan ulang tanpa dihitung ulang,
 * sehingga satu barang mustahil menyebut kekurangan yang berbeda di halaman
 * ini dan di halaman Pemesanan Ulang.
 *
 * KENAPA KARTU, BUKAN TABEL (3 September 2026). Bentuk sebelumnya adalah tabel
 * sembilan kolom, dan dua kolom di tengahnya -- "gudang asal" dan "gudang
 * tujuan" -- hanya memuat kode: WH-CEN-01 di satu sel, WH-CEN-02 di sel
 * sebelahnya. Membacanya menuntut dua hal yang tidak boleh dituntut layar
 * gudang: menghafal kode mana milik kota mana, dan mengingat kolom mana yang
 * mengirim dan mana yang menerima. Keduanya adalah kesalahan yang akibatnya
 * fisik -- barang berangkat ke arah yang salah -- dan tidak satu pun terbit
 * sebagai galat.
 *
 * Karena itu tiap baris kini satu kartu dengan SATU arah yang terbaca sekali
 * lihat: blok PENGIRIM di kiri, panah beserta jumlahnya di tengah, blok
 * PENERIMA di kanan, keduanya menyebut nama gudang lengkap dan kodenya sebagai
 * keterangan kedua. Pada layar sempit susunannya menurun, dan panahnya ikut
 * berputar sehingga arahnya tetap menunjuk dari pengirim ke penerima.
 *
 * KENAPA GUDANG YANG DITOLAK IKUT DITAMPILKAN. Pertanyaan yang paling sering
 * datang setelah membaca daftar seperti ini adalah "gudang Jakarta kan punya
 * barangnya, kenapa tidak dipakai?". Menyembunyikan yang ditolak berarti
 * pertanyaan itu dijawab lewat telepon, berulang kali. Menampilkannya beserta
 * sebabnya menjawabnya sekali.
 */

import dynamic from "next/dynamic";
import { ReactNode, useCallback, useEffect, useState } from "react";

import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  ChevronDown,
  Clock,
  Map as MapIcon,
  MapPin,
  MoveRight,
  PackageCheck,
  PackageOpen,
  Send,
  ShoppingCart,
  Truck,
  Warehouse,
} from "lucide-react";

import { PemilihModel, PemilihPeriode, angka } from "@/components/forecast-ui";
import { PanelRuteML, PilihanRute } from "@/components/rute-ml";
import { AKSI, PillAksi, PillKeputusan, PillTahap, TAHAP, WARNA } from "@/components/status";
import { Button, Empty, Field, Select, StatTile, TextInput } from "@/components/ui";
import { apiPatch, apiPost, useApi } from "@/lib/api";
import { dateLabel, days, idr, num } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { GudangApi } from "@/lib/peta";
import { kelompokkanRute, MuatanRute, RuteTransfer } from "@/lib/transfer-rute";
import {
  BarisTransfer,
  DetailDokumenTransfer,
  DokumenTransfer,
  KandidatTransfer,
  KirimanTransfer,
  RingkasTransfer,
  StatusTransfer,
} from "@/lib/transfer-types";

/* ------------------------------------------------------------------ */
/* Ringkasan                                                           */
/* ------------------------------------------------------------------ */

/**
 * Empat kartu, dan yang pertama adalah alasan modul ini ada.
 *
 * "Dapat dipindahkan" menghitung UNIT, bukan baris: itulah jumlah barang yang
 * tidak perlu dibeli karena perusahaan ini sudah memilikinya. Angka baris
 * tidak dapat dibandingkan dengan apa pun; angka unit dapat langsung
 * dibandingkan dengan total pembelian di sebelahnya.
 */
export function RingkasanTransfer({ ringkas }: { ringkas: RingkasTransfer }) {
  const t = useT();
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile
        label={t("tf.kpi.movable")}
        value={`${num(ringkas.total_qty_transfer)} ${t("tf.kpi.units")}`}
        hint={t("tf.kpi.movable_hint")}
        accent={ringkas.total_qty_transfer > 0 ? WARNA.good : undefined}
      />
      <StatTile
        label={t("tf.kpi.full")}
        value={num(ringkas.dapat_transfer)}
        hint={t("tf.kpi.full_hint")}
        accent={ringkas.dapat_transfer > 0 ? WARNA.good : undefined}
      />
      <StatTile
        label={t("tf.kpi.partial")}
        value={num(ringkas.transfer_sebagian)}
        hint={t("tf.kpi.partial_hint")}
        accent={ringkas.transfer_sebagian > 0 ? WARNA.warning : undefined}
      />
      {/*
        Jumlah yang tetap harus dibeli dicetak TANPA satuan tunggal: baris yang
        dijumlahkan bersatuan campur -- BOX, LTR, PCS -- sehingga menuliskan
        satu satuan di belakangnya akan berbohong. Satuan aslinya ada pada tiap
        barisnya.
      */}
      <StatTile
        label={t("tf.kpi.buy")}
        value={`${num(ringkas.total_qty_beli)} ${t("tf.kpi.units")}`}
        hint={t("tf.kpi.buy_hint", { n: num(ringkas.harus_beli) })}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tab keputusan                                                       */
/* ------------------------------------------------------------------ */

export type TabKeputusan = "" | "TRANSFER" | "TRANSFER_SEBAGIAN" | "PEMBELIAN";

/**
 * INILAH saringan keputusannya; tidak ada dropdown kedua di baris filter.
 * Dua kendali yang menyetel keadaan yang sama membuat pembaca harus memeriksa
 * keduanya untuk tahu apa yang sedang dilihatnya.
 */
export function TabTransfer({
  aktif,
  setAktif,
  ringkas,
}: {
  aktif: TabKeputusan;
  setAktif: (v: TabKeputusan) => void;
  ringkas: RingkasTransfer;
}) {
  const t = useT();
  const tabs: { key: TabKeputusan; label: string; n: number }[] = [
    { key: "", label: t("tf.tab.all"), n: ringkas.total_baris },
    { key: "TRANSFER", label: t("tf.tab.full"), n: ringkas.dapat_transfer },
    { key: "TRANSFER_SEBAGIAN", label: t("tf.tab.partial"), n: ringkas.transfer_sebagian },
    { key: "PEMBELIAN", label: t("tf.tab.buy"), n: ringkas.harus_beli },
  ];

  return (
    <div
      role="tablist"
      className="flex flex-wrap gap-1 rounded-xl p-1"
      style={{ background: "var(--surface-sunken)" }}
    >
      {tabs.map((tab) => {
        const on = tab.key === aktif;
        return (
          <button
            key={tab.key || "all"}
            role="tab"
            aria-selected={on}
            onClick={() => setAktif(tab.key)}
            className="rounded-lg px-3 py-1.5 t-small font-semibold transition"
            style={{
              background: on ? "var(--surface-1)" : "transparent",
              color: on ? "var(--text-primary)" : "var(--text-secondary)",
              boxShadow: on ? "var(--elev-1)" : "none",
            }}
          >
            {tab.label}
            <span className="ml-1.5 tnum t-caption font-medium text-muted">{num(tab.n)}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Alur pengirim -> penerima                                           */
/* ------------------------------------------------------------------ */

function Jarak({ km, dasar }: { km: number | null; dasar: string | null }) {
  const t = useT();
  if (km === null) {
    // "—" akan menyamakan "tidak diketahui" dengan "nol kilometer", dan yang
    // kedua berarti gudang yang sama persis letaknya.
    return <span className="t-caption text-muted">{t("tf.dist.unknown")}</span>;
  }
  return (
    <span className="tnum whitespace-nowrap">
      {num(km)} km
      {dasar === "haversine" && (
        <span className="ml-1 t-caption text-muted" title={t("tf.dist.straight_hint")}>
          {t("tf.dist.straight")}
        </span>
      )}
    </span>
  );
}

/** Satu angka berlabel di dalam blok gudang. */
function Angka({ label, nilai }: { label: string; nilai: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="t-caption text-muted">{label}</dt>
      <dd className="tnum t-body font-semibold text-ink">{nilai}</dd>
    </div>
  );
}

/**
 * Blok satu gudang, dan inilah yang menjawab "siapa mengirim ke siapa".
 *
 * NAMA GUDANG LENGKAP YANG BESAR, kodenya kecil di bawahnya. Kode dipertahankan
 * karena itu yang tercetak pada surat jalan dan yang diucapkan lewat radio,
 * tetapi ia tidak boleh menjadi satu-satunya penanda: "WH-CEN-01" dan
 * "WH-CEN-02" berselisih satu huruf, dan satu huruf bukan pembeda yang cukup
 * untuk perintah yang menggerakkan barang antar pulau.
 */
function BlokGudang({
  peran,
  kode,
  nama,
  garis,
  warna,
  redup = false,
  anak,
}: {
  peran: "kirim" | "terima";
  kode: string;
  nama: string;
  garis?: { label: string; nilai: ReactNode }[];
  warna: string;
  /** gudang yang tidak ada; digambar putus-putus, bukan disembunyikan */
  redup?: boolean;
  anak?: ReactNode;
}) {
  const t = useT();
  const Ikon = peran === "kirim" ? PackageOpen : Warehouse;

  return (
    <div
      className="flex min-w-0 flex-1 flex-col gap-2 rounded-2xl px-4 py-3.5"
      style={
        redup
          ? {
              // Bergaris putus-putus, bukan diarsir: bentuk yang sama dengan
              // tempat kosong pada formulir mana pun, dan terbaca sebagai
              // "belum terisi" tanpa satu kata pun.
              background: "var(--surface-1)",
              outline: "1px dashed color-mix(in srgb, var(--text-muted) 40%, transparent)",
              outlineOffset: "-1px",
            }
          : {
              background: `linear-gradient(150deg, color-mix(in srgb, ${warna} 9%, var(--surface-1)) 0%, var(--surface-1) 68%)`,
              boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${warna} 26%, var(--border)), var(--elev-1)`,
            }
      }
    >
      <span
        className="flex items-center gap-1.5 t-eyebrow"
        style={{ color: redup ? "var(--text-muted)" : warna }}
      >
        <Ikon size={12} aria-hidden />
        {t(peran === "kirim" ? "tf.role.sender" : "tf.role.receiver")}
      </span>

      <div className="min-w-0">
        <p className="truncate t-base font-semibold text-ink" title={nama}>
          {nama}
        </p>
        {kode && <p className="truncate tnum t-caption text-muted">{kode}</p>}
      </div>

      {garis && garis.length > 0 && (
        <dl className="flex flex-wrap gap-x-6 gap-y-1.5">
          {garis.map((g) => (
            <Angka key={g.label} label={g.label} nilai={g.nilai} />
          ))}
        </dl>
      )}

      {anak}
    </div>
  );
}

/**
 * Bagian tengah: arah, jumlah, dan ongkos perjalanannya.
 *
 * Panahnya berputar 90 derajat pada layar sempit -- di sana kedua blok
 * bertumpuk, dan panah mendatar di antara dua blok bertumpuk menunjuk ke
 * tempat yang tidak ada apa-apanya.
 */
function PanahAlur({
  qty,
  satuan,
  keterangan,
  km,
  dasarJarak,
  hari,
  skor,
  redup = false,
}: {
  qty: number;
  satuan: string;
  keterangan: string;
  km?: number | null;
  dasarJarak?: string | null;
  hari?: number | null;
  skor?: number | null;
  redup?: boolean;
}) {
  const t = useT();
  const warna = redup ? "var(--text-muted)" : "var(--brand)";

  return (
    <div className="flex shrink-0 flex-row items-center justify-center gap-3 lg:w-44 lg:flex-col lg:gap-1.5">
      <MoveRight
        size={22}
        aria-hidden
        className="rotate-90 lg:rotate-0"
        style={{ color: warna, opacity: redup ? 0.5 : 0.9 }}
      />
      <div className="text-center">
        <p className="whitespace-nowrap">
          <span
            className="stat-figure t-title font-bold"
            style={{ color: redup ? "var(--text-muted)" : "var(--text-primary)" }}
          >
            {num(qty)}
          </span>
          {satuan && <span className="ml-1 t-small font-medium text-muted">{satuan}</span>}
        </p>
        <p className="t-caption text-muted">{keterangan}</p>
      </div>

      {(km !== undefined || hari != null) && (
        <p className="flex flex-wrap items-center justify-center gap-x-2 gap-y-0.5 t-caption text-muted">
          {km !== undefined && (
            <span className="inline-flex items-center gap-1">
              <MapPin size={10} aria-hidden />
              <Jarak km={km ?? null} dasar={dasarJarak ?? null} />
            </span>
          )}
          {hari != null && (
            <span className="inline-flex items-center gap-1">
              <Clock size={10} aria-hidden />
              {days(hari)}
            </span>
          )}
        </p>
      )}

      {skor != null && (
        <span
          className="rounded-full px-2 py-0.5 tnum t-caption font-semibold"
          style={{
            background: "color-mix(in srgb, var(--brand) 12%, transparent)",
            color: "var(--brand)",
          }}
          title={t("tf.col.score")}
        >
          {t("tf.flow.score", { n: skor })}
        </span>
      )}
    </div>
  );
}

/** Kerangka tiga bagian: pengirim, panah, penerima. */
function RelAlur({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2.5 lg:flex-row lg:items-stretch lg:gap-3">{children}</div>
  );
}

/* ------------------------------------------------------------------ */
/* Kandidat gudang sumber                                              */
/* ------------------------------------------------------------------ */

/**
 * Rincian skor satu kandidat sebagai batang berbobot.
 *
 * Empat batang, bukan satu angka. Yang ingin diketahui pembaca yang meragukan
 * peringkat bukan "berapa skornya" melainkan "kenapa yang itu menang", dan itu
 * hanya terjawab bila komponennya berdampingan -- gudang yang menang karena
 * dekat meski stoknya pas-pasan terlihat berbeda seketika dari gudang yang
 * menang karena stoknya berlimpah.
 */
function RincianSkor({ k }: { k: KandidatTransfer }) {
  const t = useT();
  if (!k.components || !k.weights) return null;

  const baris: { kunci: keyof typeof k.weights; nilai: number }[] = [
    { kunci: "sufficiency", nilai: k.components.sufficiency },
    { kunci: "surplus_ratio", nilai: k.components.surplus_ratio },
    { kunci: "distance", nilai: k.components.distance },
    { kunci: "lead_time", nilai: k.components.lead_time },
  ];

  return (
    <div className="mt-2 flex flex-col gap-1.5">
      {baris.map((b) => (
        <div key={String(b.kunci)} className="flex items-center gap-2">
          <span className="w-28 shrink-0 t-caption text-muted">
            {t(`tf.score.${String(b.kunci)}`)}
          </span>
          <span
            className="h-1.5 flex-1 overflow-hidden rounded-full"
            style={{ background: "var(--surface-sunken)" }}
          >
            <span
              className="block h-full rounded-full"
              style={{
                width: `${Math.round(100 * b.nilai)}%`,
                background: "var(--brand)",
              }}
            />
          </span>
          <span className="w-20 shrink-0 text-right tnum t-caption text-muted">
            {Math.round(100 * b.nilai)}%
            <span className="ml-1 opacity-70">
              ×{k.weights![b.kunci as string].toFixed(2)}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

/** Satu kandidat, lolos maupun ditolak, pada panel rincian. */
function BarisKandidat({
  k,
  qty,
  satuan,
}: {
  k: KandidatTransfer;
  /** jumlah yang benar-benar dialokasikan; kosong berarti tidak kebagian */
  qty?: number;
  satuan: string;
}) {
  const t = useT();
  const [buka, setBuka] = useState(false);
  const mati = !k.eligible;

  return (
    <div
      className="rounded-xl px-3.5 py-3"
      style={{
        background: "var(--surface-1)",
        boxShadow: `inset 0 0 0 1px ${
          qty ? "color-mix(in srgb, var(--status-good) 35%, transparent)" : "var(--border)"
        }`,
        opacity: mati ? 0.78 : 1,
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {/* Nama gudang lebih dulu, kodenya menyusul: urutan yang sama
                dengan blok pengirim di atas, supaya keduanya dibaca dengan
                cara yang sama. */}
            <span className="font-semibold text-ink">{k.from_warehouse_name}</span>
            <span className="tnum t-caption text-muted">{k.from_warehouse_code}</span>
            {k.match_type === "fuzzy" && (
              // Baris fuzzy WAJIB dapat dikenali sebelum barang bergerak: yang
              // dikirim adalah barang bernomor lain, dan hanya orang gudang
              // yang dapat memutuskan apakah keduanya memang barang yang sama.
              <span
                className="rounded-full px-2 py-0.5 t-caption font-semibold"
                style={{
                  background: "color-mix(in srgb, var(--status-warning) 14%, transparent)",
                  color: "var(--status-warning)",
                }}
                title={t("tf.fuzzy.badge_hint")}
              >
                {t("tf.fuzzy.badge", { n: Math.round(100 * (k.match_similarity ?? 0)) })}
              </span>
            )}
            {mati && (
              <PillAksi status={k.source_status} label={k.source_status_label} padat />
            )}
          </div>

          {k.match_type === "fuzzy" && (
            <div className="mt-0.5 t-caption text-muted">
              {t("tf.fuzzy.sends", { sku: k.sku, nama: k.item_name })}
            </div>
          )}

          <p className="mt-1 max-w-2xl t-caption leading-relaxed text-ink-2">{k.why}</p>
        </div>

        <div className="flex shrink-0 items-center gap-4">
          <span className="text-right">
            <span className="block t-caption text-muted">{t("tf.col.surplus")}</span>
            <span className="tnum t-body font-semibold text-ink">
              {angka(k.surplus, satuan)}
            </span>
          </span>
          <span className="text-right">
            <span className="block t-caption text-muted">{t("tf.col.distance")}</span>
            <span className="t-body">
              <Jarak km={k.distance_km} dasar={k.distance_basis} />
            </span>
          </span>
          <span className="text-right">
            <span className="block t-caption text-muted">{t("tf.col.score")}</span>
            <span className="tnum t-body font-semibold" style={{ color: "var(--brand)" }}>
              {mati ? "—" : k.score}
            </span>
          </span>
          {qty ? (
            <span className="text-right">
              <span className="block t-caption text-muted">{t("tf.col.qty")}</span>
              <span className="stat-figure tnum t-lead font-bold text-ink">
                {num(qty)} {satuan}
              </span>
            </span>
          ) : null}
        </div>
      </div>

      {!mati && (
        <button
          onClick={() => setBuka((v) => !v)}
          className="mt-1.5 inline-flex items-center gap-1 t-caption font-semibold"
          style={{ color: "var(--brand)" }}
        >
          <ChevronDown
            size={12}
            style={{ transform: buka ? "rotate(180deg)" : "none" }}
            aria-hidden
          />
          {t("tf.score.breakdown")}
        </button>
      )}
      {buka && <RincianSkor k={k} />}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Panel rincian satu rekomendasi                                      */
/* ------------------------------------------------------------------ */

/** Judul kecil di dalam panel rincian. */
function JudulPanel({ children }: { children: ReactNode }) {
  return (
    <h4 className="mb-2 t-caption font-semibold uppercase tracking-[0.08em] text-ink-2">
      {children}
    </h4>
  );
}

/**
 * Panel di bawah kartu: keadaan gudang penerima menurut mesin keputusan, lalu
 * seluruh kandidat -- yang dipakai, yang tersedia, dan yang ditolak.
 *
 * TOMBOL PENGAJUANNYA TIDAK DI SINI melainkan di kaki kartu, terlihat tanpa
 * membuka apa pun. Tindakan yang tersembunyi di balik satu klik tambahan
 * adalah tindakan yang tidak dikerjakan.
 */
function PanelKandidat({ baris }: { baris: BarisTransfer }) {
  const t = useT();
  const satuan = baris.unit_code ?? "";

  const dipakai = new Set(baris.legs.map((l) => l.from_warehouse_id));
  const cadangan = baris.candidates.filter((k) => !dipakai.has(k.from_warehouse_id));

  return (
    <div
      className="border-t px-4 py-4 sm:px-5"
      style={{ borderColor: "var(--border)", background: "var(--surface-sunken)" }}
    >
      {/* --- kebutuhan gudang penerima, seluruhnya dari mesin keputusan --- */}
      <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-2 t-small">
        <span>
          <span className="text-muted">{t("tf.detail.available")}: </span>
          <span className="tnum font-semibold text-ink">
            {angka(baris.available_stock_int, satuan)}
          </span>
        </span>
        <span>
          <span className="text-muted">
            {t("tf.detail.demand", { n: baris.decision_horizon_days })}:{" "}
          </span>
          <span className="tnum font-semibold text-ink">
            {angka(baris.forecast_usage_int, satuan)}
          </span>
        </span>
        <span>
          <span className="text-muted">{t("tf.detail.need")}: </span>
          <span className="tnum font-semibold text-ink">
            {baris.need_qty === null ? t("tf.qty_none") : angka(baris.need_qty, satuan)}
          </span>
        </span>
        <span className="t-caption text-muted">{t("tf.detail.need_basis")}</span>
      </div>

      {baris.legs.length > 0 && (
        <>
          <JudulPanel>{t("tf.detail.plan")}</JudulPanel>
          <div className="flex flex-col gap-2">
            {baris.legs.map((l) => (
              <BarisKandidat
                key={`${l.from_warehouse_id}-${l.item_id}`}
                k={l}
                qty={l.transfer_qty}
                satuan={satuan}
              />
            ))}
          </div>
        </>
      )}

      {cadangan.length > 0 && (
        <div className="mt-4">
          <JudulPanel>{t("tf.detail.alternatives")}</JudulPanel>
          <div className="flex flex-col gap-2">
            {cadangan.map((k) => (
              <BarisKandidat key={`${k.from_warehouse_id}-${k.item_id}`} k={k} satuan={satuan} />
            ))}
          </div>
        </div>
      )}

      {baris.rejected.length > 0 && (
        <div className="mt-4">
          <JudulPanel>{t("tf.detail.rejected")}</JudulPanel>
          <div className="flex flex-col gap-2">
            {baris.rejected.map((k) => (
              <BarisKandidat key={`${k.from_warehouse_id}-${k.item_id}`} k={k} satuan={satuan} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Kartu rekomendasi                                                   */
/* ------------------------------------------------------------------ */

/**
 * Satu kebutuhan, satu kartu.
 *
 * SATU DOKUMEN PER GUDANG ASAL, bukan satu dokumen untuk seluruh rencana.
 * Dokumen transfer punya satu gudang asal dan satu gudang tujuan -- itu bentuk
 * fisiknya, karena satu kiriman berangkat dari satu tempat. Rencana yang
 * menggabungkan dua gudang karena itu menghasilkan dua dokumen yang berjalan
 * sendiri-sendiri: yang satu dapat sampai lebih dulu, dan yang lain dapat
 * dibatalkan tanpa menahan yang pertama.
 */
function KartuTransfer({ baris, onSegar }: { baris: BarisTransfer; onSegar: () => void }) {
  const t = useT();
  const [buka, setBuka] = useState(false);
  const [kirim, setKirim] = useState(false);
  const [galat, setGalat] = useState<string | null>(null);
  const [nomor, setNomor] = useState<string[]>([]);
  // Moda yang direkomendasikan model rute untuk kiriman UTAMA; dicatat pada
  // dokumennya. Kiriman tambahan dari sumber lain diajukan tanpa moda.
  // Satu rekomendasi PER PENGIRIM: tiap kiriman adalah dokumennya sendiri, jadi
  // tiap kiriman membawa modanya sendiri.
  const [rute, setRute] = useState<Record<number, PilihanRute | null>>({});

  const satuan = baris.unit_code ?? "";
  const utama: KirimanTransfer | undefined = baris.legs[0];
  const warnaPenerima = (AKSI as any)[baris.action_status]?.warna ?? WARNA.neutral;

  async function ajukan() {
    if (kirim || nomor.length || !baris.legs.length) return;
    setKirim(true);
    setGalat(null);
    try {
      const dibuat: string[] = [];
      for (const leg of baris.legs) {
        const utamaIni = rute[leg.from_warehouse_id] ?? null;
        const r = await apiPost<{ transfer_number: string }>("/api/transfers", {
          from_warehouse_id: leg.from_warehouse_id,
          to_warehouse_id: baris.to_warehouse_id,
          source: "transfer_engine",
          score: leg.score,
          reason: leg.why,
          distance_km: leg.distance_km,
          transport_mode: utamaIni ? utamaIni.mode : undefined,
          planned_days: utamaIni ? Math.ceil(utamaIni.hari) : undefined,
          items: [
            {
              item_id: leg.item_id,
              quantity: leg.transfer_qty,
              for_item_id: baris.item_id,
              match_type: leg.match_type,
              match_similarity: leg.match_similarity,
            },
          ],
        });
        dibuat.push(r.transfer_number);
      }
      setNomor(dibuat);
      onSegar();
    } catch (e) {
      setGalat((e as Error).message);
    } finally {
      setKirim(false);
    }
  }

  return (
    <article className="surface-card overflow-hidden">
      {/* --- kepala: barang, lalu keputusannya --- */}
      <header
        className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-4 py-3.5 sm:px-5"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="min-w-0">
          <h3 className="truncate t-lead font-semibold text-ink" title={baris.item_name}>
            {baris.item_name}
          </h3>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 t-caption text-muted">
            <span className="tnum">{baris.sku}</span>
            {satuan && (
              <>
                <span aria-hidden>·</span>
                <span>{satuan}</span>
              </>
            )}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <PillAksi status={baris.action_status} label={baris.action_status_label} padat />
          <PillKeputusan keputusan={baris.decision} label={baris.decision_label} />
        </div>
      </header>

      {/* --- alur pengirim -> penerima --- */}
      <div className="px-4 py-4 sm:px-5">
        <RelAlur>
          {utama ? (
            <BlokGudang
              peran="kirim"
              warna={WARNA.good}
              kode={utama.from_warehouse_code}
              nama={utama.from_warehouse_name}
              garis={[
                { label: t("tf.card.stock"), nilai: angka(utama.source_stock_int, satuan) },
                { label: t("tf.card.spare"), nilai: angka(utama.surplus, satuan) },
              ]}
              anak={
                baris.legs.length > 1 ? (
                  <p className="t-caption font-medium" style={{ color: "var(--brand)" }}>
                    {t("tf.card.more_sources", { n: baris.legs.length - 1 })}
                  </p>
                ) : utama.match_type === "fuzzy" ? (
                  <p className="t-caption text-muted">
                    {t("tf.fuzzy.sends", { sku: utama.sku, nama: utama.item_name })}
                  </p>
                ) : null
              }
            />
          ) : (
            /* Blok pengirim tetap ada walau kosong: menghilangkannya membuat
               kartu "beli baru" berbentuk lain sama sekali, dan pembaca
               kehilangan pola yang baru saja dipelajarinya dua baris di atas. */
            <BlokGudang
              peran="kirim"
              warna={WARNA.neutral}
              redup
              kode=""
              nama={t("tf.role.sender_none")}
              anak={
                <p className="t-caption leading-relaxed text-muted">
                  {baris.rejected.length
                    ? t("tf.role.sender_blocked", { n: baris.rejected.length })
                    : t("tf.role.sender_absent")}
                </p>
              }
            />
          )}

          <PanahAlur
            qty={baris.transfer_qty}
            satuan={satuan}
            keterangan={baris.transfer_qty > 0 ? t("tf.flow.shipped") : t("tf.flow.nothing")}
            km={utama ? utama.distance_km : undefined}
            dasarJarak={utama?.distance_basis}
            hari={utama?.lead_time_days ?? null}
            skor={utama ? utama.score : null}
            redup={!utama}
          />

          <BlokGudang
            peran="terima"
            warna={warnaPenerima}
            kode={baris.to_warehouse_code}
            nama={baris.to_warehouse_name}
            garis={[
              { label: t("tf.card.stock"), nilai: angka(baris.available_stock_int, satuan) },
              {
                label: t("tf.card.need"),
                nilai:
                  baris.need_qty === null ? t("tf.qty_none") : angka(baris.need_qty, satuan),
              },
            ]}
          />
        </RelAlur>

        <p className="mt-3 t-small leading-relaxed text-ink-2">{baris.reason}</p>
      </div>

      {/* --- satu rekomendasi rute (model ML klasik) per pengirim --- */}
      {baris.legs
        .filter((leg) => leg.transfer_qty > 0)
        .map((leg) => (
          <PanelRuteML
            key={leg.from_warehouse_id}
            sumber={baris.legs.length > 1 ? leg.from_warehouse_code : undefined}
            dariId={leg.from_warehouse_id}
            keId={baris.to_warehouse_id}
            // Yang dinilai kiriman GABUNGAN satu pasangan gudang (server yang
            // menyusunnya), supaya moda pada kartu ini sama dengan garis di peta.
            jumlah={leg.route_ml?.shipment_qty ?? leg.transfer_qty}
            itemId={leg.item_id}
            nilai={leg.route_ml?.shipment_value}
            gabungan={
              leg.route_ml
                ? { barang: leg.route_ml.shipment_items, unit: leg.route_ml.shipment_qty }
                : undefined
            }
            batasHari={leg.route_ml?.deadline_days ?? baris.route_deadline_days ?? baris.lead_time_days_int}
            onPilih={(p) => setRute((s) => (s[leg.from_warehouse_id]?.mode === p?.mode &&
              s[leg.from_warehouse_id]?.hari === p?.hari ? s : { ...s, [leg.from_warehouse_id]: p }))}
          />
        ))}

      {/* --- kaki: tindakan --- */}
      <footer
        className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 sm:px-5"
        style={{ borderTop: "1px solid var(--border)", background: "var(--surface-sunken)" }}
      >
        <button
          onClick={() => setBuka((v) => !v)}
          aria-expanded={buka}
          className="inline-flex items-center gap-1.5 t-small font-semibold"
          style={{ color: "var(--brand)" }}
        >
          <ChevronDown
            size={13}
            aria-hidden
            className="transition-transform"
            style={{ transform: buka ? "rotate(180deg)" : "none" }}
          />
          {buka ? t("tf.card.hide") : t("tf.card.details", { n: baris.candidate_count })}
        </button>

        <span className="flex-1" />

        {/* Sisa pembelian disebut DI SEBELAH tombol transfer, bukan di layar
            lain: rencana yang menutup 10 dari 13 menuntut DUA tindakan, dan
            yang kedua paling mudah terlupakan justru setelah yang pertama
            terasa selesai. */}
        {(baris.purchase_qty ?? 0) > 0 && (
          <span className="inline-flex items-center gap-1.5 t-small text-ink-2">
            <ShoppingCart size={13} style={{ color: "var(--text-muted)" }} aria-hidden />
            {t("tf.action.still_buy", { n: num(baris.purchase_qty ?? 0), unit: satuan })}
          </span>
        )}

        {baris.legs.length > 0 &&
          (nomor.length ? (
            <span
              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold"
              style={{
                background: "color-mix(in srgb, var(--status-good) 14%, transparent)",
                color: "var(--status-good)",
              }}
            >
              <PackageCheck size={13} aria-hidden /> {t("tf.action.raised", { v: nomor.join(", ") })}
            </span>
          ) : (
            <Button variant="solid" onClick={ajukan} disabled={kirim}>
              <Send size={13} aria-hidden />{" "}
              {baris.legs.length > 1
                ? t("tf.action.propose_many", { n: baris.legs.length })
                : t("tf.action.propose")}
            </Button>
          ))}

        {galat && (
          <span className="t-caption" style={{ color: "var(--status-critical)" }}>
            {galat}
          </span>
        )}
      </footer>

      {buka && <PanelKandidat baris={baris} />}
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* Kartu rute: satu kiriman, banyak barang                             */
/* ------------------------------------------------------------------ */

/** Satu baris barang di dalam kartu rute; rincian kandidatnya dapat dibuka. */
function BarisMuatan({ m }: { m: MuatanRute }) {
  const t = useT();
  const [buka, setBuka] = useState(false);
  const { baris, leg } = m;
  const satuan = baris.unit_code ?? "";

  return (
    <li>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1 px-4 py-3 sm:px-5">
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-ink" title={baris.item_name}>
            {baris.item_name}
          </p>
          <p className="tnum t-caption text-muted">{baris.sku}</p>
          {leg.match_type === "fuzzy" && (
            <p className="t-caption text-muted">
              {t("tf.fuzzy.sends", { sku: leg.sku, nama: leg.item_name })}
            </p>
          )}
          {(baris.purchase_qty ?? 0) > 0 && (
            <p className="mt-0.5 inline-flex items-center gap-1.5 t-caption text-ink-2">
              <ShoppingCart size={11} style={{ color: "var(--text-muted)" }} aria-hidden />
              {t("tf.action.still_buy", { n: num(baris.purchase_qty ?? 0), unit: satuan })}
            </p>
          )}
        </div>

        <dl className="flex shrink-0 items-start gap-5">
          <Angka label={t("tf.card.spare")} nilai={angka(leg.surplus, satuan)} />
          <Angka
            label={t("tf.card.need")}
            nilai={baris.need_qty === null ? t("tf.qty_none") : angka(baris.need_qty, satuan)}
          />
          <div className="min-w-0 text-right">
            <dt className="t-caption text-muted">{t("tf.flow.shipped")}</dt>
            <dd className="stat-figure tnum t-lead font-bold text-ink">
              {num(leg.transfer_qty)} {satuan}
            </dd>
          </div>
        </dl>
      </div>

      <button
        onClick={() => setBuka((v) => !v)}
        aria-expanded={buka}
        className="mb-2 ml-4 inline-flex items-center gap-1 t-caption font-semibold sm:ml-5"
        style={{ color: "var(--brand)" }}
      >
        <ChevronDown
          size={12}
          aria-hidden
          style={{ transform: buka ? "rotate(180deg)" : "none" }}
        />
        {buka ? t("tf.card.hide") : t("tf.card.details", { n: baris.candidate_count })}
      </button>
      {buka && <PanelKandidat baris={baris} />}
    </li>
  );
}

/**
 * Satu rute, satu kartu, satu dokumen.
 *
 * Jumlah pada panah adalah JUMLAH BARANG, bukan jumlah unit: menjumlahkan BOX,
 * PCS, dan LTR menghasilkan angka yang tidak berarti apa-apa. Berapa persisnya
 * tiap barang dibaca pada daftar di bawahnya.
 */
function KartuRute({ rute, gudang, onSegar }: {
  rute: RuteTransfer;
  gudang: { dari: KirimanTransfer; ke: BarisTransfer };
  onSegar: () => void;
}) {
  const t = useT();
  const [kirim, setKirim] = useState(false);
  const [galat, setGalat] = useState<string | null>(null);
  const [nomor, setNomor] = useState<string | null>(null);
  const [moda, setModa] = useState<PilihanRute | null>(null);

  const { dari, ke } = gudang;
  const jumlah = rute.muatan.length;
  const totalUnit = rute.muatan.reduce((a, m) => a + m.leg.transfer_qty, 0);
  const skor = Math.round(rute.muatan.reduce((a, m) => a + m.leg.score, 0) / jumlah);
  const warnaPenerima = WARNA.neutral;

  async function ajukan() {
    if (kirim || nomor) return;
    setKirim(true);
    setGalat(null);
    try {
      const r = await apiPost<{ transfer_number: string }>("/api/transfers", {
        from_warehouse_id: rute.dariId,
        to_warehouse_id: rute.keId,
        source: "transfer_engine",
        score: skor,
        reason: rute.muatan.map((m) => `${m.baris.sku}: ${m.leg.why}`).join("\n"),
        distance_km: dari.distance_km,
        transport_mode: moda?.mode,
        planned_days: moda ? Math.ceil(moda.hari) : undefined,
        items: rute.muatan.map((m) => ({
          item_id: m.leg.item_id,
          quantity: m.leg.transfer_qty,
          for_item_id: m.baris.item_id,
          match_type: m.leg.match_type,
          match_similarity: m.leg.match_similarity,
        })),
      });
      setNomor(r.transfer_number);
      onSegar();
    } catch (e) {
      setGalat((e as Error).message);
    } finally {
      setKirim(false);
    }
  }

  return (
    <article className="surface-card overflow-hidden">
      <div className="px-4 py-4 sm:px-5">
        <RelAlur>
          <BlokGudang
            peran="kirim"
            warna={WARNA.good}
            kode={dari.from_warehouse_code}
            nama={dari.from_warehouse_name}
          />
          <PanahAlur
            qty={jumlah}
            satuan={t("tf.route.items_unit")}
            keterangan={t("tf.flow.shipped")}
            km={dari.distance_km}
            dasarJarak={dari.distance_basis}
            hari={dari.lead_time_days ?? null}
            skor={skor}
          />
          <BlokGudang
            peran="terima"
            warna={warnaPenerima}
            kode={ke.to_warehouse_code}
            nama={ke.to_warehouse_name}
          />
        </RelAlur>
      </div>

      <div style={{ borderTop: "1px solid var(--border)" }}>
        <p className="px-4 pt-3 t-caption font-semibold uppercase tracking-[0.08em] text-ink-2 sm:px-5">
          {t("tf.route.manifest", { n: jumlah })}
        </p>
        <ul className="divide-y" style={{ borderColor: "var(--border)" }}>
          {rute.muatan.map((m) => (
            <BarisMuatan key={`${m.baris.item_id}-${m.leg.item_id}`} m={m} />
          ))}
        </ul>
      </div>

      {totalUnit > 0 && (
        <PanelRuteML
          dariId={rute.dariId}
          keId={rute.keId}
          jumlah={totalUnit}
          itemId={rute.muatan.length === 1 ? rute.muatan[0].leg.item_id : undefined}
          nilai={rute.muatan[0]?.leg.route_ml?.shipment_value}
          batasHari={rute.muatan[0]?.leg.route_ml?.deadline_days}
          gabungan={{ barang: jumlah, unit: totalUnit }}
          onPilih={setModa}
        />
      )}

      <footer
        className="flex flex-wrap items-center justify-end gap-x-3 gap-y-2 px-4 py-3 sm:px-5"
        style={{ borderTop: "1px solid var(--border)", background: "var(--surface-sunken)" }}
      >
        {nomor ? (
          <span
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold"
            style={{
              background: "color-mix(in srgb, var(--status-good) 14%, transparent)",
              color: "var(--status-good)",
            }}
          >
            <PackageCheck size={13} aria-hidden /> {t("tf.action.raised", { v: nomor })}
          </span>
        ) : (
          <Button variant="solid" onClick={ajukan} disabled={kirim}>
            <Send size={13} aria-hidden />{" "}
            {jumlah > 1 ? t("tf.route.propose", { n: jumlah }) : t("tf.action.propose")}
          </Button>
        )}
        {galat && (
          <span className="t-caption" style={{ color: "var(--status-critical)" }}>
            {galat}
          </span>
        )}
      </footer>
    </article>
  );
}

export function DaftarKartuTransfer({
  items,
  tab,
  onSegar,
}: {
  items: BarisTransfer[];
  tab: TabKeputusan;
  onSegar: () => void;
}) {
  const t = useT();

  if (!items.length) {
    // Kosong pada tab "dapat dipindahkan" berarti tidak ada yang bisa dihemat
    // hari ini; kosong pada tab "semua" berarti tidak ada yang kekurangan sama
    // sekali, dan itu KABAR BAIK yang harus berbunyi begitu.
    return <Empty message={tab === "" ? t("tf.empty_none_short") : t("tf.empty")} />;
  }

  // Barang yang berangkat dari gudang yang sama ke gudang yang sama dijadikan
  // SATU kartu dan SATU dokumen; barang yang murni dibeli tetap kartu sendiri.
  const { rute, beli } = kelompokkanRute(items);

  return (
    <div className="flex flex-col gap-3">
      {rute.map((r) => (
        <KartuRute
          key={r.kunci}
          rute={r}
          gudang={{ dari: r.muatan[0].leg, ke: r.muatan[0].baris }}
          onSegar={onSegar}
        />
      ))}
      {beli.map((b) => (
        <KartuTransfer key={`${b.item_id}-${b.warehouse_id}`} baris={b} onSegar={onSegar} />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Dokumen transfer                                                    */
/* ------------------------------------------------------------------ */

/*
 * Tombol per tahap. Peta ini TIDAK memutuskan tahap mana yang boleh ditekan --
 * itu datang dari `next_statuses` pada jawaban backend. Yang ditentukan di
 * sini hanya kata dan ikonnya, sehingga aturan alurnya hidup di satu tempat
 * (app/transfer.PERPINDAHAN) alih-alih disalin ke layar tempat ia cepat atau
 * lambat berbeda.
 */
const AKSI_TAHAP: Record<StatusTransfer, { kunci: string; Ikon: typeof Send; warna?: string }> = {
  draft: { kunci: "tf.doc.act.draft", Ikon: Send },
  approved: { kunci: "tf.doc.act.approve", Ikon: CheckCircle2 },
  in_transit: { kunci: "tf.doc.act.ship", Ikon: Truck },
  completed: { kunci: "tf.doc.act.receive", Ikon: PackageCheck },
  cancelled: { kunci: "tf.doc.act.cancel", Ikon: Ban, warna: "var(--status-critical)" },
};

/** Urutan tahap yang dilewati satu dokumen; "cancelled" bukan bagian deret. */
const DERET_TAHAP: StatusTransfer[] = ["draft", "approved", "in_transit", "completed"];

/**
 * Empat titik yang menjawab "sudah sampai mana".
 *
 * Cap waktunya ikut dicetak, bukan hanya titiknya. "Dikirim" tanpa tanggal
 * tidak dapat membedakan kiriman yang berangkat pagi ini dari yang berangkat
 * dua minggu lalu dan belum juga sampai -- padahal yang kedua persis keadaan
 * yang harus ditindaklanjuti seseorang hari itu juga.
 */
function GarisTahap({ d }: { d: DokumenTransfer }) {
  const t = useT();

  if (d.status === "cancelled") {
    return (
      <div
        className="flex items-center gap-2 rounded-xl px-3.5 py-2.5 t-small"
        style={{
          background: "var(--surface-sunken)",
          color: "var(--text-secondary)",
        }}
      >
        <Ban size={13} aria-hidden style={{ color: "var(--status-neutral)" }} />
        {t("tf.doc.step.cancelled")}
        <span className="tnum text-muted">{dateLabel(d.cancelled_at)}</span>
      </div>
    );
  }

  const cap: Record<string, string | null> = {
    draft: d.transfer_date,
    approved: d.approved_at,
    in_transit: d.shipped_at,
    completed: d.received_at,
  };
  const kini = DERET_TAHAP.indexOf(d.status);

  return (
    <ol className="grid grid-cols-4 gap-x-2">
      {DERET_TAHAP.map((s, i) => {
        const lewat = i <= kini;
        const warna = lewat ? TAHAP[s].warna : "var(--border-strong)";
        return (
          <li key={s} className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span
                aria-hidden
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{
                  background: lewat ? warna : "var(--surface-1)",
                  boxShadow:
                    i === kini
                      ? `0 0 0 3px color-mix(in srgb, ${warna} 22%, transparent)`
                      : `inset 0 0 0 1.5px ${warna}`,
                }}
              />
              {i < DERET_TAHAP.length - 1 && (
                <span
                  aria-hidden
                  className="h-px flex-1"
                  style={{ background: i < kini ? warna : "var(--border)" }}
                />
              )}
            </div>
            <p
              className="mt-1.5 truncate t-caption font-semibold"
              style={{ color: lewat ? "var(--text-primary)" : "var(--text-muted)" }}
            >
              {t(`tf.doc.step.${s}`)}
            </p>
            <p className="truncate tnum t-caption text-muted">
              {cap[s] ? dateLabel(cap[s]) : "—"}
            </p>
          </li>
        );
      })}
    </ol>
  );
}

/** Barang yang dibawa satu dokumen; diambil saat rinciannya dibuka. */
function BarangDokumen({ id }: { id: number }) {
  const t = useT();
  const { data, loading, error } = useApi<DetailDokumenTransfer>(`/api/transfers/${id}`);

  if (loading) return <p className="t-caption text-muted">{t("c.loading")}</p>;
  if (error) return <p className="t-caption" style={{ color: "var(--status-critical)" }}>{error}</p>;
  if (!data) return null;

  return (
    <div className="flex flex-col gap-2">
      {data.lines.map((l) => (
        <div
          key={l.id}
          className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-xl px-3.5 py-2.5"
          style={{ background: "var(--surface-1)", boxShadow: "inset 0 0 0 1px var(--border)" }}
        >
          <span className="min-w-0">
            <span className="block truncate font-semibold text-ink">{l.item_name}</span>
            <span className="block tnum t-caption text-muted">{l.sku}</span>
            {l.for_item_id && l.for_item_id !== l.item_id && (
              <span className="block t-caption text-muted">
                {t("tf.doc.for_item", { sku: l.for_sku ?? "", nama: l.for_item_name ?? "" })}
              </span>
            )}
          </span>
          <span className="text-right">
            <span className="stat-figure tnum t-lead block font-bold text-ink">
              {num(l.quantity)} {l.unit_code}
            </span>
            {l.received_quantity != null && (
              <span
                className="tnum t-caption"
                style={{
                  color:
                    l.received_quantity < l.quantity ? "var(--status-warning)" : "var(--text-muted)",
                }}
              >
                {t("tf.doc.received_of", { a: num(l.received_quantity), b: num(l.quantity) })}
              </span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

/**
 * Konfirmasi penerimaan: petugas gudang TUJUAN menghitung barang yang benar-
 * benar sampai. Bawaannya sama dengan jumlah kirim, jadi kiriman yang utuh
 * cukup satu ketukan; yang kurang hanya perlu mengubah angkanya.
 *
 * Biaya angkut boleh dikosongkan: tagihan ekspedisi biasanya menyusul dan
 * diisi orang keuangan (lihat KotakBiaya). Dokumen tanpa biaya tetap sah, dan
 * hanya tidak ikut melatih model biaya.
 */
function FormTerima({
  d,
  onSelesai,
  onBatal,
}: {
  d: DokumenTransfer;
  onSelesai: () => void;
  onBatal: () => void;
}) {
  const t = useT();
  const { data, loading, error } = useApi<DetailDokumenTransfer>(`/api/transfers/${d.id}`);
  const [nilai, setNilai] = useState<Record<number, string>>({});
  const [biaya, setBiaya] = useState("");
  const [kirim, setKirim] = useState(false);
  const [galat, setGalat] = useState<string | null>(null);

  const baris = data?.lines ?? [];
  const jumlahTerima = (l: { item_id: number; quantity: number }) => {
    const v = nilai[l.item_id];
    return v === undefined || v === "" ? l.quantity : Number(v);
  };
  const lebih = baris.some((l) => jumlahTerima(l) > l.quantity || jumlahTerima(l) < 0 || Number.isNaN(jumlahTerima(l)));
  const selisih = baris.reduce((a, l) => a + Math.max(0, l.quantity - jumlahTerima(l)), 0);

  async function simpan() {
    if (kirim || lebih || !baris.length) return;
    setKirim(true);
    setGalat(null);
    try {
      await apiPatch(`/api/transfers/${d.id}/status`, {
        status: "completed",
        received: baris.map((l) => ({ item_id: l.item_id, received_quantity: jumlahTerima(l) })),
        shipping_cost: biaya.trim() === "" ? undefined : Number(biaya),
      });
      onSelesai();
    } catch (e) {
      setGalat((e as Error).message);
    } finally {
      setKirim(false);
    }
  }

  return (
    <div
      className="border-t px-4 py-4 sm:px-5"
      style={{ borderColor: "var(--border)", background: "var(--surface-sunken)" }}
    >
      <JudulPanel>{t("tf.recv.title")}</JudulPanel>
      <p className="mt-1 t-caption text-muted">{t("tf.recv.hint")}</p>

      {loading && <p className="mt-2 t-caption text-muted">{t("c.loading")}</p>}
      {error && <p className="mt-2 t-caption" style={{ color: "var(--status-critical)" }}>{error}</p>}

      <div className="mt-3 flex flex-col gap-2">
        {baris.map((l) => (
          <div
            key={l.id}
            className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-xl px-3.5 py-2.5"
            style={{ background: "var(--surface-1)", boxShadow: "inset 0 0 0 1px var(--border)" }}
          >
            <span className="min-w-0">
              <span className="block truncate font-semibold text-ink">{l.item_name}</span>
              <span className="block tnum t-caption text-muted">
                {l.sku} · {t("tf.recv.line", { n: `${num(l.quantity)} ${l.unit_code}` })}
              </span>
            </span>
            <span className="w-28">
              <TextInput
                type="number"
                value={nilai[l.item_id] ?? String(l.quantity)}
                onChange={(v) => setNilai((s) => ({ ...s, [l.item_id]: v }))}
              />
            </span>
          </div>
        ))}
      </div>

      {lebih && (
        <p className="mt-2 t-caption" style={{ color: "var(--status-critical)" }}>{t("tf.recv.over")}</p>
      )}
      {!lebih && selisih > 0 && (
        <p className="mt-2 t-caption" style={{ color: "var(--status-warning)" }}>
          {t("tf.recv.short", { n: num(selisih) })}
        </p>
      )}

      <div className="mt-3 max-w-sm">
        <span className="t-caption text-muted">{t("tf.recv.cost")}</span>
        <TextInput type="number" value={biaya} onChange={setBiaya} placeholder="0" />
        <span className="mt-1 block t-caption text-muted">{t("tf.recv.cost_hint")}</span>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button variant="solid" onClick={simpan} disabled={kirim || lebih || !baris.length}>
          <PackageCheck size={13} aria-hidden /> {t("tf.recv.confirm")}
        </Button>
        <Button variant="ghost" onClick={onBatal} disabled={kirim}>
          {t("tf.recv.cancel")}
        </Button>
        {galat && <span className="t-caption" style={{ color: "var(--status-critical)" }}>{galat}</span>}
      </div>
    </div>
  );
}

/**
 * Biaya angkut sesungguhnya, diisi belakangan. Tagihan ekspedisi biasanya tiba
 * beberapa hari sesudah barang sampai dan yang memegangnya orang keuangan --
 * karena itu ini kotak tersendiri pada kartu, bukan bagian dari menerima.
 */
function KotakBiaya({ d, onSegar }: { d: DokumenTransfer; onSegar: () => void }) {
  const t = useT();
  const [ubah, setUbah] = useState(false);
  const [nilai, setNilai] = useState(d.shipping_cost != null ? String(Number(d.shipping_cost)) : "");
  const [kirim, setKirim] = useState(false);
  const [galat, setGalat] = useState<string | null>(null);

  async function simpan() {
    if (kirim) return;
    setKirim(true);
    setGalat(null);
    try {
      await apiPatch(`/api/transfers/${d.id}/biaya`, {
        shipping_cost: nilai.trim() === "" ? null : Number(nilai),
      });
      setUbah(false);
      onSegar();
    } catch (e) {
      setGalat((e as Error).message);
    } finally {
      setKirim(false);
    }
  }

  if (ubah) {
    return (
      <span className="inline-flex flex-wrap items-center gap-2">
        <span className="w-40">
          <TextInput type="number" value={nilai} onChange={setNilai} placeholder="Rp" onEnter={simpan} />
        </span>
        <Button variant="solid" onClick={simpan} disabled={kirim}>{t("tf.cost.save")}</Button>
        <Button variant="ghost" onClick={() => setUbah(false)} disabled={kirim}>{t("tf.recv.cancel")}</Button>
        {galat && <span className="t-caption" style={{ color: "var(--status-critical)" }}>{galat}</span>}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-2 t-caption text-ink-2">
      {d.shipping_cost != null ? (
        <>
          {t("tf.doc.cost")}: <strong className="tnum text-ink">{idr(d.shipping_cost)}</strong>
          <button className="font-semibold" style={{ color: "var(--brand)" }} onClick={() => setUbah(true)}>
            {t("tf.cost.edit")}
          </button>
        </>
      ) : (
        <>
          <span style={{ color: "var(--status-warning)" }}>{t("tf.cost.missing")}</span>
          <button className="font-semibold" style={{ color: "var(--brand)" }} onClick={() => setUbah(true)}>
            {t("tf.cost.record")}
          </button>
        </>
      )}
    </span>
  );
}

/** Moda, biaya, dan janji vs lama tempuh sesungguhnya satu dokumen. */
function InfoAngkut({ d, onSegar }: { d: DokumenTransfer; onSegar: () => void }) {
  const t = useT();
  const aktual =
    d.shipped_at && d.received_at
      ? (new Date(d.received_at).getTime() - new Date(d.shipped_at).getTime()) / 86_400_000
      : null;
  return (
    <p className="flex flex-wrap items-center gap-x-3 gap-y-1 t-caption text-ink-2">
      <span>
        {t("tf.doc.mode")}: <strong className="text-ink">{t(`rt.mode.${d.transport_mode}`)}</strong>
      </span>
      {(d.status === "in_transit" || d.status === "completed") && (
        <KotakBiaya key={String(d.shipping_cost)} d={d} onSegar={onSegar} />
      )}
      {d.planned_days != null && (
        <span>
          {t("tf.doc.promised")}:{" "}
          <strong className="tnum text-ink">{t("rt.days", { n: num(d.planned_days, 0) })}</strong>
        </span>
      )}
      {aktual != null && (
        <span>
          {t("tf.doc.actual")}:{" "}
          <strong className="tnum text-ink">{t("rt.days", { n: num(aktual, 1) })}</strong>
        </span>
      )}
    </p>
  );
}

function KartuDokumen({
  d,
  onSegar,
  terpilih,
  onPilih,
}: {
  d: DokumenTransfer;
  onSegar: () => void;
  /** kartu ini yang sedang disorot peta */
  terpilih: boolean;
  onPilih: () => void;
}) {
  const t = useT();
  const [kirim, setKirim] = useState(false);
  const [buka, setBuka] = useState(false);
  const [terima, setTerima] = useState(false);
  const [galat, setGalat] = useState<string | null>(null);

  async function pindah(status: StatusTransfer) {
    // "Diterima" tidak langsung mengubah status: petugas lebih dulu diminta
    // mengonfirmasi jumlah yang benar-benar sampai.
    if (status === "completed") {
      setTerima(true);
      return;
    }
    if (kirim) return;
    setKirim(true);
    setGalat(null);
    try {
      await apiPatch(`/api/transfers/${d.id}/status`, { status });
      onSegar();
    } catch (e) {
      setGalat((e as Error).message);
    } finally {
      setKirim(false);
    }
  }

  const warnaTahap = TAHAP[d.status]?.warna ?? WARNA.neutral;

  return (
    <article
      /*
       * Id-nya dipakai peta untuk menggulung kartu ini ke depan mata saat
       * rutenya ditunjuk di sana. Tanpa itu, memilih sebuah rute pada peta
       * memilih pula sebuah kartu yang berada tiga layar di bawah -- sorotan
       * yang tidak pernah dilihat siapa pun.
       */
      id={`tf-kartu-${d.id}`}
      aria-current={terpilih ? "true" : undefined}
      /*
       * Seluruh kartu memilih dirinya, KECUALI bila yang ditekan sebuah tombol.
       * Tombol di dalamnya menggerakkan dokumen ke tahap berikutnya, dan
       * penekanan yang ikut memindahkan peta membuat pembacanya ragu apakah
       * tahapnya benar-benar berubah.
       */
      onClick={(e) => {
        if ((e.target as HTMLElement).closest("button")) return;
        onPilih();
      }}
      className="surface-card overflow-hidden"
      style={{
        borderLeft: `3px solid ${warnaTahap}`,
        boxShadow: terpilih
          ? `var(--elev-2), 0 0 0 2px color-mix(in srgb, ${warnaTahap} 55%, transparent)`
          : undefined,
      }}
    >
      <header
        className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2 px-4 py-3.5 sm:px-5"
        style={{ borderBottom: "1px solid var(--border)" }}
      >
        <div className="min-w-0">
          <h3 className="truncate tnum t-lead font-semibold text-ink">{d.transfer_number}</h3>
          <p className="mt-0.5 t-caption text-muted">{dateLabel(d.transfer_date)}</p>
        </div>
        <PillTahap tahap={d.status} label={d.status_label} />
      </header>

      <div className="flex flex-col gap-4 px-4 py-4 sm:px-5">
        <RelAlur>
          <BlokGudang
            peran="kirim"
            warna={WARNA.good}
            kode={d.from_warehouse_code}
            nama={d.from_warehouse_name}
          />
          <PanahAlur
            qty={d.total_quantity}
            satuan=""
            keterangan={t("tf.doc.qty_hint", { n: num(d.line_count) })}
            km={d.distance_km === null ? null : Number(d.distance_km)}
            dasarJarak={null}
            skor={d.score}
          />
          <BlokGudang
            peran="terima"
            warna={WARNA.neutral}
            kode={d.to_warehouse_code}
            nama={d.to_warehouse_name}
          />
        </RelAlur>

        <GarisTahap d={d} />

        {d.transport_mode && <InfoAngkut d={d} onSegar={onSegar} />}

        {d.reason && <p className="t-small leading-relaxed text-ink-2">{d.reason}</p>}
      </div>

      <footer
        className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 py-3 sm:px-5"
        style={{ borderTop: "1px solid var(--border)", background: "var(--surface-sunken)" }}
      >
        <button
          onClick={() => setBuka((v) => !v)}
          aria-expanded={buka}
          className="inline-flex items-center gap-1.5 t-small font-semibold"
          style={{ color: "var(--brand)" }}
        >
          <ChevronDown
            size={13}
            aria-hidden
            className="transition-transform"
            style={{ transform: buka ? "rotate(180deg)" : "none" }}
          />
          {buka ? t("tf.card.hide") : t("tf.doc.items", { n: num(d.line_count) })}
        </button>

        {/*
          Jalan yang TERLIHAT menuju peta. Seluruh kartu memang dapat ditekan,
          tetapi tidak ada satu pun tanda yang mengatakannya -- dan kemampuan
          yang tidak terlihat sama saja dengan kemampuan yang tidak ada.
        */}
        <button
          onClick={onPilih}
          aria-pressed={terpilih}
          className="inline-flex items-center gap-1.5 t-small font-semibold"
          style={{ color: terpilih ? warnaTahap : "var(--text-secondary)" }}
        >
          <MapIcon size={13} aria-hidden />
          {terpilih ? t("tf.doc.selected") : t("tf.doc.on_map")}
        </button>

        <span className="flex-1" />

        {d.next_statuses.map((s) => {
          const a = AKSI_TAHAP[s];
          return (
            <Button
              key={s}
              onClick={() => pindah(s)}
              disabled={kirim}
              color={a.warna}
              variant={a.warna ? "ghost" : "solid"}
            >
              <a.Ikon size={13} aria-hidden /> {t(a.kunci)}
            </Button>
          );
        })}

        {galat && (
          <span className="t-caption" style={{ color: "var(--status-critical)" }}>
            {galat}
          </span>
        )}
      </footer>

      {terima && (
        <FormTerima
          d={d}
          onBatal={() => setTerima(false)}
          onSelesai={() => {
            setTerima(false);
            onSegar();
          }}
        />
      )}

      {buka && (
        <div
          className="border-t px-4 py-4 sm:px-5"
          style={{ borderColor: "var(--border)", background: "var(--surface-sunken)" }}
        >
          <JudulPanel>{t("tf.doc.lines_title")}</JudulPanel>
          <BarangDokumen id={d.id} />
        </div>
      )}
    </article>
  );
}

/* ------------------------------------------------------------------ */
/* Peta + daftar dokumen                                               */
/* ------------------------------------------------------------------ */

/**
 * Peta dimuat HANYA DI PERAMBAN, dan itu bukan pilihan gaya.
 *
 * Leaflet menyentuh `document` saat modulnya dievaluasi -- ia membaca gaya
 * dokumen untuk mendeteksi kemampuan peramban. Diimpor biasa, modul itu ikut
 * dijalankan saat Next merender halaman ini di server, dan `next build`
 * berhenti dengan "document is not defined". `ssr: false` membuat modulnya
 * tidak pernah dievaluasi di sana, sekaligus menghapus seluruh kelas galat
 * hidrasi: tidak ada markup peta yang dirender server untuk diperselisihkan
 * klien, karena servernya tidak merender peta sama sekali.
 */
const PetaTransfer = dynamic(() => import("@/components/peta-transfer"), {
  ssr: false,
  loading: () => (
    <div className="surface-card overflow-hidden">
      <div className="pt-tinggi w-full" style={{ background: "var(--surface-sunken)" }} />
    </div>
  ),
});

/**
 * Layar Dokumen: peta di atas, kartu di bawah, SATU pilihan yang dipakai
 * keduanya.
 *
 * KENAPA PILIHANNYA HIDUP DI SINI dan bukan di dalam salah satunya. Menunjuk
 * rute di peta harus menyorot kartunya, dan menekan kartu harus memperbesar
 * rutenya -- dua arah dari satu keadaan. Bila peta menyimpan pilihannya sendiri
 * dan daftar menyimpan pilihannya sendiri, keduanya cepat atau lambat menunjuk
 * dokumen yang berbeda, dan tidak ada satu pun galat yang terbit dari itu:
 * hanya layar yang menyorot satu dokumen di atas dan dokumen lain di bawah.
 *
 * ASALNYA IKUT DICATAT karena akibatnya berbeda. Pilihan dari peta menggulung
 * kartunya ke depan mata; pilihan dari kartu tidak boleh menggulung apa pun --
 * pembacanya sudah berada di sana, dan halaman yang melompat sendiri sesudah
 * ditekan terbaca sebagai kesalahan tekan.
 */
/**
 * SATU pilihan dokumen, dipakai bersama peta dan daftar kartu.
 *
 * KENAPA SEBUAH HOOK, BUKAN KEADAAN DI DALAM SALAH SATUNYA. Sejak peta naik ke
 * atas pemilih layar (4 September 2026), peta dan daftar kartu tidak lagi
 * bertetangga di dalam satu komponen: peta berdiri tepat di bawah penyaring dan
 * SELALU terlihat, sedangkan kartunya hanya muncul pada layar Dokumen. Keduanya
 * tetap harus menunjuk dokumen yang SAMA -- menunjuk rute di peta menyorot
 * kartunya, menekan kartu memperbesar rutenya -- dan satu-satunya cara
 * memastikannya adalah satu keadaan yang dipegang bersama.
 *
 * ASALNYA IKUT DICATAT karena akibatnya berbeda. Pilihan dari peta menggulung
 * kartunya ke depan mata; pilihan dari kartu tidak boleh menggulung apa pun --
 * pembacanya sudah berada di sana, dan halaman yang melompat sendiri sesudah
 * ditekan terbaca sebagai kesalahan tekan.
 */
export function usePilihTransfer(items: DokumenTransfer[]) {
  const [pilih, setPilih] = useState<number | null>(null);
  const [asal, setAsal] = useState<"peta" | "daftar">("daftar");

  // Berpindah halaman atau menyaring dapat membuang dokumen yang sedang
  // disorot. Sorotan yang tertinggal pada dokumen yang tidak ada lagi di layar
  // menahan peta pada rute yang tidak dapat ditelusuri ke kartu mana pun.
  useEffect(() => {
    if (pilih !== null && !items.some((d) => d.id === pilih)) setPilih(null);
  }, [items, pilih]);

  useEffect(() => {
    if (pilih === null || asal !== "peta") return;
    // Kartunya boleh belum ada: pilihan dapat lahir dari peta selagi pembaca
    // berada di layar Rekomendasi. Yang memunculkan kartunya adalah perpindahan
    // layar yang menyertainya, bukan gulungan ini.
    document
      .getElementById(`tf-kartu-${pilih}`)
      ?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [pilih, asal]);

  /*
   * Identitasnya DIJAGA TETAP. Peta menggambar ulang seluruh lapisannya setiap
   * kali fungsi ini berganti; fungsi sebaris yang lahir baru pada tiap render
   * membuat busur dan penandanya dihapus lalu dipasang kembali berkali-kali per
   * detik -- peta yang berkedip, dan klik yang jatuh ke lapisan yang sudah
   * dibuang.
   */
  const dariPeta = useCallback((id: number | null) => {
    setAsal("peta");
    setPilih(id);
  }, []);

  const dariDaftar = useCallback((id: number) => {
    setAsal("daftar");
    setPilih((kini) => (kini === id ? null : id));
  }, []);

  return { pilih, dariPeta, dariDaftar };
}

/**
 * Peta rute, siap dipasang di mana pun pada halaman.
 *
 * Pembungkus setipis mungkin di atas komponen peta yang dimuat malas: yang
 * ditambahkannya hanya batas modul, sehingga halaman tidak perlu tahu bahwa
 * peta itu tidak boleh dirender di server.
 */
export function PetaDokumen(props: {
  items: DokumenTransfer[];
  gudang: GudangApi[];
  /** baris rekomendasi mentah; petanya sendiri yang menyaring mana yang layak digambar */
  usulan: BarisTransfer[];
  memuat: boolean;
  galat: string | null;
  pilih: number | null;
  onPilih: (id: number | null) => void;
}) {
  return (
    <PetaTransfer
      dokumen={props.items}
      gudang={props.gudang}
      usulan={props.usulan}
      pilih={props.pilih}
      onPilih={props.onPilih}
      memuat={props.memuat}
      galat={props.galat}
    />
  );
}

export function DaftarKartuDokumen({
  items,
  onSegar,
  pilih,
  onPilih,
}: {
  items: DokumenTransfer[];
  onSegar: () => void;
  pilih: number | null;
  onPilih: (id: number) => void;
}) {
  const t = useT();
  if (!items.length) return <Empty message={t("tf.doc.empty")} />;

  return (
    <div className="flex flex-col gap-3">
      {items.map((d) => (
        <KartuDokumen
          key={d.id}
          d={d}
          onSegar={onSegar}
          terpilih={d.id === pilih}
          onPilih={() => onPilih(d.id)}
        />
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Saringan                                                            */
/* ------------------------------------------------------------------ */

export function SaringanTransfer({
  gudang,
  warehouseId,
  setWarehouseId,
  cari,
  setCari,
  fuzzy,
  setFuzzy,
  periode,
  setPeriode,
  model,
  setModel,
}: {
  periode: string;
  setPeriode: (v: string) => void;
  model: string;
  setModel: (v: string) => void;
  gudang: { id: number; code: string; name: string }[];
  warehouseId: string;
  setWarehouseId: (v: string) => void;
  cari: string;
  setCari: (v: string) => void;
  fuzzy: boolean;
  setFuzzy: (v: boolean) => void;
}) {
  const t = useT();
  return (
    <div className="baris-saring flex flex-wrap items-end gap-3">
      <Field label={t("tf.filter.destination")}>
        <Select
          value={warehouseId}
          onChange={setWarehouseId}
          options={[
            { value: "", label: t("tf.filter.all_warehouse") },
            ...gudang.map((w) => ({ value: String(w.id), label: `${w.name} (${w.code})` })),
          ]}
          className="min-w-[220px]"
        />
      </Field>
      {/* Periode dan Model yang sama dengan Prakiraan dan Pemesanan Ulang:
          kekurangan yang ditutup di sini adalah kekurangan untuk periode itu. */}
      <PemilihPeriode periode={periode} setPeriode={setPeriode} />
      <PemilihModel model={model} setModel={setModel} />
      <Field label={t("tf.search")}>
        <TextInput value={cari} onChange={setCari} placeholder={t("tf.search")} />
      </Field>
      {/*
        Pencocokan nama MATI secara bawaan, dan saklarnya berdiri di sini
        alih-alih tersembunyi di Pengaturan. Ia mengubah barang apa yang
        dianggap sama, jadi yang menyalakannya harus melihat akibatnya pada
        daftar yang sedang dibacanya -- dan dapat mematikannya kembali seketika
        bila hasilnya tidak masuk akal.
      */}
      <Field label={t("tf.filter.fuzzy")} petunjuk={t("tf.filter.fuzzy_hint")}>
        <label className="flex h-9 cursor-pointer items-center gap-2 t-small text-ink-2">
          <input
            type="checkbox"
            checked={fuzzy}
            onChange={(e) => setFuzzy(e.target.checked)}
            className="h-4 w-4 cursor-pointer accent-[var(--brand)]"
          />
          {t("tf.filter.fuzzy_label")}
        </label>
      </Field>
    </div>
  );
}

/** Peringatan bahwa daftarnya dipotong; tidak boleh disembunyikan. */
export function PeringatanTerpotong({ batas }: { batas: number }) {
  const t = useT();
  return (
    <div
      className="mt-3 flex items-start gap-2.5 rounded-xl px-4 py-3 t-small leading-relaxed"
      style={{
        background: "color-mix(in srgb, var(--status-warning) 10%, var(--surface-1))",
        boxShadow: "inset 0 0 0 1px var(--border)",
        color: "var(--text-secondary)",
      }}
    >
      <AlertTriangle
        size={14}
        className="mt-0.5 shrink-0"
        style={{ color: "var(--status-warning)" }}
      />
      {t("tf.truncated", { n: batas })}
    </div>
  );
}
