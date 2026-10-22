"use client";

/**
 * Stok Opname — hitung fisik, bandingkan dengan sistem, lalu koreksi.
 *
 * Alurnya tiga langkah: buat draft (stok sistem dibekukan), isi hitungan
 * (boleh bertahap, oleh staf), lalu posting (hanya admin/owner). Selisih yang
 * sebenarnya dihitung BACKEND saat posting terhadap stok saat itu; layar ini
 * hanya menampilkan perkiraannya.
 */

import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, Check, ClipboardCheck, Plus, Save, X } from "lucide-react";

import {
  Badge,
  Button,
  Card,
  DialogKonfirmasi,
  Empty,
  ErrorBox,
  Field,
  JendelaFormulir,
  PageHeader,
  Pager,
  PesanBerhasil,
  Select,
  SkeletonRows,
  StatTile,
  Table,
  Td,
  TextInput,
  Th,
} from "@/components/ui";
import { apiPatch, apiPost, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateLabel, idr, num } from "@/lib/format";
import { useT } from "@/lib/i18n";

const WARNA_STATUS: Record<string, string> = {
  draft: "var(--status-warning)",
  completed: "var(--status-good)",
  cancelled: "var(--status-neutral)",
};

function StatusOpname({ status }: { status: string }) {
  const t = useT();
  return (
    <Badge
      label={t(`op.status.${status}`)}
      color={WARNA_STATUS[status] ?? "var(--status-neutral)"}
      icon={status === "completed" ? <Check size={12} /> : undefined}
    />
  );
}

export default function StockOpnamePage() {
  const t = useT();
  const [aktif, setAktif] = useState<number | null>(null);
  const [pesan, setPesan] = useState<string | null>(null);

  return (
    <>
      <PageHeader
        icon={<ClipboardCheck size={20} />}
        eyebrow={t("nav.transactions")}
        title={t("op.title")}
        description={t("op.desc")}
      />
      {pesan && (
        <div className="mb-4">
          <PesanBerhasil>{pesan}</PesanBerhasil>
        </div>
      )}
      {aktif == null ? (
        <DaftarOpname
          onBuka={(id) => {
            setPesan(null);
            setAktif(id);
          }}
        />
      ) : (
        <DetailOpname
          id={aktif}
          onKembali={() => setAktif(null)}
          onSelesai={(teks) => {
            setPesan(teks);
            setAktif(null);
          }}
        />
      )}
    </>
  );
}

