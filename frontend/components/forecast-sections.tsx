"use client";

/**
 * Blok-blok halaman Prakiraan / Forecasting page blocks.
 *
 * SATU PERTANYAAN: apa yang kemungkinan terjadi pada stok barang ini. Bukan
 * "berapa yang harus dibeli" -- itu pertanyaan halaman Pemesanan Ulang, dan
 * tidak ada satu pun jumlah pesanan, titik pesan efektif, atau status
 * pengadaan yang dirender dari berkas ini.
 *
 * Konsekuensinya sengaja: apa pun yang dirender file ini BOLEH berubah ketika
 * Periode diganti. Satu-satunya kekecualian dinyatakan terang-terangan --
 * masa tunggu dan stok pengaman pada panel detail, yang memang berpatokan lead
 * time dan diberi keterangan bahwa ia tidak ikut bergerak.
 *
 * Urutan bloknya mengikuti urutan orang membaca: kesimpulan (banner), angka
 * (empat kartu), bentuknya sepanjang waktu (grafik), lalu asal-usulnya (panel
 * detail yang tertutup). Pembaca yang berhenti di baris pertama tetap membawa
 * pulang jawaban yang benar.
 */

import Link from "next/link";
import { AlertTriangle, ArrowRight, LineChart, TrendingUp } from "lucide-react";

import { StockForecastChart } from "@/components/charts";
import { Blok, KartuKeputusan, angka } from "@/components/forecast-ui";
import { Card, Insight, Section, Table, Td } from "@/components/ui";
import { Forecast } from "@/lib/forecast-types";
import { useT } from "@/lib/i18n";
import { num } from "@/lib/format";

/* ------------------------------------------------------------------ */
/* Banner status prakiraan                                             */
/* ------------------------------------------------------------------ */

/**
 * Kondisi prakiraan dalam satu kalimat, dengan dua angka penopangnya.
 *
 * MENGGANTIKAN BLOK CERITA. Cerita disusun backend dari lapisan KEPUTUSAN:
 * judulnya berbunyi "Pesan 3 Meter" dan paragraf terakhirnya mengulang
 * `order_qty_reason`. Kalimat itu benar, tetapi ia menjawab pertanyaan halaman
 * sebelah -- dan begitu ia tercetak di sini, halaman Prakiraan kembali menjadi
 * layar keputusan pembelian, persis keadaan yang pemisahan kedua halaman ini
 * dibuat untuk mengakhiri. Yang tersisa di sini hanya kesimpulan tentang
 * STOK: kapan ia habis, atau kapan ia menyentuh titik pesan.
 *
 * TIGA KEADAAN, DIURUT DARI YANG PALING MENDESAK. Ketiganya dibaca dari
 * lapisan prakiraan saja, bukan dari `action_status`:
 *
 *   habis        `days_until_stockout` terisi -- proyeksi menyentuh nol di
 *                dalam periode yang dipilih.
 *   titik pesan  `days_until_reorder_point` terisi -- proyeksi memotong garis
 *                titik pesan, tetapi belum sampai nol.
 *   cukup        tidak keduanya.
 *
 * Keduanya DIBATASI PANJANG PERIODE: kosong berarti "tidak terjadi di dalam
 * {n} hari ini", bukan "tidak akan pernah terjadi". Karena itu kalimat amannya
 * menyebut periodenya secara eksplisit ("sepanjang 90 hari ke depan") dan
 * tidak pernah berbunyi "stok aman" tanpa batas waktu.
 *
 * CTA-nya kecil dan satu-satunya. Ia mengakui bahwa pertanyaan berikutnya
 * memang "lalu pesan berapa", tanpa menjawabnya di sini.
 */
