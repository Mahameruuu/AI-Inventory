"use client";

/**
 * Blok-blok halaman Prakiraan / Forecasting page blocks.
 *
 * SATU PERTANYAAN: cukupkah stok barang ini untuk periode yang dipilih, dan
 * bila tidak, kurang berapa. Sejak 6 Oktober 2026 kekurangan itu DICETAK di
 * sini (kebutuhan periode dikurangi stok) atas permintaan pengguna. Jumlah
 * PESANAN tetap milik halaman Pemesanan Ulang: tidak ada titik pesan efektif,
 * stok pengaman yang ikut dihitung, atau status pengadaan yang dirender dari
 * berkas ini.
 *
 * Konsekuensinya sengaja: apa pun yang dirender file ini BOLEH berubah ketika
 * Periode diganti. Satu-satunya kekecualian dinyatakan terang-terangan --
 * masa tunggu dan stok pengaman pada panel detail, yang memang berpatokan lead
 * time dan diberi keterangan bahwa ia tidak ikut bergerak.
 *
 * Urutan bloknya mengikuti urutan orang membaca: kesimpulan (banner), angka
 * (tiga kartu: stok, kebutuhan, selisihnya), pemakaian hari demi hari (tabel
 * bilangan bulat), bentuknya sepanjang waktu (grafik), lalu asal-usulnya
 * (panel detail yang tertutup). Pembaca yang berhenti di baris pertama tetap membawa
 * pulang jawaban yang benar.
 */

import Link from "next/link";
import { AlertTriangle, ArrowRight, CalendarDays, LineChart, ShoppingCart, TrendingUp } from "lucide-react";

import { StockForecastChart } from "@/components/charts";
import { Blok, KartuKeputusan, angka } from "@/components/forecast-ui";
import { Card, Insight, Section, Table, Td, Th } from "@/components/ui";
import { Forecast } from "@/lib/forecast-types";
import { useT } from "@/lib/i18n";
import { dateLabel, num, shortDate } from "@/lib/format";

/* ------------------------------------------------------------------ */
/* Ringkasan periode: stok, kebutuhan, dan selisihnya                  */
/* ------------------------------------------------------------------ */

/**
 * Tiga angka yang menopang seluruh halaman, dibaca dari SATU tempat.
 *
 * Stok, kebutuhan, dan selisihnya harus genap di mata pembacanya: "stok 40,
 * butuh 55, kurang 15". Ketiganya karena itu diambil dari `daily_plan`, yang
 * membulatkan pemakaian kumulatif sekali lalu menurunkan sisa dan kekurangan
 * dari bilangan bulat yang sama. Tiga field `*_int` yang dibulatkan
 * sendiri-sendiri bisa berselisih satu ("40, 55, kurang 14"), dan selisih
 * satu itulah yang membuat orang berhenti mempercayai seluruh layar.
 *
 * Basis stoknya stok TERSEDIA -- yang sudah dicadangkan keluar tidak ikut
 * menutup kebutuhan baru. Tanpa stok tercadang ia sama dengan stok di rak.
 */
function ringkasPeriode(data: Forecast) {
  const rencana = data.daily_plan ?? [];
  const akhir = rencana.length ? rencana[rencana.length - 1] : null;
  const kurang = akhir?.shortage_int ?? 0;
  // Hari pertama stok menyentuh nol; hanya berarti bila memang ada pemakaian.
  const habis = rencana.find((b) => b.stock_int <= 0 && b.usage_int + b.shortage_int > 0) ?? null;
  return {
    rencana,
    stok: data.available_stock_int,
    butuh: data.forecast_usage_int ?? 0,
    sisa: akhir ? akhir.stock_int : data.available_stock_int,
    kurang,
    habis,
  };
}

/**
 * Kesimpulan dalam satu kalimat: cukup atau tidak, dan kurang berapa.
 *
 * Kalimatnya menjawab pertanyaan yang benar-benar diajukan orang gudang --
 * "stok saya cukup tidak untuk {n} hari ini?" -- dan bila tidak, langsung
 * menyebut jumlah yang kurang. Angka penopangnya ada pada tiga kartu tepat di
 * bawahnya, jadi tidak diulang di sini.
 *
 * Selalu menyebut periodenya: "cukup" tanpa batas waktu adalah janji yang
 * tidak pernah dibuat prakiraan.
 */
