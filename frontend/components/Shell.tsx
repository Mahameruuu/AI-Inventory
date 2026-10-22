"use client";

/**
 * Kerangka aplikasi: sidebar, bilah atas, dan area isi.
 * Application shell: sidebar, top bar, content area.
 *
 * Label navigasi TIDAK ditulis mati di sini. Setiap butir membawa kunci kamus,
 * sehingga menambah bahasa ketiga kelak tidak menyentuh berkas ini sama sekali.
 * Nav labels are never hardcoded: each entry carries a dictionary key, so a
 * third language would not touch this file at all.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowLeftRight,
  ArrowUpFromLine,
  ChevronDown,
  ClipboardCheck,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Settings,
  Sparkles,
  Sun,
  Timer,
  TrendingUp,
  Users,
  Warehouse,
  X,
} from "lucide-react";

import { DialogKonfirmasi } from "@/components/ui";
import { NavigationProvider, useNavPending } from "@/components/nav-progress";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

interface NavItem {
  href: string;
  /** kunci kamus, bukan teks jadi / dictionary key, never a finished string */
  key: string;
  icon: typeof LayoutDashboard;
  /**
   * Hanya tampil bagi owner dan admin.
   *
   * Menyembunyikannya adalah soal tampilan, BUKAN penjagaan: yang menolak
   * peran lain tetap backend, dan halamannya sendiri menampilkan kalimat yang
   * menjelaskan bila dibuka langsung lewat alamatnya. Yang dihindari di sini
   * hanyalah menawarkan pintu yang sudah pasti terkunci.
   */
  kelola?: boolean;
}

interface NavGroup {
  /** kunci kamus untuk label bagian; tercetak kecil di atas butirnya */
  key: string;
  items: NavItem[];
}

/*
 * Navigasi disusun sebagai SATU ALUR, bukan katalog fitur.
 *
 * Urutannya mengikuti perjalanan datanya sendiri: apa yang dikelola (Data
 * Dasar), bagaimana ia masuk (Input Manual), lalu apa yang disimpulkan mesin
 * dari keduanya (Kecerdasan AI). Seorang pengguna baru dapat menelusurinya
 * dari atas ke bawah tanpa perlu diberi tahu urutannya.
 *
 * KELOMPOK TIDAK LAGI DAPAT DILIPAT, dan itu perubahan yang disengaja pada
 * 2 September 2026. Pelipatan dipasang saat sidebar memuat empat belas tautan
 * dan memanjang melewati layar; setelah pemangkasan modul, yang tersisa
 * sembilan. Sembilan tautan muat seluruhnya tanpa menggulir, sehingga
 * pelipatan hanya menyisakan biayanya -- satu klik sebelum sebuah tautan
 * terlihat, dan satu keadaan yang harus diingat pengguna. Judul kelompok kini
 * menjadi LABEL BAGIAN: penanda arah yang dibaca sekilas, bukan tombol.
 *
 * Modul yang dihapus pada 31 Agustus 2026 -- Persediaan, Gudang (tampilan
 * baca), Transfer, Penyesuaian, Riwayat, Pembelian, seluruh Laporan,
 * Kategori, Satuan, Pemasok, Impor, dan Pengguna -- dibuang karena berdiri di
 * luar alur itu atau hanya menyajikan tabel angka mentah. Kodenya ikut
 * dihapus, bukan sekadar disembunyikan dari menu, supaya tidak ada halaman
 * yang hidup tanpa jalan menuju ke sana. Arsipnya ada di backups/.
 *
 * Pengaturan TIDAK ada di daftar ini: ia tinggal di popup akun di kanan
 * atas, terpisah dari alur kerja. Lihat MenuAkun.
 */
const NAV: NavGroup[] = [
  {
    key: "nav.section.main",
    items: [{ href: "/", key: "nav.dashboard", icon: LayoutDashboard }],
  },
  {
    // `kelola` dipertahankan seperti sebelumnya: kedua halaman ini menyunting
    // data induk, dan haknya tidak ikut berubah oleh penataan ulang menu.
    key: "nav.basic_data",
    items: [
      { href: "/master/items", key: "nav.md_items", icon: Package, kelola: true },
      { href: "/master/warehouses", key: "nav.md_warehouses", icon: Warehouse, kelola: true },
    ],
  },
  {
    key: "nav.manual_input",
    items: [
      { href: "/transactions/receipts", key: "nav.receipt", icon: ArrowDownToLine },
      { href: "/transactions/issues", key: "nav.issue", icon: ArrowUpFromLine },
      // Stok opname menutup Input Manual: penerimaan dan pengeluaran mencatat
      // barang yang bergerak, opname mengoreksi selisih yang tidak tercatat.
      { href: "/transactions/opname", key: "nav.opname", icon: ClipboardCheck },
    ],
  },
  {
    key: "nav.ai",
    items: [
      { href: "/forecasting", key: "nav.forecasting", icon: TrendingUp },
      // Pemesanan ulang berdiri sendiri, bukan bagian Prakiraan: yang dijawabnya
      // kapan dan berapa harus dipesan, berpatokan lead time -- bukan periode
      // prakiraan yang dipilih pengguna di layar Prakiraan.
      { href: "/reorder", key: "nav.reorder", icon: RefreshCw },
      // Transfer Antar Gudang berdiri TEPAT SESUDAH Pemesanan Ulang, dan
      // urutan itu adalah urutan pertanyaannya: berapa yang kurang dijawab
      // lebih dulu, dari mana kekurangan itu ditutup dijawab sesudahnya.
      // Meletakkannya sebelum Pemesanan Ulang berarti menawarkan sumber untuk
      // kekurangan yang belum pernah dihitung.
      { href: "/transfer", key: "nav.transfer", icon: ArrowLeftRight },
      // Analisis Umur Pakai menempati posisi Deteksi Anomali, yang dihapus
      // pada 2 September 2026. Letaknya SESUDAH Pemesanan Ulang dan sebelum
      // Asisten: ia menjelaskan pola penggantian yang menghasilkan permintaan,
      // sehingga dibaca setelah orang melihat apa yang perlu dipesan.
      { href: "/lifetime", key: "nav.lifetime", icon: Timer },
      { href: "/assistant", key: "nav.chat", icon: Sparkles },
    ],
  },
];

