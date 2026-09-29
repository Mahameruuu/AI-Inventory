/**
 * Geometri dan pengelompokan untuk peta Transfer Antar Gudang.
 * Geometry and grouping for the inter-warehouse transfer map.
 *
 * TIDAK ADA SATU BARIS LEAFLET DI BERKAS INI, dan itu disengaja. Yang dikerjakan
 * di sini hanya aritmetika: memproyeksikan koordinat, melengkungkan garis, dan
 * mengelompokkan dokumen menjadi rute. Semuanya dapat dibaca -- dan kelak diuji
 * -- tanpa DOM, tanpa peta, dan tanpa peramban.
 *
 * TIDAK ADA SATU PUN ANGKA TRANSFER YANG LAHIR DI SINI. Kuantitas, status,
 * gudang asal, dan gudang tujuan datang jadi dari GET /api/transfers. Yang
 * ditambahkan berkas ini hanya PENJUMLAHAN qty per rute -- dan penjumlahan itu
 * tidak pernah menggantikan angka per dokumen, hanya berdiri di sampingnya pada
 * label rute.
 *
 * KOORDINAT YANG KOSONG TIDAK DIISI. Gudang tanpa lintang/bujur tidak muncul di
 * peta dan rutenya tidak digambar; keduanya dilaporkan sebagai cacah supaya
 * layar dapat mengatakannya terus terang. Menebak letak gudang menghasilkan
 * rute yang terbaca persis sama meyakinkannya dengan rute yang benar, dan itu
 * jenis kesalahan yang tidak pernah terbit sebagai galat.
 */

import {
  BarisTransfer,
  DokumenTransfer,
  KandidatTransfer,
  KeputusanTransfer,
  KomponenSkor,
  DasarCocok,
  ModaAngkut,
  StatusTransfer,
} from "@/lib/transfer-types";

/* ------------------------------------------------------------------ */
/* Proyeksi                                                            */
/* ------------------------------------------------------------------ */

/**
 * Web Mercator ternormalisasi, sama dengan yang dipakai petak peta.
 *
 * Lengkungan rute dihitung DI RUANG INI, bukan di lintang/bujur mentah.
 * Bedanya terlihat begitu peta digeser ke zoom lain: busur yang dilengkungkan
 * pada lintang/bujur menjadi makin miring makin jauh dari khatulistiwa dan
 * kepala panahnya menunjuk ke arah yang meleset, sementara busur yang
 * dilengkungkan di ruang proyeksi tetap sama bentuknya pada setiap zoom --
 * karena itulah ruang tempat peta menggambarnya.
 */
export interface Titik {
  x: number;
  y: number;
}

const BATAS_LINTANG = 85.05112878;

export function proyeksi(lat: number, lon: number): Titik {
  const φ = (Math.max(-BATAS_LINTANG, Math.min(BATAS_LINTANG, lat)) * Math.PI) / 180;
  return { x: lon / 360, y: -Math.log(Math.tan(Math.PI / 4 + φ / 2)) / (2 * Math.PI) };
}

export function balik(p: Titik): [number, number] {
  const φ = 2 * Math.atan(Math.exp(-p.y * 2 * Math.PI)) - Math.PI / 2;
  return [(φ * 180) / Math.PI, p.x * 360];
}

/* ------------------------------------------------------------------ */
/* Busur berarah                                                       */
/* ------------------------------------------------------------------ */

/** Satu kepala panah: tempatnya, dan sudutnya dalam derajat layar (0 = ke kanan). */
export interface KepalaPanah {
  titik: [number, number];
  sudut: number;
}

/** Satu busur siap gambar: titik-titiknya, kepala panahnya, dan puncaknya. */
export interface Busur {
  titik: [number, number][];
  /*
   * DUA kepala panah, bukan satu. Satu panah di tengah busur hilang di balik
   * label jumlahnya pada rute pendek, dan pada rute panjang ia terlalu jauh
   * dari kedua ujung untuk terbaca sebagai "dari sini ke sana". Dua panah pada
   * seperempat dan tiga perempat perjalanan membuat arahnya terbaca dari mana
   * pun mata jatuh di garis itu.
   */
  panah: KepalaPanah[];
  /** puncak busur; tempat label jumlah digantung */
  puncak: [number, number];
}

