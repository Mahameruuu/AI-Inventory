"use client";

/**
 * Pemandu demo: kartu langkah demi langkah yang menggerakkan state tampilan
 * dasbor (lapisan, pilihan rak, contoh pesanan, rute, skenario). Hanya muncul
 * pada tenant demo (perusahaan.is_demo) dan TIDAK menulis apa pun: semua yang
 * dijalankannya adalah state di browser.
 */

import { ChevronLeft, ChevronRight, FlaskConical, X } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui";
import { useT } from "@/lib/i18n";

export const JUMLAH_LANGKAH = 9;

export default function PanduDemo({
  langkah, onLangkah, onKeluar, info,
}: {
  langkah: number;
  onLangkah: (n: number) => void;
  onKeluar: () => void;
  /** baris angka hidup untuk langkah ini (diambil dari hasil sebenarnya) */
  info: string[];
}) {
  const t = useT();
  useEffect(() => {
    const tombol = (e: KeyboardEvent) => {
      if (e.key === "Escape") onKeluar();
      else if (e.key === "ArrowRight") onLangkah(Math.min(JUMLAH_LANGKAH - 1, langkah + 1));
      else if (e.key === "ArrowLeft") onLangkah(Math.max(0, langkah - 1));
    };
    window.addEventListener("keydown", tombol);
    return () => window.removeEventListener("keydown", tombol);
  }, [langkah, onLangkah, onKeluar]);
  const akhir = langkah === JUMLAH_LANGKAH - 1;
  // Portal ke body: pembungkus halaman memakai transform (animasi masuk), yang membuat
  // position:fixed relatif terhadap pembungkus itu, bukan jendela.
  const [siap, setSiap] = useState(false);
  useEffect(() => setSiap(true), []);
  if (!siap) return null;
  return createPortal(
    <div
      role="dialog"
      aria-label={t("dm.start")}
      className="fixed bottom-4 right-4 z-[1200] w-[min(420px,calc(100vw-2rem))] rounded-2xl p-4"
      style={{ background: "var(--surface-1)", boxShadow: "0 0 0 1px var(--border-strong), 0 12px 40px rgba(13,21,38,.28)" }}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="rounded-md px-2 py-0.5 text-[10px] font-bold tracking-wide text-white" style={{ background: "#7c3aed" }}>
          {t("dm.badge")}
        </span>
        <button type="button" onClick={onKeluar} title={t("dm.exit")} className="rounded p-1 text-muted hover:text-ink">
          <X size={16} />
        </button>
      </div>
      <div className="mt-2 flex items-center gap-1.5 t-small text-muted">
        <FlaskConical size={13} /> {t("dm.step", { n: langkah + 1, m: JUMLAH_LANGKAH })}
      </div>
      <h3 className="mt-1 font-display text-[17px] font-bold leading-snug text-ink">{t(`dm.s${langkah}.t`)}</h3>
      <p className="mt-1.5 t-body leading-relaxed text-ink-2">{t(`dm.s${langkah}.b`)}</p>
      {info.length > 0 && (
        <div className="mt-2 space-y-1 rounded-lg px-2.5 py-1.5" style={{ background: "var(--surface-sunken)" }}>
          {info.map((x) => <p key={x} className="t-body font-semibold text-ink">{x}</p>)}
        </div>
      )}
      <p className="mt-2 t-small text-muted">{t("dm.safe")}</p>
      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="flex gap-1" aria-hidden>
          {Array.from({ length: JUMLAH_LANGKAH }, (_, i) => (
            <span key={i} className="h-1.5 w-4 rounded-full" style={{ background: i <= langkah ? "var(--brand)" : "var(--border-strong)" }} />
          ))}
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => onLangkah(langkah - 1)} disabled={langkah === 0}><ChevronLeft size={14} /> {t("dm.back")}</Button>
          <Button variant="solid" onClick={() => (akhir ? onKeluar() : onLangkah(langkah + 1))}>
            {akhir ? t("dm.done") : t("dm.next")} {!akhir && <ChevronRight size={14} />}
          </Button>
        </div>
      </div>
    </div>,
    document.body
  );
}
