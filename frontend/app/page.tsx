"use client";

/**
 * Dasbor / Dashboard.
 *
 * TIGA PERTANYAAN, DAN HANYA TIGA:
 *
 *   1. Bagaimana kondisi persediaan sekarang?   -> Total SKU, Total Stok
 *   2. Apa yang membutuhkan perhatian?          -> Perlu pesan ulang, risiko habis
 *   3. Apa yang diprakirakan akan terjadi?      -> Kebutuhan horizon keputusan
 *
 * APA YANG DICABUT PADA 2 SEPTEMBER 2026, dan kenapa. Versi sebelumnya
 * menampilkan delapan kartu angka, dua grafik, dua gauge, dan dua tabel; tidak
 * satu pun dari yang berikut menjawab salah satu dari ketiga pertanyaan di
 * atas:
 *
 *   Penerimaan / Pengeluaran / Pergerakan Stok   tiga kartu berisi jumlah
 *       DOKUMEN. Tidak ada keputusan yang berubah karena jumlah dokumen naik.
 *   Arus Stok 30 Hari (donat masuk vs keluar)    dua angka yang sudah
 *       diucapkan kartu Pergerakan tepat di sebelahnya.
 *   Kesiapan Operasional (dua gauge)             persentase master data yang
 *       berstatus aktif. Bukan kondisi persediaan sama sekali.
 *   Transaksi Terakhir (10 baris)                salinan halaman Transaksi.
 *
 * GUDANG 3D MENJADI TOKOH UTAMA (Oktober 2026). Modul 3D Warehouse Twin tidak
 * lagi punya halaman, menu, pemilih gudang, maupun deretan KPI sendiri: ia
 * adalah bagian dari dasbor ini, membaca gudang yang sama dan status yang
 * sama. Dua definisi "perlu perhatian" dalam satu aplikasi adalah cacat yang
 * sudah pernah dibereskan di sini; karena itu warna 3D memakai keputusan mesin
 * pemesanan ulang, bukan aturan stok minimum sendiri. Alamat lama
 * /warehouse-twin dialihkan ke sini (next.config.mjs).
 *
 * DASBOR TIDAK PUNYA RUMUS SENDIRI. Sebelumnya ia memakai definisi "stok
 * menipis" miliknya sendiri sementara halaman Pemesanan Ulang memakai titik
 * pesan efektif -- dua definisi untuk satu pertanyaan, dan tidak ada satu pun
 * galat yang menunjukkan mana yang benar bila keduanya berselisih. Kini
 * seluruh angka perhatian dan kebutuhan ke depan berasal dari mesin pemesanan
 * ulang, dirakit di backend/app/routers/dashboard.py, dan layar ini hanya
 * merendernya.
 */

import Link from "next/link";
import { ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeftRight,
  ArrowRight,
  Boxes,
  ChevronDown,
  Info,
  Pause,
  Play,
  Route,
  LayoutDashboard,
  Sparkles,
  Timer,
  Layers,
  Package,
  RefreshCw,
  TrendingUp,
  TriangleAlert,
} from "lucide-react";