function DaftarOpname({ onBuka }: { onBuka: (id: number) => void }) {
  const t = useT();
  const { bolehMencatat } = useAuth();
  const [page, setPage] = useState(1);
  const [formBuka, setFormBuka] = useState(false);
  const [warehouseId, setWarehouseId] = useState("");
  const [catatan, setCatatan] = useState("");
  const [kirim, setKirim] = useState(false);
  const [galat, setGalat] = useState<string | null>(null);

  const { data: gudang } = useApi<any>("/api/warehouses", { page_size: 200, only_active: true });
  const daftar = useApi<any>("/api/stock-opname", { page, page_size: 10 });

  async function mulai() {
    setGalat(null);
    setKirim(true);
    try {
      const r: any = await apiPost("/api/stock-opname", {
        warehouse_id: Number(warehouseId),
        notes: catatan || null,
      });
      setFormBuka(false);
      onBuka(r.id);
    } catch (e) {
      setGalat((e as Error).message);
    } finally {
      setKirim(false);
    }
  }

  if (daftar.error) return <ErrorBox message={daftar.error} />;

  return (
    <>
      <JendelaFormulir
        terbuka={formBuka}
        judul={t("op.start")}
        keterangan={t("op.start_sub")}
        labelTutup={t("md.cancel")}
        onTutup={() => setFormBuka(false)}
        kaki={
          <>
            <Button onClick={() => setFormBuka(false)} disabled={kirim}>
              {t("md.cancel")}
            </Button>
            <Button variant="solid" onClick={mulai} disabled={!warehouseId || kirim}>
              {kirim ? t("c.saving") : t("op.start")}
            </Button>
          </>
        }
      >
        {galat && (
          <div className="mb-4">
            <ErrorBox message={galat} />
          </div>
        )}
        <div className="grid gap-3.5">
          <Field label={t("c.warehouse")} wajib>
            <Select
              value={warehouseId}
              onChange={setWarehouseId}
              options={[
                { value: "", label: t("c.select_warehouse") },
                ...((gudang?.items ?? []) as any[]).map((w) => ({
                  value: String(w.id),
                  label: `${w.code} — ${w.name}`,
                })),
              ]}
              className="w-full"
            />
          </Field>
          <Field label={t("op.notes")}>
            <TextInput
              value={catatan}
              onChange={setCatatan}
              placeholder={`${t("op.notes_ph")} (${t("c.optional")})`}
              className="w-full"
            />
          </Field>
        </div>
      </JendelaFormulir>

      <Card
        icon={<ClipboardCheck size={15} />}
        title={t("op.history")}
        right={
          bolehMencatat && (
            <Button
              variant="solid"
              onClick={() => {
                setGalat(null);
                setFormBuka(true);
              }}
            >
              <Plus size={14} aria-hidden />
              {t("op.start")}
            </Button>
          )
        }
        dim={daftar.refreshing}
      >
        {daftar.loading && !daftar.data ? (
          <SkeletonRows rows={5} cols={6} />
        ) : !daftar.data?.items.length ? (
          <Empty message={t("op.empty")} />
        ) : (
          <>
            <Table kartuPonsel>
              <thead>
                <tr>
                  <Th>{t("c.number")}</Th>
                  <Th>{t("c.date")}</Th>
                  <Th>{t("c.warehouse")}</Th>
                  <Th align="right">{t("op.progress")}</Th>
                  <Th align="right">{t("op.diff_items")}</Th>
                  <Th>{t("op.by")}</Th>
                  <Th>{t("c.status")}</Th>
                </tr>
              </thead>
              <tbody>
                {daftar.data.items.map((r: any) => (
                  <tr key={r.id} className="cursor-pointer" onClick={() => onBuka(r.id)}>
                    <Td>
                      <span className="font-semibold text-ink underline-offset-2 hover:underline">
                        {r.adjustment_number}
                      </span>
                    </Td>
                    <Td>{dateLabel(r.adjustment_date)}</Td>
                    <Td>{r.warehouse_code}</Td>
                    <Td align="right" numeric>
                      {num(r.counted_count)} / {num(r.line_count)}
                    </Td>
                    <Td align="right" numeric>
                      {r.status === "draft" ? "—" : num(r.diff_count)}
                    </Td>
                    <Td>
                      <div>{r.created_by_name ?? "—"}</div>
                      {r.approved_by_name && (
                        <div className="t-caption text-muted">
                          {t("op.approved_by", { nama: r.approved_by_name })}
                        </div>
                      )}
                    </Td>
                    <Td>
                      <StatusOpname status={r.status} />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <Pager page={daftar.data.page} pages={daftar.data.pages} onPage={setPage} />
          </>
        )}
      </Card>
    </>
  );
}

interface Isian {
  qty: string;
  note: string;
}

function DetailOpname({
  id,
  onKembali,
  onSelesai,
}: {
  id: number;
  onKembali: () => void;
  onSelesai: (teks: string) => void;
}) {
  const t = useT();
  const { bolehMengelola, bolehMencatat } = useAuth();
  const detail = useApi<any>(`/api/stock-opname/${id}`);
  const [isian, setIsian] = useState<Record<number, Isian>>({});
  const [kotor, setKotor] = useState<Set<number>>(new Set());
  const [cari, setCari] = useState("");
  const [hanyaBelum, setHanyaBelum] = useState(false);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState<string | null>(null);
  const [tanya, setTanya] = useState<"post" | "cancel" | null>(null);

  const d = detail.data;
  const draft = d?.opname.status === "draft";
  const bisaIsi = draft && bolehMencatat;

  // Isian lokal diisi ulang dari server setiap kali datanya berubah,
  // kecuali baris yang sedang disunting dan belum disimpan.
  useEffect(() => {
    if (!d) return;
    setIsian((lama) => {
      const baru: Record<number, Isian> = {};
      for (const l of d.lines as any[]) {
        baru[l.item_id] = kotor.has(l.item_id)
          ? lama[l.item_id]
          : { qty: l.actual_quantity == null ? "" : String(Number(l.actual_quantity)), note: l.note ?? "" };
      }
      return baru;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d]);

  const baris = useMemo(() => {
    const q = cari.trim().toLowerCase();
    return ((d?.lines ?? []) as any[]).filter(
      (l) =>
        (!q || l.sku.toLowerCase().includes(q) || l.item_name.toLowerCase().includes(q)) &&
        (!hanyaBelum || (isian[l.item_id]?.qty ?? "") === ""),
    );
  }, [d, cari, hanyaBelum, isian]);

  function ubah(itemId: number, patch: Partial<Isian>) {
    setIsian((s) => ({ ...s, [itemId]: { ...s[itemId], ...patch } }));
    setKotor((k) => new Set(k).add(itemId));
  }

  const qtyTidakSah = [...kotor].some((iid) => {
    const v = isian[iid]?.qty ?? "";
    return v !== "" && !(Number(v) >= 0);
  });

  async function simpan() {
    setGalat(null);
    setSibuk(true);
    try {
      await apiPatch(`/api/stock-opname/${id}/lines`, {
        lines: [...kotor].map((iid) => ({
          item_id: iid,
          actual_quantity: isian[iid].qty === "" ? null : Number(isian[iid].qty),
          note: isian[iid].note || null,
        })),
      });
      setKotor(new Set());
      detail.reload();
    } catch (e) {
      setGalat((e as Error).message);
    } finally {
      setSibuk(false);
    }
  }

  async function lanjutkan() {
    const aksi = tanya;
    setTanya(null);
    setGalat(null);
    setSibuk(true);
    try {
      const r: any = await apiPost(`/api/stock-opname/${id}/${aksi}`, {});
      onSelesai(
        aksi === "post"
          ? t("op.posted", { no: r.opname.adjustment_number, n: r.adjusted_count })
          : t("op.cancelled", { no: r.opname.adjustment_number }),
      );
    } catch (e) {
      setGalat((e as Error).message);
    } finally {
      setSibuk(false);
    }
  }

  if (detail.error) return <ErrorBox message={detail.error} />;
  if (!d) return <SkeletonRows rows={8} cols={6} />;

  const s = d.summary;
  const o = d.opname;

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Button onClick={onKembali}>
          <ArrowLeft size={14} aria-hidden />
          {t("op.back")}
        </Button>
        <span className="t-body font-semibold text-ink">{o.adjustment_number}</span>
        <span className="t-small text-muted">
          {o.warehouse_code} — {o.warehouse_name}
        </span>
        <StatusOpname status={o.status} />
      </div>

      {galat && (
        <div className="mb-4">
          <ErrorBox message={galat} />
        </div>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label={t("op.progress")} value={`${num(s.counted_count)} / ${num(s.line_count)}`} />
        <StatTile label={t("op.diff_items")} value={num(s.diff_count)} />
        <StatTile label={t("op.diff_value")} value={idr(s.difference_value)} />
        <StatTile label={t("op.by")} value={o.created_by_name ?? "—"} />
      </div>

      {draft && s.moved_since_draft > 0 && (
        <div
          className="mb-4 rounded-lg px-3.5 py-2.5 t-small"
          style={{
            background: "color-mix(in srgb, var(--status-warning) 12%, transparent)",
            color: "var(--text-primary)",
          }}
        >
          {t("op.moved_warning", { n: s.moved_since_draft })}
        </div>
      )}

      <Card
        icon={<ClipboardCheck size={15} />}
        title={t("op.count_sheet")}
        subtitle={bisaIsi ? t("op.count_sheet_sub") : undefined}
        right={
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <div className="min-w-0 flex-1 sm:w-48 sm:flex-none">
              <TextInput value={cari} onChange={setCari} placeholder={t("op.search")} className="w-full" />
            </div>
            {draft && (
              <label className="flex items-center gap-1.5 t-small text-muted">
                <input
                  type="checkbox"
                  checked={hanyaBelum}
                  onChange={(e) => setHanyaBelum(e.target.checked)}
                />
                {t("op.only_uncounted")}
              </label>
            )}
          </div>
        }
        dim={detail.refreshing}
      >
        {!baris.length ? (
          <Empty message={t("op.no_match")} />
        ) : (
          <Table kartuPonsel>
            <thead>
              <tr>
                <Th>{t("c.item")}</Th>
                <Th align="right">{draft ? t("op.system_now") : t("op.system")}</Th>
                <Th width="130px">{t("op.actual")}</Th>
                <Th align="right">{t("op.diff")}</Th>
                <Th>{t("op.note")}</Th>
              </tr>
            </thead>
            <tbody>
              {baris.map((l: any) => {
                const v = isian[l.item_id] ?? { qty: "", note: "" };
                const sistem = Number(draft ? l.current_quantity : l.system_quantity);
                const beda = v.qty === "" ? null : Number(v.qty) - sistem;
                const warna =
                  beda == null || beda === 0
                    ? undefined
                    : beda < 0
                      ? "var(--status-critical)"
                      : "var(--status-warning)";
                return (
                  <tr key={l.item_id}>
                    <Td>
                      <div className="font-semibold text-ink">{l.sku}</div>
                      <div className="t-caption text-muted">{l.item_name}</div>
                    </Td>
                    <Td align="right" numeric>
                      {num(sistem, 3)} {l.unit_code}
                    </Td>
                    <Td>
                      {bisaIsi ? (
                        <TextInput
                          value={v.qty}
                          onChange={(x) => ubah(l.item_id, { qty: x })}
                          placeholder={t("op.not_counted")}
                          className="w-full"
                        />
                      ) : (
                        <span className="tabular-nums">{v.qty === "" ? "—" : num(v.qty, 3)}</span>
                      )}
                    </Td>
                    <Td align="right" numeric>
                      <span style={{ color: warna, fontWeight: warna ? 600 : undefined }}>
                        {beda == null ? "—" : `${beda > 0 ? "+" : ""}${num(beda, 3)}`}
                      </span>
                    </Td>
                    <Td>
                      {bisaIsi ? (
                        <TextInput
                          value={v.note}
                          onChange={(x) => ubah(l.item_id, { note: x })}
                          placeholder={t("c.optional")}
                          className="w-full"
                        />
                      ) : (
                        <span className="t-small">{v.note || "—"}</span>
                      )}
                      {l.counted_by_name && (
                        <div className="t-caption text-muted">{l.counted_by_name}</div>
                      )}
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>

      {draft && (
        <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
          {kotor.size > 0 && (
            <span className="mr-auto t-small text-muted">{t("op.unsaved", { n: kotor.size })}</span>
          )}
          {bolehMencatat && (
            <Button onClick={() => setTanya("cancel")} disabled={sibuk} color="var(--status-critical)">
              <X size={14} aria-hidden />
              {t("op.cancel")}
            </Button>
          )}
          {bisaIsi && (
            <Button onClick={simpan} disabled={sibuk || kotor.size === 0 || qtyTidakSah}>
              <Save size={14} aria-hidden />
              {sibuk ? t("c.saving") : t("op.save")}
            </Button>
          )}
          {bolehMengelola ? (
            <Button
              variant="solid"
              onClick={() => setTanya("post")}
              disabled={sibuk || kotor.size > 0 || s.counted_count === 0}
              title={kotor.size > 0 ? t("op.save_first") : undefined}
            >
              <Check size={14} aria-hidden />
              {t("op.post")}
            </Button>
          ) : (
            <span className="t-small text-muted">{t("op.need_admin")}</span>
          )}
        </div>
      )}

      <DialogKonfirmasi
        terbuka={tanya != null}
        judul={tanya === "post" ? t("op.post_title") : t("op.cancel_title")}
        pesan={
          tanya === "post"
            ? t("op.post_confirm", { n: s.counted_count, sisa: s.line_count - s.counted_count })
            : t("op.cancel_confirm")
        }
        labelLanjut={tanya === "post" ? t("op.post") : t("op.cancel")}
        labelBatal={t("md.cancel")}
        merusak={tanya === "cancel"}
        sibuk={sibuk}
        onBatal={() => setTanya(null)}
        onLanjut={lanjutkan}
      />
    </>
  );
}