const RUAS = 48;

/**
 * Busur Bezier kuadratik dari `a` ke `b`.
 *
 * SELALU MELENGKUNG KE SISI YANG SAMA relatif arah jalannya, dan itu yang
 * memisahkan Surabaya->Jakarta dari Jakarta->Surabaya. Dua rute berlawanan arah
 * di antara dua gudang yang sama akan menempati garis lurus yang persis sama
 * bila digambar lurus; melengkungkannya ke sisi kiri arah perjalanan membuat
 * keduanya menjadi dua busur yang berdampingan, dan mata membaca arahnya dari
 * bentuknya bahkan sebelum melihat kepala panahnya.
 *
 * `lapis` menggeser lengkungannya lebih jauh lagi, untuk rute yang sama dengan
 * status berbeda: tiga dokumen Surabaya->Jakarta yang berlainan tahap menjadi
 * tiga busur sejajar, bukan tiga garis yang saling menimpa.
 */
export function busur(
  a: [number, number],
  b: [number, number],
  lapis = 0,
  lengkung = 1,
): Busur {
  const p0 = proyeksi(a[0], a[1]);
  const p1 = proyeksi(b[0], b[1]);

  const dx = p1.x - p0.x;
  const dy = p1.y - p0.y;
  const panjang = Math.hypot(dx, dy) || 1e-9;

  /*
   * LENGKUNGANNYA DANGKAL, dan itu disengaja.
   *
   * Busur hanya perlu melengkung secukupnya untuk dua hal: memisahkan arah
   * pergi dari arah pulang, dan memisahkan rute yang bertumpuk. Lebih dari itu
   * ia berhenti terbaca sebagai garis perjalanan dan mulai terbaca sebagai
   * busur pada diagram -- rute Jakarta-Surabaya yang membusur sampai ke tengah
   * Laut Jawa menunjuk tempat yang tidak dilewati kiriman mana pun.
   *
   * Kelengkungannya berbanding terbalik dengan jarak, dengan langit-langit:
   * bagian tetapnya menjaga dua gudang bertetangga tidak berubah menjadi
   * lingkaran, dan batas atasnya menjaga rute antarpulau tetap dangkal.
   */
  const dasar = Math.min(0.11, 0.006 / panjang + 0.055);
  const k = (dasar + lapis * 0.055) * panjang * lengkung;

  // Tegak lurus arah jalan, ke sisi KIRI perjalanan pada layar.
  const nx = -dy / panjang;
  const ny = dx / panjang;

  const cx = (p0.x + p1.x) / 2 + nx * k;
  const cy = (p0.y + p1.y) / 2 + ny * k;

  const pada = (t: number): Titik => {
    const u = 1 - t;
    return {
      x: u * u * p0.x + 2 * u * t * cx + t * t * p1.x,
      y: u * u * p0.y + 2 * u * t * cy + t * t * p1.y,
    };
  };

  const titik: [number, number][] = [];
  for (let i = 0; i <= RUAS; i++) titik.push(balik(pada(i / RUAS)));

  // Arah kepala panah diambil dari dua titik BERSEBELAHAN pada busurnya
  // sendiri, bukan dari garis lurus a->b: pada busur yang melengkung tajam
  // keduanya berbeda belasan derajat, dan panah yang miring terhadap garisnya
  // terbaca sebagai gambar yang salah gambar.
  const kepala = (t: number): KepalaPanah => {
    const q0 = pada(t - 0.01);
    const q1 = pada(t + 0.01);
    return {
      titik: balik(pada(t)),
      // y proyeksi tumbuh ke BAWAH pada layar, jadi tandanya tidak dibalik.
      sudut: (Math.atan2(q1.y - q0.y, q1.x - q0.x) * 180) / Math.PI,
    };
  };

  /*
   * Label busur DIGESER menurut lapisnya, bukan selalu di titik tengah.
   *
   * Jarak antarbusur ditulis dalam satuan proyeksi, jadi ia ikut mengecil saat
   * peta diperkecil -- sementara label jumlahnya tetap sebesar hurufnya. Pada
   * zoom rendah tiga label rute yang sama karena itu bertumpuk menjadi satu
   * gumpalan angka yang tidak dapat dibaca satu pun. Menggesernya di sepanjang
   * busur memisahkannya MENDATAR, dan pemisahan mendatar tidak menyusut
   * bersama zoom.
   */
  const geser = [0, -0.15, 0.15, -0.27, 0.27];

  return {
    titik,
    // Kepala panah didorong ke dekat kedua ujungnya, menjauh dari pita label
    // yang menempati bagian tengah busur.
    panah: [kepala(0.16), kepala(0.84)],
    puncak: balik(pada(0.5 + (geser[lapis] ?? 0))),
  };
}

