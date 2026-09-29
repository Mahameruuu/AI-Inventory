"use client";

/**
 * Pengalih bahasa / language runtime.
 *
 * Bahasa disimpan di localStorage dan dipulihkan SETELAH hidrasi, bukan saat
 * render pertama. Pilihan itu disengaja: render server tidak dapat membaca
 * localStorage, jadi memulai dari bahasa tersimpan akan membuat markup server
 * dan klien berbeda -- React membuang seluruh pohon dan mencetak peringatan
 * hidrasi. Satu kedipan singkat jauh lebih murah daripada itu.
 *
 * The language lives in localStorage and is restored AFTER hydration, never on
 * the first render: the server cannot read localStorage, so starting from the
 * stored value would make server and client markup disagree. One brief flash is
 * far cheaper than a discarded tree.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { setApiLang } from "@/lib/api";
import { DICT, type Lang } from "@/lib/dictionary";
import { setFormatLocale } from "@/lib/format";

export type { Lang };

interface Isi {
  lang: Lang;
  setLang: (l: Lang) => void;
  /** Terjemahkan satu kunci; `{nama}` pada teks diganti dari `vars`. */
  t: (key: string, vars?: Record<string, string | number>) => string;
  /** Pilih salah satu dari dua nilai sesuai bahasa aktif. */
  pick: <T>(id: T, en: T) => T;
}

const Ctx = createContext<Isi | null>(null);

const KUNCI_SIMPAN = "lang";

function terjemah(lang: Lang, key: string, vars?: Record<string, string | number>): string {
  const entri = DICT[key];
  // Kunci yang belum diterjemahkan dikembalikan apa adanya, bukan dijadikan
  // string kosong: layar yang kehilangan kalimat jauh lebih sulit dilacak
  // daripada layar yang menampilkan nama kuncinya.
  let teks = entri ? entri[lang] : key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      teks = teks.split(`{${k}}`).join(String(v));
    }
  }
  return teks;
}

export function LangProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState<Lang>("id");

  // Pemformat angka & tanggal dan lapisan API hidup di luar React. Keduanya
  // disetel saat render, bukan di dalam efek, supaya anak-anak komponen pada
  // render yang SAMA sudah memakai locale dan bahasa yang benar -- termasuk
  // permintaan pertama yang berangkat dari efek mereka.
  setFormatLocale(lang);
  setApiLang(lang);

  useEffect(() => {
    const tersimpan = localStorage.getItem(KUNCI_SIMPAN);
    if (tersimpan === "en" || tersimpan === "id") setLangState(tersimpan);
    else {
      // Tanpa pilihan tersimpan, bahasa peramban yang menentukan -- pengunjung
      // demo berbahasa Inggris tidak perlu mencari sakelarnya lebih dulu.
      const peramban = navigator.language?.toLowerCase() ?? "";
      if (peramban && !peramban.startsWith("id")) setLangState("en");
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("lang", lang);
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    setFormatLocale(l);
    setApiLang(l);
    try {
      localStorage.setItem(KUNCI_SIMPAN, l);
    } catch {
      /* peramban mode privat: pilihan tetap berlaku untuk sesi ini */
    }
  }, []);

  const nilai = useMemo<Isi>(
    () => ({
      lang,
      setLang,
      t: (key, vars) => terjemah(lang, key, vars),
      pick: (id, en) => (lang === "id" ? id : en),
    }),
    [lang, setLang]
  );

  return <Ctx.Provider value={nilai}>{children}</Ctx.Provider>;
}

export function useI18n(): Isi {
  const ctx = useContext(Ctx);
  if (!ctx) {
    // Komponen di luar provider tetap dapat dirender (mis. saat diuji
    // sendirian); bahasanya jatuh ke bawaan.
    return {
      lang: "id",
      setLang: () => {},
      t: (key, vars) => terjemah("id", key, vars),
      pick: (id) => id,
    };
  }
  return ctx;
}

/** Pintasan yang paling sering dipakai: `const t = useT();` */
export function useT() {
  return useI18n().t;
}
