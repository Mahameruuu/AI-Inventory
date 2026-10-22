"use client";

/**
 * Halaman masuk dan lupa kata sandi.
 *
 * Masuk memakai USERNAME + kata sandi. Pendaftaran mandiri dicabut pada
 * 22 Oktober 2026: perusahaan baru dibuat orang dalam, dan pengguna baru
 * dibuat admin dari halaman Pengguna.
 *
 * Lupa kata sandi TIDAK lewat email (sistem ini tidak mengirim surat):
 * permintaannya diteruskan ke admin perusahaan, yang menyetel kata sandi baru
 * dari halaman Pengguna. Jawabannya selalu sama, terdaftar atau tidak
 * username-nya, supaya halaman ini tidak bisa dipakai menebak username.
 *
 * Halaman ini TIDAK memakai kerangka aplikasi -- lihat components/Shell.tsx.
 * Sidebar berisi tautan ke halaman yang semuanya menuntut token akan menjadi
 * dinding tautan mati bagi orang yang justru belum punya token.
 */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Eye, EyeOff, KeyRound, ShieldCheck } from "lucide-react";

import { Button, ErrorBox, Field, PesanBerhasil, TextInput } from "@/components/ui";
import { apiPost } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

type Mode = "masuk" | "lupa";

export default function HalamanMasuk() {
  const { t } = useI18n();
  const router = useRouter();
  const { masuk } = useAuth();

  const [mode, setMode] = useState<Mode>("masuk");
  const [username, setUsername] = useState("");
  const [sandi, setSandi] = useState("");
  const [lihatSandi, setLihatSandi] = useState(false);
  const [galat, setGalat] = useState<string | null>(null);
  const [terkirim, setTerkirim] = useState<string | null>(null);
  const [sibuk, setSibuk] = useState(false);

  async function kirimMasuk() {
    if (sibuk) return;
    setGalat(null);
    setSibuk(true);
    try {
      await masuk(username, sandi);
      // replace, bukan push: halaman masuk tidak boleh muncul lagi saat
      // pengguna menekan tombol kembali setelah berhasil masuk.
      router.replace("/");
    } catch (e) {
      setGalat(e instanceof Error ? e.message : String(e));
      setSibuk(false);
    }
  }

  async function kirimLupa() {
    if (sibuk || !username.trim()) return;
    setGalat(null);
    setSibuk(true);
    try {
      const r = await apiPost<{ message: string }>("/api/auth/forgot-password", {
        username: username.trim().toLowerCase(),
      });
      setTerkirim(r.message);
    } catch (e) {
      setGalat(e instanceof Error ? e.message : String(e));
    } finally {
      setSibuk(false);
    }
  }

  function gantiMode(baru: Mode) {
    setMode(baru);
    setGalat(null);
    setTerkirim(null);
  }

  const lupa = mode === "lupa";

  return (
    <div className="flex min-h-[100dvh] items-center justify-center px-4 py-8 sm:px-5 sm:py-10">
      <div className="w-full max-w-[400px]">
        {/* Identitas produk */}
        <div className="mb-7">
          {/* Dua logo mitra dalam kotak yang ukuran dan latarnya sama persis */}
          <div className="flex items-center gap-3">
            {["/logo-sml.svg", "/logo-xorca-dark-text.svg"].map((src) => (
              <span
                key={src}
                className="flex h-12 w-[132px] shrink-0 items-center justify-center rounded-xl bg-white px-3 py-2"
                style={{ boxShadow: "inset 0 0 0 1px var(--border)" }}
                aria-hidden
              >
                <img src={src} alt="" className="h-full w-full object-contain" />
              </span>
            ))}
          </div>
          <div className="mt-4 font-display truncate t-lead font-bold leading-tight text-ink">
            {t("brand.name")}
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
          <h1 className="font-display text-[19px] font-bold leading-tight text-ink">
            {lupa ? t("auth.forgot_title") : t("auth.welcome")}
          </h1>
          <p className="mt-1.5 t-small leading-relaxed text-muted">
            {lupa ? t("auth.forgot_sub") : t("auth.welcome_sub")}
          </p>

          <div className="mt-6 flex flex-col gap-4">
            {lupa && terkirim ? (
              <PesanBerhasil>{terkirim}</PesanBerhasil>
            ) : (
              <>
                <Field label={t("auth.username")}>
                  <TextInput
                    value={username}
                    onChange={setUsername}
                    placeholder="username"
                    autoComplete="username"
                    onEnter={lupa ? kirimLupa : kirimMasuk}
                    className="w-full"
                  />
                </Field>

                {!lupa && (
                  <Field label={t("auth.password")}>
                    <div className="relative">
                      <TextInput
                        type={lihatSandi ? "text" : "password"}
                        value={sandi}
                        onChange={setSandi}
                        placeholder="••••••••••"
                        autoComplete="current-password"
                        onEnter={kirimMasuk}
                        className="w-full pr-11"
                      />
                      <button
                        type="button"
                        onClick={() => setLihatSandi((v) => !v)}
                        aria-label={t(lihatSandi ? "auth.hide_password" : "auth.show_password")}
                        title={t(lihatSandi ? "auth.hide_password" : "auth.show_password")}
                        aria-pressed={lihatSandi}
                        className="absolute inset-y-0 right-0 flex w-11 items-center justify-center rounded-r-lg text-muted transition-colors hover:text-ink"
                      >
                        {lihatSandi ? <EyeOff size={17} aria-hidden /> : <Eye size={17} aria-hidden />}
                      </button>
                    </div>
                  </Field>
                )}

                {galat && <ErrorBox message={galat} />}

                {/* Satu-satunya tombol pada layar ini, dan di ponsel ia ditekan
                    dengan ibu jari: memenuhi lebar kartu, setinggi 44px. */}
                <div className="mt-1">
                  <Button
                    variant="solid"
                    onClick={lupa ? kirimLupa : kirimMasuk}
                    disabled={sibuk || (lupa && !username.trim())}
                    className="h-11 w-full justify-center t-base"
                  >
                    {sibuk ? t("auth.working") : lupa ? t("auth.forgot_send") : t("auth.sign_in")}
                  </Button>
                </div>
              </>
            )}
          </div>

          <div
            className="mt-5 flex items-center gap-2 border-t pt-4 t-caption text-muted"
            style={{ borderColor: "var(--border)" }}
          >
            {lupa ? (
              <button
                type="button"
                onClick={() => gantiMode("masuk")}
                className="flex items-center gap-1.5 font-semibold"
                style={{ color: "var(--brand)" }}
              >
                <ArrowLeft size={13} aria-hidden />
                {t("auth.back_to_login")}
              </button>
            ) : (
              <>
                <ShieldCheck size={13} aria-hidden className="shrink-0" />
                <button
                  type="button"
                  onClick={() => gantiMode("lupa")}
                  className="flex items-center gap-1 font-semibold underline underline-offset-2"
                  style={{ color: "var(--brand)" }}
                >
                  <KeyRound size={12} aria-hidden />
                  {t("auth.forgot_link")}
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
