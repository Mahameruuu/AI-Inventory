"use client";

/**
 * Panel pendamping 3D Warehouse Twin: ringkasan, legenda, dan rincian rak.
 * Semua angka datang dari /api/warehouse-twin lewat lib/twin.ts.
 */

import Link from "next/link";
import { ArrowRight, X } from "lucide-react";

import { Badge, Card } from "@/components/ui";
import { num } from "@/lib/format";
import { useT } from "@/lib/i18n";
import {
  BarisTwin, LapisRisiko, RakTwin, StatusTwin, URUT_STATUS, WARNA_STATUS, kapasitasRak,
} from "@/lib/twin";

const pct = (v: number) => `${num(v * 100, 0)}%`;

export function LabelStatus({ s, lapis = "reorder", h }: { s: StatusTwin; lapis?: LapisRisiko; h?: number | null }) {
  const t = useT();
  return <Badge label={t(`tw.l.${lapis}.${s}`)} color={WARNA_STATUS[s]} title={t(`tw.l.${lapis}.${s}_d`, vars(h))} />;
}

/** Variabel {h}/{h2} untuk deskripsi lapisan "habis"; kosong bila horizon tidak diketahui. */
function vars(h?: number | null) {
  return h ? { h, h2: 2 * h } : { h: "?", h2: "?" };
}