export function BannerPrakiraan({ data }: { data: Forecast }) {
  const t = useT();
  const satuan = data.item.unit_code ?? "";

  const habis = data.days_until_stockout;
  const menyentuh = data.days_until_reorder_point;
  const adaLaju = Boolean(data.average_daily_usage);

  const nada: "neutral" | "warning" | "critical" =
    habis !== null ? "critical" : menyentuh !== null ? "warning" : "neutral";

  const judul =
    habis !== null
      ? t("fc.banner.stockout", { n: num(habis) })
      : menyentuh !== null
        ? t("fc.banner.rop", { n: num(menyentuh) })
        : adaLaju
          ? t("fc.banner.safe", { n: data.forecast_days })
          : t("fc.banner.idle");

  return (
    <Insight tone={nada}>
      <p className="font-display t-lead font-bold leading-snug text-ink">{judul}</p>

      {/* Dua angka penopang, bukan seluruh kartu diulang. Yang satu keadaan
          sekarang, yang lain kebutuhan sepanjang periode -- selisih keduanya
          persis yang membuat kalimat di atas berbunyi seperti itu. */}
      <p className="mt-2 flex flex-wrap items-baseline gap-x-5 gap-y-1 t-body leading-relaxed text-ink-2">
        <span>
          {t("fc.banner.stock")}:{" "}
          <span className="tnum font-semibold text-ink">
            {angka(data.current_stock_int, satuan)}
          </span>
        </span>
        <span>
          {t("fc.banner.need", { n: data.forecast_days })}:{" "}
          <span className="tnum font-semibold text-ink">
            {angka(data.forecast_usage_int, satuan)}
          </span>
        </span>
      </p>

      {/* Catatan mutu histori HANYA saat histori itu benar-benar membatasi.
          Kalimatnya menyebut tiga angka sekaligus dan panjangnya nyaris
          sebaris penuh; dicetak pada setiap barang ia menjadi hiasan tetap
          yang berhenti dibaca justru sebelum barang yang memerlukannya tiba.
          Pada mutu yang memadai, kartu grafik di bawah sudah menyebutkannya
          dengan cara yang jauh lebih ringkas ("Histori 90 hari · mutu data
          tinggi"), dan panel detail memuat alasan lengkapnya.

          Kembaran LAPISAN PRAKIRAAN yang dipakai, bukan confidence_note milik
          lapisan reorder: historinya satu dan sama, tetapi daftar angka yang
          disebutnya harus angka yang benar-benar tercetak di halaman ini. */}
      {data.low_confidence_estimate && data.confidence_note_forecast ? (
        <p className="mt-2 t-body leading-relaxed text-ink-2">
          {data.confidence_note_forecast}
        </p>
      ) : null}

      <Link
        href="/reorder"
        className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold"
        style={{ color: "var(--brand)" }}
      >
        {t("fc.banner.cta")} <ArrowRight size={13} />
      </Link>
    </Insight>
  );
}

/**
 * Ambang di mana laju harian masih layak dicetak sebagai pecahan.
 *
 * Laju harian TIDAK boleh dicetak sebagai pecahan tanpa syarat. Pada barang
 * yang keluar sekali dalam dua bulan, "0,016 PCS/hari" dibulatkan menjadi
 * "0,0 PCS/hari" -- rapi, dan salah: kartunya lalu berbunyi nol untuk barang
 * yang jelas terpakai. Di atas ambang ini satu desimal masih membawa isi
 * ("0,1 METER/hari"); di bawahnya kartu jatuh ke label frekuensi, yang
 * membalik pertanyaannya menjadi "±1 PCS per 62 hari" -- tetap benar pada
 * laju serendah apa pun.
 *
 * 0,05 karena itulah titik pembulatan satu desimal: di bawahnya hasilnya
 * "0,0", di atasnya paling kecil "0,1".
 */
const AMBANG_LAJU_PECAHAN = 0.05;

