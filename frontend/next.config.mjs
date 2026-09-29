/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Hanya berlaku saat `next dev`. Tanpa ini, membuka dashboard lewat alamat
  // jaringan (bukan localhost) memunculkan peringatan cross-origin pada
  // permintaan aset /_next/*, dan pada Next versi mayor berikutnya akan
  // ditolak. Diperlukan bila demo dibuka dari laptop/HP lain di jaringan
  // yang sama. Tidak berpengaruh pada build produksi.
  allowedDevOrigins: ["172.16.100.18", "localhost", "127.0.0.1"],

  /*
   * HTML halaman TIDAK boleh disimpan browser, berkas /_next/static boleh
   * selamanya.
   *
   * Nama berkas chunk mengandung hash isinya dan berganti pada setiap build.
   * Bawaan Next untuk halaman prerender adalah `s-maxage=31536000` tanpa
   * `max-age`: cache bersama terurus, tetapi browser dibiarkan memakai
   * heuristiknya sendiri dan kerap menyajikan HTML lama. HTML lama itu
   * menunjuk chunk yang sudah tidak ada, jawabannya 404, dan halamannya
   * berhenti dirakit -- daftar gudang kosong, daftar barang kosong, tanpa
   * satu pun galat yang menyebut sebabnya. Setiap deploy mengulanginya, dan
   * satu-satunya jalan keluar bagi pengguna adalah hard reload yang mustahil
   * ditebak sendiri.
   *
   * must-revalidate + no-cache: browser tetap menyimpan salinannya, tetapi
   * wajib menanyakan ETag lebih dulu. Bila tidak ada deploy baru jawabannya
   * 304 dan tidak ada byte yang berpindah, jadi ini bukan mematikan cache.
   */
  async headers() {
    return [
      {
        source: "/:path((?!_next/static|_next/image|favicon.ico).*)",
        headers: [
          { key: "Cache-Control", value: "no-cache, must-revalidate" },
        ],
      },
      {
        source: "/_next/static/:path*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
    ];
  },
};

export default nextConfig;