export function Legenda({
  hitung, lapis = "reorder", horizon,
}: { hitung?: Record<StatusTwin, number>; lapis?: LapisRisiko; horizon?: number | null }) {
  const t = useT();
  return (
    <Card title={t("tw.legend")} subtitle={t(`tw.layer.src.${lapis}`, { h: horizon ?? "?" })}>
      <ul className="space-y-2">
        {URUT_STATUS.map((s) => (
          <li key={s} className="flex items-start gap-2.5">
            <span className="mt-1 h-3 w-3 shrink-0 rounded-sm" style={{ background: WARNA_STATUS[s] }} />
            <span className="t-body text-ink">
              <b>{t(`tw.l.${lapis}.${s}`)}</b>
              {hitung && <span className="ml-1.5 tabular-nums text-muted">· {t("tw.counts", { n: hitung[s] })}</span>}
              <span className="block t-small text-muted">{t(`tw.l.${lapis}.${s}_d`, vars(horizon))}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 t-small text-muted">{t("tw.box_note")}</p>
    </Card>
  );
}

function Baris({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b py-1.5 last:border-0" style={{ borderColor: "var(--border)" }}>
      <dt className="t-small text-muted">{k}</dt>
      <dd className="t-body text-right text-ink">{v}</dd>
    </div>
  );
}

export function DetailRak({
  rak, gudang, itemId, onPilihItem, onTutup, lapis = "reorder", horizon,
}: {
  lapis?: LapisRisiko;
  horizon?: number | null;
  rak: RakTwin;
  gudang: string;
  itemId: number | null;
  onPilihItem: (id: number | null) => void;
  onTutup: () => void;
}) {
  const t = useT();
  const kap = kapasitasRak(rak);
  const terpilih: BarisTwin | undefined = rak.slots.find((s) => s.item.item_id === itemId)?.item;
  const ada = (v: number | string | null | undefined) => (v == null || Number(v) <= 0 ? t("tw.slot.not_set") : num(v));

  return (
    <Card
      title={`${t("tw.rack")} ${rak.kode}`}
      subtitle={gudang}
      right={
        <button type="button" onClick={onTutup} aria-label={t("tw.detail.close")} className="rounded-md p-1 text-muted hover:text-ink">
          <X size={16} />
        </button>
      }
    >
      <dl>
        <Baris k={t("tw.zone")} v={<span className="text-muted">{t("tw.zone_na")}</span>} />
        <Baris k={t("tw.group")} v={rak.kategori} />
        <Baris k={t("tw.col.status")} v={<LabelStatus s={rak.status} lapis={lapis} h={horizon} />} />
        <Baris
          k={t("tw.capacity")}
          v={kap.persen == null ? <span className="text-muted">{t("tw.slot.not_set")}</span> : pct(kap.persen)}
        />
      </dl>
      {kap.persen != null && kap.dari < kap.dariTotal && (
        <p className="mt-1 t-small text-muted">{t("tw.capacity_partial", { n: kap.dari, m: kap.dariTotal })}</p>
      )}

      {terpilih && (
        <div className="mt-3 rounded-lg p-3" style={{ background: "var(--surface-sunken)" }}>
          <div className="t-small font-semibold uppercase tracking-wide text-muted">{t("tw.slot.selected")}</div>
          <div className="mt-1 t-body font-semibold text-ink">{terpilih.name}</div>
          <div className="t-small text-muted">{terpilih.sku}</div>
          <dl className="mt-2">
            <Baris k={t("tw.col.qty")} v={`${num(terpilih.quantity)} ${terpilih.unit_code}`} />
            <Baris k={t("tw.slot.reserved")} v={num(terpilih.reserved_quantity)} />
            <Baris k={t("tw.slot.min")} v={ada(terpilih.minimum_stock)} />
            <Baris k={t("tw.slot.reorder")} v={ada(terpilih.reorder_point)} />
            <Baris k={t("tw.slot.max")} v={ada(terpilih.maximum_stock)} />
            <Baris k={t("tw.col.status")} v={<LabelStatus s={terpilih.status} lapis={lapis} h={horizon} />} />
          </dl>
          <div className="mt-3 t-small font-semibold uppercase tracking-wide text-muted">{t("tw.dec.title")}</div>
          {terpilih.decision ? (
            <dl className="mt-1">
              <Baris k={t("tw.dec.order")} v={terpilih.decision.recommended_order_qty == null ? "—" : `${num(terpilih.decision.recommended_order_qty)} ${terpilih.unit_code}`} />
              <Baris k={t("tw.dec.stock")} v={terpilih.decision.available_stock == null ? "—" : num(terpilih.decision.available_stock)} />
              <Baris k={t("tw.dec.rop")} v={terpilih.decision.effective_reorder_point == null ? "—" : num(terpilih.decision.effective_reorder_point)} />
              <Baris k={t("tw.dec.cover")} v={terpilih.decision.days_of_cover == null ? "—" : t("tw.dec.days", { n: num(terpilih.decision.days_of_cover) })} />
            </dl>
          ) : (
            <p className="mt-1 t-small text-muted">{t("tw.dec.none")}</p>
          )}
          <div className="mt-3 t-small font-semibold uppercase tracking-wide text-muted">{t("tw.life.title")}</div>
          {terpilih.lifetime ? (
            <dl className="mt-1">
              <Baris k={t("tw.col.status")} v={terpilih.lifetime.status_label} />
              <Baris k={t("tw.life.deviation")} v={terpilih.lifetime.deviation_percentage == null ? "—" : `${num(terpilih.lifetime.deviation_percentage, 0)}%`} />
              <p className="mt-1 t-small text-muted">{terpilih.lifetime.basis}</p>
            </dl>
          ) : (
            <p className="mt-1 t-small text-muted">{t("tw.life.none")}</p>
          )}
          <Link href="/lifetime" className="mt-2 inline-flex items-center gap-1 text-xs font-semibold" style={{ color: "var(--brand)" }}>
            {t("tw.life.open")} <ArrowRight size={12} />
          </Link>
          <br />
          <Link href="/reorder" className="mt-2 inline-flex items-center gap-1 text-xs font-semibold" style={{ color: "var(--brand)" }}>
            {t("tw.dec.open")} <ArrowRight size={12} />
          </Link>
          {Number(terpilih.maximum_stock) > 0 && (
            <p className="mt-1 t-small text-muted">
              {t("tw.slot.fill", { p: num(Math.min(1, Number(terpilih.quantity) / Number(terpilih.maximum_stock)) * 100, 0) })}
            </p>
          )}
        </div>
      )}

      <div className="mt-3 t-small font-semibold uppercase tracking-wide text-muted">{t("tw.items")}</div>
      <ul className="mt-1 max-h-72 overflow-y-auto">
        {rak.slots.map((s) => (
          <li key={s.item.item_id}>
            <button
              type="button"
              onClick={() => onPilihItem(s.item.item_id === itemId ? null : s.item.item_id)}
              className="flex w-full items-center gap-2 rounded-md px-1.5 py-1.5 text-left hover:bg-[var(--surface-sunken)]"
              style={s.item.item_id === itemId ? { background: "var(--surface-sunken)" } : undefined}
            >
              <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: WARNA_STATUS[s.item.status] }} />
              <span className="min-w-0 flex-1">
                <span className="block truncate t-body text-ink">{s.item.name}</span>
                <span className="block t-small text-muted">{s.item.sku}</span>
              </span>
              <span className="t-body tabular-nums text-ink">{num(s.item.quantity)} <span className="text-muted">{s.item.unit_code}</span></span>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