/**
 * Prediksi Kebutuhan / Demand Prediction.
 *
 * EMPAT KARTU, dan keempatnya menjawab pertanyaan yang sama dari empat arah:
 * berapa yang akan terpakai, seberapa cepat terpakainya, berapa yang tersisa,
 * dan kapan habisnya. Tidak satu pun menyebut jumlah yang harus dibeli.
 *
 * Ketiga kartu pertama berpatokan periode yang dipilih. Kartu keempat --
 * perkiraan stok habis -- juga: `days_until_stockout` dihitung DI DALAM
 * horizon prakiraan dan kosong bila stok tidak menyentuh nol sepanjang itu.
 * Kosong karena itu TIDAK dicetak sebagai "—" seolah tidak terhitung,
 * melainkan sebagai "> 90 hari": yang diketahui bukan ketiadaan jawaban,
 * melainkan bahwa jawabannya berada di luar jendela yang sedang dilihat.
 *
 * Pernah ada kartu "Potensi kekurangan" di posisi keempat, yang dibuang karena
 * hampir selalu berbunyi "Tidak ada" pada periode bawaan 7 hari. Kartu habis
 * stok tidak mengulanginya: ia menjawab KAPAN, bukan BERAPA, dan itulah satu-
 * satunya bentuk pertanyaan yang halaman ini memang berhak menjawab.
 */
export function ForecastSummary({ data }: { data: Forecast }) {
  const t = useT();
  const satuan = data.item.unit_code ?? "";

  /* --- kartu 2: laju pemakaian --- */
  const laju = data.average_daily_usage;
  const lajuPecahan = laju !== null && laju >= AMBANG_LAJU_PECAHAN;
  // Label frekuensi backend dipakai sebagai keterangan saat lajunya di bawah
  // satu unit per hari: di situlah "±1 METER per 10 hari" benar-benar
  // menambah sesuatu yang tidak terbaca dari "0,1 METER/hari". Di atas satu
  // unit per hari ia hanya mengulang angka yang sama dengan pembulatan lain,
  // dan dua angka mirip berdampingan membuat pembaca memeriksa alih-alih
  // membaca.
  const lajuDiBawahSatu = laju !== null && laju > 0 && laju < 1;
  const nilaiLaju = lajuPecahan
    ? t("fc.need.per_day", { v: num(laju, 1), u: satuan })
    : data.usage_frequency_label;
  const detailLaju = !lajuPecahan
    ? data.usage_frequency_detail
    : lajuDiBawahSatu
      ? `${data.usage_frequency_label} ${data.usage_frequency_detail}`.trim()
      : t("fc.need.rate_detail", { n: data.data_quality.history_days });

  /* --- kartu 4: perkiraan stok habis --- */
  const habis = data.days_until_stockout;
  const adaLaju = Boolean(laju);
  const nilaiHabis =
    habis !== null
      ? t("fc.need.days_pm", { n: num(habis) })
      : adaLaju
        ? t("fc.need.stockout_beyond", { n: data.forecast_days })
        : "—";
  const detailHabis =
    habis !== null
      ? t("fc.need.stockout_detail")
      : adaLaju
        ? t("fc.need.stockout_beyond_detail", { n: data.forecast_days })
        : t("fc.need.stockout_idle_detail");

  return (
    <Blok
      Ikon={TrendingUp}
      judul={t("fc.need.title")}
      keterangan={t("fc.need.note", { n: data.forecast_days })}
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <KartuKeputusan
          label={t("fc.need.usage", { n: data.forecast_days })}
          nilai={angka(data.forecast_usage_int, satuan)}
          detail={t("fc.need.usage_detail")}
          aksen="var(--brand)"
        />
        <KartuKeputusan label={t("fc.need.rate")} nilai={nilaiLaju} detail={detailLaju} />
        <KartuKeputusan
          label={t("fc.need.left")}
          nilai={angka(data.expected_stock_int, satuan)}
          detail={t("fc.need.left_detail", { n: data.forecast_days })}
        />
        {/* Garis aksen HANYA saat stok benar-benar habis di dalam periode.
            "> 90 hari" adalah kabar baik, dan memberinya warna status akan
            membuat kartu yang tenang terbaca segenting kartu yang tidak.

            KETERANGANNYA TIDAK IKUT DIMERAHKAN. Kalimat "dihitung dari hari
            ini pada laju pemakaian saat ini" tidak membawa kabar buruk apa
            pun -- ia menerangkan cara menghitung. Dicat merah, kartu ini
            terbaca seperti galat, dan merahnya berhenti berarti "genting"
            karena dipakai untuk dua hal sekaligus. Yang genting adalah
            angkanya, dan itu sudah ditandai garis aksen di tepi atas. */}
        <KartuKeputusan
          label={t("fc.need.stockout")}
          nilai={nilaiHabis}
          detail={detailHabis}
          aksen={habis !== null ? "var(--status-critical)" : undefined}
        />
      </div>
    </Blok>
  );
}