/* ------------------------------------------------------------------ */
/* Jalan sungguhan dan lintasan truk                                   */
/* ------------------------------------------------------------------ */

/**
 * Busur siap gambar dari garis jalan yang sudah diambil dari OSRM.
 *
 * Bentuknya sama dengan hasil busur(), jadi seluruh penggambar tidak perlu tahu
 * dari mana garisnya berasal. Garisnya digeser sedikit ke sisi kanan arah
 * jalannya: dua rute berlawanan arah di antara gudang yang sama menempuh jalan
 * yang PERSIS sama, dan tanpa pergeseran yang satu menutupi yang lain. Menyisih
 * ke kanan juga persis kelakuan jalan sungguhan -- dua arah, dua lajur.
 * `lapis` menambah pergeserannya untuk dokumen yang lain tahap.
 *
 * Pergeserannya dalam satuan proyeksi (kecil sekali, 0,00002), sehingga ikut
 * mengecil bersama zoom;
 * pada zoom nasional kedua lajur menyatu menjadi satu garis, dan pada zoom kota
 * keduanya terpisah jelas -- perilaku yang sama dengan jalan pada peta mana pun.
 */
export function busurDariJalan(jalan: [number, number][], lapis = 0): Busur {
  const pr = jalan.map((q) => proyeksi(q[0], q[1]));
  const geser = 0.00002 * (1 + lapis);

  const titik: [number, number][] = pr.map((p, i) => {
    const a = pr[Math.max(0, i - 1)];
    const b = pr[Math.min(pr.length - 1, i + 1)];
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const n = Math.hypot(dx, dy) || 1e-9;
    return balik({ x: p.x + (-dy / n) * geser, y: p.y + (dx / n) * geser });
  });

  const lin = susunLintasan(titik);
  const offsetLabel = [0, -0.15, 0.15, -0.27, 0.27];
  return {
    titik,
    panah: [lin.pada(0.25), lin.pada(0.75)],
    puncak: lin.pada(0.5 + (offsetLabel[lapis] ?? 0)).titik,
  };
}

export interface Lintasan {
  /** posisi dan arah (derajat layar, 0 = ke kanan) pada pecahan t dari 0 sampai 1 */
  pada: (t: number) => KepalaPanah;
}

/**
 * Lintasan berjarak-tetap di atas sebuah garis.
 *
 * Pecahan t diukur menurut PANJANG garis, bukan menurut nomor titiknya: garis
 * dari OSRM rapat di tikungan dan renggang di jalan lurus, jadi truk yang
 * berjalan menurut nomor titik akan melambat di tikungan dan ngebut di tol.
 * Panjangnya diukur dalam satuan proyeksi -- cukup untuk membandingkan ruas
 * satu dengan ruas lain pada satu garis.
 */
export function susunLintasan(titik: [number, number][]): Lintasan {
  const pr = titik.map((q) => proyeksi(q[0], q[1]));
  const kum: number[] = [0];
  for (let i = 1; i < pr.length; i++) {
    kum.push(kum[i - 1] + Math.hypot(pr[i].x - pr[i - 1].x, pr[i].y - pr[i - 1].y));
  }
  const total = kum[kum.length - 1] || 1e-9;

  return {
    pada(t: number): KepalaPanah {
      const sasaran = Math.min(1, Math.max(0, t)) * total;
      // pencarian biner ruas yang memuat `sasaran`
      let lo = 0;
      let hi = kum.length - 1;
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if (kum[mid] <= sasaran) lo = mid;
        else hi = mid;
      }
      const a = pr[lo];
      const b = pr[hi];
      const seg = kum[hi] - kum[lo] || 1e-9;
      const f = (sasaran - kum[lo]) / seg;
      // Arah diambil dari jendela sekitar titiknya, bukan dari satu ruas:
      // ruas OSRM di tikungan pendek dan berayun belasan derajat.
      const a2 = pr[Math.max(0, lo - 3)];
      const b2 = pr[Math.min(pr.length - 1, hi + 3)];
      return {
        titik: balik({ x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f }),
        sudut: (Math.atan2(b2.y - a2.y, b2.x - a2.x) * 180) / Math.PI,
      };
    },
  };
}

