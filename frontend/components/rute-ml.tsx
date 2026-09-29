"use client";

/**
 * Rekomendasi rute terbaik (moda angkut) untuk satu kiriman.
 *
 * Yang ditampilkan datang seluruhnya dari GET /api/transfer/rute-ml: model
 * gradient boosting yang dilatih dari riwayat transfer selesai memperkirakan
 * lama di jalan, biaya, dan jumlah yang sampai untuk tiap moda. Layar tidak
 * menghitung apa pun sendiri, dan menyebut terang-terangan bila jawabannya
 * berasal dari tarif standar (riwayat belum cukup) alih-alih dari model.
 */

import { Plane, Ship, Sparkles, Truck, TriangleAlert } from "lucide-react";
import { ReactNode, useEffect, useState } from "react";

import { useApi } from "@/lib/api";
import { idr, num } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import { ModaAngkut, OpsiRute, PrioritasRute, RekomendasiRute } from "@/lib/transfer-types";

const IKON: Record<ModaAngkut, ReactNode> = {
  darat: <Truck size={15} aria-hidden />,
  laut: <Ship size={15} aria-hidden />,
  udara: <Plane size={15} aria-hidden />,
};

const PRIORITAS: PrioritasRute[] = ["seimbang", "tercepat", "termurah", "terpenuh"];

export interface PilihanRute {
  mode: ModaAngkut;
  hari: number;
}

