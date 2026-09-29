"use client";

/**
 * Blok-blok layar keputusan SATU BARANG / single-item reorder blocks.
 *
 * TIDAK LAGI TERPASANG DI HALAMAN MANA PUN, 2 September 2026, dan itu bukan
 * impor yang tertinggal. Halaman /reorder kini berupa DAFTAR seluruh barang
 * (components/reorder-list.tsx): pertanyaan yang dibawa orang pengadaan adalah
 * "mana saja yang perlu dipesan", dan layar satu-barang tidak pernah dapat
 * menjawabnya tanpa menuntut pembacanya memilih SKU satu per satu.
 *
 * Kedua komponen di bawah dipertahankan utuh, bukan dihapus: keduanya
 * menjelaskan satu barang jauh lebih dalam daripada baris tabel, dan bila
 * kelak ada halaman detail per barang, inilah isinya. Yang perlu diperiksa
 * lebih dulu bila itu terjadi: `data.action_status === "SEGERA_PESAN"` di
 * bawah menguji nilai sumbu status LAMA yang tidak diterbitkan backend lagi --
 * penggantinya "RISIKO_STOCKOUT".
 *
 * Menjawab dua pertanyaan operasional: KAPAN stok perlu dipesan, dan BERAPA
 * jumlahnya. Keduanya berpatokan lead time, safety stock, dan stok tersedia --
 * bukan periode prakiraan. Karena itu tidak satu pun komponen di file ini
 * menerima pilihan periode dari pengguna, dan tidak satu pun membaca
 * forecast_usage, projected_shortage, atau days_until_stockout: ketiganya
 * bergerak saat periode digeser di layar Prakiraan, sedangkan urgensi
 * pembelian tidak boleh ikut bergerak karenanya.
 *
 * Halaman ini terdiri dari DUA blok saja: kondisi persediaan yang tercatat,
 * dan satu panel keputusan. Empat kartu keputusan, banner tingkat keyakinan,
 * banner saran, dan blok pengadaan tersendiri sudah dilebur ke dalam panel itu
 * -- lihat catatan pada PanelKeputusan untuk sebabnya.
 *
 * SELURUH ANGKA DIRENDER DARI FIELD `*_int`, dan seluruh kalimat penjelas
 * dari field `*_reason` / `*_basis` / `*_label`. Tidak ada pembulatan dan
 * tidak ada rumus yang hidup di berkas ini: status dan angka yang
 * menyertainya berasal dari satu perhitungan yang sama di backend, sehingga
 * "Segera pesan" mustahil lagi berdampingan dengan "belum ada jumlah yang
 * perlu diadakan".
 *
 * Yang DITERJEMAHKAN di layar hanyalah label yang berasal dari enum status;
 * kalimat alasan tetap datang apa adanya dari backend, karena di sanalah
 * angka dan kata-katanya disusun bersama-sama.
 */

import { useEffect, useState } from "react";

import { AlertTriangle, Boxes, ChevronRight } from "lucide-react";

import { AKSI, Blok, KartuKeputusan, angka, useLabelAksi } from "@/components/forecast-ui";
import { Button } from "@/components/ui";
import { apiPost } from "@/lib/api";
import { Forecast } from "@/lib/forecast-types";
import { useT } from "@/lib/i18n";
import { num } from "@/lib/format";

/**
 * Lencana "di bawah minimum" pada kartu stok tersedia.
 *
 * Kartu Stok minimum sudah tidak ada, tetapi sinyalnya tetap perlu terbaca --
 * yang hilang bersama kartu itu bukan angkanya, melainkan peringatannya.
 * Ditempel pada kartu stok tersedia karena di sanalah perbandingannya terjadi:
 * yang berada di bawah minimum adalah stok itu, bukan sesuatu yang lain.
 *
 * Angka ambangnya dibawa pada atribut title, bukan dicetak di kartu. Stok
 * minimum BUKAN ambang yang menentukan status halaman ini -- yang menentukan
 * titik pesan efektif -- jadi mencetaknya sejajar dengan angka lain akan
 * mengembalikan persis kekeliruan yang membuat kartunya dihapus. Sebagai
 * keterangan yang muncul saat ditunjuk, ia tersedia tanpa menuntut perhatian.
 *
 * Merah, bukan kuning: ini pernyataan tentang keadaan yang sudah terjadi, bukan
 * tentang mutu taksiran. Warnanya didampingi ikon dan teks, tidak pernah
 * berdiri sendiri.
 */
