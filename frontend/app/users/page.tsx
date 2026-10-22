"use client";

/**
 * Pengguna — siapa yang boleh masuk ke perusahaan ini, dan sebatas apa.
 *
 * Khusus admin/owner. Sejak pendaftaran mandiri dicabut (22 Oktober 2026),
 * inilah satu-satunya pintu menambah pengguna, dan juga tempat menangani
 * permintaan "lupa kata sandi" yang dikirim dari halaman masuk.
 */

import { useState } from "react";
import { KeyRound, Plus, Users, X } from "lucide-react";

import {
  Badge,
  Button,
  Card,
  Empty,
  ErrorBox,
  Field,
  JendelaFormulir,
  PageHeader,
  PesanBerhasil,
  Select,
  SkeletonRows,
  Table,
  Td,
  TextInput,
  Th,
} from "@/components/ui";
import { apiPatch, apiPost, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { dateLabel } from "@/lib/format";
import { useT } from "@/lib/i18n";

const PERAN = ["admin", "staff", "viewer"] as const;

interface Sasaran {
  id: number;
  username: string;
  full_name: string;
}

export default function UsersPage() {
  const t = useT();
  const { pengguna, bolehMengelola } = useAuth();
  const daftar = useApi<any>(bolehMengelola ? "/api/users" : null, { page_size: 200 });
  const permintaan = useApi<any>(bolehMengelola ? "/api/users/reset-requests" : null);

  const [pesan, setPesan] = useState<string | null>(null);
  const [galat, setGalat] = useState<string | null>(null);

  // --- tambah pengguna ---
  const [tambahBuka, setTambahBuka] = useState(false);
  const [baru, setBaru] = useState({ username: "", full_name: "", email: "", password: "", role: "staff" });
  // --- setel sandi ---
  const [sasaran, setSasaran] = useState<Sasaran | null>(null);
  const [sandiBaru, setSandiBaru] = useState("");
  const [sibuk, setSibuk] = useState(false);
  const [galatForm, setGalatForm] = useState<string | null>(null);

  function muatUlang() {
    daftar.reload();
    permintaan.reload();
  }

  async function jalankan(fn: () => Promise<unknown>, berhasil: string, onForm = false) {
    setSibuk(true);
    setGalat(null);
    setGalatForm(null);
    try {
      await fn();
      setPesan(berhasil);
      muatUlang();
      return true;
    } catch (e) {
      (onForm ? setGalatForm : setGalat)((e as Error).message);
      return false;
    } finally {
      setSibuk(false);
    }
  }

  async function simpanBaru() {
    const ok = await jalankan(
      () =>
        apiPost("/api/users", {
          username: baru.username.trim().toLowerCase(),
          full_name: baru.full_name,
          email: baru.email || null,
          password: baru.password,
          role: baru.role,
        }),
      t("us.created"),
      true,
    );
    if (ok) {
      setTambahBuka(false);
      setBaru({ username: "", full_name: "", email: "", password: "", role: "staff" });
    }
  }

  async function simpanSandi() {
    if (!sasaran) return;
    const ok = await jalankan(
      () => apiPost(`/api/users/${sasaran.id}/reset-password`, { new_password: sandiBaru }),
      t("us.reset_done", { nama: sasaran.full_name }),
      true,
    );
    if (ok) {
      setSasaran(null);
      setSandiBaru("");
    }
  }

  if (!bolehMengelola) {
    return (
      <>
        <PageHeader icon={<Users size={20} />} eyebrow={t("nav.settings")} title={t("us.title")} />
        <ErrorBox message={t("us.forbidden")} />
      </>
    );
  }

  const menunggu = (permintaan.data?.items ?? []) as any[];
  const siapBaru =
    /^[a-z0-9._-]{3,50}$/.test(baru.username.trim().toLowerCase()) &&
    baru.full_name.trim().length >= 2 &&
    baru.password.length >= 10;

  return (
    <>
      <PageHeader
        icon={<Users size={20} />}
        eyebrow={t("nav.settings")}
        title={t("us.title")}
        description={t("us.desc")}
      />

      {pesan && (
        <div className="mb-4">
          <PesanBerhasil>{pesan}</PesanBerhasil>
        </div>
      )}
      {galat && (
        <div className="mb-4">
          <ErrorBox message={galat} />
        </div>
      )}

      {menunggu.length > 0 && (
        <div className="mb-4">
          <Card
            icon={<KeyRound size={15} />}
            title={t("us.reset_requests", { n: menunggu.length })}
            subtitle={t("us.reset_requests_sub")}
          >
            <Table kartuPonsel>
              <thead>
                <tr>
                  <Th>{t("us.name")}</Th>
                  <Th>{t("us.requested_at")}</Th>
                  <Th width="260px"> </Th>
                </tr>
              </thead>
              <tbody>
                {menunggu.map((r) => (
                  <tr key={r.id}>
                    <Td>
                      <div className="font-semibold text-ink">{r.full_name}</div>
                      <div className="t-caption text-muted">@{r.username}</div>
                    </Td>
                    <Td>{dateLabel(r.requested_at)}</Td>
                    <Td>
                      <div className="flex flex-wrap justify-end gap-2">
                        <Button
                          onClick={() =>
                            jalankan(
                              () => apiPost(`/api/users/reset-requests/${r.id}/dismiss`, {}),
                              t("us.dismissed"),
                            )
                          }
                          disabled={sibuk}
                        >
                          <X size={13} aria-hidden />
                          {t("us.dismiss")}
                        </Button>
                        <Button
                          variant="solid"
                          onClick={() => {
                            setGalatForm(null);
                            setSandiBaru("");
                            setSasaran({ id: r.user_id, username: r.username, full_name: r.full_name });
                          }}
                        >
                          <KeyRound size={13} aria-hidden />
                          {t("us.set_password")}
                        </Button>
                      </div>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>
        </div>
      )}

      <Card
        icon={<Users size={15} />}
        title={t("us.list")}
        subtitle={t("us.list_sub")}
        dim={daftar.refreshing}
        right={
          <Button
            variant="solid"
            onClick={() => {
              setGalatForm(null);
              setTambahBuka(true);
            }}
          >
            <Plus size={14} aria-hidden />
            {t("us.add")}
          </Button>
        }
      >
        {daftar.error ? (
          <ErrorBox message={daftar.error} />
        ) : daftar.loading && !daftar.data ? (
          <SkeletonRows rows={4} cols={5} />
        ) : !daftar.data?.items.length ? (
          <Empty message={t("md.empty")} />
        ) : (
          <Table kartuPonsel>
            <thead>
              <tr>
                <Th>{t("us.name")}</Th>
                <Th>{t("us.role")}</Th>
                <Th>{t("us.status")}</Th>
                <Th>{t("us.last_login")}</Th>
                <Th width="230px"> </Th>
              </tr>
            </thead>
            <tbody>
              {(daftar.data.items as any[]).map((u) => {
                const diriSendiri = u.id === pengguna?.id;
                const terkunci = u.role === "owner" || diriSendiri;
                return (
                  <tr key={u.id}>
                    <Td>
                      <div className="font-semibold text-ink">
                        {u.full_name}
                        {diriSendiri && <span className="ml-1.5 t-caption text-muted">({t("us.you")})</span>}
                      </div>
                      <div className="t-caption text-muted">
                        @{u.username}
                        {u.email ? ` · ${u.email}` : ""}
                      </div>
                      {u.reset_pending && (
                        <div className="mt-1">
                          <Badge label={t("us.reset_pending")} color="var(--status-warning)" />
                        </div>
                      )}
                    </Td>
                    <Td>
                      {terkunci ? (
                        <span title={u.role === "owner" ? t("us.owner_locked") : undefined}>
                          {t(`auth.role.${u.role}`)}
                        </span>
                      ) : (
                        <Select
                          value={u.role}
                          onChange={(v) =>
                            jalankan(() => apiPatch(`/api/users/${u.id}`, { role: v }), t("us.updated"))
                          }
                          options={PERAN.map((p) => ({ value: p, label: t(`auth.role.${p}`) }))}
                        />
                      )}
                    </Td>
                    <Td>
                      <Badge
                        label={u.is_active ? t("us.active") : t("us.inactive")}
                        color={u.is_active ? "var(--status-good)" : "var(--status-neutral)"}
                      />
                    </Td>
                    <Td>{u.last_login_at ? dateLabel(u.last_login_at) : t("us.never")}</Td>
                    <Td>
                      <div className="flex flex-wrap justify-end gap-2">
                        <Button
                          onClick={() => {
                            setGalatForm(null);
                            setSandiBaru("");
                            setSasaran({ id: u.id, username: u.username, full_name: u.full_name });
                          }}
                        >
                          <KeyRound size={13} aria-hidden />
                          {t("us.set_password")}
                        </Button>
                        {!terkunci && (
                          <Button
                            color={u.is_active ? "var(--status-critical)" : undefined}
                            disabled={sibuk}
                            onClick={() =>
                              jalankan(
                                () => apiPatch(`/api/users/${u.id}`, { is_active: !u.is_active }),
                                t("us.updated"),
                              )
                            }
                          >
                            {u.is_active ? t("us.deactivate") : t("us.activate")}
                          </Button>
                        )}
                      </div>
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        )}
      </Card>

      {/* --- tambah pengguna --- */}
      <JendelaFormulir
        terbuka={tambahBuka}
        judul={t("us.add")}
        keterangan={t("us.add_sub")}
        labelTutup={t("md.cancel")}
        onTutup={() => setTambahBuka(false)}
        kaki={
          <>
            <Button onClick={() => setTambahBuka(false)} disabled={sibuk}>
              {t("md.cancel")}
            </Button>
            <Button variant="solid" onClick={simpanBaru} disabled={!siapBaru || sibuk}>
              {sibuk ? t("c.saving") : t("us.save")}
            </Button>
          </>
        }
      >
        {galatForm && (
          <div className="mb-4">
            <ErrorBox message={galatForm} />
          </div>
        )}
        <div className="grid gap-3.5 sm:grid-cols-2">
          <Field label={t("auth.username")} wajib>
            <TextInput
              value={baru.username}
              onChange={(v) => setBaru({ ...baru, username: v })}
              placeholder="budi.santoso"
              autoComplete="off"
              className="w-full"
            />
          </Field>
          <Field label={t("auth.full_name")} wajib>
            <TextInput
              value={baru.full_name}
              onChange={(v) => setBaru({ ...baru, full_name: v })}
              placeholder="Budi Santoso"
              className="w-full"
            />
          </Field>
          <Field label={t("auth.password")} wajib>
            <TextInput
              type="password"
              value={baru.password}
              onChange={(v) => setBaru({ ...baru, password: v })}
              autoComplete="new-password"
              className="w-full"
            />
          </Field>
          <Field label={t("us.role")} wajib>
            <Select
              value={baru.role}
              onChange={(v) => setBaru({ ...baru, role: v })}
              options={PERAN.map((p) => ({ value: p, label: t(`auth.role.${p}`) }))}
              className="w-full"
            />
          </Field>
          <Field label={`${t("auth.email")} (${t("c.optional")})`}>
            <TextInput
              type="email"
              value={baru.email}
              onChange={(v) => setBaru({ ...baru, email: v })}
              placeholder="budi@perusahaan.co.id"
              className="w-full"
            />
          </Field>
        </div>
        <p className="mt-3 t-caption text-muted">{t("us.username_hint")}</p>
        <p className="mt-1 t-caption text-muted">{t("auth.password_hint")}</p>
        <p className="mt-1 t-caption text-muted">{t("us.role.admin_help")}</p>
      </JendelaFormulir>

      {/* --- setel kata sandi baru --- */}
      <JendelaFormulir
        terbuka={sasaran != null}
        judul={t("us.set_password")}
        keterangan={sasaran ? t("us.set_password_sub", { nama: sasaran.full_name, username: sasaran.username }) : ""}
        labelTutup={t("md.cancel")}
        onTutup={() => setSasaran(null)}
        kaki={
          <>
            <Button onClick={() => setSasaran(null)} disabled={sibuk}>
              {t("md.cancel")}
            </Button>
            <Button variant="solid" onClick={simpanSandi} disabled={sandiBaru.length < 10 || sibuk}>
              {sibuk ? t("c.saving") : t("us.save")}
            </Button>
          </>
        }
      >
        {galatForm && (
          <div className="mb-4">
            <ErrorBox message={galatForm} />
          </div>
        )}
        <Field label={t("us.new_password")} wajib>
          <TextInput
            type="password"
            value={sandiBaru}
            onChange={setSandiBaru}
            autoComplete="new-password"
            className="w-full"
          />
        </Field>
        <p className="mt-2 t-caption text-muted">{t("auth.password_hint")}</p>
      </JendelaFormulir>
    </>
  );
}
