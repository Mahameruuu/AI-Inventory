"use client";

/**
 * Peta Transfer Antar Gudang.
 * Inter-warehouse transfer map.
 *
 * SATU PERTANYAAN, DIJAWAB TANPA MEMBACA SATU BARIS TABEL PUN: gudang mana
 * mengirim ke gudang mana, barang apa, berapa unit, dan sudah sampai tahap apa.
 * Daftar kartu di bawahnya menjawab pertanyaan yang sama dengan lengkap; peta
 * ini menjawabnya SEKALI LIHAT, dan itu dua pekerjaan yang berbeda.
 *
 * TIDAK ADA SATU PUN ANGKA YANG LAHIR DI SINI. Kuantitas, status, dan kedua
 * gudang datang jadi dari GET /api/transfers; koordinatnya dari kolom
 * warehouses.latitude/longitude lewat jawaban yang sama. Yang dikerjakan berkas
 * ini hanya menggambar. Bila sebuah gudang belum punya koordinat, rutenya TIDAK
 * digambar dan jumlahnya disebut terus terang di bawah peta -- letak gudang
 * tidak pernah ditebak, karena rute yang berangkat dari kota yang salah terbaca
 * persis sama meyakinkannya dengan rute yang benar.
 *
 * KENAPA LEAFLET MENTAH, BUKAN PEMBUNGKUS REACT. Yang digambar peta ini bukan
 * penanda dan garis lurus biasa: tiap rute adalah busur Bezier berarah dengan
 * dua kepala panah yang berputar mengikuti kemiringan busurnya, dan rute yang
 * sama dengan status berbeda disusun berlapis supaya tidak saling menimpa.
 * Tidak satu pun di antaranya ada pada API deklaratif mana pun, jadi
 * pembungkusnya hanya akan menjadi lapisan yang harus ditembus setiap kali.
 *
 * KENAPA PANEL REACT, BUKAN POPUP LEAFLET. Popup Leaflet dirakit dari string
 * HTML: ia berada di luar jangkauan kamus dwibahasa, di luar sistem warna,
 * dan setiap nama gudang yang masuk ke dalamnya harus dilolosi tangan. Panel
 * yang berdiri di samping peta memakai komponen yang sama dengan seluruh
 * aplikasi, dan rincian barangnya dapat diambil malas lewat useApi seperti di
 * tempat lain.
 *
 * SSR: berkas ini TIDAK boleh diimpor dari server. Leaflet menyentuh
 * `document` saat modulnya dievaluasi, jadi pemanggilnya wajib memuatnya lewat
 * next/dynamic dengan ssr:false -- lihat transfer-sections.tsx.
 */

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Ban,
  Boxes,
  Crosshair,
  Layers,
  MapPin,
  Minus,
  MoveRight,
  PackageOpen,
  Plane,
  Plus,
  Ship,
  Sparkles,
  Truck,
  Warehouse,
  X,
} from "lucide-react";

import { PillKeputusan, PillTahap, TAHAP } from "@/components/status";
import { Empty, ErrorBox, Loading } from "@/components/ui";
import { apiGet, useApi } from "@/lib/api";
import { dateLabel, num } from "@/lib/format";
import { useT } from "@/lib/i18n";
import {
  GudangApi,
  Kotak,
  PenandaGudang,
  RuteTransfer,
  UsulanBaris,
  UsulanRute,
  kotak,
  susunGudang,
  susunLintasan,
  susunRute,
  susunUsulan,
  rencanaKendaraan,
  terapkanLapis,
} from "@/lib/peta";
import {
  BarisTransfer,
  DetailDokumenTransfer,
  DokumenTransfer,
  KandidatTransfer,
  ModaAngkut,
  StatusTransfer,
} from "@/lib/transfer-types";

/*
 * PETAK PETA: OpenStreetMap baku. Tanpa kunci API, tanpa akun, tanpa langganan.
 *
 * SUDAH DICOBA DAN DITOLAK: kartografi "Voyager" milik CARTO
 * (basemaps.cartocdn.com), yang tata warnanya jauh lebih dekat ke aplikasi peta
 * harian. Layanan itu KINI MENUNTUT KUNCI API -- petaknya tetap terkirim, hanya
 * saja setiap ubinnya bertuliskan "API KEY REQUIRED" melintang. Kegagalan
 * seperti itu tidak terbit sebagai galat di mana pun: cacah petak yang termuat
 * tetap benar, tidak ada permintaan yang gagal, dan hanya tangkapan layar yang
 * memperlihatkannya. Itulah sebabnya setiap perubahan pada peta ini diperiksa
 * dengan mata, bukan dengan cacah elemen.
 *
 * Yang mendekatkan tampilannya ke peta harian karena itu bukan sumber petaknya,
 * melainkan peredaman warnanya di globals.css -- lihat catatan di sana.
 */
const PETAK = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const ATRIBUSI =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>';

/** Larik kosong tetap; menjaga identitas prop saat lapisan usulan dimatikan. */
const KOSONG_USULAN: UsulanRute[] = [];


/**
 * Sisa ruang di sekeliling isi peta saat pandangannya disetel.
 *
 * `denganPanel` MENYISIHKAN TEMPAT YANG DITEMPATI PANEL RINCIAN, dan itu bukan
 * kerapian: tanpa itu, memilih sebuah rute memperbesar peta ke rute itu lalu
 * menutupi salah satu ujungnya dengan panel yang baru saja terbuka -- gudang
 * penerima hilang persis pada saat pembacanya menanyakannya. Leaflet menerima
 * sela yang berbeda di tiap sisi, jadi yang bergeser cukup titik tengahnya.
 *
 * Ambangnya 1024px, sama dengan titik henti tempat panel berpindah dari lembar
 * di tepi bawah menjadi kolom di sisi kanan (lihat globals.css).
 */
function sela(denganPanel = false): L.FitBoundsOptions {
  if (!denganPanel) return { padding: [56, 56], maxZoom: 11 };
  const lebar = typeof window === "undefined" ? 1280 : window.innerWidth;
  // Di bawah 1024px panel berdiri DI BAWAH peta, bukan di atasnya, jadi tidak
  // ada yang perlu disisihkan -- selanya kembali seperti biasa.
  return lebar >= 1024
    ? { paddingTopLeft: [56, 56], paddingBottomRight: [388, 56], maxZoom: 11 }
    : { padding: [40, 40], maxZoom: 11 };
}

/** Apa yang sedang dibuka panel di samping peta. */
type Fokus =
  | { jenis: "gudang"; id: number }
  | { jenis: "rute"; kunci: string }
  | { jenis: "usulan"; kunci: string }
  | null;

export interface PetaTransferProps {
  dokumen: DokumenTransfer[];
  gudang: GudangApi[];
  /** dokumen yang sedang disorot, dari daftar kartu maupun dari peta */
  pilih: number | null;
  onPilih: (id: number | null, dari: "peta") => void;
  memuat: boolean;
  /**
   * Baris rekomendasi dari GET /api/transfer, apa adanya.
   *
   * Penyaringannya dikerjakan `susunUsulan()`, bukan pemanggil: aturan
   * "hanya TRANSFER dan TRANSFER_SEBAGIAN yang boleh digambar" adalah aturan
   * PETA, dan menaruhnya di halaman berarti setiap pemasang peta berikutnya
   * harus mengingatnya sendiri.
   */
  usulan: BarisTransfer[];
  /*
   * Kegagalan mengambil daftar gudang, bila ada.
   *
   * DIPISAH DARI "belum ada koordinat", dan pemisahan itu penting. Keduanya
   * sama-sama berakhir dengan nol penanda, tetapi jawabannya berlawanan:
   * yang satu diperbaiki dengan mengisi lintang/bujur pada Master Gudang, yang
   * satu lagi tidak dapat diperbaiki siapa pun di layar ini. Menyamakannya
   * mengirim orang mengisi koordinat yang sebenarnya sudah terisi.
   */
  galat?: string | null;
}

/* ------------------------------------------------------------------ */
/* Ikon                                                                */
/* ------------------------------------------------------------------ */

/**
 * Penanda gudang: pin bertumpu pada titiknya, kode gudang tercetak di bawahnya.
 *
 * KODENYA IKUT, bukan hanya pinnya. Dua pin tanpa nama pada peta Jawa menuntut
 * pembacanya mengenali kota dari bentuk garis pantai; kode yang tercetak
 * menjawabnya tanpa satu klik pun, dan kode itu pula yang tercetak pada surat
 * jalan.
 */
function ikonGudang(g: PenandaGudang, aktif: boolean): L.DivIcon {
  const lalu = g.keluar + g.masuk;
  return L.divIcon({
    className: "pt-pin-wrap",
    iconSize: [0, 0],
    html: `
      <span class="pt-pin${aktif ? " is-aktif" : ""}${lalu ? "" : " is-sepi"}">
        <span class="pt-pin-badan">
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none"
               stroke="currentColor" stroke-width="2.2"
               stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M22 8.35V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8.35"/>
            <path d="M1 8.27 12 2l11 6.27"/>
            <path d="M6 18h12"/><path d="M6 14h12"/>
          </svg>
        </span>
        <span class="pt-pin-nama">${teksAman(g.kode)}</span>
      </span>`,
  });
}

interface Truk {
  truk: L.Marker;
  lin: ReturnType<typeof susunLintasan>;
  geser: number;
  arah: 1 | -1;
}

/**
 * Truk boks tampak samping, berwarna sesuai tahap dokumennya.
 *
 * Berbalik mendatar (bukan berputar) bila jalannya ke arah barat: truk yang
 * berputar 180 derajat berjalan terbalik dengan roda di atas, sedangkan yang
 * dibalik cermin tetap tegak -- cara yang sama dipakai semua aplikasi kurir.
 * Kabin selalu di sisi depan.
 */
function ikonTruk(arah: 1 | -1, status: StatusTransfer, aktif: boolean,
                  moda: ModaAngkut = "darat"): L.DivIcon {
  return L.divIcon({
    className: "pt-truk-wrap",
    iconSize: [0, 0],
    html: `
      <span class="pt-truk pt-warna--${status}${aktif ? " is-aktif" : ""}"
            style="--pt-arah:${arah}">
        ${BADAN_KENDARAAN[moda]}
      </span>`,
  });
}

/**
 * Badan kendaraan menurut moda: truk untuk darat, kapal untuk laut, pesawat
 * untuk udara. Truk yang "melaju" di atas laut Makassar terbaca sebagai galat.
 */
