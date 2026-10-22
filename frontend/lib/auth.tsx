"use client";

/**
 * Keadaan "siapa yang sedang masuk", untuk seluruh aplikasi.
 *
 * SATU SUMBER, BUKAN PEMERIKSAAN DI SETIAP HALAMAN. Delapan belas halaman
 * tidak boleh masing-masing memutuskan apa yang terjadi bila pengguna belum
 * masuk -- satu yang lupa memeriksanya akan tampil separuh jadi dengan pesan
 * galat di setiap kartunya. Kerangka aplikasi memakai keadaan ini sekali, dan
 * halaman tetap ditulis seolah-olah pengguna selalu ada.
 *
 * TOKEN BUKAN KEBENARAN. Adanya token di peramban hanya berarti pengguna
 * PERNAH masuk; ia bisa saja sudah kedaluwarsa atau dicabut. Karena itu
 * pemuatan pertama selalu menanyakannya ke backend lewat /api/auth/me, dan
 * sampai jawabannya datang keadaannya adalah "memuat" -- bukan "sudah masuk".
 * Tanpa langkah itu, sesi yang sudah mati akan menampilkan kerangka aplikasi
 * lengkap selama sekejap sebelum semuanya gagal satu per satu.
 */

import { useRouter } from "next/navigation";
import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { apiGet, apiPost } from "@/lib/api";
import { akhiriSesi, bacaToken, saatSesiBerakhir, simpanToken } from "@/lib/token";

export interface Pengguna {
  id: number;
  username: string;
  email: string | null;
  full_name: string;
  role: "owner" | "admin" | "staff" | "viewer";
}

export interface Perusahaan {
  id: number;
  name: string;
  slug: string;
  is_demo: boolean;
}

type Status = "memuat" | "masuk" | "keluar";

interface Sesi {
  access_token: string;
  user: Pengguna;
  company: Perusahaan;
}

interface NilaiAuth {
  status: Status;
  pengguna: Pengguna | null;
  perusahaan: Perusahaan | null;
  /** true untuk owner dan admin; dipakai menyembunyikan menu pengelolaan. */
  bolehMengelola: boolean;
  /** true untuk owner, admin, dan staff; viewer hanya membaca. */
  bolehMencatat: boolean;
  masuk: (username: string, sandi: string) => Promise<void>;
  keluar: () => void;
}

const KonteksAuth = createContext<NilaiAuth | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<Status>("memuat");
  const [pengguna, setPengguna] = useState<Pengguna | null>(null);
  const [perusahaan, setPerusahaan] = useState<Perusahaan | null>(null);

  const bersihkan = useCallback(() => {
    setPengguna(null);
    setPerusahaan(null);
    setStatus("keluar");
  }, []);

  // Memulihkan sesi saat halaman dimuat atau dimuat ulang.
  useEffect(() => {
    if (!bacaToken()) {
      setStatus("keluar");
      return;
    }
    let batal = false;
    apiGet<{ user: Pengguna; company: Perusahaan }>("/api/auth/me")
      .then((j) => {
        if (batal) return;
        setPengguna(j.user);
        setPerusahaan(j.company);
        setStatus("masuk");
      })
      .catch(() => {
        // Token yang tidak lagi diterima sudah dibuang oleh lib/api.ts lewat
        // akhiriSesi; di sini tinggal memastikan keadaannya ikut turun.
        if (!batal) bersihkan();
      });
    return () => {
      batal = true;
    };
  }, [bersihkan]);

  // Satu permintaan yang dijawab 401 di sudut mana pun aplikasi memulangkan
  // pengguna ke halaman masuk, tanpa halaman itu perlu tahu apa-apa.
  useEffect(() => saatSesiBerakhir(bersihkan), [bersihkan]);

  const terima = useCallback((sesi: Sesi) => {
    simpanToken(sesi.access_token);
    setPengguna(sesi.user);
    setPerusahaan(sesi.company);
    setStatus("masuk");
  }, []);

  const masuk = useCallback(
    async (username: string, sandi: string) => {
      const sesi = await apiPost<Sesi>("/api/auth/login", {
        username: username.trim().toLowerCase(),
        password: sandi,
      });
      terima(sesi);
    },
    [terima],
  );

  const keluar = useCallback(() => {
    // Keluar dari SATU perangkat tidak perlu memanggil server: tokennya cukup
    // dibuang di sini. Mengusir perangkat LAIN adalah tindakan berbeda, dan
    // punya endpoint tersendiri (/api/auth/logout-all).
    simpanToken(null);
    bersihkan();
    router.replace("/login");
  }, [bersihkan, router]);

  const nilai = useMemo<NilaiAuth>(
    () => ({
      status,
      pengguna,
      perusahaan,
      bolehMengelola: pengguna?.role === "owner" || pengguna?.role === "admin",
      bolehMencatat: pengguna != null && pengguna.role !== "viewer",
      masuk,
      keluar,
    }),
    [status, pengguna, perusahaan, masuk, keluar],
  );

  return <KonteksAuth.Provider value={nilai}>{children}</KonteksAuth.Provider>;
}

export function useAuth(): NilaiAuth {
  const nilai = useContext(KonteksAuth);
  if (!nilai) throw new Error("useAuth dipakai di luar AuthProvider");
  return nilai;
}

/** Dipakai lib/api.ts secara tidak langsung; diekspor ulang demi kemudahan. */
export { akhiriSesi };