/**
 * Proyeksi Stok / Stock Projection.
 *
 * Garis titik pesan tetap digambar sebagai KONTEKS VISUAL -- pembaca perlu
 * tahu di ketinggian mana garis proyeksi itu bergerak. Yang tidak ada di sini
 * adalah keputusannya: kapan harus memesan dan berapa banyak dijawab halaman
 * Pemesanan Ulang.
 */
export function ForecastChart({ data }: { data: Forecast }) {
  const t = useT();
  return (
    <Blok Ikon={LineChart} judul={t("fc.proj.title")} keterangan={t("fc.proj.note")}>
      <Card
        meta={t("fc.proj.meta", {
          n: data.data_quality.history_days,
          q: data.data_quality.label,
        })}
      >
        <StockForecastChart
          historical={data.historical}
          forecast={data.forecast}
          reorderPoint={data.reorder_point_int}
          unit={data.item.unit_code ?? ""}
          crossingDate={data.reorder_crossing_date}
          crossingLabel={
            data.days_until_reorder_point
              ? t("fc.chart.days_left", { n: data.days_until_reorder_point })
              : ""
          }
        />
      </Card>
    </Blok>
  );
}

/**
 * Detail perhitungan prakiraan.
 *
 * Kartu di atas menjawab "berapa kebutuhannya"; bagian ini menjawab "dari mana
 * angkanya" -- dan itu tetap harus bisa diperiksa siapa pun yang meragukannya.
 *
 * TERTUTUP SECARA BAWAAN, lewat `Section` yang berupa <details> asli sehingga
 * tetap ramah keyboard dan pembaca layar. Yang dibutuhkan hampir semua orang
 * hanyalah empat kartu dan grafiknya; rantai turunannya baru dibuka ketika ada
 * yang meragukan salah satu angka. Memaksanya selalu terbuka mengubah halaman
 * prakiraan menjadi laporan uji.
 *
 * Panel ini juga BILANGAN BULAT, sama seperti kartunya. Sebelumnya ia
 * menampilkan nilai desimal penuh beserta rumus bersubstitusi; begitu angka
 * layar dibulatkan, rumus itu justru menjadi sumber keraguan baru ("1 × 90 =
 * 104" terbaca sebagai salah hitung). Nilai desimalnya tetap terkirim pada
 * field `raw` tiap baris bagi siapa pun yang perlu menelusurinya lewat API.
 *
 * Baris berjenis `status` DISARING keluar: itu status keputusan reorder, satu-
 * satunya baris pada panel ini yang bukan urusan prakiraan.
 *
 * MASA TUNGGU DAN STOK PENGAMAN DISISIPKAN sebagai seksi terakhir, walau
 * keduanya milik lapisan reorder. Keduanya masuk di sini sebagai SUMBER ANGKA,
 * bukan sebagai keputusan: pembaca yang menelusuri dari mana "±10 hari" datang
 * akan menanyakan keduanya cepat atau lambat, dan jawaban yang harus dicari di
 * layar lain memutus penelusuran tepat di tengah. Yang menjaga pemisahan kedua
 * halaman bukan ketiadaan angkanya di sini, melainkan tempatnya -- di dalam
 * panel yang tertutup, di bawah judul yang menyebutnya referensi, dengan
 * catatan yang menyatakan bahwa ia tidak bergerak saat periode diganti dan
 * bahwa keputusannya ada di halaman sebelah.
 */
