"use client";

/**
 * AI Inventory Assistant.
 *
 * Halaman ini tidak pernah menyusun angka sendiri: yang ditampilkan hanyalah
 * jawaban backend, ditambah daftar sumber data yang benar-benar dibaca.
 *
 * Identitas mesin di baliknya -- nama model, nama runtime, katalog model yang
 * terpasang -- sengaja TIDAK ditampilkan. Bagi pengguna bisnis detail itu
 * bukan sesuatu yang bisa ditindaklanjuti, dan menampilkannya membuat halaman
 * terlihat seperti alat internal, bukan produk. Diagnosisnya ada di log
 * server, tempat administrator memang mencarinya.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Check,
  Copy,
  Database,
  RotateCw,
  Send,
  Sparkles,
  Trash2,
  TriangleAlert,
} from "lucide-react";

import { apiPost, useApi } from "@/lib/api";
import { useI18n, useT } from "@/lib/i18n";
import { timeLabel } from "@/lib/format";

interface JejakTool {
  tool: string;
  arguments: Record<string, unknown>;
  ok: boolean;
}

interface Jawaban {
  answer: string;
  tool_calls: JejakTool[];
  elapsed_ms: number;
}

interface Pesan {
  peran: "user" | "assistant";
  teks: string;
  waktu: number;
  galat?: boolean;
  jejak?: JejakTool[];
}

interface Kesehatan {
  api_key_configured: boolean;
  connected: boolean;
  model_loaded: boolean;
  message: string;
  tools_available: number;
  write_enabled: boolean;
}

/**
 * Nama tool internal -> nama sumber data yang dikenali pengguna.
 *
 * Jejak tool ditampilkan supaya jawaban bisa ditelusuri asalnya, tetapi
 * "get_low_stock" tidak berarti apa-apa bagi pengguna gudang. Nama yang belum
 * ada di kamus dirapikan seadanya, jadi tool baru tetap tampil wajar tanpa
 * harus menyentuh berkas ini lebih dulu.
 */
function useNamaSumber() {
  const t = useT();
  return (tool: string): string => {
    const kunci = `as.src.${tool}`;
    const teks = t(kunci);
    if (teks !== kunci) return teks;
    const bersih = tool.replace(/^(get|create|update)_/, "").replace(/_/g, " ");
    return bersih.charAt(0).toUpperCase() + bersih.slice(1);
  };
}

/* ------------------------------------------------------------------ *
 * Penyaji teks jawaban
 * ------------------------------------------------------------------ */

/** Sel tabel yang isinya angka -- dipakai untuk merata-kanankan kolomnya. */
const ANGKA = /^[-+]?(rp\s*)?[\d][\d.,]*\s*(%|jt|rb|m|t|unit|pcs|hari)?$/i;

/** Markdown sebaris: **tebal**, *miring*, `kode`. */
function Sebaris({ teks }: { teks: string }) {
  const bagian: React.ReactNode[] = [];
  const pola = /(\*\*[^*]+\*\*|__[^_]+__|`[^`]+`|\*[^*\n]+\*)/g;
  let akhir = 0;
  let k = 0;
  let m: RegExpExecArray | null;

  while ((m = pola.exec(teks)) !== null) {
    if (m.index > akhir) bagian.push(teks.slice(akhir, m.index));
    const s = m[0];
    if (s.startsWith("**") || s.startsWith("__")) {
      bagian.push(
        <strong key={k++} className="font-semibold text-ink">
          {s.slice(2, -2)}
        </strong>
      );
    } else if (s.startsWith("`")) {
      bagian.push(
        <code
          key={k++}
          className="tnum rounded px-1.5 py-0.5 t-small text-ink"
          style={{ background: "var(--gridline)" }}
        >
          {s.slice(1, -1)}
        </code>
      );
    } else {
      bagian.push(<em key={k++}>{s.slice(1, -1)}</em>);
    }
    akhir = m.index + s.length;
  }
  if (akhir < teks.length) bagian.push(teks.slice(akhir));
  return <>{bagian}</>;
}