export function PanelRuteML({
  dariId,
  keId,
  jumlah,
  itemId,
  batasHari,
  onPilih,
  sumber,
  nilai,
  gabungan,
}: {
  /** kode gudang pengirim, disebut pada judul bila satu kartu punya beberapa pengirim */
  sumber?: string;
  /** nilai barang seluruh kiriman (rupiah); dipakai bila kiriman berisi beberapa barang */
  nilai?: number;
  /** kiriman gabungan: barang lain yang naik bersama, supaya angkanya terbaca benar */
  gabungan?: { barang: number; unit: number };
  dariId: number;
  keId: number;
  jumlah: number;
  itemId?: number;
  /** batas waktu, mis. lead time pembelian baru; moda yang lebih lambat diberi tanda */
  batasHari?: number | null;
  /** dipanggil dengan moda yang sedang direkomendasikan, supaya dokumen mencatatnya */
  onPilih?: (p: PilihanRute | null) => void;
}) {
  const { t } = useI18n();
  const [prioritas, setPrioritas] = useState<PrioritasRute>("seimbang");
  const [terbuka, setTerbuka] = useState(false);

  const { data, loading, error } = useApi<RekomendasiRute>(
    jumlah > 0 ? "/api/transfer/rute-ml" : null,
    {
      from_warehouse_id: dariId,
      to_warehouse_id: keId,
      quantity: jumlah,
      item_id: nilai === undefined ? itemId : undefined,
      value: nilai,
      priority: prioritas,
      deadline_days: batasHari ?? undefined,
    },
  );

  const terbaik = data?.options?.[0] ?? null;
  useEffect(() => {
    onPilih?.(terbaik ? { mode: terbaik.mode, hari: terbaik.predicted_days } : null);
    // onPilih sengaja tidak jadi dependensi: pemanggil membuatnya ulang tiap render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [terbaik?.mode, terbaik?.predicted_days]);

  return (
    <section
      className="px-4 py-3 sm:px-5"
      style={{ borderTop: "1px solid var(--border)" }}
      aria-label={t("rt.title")}
    >
      {/*
        SATU REKOMENDASI, DAN ITU YANG DITAMPILKAN. Sistem yang memutuskan
        gudang dan moda; pengguna cukup menerapkannya. Perbandingan moda dan
        pilihan prioritas ada di balik tautan "Lihat alternatif" -- pengecualian,
        bukan tahap yang harus dilewati.
      */}
      <span
        className="inline-flex items-center gap-1.5 t-caption font-semibold uppercase tracking-[0.08em]"
        style={{ color: "var(--brand)" }}
      >
        <Sparkles size={13} aria-hidden /> {t("rt.title")}
        {sumber ? <span className="tnum normal-case tracking-normal text-muted">· {sumber}</span> : null}
      </span>

      {loading && !data && <p className="mt-2 t-caption text-muted">{t("rt.loading")}</p>}
      {error && (
        <p className="mt-2 t-caption" style={{ color: "var(--status-critical)" }}>
          {error}
        </p>
      )}

      {terbaik && (
        <div className="mt-2 flex flex-wrap items-end gap-x-6 gap-y-2">
          <span className="inline-flex items-center gap-2 t-lead font-semibold text-ink">
            {IKON[terbaik.mode]} {t(`rt.mode.${terbaik.mode}`)}
          </span>
          <Ukuran label={t("rt.arrive")} nilai={t("rt.days", { n: num(terbaik.predicted_days, 1) })} />
          <Ukuran label={t("rt.col.cost")} nilai={idr(terbaik.predicted_cost)} />
          <Ukuran
            label={t("rt.col.received")}
            nilai={t("rt.of", { a: num(terbaik.predicted_received), b: num(jumlah) })}
          />
        </div>
      )}

      {terbaik && data && (
        <p className="mt-2 t-caption leading-relaxed text-muted">
          {alasan(data, t, batasHari)}
        </p>
      )}
      {terbaik && gabungan && gabungan.barang > 1 && (
        <p className="mt-1 t-caption leading-relaxed text-muted">
          {t("rt.combined", { n: num(gabungan.barang), q: num(gabungan.unit) })}
        </p>
      )}

      {data && data.options.length === 0 && (
        <p className="mt-2 t-caption text-muted">{t("rt.none")}</p>
      )}

      {data && data.options.length > 1 && (
        <button
          onClick={() => setTerbuka((v) => !v)}
          aria-expanded={terbuka}
          className="mt-2 t-small font-semibold"
          style={{ color: "var(--brand)" }}
        >
          {terbuka ? t("rt.hide") : t("rt.compare", { n: num(data.options.length - 1) })}
        </button>
      )}

      {terbuka && data && data.options.length > 0 && (
        <div className="mt-3">
          <div className="mb-3 flex flex-wrap items-center gap-2" role="group" aria-label={t("rt.priority")}>
            <span className="t-caption text-muted">{t("rt.priority")}:</span>
            {PRIORITAS.map((p) => (
              <button
                key={p}
                onClick={() => setPrioritas(p)}
                aria-pressed={prioritas === p}
                className="rounded-full px-3 py-1 t-caption font-semibold"
                style={{
                  background:
                    prioritas === p
                      ? "color-mix(in srgb, var(--brand) 16%, transparent)"
                      : "var(--surface-sunken)",
                  color: prioritas === p ? "var(--brand)" : "var(--text-secondary)",
                  boxShadow: `inset 0 0 0 1px ${
                    prioritas === p ? "color-mix(in srgb, var(--brand) 40%, transparent)" : "var(--border)"
                  }`,
                }}
              >
                {t(`rt.p.${p}`)}
              </button>
            ))}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left t-small">
              <thead>
                <tr className="t-caption uppercase tracking-[0.06em] text-muted">
                  <th className="py-1.5 pr-3 font-semibold">{t("rt.col.mode")}</th>
                  <th className="py-1.5 pr-3 text-right font-semibold">{t("rt.col.distance")}</th>
                  <th className="py-1.5 pr-3 text-right font-semibold">{t("rt.col.days")}</th>
                  <th className="py-1.5 pr-3 text-right font-semibold">{t("rt.col.cost")}</th>
                  <th className="py-1.5 pr-3 text-right font-semibold">{t("rt.col.received")}</th>
                  <th className="py-1.5 text-right font-semibold">{t("rt.col.score")}</th>
                </tr>
              </thead>
              <tbody>
                {data.options.map((o) => (
                  <BarisOpsi key={o.mode} o={o} jumlah={jumlah} batasHari={batasHari} />
                ))}
              </tbody>
            </table>
          </div>

          <p className="mt-3 t-caption leading-relaxed text-muted">
            {data.model.kind === "ml" && data.model.metrics && data.model.range
              ? t("rt.model.ml", {
                  n: num(data.model.n_train),
                  dari: data.model.range.dari,
                  sampai: data.model.range.sampai,
                  h: num(data.model.metrics.hari_mae, 1),
                  b: num(data.model.metrics.biaya_mape * 100, 1),
                  t: num(data.model.metrics.terima_mae * 100, 1),
                })
              : t("rt.model.std", { n: num(data.model.n_train), min: num(data.model.min_history) })}
          </p>
        </div>
      )}
    </section>
  );
}

/** Satu ukuran (label kecil di atas, angka di bawah). */
function Ukuran({ label, nilai }: { label: string; nilai: string }) {
  return (
    <span className="flex flex-col">
      <span className="t-caption text-muted">{label}</span>
      <span className="tnum t-small font-semibold text-ink">{nilai}</span>
    </span>
  );
}

/** Kalimat alasan, disusun dari angka jawaban -- tidak dari tebakan layar. */
function alasan(
  d: RekomendasiRute,
  t: (k: string, p?: Record<string, string | number>) => string,
  batas?: number | null,
): string {
  const [b, ...lain] = d.options;
  if (!lain.length) return t("rt.why.single");
  const terlambat = lain.filter((o) => o.late);
  if (batas != null && terlambat.length) {
    return t("rt.why.late", {
      m: terlambat.map((o) => t(`rt.mode.${o.mode}`)).join(", "),
      d: num(batas),
    });
  }
  return t("rt.why.best", { s: b.score, n: d.options.length });
}

function BarisOpsi({
  o,
  jumlah,
  batasHari,
}: {
  o: OpsiRute;
  jumlah: number;
  batasHari?: number | null;
}) {
  const { t } = useI18n();
  const terbaik = o.rank === 1;
  return (
    <tr
      style={{
        borderTop: "1px solid var(--border)",
        background: terbaik ? "color-mix(in srgb, var(--brand) 7%, transparent)" : undefined,
      }}
    >
      <td className="py-2 pr-3">
        <span className="inline-flex items-center gap-1.5 font-semibold text-ink">
          {IKON[o.mode]} {t(`rt.mode.${o.mode}`)}
        </span>
        <span className="mt-1 flex flex-wrap items-center gap-1">
          {terbaik && (
            <span
              className="rounded-full px-2 py-0.5 t-caption font-semibold"
              style={{ background: "var(--brand)", color: "var(--on-brand, #fff)" }}
            >
              {t("rt.best")}
            </span>
          )}
          {o.badges.map((b) => (
            <span
              key={b}
              className="rounded-full px-2 py-0.5 t-caption"
              style={{ boxShadow: "inset 0 0 0 1px var(--border)", color: "var(--text-secondary)" }}
            >
              {t(`rt.badge.${b}`)}
            </span>
          ))}
          {o.late && batasHari != null && (
            <span
              className="inline-flex items-center gap-1 t-caption"
              style={{ color: "var(--status-warning)" }}
              title={t("rt.late", { n: num(batasHari) })}
            >
              <TriangleAlert size={12} aria-hidden /> {t("rt.late", { n: num(batasHari) })}
            </span>
          )}
        </span>
      </td>
      <td className="tnum py-2 pr-3 text-right">{num(o.distance_km)} km</td>
      <td className="tnum py-2 pr-3 text-right">{t("rt.days", { n: num(o.predicted_days, 1) })}</td>
      <td className="tnum py-2 pr-3 text-right">
        {idr(o.predicted_cost)}
        {o.expected_loss_value > 0 && (
          <span className="block t-caption text-muted">
            {t("rt.loss", { v: idr(o.expected_loss_value) })}
          </span>
        )}
      </td>
      <td className="tnum py-2 pr-3 text-right">
        {t("rt.of", { a: num(o.predicted_received), b: num(jumlah) })}
      </td>
      <td className="tnum py-2 text-right font-bold text-ink">{o.score}</td>
    </tr>
  );
}
