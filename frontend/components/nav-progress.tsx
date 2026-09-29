"use client";

/**
 * Umpan balik perpindahan halaman / navigation feedback.
 *
 * MASALAHNYA BUKAN KECEPATAN, MELAINKAN KESUNYIAN. Next.js memuat halaman
 * berikutnya di latar belakang, dan selama itu layar lama diam sepenuhnya --
 * tidak ada tanda bahwa klik tadi diterima. Jeda 200 ms yang bisu terasa lebih
 * lama daripada jeda 600 ms yang menunjukkan sesuatu sedang berjalan.
 *
 * THE PROBLEM IS NOT SPEED, IT IS SILENCE. While the next route loads, the old
 * screen sits perfectly still with no sign the click registered. A silent 200 ms
 * feels longer than a 600 ms one that shows progress.
 *
 * Dua hal yang disediakan berkas ini:
 *   1. bilah tipis di tepi atas yang berjalan selama perpindahan;
 *   2. `useNavPending()` — alamat yang sedang dituju, supaya sidebar dapat
 *      memindahkan sorotannya SEKETIKA, sebelum halamannya sendiri siap.
 *
 * Pendengarnya dipasang pada dokumen (fase capture), bukan pada komponen tautan
 * tersendiri. Dengan begitu setiap <Link> di seluruh aplikasi ikut terpantau
 * tanpa perlu diganti satu per satu, termasuk tautan yang ditulis kelak.
 */

import { usePathname } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useState } from "react";

interface Isi {
  /** pathname yang sedang dituju, atau null bila tidak sedang berpindah */
  pending: string | null;
}

const Ctx = createContext<Isi>({ pending: null });

/** Alamat yang sedang dituju; dipakai untuk sorotan navigasi yang optimistis. */
export function useNavPending(): string | null {
  return useContext(Ctx).pending;
}

/**
 * Batas aman. Bila karena satu dan lain hal perpindahan tidak pernah selesai
 * (tautan dibatalkan, rute yang sama, galat), bilahnya tidak boleh berjalan
 * selamanya -- keadaan "sedang memuat" yang tidak pernah berakhir lebih
 * membingungkan daripada tidak ada indikator sama sekali.
 */
const BATAS_MS = 8000;

export function NavigationProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [pending, setPending] = useState<string | null>(null);
  const [selesai, setSelesai] = useState(false);
  const jaga = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      // Klik yang sudah ditangani orang lain, klik kanan, atau klik dengan
      // pemodifikasi (buka di tab baru) bukan urusan kita.
      if (e.defaultPrevented || e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;

      const a = (e.target as HTMLElement | null)?.closest?.("a");
      if (!a) return;
      if (a.target === "_blank" || a.hasAttribute("download")) return;

      const href = a.getAttribute("href");
      if (!href || href.startsWith("#")) return;

      const url = new URL(href, window.location.href);
      if (url.origin !== window.location.origin) return;
      // Menuju halaman yang sedang dibuka tidak memuat apa pun.
      if (url.pathname === pathname) return;

      setSelesai(false);
      setPending(url.pathname);
    }

    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [pathname]);

  // Perpindahan dianggap selesai begitu pathname benar-benar berganti.
  useEffect(() => {
    setPending((p) => {
      if (p === null) return null;
      setSelesai(true);
      return null;
    });
  }, [pathname]);

  useEffect(() => {
    if (jaga.current) clearTimeout(jaga.current);
    if (pending) {
      jaga.current = setTimeout(() => setPending(null), BATAS_MS);
    } else if (selesai) {
      // Bilah yang penuh perlu sekejap terlihat sebelum menghilang; tanpa jeda
      // ini perpindahan yang cepat hanya tampak sebagai kedipan.
      jaga.current = setTimeout(() => setSelesai(false), 420);
    }
    return () => {
      if (jaga.current) clearTimeout(jaga.current);
    };
  }, [pending, selesai]);

  return (
    <Ctx.Provider value={{ pending }}>
      {(pending || selesai) && (
        <div
          className="pointer-events-none fixed inset-x-0 top-0 z-[60] h-[3px]"
          role="progressbar"
          aria-hidden
        >
          <div
            className={pending ? "nav-progress-run" : "nav-progress-done"}
            style={{
              height: "100%",
              background: "var(--grad-brand)",
              boxShadow: "0 0 12px color-mix(in srgb, var(--brand) 70%, transparent)",
              borderRadius: "0 3px 3px 0",
            }}
          />
        </div>
      )}
      {children}
    </Ctx.Provider>
  );
}