export function BannerPrakiraan({ data }: { data: Forecast }) {
  const t = useT();
  const satuan = data.item.unit_code ?? "";
  const n = data.forecast_days;
  const r = ringkasPeriode(data);

  const nada: "neutral" | "warning" | "critical" =
    r.kurang > 0 ? "critical" : r.habis ? "warning" : "neutral";

  const judul =
    r.kurang > 0
      ? t("fc.banner.short", { n, q: angka(r.kurang, satuan) })
      : r.habis
        ? t("fc.banner.exact", { n })
        : r.butuh > 0
          ? t("fc.banner.enough", { n, q: angka(r.sisa, satuan) })
          : t("fc.banner.none", { n });

  return (
    <Insight tone={nada}>
      <p className="font-display t-lead font-bold leading-snug text-ink">{judul}</p>

      {r.habis ? (
        <p className="mt-2 t-body leading-relaxed text-ink-2">
          {t("fc.banner.runout", { d: dateLabel(r.habis.date), h: r.habis.day })}
        </p>
      ) : null}

      {/* Catatan mutu histori HANYA saat histori itu benar-benar membatasi;
          dicetak pada setiap barang ia menjadi hiasan tetap yang berhenti
          dibaca justru sebelum barang yang memerlukannya tiba. */}
      {data.low_confidence_estimate && data.confidence_note_forecast ? (
        <p className="mt-2 t-body leading-relaxed text-ink-2">
          {data.confidence_note_forecast}
        </p>
      ) : null}

      {/* Angka "kurang" di atas murni selisih kebutuhan periode dan stok.
          Jumlah pesanan di halaman Pemesanan Ulang dihitung mesin lain yang
          ikut menimbang masa tunggu dan stok pengaman, jadi boleh lebih besar
          -- dan dikatakan terang-terangan supaya dua angka itu tidak dibaca
          sebagai dua jawaban yang berselisih. */}
      {r.kurang > 0 ? (
        <p className="mt-2 text-xs leading-relaxed text-muted">{t("fc.banner.order_note")}</p>
      ) : null}

      {/* TOMBOL saat stok kurang, tautan kecil saat tidak. Kekurangan adalah
          satu-satunya keadaan di halaman ini yang menuntut tindakan, jadi
          hanya di situ jalan keluarnya dibuat mencolok; pada stok yang cukup
          tombol yang sama akan mengajak memesan barang yang tidak perlu
          dipesan. Alamatnya membawa gudang dan SKU supaya halaman Pemesanan
          Ulang terbuka langsung pada barang ini. */}
      {r.kurang > 0 ? (
        <Link
          href={`/reorder?gudang=${data.warehouse.id}&cari=${encodeURIComponent(data.item.sku)}`}
          className="btn-brand mt-3 inline-flex h-10 items-center gap-2 whitespace-nowrap rounded-lg px-4 text-sm font-semibold transition"
        >
          <ShoppingCart size={15} /> {t("fc.banner.reorder_btn")} <ArrowRight size={14} />
        </Link>
      ) : (
        <Link
          href="/reorder"
          className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold"
          style={{ color: "var(--brand)" }}
        >
          {t("fc.banner.cta")} <ArrowRight size={13} />
        </Link>
      )}
    </Insight>
  );
}

/**
 * Tiga kartu: stok saat ini, kebutuhan periode, dan selisihnya.
 *
 * Kartu ketiga BERGANTI WUJUD menurut jawabannya. Saat stok tidak cukup ia
 * berbunyi "Perlu ditambah" dan diberi garis aksen; saat cukup ia berbunyi
 * "Sisa stok". Satu kartu, bukan dua: keduanya adalah selisih yang sama
 * dilihat dari dua sisi, dan mencetak "Kurang: 0" di sebelah "Sisa: 25"
 * hanya menambah angka yang harus dibaca tanpa menambah yang diketahui.
 *
 * TIDAK ADA KARTU RATA-RATA PEMAKAIAN. "0,3 PCS/hari" benar secara hitungan
 * dan tidak terbaca oleh siapa pun -- tidak ada yang mengambil sepertiga
 * barang. Pemakaian per hari kini dijawab tabel di bawah, dalam bilangan
 * bulat, hari demi hari.
 */
export function ForecastSummary({ data }: { data: Forecast }) {
  const t = useT();
  const satuan = data.item.unit_code ?? "";
  const n = data.forecast_days;
  const r = ringkasPeriode(data);
  const hitungan = t("fc.need.math", {
    a: num(r.butuh),
    b: num(r.stok),
  });

  return (
    <Blok Ikon={TrendingUp} judul={t("fc.need.title")} keterangan={t("fc.need.note", { n })}>
      <div className="grid gap-3 sm:grid-cols-3">
        <KartuKeputusan
          label={t("fc.banner.stock")}
          nilai={angka(r.stok, satuan)}
          detail={
            data.reserved_stock_int > 0
              ? t("fc.need.stock_reserved", {
                  a: angka(data.current_stock_int, satuan),
                  b: angka(data.reserved_stock_int, satuan),
                })
              : t("fc.need.stock_detail")
          }
        />
        <KartuKeputusan
          label={t("fc.need.usage", { n })}
          nilai={angka(r.butuh, satuan)}
          detail={t("fc.need.usage_detail")}
          aksen="var(--brand)"
        />
        {r.kurang > 0 ? (
          <KartuKeputusan
            label={t("fc.need.short")}
            nilai={angka(r.kurang, satuan)}
            detail={hitungan}
            aksen="var(--status-critical)"
          />
        ) : (
          <KartuKeputusan
            label={t("fc.need.left_after", { n })}
            nilai={angka(r.sisa, satuan)}
            detail={t("fc.need.left_math", { a: num(r.stok), b: num(r.butuh) })}
          />
        )}
      </div>
    </Blok>
  );
}

