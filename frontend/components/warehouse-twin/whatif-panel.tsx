"use client";

/**
 * Panel What-if Penempatan. Sandbox: memegang skenario penempatan di memori
 * browser dan menghitung KPI rute untuk kondisi awal vs skenario pada pesanan
 * simulasi yang sama (lib/whatif.ts). Tidak ada panggilan API dan tidak ada
 * penulisan apa pun.
 */

import { Shuffle, Undo2, Wand2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button, Select } from "@/components/ui";
import { num } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { HasilRute, adalahGalat, hitungRute } from "@/lib/picking";
import { BarisTwin, TataLetak } from "@/lib/twin";
import {
  Penempatan, bandingkan, barangBerpindah, bayKeluar, bobotPrakiraan, buatPesananSimulasi, penempatanAwal,
  Evaluasi, terapkanPenempatan, tukar, usulanPenempatan,
} from "@/lib/whatif";

const KELAS_INPUT = "h-8 w-20 rounded-lg border bg-surface px-2 text-right t-body tabular-nums text-ink outline-none focus:border-[var(--brand)]";

function Angka({ nilai, onUbah, min = 1 }: { nilai: number; onUbah: (v: number) => void; min?: number }) {
  return (
    <input type="number" min={min} step={1} value={Number.isFinite(nilai) ? nilai : ""}
      onChange={(e) => onUbah(e.target.value === "" ? NaN : Math.max(min, Math.floor(Number(e.target.value))))}
      className={KELAS_INPUT} style={{ borderColor: "var(--border)" }} />
  );
}

function Delta({ awal, skenario, satuan, t }: { awal: number; skenario: number; satuan: string; t: ReturnType<typeof useT> }) {
  const d = skenario - awal;
  const pct = awal > 0 ? (d / awal) * 100 : 0;
  const baik = d < -1e-9, buruk = d > 1e-9;
  return (
    <span className="t-small tabular-nums" style={{ color: baik ? "var(--status-good)" : buruk ? "var(--status-critical)" : "var(--text-muted)" }}>
      {baik || buruk ? `${d > 0 ? "+" : ""}${num(d, 1)} ${satuan} (${pct > 0 ? "+" : ""}${num(pct, 0)}%) · ${t(baik ? "wi.better" : "wi.worse")}` : t("wi.same")}
    </span>
  );
}