import {
  Card,
  Empty,
  ErrorBox,
  Insight,
  PageHeader,
  Select,
  SkeletonChart,
  SkeletonTable,
  SkeletonTiles,
  StatTile,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { HBar } from "@/components/charts";
import { AKSI, PillAksi } from "@/components/status";
import PanggungTwin from "@/components/warehouse-twin/stage";
import { DetailRak, Legenda } from "@/components/warehouse-twin/panels";
import PanelPicking from "@/components/warehouse-twin/picking-panel";
import type { HasilRute } from "@/lib/picking";
import type { Pilihan } from "@/components/warehouse-twin/scene";
import { segarkanSemua, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { idr, num } from "@/lib/format";
import { GudangApi } from "@/lib/peta";
import { JawabanTwin, LapisRisiko, URUT_LAPIS, hitungStatus, horizonHari, susunTataLetak, terapkanLapis } from "@/lib/twin";

interface Dashboard {
  condition: { warehouses: number; items: number; stock: number; value: number };
  stock_by_warehouse: { code: string; name: string; total_stock: number; stock_value: number }[];
  attention: {
    need_reorder: number;
    stockout_risk: number;
    high_priority: number;
    healthy: number;
    rows: {
      sku: string;
      item_name: string;
      warehouse_code: string;
      unit_code: string | null;
      current_stock: number;
      reorder_point: number;
      forecast_usage: number | null;
      horizon_days: number;
      days_of_cover: number | null;
      recommended_order_qty: number | null;
      status: string;
      status_label: string;
      priority: string;
      priority_label: string;
    }[];
  };
  forecast: {
    horizon_days: number | null;
    forecast_usage: number;
    recommended_order_qty: number;
    qty_unknown: number;
    projected_stockout: number;
    without_forecast: number;
  };
  state: { text: string; level: string };
  value_basis: string;
  truncated: boolean;
}

/*
 * Warna status TIDAK LAGI DIDEFINISIKAN DI SINI.
 *
 * Komentar yang berdiri di tempat ini dulu berbunyi "nilainya sama persis
 * dengan yang dipakai halaman Pemesanan Ulang" -- dan itu tidak benar:
 * "Perlu pesan ulang" tertulis `--status-serious` di sini dan
 * `--status-warning` di sana. Satu barang berganti warna saat pembacanya
 * berpindah layar, tanpa satu pun angkanya berubah. Komentar tidak dapat
 * menjaga dua salinan tetap sama; hanya satu salinan yang bisa.
 */

const NADA: Record<string, "neutral" | "warning"> = {
  good: "neutral",
  info: "neutral",
  warning: "warning",
};

const AKSES_CEPAT = [
  { href: "/forecasting", key: "nav.forecasting", icon: TrendingUp },
  { href: "/reorder", key: "nav.reorder", icon: RefreshCw },
  { href: "/transfer", key: "nav.transfer", icon: ArrowLeftRight },
  { href: "/lifetime", key: "nav.lifetime", icon: Timer },
  { href: "/assistant", key: "nav.chat", icon: Sparkles },
];

/** Selang penyegaran otomatis. Mesin reorder menjawab dalam ~0,3 dtk per gudang. */
const SELANG_SEGAR_MS = 30_000;

/**
 * Penyegaran otomatis: menarik ulang seluruh data layar tiap SELANG_SEGAR_MS
 * selama tab terlihat. Tab yang tersembunyi tidak menembak API; begitu terlihat
 * kembali dan data sudah basi, ditarik seketika.
 */
function useSegarOtomatis(aktif: boolean) {
  const terakhir = useRef(Date.now());
  useEffect(() => {
    if (!aktif) return;
    const tarik = () => { terakhir.current = Date.now(); segarkanSemua(); };
    const id = window.setInterval(() => { if (!document.hidden) tarik(); }, SELANG_SEGAR_MS);
    const saatTampil = () => {
      if (!document.hidden && Date.now() - terakhir.current > SELANG_SEGAR_MS) tarik();
    };
    document.addEventListener("visibilitychange", saatTampil);
    return () => { window.clearInterval(id); document.removeEventListener("visibilitychange", saatTampil); };
  }, [aktif]);
}

/** Kartu yang dapat dilipat, supaya panggung 3D tetap mendapat ruang. */
function Lipat({
  icon, title, subtitle, right, defaultOpen = true, children,
}: {
  icon: ReactNode;
  title: string;
  subtitle?: string;
  right?: ReactNode;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const { t } = useI18n();
  const [buka, setBuka] = useState(defaultOpen);
  return (
    <Card
      icon={icon}
      title={title}
      subtitle={buka ? subtitle : undefined}
      right={
        <div className="flex items-center gap-3">
          {buka && right}
          <button
            type="button"
            onClick={() => setBuka((v) => !v)}
            aria-expanded={buka}
            title={buka ? t("dash.panel.fold") : t("dash.panel.unfold")}
            className="rounded-md p-1 text-muted hover:text-ink"
          >
            <ChevronDown size={16} className={buka ? "" : "-rotate-90"} style={{ transition: "transform .15s" }} />
          </button>
        </div>
      }
    >
      {buka ? children : null}
    </Card>
  );
}

export default function DashboardPage() {
  const { t } = useI18n();
  const gudang = useApi<{ items: GudangApi[] }>("/api/warehouses", { page_size: 200 });
  const [gudangId, setGudangId] = useState("");
  const [pilihan, setPilihan] = useState<Pilihan | null>(null);

  const daftar = gudang.data?.items;
  useEffect(() => {
    if (!gudangId && daftar && daftar.length) setGudangId(String(daftar[0].id));
  }, [daftar, gudangId]);
  useEffect(() => { setPilihan(null); setRutePicking(null); }, [gudangId]);

  const { data, error, loading } = useApi<Dashboard>(
    gudangId ? "/api/dashboard" : null, { warehouse_id: gudangId });
  const twin = useApi<JawabanTwin>(gudangId ? "/api/warehouse-twin" : null, { warehouse_id: gudangId });

  // useApi menahan data lama selama penarikan baru atau saat galat. Menampilkannya
  // di bawah gudang lain yang sedang dipilih berarti angka gudang A tampil sebagai gudang B.
  const twinData = twin.data && !twin.error && String(twin.data.warehouse.id) === gudangId ? twin.data : null;
  // Lapisan risiko hanya mengganti `status` tiap barang; tata letak tetap sama.
  const [lapis, setLapis] = useState<LapisRisiko>("reorder");
  const itemsLapis = useMemo(() => (twinData ? terapkanLapis(twinData.items, lapis) : null), [twinData, lapis]);
  const tata = useMemo(() => (itemsLapis ? susunTataLetak(itemsLapis) : null), [itemsLapis]);
  const hitung = useMemo(() => (itemsLapis ? hitungStatus(itemsLapis) : undefined), [itemsLapis]);
  const horizon = useMemo(() => (twinData ? horizonHari(twinData.items) : null), [twinData]);
  const [rutePicking, setRutePicking] = useState<HasilRute | null>(null);
  const [rutePembanding, setRutePembanding] = useState(false);
  const pilihFn = useCallback((p: Pilihan | null) => setPilihan(p), []);

  // ---------- data langsung ----------
  const [otomatis, setOtomatis] = useState(true);
  useSegarOtomatis(otomatis && !!gudangId);
  const [diperbarui, setDiperbarui] = useState<Date | null>(null);
  const [berubah, setBerubah] = useState<string[]>([]);
  const prevStok = useRef<{ gudang: number; peta: Map<number, number> } | null>(null);
  useEffect(() => {
    if (!twinData) return;
    const peta = new Map(twinData.items.map((b) => [b.item_id, Number(b.quantity)]));
    const prev = prevStok.current;
    if (prev && prev.gudang === twinData.warehouse.id) {
      // Selisih dihitung dari DATA, bukan dari animasi: hanya barang yang stoknya
      // benar-benar berbeda dari penarikan sebelumnya yang dilaporkan.
      setBerubah(twinData.items.filter((b) => prev.peta.get(b.item_id) !== Number(b.quantity)).map((b) => b.name));
    } else {
      setBerubah([]);
    }
    prevStok.current = { gudang: twinData.warehouse.id, peta };
    setDiperbarui(new Date());
  }, [twinData]);

  if (error || gudang.error) return <ErrorBox message={(error || gudang.error) as string} />;

  /*
   * Kepala halaman berdiri di LUAR cabang memuat: judul dan kalimat
   * pengantarnya tidak bergantung pada data, jadi menahannya sampai data tiba
   * hanya membuat layar kosong lebih lama.
   */
  const kepala = (
    <PageHeader
      icon={<LayoutDashboard size={20} />}
      eyebrow={t("brand.name")}
      title={t("dash.title")}
      description={t("dash.desc")}
    >
      <div className="flex items-center gap-2">
        <label className="t-small text-muted">{t("dash.warehouse")}</label>
        <Select
          value={gudangId}
          onChange={setGudangId}
          options={(daftar ?? []).map((g) => ({ value: String(g.id), label: `${g.code} · ${g.name}` }))}
        />
      </div>
    </PageHeader>
  );

  // data lama dari gudang sebelumnya tidak ditampilkan di bawah pilihan baru
  const d = loading || !data || String(gudangId) === "" ? null : data;
  if (!d) {
    return (
      <>
        {kepala}
        <SkeletonTiles count={4} />
        <div className="mt-4">
          <SkeletonChart height={420} delay={90} />
        </div>
      </>
    );
  }

  const a = d.attention;
  const f = d.forecast;
  const rakTerpilih = tata?.rak.find((r) => r.id === pilihan?.rakId) ?? null;
  const namaGudang = twinData ? `${twinData.warehouse.code} · ${twinData.warehouse.name}` : "";

  return (
    <>
      {kepala}

      {/* SATU kalimat kondisi, bukan daftar berbutir. Kalimatnya sudah menyebut
          tindakannya, dan angkanya sudah ada di kartu tepat di bawahnya. */}
      <Insight tone={NADA[d.state.level] ?? "neutral"}>{d.state.text}</Insight>

      {/* ---------- 1 & 2: kondisi sekarang, lalu yang perlu perhatian ---------- */}
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
        <StatTile
          label={t("dash.kpi.items")}
          value={num(d.condition.items)}
          hint={t("dash.kpi.items_hint")}
          icon={<Package size={15} />}
          delay={0}
        />
        <StatTile
          label={t("dash.kpi.stock")}
          value={num(d.condition.stock)}
          hint={t("dash.kpi.stock_hint", { n: num(d.condition.warehouses) })}
          icon={<Layers size={15} />}
          delay={60}
        />
        <StatTile
          label={t("dash.kpi.reorder")}
          value={num(a.need_reorder)}
          hint={a.need_reorder > 0 ? t("dash.kpi.reorder_hint") : t("dash.kpi.reorder_ok")}
          icon={<RefreshCw size={15} />}
          accent={a.need_reorder > 0 ? AKSI.PERLU_REORDER.warna : AKSI.AMAN.warna}
          delay={120}
        />
        <StatTile
          label={t("dash.kpi.stockout")}
          value={num(a.stockout_risk)}
          hint={
            a.stockout_risk > 0
              ? t("dash.kpi.stockout_hint", { n: num(a.high_priority) })
              : t("dash.kpi.stockout_ok")
          }
          icon={<TriangleAlert size={15} />}
          accent={a.stockout_risk > 0 ? AKSI.RISIKO_STOCKOUT.warna : AKSI.AMAN.warna}
          delay={180}
        />
      </div>

      {/* ---------- akses cepat ke modul AI ---------- */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="t-small font-semibold uppercase tracking-wide text-muted">{t("dash.quick")}</span>
        {AKSES_CEPAT.map((q) => (
          <Link
            key={q.href}
            href={q.href}
            className="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold text-ink-2 hover:text-ink"
            style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
          >
            <q.icon size={13} /> {t(q.key)}
          </Link>
        ))}
      </div>

      {/* ---------- gudang 3D: tokoh utama ---------- */}
      <div className="mt-4 grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
        <Card
          icon={<Boxes size={15} />}
          title={t("tw.view.title")}
          subtitle={t("tw.view.sub")}
          right={
            <div className="flex items-center gap-2 t-small text-muted">
              <span
                className="inline-block h-2 w-2 rounded-full"
                style={{ background: otomatis ? "var(--status-good)" : "var(--status-neutral)" }}
              />
              <span title={berubah.slice(0, 5).join(", ")}>
                {diperbarui ? t("dash.live.updated", { jam: diperbarui.toLocaleTimeString() }) : ""}
                {berubah.length > 0 && ` · ${t("dash.live.changed", { n: berubah.length })}`}
              </span>
              <button
                type="button"
                onClick={() => setOtomatis((v) => !v)}
                title={otomatis ? t("dash.live.pause") : t("dash.live.resume")}
                className="rounded-md p-1 hover:text-ink"
              >
                {otomatis ? <Pause size={13} /> : <Play size={13} />}
              </button>
            </div>
          }
          className="!p-0"
        >
          <div className="mx-3 mb-3 flex items-start gap-2 rounded-lg p-2.5" style={{ background: "color-mix(in srgb, var(--status-warning) 12%, transparent)", boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--status-warning) 35%, transparent)" }}>
            <Info size={15} className="mt-0.5 shrink-0" style={{ color: "var(--status-warning)" }} />
            <p className="t-small text-ink"><b>{t("tw.virtual.title")}.</b> {t("tw.virtual.body")}</p>
          </div>
          <div className="mx-3 mb-2 flex flex-wrap items-center gap-2">
            <span className="t-small font-semibold uppercase tracking-wide text-muted">{t("tw.layer.title")}</span>
            {URUT_LAPIS.map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLapis(l)}
                aria-pressed={lapis === l}
                className="rounded-lg border px-2.5 py-1 text-xs font-semibold"
                style={{
                  borderColor: lapis === l ? "var(--brand)" : "var(--border)",
                  background: lapis === l ? "color-mix(in srgb, var(--brand) 12%, transparent)" : "var(--surface-1)",
                  color: lapis === l ? "var(--brand)" : "var(--text-secondary)",
                }}
              >
                {t(`tw.layer.${l}`)}
              </button>
            ))}
            {lapis === "umur" && twinData && !twinData.lifetime_available && (
              <span className="t-small" style={{ color: "var(--status-serious)" }}>{t("tw.layer.umur_na")}</span>
            )}
          </div>
          {twin.error ? (
            <div className="p-3"><ErrorBox message={twin.error} /></div>
          ) : !tata ? (
            <div className="p-3"><SkeletonChart height={420} /></div>
          ) : tata.rak.length === 0 ? (
            <div className="p-3"><Empty message={t("tw.empty")} /></div>
          ) : (
            <PanggungTwin tata={tata} pilihan={pilihan} onPilih={pilihFn} rute={rutePicking} tampilPembanding={rutePembanding} />
          )}
        </Card>

        <div className="space-y-4">
          {rakTerpilih ? (
            <DetailRak
              rak={rakTerpilih}
              gudang={namaGudang}
              lapis={lapis}
              horizon={horizon}
              itemId={pilihan?.itemId ?? null}
              onPilihItem={(id) => setPilihan({ rakId: rakTerpilih.id, itemId: id })}
              onTutup={() => setPilihan(null)}
            />
          ) : (
            <Card><p className="t-body text-muted">{t("tw.detail.empty")}</p></Card>
          )}
          <Legenda hitung={hitung} lapis={lapis} horizon={horizon} />
        </div>
      </div>

      {/* ---------- optimasi rute picking ---------- */}
      {twinData && tata && tata.rak.length > 0 && (
        <div className="mt-4">
          <Lipat icon={<Route size={15} />} title={t("pk.title")} subtitle={t("pk.sub")}>
            <PanelPicking
              key={gudangId}
              items={twinData.items}
              tata={tata}
              hasil={rutePicking}
              onHasil={setRutePicking}
              onPilihItem={(rakId, itemId) => setPilihan({ rakId, itemId })}
              tampilPembanding={rutePembanding}
              onTampilPembanding={setRutePembanding}
            />
          </Lipat>
        </div>
      )}

      {/* ---------- tabel: yang perlu ditangani ---------- */}
      <div className="mt-4">
        <Lipat
          icon={<TriangleAlert size={15} />}
          title={t("dash.attention")}
          subtitle={t("dash.attention_sub")}
          right={
            <Link
              href="/reorder"
              className="inline-flex items-center gap-1 text-xs font-semibold"
              style={{ color: "var(--brand)" }}
            >
              {t("dash.attention_all")}
              <ArrowRight size={12} />
            </Link>
          }
        >
          {a.rows.length ? (
            <Table kartuPonsel>
              <thead>
                <tr>
                  <Th>{t("c.item")}</Th>
                  <Th>{t("c.warehouse")}</Th>
                  {/* Judul kolom yang SAMA PERSIS dengan halaman Pemesanan
                      Ulang, karena isinya memang angka yang sama: stok
                      tersedia, dan kebutuhan periode yang dibandingkan mesin
                      terhadapnya di kolom sebelahnya. */}
                  <Th align="right">{t("rl.col.stock")}</Th>
                  <Th align="right">
                    {t("rl.col.forecast", { n: a.rows[0].horizon_days })}
                  </Th>
                  <Th align="right">{t("rl.col.qty")}</Th>
                  <Th>{t("c.status")}</Th>
                </tr>
              </thead>
              <tbody>
                {a.rows.map((r) => (
                  <tr key={`${r.sku}-${r.warehouse_code}`}>
                    <Td>
                      <div className="font-medium text-ink">{r.item_name}</div>
                      <div className="text-xs text-muted">{r.sku}</div>
                    </Td>
                    <Td>{r.warehouse_code}</Td>
                    <Td align="right" numeric>
                      <span
                        className="font-semibold"
                        style={{ color: AKSI[r.status as keyof typeof AKSI]?.warna ?? "var(--text-primary)" }}
                      >
                        {num(r.current_stock)}
                      </span>
                    </Td>
                    <Td align="right" numeric>
                      {r.forecast_usage === null ? (
                        <span className="text-muted">—</span>
                      ) : (
                        num(r.forecast_usage)
                      )}
                    </Td>
                    <Td align="right" numeric>
                      {/* null berarti belum dapat dihitung, bukan nol -- nol
                          akan berbunyi "tidak perlu dipesan". */}
                      {r.recommended_order_qty === null ? (
                        <span className="text-muted">—</span>
                      ) : (
                        <span className="font-semibold text-ink">
                          {num(r.recommended_order_qty)}
                          {r.unit_code ? ` ${r.unit_code}` : ""}
                        </span>
                      )}
                    </Td>
                    <Td>
                      <PillAksi status={r.status} label={r.status_label} padat />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            <Empty message={t("dash.attention_empty")} />
          )}
        </Lipat>
      </div>

      {/* ---------- 3: apa yang diprakirakan terjadi ---------- */}
      {f.horizon_days !== null && (
        <div className="mt-4">
          <Lipat
            icon={<TrendingUp size={15} />}
            title={t("dash.forecast", { n: num(f.horizon_days) })}
            subtitle={t("dash.forecast_sub")}
            right={
              <Link
                href="/forecasting"
                className="inline-flex items-center gap-1 text-xs font-semibold"
                style={{ color: "var(--brand)" }}
              >
                {t("dash.forecast_open")}
                <ArrowRight size={12} />
              </Link>
            }
          >
            <div className="grid gap-5 sm:grid-cols-3">
              <AngkaPrakiraan label={t("dash.forecast.usage")} nilai={num(f.forecast_usage)} />
              <AngkaPrakiraan
                label={t("dash.forecast.qty")}
                nilai={num(f.recommended_order_qty)}
              />
              <AngkaPrakiraan
                label={t("dash.forecast.stockout", { n: num(f.horizon_days) })}
                nilai={num(f.projected_stockout)}
                warna={f.projected_stockout > 0 ? AKSI.RISIKO_STOCKOUT.warna : undefined}
              />
            </div>
            {/* Barang yang belum dapat diprakirakan disebutkan, tidak
                dibulatkan menjadi nol di dalam angka-angka di atas. */}
            {f.without_forecast > 0 && (
              <p className="mt-4 text-xs text-muted">
                {t("dash.forecast.unknown", { n: num(f.without_forecast) })}
              </p>
            )}
          </Lipat>
        </div>
      )}

      {/* ---------- perbandingan antargudang; selalu SEMUA gudang ---------- */}
      <div className="mt-4">
        <Lipat
          icon={<Layers size={15} />}
          title={t("dash.by_warehouse")}
          subtitle={t("dash.by_warehouse_sub")}
          defaultOpen={false}
        >
          {d.stock_by_warehouse.length ? (
            <HBar
              data={d.stock_by_warehouse.map((w) => ({
                label: w.code,
                value: Number(w.total_stock),
                display: `${num(w.total_stock)} ${t("dash.units")} · ${idr(w.stock_value)}`,
              }))}
              height={124}
              labelWidth={84}
              valueWidth={200}
            />
          ) : (
            <Empty message={t("dash.empty_stock")} />
          )}
        </Lipat>
      </div>

      <p className="mt-4 text-xs text-muted">{d.value_basis}</p>
      {(d.truncated || twinData?.truncated) && (
        <p className="mt-1 text-xs" style={{ color: "var(--status-serious)" }}>
          {t("dash.truncated")}
        </p>
      )}
    </>
  );
}

function AngkaPrakiraan({
  label,
  nilai,
  warna,
}: {
  label: string;
  nilai: string;
  warna?: string;
}) {
  return (
    <div>
      <div className="t-micro font-semibold uppercase tracking-[0.07em] text-muted">
        {label}
      </div>
      <div
        className="stat-figure mt-1.5 text-[22px] font-bold leading-none"
        style={{ color: warna ?? "var(--text-primary)" }}
      >
        {nilai}
      </div>
    </div>
  );
}