/**
 * Pengaturan. Satu-satunya pintunya kini popup akun di kanan atas.
 *
 * Tetap ikut di SEMUA supaya pencocokan rute terpanjang tahu bahwa
 * "/settings" adalah sebuah rute -- tanpa itu, membuka halaman Pengaturan
 * membuat pencocokan jatuh ke rute lain yang kebetulan berawalan sama.
 */
const PENGATURAN: NavItem = { href: "/settings", key: "nav.settings", icon: Settings };

/** Jejak Audit, khusus admin/owner; pintunya di popup akun seperti Pengaturan. */
const AUDIT: NavItem = { href: "/audit", key: "nav.audit", icon: History, kelola: true };
/** Pengguna, khusus admin/owner: satu-satunya pintu menambah pengguna sejak pendaftaran dicabut. */
const PENGGUNA: NavItem = { href: "/users", key: "nav.users", icon: Users, kelola: true };

const SEMUA = [...NAV.flatMap((g) => g.items), PENGATURAN, AUDIT, PENGGUNA];

/** Rute terpilih = pencocokan terpanjang, supaya /inventory/items tidak menyalakan /inventory. */
function isActive(pathname: string, href: string): boolean {
  const cocok = SEMUA.filter(
    (i) => pathname === i.href || (i.href !== "/" && pathname.startsWith(i.href + "/"))
  );
  if (!cocok.length) return false;
  const terpanjang = cocok.reduce((a, b) => (b.href.length > a.href.length ? b : a));
  return terpanjang.href === href;
}

/**
 * Satu tautan navigasi.
 *
 * KEADAAN AKTIF DITANDAI TIGA HAL SEKALIGUS -- latar bertintasi, batang aksen
 * di tepi kiri, dan ikon berwarna merek -- karena satu saja tidak cukup untuk
 * semua orang: latar tipis lenyap pada layar berkontras rendah, dan warna
 * sendirian tidak terbaca oleh mata yang tidak membedakannya. Tebal hurufnya
 * dinaikkan tanpa mengubah tinggi baris, sehingga tidak ada yang bergeser saat
 * pengguna berpindah halaman.
 *
 * `ringkas` adalah mode rel: hanya ikon, label pindah ke atribut title.
 *
 * `sentuh` MENINGGIKAN BARISNYA DARI 36px MENJADI 44px, dan dipakai hanya oleh
 * laci di layar sempit. Tiga puluh enam piksel adalah tinggi yang benar untuk
 * sasaran yang dibidik dengan penunjuk tetikus selebar satu piksel; ia terlalu
 * pendek untuk ujung jari, dan sembilan tautan setinggi 36px yang berdempetan
 * membuat orang menekan tetangga dari yang dituju. Angka 44 adalah ambang yang
 * dipakai pedoman sentuh Apple maupun Google.
 */
function TautanNav({
  href,
  label,
  Icon,
  aktif,
  ringkas = false,
  sentuh = false,
}: {
  href: string;
  label: string;
  Icon: typeof LayoutDashboard;
  aktif: boolean;
  ringkas?: boolean;
  /** sasaran sentuh diperbesar; untuk laci navigasi di ponsel */
  sentuh?: boolean;
}) {
  return (
    <Link
      href={href}
      title={ringkas ? label : undefined}
      aria-current={aktif ? "page" : undefined}
      className={`group relative flex items-center rounded-lg t-body transition-colors duration-150 ${
        sentuh ? "h-11" : "h-9"
      } ${
        ringkas ? "justify-center px-0" : "gap-3 px-3"
      } ${aktif ? "" : "hover:bg-[color-mix(in_srgb,var(--text-primary)_5%,transparent)]"}`}
      style={{
        background: aktif
          ? "color-mix(in srgb, var(--brand) 11%, transparent)"
          : "transparent",
        color: aktif ? "var(--text-primary)" : "var(--text-secondary)",
        fontWeight: aktif ? 600 : 450,
      }}
    >
      {aktif && (
        <span
          aria-hidden
          className="absolute left-0 top-1/2 w-[3px] -translate-y-1/2 rounded-r-full"
          style={{ height: 18, background: "var(--brand)" }}
        />
      )}
      <Icon
        size={sentuh ? 17 : 16}
        className="shrink-0"
        style={{ color: aktif ? "var(--brand)" : "var(--text-muted)" }}
      />
      {!ringkas && <span className="truncate">{label}</span>}
    </Link>
  );
}

/**
 * Label bagian: penanda arah, bukan tombol.
 *
 * Sengaja kecil, huruf besar, berjarak longgar, dan berwarna paling redup di
 * palet. Ia harus terbaca saat dicari dan menghilang saat tidak -- label
 * bagian yang menuntut perhatian sama besar dengan tautannya sendiri membuat
 * daftar sembilan tautan terbaca seperti daftar tiga belas baris.
 *
 * Pada mode rel ia menjadi sepotong garis: pengelompokannya tetap terasa
 * meski katanya tidak muat.
 */