/* ------------------------------------------------------------------ */
/* Gudang di peta                                                      */
/* ------------------------------------------------------------------ */

/** Bentuk gudang seperti yang diterbitkan GET /api/warehouses. */
export interface GudangApi {
  id: number;
  code: string;
  name: string;
  location?: string | null;
  latitude?: number | string | null;
  longitude?: number | string | null;
  is_active?: boolean;
  item_count?: number | string | null;
  total_stock?: number | string | null;
}

/** Satu penanda gudang, beserta lalu lintas transfer yang menyentuhnya. */
export interface PenandaGudang {
  id: number;
  kode: string;
  nama: string;
  lokasi: string | null;
  lat: number;
  lon: number;
  aktif: boolean;
  cacahBarang: number | null;
  totalStok: number | null;
  /** dokumen yang BERANGKAT dari sini, di antara yang sedang ditampilkan */
  keluar: number;
  qtyKeluar: number;
  /** dokumen yang MENUJU ke sini */
  masuk: number;
  qtyMasuk: number;
}

/** Angka yang mungkin datang sebagai Decimal berbentuk string. */
function angkaAtauNull(v: number | string | null | undefined): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * Penanda untuk SETIAP gudang yang punya koordinat, bukan hanya yang sedang
 * berkirim barang.
 *
 * Gudang yang sepi justru bagian dari jawabannya: peta yang hanya memuat gudang
 * dengan rute berjalan tidak dapat membedakan "gudang itu tidak mengirim
 * apa-apa minggu ini" dari "gudang itu tidak ada".
 */
export function susunGudang(
  daftar: GudangApi[],
  dokumen: DokumenTransfer[],
): { penanda: PenandaGudang[]; tanpaKoordinat: number } {
  let tanpaKoordinat = 0;
  const penanda: PenandaGudang[] = [];

  for (const g of daftar) {
    const lat = angkaAtauNull(g.latitude);
    const lon = angkaAtauNull(g.longitude);
    if (lat === null || lon === null) {
      tanpaKoordinat += 1;
      continue;
    }
    penanda.push({
      id: g.id,
      kode: g.code,
      nama: g.name,
      lokasi: g.location ?? null,
      lat,
      lon,
      aktif: g.is_active !== false,
      cacahBarang: angkaAtauNull(g.item_count),
      totalStok: angkaAtauNull(g.total_stock),
      keluar: 0,
      qtyKeluar: 0,
      masuk: 0,
      qtyMasuk: 0,
    });
  }

  const olehId = new Map(penanda.map((p) => [p.id, p]));
  for (const d of dokumen) {
    const dari = olehId.get(d.from_warehouse_id);
    if (dari) {
      dari.keluar += 1;
      dari.qtyKeluar += d.total_quantity;
    }
    const ke = olehId.get(d.to_warehouse_id);
    if (ke) {
      ke.masuk += 1;
      ke.qtyMasuk += d.total_quantity;
    }
  }

  return { penanda, tanpaKoordinat };
}

/* ------------------------------------------------------------------ */
/* Rute                                                                */
/* ------------------------------------------------------------------ */

/**
 * Satu busur di peta: SATU pasang gudang, SATU status.
 *
 * KENAPA STATUS IKUT MENJADI KUNCI. Tiga dokumen Surabaya -> Jakarta yang
 * masing-masing berstatus diajukan, disetujui, dan dikirim adalah satu garis
 * bila dikelompokkan menurut rute saja -- dan garis itu harus memilih satu
 * warna untuk mewakili tiga keadaan yang berbeda. Warna apa pun yang dipilihnya
 * salah untuk dua di antaranya. Memasukkan status ke dalam kuncinya membuat
 * ketiganya menjadi tiga busur sejajar yang masing-masing berwarna jujur, dan
 * jumlah dokumen di dalam tiap busur tetap ditulis pada labelnya.
 */