function TandaDiBawahMinimum({ minimum, satuan }: { minimum: number; satuan: string }) {
  const t = useT();
  return (
    <span
      title={t("ro.cond.below_min_title", { v: `${num(minimum)} ${satuan}`.trim() })}
      className="inline-flex items-center gap-1 whitespace-nowrap rounded-lg px-1.5 py-0.5 t-micro font-semibold"
      style={{
        background: "color-mix(in srgb, var(--status-critical) 18%, transparent)",
        color: "var(--text-secondary)",
      }}
    >
      <AlertTriangle size={10} style={{ color: "var(--status-critical)" }} />
      {t("ro.cond.below_min_badge")}
    </span>
  );
}

/**
 * Kondisi Persediaan / Inventory Condition.
 *
 * Stok saat ini dan parameter pada master barang. Seluruhnya angka yang
 * tercatat, bukan hasil prakiraan -- karena itu blok ini tetap berarti bahkan
 * ketika histori belum cukup untuk memprakirakan apa pun.
 */
export function InventoryStatus({
  data,
  strategiLabel,
}: {
  data: Forecast;
  strategiLabel?: string;
}) {
  const t = useT();
  const satuan = data.item.unit_code ?? "";

  return (
    <Blok Ikon={Boxes} judul={t("ro.cond.title")} keterangan={t("ro.cond.note")}>
      {/* TIGA kartu, bukan lima. Stok minimum dan safety stock dikeluarkan dari
          baris ini: keduanya ambang master yang TIDAK menentukan status apa pun
          di halaman ini -- yang menentukan adalah titik pesan efektif -- dan
          berdiri sebagai kartu sebesar kartu lain, keduanya terbaca sebagai
          ambang yang setara. Tidak satu pun sinyalnya ikut terhapus: safety
          stock tetap muncul pada dasar perhitungan di blok Pengadaan, tempat ia
          memang dipakai sebagai komponen titik pesan efektif, dan peringatan
          stok di bawah minimum menempel sebagai lencana pada kartu stok
          tersedia. */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <KartuKeputusan
          label={t("ro.cond.available")}
          nilai={angka(data.available_stock_int, satuan)}
          detail={
            data.reserved_stock_int > 0
              ? t("ro.cond.available_split", {
                  a: num(data.current_stock_int),
                  b: num(data.reserved_stock_int),
                  u: satuan,
                })
              : t("ro.cond.available_free", { a: num(data.current_stock_int), u: satuan })
          }
          tanda={
            data.stock_below_minimum ? (
              <TandaDiBawahMinimum minimum={data.minimum_stock_int} satuan={satuan} />
            ) : undefined
          }
        />
        {/* Kartu inilah yang menjawab dropdown Strategi.
            Sebelumnya di sini berdiri titik pesan master -- angka tetap yang
            tidak bergeser sedikit pun ketika strategi diganti, sehingga
            dropdownnya terasa tidak melakukan apa-apa. Yang tampil sekarang
            titik pesan menurut strategi yang sedang dipilih, dan angka master
            turun menjadi keterangan di bawahnya: ia tetap terbaca, tetapi
            tidak lagi berebut tempat dengan angka yang benar-benar dipakai. */}
        <KartuKeputusan
          label={
            data.strategy_applied
              ? t("ro.cond.rop_strategy", { strategi: strategiLabel ?? "" })
              : t("ro.cond.rop_master")
          }
          nilai={angka(
            data.strategy_applied
              ? data.effective_reorder_point_int
              : data.reorder_point_int,
            satuan
          )}
          detail={
            data.strategy_applied
              ? t("ro.cond.rop_strategy_detail", {
                  master: num(data.reorder_point_int),
                  u: satuan,
                })
              : t("ro.cond.rop_master_detail")
          }
        />
        <KartuKeputusan
          label={t("ro.cond.lead")}
          nilai={
            data.lead_time_days_int === null
              ? t("ro.cond.lead_empty")
              : t("c.days", { n: num(data.lead_time_days_int) })
          }
          detail={
            data.lead_time_days_int === null
              ? t("ro.cond.lead_empty_detail")
              : t("ro.cond.lead_detail")
          }
          detailWarna={data.lead_time_days_int === null ? "var(--status-warning)" : undefined}
        />
      </div>
    </Blok>
  );
}

/* ------------------------------------------------------------------ */
/* Panel Keputusan / Decision panel                                    */
/* ------------------------------------------------------------------ */

/**
 * SATU panel, SATU keputusan.
 *
 * Sebelumnya jawaban atas "perlu pesan atau tidak, dan berapa" tersebar pada
 * empat kartu keputusan, satu banner tingkat keyakinan, satu banner saran, dan
 * satu blok pengadaan tersendiri -- tujuh tempat untuk satu kesimpulan. Yang
 * membuatnya sulit dibaca bukan jumlah angkanya, melainkan bahwa tidak satu
 * pun dari ketujuhnya menyatakan kesimpulan itu lebih dulu: pembaca harus
 * merakitnya sendiri dari potongan yang tersebar, dan jumlah yang harus dibeli
 * -- satu-satunya angka yang berujung pada pengeluaran uang -- justru berada
 * paling bawah.
 *
 * Panel ini membalik urutannya. Kesimpulan lebih dulu (headline), ukuran
 * pendukung sesudahnya (tiga metrik), dasar perhitungan hanya bila diminta
 * (accordion tertutup), dan tindakan di ujung. Yang di bawah menjelaskan yang
 * di atas, tidak pernah sebaliknya.
 *
 * DISIPLIN WARNA. Merah hanya muncul di headline dan hanya ketika memang harus
 * memesan sekarang; kuning hanya pada strip peringatan mutu master data.
 * Sisanya netral. Aturan ini yang membuat satu warna berarti satu hal: layar
 * lama memakai merah untuk status, kuning untuk keyakinan, dan merah lagi
 * untuk blok pengadaan, sehingga tidak ada warna yang menandakan apa pun.
 *
 * SELURUH NILAI DARI BACKEND. Tidak ada rumus, tidak ada ambang, dan tidak ada
 * kalimat berisi angka yang disusun di berkas ini -- termasuk kalimat sub-
 * headline, yang datang jadi sebagai `reorder_status_reason`.
 */

/** Satu ukuran pendukung pada baris metrik. */
function Metrik({ label, nilai, detail }: { label: string; nilai: string; detail: string }) {
  return (
    <div
      className="rounded-xl px-3.5 py-3"
      style={{ background: "var(--surface-2)", boxShadow: "inset 0 0 0 1px var(--border)" }}
    >
      <span className="block t-micro font-semibold uppercase tracking-[0.06em] text-muted">
        {label}
      </span>
      <span className="stat-figure mt-1 block text-[17px] font-bold leading-tight text-ink">
        {nilai}
      </span>
      <span className="mt-0.5 block t-caption leading-relaxed text-muted">{detail}</span>
    </div>
  );
}

/**
 * Satu baris dasar perhitungan.
 *
 * `operator` sengaja berupa kolom tersendiri, bukan bagian dari label: dengan
 * begitu tanda "+" dan "=" berbaris tegak lurus di bawah satu sama lain dan
 * rangkaiannya terbaca sebagai hitungan, bukan sebagai daftar yang kebetulan
 * berurutan.
 */
function BarisHitung({
  label,
  nilai,
  operator,
  total,
  catatan,
}: {
  label: string;
  nilai: string;
  /** "+", "-", "=" atau kosong untuk baris pertama sebuah kelompok */
  operator?: string;
  /** baris hasil: ditebalkan dan diberi garis pemisah di atasnya */
  total?: boolean;
  /** dari mana angka baris ini sendiri datang; dicetak kecil di bawahnya */
  catatan?: string;
}) {
  return (
    <div
      className={`py-1.5 ${total ? "border-t" : ""}`}
      style={total ? { borderColor: "var(--border)" } : undefined}
    >
      <div className="flex items-baseline gap-2">
        <span
          aria-hidden
          className="w-3 shrink-0 text-right t-small font-semibold text-muted"
        >
          {operator ?? ""}
        </span>
        <span className={`flex-1 t-small ${total ? "font-semibold text-ink" : "text-ink-2"}`}>
          {label}
        </span>
        <span
          className={`stat-figure t-small tabular-nums ${
            total ? "font-bold text-ink" : "text-ink-2"
          }`}
        >
          {nilai}
        </span>
      </div>
      {catatan ? (
        <p className="pl-5 t-micro leading-relaxed text-muted">{catatan}</p>
      ) : null}
    </div>
  );
}

/**
 * Strip peringatan mutu master data.
 *
 * KUNING, dan satu-satunya yang kuning di halaman ini. Ia tidak berbicara
 * tentang kegawatan stok melainkan tentang ambang yang tercatat pada master
 * barang: titik pesan master yang lebih rendah daripada kebutuhan masa tunggu
 * ditambah safety stock akan selalu terlambat memicu pemesanan. Barangnya
 * sendiri bisa saja aman hari ini -- karena itu warnanya tidak boleh sama
 * dengan warna headline.
 *
 * TIDAK ADA TOMBOL DI SINI LAGI. Dulu strip ini memuat tombol yang menulis
 * titik pesan efektif ke `items.reorder_point`; tombol itu dicabut atas
 * permintaan, karena di layar yang sama sudah berdiri tombol Buat PO dan
 * dua tombol berdampingan terbaca sebagai dua jalan untuk satu urusan.
 *
 * Keduanya sebenarnya BERBEDA URUSAN, dan itu sebabnya kalimat strip ini kini
 * menunjuk ke tempat lain alih-alih berhenti sebagai keluhan. Buat PO membuat
 * transaksi pesanan; yang hilang di sini mengkalibrasi AMBANG pada master
 * barang. Selama ambang itu tidak dinaikkan, peringatan ini akan terus muncul
 * pada setiap kunjungan berikutnya.
 *
 * MASTER BARANG BERLAKU LINTAS GUDANG, dan itu pula alasan perbaikannya lebih
 * tepat dikerjakan di Data Dasar. `items.reorder_point` satu kolom untuk
 * seluruh gudang; tabel `inventory` tidak menyimpan ambang per gudang sama
 * sekali. Angka yang tampil di layar ini lahir dari laju pemakaian SATU
 * gudang, jadi menyimpannya dari sini akan mengubah ambang bagi setiap gudang
 * yang menyimpan barang tersebut -- konsekuensi yang dulu hanya tertulis pada
 * atribut title sebuah tombol kecil.
 */
function StripPeringatanMaster({ data }: { data: Forecast }) {
  const t = useT();
  const satuan = data.item.unit_code ?? "";
  const master = `${num(data.reorder_point_int)} ${satuan}`.trim();
  const warna = "var(--status-warning)";

  return (
    <div
      className="mt-3 flex flex-wrap items-start gap-x-4 gap-y-2 rounded-xl px-4 py-3"
      style={{
        background: `color-mix(in srgb, ${warna} 10%, var(--surface-1))`,
        boxShadow: `inset 3px 0 0 0 ${warna}, inset 0 0 0 1px var(--border)`,
      }}
    >
      <AlertTriangle size={14} className="mt-0.5 shrink-0" style={{ color: warna }} />
      <p className="min-w-[16rem] flex-1 t-small leading-relaxed text-ink-2">
        {t("ro.panel.warn", { m: master })} {t("ro.panel.warn_where")}
      </p>
    </div>
  );
}

export function PanelKeputusan({
  data,
  warehouseId,
  itemId,
}: {
  data: Forecast;
  warehouseId: string;
  itemId: string;
}) {
  const t = useT();
  const label = useLabelAksi();
  const satuan = data.item.unit_code ?? "";

  const qty = data.recommended_order_qty;
  const perluPesan = qty !== null && qty > 0;
  // Merah HANYA di sini, dan hanya untuk keadaan yang menuntut tindakan hari
  // ini. "Perlu dipantau" sengaja netral: ia peringatan dini, bukan perintah.
  const mendesak = data.action_status === "SEGERA_PESAN";
  const warnaKepala = mendesak ? "var(--status-critical)" : "var(--text-secondary)";
  const { Ikon } = AKSI[data.action_status];

  const jumlah = qty === null ? null : `${num(qty)} ${satuan}`.trim();

  // --- pesanan pembelian ---
  const [poNomor, setPoNomor] = useState<string | null>(null);
  const [poKirim, setPoKirim] = useState(false);
  const [poGalat, setPoGalat] = useState<string | null>(null);

  // Berganti barang/gudang membatalkan nomor PO lama: ia dibuat untuk barang
  // yang sudah tidak ditampilkan lagi, dan nomor yang tertinggal di layar
  // barang berikutnya akan terbaca seolah barang itu yang sudah dipesan.
  useEffect(() => {
    setPoNomor(null);
    setPoGalat(null);
  }, [warehouseId, itemId]);

  /*
   * Backend sengaja TIDAK menolak PO kembar, jadi pencegahan klik gandanya ada
   * di sini: begitu satu PO terbit, tombolnya berganti menjadi nomor PO dan
   * tidak dapat ditekan lagi sampai barang atau gudangnya berganti.
   */
  function buatPo() {
    if (!perluPesan || poKirim || poNomor) return;
    setPoKirim(true);
    setPoGalat(null);
    apiPost<{ po_number: string }>("/api/purchase-orders", {
      warehouse_id: Number(warehouseId),
      source: "reorder_panel",
      items: [{ item_id: Number(itemId), quantity: qty }],
    })
      .then((r) => setPoNomor(r.po_number))
      .catch((e: Error) => setPoGalat(e.message))
      .finally(() => setPoKirim(false));
  }

  return (
    <section
      className="rise mt-7 rounded-xl px-5 py-5"
      style={{
        background: "var(--surface-1)",
        boxShadow: "inset 0 0 0 1px var(--border), var(--elev-1)",
      }}
    >
      {/* --- 1. Headline: kesimpulannya lebih dulu --- */}
      <div className="flex flex-wrap items-start gap-x-4 gap-y-3">
        <span
          aria-hidden
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl"
          style={{
            background: `color-mix(in srgb, ${warnaKepala} 13%, transparent)`,
            boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${warnaKepala} 26%, transparent)`,
            color: warnaKepala,
          }}
        >
          <Ikon size={19} />
        </span>

        <div className="min-w-[14rem] flex-1">
          <h2
            className="font-display text-[21px] font-bold leading-tight"
            style={{ color: mendesak ? "var(--status-critical)" : "var(--text-primary)" }}
          >
            {perluPesan && jumlah
              ? t("ro.panel.head_qty", { s: label.status(data.action_status), v: jumlah })
              : label.status(data.action_status)}
          </h2>
          <p className="mt-1.5 max-w-2xl t-body leading-relaxed text-ink-2">
            {data.reorder_status_reason}
          </p>
        </div>

        {/* Lencana kanan. Merah hanya ketika titik pesan efektif memang sudah
            terlampaui; selain itu ia keterangan waktu yang netral, bukan
            penanda kegawatan yang diperhalus. */}
        {data.effective_reorder_point_reached ? (
          <span
            className="whitespace-nowrap rounded-full px-3 py-1 t-caption font-semibold"
            style={{
              background: "color-mix(in srgb, var(--status-critical) 15%, transparent)",
              color: "var(--status-critical)",
              boxShadow:
                "inset 0 0 0 1px color-mix(in srgb, var(--status-critical) 38%, transparent)",
            }}
          >
            {t("ro.panel.badge_reached")}
          </span>
        ) : data.days_to_effective_rop_label ? (
          <span
            className="whitespace-nowrap rounded-full px-3 py-1 t-caption font-semibold text-ink-2"
            style={{ background: "var(--surface-2)", boxShadow: "inset 0 0 0 1px var(--border)" }}
          >
            {t("ro.panel.badge_eta", { v: data.days_to_effective_rop_label })}
          </span>
        ) : null}
      </div>

      {/* --- 2. Ukuran pendukung ---
          SATU, bukan tiga. Stok tersedia dan masa tunggu sudah berdiri sebagai
          kartu penuh pada blok Kondisi Persediaan di atas; mencetaknya lagi di
          sini membuat satu halaman memuat enam kartu yang dua di antaranya
          kembar, dan pembaca kehilangan jejak mana yang seharusnya jadi fokus.
          Yang tersisa hanyalah ukuran yang memang hanya berarti di blok
          keputusan ini. */}
      <div className="mt-4 sm:max-w-xs">
        {/* Ketahanan stok dinyatakan dalam KALI PENGAMBILAN, bukan hari.
            Backend tidak mengirim days_of_cover pada endpoint ini, dan barang
            gudang bergerak per pengambilan, bukan per hari -- "±7 pengambilan
            lagi" adalah satuan yang benar-benar dipakai orang gudang. */}
        <Metrik
          label={t("ro.panel.cover")}
          nilai={
            data.remaining_pickups === null || data.remaining_pickups === undefined
              ? "—"
              : t("ro.panel.pickups", { n: num(data.remaining_pickups) })
          }
          detail={`${data.usage_frequency_label ?? ""} ${
            data.usage_frequency_detail ?? ""
          }`.trim()}
        />
      </div>

      {/* --- 3. Dasar perhitungan, tertutup sampai diminta --- */}
      <details className="group mt-3">
        <summary
          className="flex cursor-pointer list-none items-center gap-1.5 rounded-lg py-1.5 t-small font-semibold text-ink-2 hover:text-ink"
        >
          <ChevronRight
            size={13}
            className="transition-transform group-open:rotate-90"
            aria-hidden
          />
          {t("ro.proc.basis")}
        </summary>

        <div className="mt-1 max-w-md pl-[19px]">
          {/* Rangkaian ini BOLEH ditulis sebagai persamaan: safety stock pada
              master barang selalu bilangan bulat, sehingga pembulatan
              kebutuhan masa tunggu tidak pernah menggeser jumlahnya. */}
          <BarisHitung
            label={t("ro.proc.lead_demand")}
            nilai={
              data.lead_time_demand_int === null
                ? "—"
                : `${num(data.lead_time_demand_int)} ${satuan}`.trim()
            }
          />
          {/* Turunannya menempel PADA barisnya, bukan berdiri sebagai blok
              tersendiri. Sebelumnya Z dan simpangan permintaan tinggal di satu
              seksi terpisah di atas Kondisi Persediaan, yang mencetak ulang
              seluruh rantai ini sekali lagi -- dua tempat untuk satu
              perhitungan, dan pembaca harus menebak mana yang harus dibaca.
              Desimalnya DISENGAJA, bukan kelalaian. Dibulatkan ke bilangan
              bulat, "Z 2 x s 3 x akar 10" berbunyi 19 sementara barisnya
              berbunyi 22; pada dua desimal ia berbunyi 21,7 dan membulat ke
              angka yang sama. Catatan turunan yang tidak dapat direkonsiliasi
              pembaca lebih buruk daripada tidak ada catatan sama sekali --
              itulah persis yang membuat blok strategi yang lama membingungkan. */}
          <BarisHitung
            operator="+"
            label={t("ro.cond.safety")}
            nilai={`${num(data.safety_stock_int)} ${satuan}`.trim()}
            catatan={
              data.strategy_applied && data.strategy_rmse !== null
                ? t("ro.proc.safety_from", {
                    z: num(data.strategy_z ?? 0, 2),
                    s: `${num(data.strategy_rmse, 2)} ${satuan}`.trim(),
                    lead: num(data.lead_time_days_int ?? 0),
                  })
                : undefined
            }
          />
          <BarisHitung
            operator="="
            total
            label={t("ro.dec.eff_rop")}
            nilai={`${num(data.effective_reorder_point_int)} ${satuan}`.trim()}
          />

          {perluPesan && data.order_up_to_level_int !== null && (
            <div className="mt-3">
              <BarisHitung
                label={t("ro.proc.fill_to")}
                nilai={`${num(data.order_up_to_level_int)} ${satuan}`.trim()}
              />
              <BarisHitung
                operator="−"
                label={t("ro.cond.available")}
                nilai={`${num(data.available_stock_int)} ${satuan}`.trim()}
              />
              <BarisHitung
                operator="="
                total
                label={t("ro.proc.order_qty")}
                nilai={jumlah ?? "—"}
              />
              {/* Kelompok kedua ini TIDAK selalu tutup di layar: jumlah pesanan
                  dibulatkan ke atas dari selisih desimalnya, sedangkan dua
                  baris di atasnya dibulatkan sendiri-sendiri. Selisih satu unit
                  yang muncul karenanya dinyatakan, bukan dibiarkan ditemukan
                  pembaca sebagai kekeliruan. */}
              <p className="mt-1.5 t-micro leading-relaxed text-muted">
                {t("ro.panel.round_note")}
              </p>
            </div>
          )}

          {/* Pindahan dari blok strategi yang dihapus. Kartu Lead time di atas
              sudah menandainya "Belum diisi", tetapi hanya kalimat inilah yang
              menyebutkan APA yang harus dilakukan dan di mana. */}
          {data.lead_time_days_int === null && (
            <p
              className="mt-2.5 t-caption leading-relaxed"
              style={{ color: "var(--status-warning)" }}
            >
              {t("ro.proc.no_lead")}
            </p>
          )}

          <p className="mt-2.5 t-micro leading-relaxed text-muted">
            {t("ro.proc.footer")}
          </p>
        </div>
      </details>

      {/* --- 4. Peringatan mutu master data --- */}
      {data.reorder_point_adequate === false && (
        <StripPeringatanMaster data={data} />
      )}

      {/* --- 5. Tindakan ---
          Satu tombol saja. Tombol "Request AI review" dihapus: ulasannya
          mengulang kalimat yang sudah disusun backend pada sub-headline dan
          alasan jumlah pesanan, dengan menunggu layanan bahasa lebih dulu.

          Labelnya TANPA jumlah. Angka yang sama sudah berdiri di headline panel
          ini dan pada dasar perhitungannya; mencetaknya di tombol membuat satu
          panel menyebut satu angka tiga kali. Yang dipesan tetap angka itu --
          `buatPo()` mengirim `qty` yang sama persis dengan yang tercetak di
          headline, bukan angka lain yang kebetulan tidak terlihat. */}
      <div className="mt-4 flex flex-wrap items-center gap-2.5 border-t pt-4"
           style={{ borderColor: "var(--border)" }}>
        {perluPesan && (
          <Button
            color="var(--status-good)"
            onClick={buatPo}
            disabled={poKirim || poNomor !== null}
            title={t("ro.panel.po_scope")}
          >
            {poKirim ? t("ro.panel.po_busy") : t("ro.panel.make_po")}
          </Button>
        )}
      </div>

      {/* Hasil pembuatan PO. Nomornya dicetak apa adanya supaya PO itu benar-
          benar dapat dicari, dan statusnya disebut supaya tidak ada yang
          menyangka stok sudah bertambah. */}
      {(poNomor || poGalat) && (
        <p
          className="mt-2.5 t-small leading-relaxed"
          style={{ color: poGalat ? "var(--status-critical)" : "var(--text-secondary)" }}
        >
          {poGalat ?? t("ro.panel.po_done", { v: poNomor as string })}
        </p>
      )}

    </section>
  );
}