function LabelBagian({ label, ringkas }: { label: string; ringkas: boolean }) {
  if (ringkas) {
    return (
      <div
        aria-hidden
        className="mx-auto my-2 h-px w-6"
        style={{ background: "var(--border)" }}
      />
    );
  }
  return (
    <div className="px-3 pb-1.5 pt-4 t-micro font-semibold uppercase tracking-[0.13em] text-muted">
      {label}
    </div>
  );
}

/** Satu kelompok navigasi beserta label bagiannya. */
interface KelompokTampil {
  key: string;
  items: NavItem[];
}

/**
 * Daftar tautan navigasi, dipakai DUA KALI: oleh sidebar di layar lebar dan
 * oleh laci di layar sempit.
 *
 * Sebelum 2 September 2026 keduanya tidak berbagi apa pun. Sidebar memakai
 * daftar berkelompok dengan ikon; layar sempit mendapat versinya sendiri --
 * sebaris tautan teks yang menggulir mendatar di dalam bilah atas, tanpa ikon,
 * tanpa kelompok, dan berdesakan dengan empat kendali lain di baris yang sama.
 * Yang dihasilkannya bukan sekadar tampilan yang lebih rapat, melainkan PETA
 * YANG BERBEDA: di ponsel sembilan tautan berbaris rata tanpa menyebut bahwa
 * tiga di antaranya data dasar dan empat lainnya keluaran mesin, dan tautan
 * kesembilan hanya terlihat oleh yang menebak bahwa barisnya masih berlanjut
 * ke kanan.
 *
 * Satu sumber, dua bentuk. Menambah halaman kelak mengubah satu tempat.
 */
function DaftarNavigasi({
  nav,
  jalur,
  ringkas = false,
  sentuh = false,
}: {
  nav: KelompokTampil[];
  jalur: string;
  ringkas?: boolean;
  sentuh?: boolean;
}) {
  const { t } = useI18n();
  return (
    <>
      {nav.map((group) => (
        <div key={group.key}>
          <LabelBagian label={t(group.key)} ringkas={ringkas} />
          <div className="flex flex-col gap-0.5">
            {group.items.map(({ href, key, icon: Icon }) => (
              <TautanNav
                key={href}
                href={href}
                label={t(key)}
                Icon={Icon}
                aktif={isActive(jalur, href)}
                ringkas={ringkas}
                sentuh={sentuh}
              />
            ))}
          </div>
        </div>
      ))}
    </>
  );
}

/**
 * Laci navigasi untuk layar sempit.
 *
 * MENGGANTIKAN BARIS TAUTAN YANG MENGGULIR MENDATAR di dalam bilah atas.
 * Baris itu punya tiga cacat sekaligus dan tidak satu pun dapat diperbaiki
 * tanpa membuangnya: ia berbagi satu baris setinggi 36px dengan bilah demo,
 * sakelar bahasa, sakelar tema, dan menu akun -- sehingga navigasinya menyusut
 * sampai selebar dua tautan; ia menyembunyikan tautan di luar layar tanpa
 * memberi tanda apa pun bahwa masih ada lanjutannya; dan ia membuang
 * pengelompokan yang justru menjadi alasan sidebar disusun sebagai alur.
 *
 * Laci menutup pada TIGA kejadian, dan ketiganya perlu: tombol tutup, tirai
 * di belakangnya, dan Esc. Yang keempat -- berpindah halaman -- ditangani
 * pemanggilnya, karena laci yang tetap terbuka di atas halaman baru menutupi
 * hal yang baru saja diminta pengguna.
 *
 * FOKUS DIKEMBALIKAN ke tombol pemicunya saat ditutup. Tanpa itu, orang yang
 * menutup laci dengan Esc meninggalkan fokusnya pada elemen yang sudah tidak
 * ada, dan Tab berikutnya melompat kembali ke awal halaman.
 */