const BADAN_KENDARAAN: Record<ModaAngkut, string> = {
  darat: `
        <svg viewBox="0 0 34 21" width="34" height="21" aria-hidden="true">
          <rect x="1" y="2" width="21" height="13" rx="2" fill="currentColor"/>
          <path d="M23 6.2h5a2 2 0 0 1 1.6.8l3 4A2 2 0 0 1 33 12.2V15H23z" fill="currentColor"/>
          <path d="M23 6.2h5a2 2 0 0 1 1.6.8l3 4A2 2 0 0 1 33 12.2V15H23z" fill="#000" opacity=".16"/>
          <path d="M25 7.9h3l2.3 3.1H25z" fill="#fff" opacity=".92"/>
          <rect x="3.5" y="4.5" width="15" height="1.6" rx=".8" fill="#fff" opacity=".55"/>
          <circle cx="8" cy="16" r="3" fill="#1f2937" stroke="#fff" stroke-width="1.3"/>
          <circle cx="27" cy="16" r="3" fill="#1f2937" stroke="#fff" stroke-width="1.3"/>
        </svg>`,
  laut: `
        <svg viewBox="0 0 34 21" width="34" height="21" aria-hidden="true">
          <rect x="6" y="3" width="6" height="6" rx="1" fill="currentColor"/>
          <rect x="13" y="5" width="6" height="4" rx="1" fill="currentColor" opacity=".8"/>
          <rect x="20" y="5" width="6" height="4" rx="1" fill="currentColor" opacity=".8"/>
          <path d="M2 10h30l-4.2 6.2A2.5 2.5 0 0 1 25.7 17.3H8.3a2.5 2.5 0 0 1-2.1-1.1z" fill="currentColor"/>
          <path d="M2 10h30l-1 1.6H3z" fill="#000" opacity=".18"/>
          <path d="M3 19.4c2 0 2-1 4-1s2 1 4 1 2-1 4-1 2 1 4 1 2-1 4-1 2 1 4 1 2-1 4-1"
                fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity=".6"/>
        </svg>`,
  udara: `
        <svg viewBox="0 0 34 21" width="34" height="21" aria-hidden="true">
          <path d="M33 10.5c0 1-1.6 1.7-3 1.7H21l-6 6.3h-3l2.6-6.3H8l-2.3 2.6H3.5l1.3-2.6-1.3-2.6h2.2L8 10.8h6.6L12 4.5h3l6 6.3h9c1.4 0 3 .7 3 1.7z"
                fill="currentColor" transform="translate(0 -1.5)"/>
          <path d="M8 10.8h6.6" stroke="#fff" stroke-width=".8" opacity=".5" transform="translate(0 -1.5)"/>
        </svg>`,
};

/**
 * Kepala panah usulan: BERONGGA, bukan padat.
 *
 * Bentuknya yang membedakannya dari panah dokumen, bukan hanya warnanya --
 * segitiga bergaris tanpa isi terbaca sebagai "belum terisi" pada layar mana
 * pun, termasuk yang warnanya tidak dapat dibedakan pembacanya.
 */
function ikonPanahUsulan(sudut: number, aktif: boolean): L.DivIcon {
  return L.divIcon({
    className: "pt-panah-wrap",
    iconSize: [0, 0],
    html: `
      <span class="pt-panah pt-panah--usul${aktif ? " is-aktif" : ""}"
            style="--pt-sudut:${sudut.toFixed(2)}deg">
        <svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true">
          <path d="M2.1 1.9 9.8 6 2.1 10.1 3.7 6z" fill="none"
                stroke="currentColor" stroke-width="1.6"
                stroke-linejoin="round"/>
        </svg>
      </span>`,
  });
}

/** Label usulan: berbingkai putus-putus, dengan tanda mesin di depannya. */
function ikonLabelUsulan(u: UsulanRute, aktif: boolean): L.DivIcon {
  const banyak = u.baris.length > 1 ? `<span class="pt-label-n">\u00d7${u.baris.length}</span>` : "";
  return L.divIcon({
    className: "pt-label-wrap",
    iconSize: [0, 0],
    html: `
      <span class="pt-label pt-label--usul${aktif ? " is-aktif" : ""}">
        <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor"
             stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>
        </svg>
        <span class="pt-label-qty">${teksAman(num(u.totalQty))}</span>${banyak}
      </span>`,
  });
}

/**
 * Label jumlah di puncak busur; menyebut cacah dokumen bila lebih dari satu.
 *
 * `ringkas` (bila jalurnya sudah dikenal) menambah dua baris di bawah jumlah:
 * lama tempuh dan total biaya, lalu solar dan tol. Ini yang membuat hasil
 * rekomendasi terbaca DI PETA tanpa harus mengklik rute dulu -- panel rincian
 * hanya terbuka bagi yang mengkliknya, dan biaya yang tersembunyi di sana tidak
 * pernah terlihat oleh yang sekadar memandang peta.
 */
function ikonLabel(r: RuteTransfer, aktif: boolean, ringkas: [string, string] | null): L.DivIcon {
  const banyak = r.dokumen.length > 1 ? `<span class="pt-label-n">×${r.dokumen.length}</span>` : "";
  const baris = `<span class="pt-label-baris"><span class="pt-label-qty">${teksAman(num(r.totalQty))}</span>${banyak}</span>`;
  const sub = ringkas
    ? `<span class="pt-label-sub">${teksAman(ringkas[0])}</span><span class="pt-label-sub pt-label-sub--rinci">${teksAman(ringkas[1])}</span>`
    : "";
  return L.divIcon({
    className: "pt-label-wrap",
    iconSize: [0, 0],
    html: `
      <span class="pt-label pt-warna--${r.status}${aktif ? " is-aktif" : ""}${ringkas ? " pt-label--dua" : ""}">
        ${baris}${sub}
      </span>`,
  });
}

/** Rupiah ringkas untuk label peta: "Rp 2,76 jt" atau "Rp 850 rb". */
function rpRingkas(n: number): string {
  return n >= 1_000_000 ? `Rp ${num(n / 1_000_000, 2)} jt` : `Rp ${num(n / 1000)} rb`;
}

/**
 * Pelolosan untuk teks yang masuk ke HTML ikon.
 *
 * Yang lewat sini hanya kode gudang dan angka yang sudah diformat, tetapi kode
 * gudang adalah master data yang diketik orang -- dan satu-satunya cara
 * memastikan ia tidak pernah menjadi markup adalah tidak pernah
 * mempercayainya.
 */
function teksAman(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    c === "&" ? "&amp;" : c === "<" ? "&lt;" : c === ">" ? "&gt;" : c === '"' ? "&quot;" : "&#39;",
  );
}

/* ------------------------------------------------------------------ */
/* Jalan sungguhan                                                     */
/* ------------------------------------------------------------------ */

/*
 * Geometri jalan per pasangan gudang. Disimpan di tingkat modul: berpindah
 * halaman dan kembali tidak menanyakan lagi jalan yang sudah dikenal. `null`
 * berarti penyedia jalan gagal DALAM SESI INI; muat ulang halaman mencoba lagi.
 * Peta tidak menunggu jawabannya -- busur tergambar lebih dulu dan jalan
 * menggantikannya begitu tiba.
 */
const CACHE_JALAN = new Map<string, PaketJalan | null>();
const SEDANG_DIAMBIL = new Set<string>();

/**
 * Satu pilihan jalur dari OSRM. Durasi = jalan lengang TANPA lalu lintas
 * langsung; tidak ada penilaian keamanan di mana pun -- sumbernya tidak
 * memilikinya, dan label yang dikarang lebih berbahaya daripada tidak ada.
 */
interface OpsiJalan {
  points: [number, number][];
  distance_m: number;
  duration_s: number;
  tercepat: boolean;
  terpendek: boolean;
  /** panjang ruas tol menurut nama ruasnya; bisa kurang dari sebenarnya */
  tol_m: number;
  /** ada penyeberangan feri; tarifnya TIDAK ikut dihitung */
  feri: boolean;
  /** kota perantara bila jalur ini dipaksa lewat sana; null = jalan langsung */
  via?: string | null;
  /** estimasi rupiah dari asumsi di server, dibulatkan ke ribuan */
  biaya: { liter: number; bbm: number; tol: number; waktu: number; total: number };
}

/** Alasan rekomendasi: kode + angka; kalimatnya disusun di layar (kamus dwibahasa). */
interface AlasanJalur {
  kode:
    | "satu_jalur"
    | "tercepat"
    | "tercepat_dan_hemat"
    | "hemat_walau_lebih_lama"
    | "tol_lebih_banyak"
    | "ada_feri";
  lawan?: number;
  hemat_rp?: number;
  hemat_detik?: number;
  lebih_lama_detik?: number;
}

/** Asumsi biaya yang dipakai server; ditampilkan supaya tak dikira tarif resmi. */
interface AsumsiJalur {
  golongan_tol: string;
  km_per_liter: number;
  harga_solar_per_liter: number;
  tarif_tol_per_km: number;
  biaya_per_jam: number;
}

interface PaketJalan {
  opsi: OpsiJalan[];
  rekomendasi: { index: number; alasan: AlasanJalur[] };
  asumsi: AsumsiJalur;
}

interface JawabanJalur extends Partial<PaketJalan> {
  ada: boolean;
}

/** Jalur yang tampil: pilihan orangnya, atau rekomendasi bila belum memilih. */
function indeksJalur(paket: PaketJalan, pilih: number | undefined): number {
  return pilih !== undefined && paket.opsi[pilih] ? pilih : paket.rekomendasi.index;
}

function salinanJalan(): Map<string, PaketJalan> {
  const m = new Map<string, PaketJalan>();
  for (const [k, v] of CACHE_JALAN) if (v) m.set(k, v);
  return m;
}

/** 9,2 jam -> "9 j 12 mnt"; di bawah satu jam -> "45 mnt". */
function lamaTempuh(detik: number, satuanJam: string, satuanMenit: string): string {
  const menit = Math.max(1, Math.round(detik / 60));
  const j = Math.floor(menit / 60);
  const m = menit % 60;
  return j ? `${j} ${satuanJam}${m ? ` ${m} ${satuanMenit}` : ""}` : `${m} ${satuanMenit}`;
}

/** Kunci pasangan berarah, sama dengan kunci di terapkanLapis(). */
const kunciJalan = (b: { dariId: number; keId: number }) => `${b.dariId}>${b.keId}`;

/**
 * Paket jalan untuk arah SEBALIKNYA: garis yang sama dibaca dari ujung.
 *
 * Jalan Surabaya->Jakarta dan Jakarta->Surabaya ditanyakan SEKALI (arah
 * kanonik: id gudang kecil ke besar), lalu arah lawannya dibalik dari
 * jawaban itu. Bila keduanya ditanyakan sendiri-sendiri, OSRM boleh memberi
 * alternatif yang berbeda per arah, atau satu arah gagal dan jatuh ke busur
 * sementara yang lain menyusuri jalan -- dan pembaca melihat dua kiriman di
 * antara gudang yang sama tampil dengan cara yang berbeda. Jarak, durasi,
 * biaya, dan urutan pilihan tidak berubah; hanya titiknya yang dibalik.
 */
function balikPaket(p: PaketJalan): PaketJalan {
  return { ...p, opsi: p.opsi.map((o) => ({ ...o, points: [...o.points].reverse() })) };
}

