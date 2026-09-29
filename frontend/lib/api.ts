"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { akhiriSesi, bacaToken } from "@/lib/token";

/**
 * Alamat API.
 *
 * Bila NEXT_PUBLIC_API_URL tidak diisi, alamatnya diturunkan dari host yang
 * sedang membuka halaman — bukan dipatok ke "localhost". Ini penting saat
 * dashboard dibuka dari perangkat lain di jaringan yang sama (mis. laptop
 * klien atau HP saat demo): di perangkat itu "localhost" menunjuk ke dirinya
 * sendiri, sehingga panggilan API gagal dengan "Failed to fetch".
 */
/**
 * SAKLAR BACKEND.
 *
 * Backend lama sudah dihapus seluruhnya (reset total) dan backend baru belum
 * dibangun. Selama masa itu seluruh panggilan data dimatikan DI SATU TEMPAT
 * ini saja, supaya:
 *   - tidak ada halaman yang menembak alamat yang sudah tidak ada;
 *   - seluruh halaman, komponen, dan styling tetap utuh dan bisa dijalankan;
 *   - setiap halaman menampilkan pesan yang jujur, bukan "Failed to fetch".
 *
 * MENGHUBUNGKAN KE BACKEND BARU: ubah BACKEND_READY menjadi true. Bila alamat
 * backend baru bukan port 8000, isi juga NEXT_PUBLIC_API_URL pada .env.local.
 * Tidak ada berkas lain yang perlu disentuh.
 */
export const BACKEND_READY = true;

export const BACKEND_OFFLINE_MESSAGE =
  "Backend sedang dibangun ulang, jadi data belum tersedia. Tampilan dan navigasi tetap berfungsi.";

export function apiBase(): string {
  const env = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "");
  if (env) return env;
  if (typeof window !== "undefined") {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return "http://localhost:8000"; // saat prerender di server
}

/**
 * Bahasa yang disertakan pada SETIAP permintaan.
 *
 * Sebagian kalimat di layar disusun backend bersama angkanya -- alasan status
 * pemesanan, deskripsi temuan, panel perhitungan. Kalimat itu tidak dapat
 * diterjemahkan ulang di layar tanpa membongkarnya untuk mengambil angkanya,
 * jadi bahasanya diminta sejak awal: satu parameter pada setiap panggilan, dan
 * backend menyusun kalimatnya langsung dalam bahasa itu.
 *
 * Disimpan di modul, bukan dilewatkan lewat argumen, karena ada puluhan
 * pemanggil dan tidak satu pun di antaranya punya urusan dengan bahasa.
 * Nilainya disetel LangProvider pada setiap render.
 */
let BAHASA = "id";

export function setApiLang(lang: string): void {
  BAHASA = lang;
}

export function apiLang(): string {
  return BAHASA;
}

/**
 * Header setiap permintaan, termasuk token bila pengguna sudah masuk.
 *
 * Disusun di satu tempat supaya menambah endpoint baru tidak berarti mengingat
 * untuk menyertakan tokennya. Endpoint yang memang tidak menuntut token --
 * masuk dan mendaftar -- tidak dirugikan: backend mengabaikan header yang
 * tidak ia perlukan.
 */
