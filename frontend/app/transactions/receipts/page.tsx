"use client";

/**
 * Penerimaan Barang / Stock Receipt — daftar penerimaan + formulir pembuatan.
 *
 * Formulir hanya memanggil POST /api/stock-receipts. Stok TIDAK pernah diubah
 * dari sisi frontend; keberhasilan ditentukan sepenuhnya oleh jawaban backend.
 */

import { useState } from "react";
import { ArrowDownToLine, Check, Plus, X } from "lucide-react";

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
import { dateLabel, idr, num } from "@/lib/format";

interface Baris {
  item_id: string;
  quantity: string;
  unit_price: string;
  batch_number: string;
}

const BARIS_KOSONG: Baris = { item_id: "", quantity: "", unit_price: "", batch_number: "" };

export default function StockReceiptPage() {
  const t = useT();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);

  const [warehouseId, setWarehouseId] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [receivedDate, setReceivedDate] = useState(new Date().toISOString().slice(0, 10));
  const [referensi, setReferensi] = useState("");
  const [baris, setBaris] = useState<Baris[]>([{ ...BARIS_KOSONG }]);
  const [kirim, setKirim] = useState(false);
  const [pesan, setPesan] = useState<{ ok: boolean; teks: string } | null>(null);

  const { data: gudang } = useApi<any>("/api/warehouses", { page_size: 200, only_active: true });
  const { data: barang } = useApi<any>("/api/items", { page_size: 200, only_active: true });
  const { data: supplier } = useApi<any>("/api/suppliers", { page_size: 200, only_active: true });
  const daftar = useApi<any>("/api/stock-receipts", { q: q || undefined, page, page_size: 10 });

  function ubahBaris(i: number, patch: Partial<Baris>) {
    setBaris((b) => b.map((x, k) => (k === i ? { ...x, ...patch } : x)));
  }

  async function simpan() {
    setPesan(null);
    setKirim(true);
    try {
      const payload = {
        warehouse_id: Number(warehouseId),
        supplier_id: Number(supplierId),
        received_date: receivedDate,
        reference_number: referensi || null,
        items: baris
          .filter((b) => b.item_id && b.quantity)
          .map((b) => ({
            item_id: Number(b.item_id),
            quantity: Number(b.quantity),
            unit_price: Number(b.unit_price || 0),
            batch_number: b.batch_number || null,
          })),
      };
      const r: any = await apiPost("/api/stock-receipts", payload);
      setPesan({
        ok: true,
        teks: t("rc.saved", {
          no: r.receipt_number,
          lines: r.item_count,
          qty: r.total_quantity,
          value: idr(Number(r.total_value)),
        }),
      });
      setBaris([{ ...BARIS_KOSONG }]);
      setReferensi("");
      daftar.reload();
    } catch (e) {
      setPesan({ ok: false, teks: (e as Error).message });
    } finally {
      setKirim(false);
    }
  }

  const siap =
    warehouseId &&
    supplierId &&
    receivedDate &&
    baris.some((b) => b.item_id && Number(b.quantity) > 0);

  if (daftar.error) return <ErrorBox message={daftar.error} />;

  return (
    <>
      <PageHeader
        icon={<ArrowDownToLine size={20} />}
        eyebrow={t("nav.transactions")}
        title={t("rc.title")}
        description={t("rc.desc")}
      />

      <Section title={t("rc.new")} subtitle={t("rc.new_sub")} defaultOpen>
        <div className="baris-saring flex flex-wrap items-end gap-3">
          <Field label={t("c.warehouse")}>
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
              className="min-w-[210px]"
            />
          </Field>
          <Field label={t("c.supplier")}>
            <Select
              value={supplierId}
              onChange={setSupplierId}
              options={[
                { value: "", label: t("c.select_supplier") },
                ...((supplier?.items ?? []) as any[]).map((s) => ({
                  value: String(s.id),
                  label: `${s.code} — ${s.name}`,
                })),
              ]}
              className="min-w-[190px]"
            />
          </Field>
          <Field label={t("rc.received_date")}>
            <DateInput value={receivedDate} onChange={setReceivedDate} />
          </Field>
          <Field label={t("rc.reference")}>
            <TextInput
              value={referensi}
              onChange={setReferensi}
              placeholder="PO-…"
              className="w-40"
            />
          </Field>
        </div>

        <div className="mt-4">
          <Table kartuPonsel>
            <thead>
              <tr>
                <Th>{t("c.item")}</Th>
                <Th width="120px">{t("c.qty")}</Th>
                <Th width="160px">{t("c.unit_price")}</Th>
                <Th width="140px">{t("c.batch")}</Th>
                <Th width="60px"> </Th>
              </tr>
            </thead>
            <tbody>
              {baris.map((b, i) => (
                <tr key={i}>
                  <Td>
                    <Select
                      value={b.item_id}
                      onChange={(v) => ubahBaris(i, { item_id: v })}
                      options={[
                        { value: "", label: t("c.select_item") },
                        ...((barang?.items ?? []) as any[]).map((it) => ({
                          value: String(it.id),
                          label: `${it.sku} — ${it.name}`,
                        })),
                      ]}
                      className="w-full"
                    />
                  </Td>
                  <Td>
                    <TextInput
                      value={b.quantity}
                      onChange={(v) => ubahBaris(i, { quantity: v })}
                      placeholder="0"
                      className="w-full"
                    />
                  </Td>
                  <Td>
                    <TextInput
                      value={b.unit_price}
                      onChange={(v) => ubahBaris(i, { unit_price: v })}
                      placeholder="0"
                      className="w-full"
                    />
                  </Td>
                  <Td>
                    <TextInput
                      value={b.batch_number}
                      onChange={(v) => ubahBaris(i, { batch_number: v })}
                      placeholder={t("c.optional")}
                      className="w-full"
                    />
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
              ))}
            </tbody>
          </Table>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button onClick={() => setBaris((b) => [...b, { ...BARIS_KOSONG }])}>
            <Plus size={13} />
            {t("c.add_row")}
          </Button>
          <Button variant="solid" onClick={simpan} disabled={!siap || kirim}>
            {kirim ? t("c.saving") : t("rc.save")}
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
          title={t("rc.history")}
          right={
            <TextInput
              value={q}
              onChange={(v) => {
                setQ(v);
                setPage(1);
              }}
              placeholder={t("rc.search")}
              className="w-48"
            />
          }
          dim={daftar.refreshing}
        >
          {daftar.loading && !daftar.data ? (
            <SkeletonRows rows={6} cols={8} />
          ) : !daftar.data?.items.length ? (
            <Empty message={t("rc.empty")} />
          ) : (
            <>
              <Table kartuPonsel>
                <thead>
                  <tr>
                    <Th>{t("c.number")}</Th>
                    <Th>{t("c.date")}</Th>
                    <Th>{t("c.supplier")}</Th>
                    <Th>{t("c.warehouse")}</Th>
                    <Th align="right">{t("c.rows")}</Th>
                    <Th align="right">{t("c.qty")}</Th>
                    <Th align="right">{t("c.value")}</Th>
                    <Th>{t("c.status")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {daftar.data.items.map((r: any) => (
                    <tr key={r.id}>
                      <Td>
                        <span className="font-semibold text-ink">{r.receipt_number}</span>
                        {r.reference_number && (
                          <div className="text-xs text-muted">{r.reference_number}</div>
                        )}
                      </Td>
                      <Td>{dateLabel(r.receipt_date)}</Td>
                      <Td>{r.supplier_name}</Td>
                      <Td>{r.warehouse_code}</Td>
                      <Td align="right" numeric>
                        {num(r.line_count)}
                      </Td>
                      <Td align="right" numeric>
                        {num(r.total_quantity)}
                      </Td>
                      <Td align="right" numeric>
                        {idr(r.total_value)}
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
                onPage={setPage}
              />
            </>
          )}
        </Card>
      </div>
    </>
  );
}
