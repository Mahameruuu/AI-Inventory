"use client";

/**
 * Perkakas bersama halaman Prakiraan dan halaman Pemesanan Ulang.
 * Shared building blocks for the Forecasting and Reorder pages.
 *
 * Keduanya membaca satu endpoint yang sama dan memilih gudang/barang dengan
 * cara yang sama, tetapi menjawab pertanyaan yang berbeda. Yang dipakai
 * bersama hanya bentuk tampilan dan pemilihan barang -- BUKAN isi bloknya:
 * kartu prakiraan tinggal di forecast-sections.tsx, kartu keputusan di
 * reorder-sections.tsx, dan tidak satu pun saling mengimpor.
 */

import { ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { LucideIcon } from "lucide-react";

import { Field, Select } from "@/components/ui";
import { apiGet, useApi } from "@/lib/api";
import { AksiStatus, JenisPemakaian, PilihanModel, PilihanStrategi } from "@/lib/forecast-types";
import { useT } from "@/lib/i18n";
import { num } from "@/lib/format";

/*
 * Peta status keputusan PINDAH ke components/status.tsx pada 2 September 2026.
 *
 * Ia dipakai halaman Prakiraan, Pemesanan Ulang, DAN Dasbor -- dan selama ia
 * tinggal di berkas milik Prakiraan, Dasbor menyalin sendiri versinya dengan
 * warna yang berbeda. Di-ekspor ulang di sini supaya pemanggil lama tidak
 * perlu ikut berubah; yang baru sebaiknya mengimpor langsung dari status.tsx.
 */
export { AKSI } from "@/components/status";

/** Label status keputusan dalam bahasa yang sedang aktif. */
export function useLabelAksi() {
  const t = useT();
  return {
    status: (s: AksiStatus) => t(`ro.status.${s}`),
    aksi: (s: AksiStatus) => t(`ro.action.${s}`),
  };
}

/**
 * Kartu keputusan.
 *
 * Menggantikan StatTile pada kedua halaman ini karena kartunya menampung label
 * teks ("±2 minggu", "Tidak ada pemakaian"), bukan hanya angka, dan kartu
 * terpenting perlu diberi garis warna status.
 */
export function KartuKeputusan({
  label,
  nilai,
  detail,
  detailWarna,
  aksen,
  tanda,
}: {
  label: string;
  nilai: string;
  detail: string;
  detailWarna?: string;
  /** garis atas berwarna status -- hanya untuk kartu yang paling menentukan */
  aksen?: string;
  /** lencana kecil di samping nilai, mis. peringatan data terbatas */
  tanda?: ReactNode;
}) {
  return (
    <div className="surface-card surface-card-hover relative flex flex-col gap-1 overflow-hidden px-4 pb-3.5 pt-4">
      {aksen && (
        <span
          aria-hidden
          className="absolute inset-x-0 top-0 h-[3px]"
          style={{
            background: `linear-gradient(90deg, ${aksen}, color-mix(in srgb, ${aksen} 15%, transparent))`,
          }}
        />
      )}
      <span className="t-caption font-semibold uppercase tracking-[0.06em] text-ink-2">
        {label}
      </span>
      <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="stat-figure text-[24px] font-bold leading-tight text-ink">{nilai}</span>
        {tanda}
      </span>
      <span
        className="t-caption leading-relaxed"
        style={{ color: detailWarna ?? "var(--text-muted)" }}
      >
        {detail}
      </span>
    </div>
  );
}

/**
 * Kepala satu blok konsep.
 *
 * Ikonnya berupa VEKTOR, bukan emoji: emoji digambar berbeda oleh setiap sistem
 * operasi, ukurannya tidak mengikuti teks, dan pada layar proyektor ia terbaca
 * sebagai stiker -- bukan sebagai penanda bagian pada perangkat lunak
 * perusahaan.
 *
 * Keterangan di bawah judul menyebut PATOKAN WAKTU blok itu, karena justru
 * hubungan antarblok yang dulu paling sering disalahpahami, bukan angkanya
 * sendiri: blok prakiraan bergerak saat periode diganti, blok reorder tidak.
 */
export function Blok({
  Ikon,
  judul,
  keterangan,
  warna = "var(--brand)",
  children,
}: {
  Ikon: LucideIcon;
  judul: string;
  keterangan: string;
  /** warna aksen ikon; bawaannya warna merek */
  warna?: string;
  children: ReactNode;
}) {
  return (
    <section className="rise mt-7">
      <header className="mb-3 flex items-start gap-3">
        <span
          aria-hidden
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
          style={{
            background: `color-mix(in srgb, ${warna} 13%, transparent)`,
            boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${warna} 26%, transparent)`,
            color: warna,
          }}
        >
          <Ikon size={17} />
        </span>
        <div className="min-w-0">
          <h2 className="font-display t-lead font-bold leading-tight text-ink">{judul}</h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-muted">{keterangan}</p>
        </div>
      </header>
      {children}
    </section>
  );
}

/**
 * Angka bersatuan, atau "—" bila memang belum ada nilainya.
 *
 * null di sini SELALU berarti "belum dapat dihitung", tidak pernah "nol" --
 * backend membedakan keduanya dengan sengaja, dan menampilkan 0 untuk nilai
 * yang belum terhitung akan menghapus perbedaan itu di layar terakhir.
 *
 * BILANGAN BULAT SAJA. Yang dikirim ke sini harus sudah berupa field `*_int`
 * dari backend; `maximumFractionDigits: 0` hanyalah jaring pengaman agar satu
 * field desimal yang lolos tidak diam-diam mencetak "45,48 PCS" di sebelah
 * kartu yang berbunyi "45 PCS".
 */
export function angka(v: number | null | undefined, satuan = ""): string {
  if (v === null || v === undefined) return "—";
  return satuan ? `${num(v, 0)} ${satuan}` : num(v, 0);
}

/** Satu kelompok barang yang boleh muncul pada dropdown. */
export interface KelompokBarang {
  /** Nama yang ditampilkan pada label dropdown, mis. "Pompa". */
  nama: string;
  /**
   * Kata yang dicari pada NAMA barang, huruf besar-kecil diabaikan.
   *
   * Perlu lebih dari satu kata karena katalognya dwibahasa: pompa tercatat
   * sebagai "Pompa Sentrifugal" maupun "Centrifugal Pump"/"Gear Pump", jadi
   * satu kata kunci saja akan menghilangkan sebagian besar barangnya.
   */
  kata: string[];
}

/** Urutkan dari pergerakan terakhir paling baru. */
function teraktifDulu(rows: any[]): any[] {
  return [...rows].sort((a, b) =>
    String(b.last_movement_date ?? "").localeCompare(String(a.last_movement_date ?? ""))
  );
}

/**
 * Susun isi dropdown barang: saring menurut kelompok, lalu potong.
 *
 * Penyaringan dan pemotongan dikerjakan SETELAH seluruh halaman terkumpul,
 * bukan dengan meminta lebih sedikit baris ke API. /api/inventory mengurutkan
 * menurut SKU dan tidak punya parameter urutan, jadi sepuluh baris pertamanya
 * adalah sepuluh SKU teratas menurut abjad -- yang sebagian besar sudah lama
 * tidak bergerak dan menjawab "Insufficient Data". Parameter `q`-nya pun hanya
 * menerima satu kata, sedangkan yang dicari di sini empat kata sekaligus.
 *
 * Pengambilannya BERGILIR antar kelompok, bukan sepuluh teraktif dari seluruh
 * hasil saringan. Ketiga kelompok punya jumlah yang timpang per gudang (di
 * Surabaya ada 33 oli tetapi hanya 23 bearing) dan sebagian besar barang
 * bergerak pada stempel waktu yang sama, sehingga pengambilan lurus menurut
 * kebaruan mudah terisi satu kelompok saja -- padahal justru ketiganya yang
 * ingin dilihat. Bergilir menjamin tiap kelompok kebagian selama masih ada
 * isinya, dan tetap mendahulukan yang terakhir bergerak di dalam kelompoknya.
 *
 * Satu barang hanya masuk ke kelompok pertama yang cocok, supaya nama yang
 * kebetulan memuat dua kata kunci tidak muncul dua kali pada dropdown.
 *
 * Tanpa `kelompok` dan `maks` daftarnya dikembalikan apa adanya -- halaman
 * Pemesanan Ulang memakai jalur itu dan tetap memuat seluruh barang gudang.
 */
function susunBarang(rows: any[], kelompok?: KelompokBarang[], maks?: number): any[] {
  // Terbaru dulu, dengan atau tanpa saringan kelompok. Sebelumnya cabang tanpa
  // kelompok mengembalikan urutan API apa adanya -- yaitu menurut abjad SKU --
  // sehingga begitu pembatasan dicabut, dropdown-nya berhenti mendahulukan
  // barang yang baru bergerak dan yang pertama terpilih menjadi barang yang
  // kebetulan SKU-nya paling awal.
  if (!kelompok?.length) {
    const urut = teraktifDulu(rows);
    return maks ? urut.slice(0, maks) : urut;
  }

  const antrean: any[][] = kelompok.map(() => []);
  for (const r of rows) {
    const nama = String(r.item_name ?? "").toLowerCase();
    const k = kelompok.findIndex((g) => g.kata.some((w) => nama.includes(w.toLowerCase())));
    if (k >= 0) antrean[k].push(r);
  }
  const siap = antrean.map(teraktifDulu);

  const batas = maks ?? rows.length;
  const hasil: any[] = [];
  const terpanjang = Math.max(0, ...siap.map((q) => q.length));
  for (let putaran = 0; putaran < terpanjang && hasil.length < batas; putaran += 1) {
    for (const q of siap) {
      if (hasil.length >= batas) break;
      if (putaran < q.length) hasil.push(q[putaran]);
    }
  }
  /*
   * Sama seperti saringan gudang: kata kunci kelompok mengikuti katalog satu
   * penyewa. Katalog lain bisa tidak memuat satu pun kata itu -- katalog Demo
   * berisi kawat las, amplas, dan lakban -- dan mengembalikan daftar kosong
   * berarti halaman ikut kosong. Lebih baik menampilkan barang teraktif apa
   * adanya daripada tidak menampilkan apa pun.
   */
  return hasil.length ? hasil : teraktifDulu(rows).slice(0, batas);
}

/**
 * Seluruh barang yang tercatat di satu gudang.
 *
 * API membatasi 200 baris per halaman sedangkan satu gudang berisi sekitar 450
 * barang, jadi sekali panggil saja akan memotong lebih dari separuh daftarnya
 * tanpa memberi tanda apa pun -- barang yang hilang itu mustahil dipilih
 * pengguna. Karena itu halamannya ditelusuri sampai habis (biasanya tiga
 * panggilan), bukan diambil satu kali lalu dianggap lengkap.
 */
function useBarangGudang(warehouseId: string, kelompok?: KelompokBarang[], maks?: number) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!warehouseId) {
      setItems([]);
      return;
    }
    let batal = false;
    setLoading(true);
    (async () => {
      const kumpul: any[] = [];
      const terlihat = new Set<number>();
      /*
       * Kata kunci kelompok dikirim sebagai parameter q, bukan dipakai
       * menyaring setelah seluruh katalog ditarik. Satu gudang berisi 8.006
       * barang = 41 halaman: menariknya utuh berarti puluhan permintaan
       * berurutan pada SETIAP pergantian gudang, dan penjaga halaman di
       * bawahnya akan memotong daftarnya di tengah abjad -- karena API
       * mengurutkan menurut SKU, barang berriwayat yang jatuh di paruh
       * belakang menjadi mustahil terpilih. Dengan q, satu kata paling banyak
       * menyisakan sekitar 400 baris.
       */
      const kunci: (string | undefined)[] = kelompok?.length
        ? Array.from(new Set(kelompok.flatMap((g) => g.kata)))
        : [undefined];
      for (const q of kunci) {
        // Batas halaman semata-mata penjaga supaya satu jawaban aneh tidak
        // memutar tanpa henti; satu kata kunci tidak pernah sedekat ini.
        for (let page = 1; page <= 20; page += 1) {
          /*
           * Lewat apiGet, BUKAN fetch langsung. /api/inventory menuntut token
           * seperti setiap endpoint data lainnya, dan fetch yang ditulis di
           * sini tidak membawanya: jawabannya 401, perulangan ini berhenti
           * pada halaman pertama, daftar barang tetap kosong, dan karena
           * `siap` ikut kosong maka /api/forecast tidak pernah dipanggil sama
           * sekali. Halaman Prakiraan dan Pemesanan Ulang lalu tampil kosong
           * tanpa satu pun galat -- tidak di layar, tidak pula di Network.
           */
          let j: any;
          try {
            j = await apiGet<any>("/api/inventory", {
              warehouse_id: warehouseId,
              q,
              page,
              page_size: 200,
            });
          } catch {
            break;
          }
          for (const r of (j.items ?? []) as any[]) {
            // "Filter Oli" terjaring "oli", "Pompa Oli" terjaring dua kata.
            if (terlihat.has(r.id)) continue;
            terlihat.add(r.id);
            kumpul.push(r);
          }
          if (page >= (j.pages ?? 1)) break;
        }
      }
      if (!batal) {
        setItems(susunBarang(kumpul, kelompok, maks));
        setLoading(false);
      }
    })().catch(() => {
      if (!batal) setLoading(false);
    });
    return () => {
      batal = true;
    };
  }, [warehouseId, kelompok, maks]);

  return { items, loading };
}

/* ------------------------------------------------------------------ */
/* Pilihan model, dipakai bersama dua halaman                          */
/* ------------------------------------------------------------------ */

const KUNCI_MODEL = "inventory.model_prakiraan";
const KUNCI_STRATEGI = "inventory.strategi_reorder";
const KUNCI_PERIODE = "inventory.periode_prakiraan";

/*
 * Disimpan di modul, BUKAN di state masing-masing halaman.
 *
 * Halaman Prakiraan dan Pemesanan Ulang membaca endpoint yang sama untuk
 * barang yang sama; alasannya persis sama dengan alasan keduanya berbagi
 * lingkupnya. Bila keduanya memegang pilihan model sendiri-sendiri,
 * satu barang bisa tampak genting di satu layar dan tenang di layar
 * sebelahnya -- dan tidak ada apa pun di layar yang menjelaskan sebabnya,
 * karena keduanya sama-sama benar menurut modelnya masing-masing.
 *
 * localStorage menjadi sumber kebenaran saat halaman dimuat ulang, dengan
 * penjagaan yang sama seperti lib/token.ts: peramban yang penyimpanannya
 * dimatikan tetap dapat memakai aplikasi, hanya tidak mengingat pilihannya.
 */
// Bawaan yang sama dengan backend (klasik.KUNCI_STATISTIK). Dua bawaan
// yang berbeda berarti layar dan API menghitung barang yang sama dengan
// dasar yang berlainan sampai pengguna menyentuh dropdownnya.
let modelTerpilih = "statistik";
let sudahDibaca = false;
const pendengarModel = new Set<() => void>();

function bacaModel(): string {
  if (typeof window === "undefined") return modelTerpilih;
  if (!sudahDibaca) {
    try {
      modelTerpilih = window.localStorage.getItem(KUNCI_MODEL) || "statistik";
    } catch {
      modelTerpilih = "statistik";
    }
    sudahDibaca = true;
  }
  return modelTerpilih;
}

/**
 * Model prakiraan yang sedang dipilih, sama untuk seluruh halaman.
 *
 * Mengembalikan pasangan seperti useState, sehingga halaman pemakainya tidak
 * perlu tahu bahwa nilainya dibagi dengan halaman lain.
 */
export function usePilihanModel(): [string, (v: string) => void] {
  const [model, setModelLokal] = useState(bacaModel);

  useEffect(() => {
    // Halaman yang baru dibuka mungkin dirakit sebelum localStorage terbaca;
    // penyelarasan sekali di sini menutup selisih itu.
    setModelLokal(bacaModel());
    const dengar = () => setModelLokal(modelTerpilih);
    pendengarModel.add(dengar);
    return () => {
      pendengarModel.delete(dengar);
    };
  }, []);

  const setModel = useCallback((v: string) => {
    modelTerpilih = v;
    sudahDibaca = true;
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(KUNCI_MODEL, v);
      } catch {
        /* diabaikan dengan sengaja: lihat catatan di atas */
      }
    }
    pendengarModel.forEach((fn) => fn());
  }, []);

  return [model, setModel];
}


/**
 * Dropdown model, satu bentuk untuk kedua halaman.
 *
 * Daftarnya diambil dari backend lewat /api/forecast/models, tidak ditulis
 * ulang di layar: daftar yang hidup di dua tempat akan berbeda isinya cepat
 * atau lambat, dan yang terlihat pengguna adalah pilihan yang justru ditolak
 * backend.
 */
export function PemilihModel({
  model,
  setModel,
}: {
  model: string;
  setModel: (v: string) => void;
}) {
  const t = useT();
  const { data } = useApi<{ items: PilihanModel[] }>("/api/forecast/models");
  return (
    <Field label={t("fc.model")}>
      <Select
        value={model}
        onChange={setModel}
        options={(data?.items ?? [])
          // Model pembelajaran mesin hilang dari daftar bila berkas modelnya
          // tidak termuat saat deploy. Menyembunyikannya lebih jujur daripada
          // membiarkannya dipilih lalu diam-diam jatuh ke cadangan.
          .filter((m) => m.available)
          .map((m) => ({ value: m.key, label: m.label }))}
        className="min-w-[190px]"
      />
    </Field>
  );
}


/*
 * Strategi layanan, disimpan dengan cara yang sama seperti pilihan model.
 *
 * Hanya halaman Pemesanan Ulang yang memakainya -- Prakiraan tidak menjawab
 * pertanyaan risiko -- tetapi penyimpanannya tetap disamakan supaya kelak
 * tidak ada dua cara berbeda mengingat dua pilihan yang bersebelahan di layar.
 */
let strategiTerpilih = "standar";
let strategiDibaca = false;
const pendengarStrategi = new Set<() => void>();

function bacaStrategi(): string {
  if (typeof window === "undefined") return strategiTerpilih;
  if (!strategiDibaca) {
    try {
      strategiTerpilih = window.localStorage.getItem(KUNCI_STRATEGI) || "standar";
    } catch {
      strategiTerpilih = "standar";
    }
    strategiDibaca = true;
  }
  return strategiTerpilih;
}

export function usePilihanStrategi(): [string, (v: string) => void] {
  const [strategi, setLokal] = useState(bacaStrategi);

  useEffect(() => {
    setLokal(bacaStrategi());
    const dengar = () => setLokal(strategiTerpilih);
    pendengarStrategi.add(dengar);
    return () => {
      pendengarStrategi.delete(dengar);
    };
  }, []);

  const set = useCallback((v: string) => {
    strategiTerpilih = v;
    strategiDibaca = true;
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(KUNCI_STRATEGI, v);
      } catch {
        /* diabaikan dengan sengaja */
      }
    }
    pendengarStrategi.forEach((fn) => fn());
  }, []);

  return [strategi, set];
}


/**
 * Dropdown strategi layanan.
 *
 * Labelnya menyebut tingkat layanan, bukan Z-score: yang sedang diputuskan
 * orang gudang adalah "seberapa sering saya rela kehabisan", dan angka 2,05
 * tidak menjawab itu sampai diterjemahkan.
 */
export function PemilihStrategi({
  strategi,
  setStrategi,
}: {
  strategi: string;
  setStrategi: (v: string) => void;
}) {
  const t = useT();
  const { data } = useApi<{ strategies: PilihanStrategi[] }>(
    "/api/forecast/models"
  );
  return (
    <Field label={t("ro.strategy")}>
      <Select
        value={strategi}
        onChange={setStrategi}
        options={(data?.strategies ?? []).map((s) => ({
          value: s.key,
          label: `${s.label} — ${Math.round(s.service_level * 100)}%`,
        }))}
        className="min-w-[170px]"
      />
    </Field>
  );
}


/*
 * Periode prakiraan, dibagi dua halaman.
 *
 * Halaman Pemesanan Ulang dulu memakai horizon tetap dengan alasan yang benar:
 * keputusan pengadaan tidak boleh bergeser karena setelan tampilan. Alasan itu
 * kini dijaga di tempat yang seharusnya -- backend memakai horizon tetap untuk
 * galat model dan laju keputusan, apa pun periode yang diminta layar. Dengan
 * kebocoran itu tertutup, periodenya aman dibuka di kedua halaman, dan
 * membaginya membuat "kebutuhan 30 hari" di satu layar dapat dibandingkan
 * langsung dengan angka di layar sebelahnya tanpa menyetel dua kali.
 */
export const PERIODE = [7, 14, 30, 60, 90];

let periodeTerpilih = "7";
let periodeDibaca = false;
const pendengarPeriode = new Set<() => void>();

function bacaPeriode(): string {
  if (typeof window === "undefined") return periodeTerpilih;
  if (!periodeDibaca) {
    try {
      periodeTerpilih = window.localStorage.getItem(KUNCI_PERIODE) || "7";
    } catch {
      periodeTerpilih = "7";
    }
    periodeDibaca = true;
  }
  return periodeTerpilih;
}

export function usePilihanPeriode(): [string, (v: string) => void] {
  const [periode, setLokal] = useState(bacaPeriode);

  useEffect(() => {
    setLokal(bacaPeriode());
    const dengar = () => setLokal(periodeTerpilih);
    pendengarPeriode.add(dengar);
    return () => {
      pendengarPeriode.delete(dengar);
    };
  }, []);

  const set = useCallback((v: string) => {
    periodeTerpilih = v;
    periodeDibaca = true;
    if (typeof window !== "undefined") {
      try {
        window.localStorage.setItem(KUNCI_PERIODE, v);
      } catch {
        /* diabaikan dengan sengaja */
      }
    }
    pendengarPeriode.forEach((fn) => fn());
  }, []);

  return [periode, set];
}


export function PemilihPeriode({
  periode,
  setPeriode,
}: {
  periode: string;
  setPeriode: (v: string) => void;
}) {
  const t = useT();
  return (
    <Field label={t("c.period")}>
      <Select
        value={periode}
        onChange={setPeriode}
        options={PERIODE.map((n) => ({
          value: String(n),
          label: t("c.days", { n }),
        }))}
        className="min-w-[110px]"
      />
    </Field>
  );
}


/** Pembatasan tampilan yang boleh diminta halaman pemanggil. */
export interface OpsiPemilihan {
  /**
   * Bila diisi, hanya gudang berkode ini yang muncul di dropdown -- dan gudang
   * pertama pada daftar itulah yang terpilih saat halaman dibuka.
   *
   * Yang dibatasi hanya DAFTAR PILIHnya. /api/forecast tetap melayani gudang
   * mana pun; pembatasan ini tidak boleh dibaca sebagai kontrol akses.
   */
  kodeGudang?: string[];
  /**
   * Bila diisi, dropdown barang hanya memuat kelompok ini -- diambil bergilir
   * antar kelompok supaya semuanya kebagian. Harus berupa konstanta di luar
   * komponen: array baru pada tiap render akan memicu pengambilan ulang.
   */
  kelompokBarang?: KelompokBarang[];
  /** Bila diisi, dropdown barang dipotong sebanyak ini, yang terbaru bergerak. */
  maksBarang?: number;
}

export interface PemilihanBarang {
  warehouseId: string;
  setWarehouseId: (v: string) => void;
  itemId: string;
  setItemId: (v: string) => void;
  /** "" = semua jenis; selain itu berumur_pakai atau habis_pakai */
  jenis: "" | JenisPemakaian;
  setJenis: (v: "" | JenisPemakaian) => void;
  /** jumlah barang per jenis pada gudang yang dipilih, untuk label dropdown */
  jumlahJenis: { berumur_pakai: number; habis_pakai: number };
  daftarGudang: any[];
  daftarBarang: any[];
  memuatBarang: boolean;
  /** true bila daftar barang sengaja dipotong, sehingga labelnya harus jujur */
  barangDibatasi: boolean;
  /** nama kelompok yang sedang disaring, kosong bila dropdown memuat semuanya */
  namaKelompok: string[];
  /** true bila gudang dan barang sudah terpilih, jadi API boleh dipanggil */
  siap: boolean;
}

/**
 * Pemilihan gudang dan barang, dipakai kedua halaman.
 *
 * Daftar barang WAJIB mengikuti gudang yang sedang dipilih. Sebelumnya kedua
 * dropdown diisi dari sumber terpisah (/api/warehouses dan /api/items) lalu
 * masing-masing mengambil elemen pertama, tanpa jaminan barang itu pernah ada
 * di gudang itu. Dari 8.000 barang x 50 gudang = 400.000 kombinasi, hanya 5,5%
 * yang benar-benar punya pergerakan -- jadi pilihan bawaannya hampir selalu
 * mendarat di kombinasi yang tidak pernah ada, dan halaman menampilkan
 * "Insufficient Data" meski mesin prakiraan dan datanya sehat.
 */
export function usePemilihanBarang({
  kodeGudang,
  kelompokBarang,
  maksBarang,
}: OpsiPemilihan = {}): PemilihanBarang {
  const [warehouseId, setWarehouseId] = useState("");
  const [itemId, setItemId] = useState("");
  const [jenis, setJenis] = useState<"" | JenisPemakaian>("");

  const { data: gudang } = useApi<any>("/api/warehouses", { page_size: 200 });

  /*
   * Apakah penyewa yang sedang dilayani berada DI LUAR lingkup yang ditulis
   * pemanggil?
   *
   * Lingkup yang dulu diisi LINGKUP_SEMENTARA disusun untuk katalog satu
   * penyewa: kode gudangnya
   * WH-CEN-*, kata kelompoknya pompa/bearing/oli. Penyewa Demo memakai kode
   * WH-JKT/WH-SBY/WH-BDG dengan katalog kawat las dan amplas -- tidak satu
   * pun cocok. Bila pembatasan itu tetap dipaksakan, kedua dropdown kosong
   * dan halaman tidak menampilkan apa-apa.
   *
   * Yang digugurkan hanya SARINGAN KELOMPOK, bukan batas jumlahnya.
   *
   * Keduanya sempat digugurkan bersama-sama, dengan alasan bahwa lingkup
   * setengah akan menyisakan penyewa Demo dengan 5 dari 36 barangnya tanpa
   * penjelasan. Alasan itu benar untuk saringan kelompoknya -- "pompa",
   * "bearing", "oli" adalah kata dari katalog SATU penyewa, dan katalog kawat
   * las serta amplas memang nyaris tidak menyentuhnya.
   *
   * Alasan itu TIDAK berlaku untuk `maksBarang`. Batas jumlah tidak
   * mengandung satu pun kata dari katalog mana pun; ia hanya mengambil yang
   * terakhir bergerak, dan itu berarti sama saja pada katalog apa pun. Ikut
   * menggugurkannya membuat penyewa Demo mendapat dropdown berisi 36 barang
   * sementara penyewa lain mendapat 10 -- perbedaan yang tidak pernah
   * diputuskan siapa pun, hanya efek samping dari menggugurkan sepaket.
   */
  const diLuarLingkup = useMemo(() => {
    const semua = (gudang?.items ?? []) as any[];
    if (!kodeGudang || !semua.length) return false;
    return !semua.some((w) => kodeGudang.includes(String(w.code)));
  }, [gudang, kodeGudang]);

  const { items: semuaBarang, loading: memuatBarang } = useBarangGudang(
    warehouseId,
    diLuarLingkup ? undefined : kelompokBarang,
    maksBarang
  );

  /*
   * Penyaring jenis dikerjakan di sini, atas daftar yang sudah ditarik: satu
   * gudang demo berisi puluhan barang, dan jenisnya sudah ikut pada baris
   * /api/inventory. Pilihan awal barang (di bawah) memilih dari daftar yang
   * SUDAH tersaring, sehingga mengganti jenis langsung memindahkan pilihan
   * ke barang yang cocok.
   */
  const daftarBarang = useMemo(
    () => (jenis ? semuaBarang.filter((r) => r.usage_type === jenis) : semuaBarang),
    [semuaBarang, jenis]
  );
  const jumlahJenis = useMemo(
    () => ({
      berumur_pakai: semuaBarang.filter((r) => r.usage_type === "berumur_pakai").length,
      habis_pakai: semuaBarang.filter((r) => r.usage_type === "habis_pakai").length,
    }),
    [semuaBarang]
  );

  /*
   * Penyaringan gudang dikerjakan di sini, bukan dengan parameter q pada API:
   * q hanya menerima satu kata sedangkan yang diminta adalah beberapa gudang
   * tertentu, dan seluruh 50 gudang sudah masuk dalam satu halaman jadi tidak
   * ada panggilan tambahan yang dihemat.
   *
   * useMemo bukan penghematan biaya, melainkan syarat: daftar inilah yang
   * dipakai efek di bawah sebagai dependensi, dan array baru pada tiap render
   * akan membuat efeknya berjalan terus-menerus.
   */
  const daftarGudang = useMemo(() => {
    const semua = (gudang?.items ?? []) as any[];
    if (!kodeGudang) return semua;
    const cocok = semua.filter((w) => kodeGudang.includes(String(w.code)));
    /*
     * Bila TIDAK ADA yang cocok, seluruh gudang ditampilkan.
     *
     * Kode gudang yang dituliskan pemanggil milik satu penyewa saja. Penyewa
     * lain --
     * Demo, yang gudangnya WH-JKT/WH-SBY/WH-BDG -- tidak punya satu pun kode
     * itu, dan saringan yang keras mengosongkan dropdown gudang; itu membuat
     * warehouseId tak pernah terisi, daftar barang tak pernah diambil, dan
     * /api/forecast tak pernah dipanggil. Halaman kosong, tanpa satu pun
     * galat yang menunjuk ke sini.
     *
     * Pembatasan ini soal tampilan, bukan kebenaran angka, jadi ia mengalah
     * pada kenyataan penyewa yang sedang dilayani.
     */
    return cocok.length ? cocok : semua;
  }, [gudang, kodeGudang]);

  // Pilihan awal diambil dari data, bukan ditulis mati.
  useEffect(() => {
    if (!warehouseId && daftarGudang.length) setWarehouseId(String(daftarGudang[0].id));
  }, [daftarGudang, warehouseId]);

  /*
   * Berganti gudang membuat barang yang dipilih bisa jadi tidak ada di sana,
   * jadi pilihannya disetel ulang.
   *
   * Yang dipilih adalah barang dengan pergerakan TERAKHIR paling baru, bukan
   * yang pertama menurut abjad SKU. Sekitar 5.000 pasangan barang/gudang sudah
   * lama tidak bergerak, dan bila kebetulan salah satunya berada di urutan
   * abjad teratas, halaman terbuka dengan "Insufficient Data" -- jawaban yang
   * benar untuk barang itu, tetapi kesan pertama yang keliru tentang sistemnya.
   */
  useEffect(() => {
    if (!daftarBarang.length) return;
    if (itemId && daftarBarang.some((r) => String(r.item_id) === itemId)) return;
    const teraktif = daftarBarang.reduce((a, b) =>
      (b.last_movement_date ?? "") > (a.last_movement_date ?? "") ? b : a
    );
    setItemId(String(teraktif.item_id));
  }, [daftarBarang, itemId]);

  return {
    warehouseId,
    setWarehouseId,
    itemId,
    setItemId,
    jenis,
    setJenis,
    jumlahJenis,
    daftarGudang,
    daftarBarang,
    memuatBarang,
    // Keterangan di layar mengikuti pembatasan yang BENAR-BENAR berlaku.
    // Batas jumlah kini berlaku pada penyewa mana pun, jadi ia tidak lagi
    // bergantung pada dikenalinya kode gudang.
    barangDibatasi: Boolean(maksBarang),
    namaKelompok: diLuarLingkup ? [] : (kelompokBarang ?? []).map((k) => k.nama),
    siap: Boolean(itemId && warehouseId),
  };
}

/*
 * LINGKUP_SEMENTARA DICABUT, 1 September 2026.
 *
 * Konstanta itu membatasi kedua halaman pada dua kode gudang, tiga kelompok
 * kata (pompa/pump, bearing, oli), dan sepuluh barang teraktif. Pembatasan itu
 * masuk akal ketika satu gudang berisi 8.006 barang: dropdown sepanjang itu
 * tidak dapat dipakai, dan sepuluh barang teraktif adalah tebakan yang jauh
 * lebih berguna daripada sepuluh SKU teratas menurut abjad.
 *
 * Katalognya kini dua puluh barang, sepuluh per gudang. Ketiga pembatasan itu
 * berhenti menolong dan mulai MENYEMBUNYIKAN: barang yang namanya tidak memuat
 * pompa, bearing, atau oli -- filter udara, seal, kopling -- tidak akan pernah
 * muncul di dropdown, dan barang kesebelas pada satu gudang ikut terpotong.
 * Keduanya terjadi tanpa satu pun tanda di layar; yang terlihat hanya daftar
 * yang tidak memuat barang yang baru saja dimasukkan.
 *
 * Yang dicabut hanya argumennya. Seluruh kemampuan menyaring tetap ada pada
 * usePemilihanBarang dan tinggal diisi kembali bila suatu saat katalognya
 * membesar lagi.
 */

/** Dua dropdown pemilihan, sebagai kolom pada baris filter halaman. */
export function PemilihBarang({ pilihan }: { pilihan: PemilihanBarang }) {
  const t = useT();
  const {
    warehouseId,
    setWarehouseId,
    itemId,
    setItemId,
    jenis,
    setJenis,
    jumlahJenis,
    daftarGudang,
    daftarBarang,
    memuatBarang,
    barangDibatasi,
    namaKelompok,
  } = pilihan;

  const keteranganDaftar = () => {
    const n = daftarBarang.length;
    if (namaKelompok.length) {
      return t("c.items_group", { n, g: namaKelompok.join(" \u00b7 ") });
    }
    return t(barangDibatasi ? "c.items_recent" : "c.items_in_wh", { n });
  };

  return (
    <>
      <Field label={t("c.warehouse")}>
        <Select
          value={warehouseId}
          onChange={setWarehouseId}
          options={daftarGudang.map((w) => ({
            value: String(w.id),
            label: `${w.code} — ${w.name}`,
          }))}
          className="min-w-[190px]"
        />
      </Field>
      {/*
        Saat daftarnya dipotong, labelnya TIDAK boleh tetap berbunyi "10 di
        gudang ini": gudangnya berisi ratusan barang, dan angka itu akan
        terbaca sebagai jumlah persediaan, bukan sebagai panjang dropdown.
        Bila penyaringannya menurut kelompok, kelompoknya ikut disebut --
        tanpa itu dropdown yang hanya berisi pompa, bearing, dan oli terbaca
        seolah gudangnya memang cuma menyimpan tiga jenis barang.
      */}
      {/* Jenis barang: komponen berumur pakai dijadwalkan, barang habis pakai
          diprakirakan. Bagian dari "prakiraan yang mana", jadi ikut baris filter. */}
      <Field label={t("jenis.label")}>
        <Select
          value={jenis}
          onChange={(v) => setJenis(v as "" | JenisPemakaian)}
          options={[
            { value: "", label: t("jenis.all") },
            {
              value: "berumur_pakai",
              label: `${t("jenis.berumur_pakai")} (${jumlahJenis.berumur_pakai})`,
            },
            {
              value: "habis_pakai",
              label: `${t("jenis.habis_pakai")} (${jumlahJenis.habis_pakai})`,
            },
          ]}
          className="min-w-[170px]"
        />
      </Field>
      <Field label={`${t("c.item")}${daftarBarang.length ? ` (${keteranganDaftar()})` : ""}`}>
        <Select
          value={itemId}
          onChange={setItemId}
          options={
            daftarBarang.length
              ? daftarBarang.map((it) => ({
                  value: String(it.item_id),
                  label: `${it.sku} — ${it.item_name}`,
                }))
              : [{ value: "", label: memuatBarang ? t("c.loading") : t("c.no_items") }]
          }
          className="min-w-[230px]"
        />
      </Field>
    </>
  );
}

/** Kalimat "SKU · Nama · Gudang" di bawah judul halaman. */
export function keteranganBarang(data: {
  item: { sku: string; name: string };
  warehouse: { code: string; name: string };
}) {
  return `${data.item.sku} · ${data.item.name} · ${data.warehouse.code} ${data.warehouse.name}`;
}

/** Lencana jenis barang beserta penjelasannya, untuk judul halaman Prakiraan. */
export function LencanaJenis({ jenis }: { jenis?: JenisPemakaian }) {
  const t = useT();
  if (!jenis) return null;
  const umur = jenis === "berumur_pakai";
  return (
    <span
      title={t(`jenis.hint.${jenis}`)}
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-0.5 t-caption font-medium"
      style={{
        color: "var(--text-primary)",
        background: `color-mix(in srgb, ${umur ? "var(--status-warning)" : "var(--status-good)"} 13%, transparent)`,
        boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${umur ? "var(--status-warning)" : "var(--status-good)"} 30%, transparent)`,
      }}
    >
      {t(`jenis.${jenis}`)}
      <span className="text-muted font-normal">· {t(`jenis.hint.${jenis}`)}</span>
    </span>
  );
}