function LaciNavigasi({
  terbuka,
  tutup,
  nav,
  jalur,
}: {
  terbuka: boolean;
  tutup: () => void;
  nav: KelompokTampil[];
  jalur: string;
}) {
  const { t } = useI18n();
  const panel = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!terbuka) return;
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") tutup();
    };
    document.addEventListener("keydown", esc);
    /*
     * Halaman di belakang laci TIDAK boleh ikut menggulir. Di ponsel, menggeser
     * jari di atas tirai yang gelap menggulirkan halaman di baliknya, dan saat
     * laci ditutup pembaca mendapati dirinya di tempat lain pada halaman yang
     * sama tanpa pernah memintanya.
     */
    const sebelum = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    // Fokus dipindahkan ke dalam laci supaya Tab berjalan di antara tautannya,
    // bukan di antara elemen halaman yang sedang tertutup tirai.
    panel.current?.focus();
    return () => {
      document.removeEventListener("keydown", esc);
      document.body.style.overflow = sebelum;
    };
  }, [terbuka, tutup]);

  if (!terbuka) return null;

  return (
    <div className="md:hidden">
      <div
        aria-hidden
        onClick={tutup}
        className="laci-tirai fixed inset-0 z-40"
        style={{ background: "color-mix(in srgb, var(--text-primary) 45%, transparent)" }}
      />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-label={t("shell.menu")}
        tabIndex={-1}
        className="laci-masuk fixed inset-y-0 left-0 z-50 flex w-[min(84vw,290px)] flex-col border-r outline-none"
        style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
      >
        <div className="flex h-14 shrink-0 items-center gap-2 px-4">
          {/* Logo tanpa kotak; tulisannya berganti terang/gelap mengikuti tema. */}
          <img src="/logo-xorca-dark-text.svg" alt="Xorca" className="block h-6 w-auto shrink-0 dark:hidden" />
          <img src="/logo-xorca-light-text.svg" alt="Xorca" className="hidden h-6 w-auto shrink-0 dark:block" />
          <span className="font-display min-w-0 flex-1 truncate text-[12px] font-bold uppercase tracking-[0.02em] text-ink">
            {t("brand.short")}
          </span>
          <button
            type="button"
            onClick={tutup}
            aria-label={t("shell.close_menu")}
            title={t("shell.close_menu")}
            className="-mr-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-muted transition hover:bg-surface-2 hover:text-ink"
          >
            <X size={18} aria-hidden />
          </button>
        </div>

        <div className="mx-3 h-px shrink-0" style={{ background: "var(--border)" }} />

        {/*
         * Menutup lewat DELEGASI, bukan lewat satu penangan pada tiap tautan.
         * Yang menutup laci adalah berpindah halaman, dan itu terjadi pada
         * setiap <a> di dalamnya -- termasuk yang ditambahkan kelak oleh orang
         * yang tidak membaca berkas ini.
         */}
        <nav
          className="flex-1 overflow-y-auto px-3 pb-4"
          onClick={(e) => {
            if ((e.target as HTMLElement).closest("a")) tutup();
          }}
        >
          <DaftarNavigasi nav={nav} jalur={jalur} sentuh />
        </nav>

        {/*
         * Sakelar bahasa tinggal DI SINI pada layar sempit, bukan di bilah atas.
         * Bilah atas ponsel hanya menyisakan ruang bagi kendali yang disentuh
         * sepanjang hari; bahasa dipilih sekali lalu tidak disentuh lagi, dan
         * dua tombol selebar 78px yang menuntut ruang tetap membuat nama produk
         * terpenggal pada layar 360px.
         *
         * `pb` memakai safe-area: pada ponsel dengan bilah gestur, tanpa itu
         * tombolnya duduk persis di bawah garis yang menutup aplikasi.
         */}
        <div
          className="shrink-0 border-t px-3 py-3"
          style={{
            borderColor: "var(--border)",
            paddingBottom: "calc(0.75rem + env(safe-area-inset-bottom))",
          }}
        >
          <LangToggle />
        </div>
      </div>
    </div>
  );
}

/**
 * Kaki sidebar: Pengaturan, lalu identitas pemakai.
 *
 * IDENTITAS PINDAH KE SINI dari bilah atas pada 2 September 2026. Di bilah
 * atas ia berdesakan dengan sakelar bahasa, sakelar tema, dan bilah demo --
 * empat kelompok kendali yang tidak berhubungan satu sama lain, dan yang
 * paling jarang disentuh justru memakan ruang paling lebar. Di kaki sidebar
 * ia menempati tempat yang sudah dikenali orang dari perkakas lain.
 *
 * PERUSAHAAN IKUT TERTULIS, bukan hanya nama orangnya. Pada sistem banyak-
 * penyewa, "angka siapa yang sedang saya lihat" adalah pertanyaan yang harus
 * terjawab tanpa perlu diklik -- terutama saat satu orang mendemokan beberapa
 * akun berturut-turut.
 */
