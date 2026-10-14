"use client";

/**
 * Panel Optimasi Rute Picking. Tidak menyentuh stok: hanya membaca barang
 * gudang terpilih dan menghitung urutan ambil (lib/picking.ts). Hasilnya
 * dikirim ke induk agar rutenya digambar di scene 3D.
 */

import { Calculator, FlaskConical, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge, Button, Select } from "@/components/ui";
import { num } from "@/lib/format";
import { useT } from "@/lib/i18n";
import {
  ASUMSI_BAWAAN, Asumsi, BarisPesanan, Blokir, HasilRute, adalahGalat, contohPesanan, hitungRute,
  periksaPesanan, stokTersedia,
} from "@/lib/picking";
import { BarisTwin, TataLetak, jalurGudang, layoutDock } from "@/lib/twin";

const KELAS_INPUT = "h-8 rounded-lg border bg-surface px-2 t-body text-ink outline-none focus:border-[var(--brand)]";

function Angka({ nilai, onUbah, lebar = "w-20", langkah = 1, min = 0 }: {
  nilai: number; onUbah: (v: number) => void; lebar?: string; langkah?: number; min?: number;
}) {
  return (
    <input
      type="number" inputMode="decimal" min={min} step={langkah} value={Number.isFinite(nilai) ? nilai : ""}
      onChange={(e) => onUbah(e.target.value === "" ? NaN : Number(e.target.value))}
      className={`${KELAS_INPUT} ${lebar} text-right tabular-nums`} style={{ borderColor: "var(--border)" }}
    />
  );
}

function durasi(detik: number, t: ReturnType<typeof useT>): string {
  if (detik < 90) return t("pk.sec", { s: num(detik, 0) });
  return t("pk.min", { m: num(detik / 60, 1) });
}