/**
 * Di atas berapa hari tabel beralih dari per hari ke per minggu.
 *
 * Empat belas baris masih terbaca sekali pandang; sembilan puluh tidak.
 * Di atas ambang ini baris dikelompokkan per tujuh hari -- tetap bilangan
 * bulat, tetap berjumlah sama dengan kartu kebutuhan.
 */
const MAKS_BARIS_HARIAN = 14;

/**
 * Pemakaian per Hari / Daily usage.
 *
 * MENGGANTIKAN KARTU RATA-RATA. Tiap baris menyebut berapa yang diperkirakan
 * terpakai pada hari itu dan berapa stok yang tersisa sesudahnya, seluruhnya
 * bilangan bulat. Barang yang jarang keluar terbaca apa adanya -- 0, 0, 1,
 * 0 -- alih-alih "0,3 per hari".
 *
 * Baris sejak stok habis ditandai, dan kolom sisanya berganti menyebut
 * kekurangan yang sudah menumpuk: dari situlah angka "perlu ditambah" pada
 * kartu berasal, dan pembaca dapat melihat sendiri hari ke berapa ia mulai.
 */
export function RincianHarian({ data }: { data: Forecast }) {
  const t = useT();
  const satuan = data.item.unit_code ?? "";
  const rencana = data.daily_plan ?? [];
  if (!rencana.length) return null;

  const perMinggu = rencana.length > MAKS_BARIS_HARIAN;
  const baris: { kunci: string; label: string; pakai: number; sisa: number; kurang: number }[] = [];
  if (perMinggu) {
    for (let i = 0; i < rencana.length; i += 7) {
      const potong = rencana.slice(i, i + 7);
      const awal = potong[0];
      const ujung = potong[potong.length - 1];
      baris.push({
        kunci: awal.date,
        label:
          potong.length > 1
            ? `${shortDate(awal.date)} – ${shortDate(ujung.date)}`
            : shortDate(awal.date),
        pakai: potong.reduce((s, b) => s + b.usage_int, 0),
        sisa: ujung.stock_int,
        kurang: ujung.shortage_int,
      });
    }
  } else {
    for (const b of rencana) {
      baris.push({
        kunci: b.date,
        label: shortDate(b.date),
        pakai: b.usage_int,
        sisa: b.stock_int,
        kurang: b.shortage_int,
      });
    }
  }

  return (
    <Blok
      Ikon={CalendarDays}
      judul={t(perMinggu ? "fc.daily.title_week" : "fc.daily.title")}
      keterangan={t(perMinggu ? "fc.daily.note_week" : "fc.daily.note")}
    >
      <Card>
        <Table lekat tinggiMaks="26rem">
          <thead>
            <tr>
              <Th>{t(perMinggu ? "fc.daily.col_week" : "fc.daily.col_date")}</Th>
              <Th align="right">{t("fc.daily.col_usage", { u: satuan })}</Th>
              <Th align="right">{t("fc.daily.col_left", { u: satuan })}</Th>
            </tr>
          </thead>
          <tbody>
            {baris.map((b) => (
              <tr key={b.kunci}>
                <Td>{b.label}</Td>
                <Td align="right" numeric>
                  <span className={b.pakai === 0 ? "text-muted" : "font-semibold text-ink"}>
                    {num(b.pakai)}
                  </span>
                </Td>
                <Td align="right" numeric>
                  {b.kurang > 0 ? (
                    <span className="font-semibold" style={{ color: "var(--status-critical)" }}>
                      {t("fc.daily.short", { q: num(b.kurang) })}
                    </span>
                  ) : b.sisa === 0 ? (
                    <span className="font-semibold" style={{ color: "var(--status-serious)" }}>
                      {t("fc.daily.empty")}
                    </span>
                  ) : (
                    num(b.sisa)
                  )}
                </Td>
              </tr>
            ))}
            <tr>
              <Td>
                <span className="font-semibold text-ink">
                  {t("fc.daily.total", { n: data.forecast_days })}
                </span>
              </Td>
              <Td align="right" numeric>
                <span className="font-semibold text-ink">
                  {num(baris.reduce((s, b) => s + b.pakai, 0))}
                </span>
              </Td>
              <Td align="right">{""}</Td>
            </tr>
          </tbody>
        </Table>
      </Card>
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

