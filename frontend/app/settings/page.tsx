"use client";

/**
 * Pengaturan / Settings — konfigurasi sistem.
 *
 * Tahap ini hanya menampilkan konfigurasi yang benar-benar berlaku dan bisa
 * diperiksa: alamat API, status koneksi, bahasa, tema tampilan, dan aturan yang
 * sedang dipakai backend. Tidak ada tombol yang tidak melakukan apa-apa.
 */

import { useEffect, useState } from "react";
import { Check, Languages, Palette, Plug, Settings as SettingsIcon, X } from "lucide-react";

import { Badge, Button, Card, PageHeader, Table, Td, Th } from "@/components/ui";
import { apiBase, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function SettingsPage() {
  const { t, lang, setLang } = useI18n();
  const { data, error, loading, reload } = useApi<any>("/api/health");
  const [tema, setTema] = useState("system");
  const [base, setBase] = useState("");

  useEffect(() => {
    setBase(apiBase());
    setTema(localStorage.getItem("theme") ?? "system");
  }, []);

  function ubahTema(nilai: string) {
    setTema(nilai);
    if (nilai === "system") {
      localStorage.removeItem("theme");
      const gelap = window.matchMedia("(prefers-color-scheme: dark)").matches;
      document.documentElement.setAttribute("data-theme", gelap ? "dark" : "light");
    } else {
      localStorage.setItem("theme", nilai);
      document.documentElement.setAttribute("data-theme", nilai);
    }
  }

  return (
    <>
      <PageHeader
        icon={<SettingsIcon size={20} />}
        eyebrow={t("brand.name")}
        title={t("st.title")}
        description={t("st.desc")}
      />

      <div className="grid gap-4 xl:grid-cols-2">
        <Card
          icon={<Plug size={15} />}
          title={t("st.backend")}
          subtitle={t("st.backend_sub")}
        >
          <Table>
            <tbody>
              <tr>
                <Td>{t("st.api_url")}</Td>
                <Td align="right">
                  <code className="text-xs">{base || "—"}</code>
                </Td>
              </tr>
              <tr>
                <Td>{t("c.status")}</Td>
                <Td align="right">
                  {loading ? (
                    <span className="text-muted">{t("st.checking")}</span>
                  ) : error ? (
                    <Badge
                      label={t("st.disconnected")}
                      color="var(--status-critical)"
                      icon={<X size={12} />}
                    />
                  ) : (
                    <Badge
                      label={t("st.connected")}
                      color="var(--status-good)"
                      icon={<Check size={12} />}
                    />
                  )}
                </Td>
              </tr>
              <tr>
                <Td>{t("st.database")}</Td>
                <Td align="right">{data?.database ?? (error ? t("st.unreachable") : "—")}</Td>
              </tr>
            </tbody>
          </Table>
          <div className="mt-3">
            <Button onClick={reload}>{t("c.recheck")}</Button>
          </div>
          {error && (
            <p className="mt-2 text-xs" style={{ color: "var(--status-critical)" }}>
              {error}
            </p>
          )}
          <p className="mt-3 text-xs leading-relaxed text-muted">
            {t("st.api_note_1")} <code>NEXT_PUBLIC_API_URL</code> {t("st.api_note_2")}{" "}
            <code>frontend/.env.local</code>.
          </p>
        </Card>

        <div className="flex flex-col gap-4">
          <Card
            icon={<Languages size={15} />}
            title={t("st.language")}
            subtitle={t("st.language_sub")}
            delay={60}
          >
            <div className="flex gap-2">
              {(
                [
                  { v: "id", l: "Bahasa Indonesia" },
                  { v: "en", l: "English" },
                ] as const
              ).map((o) => (
                <Button
                  key={o.v}
                  variant={lang === o.v ? "solid" : "ghost"}
                  onClick={() => setLang(o.v)}
                >
                  {o.l}
                </Button>
              ))}
            </div>
          </Card>

          <Card
            icon={<Palette size={15} />}
            title={t("st.appearance")}
            subtitle={t("st.appearance_sub")}
            delay={120}
          >
            <div className="flex flex-wrap gap-2">
              {[
                { v: "light", l: t("st.light") },
                { v: "dark", l: t("st.dark") },
                { v: "system", l: t("st.system") },
              ].map((o) => (
                <Button
                  key={o.v}
                  variant={tema === o.v ? "solid" : "ghost"}
                  onClick={() => ubahTema(o.v)}
                >
                  {o.l}
                </Button>
              ))}
            </div>
          </Card>
        </div>
      </div>

      <div className="mt-4">
        <Card title={t("st.rules")} subtitle={t("st.rules_sub")}>
          <Table>
            <thead>
              <tr>
                <Th>{t("st.rule")}</Th>
                <Th>{t("st.rule_value")}</Th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <Td>{t("st.rule_gr")}</Td>
                <Td>
                  <code className="text-xs">GR-YYYYMMDD-NNNN</code>, {t("st.rule_gr_v")}
                </Td>
              </tr>
              <tr>
                <Td>{t("st.rule_iss")}</Td>
                <Td>
                  <code className="text-xs">ISS-YYYYMMDD-NNNN</code>, {t("st.rule_gr_v")}
                </Td>
              </tr>
              <tr>
                <Td>{t("st.rule_low")}</Td>
                <Td>{t("st.rule_low_v")}</Td>
              </tr>
              <tr>
                <Td>{t("st.rule_value_basis")}</Td>
                <Td>{t("st.rule_value_basis_v")}</Td>
              </tr>
              <tr>
                <Td>{t("st.rule_over")}</Td>
                <Td>{t("st.rule_over_v")}</Td>
              </tr>
              <tr>
                <Td>{t("st.rule_atomic")}</Td>
                <Td>{t("st.rule_atomic_v")}</Td>
              </tr>
            </tbody>
          </Table>
        </Card>
      </div>
    </>
  );
}