/** Satu putaran penuh kendaraan pada rute berstatus Dikirim, dalam detik. */
const PUTARAN_TRUK_DETIK = 16;

/* ------------------------------------------------------------------ */
/* Peta                                                                */
/* ------------------------------------------------------------------ */

export default function PetaTransfer({
  dokumen,
  gudang,
  pilih,
  onPilih,
  memuat,
  usulan: barisUsulan,
  galat = null,
}: PetaTransferProps) {
  const t = useT();

  /*
   * KONTAINER PETA DIPEGANG SEBAGAI KEADAAN, BUKAN SEBAGAI ref BIASA.
   *
   * Komponen ini punya tiga jalan keluar lebih awal -- galat, sedang memuat,
   * dan belum ada gudang berkoordinat -- dan pada ketiganya <div> peta TIDAK
   * dirender sama sekali. Sebuah useRef yang dipasangkan padanya karena itu
   * masih null pada render pertama, sementara efek pembuatan peta dengan
   * daftar kebergantungan kosong sudah terlanjur berjalan sekali lalu tidak
   * pernah berjalan lagi: peta tidak pernah dibuat, dan yang tersisa di layar
   * adalah bingkai kosong lengkap dengan judul, legenda, dan tombol -- tanpa
   * satu pun galat yang terbit.
   *
   * Itu persis yang terjadi begitu peta naik ke atas pemilih layar (4 September
   * 2026): sebelumnya ia baru dipasang setelah datanya tiba, sehingga jalan
   * keluar "sedang memuat" tidak pernah dilewatinya. Callback ref menyimpan
   * elemennya sebagai keadaan, jadi efeknya berjalan tepat ketika <div>-nya
   * benar-benar ada.
   */
  const [wadah, setWadah] = useState<HTMLDivElement | null>(null);
  const peta = useRef<L.Map | null>(null);
  const lapisan = useRef<L.LayerGroup | null>(null);
  const animasi = useRef(0);
  const kurangiGerak = useMemo(
    () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
    [],
  );
  useEffect(
    () => () => {
      if (animasi.current) cancelAnimationFrame(animasi.current);
    },
    [],
  );
  const [siap, setSiap] = useState(false);
  const [fokus, setFokus] = useState<Fokus>(null);
  const [petunjukGulir, setPetunjukGulir] = useState(false);
  const [tampilUsulan, setTampilUsulan] = useState(true);

  /*
   * Penangan klik latar peta dipasang SEKALI saat peta dibuat, jadi ia akan
   * memegang `onPilih` versi render pertama selamanya. Ref ini yang membuatnya
   * selalu memanggil yang terbaru -- tanpa itu, mengklik latar peta memanggil
   * penutupan basi dan sorotan pada kartu tidak pernah ikut lepas.
   */
  const onPilihRef = useRef(onPilih);
  useEffect(() => {
    onPilihRef.current = onPilih;
  }, [onPilih]);

  /*
   * YANG DIGAMBAR HANYA DOKUMEN YANG MASIH HIDUP -- diajukan, disetujui,
   * dikirim -- ditambah dokumen yang sedang dipilih, apa pun tahapnya.
   *
   * Arsip transfer setahun berisi ratusan dokumen selesai atau batal; menggambar
   * busur untuk masing-masingnya memenuhi peta dengan garis yang tidak menjawab
   * "apa yang sedang bergerak". Dokumen selesai tetap ada di daftar kartu, dan
   * begitu dipilih ia tergambar (tanpa kendaraan) supaya jalurnya dapat dilihat.
   */
  const dokumenPeta = useMemo(
    () =>
      dokumen.filter(
        (d) =>
          d.status === "draft" ||
          d.status === "approved" ||
          d.status === "in_transit" ||
          d.id === pilih,
      ),
    [dokumen, pilih],
  );

  const { penanda, tanpaKoordinat: gudangTanpaKoordinat } = useMemo(
    () => susunGudang(gudang, dokumenPeta),
    [gudang, dokumenPeta],
  );
  const { rute, tanpaKoordinat: dokumenTanpaKoordinat } = useMemo(
    () => susunRute(dokumenPeta),
    [dokumenPeta],
  );

  const [opsiJalan, setOpsiJalan] = useState<ReadonlyMap<string, PaketJalan>>(() => salinanJalan());
  // Jalur yang dipilih per pasangan gudang; bawaannya yang direkomendasikan AI.
  // Pilihan ini hanya mengubah TAMPILAN peta -- tidak disimpan pada dokumen.
  const [pilihJalur, setPilihJalur] = useState<Readonly<Record<string, number>>>({});

  const jalan = useMemo(() => {
    const m = new Map<string, [number, number][]>();
    for (const [k, paket] of opsiJalan) {
      m.set(k, paket.opsi[indeksJalur(paket, pilihJalur[k])].points);
    }
    return m;
  }, [opsiJalan, pilihJalur]);

  const { usulan, usulanTanpaKoordinat } = useMemo(() => {
    const koordinat = new Map<number, [number, number]>(
      penanda.map((p) => [p.id, [p.lat, p.lon] as [number, number]]),
    );
    const hasil = susunUsulan(barisUsulan, koordinat);
    /*
     * DOKUMEN LEBIH DULU, usulan sesudahnya. Lapisnya ditetapkan atas gabungan
     * keduanya supaya busur usulan Surabaya->Jakarta tidak menempati garis yang
     * persis sama dengan dokumen Surabaya->Jakarta yang sudah berjalan. Yang
     * benar-benar bergerak karena itu selalu paling dekat ke garis lurus, dan
     * usulan mengambang di luarnya -- urutan yang juga terbaca sebagai
     * "yang ini nyata, yang itu belum".
     */
    terapkanLapis([...rute, ...hasil.usulan], jalan);
    return { usulan: hasil.usulan, usulanTanpaKoordinat: hasil.tanpaKoordinat };
    // `jalan` ikut kebergantungan: begitu jalan sungguhan tiba, geometri seluruh
    // rute disusun ulang dan hasil di bawah ini mengalir ke penggambar.
  }, [barisUsulan, penanda, rute, jalan]);

  /*
   * Mengambil jalan untuk tiap pasangan gudang yang belum dikenal. Tiap pasangan
   * ditanyakan sekali, jawabannya disimpan di server (road_route_cache) dan di
   * modul ini. Kegagalan bukan galat layar: rute tetap tergambar sebagai busur.
   */
  const terpasang = useRef(true);
  useEffect(() => {
    terpasang.current = true;
    return () => {
      terpasang.current = false;
    };
  }, []);

  /*
   * Penanda `terpasang` milik KOMPONEN, bukan milik efek: efek ini berjalan
   * ulang setiap kali `rute`/`usulan` berganti, dan bendera per-efek akan
   * membuang jawaban yang tiba setelah putaran berikutnya dimulai -- padahal
   * pasangannya sudah tercatat sebagai "sedang diambil" dan tak akan ditanya
   * lagi.
   */
  useEffect(() => {
    // Kunci = arah kanonik (id kecil -> besar); arah lawannya diturunkan darinya.
    const perlu = new Map<string, { dari: [number, number]; ke: [number, number]; balik: string }>();
    // Jalan sungguhan hanya ditanyakan untuk rute darat dan usulan: kapal dan
    // pesawat tidak lewat jalan, dan OSRM tidak punya jawaban antarpulau.
    for (const b of [
      ...rute.filter((r) => r.moda === "darat"),
      ...usulan.filter((u) => !u.moda || u.moda === "darat"),
    ]) {
      const k = kunciJalan(b);
      if (CACHE_JALAN.has(k) || SEDANG_DIAMBIL.has(k)) continue;
      const maju = b.dariId <= b.keId;
      const kanonik = maju ? k : kunciJalan({ dariId: b.keId, keId: b.dariId });
      const lawan = maju ? kunciJalan({ dariId: b.keId, keId: b.dariId }) : k;
      if (CACHE_JALAN.has(kanonik) || SEDANG_DIAMBIL.has(kanonik)) continue;
      perlu.set(kanonik, {
        dari: maju ? b.dari : b.ke,
        ke: maju ? b.ke : b.dari,
        balik: lawan,
      });
    }
    for (const [k, { dari, ke, balik }] of perlu) {
      SEDANG_DIAMBIL.add(k);
      SEDANG_DIAMBIL.add(balik);
      apiGet<JawabanJalur>("/api/transfer/jalur", {
        dari_lat: dari[0],
        dari_lon: dari[1],
        ke_lat: ke[0],
        ke_lon: ke[1],
      })
        .then((r) => {
          const paket: PaketJalan | null =
            r.ada && r.opsi?.length && r.rekomendasi && r.asumsi
              ? { opsi: r.opsi, rekomendasi: r.rekomendasi, asumsi: r.asumsi }
              : null;
          CACHE_JALAN.set(k, paket);
          CACHE_JALAN.set(balik, paket ? balikPaket(paket) : null);
        })
        .catch(() => {
          CACHE_JALAN.set(k, null);
          CACHE_JALAN.set(balik, null);
        })
        .finally(() => {
          SEDANG_DIAMBIL.delete(k);
          SEDANG_DIAMBIL.delete(balik);
          if (terpasang.current) setOpsiJalan(salinanJalan());
        });
    }
  }, [rute, usulan]);

  // Ada rute yang jalannya gagal diambil, sehingga masih berupa garis perkiraan.
  const adaGarisKira = [
    ...rute.filter((r) => r.moda === "darat"),
    ...usulan.filter((u) => !u.moda || u.moda === "darat"),
  ].some(
    (b) => CACHE_JALAN.get(kunciJalan(b)) === null,
  );

  const usulanTampak = tampilUsulan ? usulan : KOSONG_USULAN;

  /** Kotak yang memuat seluruh gudang dan seluruh busur. */
  const seluruhnya = useMemo<Kotak | null>(() => {
    const titik: [number, number][] = penanda.map((p) => [p.lat, p.lon]);
    /*
     * Gabungan SEMUA pilihan jalur, bukan jalur yang sedang dipilih. Kotak ini
     * menentukan pandangan awal, dan pandangan awal disetel ulang setiap kali
     * kotaknya berubah: bila ia mengikuti pilihan, memilih jalur lain akan
     * melempar peta kembali ke tampilan penuh di tengah pekerjaan pembacanya.
     */
    for (const b of [...rute, ...usulanTampak]) {
      const lewatJalan = !("moda" in b) || !b.moda || b.moda === "darat";
      const paket = lewatJalan ? opsiJalan.get(kunciJalan(b)) : undefined;
      if (paket) for (const o of paket.opsi) titik.push(...o.points);
      else titik.push(...b.geometri.titik);
    }
    return kotak(titik);
  }, [penanda, rute, usulanTampak, opsiJalan]);

  /* ---------------- peta dibuat sekali ---------------- */

  useEffect(() => {
    if (!wadah || peta.current) return;

    const m = L.map(wadah, {
      // Kendali bawaan dimatikan; penggantinya tombol React di kanan bawah,
      // di tempat tangan mencarinya pada aplikasi peta mana pun.
      zoomControl: false,
      attributionControl: true,
      // Roda mouse ditangani sendiri di bawah (Ctrl + gulir), bukan oleh
      // Leaflet: peta ini berdiri di tengah halaman yang lebih panjang dari
      // layar, dan gulungan yang tersedot menjadi zoom membuat pembacanya
      // kehilangan tempatnya di halaman.
      scrollWheelZoom: false,
      // Seret, klik ganda, dan cubit dua jari tetap seperti bawaannya --
      // itulah gerakan yang sudah dikenal semua orang dari aplikasi peta.
      worldCopyJump: true,
    });
    m.setView([-2.5, 118], 4);

    L.tileLayer(PETAK, { attribution: ATRIBUSI, maxZoom: 19 }).addTo(m);
    lapisan.current = L.layerGroup().addTo(m);

    // Klik pada latar peta melepas pilihannya: panel tertutup, busur kembali
    // setipis yang lain, dan sorotan pada kartu di bawah ikut lepas. Jalan
    // keluar yang sama dengan yang sudah dikenal orang dari peta mana pun --
    // dan ketiganya harus lepas bersama, karena satu kartu yang tetap tersorot
    // sesudah panelnya tertutup menunjuk sesuatu yang tidak lagi ada di peta.
    m.on("click", () => {
      setFokus(null);
      onPilihRef.current(null, "peta");
    });

    peta.current = m;
    setSiap(true);

    return () => {
      m.remove();
      peta.current = null;
      lapisan.current = null;
      setSiap(false);
    };
  }, [wadah]);

  /* ---------------- ukurannya ikut wadahnya ---------------- */

  useEffect(() => {
    if (!siap || !wadah || !peta.current) return;
    // Peta yang dirender saat wadahnya masih 0 piksel -- di dalam tab yang
    // belum terbuka, atau sebelum tata letak selesai -- menggambar petak abu
    // yang tidak pernah pulih sendiri. invalidateSize() pada setiap perubahan
    // ukuran menyelesaikan keduanya sekaligus, termasuk saat sidebar diciutkan.
    const ro = new ResizeObserver(() => peta.current?.invalidateSize());
    ro.observe(wadah);
    return () => ro.disconnect();
  }, [siap, wadah]);

  /* ---------------- roda: Ctrl + gulir memperbesar ---------------- */

  useEffect(() => {
    if (!siap || !wadah) return;
    const el = wadah;
    let jeda: ReturnType<typeof setTimeout> | undefined;

    const roda = (e: WheelEvent) => {
      const m = peta.current;
      if (!m) return;

      // Cubit dua jari pada trackpad tiba sebagai peristiwa roda ber-ctrlKey,
      // jadi satu cabang ini melayani keduanya sekaligus: Ctrl + gulir pada
      // tetikus, dan cubit pada trackpad.
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        m.setZoomAround(m.mouseEventToLatLng(e), m.getZoom() + (e.deltaY < 0 ? 1 : -1));
        return;
      }

      // Gulungan biasa dibiarkan lewat -- halaman tetap bergulir seperti
      // seharusnya -- dan yang muncul hanya kalimat yang menyebutkan jalan
      // memperbesarnya.
      setPetunjukGulir(true);
      clearTimeout(jeda);
      jeda = setTimeout(() => setPetunjukGulir(false), 1400);
    };

    el.addEventListener("wheel", roda, { passive: false });
    return () => {
      el.removeEventListener("wheel", roda);
      clearTimeout(jeda);
    };
  }, [siap, wadah]);

  /* ---------------- gambar ulang ---------------- */

  const gambar = useCallback(() => {
    const grup = lapisan.current;
    if (!grup) return;
    grup.clearLayers();
    if (animasi.current) cancelAnimationFrame(animasi.current);
    animasi.current = 0;
    const armada: Truk[] = [];

    const ruteAktif =
      fokus?.jenis === "rute"
        ? fokus.kunci
        : pilih !== null
          ? (rute.find((r) => r.dokumen.some((d) => d.id === pilih))?.kunci ?? null)
          : null;
    const usulanAktif = fokus?.jenis === "usulan" ? fokus.kunci : null;

    /*
     * USULAN DIGAMBAR LEBIH DULU, jadi ia berada DI BAWAH busur dokumen.
     * Leaflet menumpuk menurut urutan penambahan di dalam satu panel, dan
     * urutan itu harus mengikuti artinya: yang sudah disetujui manusia tidak
     * boleh tertutup oleh yang baru diusulkan mesin.
     */
    for (const u of usulanTampak) {
      const aktif = u.kunci === usulanAktif;
      const geo = u.geometri;

      if (aktif) {
        L.polyline(geo.titik, { className: "pt-halo pt-halo--usul", interactive: false }).addTo(grup);
      }

      L.polyline(geo.titik, {
        className: `pt-usul${aktif ? " is-aktif" : ""}`,
        interactive: false,
      }).addTo(grup);

      const bidikUsul = L.polyline(geo.titik, {
        className: "pt-bidik",
        interactive: true,
        bubblingMouseEvents: false,
      }).addTo(grup);
      bidikUsul.on("click", () => bukaUsulan(u));

      for (const pnh of geo.panah) {
        L.marker(pnh.titik, {
          icon: ikonPanahUsulan(pnh.sudut, aktif),
          interactive: false,
          keyboard: false,
        }).addTo(grup);
      }

      /*
       * USULAN TIDAK PUNYA KENDARAAN. Ia saran mesin, bukan kiriman: belum ada
       * barang yang bergerak, dan truk yang melaju di atasnya membuat pembaca
       * mengira ada pengiriman berjalan. Sampai 29 September 2026 usulan yang
       * dipilih ikut memiliki truk yang melaju; hasilnya, memilih satu usulan
       * lalu mengajukannya menampilkan dua kendaraan bergerak di jalan yang
       * sama -- yang satu milik saran, yang satu milik dokumen. Kendaraan hanya
       * ada untuk dokumen (lihat blok kendaraan di bawah).
       */
      const labelUsul = L.marker(geo.puncak, {
        icon: ikonLabelUsulan(u, aktif),
        interactive: true,
        keyboard: false,
        riseOnHover: true,
      }).addTo(grup);
      labelUsul.on("click", () => bukaUsulan(u));
    }

    for (const r of rute) {
      const aktif = r.kunci === ruteAktif;
      const geo = r.geometri;

      /*
       * SATU GARIS PER RUTE. Jalur alternatif OSRM tidak lagi digambar di peta:
       * empat garis dari satu pasangan gudang -- dikali setiap tahap, dikali
       * arah pulang -- membuat peta terbaca sebagai jaring jalan, bukan
       * sebagai "apa yang sedang dikirim". Alternatifnya tetap dapat dipilih
       * pada panel rincian rute, dan pilihan itu menggantikan garis yang
       * digambar di sini.
       */
      const lewatJalan = r.moda === "darat";
      const paketSemua = lewatJalan ? opsiJalan.get(`${r.dariId}>${r.keId}`) : undefined;
      const kini = paketSemua ? indeksJalur(paketSemua, pilihJalur[`${r.dariId}>${r.keId}`]) : 0;
      // Garis tepi berwarna milik jalur yang sedang dipilih (hanya rute yang dipilih).
      if (paketSemua && aktif) {
        L.polyline(geo.titik, {
          className: `pt-pilih pt-jalur--${kini % 4}`,
          interactive: false,
        }).addTo(grup);
      }

      // Bayangan tebal di bawah garisnya; hanya yang sedang dipilih yang
      // memakainya, sehingga satu rute dapat ditunjuk tanpa mengubah warna
      // status yang lain.
      if (aktif) {
        L.polyline(geo.titik, {
          className: `pt-halo pt-warna--${r.status}`,
          interactive: false,
        }).addTo(grup);
      }

      // Selubung putih di bawah garis berwarna: yang membuat garis terbaca
      // sebagai rute navigasi di atas jalan, bukan coretan di atas peta.
      L.polyline(geo.titik, {
        className: `pt-casing${aktif ? " is-aktif" : ""}`,
        interactive: false,
      }).addTo(grup);

      L.polyline(geo.titik, {
        className: `pt-busur pt-warna--${r.status} pt-moda--${r.moda}${aktif ? " is-aktif" : ""}`,
        interactive: false,
      }).addTo(grup);

      // Garis bidik yang lebar dan tak terlihat. Busur setebal tiga piksel
      // tidak dapat ditunjuk dengan jari di tablet, dan menebalkan yang
      // terlihat hanya untuk itu akan membuat peta penuh oleh pita.
      const bidik = L.polyline(geo.titik, {
        className: "pt-bidik",
        interactive: true,
        bubblingMouseEvents: false,
      }).addTo(grup);

      bidik.on("click", () => bukaRute(r));

      /*
       * KENDARAAN ADALAH FUNGSI DARI STATUS DOKUMEN, tidak dari pilihan layar.
       *
       *   Dikirim    -> bergerak, satu per dokumen (paling banyak
       *                 MAKS_KENDARAAN_PER_BUSUR, berjarak sama di sepanjang
       *                 jalan). Ini SATU-SATUNYA keadaan yang membuat sesuatu
       *                 bergerak: barangnya memang sedang di jalan.
       *   Disetujui  -> satu kendaraan terparkir di gudang asal, diam.
       *   Diajukan   -> tidak ada; belum ada barang yang bergerak.
       *   Diterima   -> tidak ada; perjalanannya selesai, garisnya cukup.
       *   Dibatalkan -> tidak ada.
       *
       * Sebelumnya rute yang sedang DIPILIH ikut melaju apa pun tahapnya, dan
       * setiap busur diterima diparkir di gudang tujuan. Memilih dokumen
       * berstatus diajukan menampilkan truk berjalan padahal tidak ada yang
       * dikirim; menekan "Diterima" membuat dokumennya pindah ke busur baru
       * yang -- karena masih terpilih -- melaju lagi, sementara truk lama dan
       * truk usulan masih di tempatnya. Semuanya visual, dan semuanya
       * menyesatkan.
       *
       * Sistem TIDAK punya GPS, jadi posisi kendaraan yang bergerak bukan
       * posisi sungguhan; ia penanda "sedang dalam perjalanan".
       */
      const rencanaK = rencanaKendaraan(r.status, r.dokumen.length, kurangiGerak);
      if (rencanaK.posisi.length > 0) {
        const lin = susunLintasan(geo.titik);
        for (const awal of rencanaK.posisi) {
          const k0 = lin.pada(awal);
          const arah: 1 | -1 = Math.abs(k0.sudut) > 90 ? -1 : 1;
          const truk = L.marker(k0.titik, {
            icon: ikonTruk(arah, r.status, aktif, r.moda),
            interactive: true,
            keyboard: false,
            zIndexOffset: 300,
          }).addTo(grup);
          truk.on("click", () => bukaRute(r));
          if (rencanaK.bergerak) {
            truk.getElement()?.classList.add("pt-truk-jalan");
            armada.push({ truk, lin, geser: awal, arah });
          }
        }
      }

      // Ringkasan biaya jalur yang sedang tampil pada rute ini, bila dikenal.
      const paketR = r.moda === "darat" ? opsiJalan.get(kunciJalan(r)) : undefined;
      let ringkas: [string, string] | null = null;
      if (paketR) {
        const o = paketR.opsi[indeksJalur(paketR, pilihJalur[kunciJalan(r)])];
        ringkas = [
          `${lamaTempuh(o.duration_s, t("tf.map.unit_h"), t("tf.map.unit_min"))} \u00b7 ${rpRingkas(o.biaya.total)}`,
          `${t("tf.map.cost_fuel")}${rpRingkas(o.biaya.bbm)} \u00b7 ${t("tf.map.cost_toll")}${rpRingkas(o.biaya.tol)}`,
        ];
      }

      const label = L.marker(geo.puncak, {
        icon: ikonLabel(r, aktif, ringkas),
        interactive: true,
        keyboard: false,
        riseOnHover: true,
      }).addTo(grup);
      label.on("click", () => bukaRute(r));
    }

    for (const g of penanda) {
      const aktif = fokus?.jenis === "gudang" && fokus.id === g.id;
      const m = L.marker([g.lat, g.lon], {
        icon: ikonGudang(g, aktif),
        interactive: true,
        keyboard: false,
        riseOnHover: true,
        // Gudang selalu berdiri di atas busur yang melintasinya.
        zIndexOffset: 500,
      }).addTo(grup);
      m.on("click", () => {
        setFokus({ jenis: "gudang", id: g.id });
        onPilih(null, "peta");
        /*
         * Penanda yang baru ditunjuk digeser keluar dari bawah panel yang
         * terbuka menutupinya. Tanpa ini, mengklik gudang paling kanan
         * membuatnya hilang persis pada saat rinciannya terbit.
         *
         * Pergeserannya dihitung sebagai SATU titik tengah baru lalu dipakai
         * sekali, bukan panTo diikuti panBy: dua gerakan berturut-turut yang
         * satunya beranimasi saling memotong, dan yang terlihat adalah peta
         * yang tersentak lalu berhenti di tempat yang salah.
         */
        const m2 = peta.current;
        if (!m2) return;
        if (window.innerWidth < 1024) return;
        const titik = m2.project([g.lat, g.lon], m2.getZoom());
        m2.panTo(m2.unproject(titik.add([190, 0]), m2.getZoom()), {
          animate: true,
          duration: 0.5,
        });
      });
      m.getElement()?.setAttribute("aria-label", `${g.nama} (${g.kode})`);
    }

    if (armada.length) {
      const mulai = performance.now();
      const jalankan = (sekarang: number) => {
        const dasar = (sekarang - mulai) / 1000 / PUTARAN_TRUK_DETIK;
        for (const a of armada) {
          const k = a.lin.pada((dasar + a.geser) % 1);
          a.truk.setLatLng(k.titik);
          const arah = Math.abs(k.sudut) > 90 ? -1 : 1;
          if (arah !== a.arah) {
            a.arah = arah;
            (a.truk.getElement()?.querySelector(".pt-truk") as HTMLElement | null)?.style.setProperty(
              "--pt-arah",
              String(arah),
            );
          }
        }
        animasi.current = requestAnimationFrame(jalankan);
      };
      animasi.current = requestAnimationFrame(jalankan);
    }

    function bukaUsulan(u: UsulanRute) {
      setFokus({ jenis: "usulan", kunci: u.kunci });
      // Sorotan dokumen dilepas: satu panel, satu jawaban. Usulan dan dokumen
      // adalah dua benda berbeda yang kebetulan menghubungkan dua gudang yang
      // sama, dan menyorot keduanya sekaligus membuat pembacanya harus menebak
      // yang mana yang sedang dijelaskan panelnya.
      onPilih(null, "peta");
    }

    function bukaRute(r: RuteTransfer) {
      setFokus({ jenis: "rute", kunci: r.kunci });
      // Rute yang hanya membawa satu dokumen langsung memilih dokumen itu:
      // menuntut satu klik lagi pada daftar berisi satu baris adalah pintu
      // yang harus dibuka untuk masuk ke ruangan yang sudah terlihat isinya.
      onPilih(r.dokumen.length === 1 ? r.dokumen[0].id : null, "peta");
    }
  }, [rute, usulanTampak, penanda, fokus, pilih, onPilih, jalan, opsiJalan, pilihJalur, kurangiGerak, t]);

  useEffect(() => {
    if (siap) gambar();
  }, [siap, gambar]);

  /* ---------------- pandangan awal ---------------- */

  // Pandangan disetel HANYA saat kumpulan gudangnya berubah, bukan pada setiap
  // pemilihan: peta yang melompat kembali ke tampilan penuh setiap kali panel
  // ditutup membuang seluruh pekerjaan menggeser dan memperbesar yang baru
  // saja dilakukan pembacanya.
  const kotakAwal = seluruhnya ? JSON.stringify(seluruhnya) : "";
  useEffect(() => {
    if (!siap || !peta.current || !kotakAwal) return;
    peta.current.fitBounds(JSON.parse(kotakAwal) as Kotak, sela());
  }, [siap, kotakAwal]);

  /* ---------------- fokus mengikuti pilihan ---------------- */

  const dipilih = useMemo(
    () => (pilih === null ? null : (dokumen.find((d) => d.id === pilih) ?? null)),
    [dokumen, pilih],
  );

  useEffect(() => {
    if (!siap || !peta.current || !dipilih) return;
    const r = rute.find((x) => x.dokumen.some((d) => d.id === dipilih.id));
    if (!r) return;
    setFokus({ jenis: "rute", kunci: r.kunci });
    peta.current.flyToBounds(kotak(r.geometri.titik) as Kotak, {
      ...sela(true),
      duration: 0.7,
    });
  }, [siap, dipilih, rute]);

  const ruteFokus = fokus?.jenis === "rute" ? rute.find((r) => r.kunci === fokus.kunci) : undefined;
  const usulanFokus =
    fokus?.jenis === "usulan" ? usulanTampak.find((u) => u.kunci === fokus.kunci) : undefined;
  const gudangFokus =
    fokus?.jenis === "gudang" ? penanda.find((g) => g.id === fokus.id) : undefined;

  const setelUlang = useCallback(() => {
    if (peta.current && seluruhnya) peta.current.fitBounds(seluruhnya, sela());
    setFokus(null);
    onPilih(null, "peta");
  }, [seluruhnya, onPilih]);

  /* ---------------- keadaan yang bukan peta ---------------- */

  if (galat) return <ErrorBox message={galat} />;

  if (memuat) {
    return (
      <div className="pt-bingkai flex items-center justify-center">
        <Loading label={t("tf.map.loading")} />
      </div>
    );
  }

  if (!penanda.length) {
    return (
      <div className="pt-bingkai flex items-center justify-center px-6">
        <Empty message={t("tf.map.no_coords")} />
      </div>
    );
  }

  const catatan =
    [
      dokumenTanpaKoordinat.length > 0 || gudangTanpaKoordinat > 0 || usulanTanpaKoordinat > 0
        ? t("tf.map.missing", {
            d: num(dokumenTanpaKoordinat.length + usulanTanpaKoordinat),
            g: num(gudangTanpaKoordinat),
          })
        : "",
      adaGarisKira ? t("tf.map.road_fallback") : "",
    ]
      .filter(Boolean)
      .join(" ") || null;

  return (
    /*
      SATU BIDANG PETA, TANPA KEPALA KARTU DI ATASNYA.
      Judul, kendali, legenda, dan catatan semuanya MELAYANG di atas petanya --
      bentuk yang sudah dikenal semua orang dari aplikasi peta mana pun. Kepala
      kartu setinggi 56px di atas peta mendorong petanya turun, memotong
      tingginya, dan membuat benda ini terbaca sebagai "grafik di dalam kartu"
      alih-alih sebagai peta.

      `isolation: isolate` BUKAN hiasan. Panel-panel Leaflet berdiri pada
      z-index 400-800, dan bilah atas aplikasi hanya z-30: tanpa konteks
      penumpukan sendiri, petak peta akan tercetak di ATAS bilah itu begitu
      halaman digulung.
    */
    <section
      className="pt-panggung pt-bingkai relative"
      style={{ isolation: "isolate" }}
      aria-label={t("tf.map.title")}
    >
      {/*
        Kanvas dipisahkan dari panggung supaya legenda dan kendali menempel pada
        tepi PETA, bukan pada tepi bagian ini. Di bawah 1024px panel rincian
        turun menjadi blok biasa di bawah peta, dan panggung ikut memanjang --
        kendali yang menempel padanya akan melayang di bawah panel, jauh dari
        peta yang dikendalikannya.
      */}
      <div className="pt-kanvas relative">
        <div ref={setWadah} className="pt-tinggi w-full" />

        <div className="pt-kiri-atas">
          <div className="pt-judul">
            <MapPin size={14} aria-hidden style={{ color: "var(--brand)" }} />
            <span className="min-w-0">
              <span className="block truncate font-semibold text-ink">{t("tf.map.title")}</span>
              <span className="block truncate t-caption text-muted">
                {t("tf.map.subtitle", { g: num(penanda.length), r: num(rute.length) })}
              </span>
            </span>
          </div>

          {/*
            Sakelar lapisan usulan, dan ia HANYA terbit bila ada usulannya.
            Sakelar mati yang berdiri permanen di atas peta menyiratkan ada
            sesuatu yang disembunyikan, padahal pada gudang yang stoknya aman
            memang tidak ada satu pun yang perlu dipindahkan.
          */}
          {usulan.length > 0 && (
            <button
              onClick={() => setTampilUsulan((v) => !v)}
              aria-pressed={tampilUsulan}
              className={`pt-lapis${tampilUsulan ? " is-on" : ""}`}
            >
              <Sparkles size={13} aria-hidden />
              {t("tf.map.ai_layer", { n: num(usulan.length) })}
            </button>
          )}
        </div>

        {/*
          Kendali di kanan bawah, bertumpuk, satu tombol satu pekerjaan -- letak
          dan bentuk yang sama dengan yang sudah dikenal orang dari aplikasi
          peta. Kendali bawaan Leaflet di kiri atas dimatikan (`zoomControl:
          false`) karena di sana ia bertabrakan dengan judul, dan bentuknya
          bukan bentuk yang dicari tangan.
        */}
        <div className="pt-kendali">
          <button onClick={setelUlang} className="pt-tombol" title={t("tf.map.reset")}>
            <Crosshair size={16} aria-hidden />
            <span className="sr-only">{t("tf.map.reset")}</span>
          </button>
          <div className="pt-tombol-grup">
            <button
              onClick={() => peta.current?.zoomIn()}
              className="pt-tombol"
              title={t("tf.map.zoom_in")}
            >
              <Plus size={16} aria-hidden />
              <span className="sr-only">{t("tf.map.zoom_in")}</span>
            </button>
            <button
              onClick={() => peta.current?.zoomOut()}
              className="pt-tombol"
              title={t("tf.map.zoom_out")}
            >
              <Minus size={16} aria-hidden />
              <span className="sr-only">{t("tf.map.zoom_out")}</span>
            </button>
          </div>
        </div>

        {!rute.length && (
          <div className="pt-pesan pt-pesan--atas">
            <Layers size={13} aria-hidden />
            {t("tf.map.no_routes")}
          </div>
        )}

        {catatan && (
          <div className="pt-pesan pt-pesan--bawah">
            <AlertTriangle size={13} aria-hidden style={{ color: "var(--status-warning)" }} />
            {catatan}
          </div>
        )}

        {/*
          Gulungan roda TIDAK langsung menjadi zoom, dan yang menggantikannya
          bukan diam melainkan kalimat ini. Peta ini berdiri di tengah halaman
          yang lebih panjang dari layar; menyedot gulungan halaman menjadi zoom
          membuat pembacanya kehilangan tempatnya. Ctrl + gulir tetap
          memperbesar, dan petunjuknya hanya terbit pada saat orangnya benar-
          benar mencoba -- bukan sebagai tulisan permanen di atas peta.
        */}
        <div className={`pt-gulir${petunjukGulir ? " is-tampak" : ""}`} aria-hidden={!petunjukGulir}>
          {t("tf.map.wheel_hint")}
        </div>

        <Legenda adaUsulan={usulanTampak.length > 0} />
      </div>

      {(ruteFokus || gudangFokus || usulanFokus) && (
        <PanelPeta
          onTutup={() => {
            setFokus(null);
            onPilih(null, "peta");
          }}
        >
          {gudangFokus && <IsiGudang g={gudangFokus} />}
          {ruteFokus && (
            <IsiRute
              r={ruteFokus}
              pilih={pilih}
              onPilih={(id) => onPilih(id, "peta")}
              paket={ruteFokus.moda === "darat" ? (opsiJalan.get(kunciJalan(ruteFokus)) ?? null) : null}
              terpilih={
                opsiJalan.get(kunciJalan(ruteFokus))
                  ? indeksJalur(opsiJalan.get(kunciJalan(ruteFokus))!, pilihJalur[kunciJalan(ruteFokus)])
                  : 0
              }
              onPilihJalur={(i) => setPilihJalur((p) => ({ ...p, [kunciJalan(ruteFokus)]: i }))}
            />
          )}
          {usulanFokus && <IsiUsulan u={usulanFokus} />}
        </PanelPeta>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Legenda                                                             */
/* ------------------------------------------------------------------ */

const DERET: StatusTransfer[] = ["draft", "approved", "in_transit", "completed"];

/**
 * Empat tahap, dengan garis contoh yang bentuknya sama persis dengan garis di
 * peta -- termasuk putus-putusnya pada tahap "diajukan". Legenda yang memakai
 * kotak warna sementara petanya memakai garis menuntut pembacanya menerjemahkan
 * satu bentuk ke bentuk lain sebelum dapat memakainya.
 */
function Legenda({ adaUsulan }: { adaUsulan: boolean }) {
  const t = useT();
  return (
    <div className="pt-legenda">
      {DERET.map((s) => (
        <span key={s} className="pt-legenda-baris">
          <span className={`pt-legenda-garis pt-warna--${s} pt-legenda-garis--${s}`} aria-hidden />
          {t(`tf.doc.step.${s}`)}
        </span>
      ))}
      {/*
        Entri kelima berdiri di seberang PEMISAH, bukan berderet dengan empat
        yang lain: empat yang pertama adalah tahap dari satu benda yang sama --
        dokumen -- sedangkan yang kelima benda yang berbeda jenisnya. Menderetkan
        kelimanya rata akan terbaca sebagai "usulan adalah tahap kelima", dan
        tahap kelima berarti sesudah diterima.
      */}
      {/* Tiga jenis jalur: bentuk garis dan kendaraannya berbeda. */}
      <span className="pt-legenda-baris pt-legenda-baris--pisah">
        <Truck size={14} aria-hidden /> {t("rt.mode.darat")}
      </span>
      <span className="pt-legenda-baris">
        <Ship size={14} aria-hidden /> {t("rt.mode.laut")}
      </span>
      <span className="pt-legenda-baris">
        <Plane size={14} aria-hidden /> {t("rt.mode.udara")}
      </span>
      {adaUsulan && (
        <span className="pt-legenda-baris pt-legenda-baris--pisah">
          <span className="pt-legenda-garis pt-legenda-garis--usul" aria-hidden />
          {t("tf.map.ai_legend")}
        </span>
      )}
      {/* Aturan kendaraan, disebut sekali: bergerak = benar-benar dikirim. */}
      <span className="pt-legenda-baris pt-legenda-baris--pisah">{t("tf.map.vehicle_rule")}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Panel rincian                                                       */
/* ------------------------------------------------------------------ */

/**
 * Kotak rincian di dalam peta.
 *
 * Pada layar lebar ia berdiri sebagai kolom di sisi kanan; pada layar sempit ia
 * turun menjadi lembar di tepi bawah dengan tinggi terbatas, supaya peta di
 * belakangnya tetap terlihat -- panel yang menutupi seluruh peta membuat
 * pembacanya kehilangan rute yang baru saja ditunjuknya.
 */
function PanelPeta({ children, onTutup }: { children: React.ReactNode; onTutup: () => void }) {
  const t = useT();
  return (
    <aside className="pt-panel panel-in" aria-live="polite">
      <button onClick={onTutup} className="pt-panel-tutup" aria-label={t("c.close")}>
        <X size={14} aria-hidden />
      </button>
      <div className="pt-panel-isi">{children}</div>
    </aside>
  );
}

function BarisNilai({ label, nilai }: { label: string; nilai: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="t-caption text-muted">{label}</dt>
      <dd className="tnum t-small font-semibold text-ink">{nilai}</dd>
    </div>
  );
}

/** Informasi satu gudang, dibuka dari penandanya. */
function IsiGudang({ g }: { g: PenandaGudang }) {
  const t = useT();
  return (
    <>
      <span className="flex items-center gap-1.5 t-eyebrow" style={{ color: "var(--brand)" }}>
        <Warehouse size={12} aria-hidden />
        {t("tf.map.warehouse")}
      </span>

      <div className="mt-1.5">
        <p className="t-base font-semibold leading-snug text-ink">{g.nama}</p>
        <p className="tnum t-caption text-muted">{g.kode}</p>
        {g.lokasi && <p className="mt-0.5 t-caption text-muted">{g.lokasi}</p>}
      </div>

      <dl className="mt-3 flex flex-col gap-1.5">
        {g.cacahBarang !== null && (
          <BarisNilai label={t("tf.map.wh_items")} nilai={num(g.cacahBarang)} />
        )}
        {g.totalStok !== null && (
          <BarisNilai label={t("tf.map.wh_stock")} nilai={num(g.totalStok)} />
        )}
        <BarisNilai
          label={t("tf.map.wh_out")}
          nilai={t("tf.map.wh_traffic", { n: num(g.keluar), q: num(g.qtyKeluar) })}
        />
        <BarisNilai
          label={t("tf.map.wh_in")}
          nilai={t("tf.map.wh_traffic", { n: num(g.masuk), q: num(g.qtyMasuk) })}
        />
        <BarisNilai
          label={t("tf.map.wh_coord")}
          nilai={`${g.lat.toFixed(4)}, ${g.lon.toFixed(4)}`}
        />
      </dl>
    </>
  );
}

/** Barang yang dibawa satu dokumen; diambil saat dokumennya dipilih. */
function BarangRingkas({ id }: { id: number }) {
  const t = useT();
  const { data, loading, error } = useApi<DetailDokumenTransfer>(`/api/transfers/${id}`);

  if (loading) return <p className="t-caption text-muted">{t("c.loading")}</p>;
  if (error)
    return (
      <p className="t-caption" style={{ color: "var(--status-critical)" }}>
        {error}
      </p>
    );
  if (!data) return null;

  return (
    <ul className="flex flex-col gap-1.5">
      {data.lines.map((l) => (
        <li key={l.id} className="flex items-baseline justify-between gap-3">
          <span className="min-w-0">
            <span className="block truncate t-small font-medium text-ink">{l.item_name}</span>
            <span className="block tnum t-caption text-muted">{l.sku}</span>
          </span>
          <span className="shrink-0 tnum t-small font-bold text-ink">
            {num(l.quantity)} {l.unit_code}
          </span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Rincian satu busur: pengirim, penerima, tahap, dan dokumen yang berjalan di
 * atasnya.
 *
 * DOKUMENNYA DIDAFTAR SATU PER SATU, bukan dijumlahkan menjadi satu baris.
 * Satu busur dapat membawa tiga dokumen, dan "Transfer ID" yang diminta orang
 * gudang adalah nomor satu dokumen -- bukan nama rutenya.
 */
function IsiRute({
  r,
  pilih,
  onPilih,
  paket,
  terpilih,
  onPilihJalur,
}: {
  r: RuteTransfer;
  pilih: number | null;
  onPilih: (id: number | null) => void;
  paket: PaketJalan | null;
  terpilih: number;
  onPilihJalur: (i: number) => void;
}) {
  const t = useT();
  const warna = TAHAP[r.status]?.warna ?? "var(--status-neutral)";

  return (
    <>
      <span className="flex items-center gap-1.5 t-eyebrow" style={{ color: warna }}>
        <PackageOpen size={12} aria-hidden />
        {t("tf.map.route")}
      </span>

      {/* Pengirim -> penerima, menurun dan berlabel: arah yang sama dengan
          kartu di bawah peta, sehingga keduanya tidak perlu dicocokkan. */}
      <p className="mt-2 inline-flex items-center gap-1.5 t-caption font-semibold text-ink">
        {r.moda === "laut" ? <Ship size={13} aria-hidden /> : r.moda === "udara" ? <Plane size={13} aria-hidden /> : <Truck size={13} aria-hidden />}
        {t(`rt.mode.${r.moda}`)}
      </p>

      <div className="mt-2 flex flex-col gap-1.5">
        <div>
          <span className="t-caption text-muted">{t("tf.role.sender")}</span>
          <p className="t-small font-semibold leading-snug text-ink">{r.dariNama}</p>
          <p className="tnum t-caption text-muted">{r.dariKode}</p>
        </div>
        <MoveRight size={15} aria-hidden className="rotate-90" style={{ color: warna }} />
        <div>
          <span className="t-caption text-muted">{t("tf.role.receiver")}</span>
          <p className="t-small font-semibold leading-snug text-ink">{r.keNama}</p>
          <p className="tnum t-caption text-muted">{r.keKode}</p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <PillTahap tahap={r.status} label={r.dokumen[0].status_label} padat />
        <span className="tnum t-small font-bold text-ink">
          {num(r.totalQty)} {t("tf.kpi.units")}
        </span>
      </div>

      <JejakTahap status={r.status} />

      {paket && <PilihanJalur paket={paket} terpilih={terpilih} onPilih={onPilihJalur} />}

      <p className="mt-3 t-eyebrow text-muted">
        {t("tf.map.docs_on_route", { n: num(r.dokumen.length) })}
      </p>

      <ul className="mt-1.5 flex flex-col gap-1.5">
        {r.dokumen.map((d) => {
          const on = d.id === pilih;
          return (
            <li key={d.id}>
              <button
                onClick={() => onPilih(on ? null : d.id)}
                aria-expanded={on}
                className="w-full rounded-xl px-3 py-2 text-left transition"
                style={{
                  background: on ? `color-mix(in srgb, ${warna} 12%, var(--surface-1))` : "var(--surface-1)",
                  boxShadow: `inset 0 0 0 1px ${on ? `color-mix(in srgb, ${warna} 42%, transparent)` : "var(--border)"}`,
                }}
              >
                <span className="flex items-baseline justify-between gap-2">
                  <span className="truncate tnum t-small font-semibold text-ink">
                    {d.transfer_number}
                  </span>
                  <span className="shrink-0 tnum t-small font-bold text-ink">
                    {num(d.total_quantity)}
                  </span>
                </span>
                <span className="mt-0.5 flex items-baseline justify-between gap-2">
                  <span className="t-caption text-muted">{dateLabel(d.transfer_date)}</span>
                  <span className="t-caption text-muted">
                    {t("tf.doc.qty_hint", { n: num(d.line_count) })}
                  </span>
                </span>
              </button>

              {on && (
                <div
                  className="mt-1.5 rounded-xl px-3 py-2.5"
                  style={{ background: "var(--surface-sunken)", boxShadow: "inset 0 0 0 1px var(--border)" }}
                >
                  <p className="mb-1.5 flex items-center gap-1.5 t-eyebrow text-muted">
                    <Boxes size={11} aria-hidden />
                    {t("tf.doc.lines_title")}
                  </p>
                  <BarangRingkas id={d.id} />
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}

/** Rupiah bulat ribuan: "Rp 1.234.000". */
const rp = (n: number) => `Rp ${num(n)}`;

/**
 * Pilihan jalur: rekomendasi AI di atas, lalu satu kartu per jalur.
 *
 * REKOMENDASINYA DETERMINISTIK dan dihitung server dari asumsi yang tampil di
 * bawah kartu; alasannya kode + angka yang dirakit menjadi kalimat di sini.
 * Tidak ada angka yang lahir di layar. Yang diberi label hanya yang DIUKUR
 * (tercepat, terpendek); tidak ada "teraman" karena sumbernya tidak
 * memilikinya.
 *
 * Bensin dan tol adalah PERKIRAAN dari asumsi (konsumsi, harga solar, tarif
 * rata-rata per km tol), bukan tarif resmi -- dan asumsinya ditulis terang-
 * terangan di ujung kartu.
 */
function PilihanJalur({
  paket,
  terpilih,
  onPilih,
}: {
  paket: PaketJalan;
  terpilih: number;
  onPilih: (i: number) => void;
}) {
  const t = useT();
  // Alternatif disembunyikan: yang ditampilkan lebih dulu hanya rekomendasi AI
  // beserta alasannya. Menyuruh pembaca membandingkan empat jalur sebelum ia
  // sempat membaca jawabannya membalik urusannya.
  const [bukaAlt, setBukaAlt] = useState(false);
  const { opsi, rekomendasi, asumsi } = paket;
  const cepat = opsi.find((o) => o.tercepat);
  const dekat = opsi.find((o) => o.terpendek);
  const durasi = (d: number) => lamaTempuh(d, t("tf.map.unit_h"), t("tf.map.unit_min"));

  const kalimat = (a: AlasanJalur): string => {
    const lawan = a.lawan !== undefined ? opsi[a.lawan] : undefined;
    switch (a.kode) {
      case "satu_jalur":
        return t("tf.map.why.single");
      case "tercepat_dan_hemat":
        return t("tf.map.why.fast_cheap", {
          h: durasi(Math.max(0, a.hemat_detik ?? 0)),
          rp: rp(a.hemat_rp ?? 0),
        });
      case "tercepat":
        return t("tf.map.why.fast", { rp: rp(lawan ? opsi[rekomendasi.index].biaya.total - lawan.biaya.total : 0) });
      case "hemat_walau_lebih_lama":
        return t("tf.map.why.cheap", {
          rp: rp(a.hemat_rp ?? 0),
          h: durasi(a.lebih_lama_detik ?? 0),
        });
      case "tol_lebih_banyak":
        return t("tf.map.why.toll");
      case "ada_feri":
        return t("tf.map.why.ferry");
    }
  };

  return (
    <div className="mt-3">
      {/* Kotak rekomendasi. */}
      <div
        className="rounded-xl px-3 py-2.5"
        style={{
          background: "color-mix(in srgb, var(--series-4) 9%, var(--surface-1))",
          boxShadow: "inset 0 0 0 1px color-mix(in srgb, var(--series-4) 40%, transparent)",
        }}
      >
        <p className="flex items-center gap-1.5 t-eyebrow" style={{ color: "var(--series-4)" }}>
          <Sparkles size={11} aria-hidden />
          {t("tf.map.ai_rec")}
        </p>
        <p className="mt-1 t-small font-semibold text-ink">
          {t("tf.map.ai_rec_pick", { n: num(rekomendasi.index + 1) })}
        </p>
        <ul className="mt-1 flex flex-col gap-1">
          {rekomendasi.alasan.map((a, i) => (
            <li key={i} className="t-caption text-muted">
              {kalimat(a)}
            </li>
          ))}
        </ul>
      </div>

      {opsi.length > 1 && (
        <button
          onClick={() => setBukaAlt((v) => !v)}
          aria-expanded={bukaAlt}
          className="mt-3 t-small font-semibold"
          style={{ color: "var(--brand)" }}
        >
          {bukaAlt ? t("rt.hide") : t("tf.map.alt_paths", { n: num(opsi.length) })}
        </button>
      )}
      <ul className="mt-1.5 flex flex-col gap-1.5" hidden={!bukaAlt && opsi.length > 1}>
        {opsi.map((o, i) => {
          const on = i === terpilih;
          const label = o.tercepat && o.terpendek
            ? t("tf.map.path_both")
            : o.tercepat
              ? t("tf.map.path_fastest")
              : o.terpendek
                ? t("tf.map.path_shortest")
                : t("tf.map.path_alt");
          const km = Math.round(o.distance_m / 1000);
          const kmTol = Math.round(o.tol_m / 1000);
          const lebihLama = cepat && !o.tercepat ? o.duration_s - cepat.duration_s : 0;
          const lebihJauh =
            dekat && !o.terpendek ? Math.round((o.distance_m - dekat.distance_m) / 1000) : 0;
          return (
            <li key={i}>
              <button
                onClick={() => onPilih(i)}
                aria-pressed={on}
                className="w-full rounded-xl px-3 py-2 text-left transition"
                style={{
                  background: on ? "color-mix(in srgb, var(--brand) 10%, var(--surface-1))" : "var(--surface-1)",
                  boxShadow: `inset 0 0 0 ${on ? 1.5 : 1}px ${on ? "var(--brand)" : "var(--border)"}`,
                }}
              >
                <span className="flex items-baseline justify-between gap-2">
                  <span className="t-small font-semibold text-ink">
                    <span
                      aria-hidden
                      className={`pt-jalur--${i % 4} pt-chip-jalur`}
                    />
                    {label}
                    {o.via && (
                      <span className="ml-1.5 t-caption font-normal text-muted">
                        {t("tf.map.path_via", { v: o.via })}
                      </span>
                    )}
                    {i === rekomendasi.index && (
                      <span className="ml-1.5 t-caption font-semibold" style={{ color: "var(--series-4)" }}>
                        {"\u2605 "}{t("tf.map.ai_badge")}
                      </span>
                    )}
                  </span>
                  <span className="tnum t-small font-bold text-ink">{durasi(o.duration_s)}</span>
                </span>
                <span className="mt-0.5 flex items-baseline justify-between gap-2">
                  <span className="tnum t-caption text-muted">
                    {num(km)} km{kmTol > 0 ? ` \u00b7 ${t("tf.map.toll_km", { n: num(kmTol) })}` : ""}
                  </span>
                  <span className="t-caption text-muted">
                    {[
                      lebihLama > 0 ? `+${durasi(lebihLama)}` : "",
                      lebihJauh > 0 ? `+${num(lebihJauh)} km` : "",
                    ]
                      .filter(Boolean)
                      .join(" \u00b7 ")}
                  </span>
                </span>

                <span className="pt-biaya">
                  <span>{t("tf.map.cost_fuel")}<b className="tnum">{rp(o.biaya.bbm)}</b></span>
                  <span>{t("tf.map.cost_toll")}<b className="tnum">{rp(o.biaya.tol)}</b></span>
                  <span className="pt-biaya-total">
                    {t("tf.map.cost_total")}<b className="tnum">{rp(o.biaya.total)}</b>
                  </span>
                </span>
                {o.feri && (
                  <span className="mt-1 block t-caption" style={{ color: "var(--status-warning)" }}>
                    {t("tf.map.why.ferry")}
                  </span>
                )}
              </button>
            </li>
          );
        })}
      </ul>

      <p className="mt-1.5 t-caption text-muted">
        {t("tf.map.assume", {
          kml: num(asumsi.km_per_liter),
          solar: rp(asumsi.harga_solar_per_liter),
          tol: rp(asumsi.tarif_tol_per_km),
          jam: rp(asumsi.biaya_per_jam),
          gol: asumsi.golongan_tol,
        })}
      </p>
      <p className="mt-1 t-caption text-muted">{t("tf.map.path_note")}</p>
    </div>
  );
}

/**
 * Jejak tahap ala pelacak kiriman: empat titik menurun, yang sudah dilewati
 * berwarna, yang sedang berjalan bercincin.
 *
 * Isinya HANYA status dokumen yang sudah ada -- tidak ada jam, tidak ada
 * perkiraan tiba. Pelacak yang menampilkan "tiba pukul 14.20" tanpa GPS di
 * belakangnya adalah janji yang tidak dapat ditepati.
 */
function JejakTahap({ status }: { status: StatusTransfer }) {
  const t = useT();
  const idx = DERET.indexOf(status);

  if (status === "cancelled") {
    const { Ikon, warna } = TAHAP.cancelled;
    return (
      <div className="pt-jejak mt-3">
        <div className="pt-jejak-baris is-kini" style={{ color: warna }}>
          <span className="pt-jejak-titik"><Ikon size={11} aria-hidden /></span>
          <span className="t-small font-semibold">{t("tf.doc.step.cancelled")}</span>
        </div>
      </div>
    );
  }

  return (
    <ol className="pt-jejak mt-3" aria-label={t("tf.map.track")}>
      {DERET.map((s, i) => {
        const { Ikon, warna } = TAHAP[s];
        const lewat = i < idx;
        const kini = i === idx;
        return (
          <li
            key={s}
            className={`pt-jejak-baris${lewat ? " is-lewat" : ""}${kini ? " is-kini" : ""}`}
            style={{ color: lewat || kini ? warna : "var(--text-muted)" }}
            aria-current={kini ? "step" : undefined}
          >
            <span className="pt-jejak-titik"><Ikon size={11} aria-hidden /></span>
            <span className={`t-small ${kini ? "font-semibold" : ""}`}>{t(`tf.doc.step.${s}`)}</span>
          </li>
        );
      })}
    </ol>
  );
}

/* ------------------------------------------------------------------ */
/* Usulan mesin                                                        */
/* ------------------------------------------------------------------ */

/** Urutan komponen skor; sama dengan urutan bobotnya pada app/config.py. */
const KOMPONEN: (keyof NonNullable<UsulanBaris["komponen"]>)[] = [
  "sufficiency",
  "surplus_ratio",
  "distance",
  "lead_time",
];

/**
 * Empat batang, bukan satu angka.
 *
 * Pertanyaan yang datang setelah membaca sebuah skor bukan "berapa" melainkan
 * "kenapa yang itu yang menang", dan itu hanya terjawab bila komponennya
 * berdampingan: gudang yang unggul karena DEKAT meski stoknya pas-pasan
 * terlihat berbeda seketika dari gudang yang unggul karena stoknya berlimpah.
 *
 * Panjang batangnya adalah SUMBANGAN komponen itu pada skor akhir -- nilai
 * dikali bobotnya -- bukan nilai mentahnya. Batang yang menggambar nilai
 * mentah membuat komponen berbobot 0,15 terlihat sama berpengaruhnya dengan
 * komponen berbobot 0,40.
 */
function BatangSkor({ b }: { b: UsulanBaris }) {
  const t = useT();
  if (!b.komponen || !b.bobot) return null;

  return (
    <dl className="mt-2 flex flex-col gap-1">
      {KOMPONEN.map((k) => {
        const nilai = b.komponen![k];
        const bobot = b.bobot![k] ?? 0;
        return (
          <div key={k} className="flex items-center gap-2">
            {/* TIDAK dipotong. "Kedalaman surplus" yang tercetak sebagai
                "Kedalaman su..." memaksa pembacanya menebak komponen mana yang
                sedang diukur batang di sebelahnya -- dan menebak nama komponen
                adalah kebalikan dari alasan rincian ini ada. Ia boleh
                membungkus ke baris kedua. */}
            <dt className="w-[92px] shrink-0 t-caption leading-tight text-muted">
              {t(`tf.score.${k}`)}
            </dt>
            <dd className="flex flex-1 items-center gap-1.5">
              <span className="bar-track h-1.5 flex-1">
                <span
                  className="block h-full rounded-full"
                  style={{
                    width: `${Math.max(2, Math.round(nilai * bobot * 100 / 0.4))}%`,
                    background: "var(--series-4)",
                  }}
                />
              </span>
              <span className="w-8 shrink-0 text-right tnum t-caption text-muted">
                {Math.round(nilai * 100)}
              </span>
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

/** Gudang lain yang dipertimbangkan mesin untuk kebutuhan yang sama. */
function KandidatLain({ daftar }: { daftar: KandidatTransfer[] }) {
  const t = useT();
  if (!daftar.length) return null;

  return (
    <div className="mt-2.5">
      <p className="t-eyebrow text-muted">{t("tf.map.ai_others", { n: num(daftar.length) })}</p>
      <ul className="mt-1 flex flex-col gap-1">
        {daftar.map((k) => (
          <li
            key={k.from_warehouse_id}
            className="rounded-lg px-2.5 py-1.5"
            style={{
              background: "var(--surface-1)",
              boxShadow: "inset 0 0 0 1px var(--border)",
              opacity: k.eligible ? 1 : 0.72,
            }}
          >
            <span className="flex items-baseline justify-between gap-2">
              <span className="truncate t-caption font-semibold text-ink">
                {k.from_warehouse_name}
              </span>
              {k.eligible ? (
                <span className="shrink-0 tnum t-caption font-bold" style={{ color: "var(--series-4)" }}>
                  {t("tf.flow.score", { n: k.score })}
                </span>
              ) : (
                <Ban size={11} aria-hidden className="shrink-0" style={{ color: "var(--text-muted)" }} />
              )}
            </span>
            {/* Kalimatnya datang jadi dari backend beserta angkanya; layar tidak
                merakit ulang satu pun bagiannya. */}
            <span className="block t-caption leading-snug text-muted">{k.why}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Satu barang yang disarankan dikirim lewat busur ini. */
function BarisUsulan({ b }: { b: UsulanBaris }) {
  const t = useT();
  const [buka, setBuka] = useState(false);

  return (
    <li>
      <button
        onClick={() => setBuka((v) => !v)}
        aria-expanded={buka}
        className="w-full rounded-xl px-3 py-2 text-left transition"
        style={{
          background: buka
            ? "color-mix(in srgb, var(--series-4) 10%, var(--surface-1))"
            : "var(--surface-1)",
          boxShadow: `inset 0 0 0 1px ${
            buka ? "color-mix(in srgb, var(--series-4) 40%, transparent)" : "var(--border)"
          }`,
        }}
      >
        <span className="flex items-baseline justify-between gap-2">
          <span className="truncate t-small font-semibold text-ink">{b.namaBarang}</span>
          <span className="shrink-0 tnum t-small font-bold text-ink">
            {num(b.qty)} {b.satuan}
          </span>
        </span>
        <span className="mt-0.5 flex items-baseline justify-between gap-2">
          <span className="tnum t-caption text-muted">{b.sku}</span>
          <span className="tnum t-caption font-semibold" style={{ color: "var(--series-4)" }}>
            {t("tf.flow.score", { n: b.skor })}
          </span>
        </span>
      </button>

      {buka && (
        <div
          className="mt-1.5 rounded-xl px-3 py-2.5"
          style={{ background: "var(--surface-sunken)", boxShadow: "inset 0 0 0 1px var(--border)" }}
        >
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <PillKeputusan keputusan={b.keputusan} label={b.keputusanLabel} padat />
            {b.butuh !== null && (
              <span className="t-caption text-muted">
                {t("tf.detail.need")}{" "}
                <span className="tnum font-semibold text-ink">{num(b.butuh)}</span>
              </span>
            )}
            {/* Sisa pembelian dicetak HANYA bila memang ada. Menuliskan "beli 0"
                pada transfer penuh membuat pembacanya mencari pesanan yang
                tidak perlu dibuat. */}
            {b.beli !== null && b.beli > 0 && (
              <span className="t-caption text-muted">
                {t("tf.kpi.buy")}{" "}
                <span className="tnum font-semibold text-ink">{num(b.beli)}</span>
              </span>
            )}
          </div>

          {/* Dua kalimat mesin, dan keduanya perlu: yang pertama menjelaskan
              KEPUTUSANNYA atas seluruh kebutuhan, yang kedua menjelaskan kenapa
              GUDANG INI yang dipilih. */}
          <p className="mt-2 t-caption leading-relaxed text-ink-2">{b.alasan}</p>
          <p className="mt-1 t-caption leading-relaxed text-muted">{b.mengapa}</p>

          {b.cocok === "fuzzy" && b.kemiripan !== null && (
            <p className="mt-1.5 t-caption" style={{ color: "var(--status-warning)" }}>
              {t("tf.fuzzy.badge", { n: Math.round(b.kemiripan * 100) })} —{" "}
              {t("tf.fuzzy.badge_hint")}
            </p>
          )}

          <p className="mt-2.5 t-eyebrow text-muted">{t("tf.score.breakdown")}</p>
          <BatangSkor b={b} />

          <KandidatLain daftar={b.kandidatLain} />
        </div>
      )}
    </li>
  );
}

/**
 * Rincian satu busur usulan.
 *
 * TIDAK ADA SATU ANGKA PUN YANG LAHIR DI SINI. Kuantitas, skor, komponen, dan
 * seluruh kalimat alasannya datang jadi dari GET /api/transfer -- jalur yang
 * sama persis dengan kartu di bawah peta. Yang dikerjakan komponen ini hanya
 * menatanya ke dalam kolom selebar 336 piksel.
 */
function IsiUsulan({ u }: { u: UsulanRute }) {
  const t = useT();
  const warna = "var(--series-4)";

  return (
    <>
      <span className="flex items-center gap-1.5 t-eyebrow" style={{ color: warna }}>
        <Sparkles size={12} aria-hidden />
        {t("tf.map.ai_title")}
      </span>

      <p className="mt-1 t-caption leading-relaxed text-muted">{t("tf.map.ai_hint")}</p>

      {/* Satu rute terbaik menurut model: moda inilah yang digambar di peta. */}
      {u.moda && (
        <p className="mt-2 inline-flex items-center gap-1.5 t-caption font-semibold text-ink">
          {u.moda === "laut" ? <Ship size={13} aria-hidden /> : u.moda === "udara" ? <Plane size={13} aria-hidden /> : <Truck size={13} aria-hidden />}
          {t(`rt.mode.${u.moda}`)}
        </p>
      )}

      <div className="mt-2.5 flex flex-col gap-1.5">
        <div>
          <span className="t-caption text-muted">{t("tf.role.sender")}</span>
          <p className="t-small font-semibold leading-snug text-ink">{u.dariNama}</p>
          <p className="tnum t-caption text-muted">{u.dariKode}</p>
        </div>
        <MoveRight size={15} aria-hidden className="rotate-90" style={{ color: warna }} />
        <div>
          <span className="t-caption text-muted">{t("tf.role.receiver")}</span>
          <p className="t-small font-semibold leading-snug text-ink">{u.keNama}</p>
          <p className="tnum t-caption text-muted">{u.keKode}</p>
        </div>
      </div>

      {/*
        Totalnya dicetak TANPA satuan tunggal: satu busur dapat membawa BOX,
        LTR, dan PCS sekaligus, dan menuliskan satu satuan di belakang
        jumlahnya akan berbohong. Satuan aslinya ada pada tiap barisnya.
      */}
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5">
        <span className="tnum t-small font-bold text-ink">
          {num(u.totalQty)} {t("tf.kpi.units")}
        </span>
        <span className="t-caption text-muted">
          {t("tf.map.ai_items", { n: num(u.baris.length) })}
        </span>
      </div>

      <ul className="mt-2 flex flex-col gap-1.5">
        {u.baris.map((b) => (
          <BarisUsulan key={`${b.itemId}`} b={b} />
        ))}
      </ul>
    </>
  );
}