export interface RuteTransfer extends BusurTerlapis {
  kunci: string;
  status: StatusTransfer;
  /** moda angkut dokumen pada busur ini; menentukan ikon kendaraannya */
  moda: ModaAngkut;

  dariKode: string;
  dariNama: string;
  keKode: string;
  keNama: string;

  /** dokumen pada busur ini, terbaru lebih dulu (urutan dari API dipertahankan) */
  dokumen: DokumenTransfer[];
  /** jumlah unit seluruh dokumen pada busur ini; bilangan bulat */
  totalQty: number;
}

/** Lengkungan busur menurut moda; darat = bawaan, udara membusur paling tinggi. */
export const LENGKUNG_MODA: Record<ModaAngkut, number> = { darat: 1, laut: 1.3, udara: 2.4 };

/** Urutan busur dari pasangan gudang yang sama; mengikuti alur dokumen. */
const URUT_STATUS: StatusTransfer[] = [
  "draft",
  "approved",
  "in_transit",
  "completed",
  "cancelled",
];

export interface HasilRute {
  rute: RuteTransfer[];
  /** dokumen yang salah satu gudangnya belum punya koordinat */
  tanpaKoordinat: DokumenTransfer[];
}

export function susunRute(dokumen: DokumenTransfer[]): HasilRute {
  const kelompok = new Map<string, RuteTransfer>();
  const tanpaKoordinat: DokumenTransfer[] = [];

  for (const d of dokumen) {
    const dLat = angkaAtauNull(d.from_latitude);
    const dLon = angkaAtauNull(d.from_longitude);
    const kLat = angkaAtauNull(d.to_latitude);
    const kLon = angkaAtauNull(d.to_longitude);

    if (dLat === null || dLon === null || kLat === null || kLon === null) {
      tanpaKoordinat.push(d);
      continue;
    }

    // Moda ikut kunci: dokumen darat dan laut pada pasangan yang sama adalah dua
    // benda berbeda, dan satu ikon kendaraan tidak boleh mewakili keduanya.
    const moda: ModaAngkut = d.transport_mode ?? "darat";
    const kunci = `${d.from_warehouse_id}>${d.to_warehouse_id}:${d.status}:${moda}`;
    const ada = kelompok.get(kunci);
    if (ada) {
      ada.dokumen.push(d);
      ada.totalQty += d.total_quantity;
      continue;
    }

    kelompok.set(kunci, {
      kunci,
      status: d.status,
      moda,
      dariId: d.from_warehouse_id,
      dariKode: d.from_warehouse_code,
      dariNama: d.from_warehouse_name,
      dari: [dLat, dLon],
      keId: d.to_warehouse_id,
      keKode: d.to_warehouse_code,
      keNama: d.to_warehouse_name,
      ke: [kLat, kLon],
      dokumen: [d],
      totalQty: d.total_quantity,
      lapis: 0,
      // sementara; digambar ulang setelah lapisnya diketahui
      geometri: busur([dLat, dLon], [kLat, kLon], 0, LENGKUNG_MODA[moda]),
    });
  }

  const rute = [...kelompok.values()];

  /*
   * Lapis ditetapkan PER PASANGAN BERARAH, sesudah seluruh dokumen terkumpul.
   * Urutannya mengikuti alur dokumen (diajukan -> ... -> selesai), bukan urutan
   * kedatangan datanya, supaya susunan busurnya tidak berubah-ubah setiap kali
   * halaman dimuat ulang -- peta yang menyusun ulang dirinya sendiri tanpa ada
   * yang berubah membuat pembacanya mencari perubahan yang tidak ada.
   */
  const perPasangan = new Map<string, RuteTransfer[]>();
  for (const r of rute) {
    const p = `${r.dariId}>${r.keId}`;
    const daftar = perPasangan.get(p);
    if (daftar) daftar.push(r);
    else perPasangan.set(p, [r]);
  }

  for (const daftar of perPasangan.values()) {
    daftar.sort((a, b) => URUT_STATUS.indexOf(a.status) - URUT_STATUS.indexOf(b.status));
  }
  // Lapisnya ditetapkan lewat fungsi bersama, bukan di sini: bila usulan mesin
  // ikut digambar, keduanya harus dilapisi dalam SATU deret -- lihat
  // terapkanLapis(). Pemanggil yang menggambar keduanya memanggilnya sekali
  // lagi atas gabungannya, dan hasil di sini menjadi keadaan awal yang benar
  // bagi pemanggil yang hanya menggambar dokumen.
  terapkanLapis(rute);

  return { rute, tanpaKoordinat };
}

