"use client";

/**
 * Pengeluaran Barang / Stock Issue — daftar pengeluaran + formulir pembuatan.
 *
 * Ketersediaan stok diperiksa BACKEND, bukan di sini. Frontend hanya
 * menampilkan sisa stok sebagai petunjuk; penolakan tetap datang dari API.
 */

import { useState } from "react";
import { ArrowUpFromLine, Check, Plus, X } from "lucide-react";

import {
  Badge,
  Button,
  Card,
  DateInput,
  Empty,
  ErrorBox,
  Field,
  SkeletonRows,
  PageHeader,
  Pager,
  Section,
  Select,
  Table,
  Td,
  Th,
  TextInput,
} from "@/components/ui";
import { apiPost, useApi } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { dateLabel, num } from "@/lib/format";

interface Baris {
  item_id: string;
  quantity: string;
}

const BARIS_KOSONG: Baris = { item_id: "", quantity: "" };

export default function StockIssuePage() {
  const t = useT();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const [warehouseId, setWarehouseId] = useState("");
  const [issueDate, setIssueDate] = useState(new Date().toISOString().slice(0, 10));
  const [keperluan, setKeperluan] = useState("");
  const [referensi, setReferensi] = useState("");
  const [baris, setBaris] = useState<Baris[]>([{ ...BARIS_KOSONG }]);
  const [kirim, setKirim] = useState(false);
  const [pesan, setPesan] = useState<{ ok: boolean; teks: string } | null>(null);

  const { data: gudang } = useApi<any>("/api/warehouses", { page_size: 200, only_active: true });
  // Stok di gudang terpilih dipakai untuk menampilkan sisa pada tiap baris.
  const { data: stok } = useApi<any>(warehouseId ? "/api/inventory" : null, {
    warehouse_id: warehouseId || undefined,
    page_size: 200,
  });
  const daftar = useApi<any>("/api/stock-issues", { q: q || undefined, page, page_size: 10 });

  const stokPerItem: Record<string, any> = Object.fromEntries(
    ((stok?.items ?? []) as any[]).map((r) => [String(r.item_id), r])
  );

  function ubahBaris(i: number, patch: Partial<Baris>) {
    setBaris((b) => b.map((x, k) => (k === i ? { ...x, ...patch } : x)));
  }

  async function simpan() {
    setPesan(null);
    setKirim(true);
    try {
      const payload = {
        warehouse_id: Number(warehouseId),
        issue_date: issueDate,
        purpose: keperluan || null,
        reference_number: referensi || null,
        items: baris
          .filter((b) => b.item_id && b.quantity)
          .map((b) => ({ item_id: Number(b.item_id), quantity: Number(b.quantity) })),
      };
      const r: any = await apiPost("/api/stock-issues", payload);
      const rincian = (r.lines ?? [])
        .map((l: any) => `${l.sku}: ${l.quantity_before} → ${l.quantity_after}`)
        .join(", ");
      setPesan({ ok: true, teks: t("is.saved", { no: r.issue_number, detail: rincian }) });
      setBaris([{ ...BARIS_KOSONG }]);
      setKeperluan("");
      setReferensi("");
      daftar.reload();
    } catch (e) {
      setPesan({ ok: false, teks: (e as Error).message });
    } finally {
      setKirim(false);
    }
  }

  const siap = warehouseId && issueDate && baris.some((b) => b.item_id && Number(b.quantity) > 0);

  if (daftar.error) return <ErrorBox message={daftar.error} />;

  return (
    <>
      <PageHeader
        icon={<ArrowUpFromLine size={20} />}
        eyebrow={t("nav.transactions")}
        title={t("is.title")}
        description={t("is.desc")}
      />

      <Section title={t("is.new")} subtitle={t("rc.new_sub")} defaultOpen>
        <div className="baris-saring flex flex-wrap items-end gap-3">
          <Field label={t("c.warehouse")}>
            <Select
              value={warehouseId}
              onChange={(v) => {
                setWarehouseId(v);
                setBaris([{ ...BARIS_KOSONG }]);
              }}
              options={[
                { value: "", label: t("c.select_warehouse") },
                ...((gudang?.items ?? []) as any[]).map((w) => ({
                  value: String(w.id),
                  label: `${w.code} — ${w.name}`,
                })),
              ]}
              className="min-w-[210px]"
            />
          </Field>
          <Field label={t("is.issue_date")}>
            <DateInput value={issueDate} onChange={setIssueDate} />
          </Field>
          <Field label={t("c.purpose")}>
            <TextInput
              value={keperluan}
              onChange={setKeperluan}
              placeholder={t("is.purpose_ph")}
              className="w-52"
            />
          </Field>
          <Field label={t("rc.reference")}>
            <TextInput
              value={referensi}
              onChange={setReferensi}
              placeholder="WO-…"
              className="w-40"
            />
          </Field>
        </div>

        {!warehouseId ? (
          <p className="mt-4 text-sm text-muted">{t("is.pick_wh_first")}</p>
        ) : (
          <div className="mt-4">
            <Table kartuPonsel>
              <thead>
                <tr>
                  <Th>{t("c.item")}</Th>
                  <Th align="right" width="130px">
                    {t("c.available")}
                  </Th>
                  <Th width="120px">{t("c.qty")}</Th>
                  <Th width="60px"> </Th>
                </tr>
              </thead>
              <tbody>
                {baris.map((b, i) => {
                  const s = stokPerItem[b.item_id];
                  const lebih = s && Number(b.quantity) > Number(s.available_quantity);
                  return (
                    <tr key={i}>
                      <Td>
                        <Select
                          value={b.item_id}
                          onChange={(v) => ubahBaris(i, { item_id: v })}
                          options={[
                            { value: "", label: t("c.select_item") },
                            ...((stok?.items ?? []) as any[]).map((it) => ({
                              value: String(it.item_id),
                              label: `${it.sku} — ${it.item_name}`,
                            })),
                          ]}
                          className="w-full"
                        />
                      </Td>
                      <Td align="right" numeric>
                        {s ? `${num(s.available_quantity)} ${s.unit_code}` : "—"}
                      </Td>
                      <Td>
                        <TextInput
                          value={b.quantity}
                          onChange={(v) => ubahBaris(i, { quantity: v })}
                          placeholder="0"
                          className="w-full"
                        />
                        {lebih && (
                          <div
                            className="mt-1 t-caption font-medium"
                            style={{ color: "var(--status-critical)" }}
                          >
                            {t("is.over_stock")}
                          </div>
                        )}
                      </Td>
                      <Td>
                        {baris.length > 1 && (
                          <Button
                            title={t("c.remove_row")}
                            onClick={() => setBaris((x) => x.filter((_, k) => k !== i))}
                          >
                            <X size={13} />
                          </Button>
                        )}
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          </div>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button
            onClick={() => setBaris((b) => [...b, { ...BARIS_KOSONG }])}
            disabled={!warehouseId}
          >
            <Plus size={13} />
            {t("c.add_row")}
          </Button>
          <Button variant="solid" onClick={simpan} disabled={!siap || kirim}>
            {kirim ? t("c.saving") : t("is.save")}
          </Button>
          {pesan && (
            <span
              className="text-sm font-medium"
              style={{ color: pesan.ok ? "var(--status-good)" : "var(--status-critical)" }}
            >
              {pesan.teks}
            </span>
          )}
        </div>
      </Section>

      <div className="mt-4">
        <Card
          title={t("is.history")}
          right={
            <TextInput
              value={q}
              onChange={(v) => {
                setQ(v);
                setPage(1);
              }}
              placeholder={t("is.search")}
              className="w-56"
            />
          }
          dim={daftar.refreshing}
        >
          {daftar.loading && !daftar.data ? (
            <SkeletonRows rows={6} cols={7} />
          ) : !daftar.data?.items.length ? (
            <Empty message={t("is.empty")} />
          ) : (
            <>
              <Table kartuPonsel>
                <thead>
                  <tr>
                    <Th>{t("c.number")}</Th>
                    <Th>{t("c.date")}</Th>
                    <Th>{t("c.warehouse")}</Th>
                    <Th>{t("c.purpose")}</Th>
                    <Th align="right">{t("c.rows")}</Th>
                    <Th align="right">{t("c.qty")}</Th>
                    <Th>{t("c.status")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {daftar.data.items.map((r: any) => (
                    <tr key={r.id}>
                      <Td>
                        <span className="font-semibold text-ink">{r.issue_number}</span>
                        {r.reference_number && (
                          <div className="text-xs text-muted">{r.reference_number}</div>
                        )}
                      </Td>
                      <Td>{dateLabel(r.issue_date)}</Td>
                      <Td>{r.warehouse_code}</Td>
                      <Td>{r.purpose ?? "—"}</Td>
                      <Td align="right" numeric>
                        {num(r.line_count)}
                      </Td>
                      <Td align="right" numeric>
                        {num(r.total_quantity)}
                      </Td>
                      <Td>
                        <Badge
                          label={r.status}
                          color="var(--status-good)"
                          icon={<Check size={12} />}
                        />
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pager
                page={daftar.data.page}
                pages={daftar.data.pages}
                total={daftar.data.total}
                label={t("is.label")}
                onPage={setPage}
              />
            </>
          )}
        </Card>
      </div>
    </>
  );
}