/** Tabel markdown. Kolom yang seluruh isinya angka dirata-kanankan. */
function Tabel({ mentah }: { mentah: string[] }) {
  const sel = mentah.map((b) =>
    b.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((s) => s.trim())
  );
  // Baris pemisah (|---|---|) bukan data; dibuang sebelum apa pun dibaca.
  const baris = sel.filter((r) => r.length > 0 && !r.every((c) => /^:?-+:?$/.test(c)));
  if (!baris.length) return null;

  const [kepala, ...isi] = baris;
  const kanan = kepala.map(
    (_, k) => isi.length > 0 && isi.every((r) => !r[k] || ANGKA.test(r[k]))
  );

  return (
    <div
      className="my-3 overflow-x-auto rounded-lg border"
      style={{ borderColor: "var(--border)" }}
    >
      <table className="w-full border-collapse t-body">
        <thead>
          <tr style={{ background: "var(--gridline)" }}>
            {kepala.map((h, i) => (
              <th
                key={i}
                className="whitespace-nowrap px-3 py-2 t-caption font-semibold uppercase tracking-wide text-ink-2"
                style={{ textAlign: kanan[i] ? "right" : "left" }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isi.map((r, i) => (
            <tr
              key={i}
              style={{
                borderTop: "1px solid var(--border)",
                background:
                  i % 2 === 1
                    ? "color-mix(in srgb, var(--text-muted) 4%, transparent)"
                    : undefined,
              }}
            >
              {kepala.map((_, k) => (
                <td
                  key={k}
                  className={`px-3 py-2 align-top text-ink-2 ${
                    kanan[k] ? "tnum whitespace-nowrap" : ""
                  }`}
                  style={{ textAlign: kanan[k] ? "right" : "left" }}
                >
                  <Sebaris teks={r[k] ?? ""} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Awal blok baru -- dipakai untuk menghentikan penggabungan paragraf. */
function blokBaru(b: string): boolean {
  return (
    !b ||
    b.startsWith("|") ||
    b.startsWith("```") ||
    b.startsWith(">") ||
    /^#{1,6}\s/.test(b) ||
    /^[-*+•]\s/.test(b) ||
    /^\d+[.)]\s/.test(b)
  );
}

/**
 * Penyaji jawaban model: judul, paragraf, daftar, kutipan, blok kode, dan
 * tabel. Versi sebelumnya membuang penanda **tebal** begitu saja dan
 * menampilkan butir daftar sebagai paragraf berawalan "-", sehingga jawaban
 * panjang terbaca sebagai satu blok datar.
 */
function Isi({ teks }: { teks: string }) {
  const baris = teks.replace(/\r\n/g, "\n").split("\n");
  const keluar: React.ReactNode[] = [];
  let i = 0;
  let kunci = 0;

  while (i < baris.length) {
    const t = baris[i].trim();

    if (!t) {
      i++;
      continue;
    }

    // Blok kode berpagar
    if (t.startsWith("```")) {
      const isi: string[] = [];
      i++;
      while (i < baris.length && !baris[i].trim().startsWith("```")) isi.push(baris[i++]);
      i++;
      keluar.push(
        <pre
          key={kunci++}
          className="my-2 overflow-x-auto rounded-lg px-3 py-2.5 t-small leading-relaxed text-ink-2"
          style={{ background: "var(--gridline)" }}
        >
          {isi.join("\n")}
        </pre>
      );
      continue;
    }

    // Tabel
    if (t.startsWith("|")) {
      const mentah: string[] = [];
      while (i < baris.length && baris[i].trim().startsWith("|")) mentah.push(baris[i++]);
      keluar.push(<Tabel key={kunci++} mentah={mentah} />);
      continue;
    }

    // Garis pemisah
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(t.replace(/\s/g, ""))) {
      keluar.push(
        <hr key={kunci++} className="my-3" style={{ borderColor: "var(--border)" }} />
      );
      i++;
      continue;
    }

    // Judul
    const judul = /^(#{1,6})\s+(.*)$/.exec(t);
    if (judul) {
      const dalam = judul[1].length;
      keluar.push(
        <p
          key={kunci++}
          className={
            dalam <= 2
              ? "mt-3 t-base font-semibold text-ink first:mt-0"
              : "mt-2.5 t-caption font-semibold uppercase tracking-wide text-muted first:mt-0"
          }
        >
          <Sebaris teks={judul[2].replace(/\s*#+\s*$/, "")} />
        </p>
      );
      i++;
      continue;
    }

    // Kutipan
    if (t.startsWith(">")) {
      const isi: string[] = [];
      while (i < baris.length && baris[i].trim().startsWith(">")) {
        isi.push(baris[i++].trim().replace(/^>\s?/, ""));
      }
      keluar.push(
        <blockquote
          key={kunci++}
          className="my-2 border-l-2 pl-3 t-body leading-relaxed text-ink-2"
          style={{ borderColor: "var(--series-1)" }}
        >
          <Sebaris teks={isi.join(" ")} />
        </blockquote>
      );
      continue;
    }

    // Daftar bernomor
    if (/^\d+[.)]\s+/.test(t)) {
      const item: string[] = [];
      while (i < baris.length && /^\d+[.)]\s+/.test(baris[i].trim())) {
        item.push(baris[i++].trim().replace(/^\d+[.)]\s+/, ""));
      }
      keluar.push(
        <ol key={kunci++} className="my-1.5 space-y-1.5">
          {item.map((x, k) => (
            <li key={k} className="flex gap-2.5 t-body leading-relaxed text-ink-2">
              <span className="tnum shrink-0 font-medium text-muted">{k + 1}.</span>
              <span className="min-w-0">
                <Sebaris teks={x} />
              </span>
            </li>
          ))}
        </ol>
      );
      continue;
    }

    // Daftar berbutir
    if (/^[-*+•]\s+/.test(t)) {
      const item: string[] = [];
      while (i < baris.length && /^[-*+•]\s+/.test(baris[i].trim())) {
        item.push(baris[i++].trim().replace(/^[-*+•]\s+/, ""));
      }
      keluar.push(
        <ul key={kunci++} className="my-1.5 space-y-1.5">
          {item.map((x, k) => (
            <li key={k} className="flex gap-2.5 t-body leading-relaxed text-ink-2">
              <span
                aria-hidden
                className="mt-[8px] h-1 w-1 shrink-0 rounded-full"
                style={{ background: "var(--text-muted)" }}
              />
              <span className="min-w-0">
                <Sebaris teks={x} />
              </span>
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // Paragraf: baris berturut-turut digabung jadi satu alinea
    const alinea: string[] = [];
    while (i < baris.length && !blokBaru(baris[i].trim())) alinea.push(baris[i++].trim());
    keluar.push(
      <p key={kunci++} className="t-body leading-relaxed text-ink-2">
        <Sebaris teks={alinea.join(" ")} />
      </p>
    );
  }

  return <div className="space-y-2">{keluar}</div>;
}

/* ------------------------------------------------------------------ *
 * Bagian-bagian tampilan
 * ------------------------------------------------------------------ */

function Avatar({ peran }: { peran: "user" | "assistant" }) {
  const t = useT();
  if (peran === "user") {
    return (
      <span
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full t-micro font-semibold text-ink-2"
        style={{ background: "var(--surface-sunken)" }}
      >
        {t("as.you")}
      </span>
    );
  }
  return (
    <span className="brand-mark flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-white">
      <Sparkles size={14} />
    </span>
  );
}

function TombolSalin({ teks }: { teks: string }) {
  const t = useT();
  const [tersalin, setTersalin] = useState(false);

  useEffect(() => {
    if (!tersalin) return;
    const t = setTimeout(() => setTersalin(false), 1600);
    return () => clearTimeout(t);
  }, [tersalin]);

  return (
    <button
      onClick={() => {
        navigator.clipboard?.writeText(teks).then(() => setTersalin(true)).catch(() => {});
      }}
      title={t("as.copy")}
      aria-label={t("as.copy")}
      className="flex items-center gap-1 rounded-lg px-1.5 py-1 t-caption text-muted transition hover:text-ink-2"
    >
      {tersalin ? <Check size={12} /> : <Copy size={12} />}
      {tersalin ? t("as.copied") : t("as.copy")}
    </button>
  );
}

function Mengetik() {
  return (
    <span className="flex items-center gap-1">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="dot-bounce h-1.5 w-1.5 rounded-full"
          style={{ background: "var(--text-muted)", animationDelay: `${i * 140}ms` }}
        />
      ))}
    </span>
  );
}

/* ------------------------------------------------------------------ *
 * Halaman
 * ------------------------------------------------------------------ */

export default function AssistantPage() {
  const { t, lang } = useI18n();
  const namaSumber = useNamaSumber();
  const [pesan, setPesan] = useState<Pesan[]>([]);
  const [teks, setTeks] = useState("");
  const [sibuk, setSibuk] = useState(false);
  const gulir = useRef<HTMLDivElement>(null);
  const akhir = useRef<HTMLDivElement>(null);
  const kolom = useRef<HTMLTextAreaElement>(null);

  const { data: saran } = useApi<{ suggestions: string[] }>("/api/assistant/suggestions");
  // deep=true membuktikan kredensial benar-benar diterima; katalog model dapat
  // dibaca tanpa kunci, jadi pemeriksaan ringan saja tidak cukup untuk
  // membedakan kunci yang salah.
  const sehat = useApi<Kesehatan>("/api/assistant/health", { deep: true });
  const h = sehat.data;
  const siap = !!h && h.connected && h.model_loaded;
  // Tanpa ini, pemeriksaan yang GAGAL akan menahan lencana pada "Memeriksa"
  // selamanya -- keadaan yang justru paling perlu terlihat.
  const memeriksa = !h && !sehat.error;
  const gangguan = sehat.error ?? (h && !siap ? h.message : null);

  useEffect(() => {
    akhir.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [pesan, sibuk]);

  /** Kolom tumbuh mengikuti isi, sampai batas supaya area percakapan tidak habis. */
  const ukurKolom = useCallback(() => {
    const el = kolom.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, []);

  useEffect(ukurKolom, [teks, ukurKolom]);

  async function tanya(pertanyaan: string) {
    const q = pertanyaan.trim();
    if (!q || sibuk) return;

    // Riwayat yang dikirim hanya percakapan yang berhasil -- pesan galat bukan
    // bagian dari konteks dan hanya akan membingungkan model.
    const riwayat = pesan
      .filter((m) => !m.galat)
      .map((m) => ({ role: m.peran, content: m.teks }));

    setPesan((p) => [...p, { peran: "user", teks: q, waktu: Date.now() }]);
    setTeks("");
    setSibuk(true);
    try {
      const j = await apiPost<Jawaban>("/api/assistant/query", {
        question: q,
        history: riwayat,
        // Bahasa antarmuka, bukan bahasa pertanyaan: satu kata asing di tengah
        // pertanyaan tidak boleh memutar seluruh jawaban ke bahasa lain.
        lang,
      });
      // Waktu respons tidak lagi ditampilkan di bawah jawaban: bagi pengguna
      // angka itu tidak mengubah apa pun, dan menempatkannya di sebelah jam
      // membuat setiap jawaban terlihat sedang diukur kinerjanya. Nilainya
      // tetap dicatat -- di sini untuk penelusuran dari sisi peramban, dan di
      // log server untuk rekaman yang bertahan.
      console.debug(
        `[assistant] jawaban dalam ${(j.elapsed_ms / 1000).toFixed(1)} detik`,
        { elapsed_ms: j.elapsed_ms, tools: j.tool_calls.map((t) => t.tool) }
      );
      setPesan((p) => [
        ...p,
        {
          peran: "assistant",
          teks: j.answer,
          waktu: Date.now(),
          jejak: j.tool_calls,
        },
      ]);
    } catch (e) {
      setPesan((p) => [
        ...p,
        { peran: "assistant", teks: (e as Error).message, waktu: Date.now(), galat: true },
      ]);
      sehat.reload();
    } finally {
      setSibuk(false);
      kolom.current?.focus();
    }
  }

  const contoh = saran?.suggestions ?? [];

  /*
   * `dvh`, BUKAN `vh`. Di peramban ponsel, `100vh` mengukur layar seolah bilah
   * alamatnya sudah tersembunyi -- padahal saat halaman dibuka ia masih
   * terpampang. Selisihnya sekitar 60-90 piksel, dan yang terdorong keluar
   * layar tepat sebesar itu adalah kolom tulis di kaki panel: satu-satunya hal
   * yang dicari orang ketika membuka halaman asisten.
   *
   * Tinggi minimumnya diturunkan dari 34rem menjadi 22rem karena alasan yang
   * sama dari arah sebaliknya: ponsel yang diputar ke lanskap hanya setinggi
   * ~375px, dan lantai setinggi 544px membuat panelnya menjulur jauh melewati
   * layar dengan kolom tulis di ujung yang tak tergapai.
   */
  return (
    <div
      className="surface-card rise flex flex-col overflow-hidden"
      style={{ height: "calc(100dvh - 7.5rem)", minHeight: "22rem" }}
    >
      {/* Kepala panel */}
      <header
        className="flex shrink-0 items-center gap-3 border-b px-4 py-3 sm:px-5 sm:py-3.5"
        style={{ borderColor: "var(--border)" }}
      >
        <span className="brand-mark flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-white sm:h-10 sm:w-10">
          <Sparkles size={18} />
        </span>
        <div className="min-w-0">
          <h1 className="font-display t-lead font-bold leading-tight text-ink">
            {t("as.title")}
          </h1>
          <p className="truncate text-xs text-muted">{t("as.sub")}</p>
        </div>

        {/*
          Tidak ada lencana "Siap" di sini dengan sengaja. Layanan yang
          berjalan normal adalah keadaan bawaan; mengumumkannya sepanjang waktu
          hanya menambah bising dan membuat halaman terasa seperti panel
          pemantauan. Status baru muncul saat ada yang perlu ditindaklanjuti --
          sebagai banner di bawah, lengkap dengan tombol coba lagi.
        */}
        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          <button
            onClick={() => setPesan([])}
            disabled={!pesan.length || sibuk}
            title={t("as.clear")}
            aria-label={t("as.clear")}
            className="flex h-8 w-8 items-center justify-center rounded-lg border text-muted transition hover:text-ink-2 disabled:opacity-35"
            style={{ borderColor: "var(--border)" }}
          >
            <Trash2 size={14} />
          </button>
        </div>
      </header>

      {/*
        Satu-satunya tempat status layanan muncul. Tombol periksa ulang ikut di
        sini, bukan di header: di luar keadaan ini tidak ada yang perlu
        diperiksa, jadi tombolnya pun tidak perlu ada.
      */}
      {gangguan && (
        <div
          className="flex shrink-0 flex-wrap items-start gap-x-3 gap-y-2 border-b px-4 py-3 t-body sm:flex-nowrap sm:px-5"
          style={{
            borderColor: "var(--border)",
            background: "color-mix(in srgb, var(--status-critical) 7%, transparent)",
          }}
        >
          <TriangleAlert
            size={15}
            className="mt-0.5 shrink-0"
            style={{ color: "var(--status-critical)" }}
          />
          <p className="flex-1 text-ink-2">{gangguan}</p>
          <button
            onClick={() => sehat.reload()}
            // Pemeriksaan yang GAGAL tidak menyimpan data, sehingga percobaan
            // berikutnya dilaporkan sebagai `loading`, bukan `refreshing` --
            // keduanya perlu dilihat agar tombolnya benar-benar berputar.
            disabled={sehat.loading || sehat.refreshing}
            className="flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1 t-small font-medium text-ink-2 transition hover:bg-surface disabled:opacity-45"
            style={{ borderColor: "var(--border)" }}
          >
            <RotateCw size={12} className={sehat.loading || sehat.refreshing ? "animate-spin" : undefined} />
            {t("c.retry")}
          </button>
        </div>
      )}

      {/* Percakapan */}
      <div
        ref={gulir}
        className="flex-1 overflow-y-auto overscroll-contain px-4 py-4 sm:px-5 sm:py-5"
      >
        {pesan.length === 0 ? (
          <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center text-center">
            <span className="brand-mark flex h-14 w-14 items-center justify-center rounded-xl text-white">
              <Sparkles size={24} />
            </span>
            <h2 className="font-display mt-4 text-lg font-bold text-ink">{t("as.greet")}</h2>
            <p className="mt-2 t-body leading-relaxed text-ink-2">{t("as.greet_body")}</p>

            {contoh.length > 0 && (
              <div className="mt-6 w-full">
                <p className="mb-2.5 t-micro font-semibold uppercase tracking-[0.09em] text-muted">
                  {t("as.examples")}
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {contoh.map((s) => (
                    <button
                      key={s}
                      onClick={() => tanya(s)}
                      disabled={sibuk || (!memeriksa && !siap)}
                      className="rounded-xl border px-3.5 py-2.5 text-left t-body text-ink-2 transition hover:-translate-y-0.5 hover:border-[color-mix(in_srgb,var(--brand)_35%,transparent)] hover:shadow-e1 disabled:opacity-40"
                      style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="mx-auto max-w-3xl space-y-5">
            {pesan.map((m, i) =>
              m.peran === "user" ? (
                <div key={i} className="flex justify-end">
                  <div className="flex max-w-[85%] flex-col items-end gap-1">
                    <div
                      className="rounded-xl rounded-br-md px-4 py-2.5 t-body leading-relaxed"
                      style={{
                        background: "var(--grad-brand)",
                        color: "#fff",
                        boxShadow: "var(--glow-brand)",
                      }}
                    >
                      {m.teks}
                    </div>
                    <span className="tnum px-1 t-caption text-muted">
                      {timeLabel(m.waktu)}
                    </span>
                  </div>
                </div>
              ) : (
                <div key={i} className="flex gap-2.5">
                  <Avatar peran="assistant" />
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <div
                      className="min-w-0 rounded-xl rounded-tl-md border px-4 py-3"
                      style={{
                        borderColor: m.galat ? "var(--status-critical)" : "var(--border)",
                        background: m.galat
                          ? "color-mix(in srgb, var(--status-critical) 6%, transparent)"
                          : "var(--plane)",
                      }}
                    >
                      {m.galat ? (
                        <p
                          className="t-body leading-relaxed"
                          style={{ color: "var(--status-critical)" }}
                        >
                          {m.teks}
                        </p>
                      ) : (
                        <Isi teks={m.teks} />
                      )}

                      {!!m.jejak?.length && (
                        <div
                          className="mt-3 flex flex-wrap items-center gap-1.5 border-t pt-2.5"
                          style={{ borderColor: "var(--border)" }}
                        >
                          <span className="flex items-center gap-1 t-caption text-muted">
                            <Database size={11} />
                            {t("as.sources")}
                          </span>
                          {m.jejak.map((jejak, k) => (
                            <span
                              key={k}
                              title={jejak.ok ? undefined : t("as.source_failed")}
                              className="rounded-lg px-2 py-0.5 t-caption"
                              style={{
                                background: jejak.ok
                                  ? "var(--surface-sunken)"
                                  : "color-mix(in srgb, var(--status-critical) 12%, transparent)",
                                color: jejak.ok
                                  ? "var(--text-secondary)"
                                  : "var(--status-critical)",
                              }}
                            >
                              {namaSumber(jejak.tool)}
                              {jejak.ok ? "" : t("as.failed_suffix")}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 px-1">
                      <span className="tnum t-caption text-muted">{timeLabel(m.waktu)}</span>
                      {!m.galat && <TombolSalin teks={m.teks} />}
                    </div>
                  </div>
                </div>
              )
            )}

            {sibuk && (
              <div className="flex gap-2.5">
                <Avatar peran="assistant" />
                <div
                  className="flex items-center gap-2.5 rounded-xl rounded-tl-md border px-4 py-3"
                  style={{ borderColor: "var(--border)", background: "var(--plane)" }}
                >
                  <Mengetik />
                  <span className="t-body text-muted">{t("as.searching")}</span>
                </div>
              </div>
            )}

            <div ref={akhir} />
          </div>
        )}
      </div>

      {/* Kolom tulis */}
      <div
        className="shrink-0 border-t px-3 py-3 sm:px-5 sm:py-4"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="mx-auto max-w-3xl">
          <div
            className="composer flex items-end gap-2 rounded-xl border px-3 py-2 transition"
            style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
          >
            <textarea
              ref={kolom}
              value={teks}
              onChange={(e) => setTeks(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  tanya(teks);
                }
              }}
              rows={1}
              disabled={!memeriksa && !siap}
              // Selama status belum diketahui, kolomnya tetap mengajak menulis:
              // pengguna memang sudah boleh mengetik, dan mengumumkan
              // "memeriksa layanan" hanya menonjolkan urusan internal yang
              // biasanya selesai sebelum kalimat pertama diketik.
              placeholder={
                !memeriksa && !siap ? t("as.placeholder_off") : t("as.placeholder")
              }
              className="max-h-40 flex-1 resize-none border-0 bg-transparent py-1.5 t-body leading-relaxed text-ink outline-none placeholder:text-muted disabled:cursor-not-allowed"
            />
            <button
              onClick={() => tanya(teks)}
              disabled={sibuk || !teks.trim()}
              title={t("as.send")}
              aria-label={t("as.send")}
              className="btn-brand mb-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-white transition disabled:opacity-30"
            >
              <Send size={14} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
