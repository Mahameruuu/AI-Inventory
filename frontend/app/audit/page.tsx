"use client";

/**
 * Jejak Audit — siapa mengubah apa, kapan, dan nilai sebelumnya.
 *
 * Hanya baca, khusus admin/owner. Barisnya ditulis trigger basis data, jadi
 * tidak ada perubahan yang bisa lolos dari sini, dan tidak ada tombol untuk
 * menyunting atau menghapus jejak.
 */

import { useState } from "react";
import { History } from "lucide-react";

import {
  Badge,
  Card,
  DateInput,
  Empty,
  ErrorBox,
  PageHeader,
  Pager,
  Select,
  SkeletonRows,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useT } from "@/lib/i18n";

const WARNA_AKSI: Record<string, string> = {
  INSERT: "var(--status-good)",
  UPDATE: "var(--status-warning)",
  DELETE: "var(--status-critical)",
};

function nilai(v: unknown): string {
  if (v == null || v === "") return "∅";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function waktu(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Ringkasan perubahan: UPDATE berupa "kolom: lama → baru", lainnya daftar kolom penting. */
function Perubahan({ r }: { r: any }) {
  const t = useT();
  if (r.action === "UPDATE") {
    const kunci = Object.keys(r.new_data ?? {});
    return (
      <ul className="space-y-0.5">
        {kunci.slice(0, 6).map((k) => (
          <li key={k} className="t-small">
            <span className="font-medium text-ink">{k}</span>
            <span className="text-muted">: </span>
            <span className="line-through text-muted">{nilai(r.old_data?.[k])}</span>
            <span className="text-muted"> → </span>
            <span className="text-ink">{nilai(r.new_data[k])}</span>
          </li>
        ))}
        {kunci.length > 6 && (
          <li className="t-caption text-muted">{t("au.more", { n: kunci.length - 6 })}</li>
        )}
      </ul>
    );
  }
  const data = r.new_data ?? r.old_data ?? {};
  const sembunyi = new Set(["id", "company_id", "created_at", "updated_at", "created_by"]);
  const kunci = Object.keys(data).filter((k) => !sembunyi.has(k) && data[k] != null);
  return (
    <details>
      <summary className="cursor-pointer t-small text-muted">
        {t("au.fields", { n: kunci.length })}
      </summary>
      <ul className="mt-1 space-y-0.5">
        {kunci.map((k) => (
          <li key={k} className="t-small">
            <span className="font-medium text-ink">{k}</span>
            <span className="text-muted">: </span>
            {nilai(data[k])}
          </li>
        ))}
      </ul>
    </details>
  );
}

export default function AuditPage() {
  const t = useT();
  const { bolehMengelola } = useAuth();
  const [page, setPage] = useState(1);
  const [tabel, setTabel] = useState("");
  const [aksi, setAksi] = useState("");
  const [pengguna, setPengguna] = useState("");
  const [dari, setDari] = useState("");
  const [sampai, setSampai] = useState("");

  const saringan = useApi<any>(bolehMengelola ? "/api/audit-log/filters" : null);
  const daftar = useApi<any>(bolehMengelola ? "/api/audit-log" : null, {
    table: tabel || undefined,
    action: aksi || undefined,
    user_id: pengguna || undefined,
    date_from: dari || undefined,
    date_to: sampai || undefined,
    page,
    page_size: 25,
  });

  const namaTabel = (n: string) => {
    const k = `au.table.${n}`;
    const s = t(k);
    return s === k ? n : s;
  };

  function setel<T>(fn: (v: T) => void) {
    return (v: T) => {
      fn(v);
      setPage(1);
    };
  }

  return (
    <>
      <PageHeader
        icon={<History size={20} />}
        eyebrow={t("nav.settings")}
        title={t("au.title")}
        description={t("au.desc")}
      />
      {!bolehMengelola ? (
        <ErrorBox message={t("au.forbidden")} />
      ) : daftar.error ? (
        <ErrorBox message={daftar.error} />
      ) : (
        <Card
          icon={<History size={15} />}
          title={t("au.log")}
          dim={daftar.refreshing}
          right={
            <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:flex-wrap">
              <Select
                value={tabel}
                onChange={setel(setTabel)}
                options={[
                  { value: "", label: t("au.all_tables") },
                  ...((saringan.data?.tables ?? []) as string[]).map((x) => ({
                    value: x,
                    label: namaTabel(x),
                  })),
                ]}
              />
              <Select
                value={aksi}
                onChange={setel(setAksi)}
                options={[
                  { value: "", label: t("au.all_actions") },
                  ...["INSERT", "UPDATE", "DELETE"].map((x) => ({
                    value: x,
                    label: t(`au.action.${x}`),
                  })),
                ]}
              />
              <Select
                value={pengguna}
                onChange={setel(setPengguna)}
                options={[
                  { value: "", label: t("au.all_users") },
                  ...((saringan.data?.users ?? []) as any[]).map((u) => ({
                    value: String(u.id),
                    label: u.full_name,
                  })),
                ]}
              />
              <DateInput value={dari} onChange={setel(setDari)} />
              <DateInput value={sampai} onChange={setel(setSampai)} />
            </div>
          }
        >
          {daftar.loading && !daftar.data ? (
            <SkeletonRows rows={8} cols={5} />
          ) : !daftar.data?.items.length ? (
            <Empty message={t("au.empty")} />
          ) : (
            <>
              <Table kartuPonsel>
                <thead>
                  <tr>
                    <Th width="150px">{t("au.when")}</Th>
                    <Th>{t("au.who")}</Th>
                    <Th>{t("au.what")}</Th>
                    <Th>{t("au.changes")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {daftar.data.items.map((r: any) => (
                    <tr key={r.id}>
                      <Td>
                        <span className="tabular-nums t-small">{waktu(r.changed_at)}</span>
                      </Td>
                      <Td>
                        {r.user_name ? (
                          <>
                            <div className="text-ink">{r.user_name}</div>
                            <div className="t-caption text-muted">{r.user_email}</div>
                          </>
                        ) : (
                          <span className="t-small text-muted">{t("au.system")}</span>
                        )}
                      </Td>
                      <Td>
                        <div className="flex flex-wrap items-center gap-1.5">
                          <Badge label={t(`au.action.${r.action}`)} color={WARNA_AKSI[r.action]} />
                          <span className="t-small text-muted">{namaTabel(r.table_name)}</span>
                        </div>
                        <div className="mt-0.5 font-semibold text-ink">
                          {r.label ?? `#${r.row_id}`}
                        </div>
                      </Td>
                      <Td>
                        <Perubahan r={r} />
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pager page={daftar.data.page} pages={daftar.data.pages} onPage={setPage} />
            </>
          )}
        </Card>
      )}
    </>
  );
}