/** Sakelar tema terang/gelap. */
function ThemeToggle() {
  const { t } = useI18n();
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    const prefers = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = stored ? stored === "dark" : prefers;
    setDark(isDark);
    document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
  }, []);

  return (
    <button
      onClick={() => {
        const next = !dark;
        setDark(next);
        localStorage.setItem("theme", next ? "dark" : "light");
        document.documentElement.setAttribute("data-theme", next ? "dark" : "light");
      }}
      className="flex h-9 w-9 items-center justify-center rounded-lg border text-ink-2 transition hover:bg-surface-2"
      style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
      aria-label={t("shell.theme")}
      title={t("shell.theme")}
    >
      {dark ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}

/**
 * Sakelar bahasa.
 *
 * Berupa dua pilihan yang KEDUANYA terlihat, bukan satu tombol yang berganti
 * makna. Pada tombol tunggal, "EN" bisa berarti "sedang berbahasa Inggris" atau
 * "tekan untuk ke Inggris" -- dan pembaca pitch tidak punya kesempatan kedua
 * untuk menebaknya.
 */
function LangToggle() {
  const { lang, setLang, t } = useI18n();
  return (
    <div
      className="relative flex h-9 items-center rounded-lg border p-0.5"
      style={{ borderColor: "var(--border)", background: "var(--surface-1)" }}
      role="group"
      aria-label={t("shell.lang")}
    >
      {(["id", "en"] as const).map((l) => {
        const aktif = lang === l;
        return (
          <button
            key={l}
            type="button"
            onClick={() => setLang(l)}
            aria-pressed={aktif}
            className="relative z-10 h-8 w-9 rounded-lg t-caption font-semibold uppercase tracking-wide transition"
            style={{
              background: aktif ? "var(--grad-brand)" : "transparent",
              color: aktif ? "#fff" : "var(--text-muted)",
              boxShadow: aktif ? "var(--glow-brand)" : "none",
            }}
          >
            {l}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Identitas pemakai di bilah atas, sekaligus jalan keluar.
 *
 * Perusahaan ikut ditulis, bukan hanya nama orangnya. Pada sistem banyak-
 * penyewa, "angka siapa yang sedang saya lihat" adalah pertanyaan yang harus
 * terjawab tanpa perlu diklik -- terutama saat satu orang mendemokan beberapa
 * akun berturut-turut.
 */
/**
 * Identitas pemakai di kanan atas, sekaligus jalan keluar.
 *
 * DI KANAN ATAS, bukan di kaki sidebar. Ia sempat dipindahkan ke kaki sidebar
 * pada 2 September 2026 dan dikembalikan pada hari yang sama: kanan atas
 * adalah tempat pertama yang dicari orang untuk akunnya sendiri, dan tempat
 * yang benar adalah tempat yang sudah dicari -- bukan tempat yang paling rapi
 * menurut tata letaknya.
 *
 * PERUSAHAAN IKUT TERTULIS, bukan hanya nama orangnya. Pada sistem banyak-
 * penyewa, "angka siapa yang sedang saya lihat" harus terjawab tanpa perlu
 * diklik -- terutama saat satu orang mendemokan beberapa akun berturut-turut.
 * Karena itu barisnya tetap terbaca di luar popup pada layar lebar.
 *
 * KELUAR SELALU BERTANYA LEBIH DULU. Ia membuang sesi dan mengembalikan orang
 * ke halaman masuk; bila terjadi di tengah presentasi atau di tengah mengisi
 * formulir penerimaan, yang hilang bukan hanya satu klik. Tombol keluar yang
 * duduk sejengkal dari tombol pengaturan menuntut pertanyaan itu.
 */
function MenuAkun() {
  const { t } = useI18n();
  const { pengguna, perusahaan, keluar, bolehMengelola } = useAuth();
  const [buka, setBuka] = useState(false);
  const [tanyaKeluar, setTanyaKeluar] = useState(false);
  const bungkus = useRef<HTMLDivElement | null>(null);
  const pemicu = useRef<HTMLButtonElement | null>(null);

  /*
   * Menutup lewat klik di luar DAN lewat Esc.
   *
   * `pointerdown`, bukan `click`: menekan tombol lain di bilah atas harus
   * menutup popup pada tekanan yang sama, bukan menunggu tombolnya dilepas --
   * kalau tidak, tekanan pertama hanya menutup popup dan tombol yang dituju
   * tidak pernah tertekan.
   */
  useEffect(() => {
    if (!buka) return;
    const luar = (e: PointerEvent) => {
      if (!bungkus.current?.contains(e.target as Node)) setBuka(false);
    };
    const esc = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setBuka(false);
      // Fokus dikembalikan ke pemicunya. Tanpa ini, menutup dengan Esc
      // meninggalkan fokus di dalam elemen yang sudah tidak ada, dan Tab
      // berikutnya melompat ke awal halaman.
      pemicu.current?.focus();
    };
    document.addEventListener("pointerdown", luar);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", luar);
      document.removeEventListener("keydown", esc);
    };
  }, [buka]);

  if (!pengguna) return null;

  const peran = t(`auth.role.${pengguna.role}`);
  // Inisial, bukan foto: sistem ini tidak menyimpan gambar profil, dan
  // lingkaran abu-abu kosong tidak menerangkan apa pun.
  const inisial =
    pengguna.full_name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((w) => w[0]?.toUpperCase() ?? "")
      .join("") || "?";

  return (
    <>
      <div className="relative" ref={bungkus}>
        <button
          ref={pemicu}
          type="button"
          onClick={() => setBuka((b) => !b)}
          aria-haspopup="menu"
          aria-expanded={buka}
          title={t("auth.account_menu")}
          className="flex h-9 items-center gap-2 rounded-lg border pl-1 pr-1.5 transition hover:bg-surface-2 sm:pr-2"
          style={{
            borderColor: buka ? "var(--brand)" : "var(--border)",
            background: buka ? "var(--surface-2)" : "var(--surface-1)",
          }}
        >
          <span
            aria-hidden
            className="brand-mark flex h-7 w-7 shrink-0 items-center justify-center rounded-lg t-caption font-bold text-white"
          >
            {inisial}
          </span>
          {/* Nama dan penyewa hanya pada layar lebar; di ponsel avatar saja
              sudah menjadi sasaran sentuh yang cukup. */}
          <span className="hidden min-w-0 text-left leading-tight sm:block">
            <span className="block max-w-[10rem] truncate t-small font-semibold text-ink">
              {pengguna.full_name}
            </span>
            <span className="block max-w-[10rem] truncate t-micro text-muted">
              {perusahaan?.name} &middot; {peran}
            </span>
          </span>
          <ChevronDown
            size={13}
            aria-hidden
            className="shrink-0 transition-transform duration-150"
            style={{ color: "var(--text-muted)", transform: buka ? "rotate(180deg)" : "none" }}
          />
        </button>

        {buka && (
          <div
            role="menu"
            aria-label={t("auth.account_menu")}
            className="absolute right-0 z-40 mt-1.5 w-60 overflow-hidden rounded-xl"
            style={{
              background: "var(--surface-1)",
              boxShadow: "var(--elev-3), inset 0 0 0 1px var(--border)",
            }}
          >
            {/*
             * Kepala popup MENGULANG nama dan penyewa dengan sengaja. Pada
             * ponsel pemicunya hanya avatar berisi dua huruf, jadi popup ini
             * satu-satunya tempat keduanya terbaca -- dan justru di ponsel
             * orang paling mudah lupa akun mana yang sedang terbuka.
             */}
            <div className="px-3.5 py-3" style={{ background: "var(--surface-2)" }}>
              <div className="truncate t-body font-semibold text-ink">{pengguna.full_name}</div>
              <div className="truncate t-caption text-muted">@{pengguna.username}</div>
              <div className="mt-1 truncate t-caption text-muted">
                {perusahaan?.name} &middot; {peran}
              </div>
            </div>

            <div className="h-px" style={{ background: "var(--border)" }} />

            <div className="p-1.5">
              <Link
                href={PENGATURAN.href}
                role="menuitem"
                onClick={() => setBuka(false)}
                className="flex h-9 items-center gap-2.5 rounded-lg px-2.5 t-body text-ink-2 transition-colors hover:bg-[color-mix(in_srgb,var(--text-primary)_5%,transparent)] hover:text-ink"
              >
                <Settings size={15} aria-hidden style={{ color: "var(--text-muted)" }} />
                {t("nav.settings")}
              </Link>
              {bolehMengelola && (
                <Link
                  href={PENGGUNA.href}
                  role="menuitem"
                  onClick={() => setBuka(false)}
                  className="flex h-9 items-center gap-2.5 rounded-lg px-2.5 t-body text-ink-2 transition-colors hover:bg-[color-mix(in_srgb,var(--text-primary)_5%,transparent)] hover:text-ink"
                >
                  <Users size={15} aria-hidden style={{ color: "var(--text-muted)" }} />
                  {t("nav.users")}
                </Link>
              )}
              {bolehMengelola && (
                <Link
                  href={AUDIT.href}
                  role="menuitem"
                  onClick={() => setBuka(false)}
                  className="flex h-9 items-center gap-2.5 rounded-lg px-2.5 t-body text-ink-2 transition-colors hover:bg-[color-mix(in_srgb,var(--text-primary)_5%,transparent)] hover:text-ink"
                >
                  <History size={15} aria-hidden style={{ color: "var(--text-muted)" }} />
                  {t("nav.audit")}
                </Link>
              )}
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setBuka(false);
                  setTanyaKeluar(true);
                }}
                className="flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 t-body transition-colors hover:bg-[color-mix(in_srgb,var(--status-critical)_10%,transparent)]"
                style={{ color: "var(--status-critical)" }}
              >
                <LogOut size={15} aria-hidden />
                {t("auth.sign_out")}
              </button>
            </div>
          </div>
        )}
      </div>

      <DialogKonfirmasi
        terbuka={tanyaKeluar}
        judul={t("auth.sign_out_title")}
        pesan={t("auth.sign_out_confirm")}
        labelLanjut={t("auth.sign_out")}
        labelBatal={t("md.cancel")}
        onBatal={() => setTanyaKeluar(false)}
        onLanjut={keluar}
      />
    </>
  );
}

/** Layar antara: sesi sedang diperiksa, atau pengguna sedang dipulangkan. */
function LayarTunggu({ label }: { label: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-5">
      <p className="t-small text-muted">{label}</p>
    </div>
  );
}

/**
 * Gerbang masuk seluruh aplikasi.
 *
 * SATU TEMPAT, BUKAN DELAPAN BELAS. Setiap halaman di bawah kerangka ini
 * membaca data yang menuntut token. Membiarkan masing-masing memutuskan apa
 * yang terjadi bila token tidak ada berarti satu halaman yang lupa akan tampil
 * lengkap dengan pesan galat di setiap kartunya -- dan halaman itu tidak akan
 * ketahuan sampai ada yang membukanya dalam keadaan keluar.
 *
 * KENAPA BUKAN MIDDLEWARE NEXT.JS. Token tinggal di localStorage, yang tidak
 * pernah ikut terkirim ke server, sehingga middleware tidak punya apa pun
 * untuk diperiksa. Penjagaan yang sesungguhnya tetap ada di backend: setiap
 * endpoint data menolak permintaan tanpa token. Yang dikerjakan gerbang ini
 * semata-mata supaya layarnya benar.
 */
function Gerbang({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const { status } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const diHalamanMasuk = pathname === "/login";

  useEffect(() => {
    if (status === "keluar" && !diHalamanMasuk) router.replace("/login");
    // Pengguna yang sudah masuk tidak punya urusan di halaman masuk.
    if (status === "masuk" && diHalamanMasuk) router.replace("/");
  }, [status, diHalamanMasuk, router]);

  // Halaman masuk berdiri sendiri tanpa sidebar: seluruh tautan di sana menuju
  // halaman yang menuntut token, dan menampilkannya kepada orang yang belum
  // punya token hanya menyajikan dinding tautan mati.
  if (diHalamanMasuk) return <>{children}</>;

  if (status === "memuat") return <LayarTunggu label={t("auth.checking")} />;
  if (status === "keluar") return <LayarTunggu label={t("auth.checking")} />;

  return <KerangkaAplikasi>{children}</KerangkaAplikasi>;
}

/**
 * Kerangka, dibungkus penyedia navigasi supaya `useNavPending` tersedia di
 * dalamnya. Pembungkusnya berdiri di luar komponen ini karena bilah kemajuan
 * harus hidup di atas SELURUH layar, termasuk saat isinya sedang diganti.
 */
export default function Shell({ children }: { children: ReactNode }) {
  return (
    <NavigationProvider>
      <Gerbang>{children}</Gerbang>
    </NavigationProvider>
  );
}

/** Lebar sidebar. Rentang 240-260px: cukup untuk label terpanjang tanpa
    memakan lebar yang dibutuhkan tabel di sebelahnya. */
const LEBAR_PENUH = 252;
/** Mode rel: hanya ikon. Selebar ikon 16px di dalam tombol 36px, plus napas. */
const LEBAR_RINGKAS = 68;
const KUNCI_SIMPAN = "sidebar-ringkas";

function KerangkaAplikasi({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { t } = useI18n();

  /*
   * Sorotan navigasi memakai alamat TUJUAN selama perpindahan berlangsung,
   * bukan alamat yang sedang terbuka. Menunggu halaman siap sebelum menyalakan
   * butir yang diklik membuat sidebar terasa lambat justru pada saat pengguna
   * paling memperhatikannya -- tepat setelah ia menekan sesuatu.
   */
  const pending = useNavPending();
  const jalur = pending ?? pathname;

  // Navigasi yang benar-benar ditampilkan kepada pengguna ini. Bagian yang
  // seluruh isinya tersaring ikut hilang, supaya tidak ada label bagian yang
  // berdiri di atas ruang kosong.
  const { bolehMengelola } = useAuth();
  const nav = useMemo(
    () =>
      NAV.map((g) => ({ ...g, items: g.items.filter((i) => !i.kelola || bolehMengelola) }))
        .filter((g) => g.items.length > 0),
    [bolehMengelola],
  );
  /*
   * Laci navigasi untuk layar sempit.
   *
   * Isinya PERSIS sama dengan sidebar -- kelompok, urutan, ikon, dan
   * penyaringan hak yang sama -- karena keduanya membaca `nav` yang sama.
   * Pengaturan tetap tidak ikut di sini: di layar sempit pun ia dicapai lewat
   * popup akun, dan laci ini adalah pengganti sidebar, bukan daftar segalanya.
   */
  const [laci, setLaci] = useState(false);
  const pemicuLaci = useRef<HTMLButtonElement | null>(null);
  /*
   * `useCallback` DENGAN daftar kosong, dan itu bukan optimasi.
   *
   * Laci memasang pengunci gulir dan memindahkan fokus di dalam sebuah efek
   * yang bergantung pada fungsi ini. Fungsi yang lahir baru pada setiap render
   * membuat efek itu dibongkar-pasang pada setiap render pula -- dan
   * pemindahan fokusnya ikut terulang, sehingga fokus direbut kembali ke panel
   * setiap kali apa pun di kerangka ini berubah.
   */
  const tutupLaci = useCallback(() => {
    setLaci(false);
    pemicuLaci.current?.focus();
  }, []);

  /*
   * Berpindah halaman menutup laci.
   *
   * Bergantung pada `jalur`, bukan `pathname`: sorotan navigasi sudah pindah
   * ke alamat tujuan begitu tautannya ditekan, dan laci yang menunggu halaman
   * benar-benar siap akan tetap terbuka selama satu detik penuh di atas
   * halaman yang sedang dimuat -- tepat pada saat orang menunggu melihatnya.
   */
  useEffect(() => {
    setLaci(false);
  }, [jalur]);

  /*
   * Melebarkan jendela melewati ambang `md` juga menutupnya. Tanpa ini, laci
   * yang terbuka pada ponsel yang diputar ke lanskap tetap mengunci gulir
   * halaman sementara panelnya sendiri sudah tidak dirender lagi -- halaman
   * yang membeku tanpa sebab yang terlihat.
   */
  useEffect(() => {
    if (!laci) return;
    const lebar = window.matchMedia("(min-width: 768px)");
    const cek = () => {
      if (lebar.matches) setLaci(false);
    };
    cek();
    lebar.addEventListener("change", cek);
    return () => lebar.removeEventListener("change", cek);
  }, [laci]);

  /*
   * Mode rel, diingat antar kunjungan.
   *
   * Dimulai dari `false` DAN BUKAN dari localStorage, karena berkas ini
   * dirender lebih dulu di server: membaca localStorage saat render membuat
   * tampilan server dan tampilan peramban berbeda, dan React membuang seluruh
   * pohonnya lalu memasangnya ulang. Nilainya dipulihkan sesudah terpasang.
   */
  const [ringkas, setRingkas] = useState(false);
  useEffect(() => {
    try {
      setRingkas(localStorage.getItem(KUNCI_SIMPAN) === "1");
    } catch {
      /* localStorage dapat ditolak peramban; bawaannya sudah benar */
    }
  }, []);

  const ubahRingkas = () => {
    setRingkas((r) => {
      const next = !r;
      try {
        localStorage.setItem(KUNCI_SIMPAN, next ? "1" : "0");
      } catch {
        /* gagal menyimpan tidak boleh membatalkan perubahannya di layar */
      }
      return next;
    });
  };

  return (
    <div className="flex min-h-[100dvh]">
      <LaciNavigasi terbuka={laci} tutup={tutupLaci} nav={nav} jalur={jalur} />

      <aside
        className="hidden shrink-0 border-r transition-[width] duration-200 ease-out md:flex md:flex-col"
        style={{
          width: ringkas ? LEBAR_RINGKAS : LEBAR_PENUH,
          borderColor: "var(--border)",
          background: "var(--surface-1)",
        }}
      >
        {/* ---------- identitas produk ---------- */}
        <div
          className={`flex h-[60px] shrink-0 items-center ${
            ringkas ? "justify-center px-2" : "gap-2 px-4"
          }`}
        >
          {ringkas ? (
            // Rel 68px terlalu sempit untuk logo bertulisan: cukup ikon pausnya.
            <span
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white p-1"
              aria-hidden
            >
              <img src="/logo-xorca-icon.svg" alt="" className="h-full w-full object-contain" />
            </span>
          ) : (
            <>
            {/* Logo tanpa kotak; tulisannya berganti terang/gelap mengikuti tema. */}
            <img src="/logo-xorca-dark-text.svg" alt="Xorca" className="block h-6 w-auto shrink-0 dark:hidden" />
            <img src="/logo-xorca-light-text.svg" alt="Xorca" className="hidden h-6 w-auto shrink-0 dark:block" />
              <span className="font-display min-w-0 flex-1 truncate text-[12px] font-bold uppercase tracking-[0.02em] text-ink">
                {t("brand.short")}
              </span>
              <button
                type="button"
                onClick={ubahRingkas}
                title={t("shell.collapse")}
                aria-label={t("shell.collapse")}
                className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-muted transition hover:bg-surface-2 hover:text-ink"
              >
                <PanelLeftClose size={15} aria-hidden />
              </button>
            </>
          )}
        </div>

        <div className="mx-3 h-px shrink-0" style={{ background: "var(--border)" }} />

        {/* Pada mode rel tombolnya turun ke barisnya sendiri: lencana merek
            sudah memenuhi lebar rel, dan menumpuk keduanya di satu baris
            membuat keduanya terlalu kecil untuk disentuh dengan yakin. */}
        {ringkas && (
          <button
            type="button"
            onClick={ubahRingkas}
            title={t("shell.expand")}
            aria-label={t("shell.expand")}
            className="mx-auto mt-2 flex h-8 w-8 items-center justify-center rounded-lg text-muted transition hover:bg-surface-2 hover:text-ink"
          >
            <PanelLeftOpen size={15} aria-hidden />
          </button>
        )}

        {/* ---------- bagian navigasi ---------- */}
        <nav className={`flex-1 overflow-y-auto pb-3 ${ringkas ? "px-2" : "px-3"}`}>
          <DaftarNavigasi nav={nav} jalur={jalur} ringkas={ringkas} />
        </nav>

        {/*
         * KAKI SIDEBAR SENGAJA KOSONG.
         *
         * Dua hal pernah tinggal di sini dan keduanya dicabut pada
         * 2 September 2026:
         *
         *   Pengaturan   pindah seluruhnya ke popup akun di kanan atas.
         *                Mempertahankan salinannya di sini berarti satu
         *                halaman punya dua pintu berjarak satu layar, dan
         *                pembaca yang menemukan keduanya wajar bertanya
         *                apakah keduanya menuju tempat yang sama.
         *   "Angka langsung dari basis data"  keterangan yang benar tetapi
         *                tidak menjawab pertanyaan siapa pun. Ia menempel di
         *                setiap layar sepanjang hari untuk menyampaikan satu
         *                hal yang hanya menarik sekali, pada kunjungan
         *                pertama -- dan titik hijau berdenyutnya menarik
         *                perhatian yang seharusnya jatuh ke angka yang
         *                memang berubah.
         *
         * Navigasi berakhir di tautan terakhirnya, dan ruang di bawahnya
         * dibiarkan kosong. Ruang kosong bukan kekurangan.
         */}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header
          className="glass-bar sticky top-0 z-30 flex h-14 items-center gap-2 border-b px-3 sm:gap-3 sm:px-5 md:h-[60px] md:justify-end"
          style={{ borderColor: "var(--border)" }}
        >
          {/*
           * Sisi kiri hanya ada di layar sempit: di layar lebar identitas
           * produk sudah berdiri di kepala sidebar, dan mengulanginya di bilah
           * atas membuat nama yang sama tercetak dua kali berjarak dua senti.
           *
           * `min-w-0` pada pembungkusnya DAN `truncate` pada namanya bukan
           * kerapian: tanpa keduanya, nama produk mendorong kendali di kanan
           * keluar dari layar pada ponsel 320px, dan yang terdorong keluar
           * adalah menu akun -- satu-satunya jalan keluar dari aplikasi.
           */}
          <div className="flex min-w-0 flex-1 items-center gap-1.5 md:hidden">
            <button
              ref={pemicuLaci}
              type="button"
              onClick={() => setLaci(true)}
              aria-label={t("shell.open_menu")}
              aria-expanded={laci}
              title={t("shell.open_menu")}
              className="-ml-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg text-ink-2 transition hover:bg-surface-2"
            >
              <Menu size={20} aria-hidden />
            </button>
            <Link href="/" className="flex min-w-0 items-center gap-2">
              {/* Logo tanpa kotak; tulisannya berganti terang/gelap mengikuti tema. */}
              <img src="/logo-xorca-dark-text.svg" alt="Xorca" className="block h-6 w-auto shrink-0 dark:hidden" />
              <img src="/logo-xorca-light-text.svg" alt="Xorca" className="hidden h-6 w-auto shrink-0 dark:block" />
              <span className="font-display min-w-0 flex-1 truncate text-[12px] font-bold uppercase tracking-[0.02em] text-ink">
                {t("brand.short")}
              </span>
            </Link>
          </div>

          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            {/* Sakelar bahasa turun ke kaki laci pada layar sempit; lihat
                catatannya di LaciNavigasi. */}
            <div className="hidden md:block">
              <LangToggle />
            </div>
            <ThemeToggle />
            <div
              className="mx-1 hidden h-5 w-px sm:block"
              style={{ background: "var(--border)" }}
            />
            <MenuAkun />
          </div>
        </header>

        {/*
          Kunci pada pathname membuat React MENGGANTI pohon isi, bukan
          memperbaruinya -- sehingga animasi masuk benar-benar terputar ulang
          pada setiap halaman baru, bukan hanya pada pemuatan pertama.
        */}
        <main className="flex-1 px-4 py-5 sm:px-5 sm:py-6 lg:px-8">
          <div key={pathname} className="page-enter">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