export default function PanelWhatIf({
  tata, items, hasil, skenario, onSkenario, tampilan, onTampilan, onEvaluasi,
}: {
  onEvaluasi?: (e: Evaluasi | null) => void;
  tata: TataLetak;
  items: BarisTwin[];
  hasil: HasilRute | null;
  skenario: Penempatan | null;
  onSkenario: (p: Penempatan | null) => void;
  tampilan: "awal" | "skenario";
  onTampilan: (v: "awal" | "skenario") => void;
}) {
  const t = useT();
  const [jumlah, setJumlah] = useState(40);
  const [baris, setBaris] = useState(6);
  const [seed, setSeed] = useState(42);
  const [seragam, setSeragam] = useState(false);
  const [a, setA] = useState("");
  const [c, setC] = useState("");

  const bay = useMemo(() => bayKeluar(tata), [tata]);
  const awal = useMemo(() => penempatanAwal(tata), [tata]);
  const { bobot, tanpaPrakiraan } = useMemo(() => bobotPrakiraan(items, seragam), [items, seragam]);
  const nama = useMemo(() => new Map(items.map((b) => [b.item_id, b])), [items]);
  const asumsi = hasil?.masukan.asumsi;
  const blokir = hasil?.masukan.blokir;

  const eval_ = useMemo(() => {
    if (!skenario || !(jumlah > 0) || !(baris > 0)) return null;
    const pesanan = buatPesananSimulasi([...awal.keys()], bobot, jumlah, baris, seed);
    return bandingkan(tata, items, skenario, pesanan, { bayAwal: bay, bayAkhir: bay, blokir, asumsi });
  }, [skenario, tata, items, awal, bobot, jumlah, baris, seed, bay, blokir, asumsi]);

  useEffect(() => { onEvaluasi?.(eval_); }, [eval_, onEvaluasi]);
  useEffect(() => () => onEvaluasi?.(null), [onEvaluasi]);

  const pesananAnda = useMemo(() => {
    if (!skenario || !hasil) return null;
    const baru = hitungRute({ ...hasil.masukan, tata: terapkanPenempatan(tata, skenario), items });
    return adalahGalat(baru) ? null : baru;
  }, [skenario, hasil, tata, items]);

  const berpindah = useMemo(() => (skenario ? [...barangBerpindah(awal, skenario)] : []), [skenario, awal]);
  const rakKode = useMemo(() => new Map(tata.rak.map((r) => [r.id, r.kode])), [tata]);
  const opsiBarang = [{ value: "", label: "—" }, ...items.filter((b) => awal.has(b.item_id)).map((b) => ({ value: String(b.item_id), label: `${b.sku} · ${b.name}` }))];

  const usul = () => { onSkenario(usulanPenempatan(tata, items, bobot, bay, blokir)); onTampilan("skenario"); };
  const tukarDua = () => {
    if (!a || !c || a === c) return;
    onSkenario(tukar(skenario ?? awal, Number(a), Number(c)));
    onTampilan("skenario");
  };

  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <div className="space-y-3">
        <p className="rounded-lg p-2.5 t-small text-ink" style={{ background: "var(--surface-sunken)" }}>{t("wi.note")}</p>

        <div className="flex flex-wrap gap-2">
          <Button variant="solid" onClick={usul}><Wand2 size={14} /> {t("wi.suggest")}</Button>
          <Button variant="ghost" onClick={() => { onSkenario(null); onTampilan("awal"); }} disabled={!skenario}>
            <Undo2 size={14} /> {t("wi.reset")}
          </Button>
        </div>

        <fieldset>
          <legend className="t-small font-semibold uppercase tracking-wide text-muted">{t("wi.swap")}</legend>
          <div className="mt-1 grid grid-cols-[1fr_1fr_auto] items-end gap-2">
            <label className="block t-small text-muted">{t("wi.swap_a")}<Select value={a} onChange={setA} options={opsiBarang} className="mt-1 w-full" /></label>
            <label className="block t-small text-muted">{t("wi.swap_b")}<Select value={c} onChange={setC} options={opsiBarang} className="mt-1 w-full" /></label>
            <Button variant="ghost" onClick={tukarDua} disabled={!a || !c || a === c}><Shuffle size={14} /> {t("wi.swap_do")}</Button>
          </div>
        </fieldset>

        <fieldset>
          <legend className="t-small font-semibold uppercase tracking-wide text-muted">{t("wi.params")}</legend>
          <div className="mt-1 flex flex-wrap items-end gap-3">
            <label className="t-small text-muted">{t("wi.orders")}<br /><Angka nilai={jumlah} onUbah={setJumlah} /></label>
            <label className="t-small text-muted">{t("wi.lines")}<br /><Angka nilai={baris} onUbah={setBaris} /></label>
            <label className="t-small text-muted">{t("wi.seed")}<br /><Angka nilai={seed} onUbah={setSeed} min={0} /></label>
          </div>
          <label className="mt-2 flex items-center gap-1.5 t-small text-muted">
            <input type="checkbox" checked={seragam} onChange={(e) => setSeragam(e.target.checked)} /> {t("wi.uniform")}
          </label>
          <p className="mt-2 t-small text-muted">{t("wi.basis", { n: jumlah, m: baris, s: seed })}</p>
          {!seragam && tanpaPrakiraan > 0 && <p className="t-small text-muted">{t("wi.no_forecast", { n: tanpaPrakiraan })}</p>}
        </fieldset>
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <span className="t-small font-semibold uppercase tracking-wide text-muted">{t("wi.view")}</span>
          {(["awal", "skenario"] as const).map((v) => (
            <button key={v} type="button" onClick={() => onTampilan(v)} disabled={v === "skenario" && !skenario}
              aria-pressed={tampilan === v}
              className="rounded-lg border px-2.5 py-1 text-xs font-semibold disabled:opacity-40"
              style={{
                borderColor: tampilan === v ? "var(--brand)" : "var(--border)",
                background: tampilan === v ? "color-mix(in srgb, var(--brand) 12%, transparent)" : "var(--surface-1)",
                color: tampilan === v ? "var(--brand)" : "var(--text-secondary)",
              }}>{t(`wi.view.${v}`)}</button>
          ))}
        </div>

        {!eval_ ? (
          <p className="t-body text-muted">{t("wi.empty")}</p>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-2.5">
              <div className="rounded-lg p-3" style={{ background: "var(--surface-sunken)" }}>
                <div className="t-micro font-semibold uppercase tracking-[0.07em] text-muted">{t("wi.kpi.dist")}</div>
                <div className="mt-1 flex items-baseline gap-2 text-ink">
                  <span className="t-body text-muted line-through">{num(eval_.awal.jarakRata, 1)} m</span>
                  <span className="stat-figure text-[20px] font-bold">{num(eval_.skenario.jarakRata, 1)} m</span>
                </div>
                <Delta awal={eval_.awal.jarakRata} skenario={eval_.skenario.jarakRata} satuan="m" t={t} />
              </div>
              <div className="rounded-lg p-3" style={{ background: "var(--surface-sunken)" }}>
                <div className="t-micro font-semibold uppercase tracking-[0.07em] text-muted">{t("wi.kpi.time")}</div>
                <div className="mt-1 flex items-baseline gap-2 text-ink">
                  <span className="t-body text-muted line-through">{num(eval_.awal.waktuRata, 0)} s</span>
                  <span className="stat-figure text-[20px] font-bold">{num(eval_.skenario.waktuRata, 0)} s</span>
                </div>
                <Delta awal={eval_.awal.waktuRata} skenario={eval_.skenario.waktuRata} satuan="s" t={t} />
              </div>
              <div className="rounded-lg p-3" style={{ background: "var(--surface-sunken)" }}>
                <div className="t-micro font-semibold uppercase tracking-[0.07em] text-muted">{t("wi.kpi.total", { n: eval_.awal.pesanan })}</div>
                <div className="mt-1 stat-figure text-[18px] font-bold text-ink">
                  {num(eval_.awal.jarakTotal, 0)} → {num(eval_.skenario.jarakTotal, 0)} m
                </div>
              </div>
              <div className="rounded-lg p-3" style={{ background: "var(--surface-sunken)" }}>
                <div className="t-micro font-semibold uppercase tracking-[0.07em] text-muted">{t("wi.kpi.moved")}</div>
                <div className="mt-1 stat-figure text-[18px] font-bold text-ink">{num(eval_.berpindah)}</div>
              </div>
            </div>
            {(eval_.awal.gagal > 0 || eval_.skenario.gagal > 0) && (
              <p className="t-small" style={{ color: "var(--status-serious)" }}>{t("wi.failed", { n: Math.max(eval_.awal.gagal, eval_.skenario.gagal) })}</p>
            )}

            <div className="rounded-lg border p-3" style={{ borderColor: "var(--border)" }}>
              <div className="t-small font-semibold uppercase tracking-wide text-muted">{t("wi.yours")}</div>
              {hasil && pesananAnda ? (
                <div className="mt-1 flex flex-wrap items-baseline gap-2 text-ink">
                  <span className="t-body text-muted line-through">{num(hasil.jarak, 1)} m</span>
                  <span className="stat-figure text-[18px] font-bold">{num(pesananAnda.jarak, 1)} m</span>
                  <Delta awal={hasil.jarak} skenario={pesananAnda.jarak} satuan="m" t={t} />
                </div>
              ) : (
                <p className="mt-1 t-small text-muted">{t("wi.yours_none")}</p>
              )}
            </div>

            {berpindah.length > 0 && (
              <div>
                <div className="t-small font-semibold uppercase tracking-wide text-muted">{t("wi.moved_list")}</div>
                <ul className="mt-1 max-h-44 overflow-y-auto">
                  {berpindah.slice(0, 20).map((id) => (
                    <li key={id} className="flex items-center justify-between gap-2 py-1 t-body text-ink">
                      <span className="min-w-0 truncate">{nama.get(id)?.name}<span className="ml-1.5 t-small text-muted">{nama.get(id)?.sku}</span></span>
                      <span className="shrink-0 t-small tabular-nums text-muted">
                        {t("wi.from_to", { a: rakKode.get(awal.get(id)!.rakId) ?? "-", b: rakKode.get(skenario!.get(id)!.rakId) ?? "-" })}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