/* ------------------------------------------------------------------ */
/* Lapis busur: dipakai bersama dokumen dan usulan                     */
/* ------------------------------------------------------------------ */

/** Apa pun yang digambar sebagai busur berarah di antara dua gudang. */
export interface BusurTerlapis {
  /** kosong = usulan/darat; laut dan udara tidak mengikuti jalan sungguhan */
  moda?: ModaAngkut;
  dariId: number;
  keId: number;
  dari: [number, number];
  ke: [number, number];
  lapis: number;
  geometri: Busur;
}

/**
 * Menyusun busur yang berbagi pasangan gudang menjadi lapisan sejajar.
 *
 * DIPANGGIL SEKALI UNTUK SELURUH BUSUR, dokumen dan usulan sekaligus. Bila
 * masing-masing melapisi dirinya sendiri, keduanya akan mulai dari lapis nol
 * dan busur usulan Surabaya->Jakarta menempati garis yang persis sama dengan
 * dokumen Surabaya->Jakarta yang sudah berjalan -- dua benda yang artinya
 * berlawanan, bertumpuk sempurna.
 *
 * Urutan masuknya menentukan urutan lapisnya, jadi pemanggil menaruh dokumen
 * lebih dulu: yang benar-benar berjalan tetap paling dekat ke garis lurus, dan
 * usulan mengambang di luarnya.
 */
export function terapkanLapis(
  daftar: BusurTerlapis[],
  jalan?: ReadonlyMap<string, [number, number][]>,
): void {
  const perPasangan = new Map<string, BusurTerlapis[]>();
  for (const r of daftar) {
    const p = `${r.dariId}>${r.keId}`;
    const ada = perPasangan.get(p);
    if (ada) ada.push(r);
    else perPasangan.set(p, [r]);
  }
  for (const g of perPasangan.values()) {
    g.forEach((r, i) => {
      r.lapis = i;
      // Hanya darat (dan usulan) yang mengikuti jalan sungguhan. Kapal dan
      // pesawat tidak lewat jalan tol: keduanya digambar sebagai lengkung
      // dengan bentuk sendiri, supaya tiga jenis jalur dapat dibedakan sekali
      // lihat -- jalan mengikuti bumi, laut melengkung landai, udara membusur tinggi.
      const lewatJalan = !r.moda || r.moda === "darat";
      const garis = lewatJalan ? jalan?.get(`${r.dariId}>${r.keId}`) : undefined;
      r.geometri = garis
        ? busurDariJalan(garis, i)
        : busur(r.dari, r.ke, i, r.moda ? LENGKUNG_MODA[r.moda] : 1);
    });
  }
}

/* ------------------------------------------------------------------ */
/* Usulan mesin                                                        */
/* ------------------------------------------------------------------ */

/**
 * Satu kiriman yang DISARANKAN mesin, untuk satu barang.
 *
 * Seluruh angkanya DIPINJAM utuh dari GET /api/transfer; tidak satu pun
 * dihitung ulang di layar. Yang dikerjakan berkas ini hanya mengelompokkannya
 * menurut pasangan gudang supaya dapat digambar sebagai satu busur.
 */
export interface UsulanBaris {
  itemId: number;
  sku: string;
  namaBarang: string;
  satuan: string;

  /** yang disarankan dikirim lewat kaki ini */
  qty: number;
  /** kekurangan seluruh baris; dipinjam dari mesin pemesanan ulang */
  butuh: number | null;
  /** sisa yang tetap harus dibeli; > 0 hanya pada transfer sebagian */
  beli: number | null;

  keputusan: KeputusanTransfer;
  keputusanLabel: string;
  /** kalimat mesin untuk seluruh baris */
  alasan: string;
  /** kalimat mesin untuk kaki ini; menyebut angka gudang asalnya */
  mengapa: string;

  skor: number;
  komponen?: KomponenSkor;
  bobot?: Record<string, number>;

