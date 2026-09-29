"use client";

/**
 * AI Inventory Forecasting.
 *
 * SATU PERTANYAAN SAJA: apa yang kemungkinan terjadi pada stok barang ini.
 *
 * Bukan "berapa yang harus dibeli". Halaman ini dulu memuat empat blok
 * sekaligus -- prakiraan, kondisi persediaan, keputusan reorder, dan pengadaan
 * -- sehingga terbaca sebagai layar keputusan pembelian, bukan layar
 * prakiraan. Yang paling merepotkan bukan panjangnya, melainkan patokan
 * waktunya: hanya blok prakiraan yang bergerak saat periode diganti, sedangkan
 * tiga blok lainnya berpatokan lead time. Satu layar dengan dua patokan waktu
 * membuat pembaca menyimpulkan bahwa mengubah pilihan "30 hari" ikut mengubah
 * urgensi pembelian.
 *
 * Ketiga blok itu kini berdiri di /reorder. Pemisahannya bukan penataan ulang
 * belaka: apa pun yang dirender halaman INI boleh berubah saat Period diganti,
 * dan apa pun yang tidak boleh berubah tidak lagi berada di sini.
 *
 * EMPAT BLOK, DAN TIDAK LEBIH:
 *
 *   1. Banner status  kesimpulan tentang stok dalam satu kalimat, dengan stok
 *                     saat ini dan perkiraan kebutuhan sebagai penopangnya.
 *                     CTA kecil ke /reorder mengakui pertanyaan berikutnya
 *                     tanpa menjawabnya di sini.
 *   2. Empat kartu    kebutuhan periode, laju pemakaian, sisa stok, dan
 *                     perkiraan kapan stok habis.
 *   3. Grafik         stok historis, proyeksi, garis hari ini, garis titik
 *                     pesan sebagai referensi visual -- bukan tempat menentukan
 *                     jumlah pesanan.
 *   4. Detail         panel tertutup berisi asal-usul seluruh angka di atas.
 *
 * TIGA HAL YANG SENGAJA TIDAK ADA DI SINI, dan sebabnya masing-masing:
 *
 *   Blok cerita          judulnya `order_qty_title` -- kalimatnya berbunyi
 *                        "Pesan 3 Meter". Itu jawaban halaman Pemesanan Ulang,
 *                        dan mencetaknya di sini mengembalikan percampuran yang
 *                        pemisahan kedua halaman ini dibuat untuk mengakhiri.
 *                        Digantikan BannerPrakiraan, yang membaca lapisan
 *                        prakiraan saja.
 *   Papan skor model     perlombaan antar model bersifat teknis: MASE dan
 *                        jumlah lipatan tidak dapat ditindaklanjuti petugas
 *                        gudang, dan kehadirannya di halaman utama membuat
 *                        layar terbaca sebagai laporan uji. Pemilih modelnya
 *                        tetap di baris filter -- yang dicabut hanya papan
 *                        skornya. Komponennya masih ada di components/
 *                        papan-model.tsx bila kelak dibutuhkan halaman teknis.
 *   Jadwal penggantian   konteksnya perawatan, bukan prakiraan: ia menakar
 *                        usia komponen, bukan pemakaian stok. Sejak 2
 *                        September 2026 pertanyaan itu punya halamannya
 *                        sendiri -- Analisis Umur Pakai -- sehingga blok yang
 *                        dulu disimpan menunggu halaman itu ikut dicabut.
 *                        Sisipannya pada kartu "prakiraan belum tersedia"
 *                        TETAP ADA: di sana ia bukan blok kedua di sebelah
 *                        prakiraan, melainkan satu-satunya yang diketahui
 *                        pasti tentang barangnya.
 *
 * Seluruh angka tetap berasal dari GET /api/forecast. Halaman tidak pernah
 * menghitung sendiri -- banner, kartu, grafik, dan panel detail memakai satu
 * sumber yang sama sehingga mustahil berselisih.
 */

import {
  BannerPrakiraan,
  ForecastCalculationDetail,
  ForecastChart,
  ForecastSummary,
  ForecastUnavailable,
} from "@/components/forecast-sections";
import {
  PemilihBarang,
  PemilihModel,
  PemilihPeriode,
  keteranganBarang,
  LencanaJenis,
  usePemilihanBarang,
  usePilihanModel,
  usePilihanPeriode,
} from "@/components/forecast-ui";
import { ErrorBox, PageHeader, PageSkeleton } from "@/components/ui";
import { useApi } from "@/lib/api";
import { Forecast } from "@/lib/forecast-types";
import { useT } from "@/lib/i18n";
import { TrendingUp } from "lucide-react";

export default function ForecastingPage() {
  const t = useT();
  // Tanpa pembatasan: seluruh barang di gudang yang dipilih. Lihat catatan
  // pada usePemilihanBarang tentang LINGKUP_SEMENTARA yang dicabut.
  const pilihan = usePemilihanBarang();
  // Periode dibagi dengan halaman Pemesanan Ulang; lihat usePilihanPeriode.
  const [days, setDays] = usePilihanPeriode();
  // Pilihan model dibagi dengan halaman Pemesanan Ulang; lihat catatan pada
  // usePilihanModel di forecast-ui.tsx.
  const [model, setModel] = usePilihanModel();

  const { data, error, loading } = useApi<Forecast>(
    pilihan.siap ? "/api/forecast" : null,
    {
      warehouse_id: pilihan.warehouseId || undefined,
      item_id: pilihan.itemId || undefined,
      days,
      model,
      // Panel saran memakai kalimat template yang disusun backend; halaman ini
      // tidak pernah menunggu layanan bahasa untuk menampilkan sesuatu. Ulasan
      // model bahasa tinggal di halaman Reorder, tempat keputusannya berada.
      include_recommendation: false,
    }
  );

  if (error) return <ErrorBox message={error} />;

  return (
    <>
      {/* Baris filter TETAP UTUH: Gudang, Barang, Periode, Model. Keempatnya
          adalah pertanyaan "prakiraan yang mana", bukan bagian dari
          jawabannya, jadi tidak satu pun ikut disederhanakan. */}
      <PageHeader
        icon={<TrendingUp size={20} />}
        eyebrow={t("nav.ai")}
        title={t("fc.title")}
        description={data ? keteranganBarang(data) : t("fc.desc")}
      >
        <div className="baris-saring flex flex-wrap items-end gap-3">
          <PemilihBarang pilihan={pilihan} />
          <PemilihPeriode periode={days} setPeriode={setDays} />
          <PemilihModel model={model} setModel={setModel} />
        </div>
      </PageHeader>

      {loading && !data ? (
        <PageSkeleton tiles={4} charts={1} rows={5} cols={2} />
      ) : !data ? (
        <p className="text-sm text-muted">{t("fc.pick")}</p>
      ) : (
        <div>
          <div className="mb-3">
            <LencanaJenis jenis={data.item.usage_type} />
          </div>
          {data.has_forecast ? (
            <>
              {/* Kesimpulan lebih dulu, angka menyusul. Nadanya diturunkan dari
                  lapisan PRAKIRAAN -- kapan stok habis atau menyentuh titik
                  pesan -- bukan dari status keputusan pengadaan, karena itulah
                  pertanyaan yang halaman ini jawab. */}
              <BannerPrakiraan data={data} />
              <ForecastSummary data={data} />
              <ForecastChart data={data} />
              <ForecastCalculationDetail data={data} />
            </>
          ) : (
            <ForecastUnavailable data={data} />
          )}
        </div>
      )}
    </>
  );
}