export function ForecastCalculationDetail({ data }: { data: Forecast }) {
  const t = useT();
  const satuan = data.item.unit_code ?? "";
  const seksi = data.calculation_detail.sections
    .map((s) => ({ ...s, rows: s.rows.filter((r) => r.kind !== "status") }))
    .filter((s) => s.rows.length > 0);

  if (!seksi.length) return null;

  // Keduanya dari field `*_int` yang sama dengan yang dirender halaman
  // Pemesanan Ulang, jadi satu barang mustahil menyebut masa tunggu atau stok
  // pengaman yang berbeda di dua layar. null pada masa tunggu berarti belum
  // diisi pada master barang -- bukan nol hari.
  const parameter: { label: string; value: string }[] = [
    {
      label: t("fc.calc.lead_time"),
      value:
        data.lead_time_days_int !== null
          ? t("c.days", { n: num(data.lead_time_days_int) })
          : "—",
    },
    { label: t("fc.calc.safety"), value: angka(data.safety_stock_int, satuan) },
  ];

  return (
    <div className="mt-5">
      {/* Nama metode/model sengaja TIDAK ditampilkan. "xgboost_tweedie" bukan
          sesuatu yang bisa ditindaklanjuti pengguna gudang, dan menampilkannya
          membuat panel terbaca seperti keluaran alat internal. Yang perlu
          diaudit adalah angkanya, dan seluruh angkanya ada di tabel ini. */}
      <Section title={t("fc.calc.title")} subtitle={t("fc.calc.sub")}>
        <div className="flex max-w-2xl flex-col">
          {seksi.map((s, i) => (
            <div
              key={s.key}
              className={i > 0 ? "mt-4 border-t pt-4" : ""}
              style={i > 0 ? { borderColor: "var(--border)" } : undefined}
            >
              <h3 className="mb-1.5 t-body font-semibold text-ink-2">{s.title}</h3>
              <Table>
                <tbody>
                  {s.rows.map((baris) => (
                    <tr key={baris.label}>
                      <Td className="whitespace-nowrap align-top">{baris.label}</Td>
                      <Td align="right">
                        {baris.kind === "warning" ? (
                          <span
                            className="inline-flex items-start gap-1.5 text-left"
                            style={{ color: "var(--status-serious)" }}
                          >
                            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
                            {baris.value}
                          </span>
                        ) : (
                          <span className="tnum">{baris.value}</span>
                        )}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>
          ))}

          <div className="mt-4 border-t pt-4" style={{ borderColor: "var(--border)" }}>
            <h3 className="mb-1.5 t-body font-semibold text-ink-2">
              {t("fc.calc.params")}
            </h3>
            <Table>
              <tbody>
                {parameter.map((baris) => (
                  <tr key={baris.label}>
                    <Td className="whitespace-nowrap align-top">{baris.label}</Td>
                    <Td align="right">
                      <span className="tnum">{baris.value}</span>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <p className="mt-2.5 text-xs leading-relaxed text-muted">
              {t("fc.calc.params_note")}
            </p>
          </div>
        </div>
      </Section>
    </div>
  );
}

/**
 * Histori belum cukup untuk memprakirakan.
 *
 * Tabelnya menyebut AMBANG KECUKUPAN DATA saja. Parameter master seperti titik
 * pesan tidak ikut di sini walau tersedia: halaman ini tidak menjawab
 * pertanyaan tentangnya, dan menampilkannya hanya karena kebetulan ada akan
 * mengembalikan percampuran yang justru sedang dibongkar.
 */
export function ForecastUnavailable({ data }: { data: Forecast }) {
  const t = useT();
  const satuan = data.item.unit_code ?? "";

  return (
    <div className="surface-card rise px-6 py-12 text-center">
      <span
        aria-hidden
        className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl"
        style={{
          background: "color-mix(in srgb, var(--status-warning) 14%, transparent)",
          color: "var(--status-warning)",
        }}
      >
        <AlertTriangle size={21} />
      </span>
      <h2 className="font-display mt-4 text-base font-bold text-ink">
        {data.item.usage_type === "berumur_pakai" ? t("fc.na.title_umur") : t("fc.na.title")}
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-muted">
        {data.item.usage_type === "berumur_pakai"
          ? t("fc.na.body_umur")
          : (data.message ?? t("fc.na.body"))}
      </p>

      <div className="mx-auto mt-6 max-w-sm text-left">
        <Table>
          <tbody>
            <tr>
              <Td>{t("fc.na.available")}</Td>
              <Td align="right" numeric>
                {t("c.days", { n: data.requirements.actual_history_days })}
              </Td>
            </tr>
            <tr>
              <Td>{t("fc.na.minimum")}</Td>
              <Td align="right" numeric>
                {t("c.days", { n: data.requirements.min_history_days })}
              </Td>
            </tr>
            <tr>
              <Td>{t("fc.na.outflow_days")}</Td>
              <Td align="right" numeric>
                {t("fc.na.of_min", {
                  a: data.requirements.actual_days_with_outflow,
                  b: data.requirements.min_days_with_outflow,
                })}
              </Td>
            </tr>
            <tr>
              <Td>{t("fc.na.current")}</Td>
              <Td align="right" numeric>
                {num(data.current_stock_int)} {satuan}
              </Td>
            </tr>
          </tbody>
        </Table>
      </div>

      <p className="mx-auto mt-6 max-w-md text-xs leading-relaxed text-muted">
        {t("fc.na.footer")}
      </p>

      {/*
        Untuk komponen berumur tahunan, kalimat penutup di atas keliru: tidak
        ada jumlah pemakaian yang akan membuat ambangnya terpenuhi, karena
        pemakaiannya memang sekali dalam beberapa tahun. Yang diketahui dengan
        pasti tentang barang itu justru bukan ramalannya melainkan umur
        pakainya, dan itulah yang ditampilkan di sini.
      */}
      <JadwalPenggantian data={data} />
    </div>
  );
}

/**
 * Isi tabel jadwal, tanpa bingkai.
 *
 * Dipakai dua kali dengan bingkai yang berbeda: sebagai sisipan pada kartu
 * "prakiraan belum tersedia", dan sebagai blok tersendiri pada halaman yang
 * prakiraannya ada. Isinya satu, karena satu barang tidak boleh menyebut
 * tanggal jatuh tempo yang berbeda hanya karena layarnya berbeda.
 */
function IsiJadwal({ u }: { u: NonNullable<Forecast["service_life"]> }) {
  const t = useT();
  const sisa = u.days_remaining;
  return (
    <>
      <div>
        <Table>
          <tbody>
            <tr>
              <Td>{t("fc.life.service_life")}</Td>
              <Td align="right" numeric>
                {num(u.value)} {u.unit}
              </Td>
            </tr>
            <tr>
              <Td>{t("fc.life.last")}</Td>
              <Td align="right" numeric>
                {u.last_replacement ?? t("fc.life.never")}
              </Td>
            </tr>
            {u.due_date && (
              <tr>
                <Td>{t("fc.life.due")}</Td>
                <Td align="right" numeric>
                  {u.due_date}
                </Td>
              </tr>
            )}
            {sisa !== null && (
              <tr>
                <Td>{t("fc.life.remaining")}</Td>
                {/*
                  Sisa negatif TIDAK dijepit ke nol: komponen yang sudah lewat
                  jatuh tempo adalah persis keadaan yang halaman ini harus
                  teriakkan, bukan yang ia bulatkan menjadi "habis".
                */}
                <Td align="right" numeric>
                  <span style={sisa < 0 ? { color: "var(--status-danger)" } : undefined}>
                    {sisa < 0
                      ? t("fc.life.overdue", { n: num(-sisa) })
                      : t("c.days", { n: num(sisa) })}
                  </span>
                </Td>
              </tr>
            )}
          </tbody>
        </Table>
      </div>
      {u.unit === "jam" && (
        <p className="mt-3 text-xs leading-relaxed text-muted">{t("fc.life.hours_note")}</p>
      )}
    </>
  );
}

/** Sisipan pada kartu "prakiraan belum tersedia". */
export function JadwalPenggantian({ data }: { data: Forecast }) {
  const t = useT();
  const u = data.service_life;
  if (!u) return null;
  return (
    <div className="mx-auto mt-8 max-w-sm text-left">
      <h3 className="font-display text-sm font-bold text-ink">{t("fc.life.title")}</h3>
      <p className="mt-1 text-xs leading-relaxed text-muted">{t("fc.life.body")}</p>
      <div className="mt-3">
        <IsiJadwal u={u} />
      </div>
    </div>
  );
}