function headerPermintaan(denganIsi = false): Record<string, string> {
  const h: Record<string, string> = {};
  if (denganIsi) h["Content-Type"] = "application/json";
  const token = bacaToken();
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

/**
 * Galat dari backend, LENGKAP dengan nama ruas yang ditolaknya.
 *
 * Backend selalu menjawab `{error:{code, message, field?}}`, dan `field`
 * menyebut kolom mana yang salah. Sampai 2 September 2026 lapisan ini
 * membuang `field` dan hanya melempar kalimatnya, sehingga formulir dengan
 * delapan kolom menampilkan "SKU sudah dipakai" sebagai spanduk di atas
 * formulir -- benar isinya, tetapi pembacanya harus menebak sendiri kolom
 * mana yang harus diperbaiki. Kelas ini membawa keterangan itu sampai ke
 * layar; yang lama tetap bekerja karena ia tetap sebuah Error dengan
 * `message` yang sama.
 */
export class GalatApi extends Error {
  readonly code: string;
  readonly field: string | null;
  readonly status: number;

  constructor(pesan: string, opsi: { code?: string; field?: string | null; status: number }) {
    super(pesan);
    this.name = "GalatApi";
    this.code = opsi.code ?? "ERROR";
    this.field = opsi.field ?? null;
    this.status = opsi.status;
  }
}

function lempar(json: any, res: Response): never {
  throw new GalatApi(json?.error?.message ?? `${res.status} ${res.statusText}`, {
    code: json?.error?.code,
    field: json?.error?.field ?? null,
    status: res.status,
  });
}

/**
 * Menutup sesi bila backend menyatakan token tidak berlaku lagi.
 *
 * 401 berarti tokennya sudah tidak sah -- kedaluwarsa, dicabut, atau kata
 * sandinya diganti di perangkat lain. Menyimpannya lebih lama hanya membuat
 * setiap halaman berikutnya gagal satu per satu dengan pesan yang
 * membingungkan.
 *
 * 403 SENGAJA tidak ikut: itu berarti tokennya sah tetapi perannya tidak
 * berhak, dan melempar pengguna keluar karena ia membuka satu halaman
 * terlarang adalah hukuman yang salah sasaran.
 */
function periksaSesi(status: number): void {
  if (status === 401) akhiriSesi();
}

/**
 * Sinyal "tarik ulang semuanya".
 *
 * Ada tindakan yang mengubah angka di SELURUH layar sekaligus, bukan hanya di
 * kartu tempat tombolnya berada -- simulasi penjualan mengubah stok, nilai
 * persediaan, daftar stok menipis, dan rekomendasi pemesanan dalam satu
 * permintaan. Tanpa sinyal ini, satu-satunya cara membuat layar jujur adalah
 * memuat ulang seluruh halaman, dan pemuatan ulang di tengah presentasi
 * mengembalikan penonton ke layar putih selama sedetik dua detik.
 *
 * Setiap useApi mendengarkannya dan menarik datanya sendiri. Data lama tetap
 * tampil selama penarikan berlangsung, sehingga angkanya berganti di tempat.
 */
const pendengarSegar = new Set<() => void>();

export function saatDimintaSegar(fn: () => void): () => void {
  pendengarSegar.add(fn);
  return () => pendengarSegar.delete(fn);
}

export function segarkanSemua(): void {
  pendengarSegar.forEach((fn) => fn());
}

export type Params = Record<string, string | number | boolean | string[] | null | undefined>;

export function buildUrl(path: string, params?: Params): string {
  const url = new URL(apiBase() + path);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === null || v === undefined || v === "") continue;
      if (Array.isArray(v)) v.forEach((x) => url.searchParams.append(k, String(x)));
      else url.searchParams.set(k, String(v));
    }
  }
  // Ikut menjadi bagian kunci cache useApi: berganti bahasa otomatis menarik
  // ulang datanya, sehingga kalimat lama tidak tertinggal di layar.
  url.searchParams.set("lang", BAHASA);
  return url.toString();
}

