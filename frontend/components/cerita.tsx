"use client";

import { Insight } from "@/components/ui";
import { Narasi } from "@/lib/forecast-types";

/**
 * Cerita halaman: kesimpulan lebih dulu, angka menyusul.
 *
 * KENAPA KALIMATNYA TIDAK DISUSUN DI SINI. Setiap kalimat di bawah menyebut
 * angka yang sama dengan kartu di bawahnya, dan angka itu disisipkan saat
 * kalimatnya dirakit di backend (app/i18n.py, app/decision.py). Komponen ini
 * hanya menatanya. Menyusun ulang di layar berarti satu kesimpulan punya dua
 * rumusan yang bisa berbeda bunyi setelah salah satunya diubah -- dan yang
 * lebih buruk, dua angka yang bisa berbeda nilai.
 *
 * Tiga lapis, dan urutannya disengaja: judul menjawab "jadi apa", paragraf
 * menjawab "kenapa begitu", catatan kaki menyebut di atas data seberapa tebal
 * seluruhnya berdiri. Pembaca yang berhenti di baris pertama tetap membawa
 * pulang kesimpulan yang benar.
 *
 * `tanpaJudul` UNTUK LAYAR YANG SUDAH MENGUCAPKAN KESIMPULANNYA SENDIRI.
 * Judulnya berbunyi "Pesan 1554 KG" -- kalimat yang sama persis dengan
 * headline panel keputusan di halaman Pemesanan Ulang. Di layar itu ia
 * pengulangan: satu angka yang berujung pada pengeluaran uang tercetak dua
 * kali dalam satu gulungan layar, dan pembaca yang melihatnya berulang mulai
 * memeriksa apakah keduanya benar-benar sama alih-alih mempercayai yang
 * pertama. Di halaman Prakiraan tidak ada panel keputusan, jadi judulnya tetap
 * terbit di sana -- itulah satu-satunya tempat angka itu diucapkan.
 */
export function Cerita({
  narasi,
  tone = "neutral",
  tanpaJudul = false,
}: {
  narasi: Narasi | null | undefined;
  tone?: "neutral" | "warning" | "critical";
  /** Sembunyikan judul karena layar pemanggil sudah mencetak kesimpulan yang sama. */
  tanpaJudul?: boolean;
}) {
  if (!narasi?.paragraf?.length) return null;
  const judul = tanpaJudul ? null : narasi.judul;

  return (
    <Insight tone={tone}>
      {judul ? (
        <p className="font-display t-lead font-bold leading-snug text-ink">
          {judul}
        </p>
      ) : null}
      {/*
       * Kalimatnya digabung menjadi SATU paragraf, bukan daftar berbutir.
       * Butir memaksa pembaca menyusun sendiri hubungan antarbaris; paragraf
       * sudah membawa hubungan itu di dalam urutannya -- yang terjadi, ke mana
       * arahnya, apa tindakannya.
       */}
      <p className={judul ? "mt-1.5" : ""}>{narasi.paragraf.join(" ")}</p>
      {narasi.dasar ? (
        <p className="mt-2 t-body leading-relaxed text-ink-2">{narasi.dasar}</p>
      ) : null}
    </Insight>
  );
}
