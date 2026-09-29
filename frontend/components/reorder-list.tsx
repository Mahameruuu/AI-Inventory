"use client";

/**
 * Daftar keputusan pemesanan ulang / Reorder decision list.
 *
 * BERORIENTASI TINDAKAN, BUKAN PERHITUNGAN. Layar ini menjawab satu pertanyaan
 * yang dibawa orang pengadaan: MANA SAJA yang perlu dipesan hari ini, dan
 * berapa. Nama model, galat terskala, dan papan skor tidak punya tempat di
 * sini -- bukan karena tidak menarik, melainkan karena tidak satu pun dapat
 * ditindaklanjuti oleh orang yang sedang menyusun pesanan pembelian.
 *
 * TIDAK ADA SATU PUN RUMUS DI BERKAS INI. Status, prioritas, jumlah, dan
 * kalimat alasannya seluruhnya datang jadi dari GET /api/reorder, yang
 * menghitungnya lewat jalur yang sama persis dengan /api/forecast. Karena itu
 * satu barang mustahil menyebut angka berbeda di daftar ini dan di halaman
 * Prakiraan.
 *
 * URUTAN BARISNYA DITENTUKAN BACKEND: paling mendesak lebih dulu, lalu
 * prioritas, lalu jumlah terbesar. Daftar yang benar isinya tetapi acak
 * urutannya menuntut pembacanya memindai seluruh halaman untuk menemukan yang
 * genting -- dan pada halaman kedua, ia tidak akan menemukannya sama sekali.
 */

import Link from "next/link";
import { useState } from "react";

import {
  AlertTriangle,
  ArrowUpRight,
  ChevronDown,
  PackageCheck,
  ShoppingCart,
  TrendingUp,
} from "lucide-react";

import { angka, useLabelAksi } from "@/components/forecast-ui";
import { PillAksi, PRIORITAS, WARNA } from "@/components/status";
import {
  Button,
  Empty,
  Field,
  Select,
  StatTile,
  Table,
  TextInput,
  Th,
  useUrutTabel,
} from "@/components/ui";
import { apiPost } from "@/lib/api";
import { BarisReorder, RingkasReorder } from "@/lib/forecast-types";
import { useT } from "@/lib/i18n";
import { num } from "@/lib/format";

/* ------------------------------------------------------------------ */
/* Ringkasan                                                           */
/* ------------------------------------------------------------------ */

/**
 * Empat kartu ringkas.
 *
 * ANGKANYA ATAS SELURUH HASIL SARINGAN, bukan atas halaman yang sedang
 * ditampilkan dan bukan pula atas tab yang sedang dibuka -- backend
 * menghitungnya sebelum saringan status dijalankan. Kartu yang berubah angkanya
 * hanya karena pembacanya berpindah tab tidak dapat dipakai mengambil keputusan
 * apa pun.
 *
 * Kartu "Aman" SENGAJA TIDAK ADA. Tiga kartu pertama menghitung pekerjaan yang
 * harus dilakukan; jumlah barang yang tidak menuntut apa-apa bukan pekerjaan,
 * dan mencetaknya sejajar membuat layar terbaca seolah "aman" adalah salah satu
 * hal yang perlu ditangani. Angkanya tetap ada pada tab Aman bagi yang mencari.
 */
