import type { Metadata, Viewport } from "next";
import "./globals.css";
import Shell from "@/components/Shell";
import { AuthProvider } from "@/lib/auth";
import { LangProvider } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "Inventory AI — Sistem Pendukung Keputusan Persediaan",
  description:
    "Visibilitas stok, analisis risiko, rekomendasi pembelian, analisis umur pakai, dan peramalan permintaan. Stock visibility, risk analysis, purchasing recommendations, lifetime analysis and demand forecasting.",
  icons: {
    icon: "/logo-sml.svg",
    shortcut: "/logo-sml.svg",
    apple: "/logo-sml.svg",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#eef2f9" },
    { media: "(prefers-color-scheme: dark)", color: "#070b14" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" suppressHydrationWarning>
      <body>
        {/*
          AuthProvider berada DI DALAM LangProvider: pesan galat pada halaman
          masuk diterjemahkan lewat kamus, sehingga penyedia bahasa harus sudah
          berdiri lebih dulu. Shell di dalam keduanya karena ia membaca dua-
          duanya.
        */}
        <LangProvider>
          <AuthProvider>
            <Shell>{children}</Shell>
          </AuthProvider>
        </LangProvider>
      </body>
    </html>
  );
}
