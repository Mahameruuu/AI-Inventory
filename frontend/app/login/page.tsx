"use client";

/**
 * Halaman masuk dan pendaftaran perusahaan.
 *
 * SATU HALAMAN, DUA MODE. Masuk dan mendaftar dipisahkan tab, bukan dua alamat
 * berbeda: orang yang salah memilih dapat berpindah tanpa kehilangan apa yang
 * sudah diketik pada kolom yang sama-sama dipakai keduanya.
 *
 * Halaman ini TIDAK memakai kerangka aplikasi -- lihat components/Shell.tsx.
 * Sidebar berisi tautan ke halaman yang semuanya menuntut token akan menjadi
 * dinding tautan mati bagi orang yang justru belum punya token.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { LogIn, ShieldCheck, UserPlus } from "lucide-react";

import { Button, ErrorBox, Field, TextInput } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

type Mode = "masuk" | "daftar";

export default function HalamanMasuk() {
  const { t } = useI18n();
  const router = useRouter();
  const { masuk, daftar } = useAuth();

  const [mode, setMode] = useState<Mode>("masuk");
  const [email, setEmail] = useState("");
  const [sandi, setSandi] = useState("");
  const [nama, setNama] = useState("");
  const [perusahaan, setPerusahaan] = useState("");
  const [galat, setGalat] = useState<string | null>(null);
  const [sibuk, setSibuk] = useState(false);

  async function kirim() {
    if (sibuk) return;
    setGalat(null);
    setSibuk(true);
    try {
      if (mode === "masuk") {
        await masuk(email, sandi);
      } else {
        await daftar({
          company_name: perusahaan,
          full_name: nama,
          email,
          password: sandi,
        });
      }
      // replace, bukan push: halaman masuk tidak boleh muncul lagi saat
      // pengguna menekan tombol kembali setelah berhasil masuk.
      router.replace("/");
    } catch (e) {
      setGalat(e instanceof Error ? e.message : String(e));
      setSibuk(false);
    }
  }

  function gantiMode(baru: Mode) {
    setMode(baru);
    setGalat(null);
  }

  const daftarMode = mode === "daftar";

  return (
    <div className="flex min-h-[100dvh] items-center justify-center px-4 py-8 sm:px-5 sm:py-10">
      <div className="w-full max-w-[400px]">
        {/* Identitas produk, disamakan dengan kepala sidebar */}
        <div className="mb-7 flex items-center gap-3">
          <span
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white p-1.5"
            aria-hidden
          >
            <img src="/logo-sml.svg" alt="" className="h-full w-full object-contain" />
          </span>
          <div className="min-w-0">
            <div className="font-display truncate t-lead font-bold leading-tight text-ink">
              {t("brand.name")}
            </div>
            <div className="truncate t-micro font-medium uppercase tracking-[0.09em] text-muted">
              {t("brand.tagline")}
            </div>
          </div>
        </div>

        <div
          className="rounded-xl border p-5 sm:p-6"
          style={{
            borderColor: "var(--border)",
            background: "var(--surface-1)",
            boxShadow: "0 18px 40px -28px rgba(0,0,0,0.45)",
          }}
        >
          {/* Pemilih mode */}
          <div
            className="mb-6 grid grid-cols-2 gap-1 rounded-xl p-1"
            style={{ background: "color-mix(in srgb, var(--border) 45%, transparent)" }}
          >
            {([
              ["masuk", t("auth.sign_in"), LogIn],
              ["daftar", t("auth.sign_up"), UserPlus],
            ] as const).map(([nilai, label, Icon]) => (
              <button
                key={nilai}
                type="button"
                onClick={() => gantiMode(nilai)}
                className="flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 t-small transition"
                style={{
                  background: mode === nilai ? "var(--surface-1)" : "transparent",
                  color: mode === nilai ? "var(--ink)" : "var(--muted)",
                  fontWeight: mode === nilai ? 600 : 500,
                  boxShadow:
                    mode === nilai ? "0 1px 3px rgba(0,0,0,0.12)" : "none",
                }}
              >
                <Icon size={14} aria-hidden />
                {label}
              </button>
            ))}
          </div>

          <h1 className="font-display text-[19px] font-bold leading-tight text-ink">
            {daftarMode ? t("auth.signup_title") : t("auth.welcome")}
          </h1>
          <p className="mt-1.5 t-small leading-relaxed text-muted">
            {daftarMode ? t("auth.signup_sub") : t("auth.welcome_sub")}
          </p>

          <div className="mt-6 flex flex-col gap-4">
            {daftarMode && (
              <>
                <Field label={t("auth.company_name")}>
                  <TextInput
                    value={perusahaan}
                    onChange={setPerusahaan}
                    placeholder="PT Contoh Sejahtera"
                    autoComplete="organization"
                    className="w-full"
                  />
                </Field>
                <Field label={t("auth.full_name")}>
                  <TextInput
                    value={nama}
                    onChange={setNama}
                    placeholder="Nama Anda"
                    autoComplete="name"
                    className="w-full"
                  />
                </Field>
              </>
            )}

            <Field label={t("auth.email")}>
              <TextInput
                type="email"
                value={email}
                onChange={setEmail}
                placeholder="nama@perusahaan.co.id"
                autoComplete="username"
                onEnter={kirim}
                className="w-full"
              />
            </Field>

            <Field label={t("auth.password")}>
              <TextInput
                type="password"
                value={sandi}
                onChange={setSandi}
                placeholder="••••••••••"
                autoComplete={daftarMode ? "new-password" : "current-password"}
                onEnter={kirim}
                className="w-full"
              />
            </Field>
            {daftarMode && (
              <p className="-mt-2 t-caption text-muted">{t("auth.password_hint")}</p>
            )}

            {galat && <ErrorBox message={galat} />}

            {/* Satu-satunya tombol pada layar ini, dan di ponsel ia ditekan
                dengan ibu jari: memenuhi lebar kartu, setinggi 44px. */}
            <div className="mt-1">
              <Button
                variant="solid"
                onClick={kirim}
                disabled={sibuk}
                className="h-11 w-full justify-center t-base"
              >
                {sibuk
                  ? t("auth.working")
                  : daftarMode
                    ? t("auth.sign_up")
                    : t("auth.sign_in")}
              </Button>
            </div>
          </div>

          <div className="mt-5 flex items-center gap-2 border-t pt-4 t-caption text-muted"
               style={{ borderColor: "var(--border)" }}>
            <ShieldCheck size={13} aria-hidden className="shrink-0" />
            <span>
              {daftarMode ? t("auth.have_account") : t("auth.no_account")}{" "}
              <button
                type="button"
                onClick={() => gantiMode(daftarMode ? "masuk" : "daftar")}
                className="font-semibold underline underline-offset-2"
                style={{ color: "var(--brand)" }}
              >
                {daftarMode ? t("auth.sign_in") : t("auth.sign_up")}
              </button>
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