export function RingkasanReorder({ ringkas }: { ringkas: RingkasReorder }) {
  const t = useT();
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile
        label={t("rl.kpi.need")}
        value={num(ringkas.perlu_reorder)}
        hint={t("rl.kpi.need_hint")}
        accent={ringkas.perlu_reorder > 0 ? "var(--status-warning)" : undefined}
      />
      <StatTile
        label={t("rl.kpi.high")}
        value={num(ringkas.prioritas_tinggi)}
        hint={t("rl.kpi.high_hint")}
        accent={ringkas.prioritas_tinggi > 0 ? WARNA[PRIORITAS.TINGGI] : undefined}
      />
      <StatTile
        label={t("rl.kpi.stockout")}
        value={num(ringkas.risiko_stockout)}
        hint={t("rl.kpi.stockout_hint")}
        accent={ringkas.risiko_stockout > 0 ? "var(--status-critical)" : undefined}
      />
      {/*
        Jumlah total dicetak TANPA satuan tunggal, dan itu disengaja: baris yang
        dijumlahkan bersatuan campur -- BOX, LTR, PCS -- jadi menuliskan satu
        satuan di belakangnya akan berbohong. Yang benar tentang angka ini hanya
        bahwa ia jumlah unit; satuan aslinya ada pada tiap barisnya.

        Barang yang jumlahnya belum dapat dihitung TIDAK dijumlahkan sebagai
        nol; banyaknya disebut terpisah supaya total yang terlihat tidak
        diam-diam lebih kecil daripada kebutuhan sebenarnya.
      */}
      <StatTile
        label={t("rl.kpi.qty")}
        value={`${num(ringkas.total_qty)} ${t("rl.kpi.units")}`}
        hint={
          ringkas.qty_belum_terhitung > 0
            ? t("rl.kpi.qty_pending", { n: ringkas.qty_belum_terhitung })
            : t("rl.kpi.qty_hint")
        }
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tab status                                                          */
/* ------------------------------------------------------------------ */

export type TabStatus = "" | "PERLU_REORDER" | "RISIKO_STOCKOUT" | "AMAN";

/**
 * Tab status.
 *
 * INILAH saringan statusnya; tidak ada dropdown status kedua di baris filter.
 * Dua kendali yang menyetel satu keadaan yang sama membuat pembaca harus
 * memeriksa keduanya untuk tahu apa yang sedang dilihatnya, dan pada saat
 * keduanya tidak sinkron -- yang cepat atau lambat terjadi -- tidak ada cara
 * menebak mana yang berlaku.
 *
 * Jumlah baris ikut dicetak pada tiap tab supaya pembaca tahu ada berapa
 * sebelum menekannya. Tab kosong tidak disembunyikan: yang ingin diketahui dari
 * "Risiko stockout" justru sering bahwa isinya memang nol.
 */
export function TabReorder({
  aktif,
  setAktif,
  ringkas,
}: {
  aktif: TabStatus;
  setAktif: (v: TabStatus) => void;
  ringkas: RingkasReorder;
}) {
  const t = useT();
  const tabs: { key: TabStatus; label: string; n: number }[] = [
    { key: "", label: t("rl.tab.all"), n: ringkas.total_baris },
    { key: "PERLU_REORDER", label: t("rl.tab.need"), n: ringkas.perlu_reorder },
    { key: "RISIKO_STOCKOUT", label: t("rl.tab.stockout"), n: ringkas.risiko_stockout },
    { key: "AMAN", label: t("rl.tab.safe"), n: ringkas.aman },
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
/* Lencana status & prioritas                                          */
/* ------------------------------------------------------------------ */

/*
 * Lencananya sendiri kini tinggal di components/status.tsx. Rakitan
 * `color-mix` yang dulu ada di sini adalah salinan ketiga dari bentuk yang
 * sama -- berbeda tinggi dan tebal cincinnya dari dua salinan lain, dan
 * ketiganya pernah tampil berdampingan di satu layar Dasbor.
 */
function LencanaStatus({ baris }: { baris: BarisReorder }) {
  const label = useLabelAksi();
  return <PillAksi status={baris.action_status} label={label.status(baris.action_status)} />;
}

/**
 * Prioritas sebagai TEKS BERWARNA, bukan lencana kedua.
 *
 * Dua lencana berdampingan pada satu baris saling bersaing, dan yang menang
 * biasanya yang kanan -- padahal statuslah yang menentukan tindakan. Prioritas
 * hanya mengurutkan di dalam status yang sama, jadi bobot visualnya harus lebih
 * ringan.
 */
function TandaPrioritas({ baris }: { baris: BarisReorder }) {
  const t = useT();
  if (baris.priority === "RENDAH") return null;
  const warna =
    baris.priority === "TINGGI" ? WARNA[PRIORITAS.TINGGI] : "var(--text-secondary)";
  return (
    <span className="t-caption font-semibold" style={{ color: warna }}>
      {t(`ro.prio.${baris.priority}`)}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Detail perhitungan satu baris                                       */
/* ------------------------------------------------------------------ */

function BarisHitung({
  label,
  nilai,
  dasar,
  tebal = false,
}: {
  label: string;
  nilai: string;
  dasar?: string;
  tebal?: boolean;
}) {
  return (
    <tr>
      <td className="py-1.5 pr-4 align-top">
        <span className={tebal ? "font-semibold text-ink" : "text-ink-2"}>{label}</span>
        {dasar && <span className="block t-caption leading-relaxed text-muted">{dasar}</span>}
      </td>
      <td className="py-1.5 text-right align-top">
        <span className={`tnum ${tebal ? "font-semibold text-ink" : "text-ink-2"}`}>{nilai}</span>
      </td>
    </tr>
  );
}

/**
 * Rantai perhitungan satu barang, tertutup sampai dibuka.
 *
 * Disusun sebagai ALUR DERIVASI, bukan daftar properti: tiap baris memakai
 * hasil baris di atasnya, dan keterangan kecil di bawah labelnya menyebut dari
 * mana ia datang. Yang ingin diperiksa pembaca yang meragukan angka pesanan
 * bukan "berapa safety stock-nya" melainkan "kenapa jumlahnya segitu", dan itu
 * hanya terjawab bila urutannya terlihat.
 *
 * ANGKANYA SELURUHNYA DARI BACKEND. Tidak ada perkalian yang dikerjakan di
 * sini -- termasuk kebutuhan masa tunggu, yang tampak sepele untuk dihitung
 * ulang di layar dan justru karena itu paling mudah berselisih setelah salah
 * satu sisi diubah.
 */
function DetailBaris({
  baris,
  onPo,
  poNomor,
  poKirim,
  poGalat,
}: {
  baris: BarisReorder;
  onPo: () => void;
  poNomor: string | null;
  poKirim: boolean;
  poGalat: string | null;
}) {
  const t = useT();
  const u = baris.unit_code ?? "";
  const belumDiisi = t("rl.detail.unset");

  return (
    <div
      className="border-t px-4 py-4 sm:px-5"
      style={{ borderColor: "var(--border)", background: "var(--surface-sunken)" }}
    >
      <div className="flex flex-wrap gap-x-10 gap-y-5">
        <div className="min-w-[19rem] flex-1">
          <h4 className="mb-2 t-small font-semibold uppercase tracking-[0.06em] text-ink-2">
            {t("rl.detail.chain")}
          </h4>
          <table className="w-full t-small">
            <tbody>
              <BarisHitung
                label={t("rl.detail.rate")}
                nilai={`${baris.usage_frequency_label} ${baris.usage_frequency_detail}`.trim()}
              />
              <BarisHitung
                label={t("rl.detail.lead")}
                nilai={
                  baris.lead_time_days_int !== null
                    ? t("c.days", { n: num(baris.lead_time_days_int) })
                    : belumDiisi
                }
              />
              <BarisHitung
                label={t("rl.detail.ltd")}
                nilai={angka(baris.lead_time_demand_int, u)}
              />
              <BarisHitung label={t("rl.detail.safety")} nilai={angka(baris.safety_stock_int, u)} />
              <BarisHitung
                label={t("rl.detail.rop_master")}
                nilai={angka(baris.reorder_point_int, u)}
              />
              <BarisHitung
                label={t("rl.detail.erop")}
                dasar={t("rl.detail.erop_basis")}
                nilai={angka(baris.effective_reorder_point_int, u)}
                tebal
              />
              <BarisHitung
                label={t("rl.detail.horizon", { n: baris.decision_horizon_days })}
                dasar={t("rl.detail.horizon_basis")}
                nilai={angka(baris.forecast_usage_int, u)}
              />
              <BarisHitung
                label={t("rl.detail.target")}
                dasar={t("rl.detail.target_basis")}
                nilai={angka(baris.order_up_to_level_int, u)}
              />
              <BarisHitung
                label={t("rl.detail.available")}
                nilai={angka(baris.available_stock_int, u)}
              />
              <BarisHitung
                label={t("rl.detail.qty")}
                dasar={t("rl.detail.qty_basis")}
                nilai={
                  baris.recommended_order_qty === null
                    ? t("rl.qty_none")
                    : angka(baris.recommended_order_qty, u)
                }
                tebal
              />
            </tbody>
          </table>
        </div>

        <div className="flex min-w-[13rem] flex-col items-start gap-3">
          {/*
            Tombol PO hanya terbit bila memang ada yang perlu dipesan. Pada
            baris aman ia akan menawarkan pembuatan pesanan berjumlah nol --
            tindakan yang tidak berarti apa-apa dan tetap meninggalkan draft
            di daftar PO.
          */}
          {(baris.recommended_order_qty ?? 0) > 0 && (
            <>
              {poNomor ? (
                <span
                  className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold"
                  style={{
                    background: "color-mix(in srgb, var(--status-good) 14%, transparent)",
                    color: "var(--status-good)",
                  }}
                >
                  <PackageCheck size={13} /> {t("rl.detail.po_done", { v: poNomor })}
                </span>
              ) : (
                <Button variant="solid" onClick={onPo} disabled={poKirim}>
                  <ShoppingCart size={13} /> {t("rl.detail.po")}
                </Button>
              )}
              {poGalat && (
                <span className="t-caption" style={{ color: "var(--status-critical)" }}>
                  {poGalat}
                </span>
              )}
            </>
          )}
          <Link
            href="/forecasting"
            className="inline-flex items-center gap-1.5 text-xs font-semibold"
            style={{ color: "var(--brand)" }}
          >
            <TrendingUp size={13} /> {t("rl.detail.forecast_link")} <ArrowUpRight size={12} />
          </Link>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Tabel                                                               */
/* ------------------------------------------------------------------ */

function Sel({
  children,
  align = "left",
  className = "",
}: {
  children: React.ReactNode;
  align?: "left" | "right";
  className?: string;
}) {
  return (
    <td
      className={`px-3 py-3 t-body ${align === "right" ? "text-right" : ""} ${className}`}
      style={{ color: "var(--text-secondary)" }}
    >
      {children}
    </td>
  );
}

/**
 * Satu baris, dan detailnya yang tersembunyi.
 *
 * Barisnya dapat DIBUKA, bukan ditautkan ke halaman lain: yang dicari pembaca
 * saat meragukan satu angka adalah asal angka itu, dan memindahkannya ke layar
 * lain berarti kehilangan konteks sembilan belas baris lain yang sedang
 * dibandingkannya.
 */
function BarisTabel({ baris }: { baris: BarisReorder }) {
  const t = useT();
  const [buka, setBuka] = useState(false);
  const u = baris.unit_code ?? "";

  const [poNomor, setPoNomor] = useState<string | null>(null);
  const [poKirim, setPoKirim] = useState(false);
  const [poGalat, setPoGalat] = useState<string | null>(null);

  // Backend tidak menolak PO kembar, jadi pencegahan klik gandanya di sini:
  // begitu satu PO terbit, tombolnya berganti menjadi nomor PO.
  function buatPo() {
    const qty = baris.recommended_order_qty;
    if (!qty || poKirim || poNomor) return;
    setPoKirim(true);
    setPoGalat(null);
    apiPost<{ po_number: string }>("/api/purchase-orders", {
      warehouse_id: baris.warehouse_id,
      source: "reorder_list",
      items: [{ item_id: baris.item_id, quantity: qty }],
    })
      .then((r) => setPoNomor(r.po_number))
      .catch((e: Error) => setPoGalat(e.message))
      .finally(() => setPoKirim(false));
  }

  const qty = baris.recommended_order_qty;

  return (
    <>
      <tr
        className="cursor-pointer border-t transition hover:bg-[var(--surface-sunken)]"
        style={{ borderColor: "var(--border)" }}
        onClick={() => setBuka((v) => !v)}
      >
        <Sel className="!text-ink">
          <span className="flex items-start gap-2">
            <ChevronDown
              size={14}
              className="mt-0.5 shrink-0 transition-transform"
              style={{ transform: buka ? "rotate(180deg)" : "none", color: "var(--text-muted)" }}
            />
            <span className="min-w-0">
              <span className="block font-semibold text-ink">{baris.item_name}</span>
              <span className="block t-caption text-muted">{baris.sku}</span>
              {/* Alasan singkat, di bawah nama barangnya. Kalimatnya dari
                  backend dan memakai angka yang sama dengan kolom di kanan. */}
              <span className="mt-1 block max-w-md t-caption leading-relaxed text-ink-2">
                {baris.reason}
              </span>
            </span>
          </span>
        </Sel>
        {/* Kode gudang TIDAK boleh patah dua baris: "WH-SBY" yang tercetak
            sebagai "WH-" dan "SBY" terbaca sebagai dua nilai berbeda pada
            kolom yang sempit. */}
        <Sel className="whitespace-nowrap">{baris.warehouse_code}</Sel>
        <Sel align="right" className="tnum">
          {angka(baris.available_stock_int, u)}
        </Sel>
        <Sel align="right" className="tnum">
          {angka(baris.effective_reorder_point_int, u)}
        </Sel>
        <Sel align="right" className="tnum">
          {angka(baris.forecast_usage_int, u)}
        </Sel>
        <Sel align="right" className="tnum">
          {/* null berarti stok TIDAK BERGERAK, bukan "belum dihitung" -- dua
              hal yang berbeda dan "—" akan menyamakan keduanya. */}
          {baris.days_of_cover_int === null
            ? t("rl.no_cover")
            : t("c.days", { n: num(baris.days_of_cover_int) })}
        </Sel>
        <Sel>
          <span className="flex flex-col items-start gap-1">
            <LencanaStatus baris={baris} />
            <TandaPrioritas baris={baris} />
          </span>
        </Sel>
        <Sel align="right">
          {qty === null ? (
            <span className="t-small text-muted">{t("rl.qty_none")}</span>
          ) : qty === 0 ? (
            <span className="t-small text-muted">{t("rl.qty_zero")}</span>
          ) : (
            <span className="stat-figure t-lead font-bold text-ink">
              {num(qty)} {u}
            </span>
          )}
        </Sel>
      </tr>
      {buka && (
        <tr>
          <td colSpan={8} className="p-0">
            <DetailBaris
              baris={baris}
              onPo={buatPo}
              poNomor={poNomor}
              poKirim={poKirim}
              poGalat={poGalat}
            />
          </td>
        </tr>
      )}
    </>
  );
}

/*
 * Kunci pengurutan. Kolom yang TIDAK dapat diurutkan sengaja tidak punya
 * entri di sini: titik pesan dan prakiraan hanya berarti dibandingkan dengan
 * stok pada barisnya sendiri, dan mengurutkan katalog menurut angka yang
 * satuannya berbeda tiap baris tidak menjawab pertanyaan siapa pun.
 */
const URUT_REORDER: Record<string, (b: BarisReorder) => number | string | null> = {
  item: (b) => b.item_name,
  stok: (b) => b.current_stock_int,
  cover: (b) => b.days_of_cover_int,
  qty: (b) => b.recommended_order_qty,
};

export function TabelReorder({
  items,
  total,
  horizon,
  tab,
}: {
  items: BarisReorder[];
  /** jumlah SELURUH hasil saringan; pengurutan layar hanya sah bila muat sehalaman */
  total: number;
  horizon: number;
  tab: TabStatus;
}) {
  const t = useT();
  const urut = useUrutTabel(items, total, URUT_REORDER);

  if (!items.length) {
    // Kosong pada tab "perlu reorder" adalah KABAR BAIK dan harus berbunyi
    // begitu; kosong karena saringan terlalu sempit adalah hal lain.
    return (
      <Empty message={tab === "PERLU_REORDER" ? t("rl.empty_safe") : t("rl.empty")} />
    );
  }

  /*
   * Memakai primitif Table/Th bersama, BUKAN <table> rakitan sendiri.
   * Sampai 2 September 2026 berkas ini menyusun kepala kolomnya sendiri dengan
   * kelas `th` sebaris -- 11px, tracking 0,06em, latar `--surface-sunken` --
   * sementara Th bersama memakai 10px, tracking 0,07em, latar `--surface-1`.
   * Dua tabel yang tampil di halaman berurutan karena itu terlihat berasal
   * dari dua aplikasi, dan tidak ada yang menyadarinya sampai keduanya
   * dibandingkan berdampingan.
   */
  return (
    <div className="surface-card px-1">
      <Table lekat minLebar="62rem" label={t("ro.title")} kartuPonsel>
        <thead>
          <tr>
            <Th urut={urut.arah("item")} onUrut={urut.handler("item")}>
              {t("rl.col.item")}
            </Th>
            <Th>{t("rl.col.warehouse")}</Th>
            <Th align="right" urut={urut.arah("stok")} onUrut={urut.handler("stok")}>
              {t("rl.col.stock")}
            </Th>
            <Th align="right">{t("rl.col.rop")}</Th>
            <Th align="right">{t("rl.col.forecast", { n: horizon })}</Th>
            <Th align="right" urut={urut.arah("cover")} onUrut={urut.handler("cover")}>
              {t("rl.col.cover")}
            </Th>
            <Th>{t("rl.col.status")}</Th>
            <Th align="right" urut={urut.arah("qty")} onUrut={urut.handler("qty")}>
              {t("rl.col.qty")}
            </Th>
          </tr>
        </thead>
        <tbody>
          {urut.baris.map((b) => (
            <BarisTabel key={`${b.item_id}-${b.warehouse_id}`} baris={b} />
          ))}
        </tbody>
      </Table>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Saringan                                                            */
/* ------------------------------------------------------------------ */

export function SaringanReorder({
  gudang,
  warehouseId,
  setWarehouseId,
  prioritas,
  setPrioritas,
  cari,
  setCari,
}: {
  gudang: { id: number; code: string; name: string }[];
  warehouseId: string;
  setWarehouseId: (v: string) => void;
  prioritas: string;
  setPrioritas: (v: string) => void;
  cari: string;
  setCari: (v: string) => void;
}) {
  const t = useT();
  return (
    <div className="baris-saring flex flex-wrap items-end gap-3">
      <Field label={t("c.warehouse")}>
        <Select
          value={warehouseId}
          onChange={setWarehouseId}
          options={[
            { value: "", label: t("rl.filter.all_warehouse") },
            ...gudang.map((w) => ({ value: String(w.id), label: `${w.code} — ${w.name}` })),
          ]}
          className="min-w-[190px]"
        />
      </Field>
      <Field label={t("rl.filter.priority")}>
        <Select
          value={prioritas}
          onChange={setPrioritas}
          options={[
            { value: "", label: t("rl.filter.all_priority") },
            { value: "TINGGI", label: t("ro.prio.TINGGI") },
            { value: "SEDANG", label: t("ro.prio.SEDANG") },
            { value: "RENDAH", label: t("ro.prio.RENDAH") },
          ]}
          className="min-w-[150px]"
        />
      </Field>
      <Field label={t("rl.search")}>
        <TextInput value={cari} onChange={setCari} placeholder={t("rl.search")} />
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
      <AlertTriangle size={14} className="mt-0.5 shrink-0" style={{ color: "var(--status-warning)" }} />
      {t("rl.truncated", { n: batas })}
    </div>
  );
}