export default function PanelPicking({
  items, tata, hasil, onHasil, onPilihItem, tampilPembanding, onTampilPembanding, perintah, onPerintahSelesai,
}: {
  /** perintah dari pemandu demo: isi contoh pesanan, lalu (opsional) hitung */
  perintah?: { id: number; jalankan: boolean } | null;
  onPerintahSelesai?: () => void;
  items: BarisTwin[];
  tata: TataLetak;
  hasil: HasilRute | null;
  onHasil: (h: HasilRute | null) => void;
  onPilihItem: (rakId: string, itemId: number) => void;
  tampilPembanding: boolean;
  onTampilPembanding: (v: boolean) => void;
}) {
  const t = useT();
  const dock = useMemo(() => layoutDock(tata), [tata]);
  const lorongN = useMemo(() => jalurGudang(tata).lorongZ.length, [tata]);
  const idxKeluar = Math.max(0, dock.bay.findIndex((b) => b.jenis === "keluar"));

  const [baris, setBaris] = useState<BarisPesanan[]>([]);
  const [bayAwal, setBayAwal] = useState(idxKeluar);
  const [bayAkhir, setBayAkhir] = useState(idxKeluar);
  const [blokir, setBlokir] = useState<Blokir>({ lorong: [], koridorKiri: false, koridorKanan: false });
  const [asumsi, setAsumsi] = useState<Asumsi>(ASUMSI_BAWAAN);
  const [galat, setGalat] = useState<string | null>(null);

  const peta = useMemo(() => new Map(items.map((b) => [b.item_id, b])), [items]);
  const lokasiRak = useMemo(() => {
    const m = new Map<number, { rakId: string; kode: string }>();
    for (const r of tata.rak) for (const s of r.slots) m.set(s.item.item_id, { rakId: r.id, kode: r.kode });
    return m;
  }, [tata]);
  const masalah = useMemo(() => new Map(periksaPesanan(baris, items).map((x) => [x.itemId, x])), [baris, items]);

  const tersisa = items.filter((b) => !baris.some((p) => p.itemId === b.item_id) && stokTersedia(b) > 0);

  const jalankan = () => {
    setGalat(null);
    if (masalah.size) { setGalat(t("pk.err.invalid")); onHasil(null); return; }
    const h = hitungRute({ tata, items, pesanan: baris, bayAwal, bayAkhir, blokir, asumsi });
    if (adalahGalat(h)) {
      const nama = (h.itemIds ?? []).map((id) => peta.get(id)?.sku ?? id).join(", ");
      setGalat(t(`pk.err.${h.jenis}`, { x: nama }));
      onHasil(null);
    } else onHasil(h);
  };
  const ubah = (next: BarisPesanan[]) => { setBaris(next); if (hasil) onHasil(null); };
  // Pemandu demo: isi contoh pesanan dan/atau jalankan, sekali per perintah.
  useEffect(() => {
    if (!perintah) return;
    const contoh = contohPesanan(items, tata);
    setBaris(contoh);
    if (perintah.jalankan) {
      const h = hitungRute({ tata, items, pesanan: contoh, bayAwal, bayAkhir, blokir, asumsi });
      if (!adalahGalat(h)) onHasil(h);
    } else onHasil(null);
    onPerintahSelesai?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [perintah?.id]);
  const opsiBay = dock.bay.map((b, i) => ({ value: String(i), label: t(`pk.bay.${b.jenis}`) }));

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      {/* ---------------- masukan ---------------- */}
      <div className="space-y-3">
        <p className="t-small text-muted">{t("pk.demo_note")} {t("pk.no_stock")}</p>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value=""
            onChange={(v) => v && ubah([...baris, { itemId: Number(v), qty: 1 }])}
            options={[{ value: "", label: t("pk.add") }, ...tersisa.map((b) => ({
              value: String(b.item_id), label: `${b.sku} · ${b.name} (${lokasiRak.get(b.item_id)?.kode ?? "-"})`,
            }))]}
            className="max-w-[300px]"
          />
          <Button variant="ghost" onClick={() => ubah(contohPesanan(items, tata))}>
            <FlaskConical size={14} /> {t("pk.sample")}
          </Button>
        </div>

        {baris.length === 0 ? (
          <p className="rounded-lg p-3 t-body text-muted" style={{ background: "var(--surface-sunken)" }}>{t("pk.empty")}</p>
        ) : (
          <ul className="divide-y rounded-lg border" style={{ borderColor: "var(--border)" }}>
            {baris.map((p, i) => {
              const b = peta.get(p.itemId);
              const pesan = masalah.get(p.itemId);
              return (
                <li key={p.itemId} className="flex items-center gap-2 px-2.5 py-2" style={pesan ? { background: "color-mix(in srgb, var(--status-critical) 8%, transparent)" } : undefined}>
                  <span className="w-5 shrink-0 text-center t-small text-muted">{i + 1}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate t-body text-ink">{b?.name ?? p.itemId}</span>
                    <span className="block t-small text-muted">{b?.sku} · {lokasiRak.get(p.itemId)?.kode} · {t("pk.col.avail")} {b ? num(stokTersedia(b)) : "-"} {b?.unit_code}</span>
                    {pesan && <span className="block t-small" style={{ color: "var(--status-critical)" }}>{t(`pk.val.${pesan.kode}`, { n: pesan.maks == null ? "" : num(pesan.maks) })}</span>}
                  </span>
                  <Angka nilai={p.qty} min={0} onUbah={(v) => ubah(baris.map((x) => (x.itemId === p.itemId ? { ...x, qty: v } : x)))} />
                  <button type="button" title={t("pk.remove")} onClick={() => ubah(baris.filter((x) => x.itemId !== p.itemId))} className="rounded p-1 text-muted hover:text-ink">
                    <Trash2 size={14} />
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <div className="grid grid-cols-2 gap-3">
          <label className="block t-small text-muted">{t("pk.start")}
            <Select value={String(bayAwal)} onChange={(v) => { setBayAwal(Number(v)); onHasil(null); }} options={opsiBay} className="mt-1 w-full" />
          </label>
          <label className="block t-small text-muted">{t("pk.end")}
            <Select value={String(bayAkhir)} onChange={(v) => { setBayAkhir(Number(v)); onHasil(null); }} options={opsiBay} className="mt-1 w-full" />
          </label>
        </div>

        <fieldset>
          <legend className="t-small font-semibold uppercase tracking-wide text-muted">{t("pk.block")}</legend>
          <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1">
            {Array.from({ length: lorongN }, (_, k) => (
              <label key={k} className="flex items-center gap-1.5 t-body text-ink">
                <input type="checkbox" checked={blokir.lorong.includes(k)}
                  onChange={(e) => { setBlokir({ ...blokir, lorong: e.target.checked ? [...blokir.lorong, k] : blokir.lorong.filter((x) => x !== k) }); onHasil(null); }} />
                {t("pk.aisle", { n: k + 1 })}
              </label>
            ))}
            <label className="flex items-center gap-1.5 t-body text-ink">
              <input type="checkbox" checked={blokir.koridorKiri} onChange={(e) => { setBlokir({ ...blokir, koridorKiri: e.target.checked }); onHasil(null); }} />
              {t("pk.corr.left")}
            </label>
            <label className="flex items-center gap-1.5 t-body text-ink">
              <input type="checkbox" checked={blokir.koridorKanan} onChange={(e) => { setBlokir({ ...blokir, koridorKanan: e.target.checked }); onHasil(null); }} />
              {t("pk.corr.right")}
            </label>
          </div>
        </fieldset>

        <details>
          <summary className="cursor-pointer t-small font-semibold uppercase tracking-wide text-muted">{t("pk.assump")}</summary>
          <div className="mt-2 flex flex-wrap gap-3">
            <label className="t-small text-muted">{t("pk.speed")}<br />
              <Angka nilai={asumsi.kecepatan} langkah={0.1} min={0.1} onUbah={(v) => setAsumsi({ ...asumsi, kecepatan: v > 0 ? v : ASUMSI_BAWAAN.kecepatan })} />
            </label>
            <label className="t-small text-muted">{t("pk.sec_line")}<br />
              <Angka nilai={asumsi.detikPerBaris} onUbah={(v) => setAsumsi({ ...asumsi, detikPerBaris: v >= 0 ? v : 0 })} />
            </label>
            <label className="t-small text-muted">{t("pk.sec_unit")}<br />
              <Angka nilai={asumsi.detikPerUnit} onUbah={(v) => setAsumsi({ ...asumsi, detikPerUnit: v >= 0 ? v : 0 })} />
            </label>
          </div>
          <p className="mt-2 t-small text-muted">{t("pk.not_modeled")}</p>
        </details>

        <div className="flex gap-2">
          <Button variant="solid" onClick={jalankan} disabled={baris.length === 0}>
            <Calculator size={14} /> {t("pk.run")}
          </Button>
          <Button variant="ghost" onClick={() => { setBaris([]); setGalat(null); onHasil(null); }} disabled={baris.length === 0 && !hasil}>
            {t("pk.clear")}
          </Button>
        </div>
        {galat && <p className="t-body" style={{ color: "var(--status-critical)" }}>{galat}</p>}
      </div>

      {/* ---------------- hasil ---------------- */}
      <div>
        {hasil ? (
          <div className="space-y-3">
            <div className="grid grid-cols-3 gap-2.5">
              <div className="rounded-lg p-3" style={{ background: "var(--surface-sunken)" }}>
                <div className="t-micro font-semibold uppercase tracking-[0.07em] text-muted">{t("pk.res.distance")}</div>
                <div className="stat-figure mt-1 text-[20px] font-bold text-ink">{num(hasil.jarak, 1)} m</div>
                <div className="t-small text-muted">{t("pk.res.baseline", { d: num(hasil.pembanding.jarak, 1) })}</div>
              </div>
              <div className="rounded-lg p-3" style={{ background: "var(--surface-sunken)" }}>
                <div className="t-micro font-semibold uppercase tracking-[0.07em] text-muted">{t("pk.res.saving")}</div>
                <div className="stat-figure mt-1 text-[20px] font-bold" style={{ color: hasil.hemat > 0 ? "var(--status-good)" : "var(--text-primary)" }}>
                  {num(hasil.hemat * 100, 0)}%
                </div>
                <div className="t-small text-muted">{num(hasil.pembanding.jarak - hasil.jarak, 1)} m</div>
              </div>
              <div className="rounded-lg p-3" style={{ background: "var(--surface-sunken)" }}>
                <div className="t-micro font-semibold uppercase tracking-[0.07em] text-muted">{t("pk.res.time")}</div>
                <div className="stat-figure mt-1 text-[20px] font-bold text-ink">{durasi(hasil.waktu.total, t)}</div>
                <div className="t-small text-muted">{t("pk.res.baseline_time", { t: durasi(hasil.waktuPembanding.total, t) })}</div>
              </div>
            </div>
            <p className="t-small text-muted">{t("pk.res.time_hint", { j: durasi(hasil.waktu.jalan, t), a: durasi(hasil.waktu.ambil, t) })}</p>

            <div className="flex flex-wrap items-center gap-2">
              <Badge label={t(`pk.method.${hasil.metode}`)} color={hasil.optimal ? "#16a34a" : "#f97316"} />
              <label className="flex items-center gap-1.5 t-small text-muted">
                <input type="checkbox" checked={tampilPembanding} onChange={(e) => onTampilPembanding(e.target.checked)} />
                {t("pk.show_base")}
              </label>
            </div>

            <div className="t-small font-semibold uppercase tracking-wide text-muted">{t("pk.steps")}</div>
            <ol className="max-h-72 space-y-1 overflow-y-auto">
              {hasil.urutan.map((l) => (
                <li key={l.itemId}>
                  <button
                    type="button"
                    onClick={() => { const r = lokasiRak.get(l.itemId); if (r) onPilihItem(r.rakId, l.itemId); }}
                    className="flex w-full items-center gap-2.5 rounded-md px-1.5 py-1.5 text-left hover:bg-[var(--surface-sunken)]"
                  >
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white" style={{ background: "var(--brand)" }}>{l.urut}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate t-body text-ink">{l.nama}</span>
                      <span className="block t-small text-muted">{l.sku} · {l.rakKode}</span>
                    </span>
                    <span className="text-right t-small tabular-nums text-muted">
                      {num(l.qty)} {l.satuan}<br />{t("pk.leg", { d: num(l.jarakDari, 1) })}
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </div>
        ) : (
          <p className="t-body text-muted">{t("pk.sub")}</p>
        )}
      </div>
    </div>
  );
}