export async function apiGet<T>(path: string, params?: Params): Promise<T> {
  if (!BACKEND_READY) throw new Error(BACKEND_OFFLINE_MESSAGE);
  const res = await fetch(buildUrl(path, params), {
    cache: "no-store",
    headers: headerPermintaan(),
  });
  if (!res.ok) {
    periksaSesi(res.status);
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${text ? ` -- ${text.slice(0, 200)}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  if (!BACKEND_READY) throw new Error(BACKEND_OFFLINE_MESSAGE);
  // Endpoint POST pun menyusun kalimat (ulasan pemesanan, jawaban asisten),
  // jadi bahasanya ikut pada query string persis seperti pada GET.
  const alamat = new URL(apiBase() + path);
  alamat.searchParams.set("lang", BAHASA);
  const res = await fetch(alamat.toString(), {
    method: "POST",
    headers: headerPermintaan(true),
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => null);
  if (!res.ok) {
    periksaSesi(res.status);
    // Backend selalu mengirim {error:{code,message}} -- pesan itu sudah ditulis
    // untuk dibaca pengguna, jadi dipakai apa adanya.
    lempar(json, res);
  }
  return json as T;
}

/**
 * Permintaan PATCH.
 *
 * Dipisah dari apiPost karena artinya berbeda, bukan karena bentuknya:
 * POST menyusun sesuatu yang baru (ulasan, jawaban asisten), PATCH mengubah
 * satu ruas data yang sudah tercatat. Penanganan galatnya sama -- pesan dari
 * backend sudah ditulis untuk dibaca pengguna, jadi dipakai apa adanya.
 */
export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  if (!BACKEND_READY) throw new Error(BACKEND_OFFLINE_MESSAGE);
  const alamat = new URL(apiBase() + path);
  alamat.searchParams.set("lang", BAHASA);
  const res = await fetch(alamat.toString(), {
    method: "PATCH",
    headers: headerPermintaan(true),
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => null);
  if (!res.ok) {
    periksaSesi(res.status);
    lempar(json, res);
  }
  return json as T;
}

/**
 * Permintaan DELETE.
 *
 * Dipakai hanya oleh master data, dan hanya untuk baris yang belum dirujuk
 * transaksi apa pun -- backend yang memutuskan itu, bukan layar. Penolakannya
 * (409) datang bersama kalimat yang menyebut berapa data yang merujuknya, jadi
 * pesannya dipakai apa adanya seperti pada POST dan PATCH.
 */
export async function apiDelete<T>(path: string): Promise<T> {
  if (!BACKEND_READY) throw new Error(BACKEND_OFFLINE_MESSAGE);
  const alamat = new URL(apiBase() + path);
  alamat.searchParams.set("lang", BAHASA);
  const res = await fetch(alamat.toString(), {
    method: "DELETE",
    headers: headerPermintaan(),
  });
  const json = await res.json().catch(() => null);
  if (!res.ok) {
    periksaSesi(res.status);
    lempar(json, res);
  }
  return json as T;
}

/**
 * Unggahan berkas (multipart), untuk impor master data.
 *
 * Content-Type sengaja TIDAK disetel: peramban yang menyusunnya sendiri, dan
 * menyetelnya manual menghilangkan penanda batas multipart sehingga server
 * menerima badan permintaan yang tidak dapat diurai.
 */
export async function apiUpload<T>(
  path: string,
  berkas: File,
  params?: Params,
): Promise<T> {
  if (!BACKEND_READY) throw new Error(BACKEND_OFFLINE_MESSAGE);
  const isi = new FormData();
  isi.append("file", berkas);
  const res = await fetch(buildUrl(path, params), {
    method: "POST",
    headers: headerPermintaan(),
    body: isi,
  });
  const json = await res.json().catch(() => null);
  if (!res.ok) {
    periksaSesi(res.status);
    lempar(json, res);
  }
  return json as T;
}

/**
 * Mengunduh berkas dari endpoint yang menuntut token.
 *
 * Tautan <a href> biasa TIDAK bisa dipakai: peramban tidak menyertakan header
 * Authorization pada navigasi, sehingga berkas contoh akan dijawab 401 dan
 * yang terunduh adalah halaman galat. Berkasnya karena itu diambil lewat fetch
 * berheader, lalu diserahkan ke peramban sebagai blob.
 */
export async function apiUnduh(path: string, namaBerkas: string): Promise<void> {
  if (!BACKEND_READY) throw new Error(BACKEND_OFFLINE_MESSAGE);
  const res = await fetch(buildUrl(path), { headers: headerPermintaan() });
  if (!res.ok) {
    periksaSesi(res.status);
    throw new Error(`${res.status} ${res.statusText}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = namaBerkas;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Dilepas setelah peramban sempat memulai unduhannya; melepas seketika
  // membatalkan unduhan pada sebagian peramban.
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  /** true saat memuat ulang -- render sebelumnya ditahan agar tidak berkedip */
  refreshing: boolean;
  reload: () => void;
}

/**
 * Hook pengambil data.
 * Saat memuat ulang, data lama TETAP ditampilkan (dengan opasitas rendah di UI)
 * sehingga tidak terjadi kedipan skeleton dan lompatan tata letak.
 */
export function useApi<T>(path: string | null, params?: Params): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Tetap mulai dari "memuat" walau backend mati: saat prerender di server,
  // useEffect belum berjalan, dan halaman yang langsung membaca data.kpi akan
  // crash bila keadaan awalnya bukan loading.
  const [loading, setLoading] = useState<boolean>(!!path);
  const [refreshing, setRefreshing] = useState(false);
  const [tick, setTick] = useState(0);
  const key = path ? buildUrl(path, params) : null;
  const hasData = useRef(false);

  useEffect(() => {
    if (!key) return;
    // Tanpa backend, berhenti di sini: tidak ada permintaan jaringan sama
    // sekali, dan halaman langsung menampilkan pesan yang benar.
    if (!BACKEND_READY) {
      setData(null);
      setError(BACKEND_OFFLINE_MESSAGE);
      setLoading(false);
      setRefreshing(false);
      return;
    }
    let cancelled = false;
    if (hasData.current) setRefreshing(true);
    else setLoading(true);

    fetch(key, { cache: "no-store", headers: headerPermintaan() })
      .then(async (res) => {
        if (!res.ok) {
          periksaSesi(res.status);
          throw new Error(`${res.status} ${res.statusText}`);
        }
        return res.json();
      })
      .then((json) => {
        if (cancelled) return;
        setData(json);
        setError(null);
        hasData.current = true;
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
        setRefreshing(false);
      });

    return () => {
      cancelled = true;
    };
  }, [key, tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  // Ikut menarik ulang saat ada tindakan yang mengubah angka di seluruh layar.
  useEffect(() => saatDimintaSegar(reload), [reload]);

  return { data, error, loading, refreshing, reload };
}