  surplus: number;
  jarakKm: number | null;
  dasarJarak: "matrix" | "haversine" | null;
  waktuHari: number | null;
  cocok: DasarCocok;
  kemiripan: number | null;

  /** gudang lain yang dipertimbangkan mesin untuk kebutuhan yang sama */
  kandidatLain: KandidatTransfer[];
}

/** Satu busur usulan: SATU pasang gudang, berapa pun barang yang lewat. */
export interface UsulanRute extends BusurTerlapis {
  kunci: string;
  dariKode: string;
  dariNama: string;
  keKode: string;
  keNama: string;
  baris: UsulanBaris[];
  totalQty: number;
  skorTertinggi: number;
}

export interface HasilUsulan {
  usulan: UsulanRute[];
  /** kaki usulan yang salah satu gudangnya belum punya koordinat */
  tanpaKoordinat: number;
}

/**
 * Usulan mesin yang LAYAK DIGAMBAR, dan hanya itu.
 *
 * TIGA SARINGAN, dan ketiganya menolak hal yang berbeda:
 *
 *   keputusan     Hanya TRANSFER dan TRANSFER_SEBAGIAN. PEMBELIAN mencakup
 *                 sekaligus tiga keadaan yang semuanya TIDAK boleh digambar
 *                 sebagai panah di peta -- tidak ada gudang sumber yang layak,
 *                 tidak ada kekurangan sama sekali (gudangnya aman), dan
 *                 kekurangannya belum dapat dihitung karena riwayatnya kurang.
 *                 Menggambar panah untuk ketiganya berarti menyarankan
 *                 perpindahan barang yang mesinnya sendiri tidak sarankan.
 *
 *   qty > 0       Penjaga kedua terhadap keadaan yang seharusnya mustahil:
 *                 kaki beralokasi nol tidak menggerakkan apa pun, dan panah
 *                 sepanjang pulau untuk nol unit adalah kebohongan yang rapi.
 *
 *   koordinat     Gudang tanpa lintang/bujur tidak digambar, dan letaknya
 *                 tidak pernah ditebak. Jumlah yang terbuang dilaporkan
 *                 supaya layar dapat mengatakannya terus terang.
 */
export function susunUsulan(
  baris: BarisTransfer[],
  koordinat: Map<number, [number, number]>,
): HasilUsulan {
  const kelompok = new Map<string, UsulanRute>();
  let tanpaKoordinat = 0;

  for (const b of baris) {
    if (b.decision !== "TRANSFER" && b.decision !== "TRANSFER_SEBAGIAN") continue;

    for (const kaki of b.legs) {
      if (!(kaki.transfer_qty > 0)) continue;

      const dari = koordinat.get(kaki.from_warehouse_id);
      const ke = koordinat.get(b.to_warehouse_id);
      if (!dari || !ke) {
        tanpaKoordinat += 1;
        continue;
      }

      const isi: UsulanBaris = {
        itemId: b.item_id,
        sku: b.sku,
        namaBarang: b.item_name,
        satuan: b.unit_code,
        qty: kaki.transfer_qty,
        butuh: b.need_qty,
        beli: b.purchase_qty,
        keputusan: b.decision,
        keputusanLabel: b.decision_label,
        alasan: b.reason,
        mengapa: kaki.why,
        skor: kaki.score,
        komponen: kaki.components,
        bobot: kaki.weights,
        surplus: kaki.surplus,
        jarakKm: kaki.distance_km,
        dasarJarak: kaki.distance_basis,
        waktuHari: kaki.lead_time_days,
        cocok: kaki.match_type,
        kemiripan: kaki.match_similarity,
        // Gudang lain yang dipertimbangkan untuk kebutuhan yang SAMA: yang
        // lolos tetapi kalah, dan yang ditolak beserta sebabnya. Gudang yang
        // sedang menjadi pengirim pada kaki ini dikeluarkan -- ia bukan
        // "pilihan lain", ia pilihan yang diambil.
        kandidatLain: [...b.candidates, ...b.rejected].filter(
          (k) => k.from_warehouse_id !== kaki.from_warehouse_id,
        ),
      };

      const kunci = `u:${kaki.from_warehouse_id}>${b.to_warehouse_id}`;
      const ada = kelompok.get(kunci);
      if (ada) {
        ada.baris.push(isi);
        ada.totalQty += isi.qty;
        ada.skorTertinggi = Math.max(ada.skorTertinggi, isi.skor);
        continue;
      }

      kelompok.set(kunci, {
        kunci,
        moda: kaki.route_ml?.mode,
        dariId: kaki.from_warehouse_id,
        dariKode: kaki.from_warehouse_code,
        dariNama: kaki.from_warehouse_name,
        dari,
        keId: b.to_warehouse_id,
        keKode: b.to_warehouse_code,
        keNama: b.to_warehouse_name,
        ke,
        baris: [isi],
        totalQty: isi.qty,
        skorTertinggi: isi.skor,
        lapis: 0,
        geometri: busur(dari, ke, 0, kaki.route_ml ? LENGKUNG_MODA[kaki.route_ml.mode] : 1),
      });
    }
  }

  // Barang berskor tertinggi lebih dulu di dalam tiap busur: itulah usulan yang
  // paling kuat alasannya, dan itulah yang dibaca orang lebih dulu.
  const usulan = [...kelompok.values()];
  for (const r of usulan) r.baris.sort((a, b) => b.skor - a.skor);
  return { usulan, tanpaKoordinat };
}

