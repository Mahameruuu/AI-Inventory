/**
 * Penyimpanan token, terpisah dari segalanya yang lain.
 *
 * KENAPA BERKAS SENDIRI. lib/api.ts butuh token untuk menyisipkannya ke setiap
 * permintaan, dan lib/auth.tsx butuh api untuk memanggil /api/auth/login.
 * Keduanya saling membutuhkan, dan menaruh token di salah satunya membuat
 * lingkaran impor. Berkas ini tidak mengimpor apa pun, sehingga keduanya boleh
 * bergantung padanya.
 *
 * KENAPA localStorage DAN BUKAN COOKIE httpOnly. Cookie httpOnly memang lebih
 * tahan XSS, tetapi menuntut backend dan frontend berbagi domain atau
 * menyiapkan CORS berkredensial beserta perlindungan CSRF-nya. Dashboard ini
 * dibuka lewat alamat IP yang berganti-ganti saat demo (lihat CORS_ORIGIN_REGEX
 * pada .env), sehingga syarat itu tidak terpenuhi hari ini. Pilihan ini dicatat
 * di sini supaya ia terbaca sebagai keputusan, bukan kelalaian -- dan supaya
 * jelas apa yang harus berubah lebih dulu bila kelak ingin dipindahkan.
 */

const KUNCI = "inventory.token";

// Salinan di memori supaya permintaan tidak perlu menyentuh localStorage setiap
// kali. localStorage tetap sumber kebenarannya saat halaman dimuat ulang.
let token: string | null = null;
let sudahDibaca = false;

const pendengar = new Set<() => void>();

export function bacaToken(): string | null {
  if (typeof window === "undefined") return null; // saat prerender di server
  if (!sudahDibaca) {
    try {
      token = window.localStorage.getItem(KUNCI);
    } catch {
      // Peramban dengan penyimpanan situs dimatikan. Aplikasi tetap jalan,
      // hanya tidak mengingat sesi setelah halaman ditutup.
      token = null;
    }
    sudahDibaca = true;
  }
  return token;
}

export function simpanToken(nilai: string | null): void {
  token = nilai;
  sudahDibaca = true;
  if (typeof window === "undefined") return;
  try {
    if (nilai) window.localStorage.setItem(KUNCI, nilai);
    else window.localStorage.removeItem(KUNCI);
  } catch {
    /* diabaikan dengan sengaja: lihat catatan pada bacaToken */
  }
}

/**
 * Mendengarkan berakhirnya sesi. Mengembalikan fungsi pembatalan.
 *
 * Dipakai AuthProvider supaya satu permintaan yang dijawab 401 di sudut mana
 * pun aplikasi langsung memulangkan pengguna ke halaman masuk -- tanpa setiap
 * halaman perlu menangani kemungkinan itu sendiri.
 */
export function saatSesiBerakhir(fn: () => void): () => void {
  pendengar.add(fn);
  return () => pendengar.delete(fn);
}

export function akhiriSesi(): void {
  if (!bacaToken()) return; // tidak pernah masuk; tidak ada yang perlu diakhiri
  simpanToken(null);
  pendengar.forEach((fn) => fn());
}