/* ------------------------------------------------------------------ */
/* Batas pandang                                                       */
/* ------------------------------------------------------------------ */

export type Kotak = [[number, number], [number, number]];

/** Kotak terkecil yang memuat seluruh titik; null bila tidak ada satu pun. */
export function kotak(titik: [number, number][]): Kotak | null {
  if (!titik.length) return null;
  let lat1 = titik[0][0];
  let lat2 = titik[0][0];
  let lon1 = titik[0][1];
  let lon2 = titik[0][1];
  for (const [lat, lon] of titik) {
    if (lat < lat1) lat1 = lat;
    if (lat > lat2) lat2 = lat;
    if (lon < lon1) lon1 = lon;
    if (lon > lon2) lon2 = lon;
  }
  return [
    [lat1, lon1],
    [lat2, lon2],
  ];
}

/* ------------------------------------------------------------------ */
/* Kendaraan di peta                                                   */
/* ------------------------------------------------------------------ */

/** Kendaraan bergerak paling banyak per busur; lebih dari ini hanya menumpuk. */
export const MAKS_KENDARAAN_PER_BUSUR = 3;

export interface RencanaKendaraan {
  /** posisi awal tiap kendaraan di sepanjang jalan, 0 (asal) .. 1 (tujuan) */
  posisi: number[];
  /** true bila kendaraannya melaju terus; false bila diam di posisinya */
  bergerak: boolean;
}

/**
 * Berapa kendaraan yang digambar pada satu busur, dan apakah ia bergerak.
 *
 * FUNGSI DARI STATUS DOKUMEN SAJA -- bukan dari rute mana yang sedang dipilih,
 * dan bukan dari ada tidaknya usulan mesin:
 *
 *   in_transit  satu per dokumen (paling banyak MAKS_KENDARAAN_PER_BUSUR),
 *               tersebar rata di sepanjang jalan, dan bergerak. Satu-satunya
 *               keadaan yang membuat sesuatu bergerak.
 *   approved    satu, terparkir di gudang asal, diam.
 *   lainnya     tidak ada (diajukan belum berangkat; diterima dan dibatalkan
 *               sudah selesai).
 *
 * `kurangiGerak` (preferensi aksesibilitas) menahan kendaraan yang seharusnya
 * bergerak di tempatnya, tersebar di tengah jalan.
 */
export function rencanaKendaraan(
  status: StatusTransfer,
  jumlahDokumen: number,
  kurangiGerak = false,
): RencanaKendaraan {
  if (status === "approved") return { posisi: [0.05], bergerak: false };
  if (status !== "in_transit" || jumlahDokumen < 1) return { posisi: [], bergerak: false };
  const n = Math.min(jumlahDokumen, MAKS_KENDARAAN_PER_BUSUR);
  if (kurangiGerak) {
    return { posisi: Array.from({ length: n }, (_, i) => (i + 1) / (n + 1)), bergerak: false };
  }
  return { posisi: Array.from({ length: n }, (_, i) => i / n), bergerak: true };
}
