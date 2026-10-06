"use client";

/**
 * Transfer Antar Gudang / Inter-warehouse transfer.
 *
 * SATU PERTANYAAN: apa yang tidak perlu dibeli hari ini karena barangnya sudah
 * ada di gudang sebelah, dan dari gudang mana persisnya.
 *
 * LETAKNYA SESUDAH PEMESANAN ULANG, dan urutan itu adalah urutan
 * pertanyaannya. Pemesanan Ulang menjawab BERAPA yang kurang; halaman ini
 * menjawab DARI MANA kekurangan itu ditutup, dan hanya menyerahkan sisanya ke
 * pembelian. Membalik urutannya berarti menawarkan sumber untuk kekurangan
 * yang belum pernah dihitung.
 *
 * ANGKA KEKURANGANNYA DIPINJAM, BUKAN DIHITUNG ULANG. Setiap baris memakai
 * `recommended_order_qty` dari mesin pemesanan ulang, lewat jalur yang sama
 * persis dengan /api/forecast dan /api/reorder. Karena itu satu barang
 * mustahil menyebut kekurangan yang berbeda di ketiga layar -- dan uji
 * test_transfer_api.py mengunci invarian itu.
 *
 * DUA TAB, DAN KEDUANYA PERLU. "Rekomendasi" dihitung ulang setiap kali dibuka
 * dari stok yang berlaku saat itu; "Dokumen" adalah apa yang sudah diajukan
 * dan sedang berjalan. Menyatukannya berarti satu daftar yang separuh barisnya
 * berubah sendiri dan separuh lagi tidak, tanpa ada yang menjelaskan mana yang
 * mana.
 *
 * SATU KARTU PER KEBUTUHAN, bukan satu baris tabel. Perintah yang dihasilkan
 * layar ini menggerakkan barang antar pulau, dan arah perpindahannya tidak
 * boleh bersandar pada ingatan pembaca tentang kolom mana yang mengirim dan
 * kolom mana yang menerima -- apalagi pada dua kode gudang yang berselisih
 * satu huruf. Tiap kartu menyebut nama gudang lengkap pada blok berlabel
 * PENGIRIM dan PENERIMA, dengan panah beserta jumlahnya di antara keduanya.
 *
 * TIDAK ADA PEMILIH PERIODE DAN TIDAK ADA PEMILIH MODEL, alasannya sama persis
 * dengan pada halaman Pemesanan Ulang: keduanya tidak menjawab pertanyaan
 * layar ini, dan menyediakannya menyiratkan bahwa menggesernya mengubah jumlah
 * kiriman -- padahal tidak, dan tidak boleh.
 */

import { useCallback, useEffect, useState } from "react";
import { ArrowLeftRight } from "lucide-react";

import {
  DaftarKartuDokumen,
  DaftarKartuTransfer,
  PeringatanTerpotong,
  PetaDokumen,
  RingkasanTransfer,
  SaringanTransfer,
  TabKeputusan,
  TabTransfer,
  usePilihTransfer,
} from "@/components/transfer-sections";
import { usePilihanModel, usePilihanPeriode } from "@/components/forecast-ui";
import { ErrorBox, PageHeader, PageSkeleton, Pager } from "@/components/ui";
import { useApi } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { GudangApi } from "@/lib/peta";
import { DaftarDokumenTransfer, DaftarTransfer } from "@/lib/transfer-types";

const PER_HALAMAN = 25;

/*
 * Satu larik kosong yang dipakai bersama, bukan `[]` sebaris.
 *
 * `?? []` melahirkan larik BARU pada setiap render, dan peta rute menggambar
 * ulang seluruh penandanya setiap kali daftar gudangnya berganti identitas --
 * bukan isinya. Selagi daftar gudang masih dalam perjalanan, itu berarti
 * peta yang menghapus dan memasang kembali isinya berkali-kali per detik.
 */
const TANPA_GUDANG: GudangApi[] = [];
const TANPA_DOKUMEN: DaftarDokumenTransfer["items"] = [];
const TANPA_USULAN: DaftarTransfer["items"] = [];

type Layar = "rekomendasi" | "dokumen";

export default function TransferPage() {
  const t = useT();

  const [layar, setLayar] = useState<Layar>("rekomendasi");
  const [warehouseId, setWarehouseId] = useState("");
  const [tab, setTab] = useState<TabKeputusan>("");
  const [cari, setCari] = useState("");
  const [fuzzy, setFuzzy] = useState(false);
  const [page, setPage] = useState(1);
  // Dibagi dengan Prakiraan dan Pemesanan Ulang; lihat usePilihanPeriode.
  const [hari, setHari] = usePilihanPeriode();
  const [model, setModel] = usePilihanModel();

  /*
   * Pencarian DITUNDA sebelum dikirim. Tiap permintaan menjalankan rantai
   * prakiraan untuk setiap pasangan barang/gudang, jadi satu permintaan per
   * ketukan tombol menjalankan rantai itu berkali-kali untuk kata yang bahkan
   * belum selesai diketik.
   */
  const [cariKirim, setCariKirim] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setCariKirim(cari.trim()), 350);
    return () => clearTimeout(id);
  }, [cari]);

  // Mengganti saringan mengembalikan ke halaman pertama. Tanpa ini, menyaring
  // dari 40 baris menjadi 3 sementara pembaca berada di halaman 2 menghasilkan
  // layar kosong yang terbaca seolah tidak ada hasilnya.
  useEffect(() => {
    setPage(1);
  }, [warehouseId, tab, cariKirim, fuzzy, layar, hari, model]);

  const gudang = useApi<{ items: GudangApi[] }>("/api/warehouses", { page_size: 200 });
  const daftarGudang = gudang.data?.items ?? TANPA_GUDANG;

  const rekomendasi = useApi<DaftarTransfer>(
    layar === "rekomendasi" ? "/api/transfer" : null,
    {
      warehouse_id: warehouseId || undefined,
      decision: tab || undefined,
      q: cariKirim || undefined,
      fuzzy: fuzzy ? "true" : undefined,
      days: hari,
      model,
      page,
      page_size: PER_HALAMAN,
    },
  );

  /*
   * DOKUMEN SELALU DIAMBIL, bukan hanya saat layarnya terbuka.
   *
   * Petanya berdiri di atas pemilih layar dan menggambar dokumen yang sedang
   * berjalan, jadi ia perlu datanya sejak halaman dibuka -- termasuk saat
   * pembacanya masih berada di layar Rekomendasi. Permintaannya murah: satu
   * SELECT dengan dua JOIN, tanpa satu pun rantai prakiraan, tidak seperti
   * /api/transfer di atasnya.
   */
  const dokumen = useApi<DaftarDokumenTransfer>("/api/transfers", {
    warehouse_id: warehouseId || undefined,
    page,
    page_size: PER_HALAMAN,
  });

  const daftarDokumen = dokumen.data?.items ?? TANPA_DOKUMEN;
  const sorot = usePilihTransfer(daftarDokumen);

  /*
   * Memilih rute di peta membuka layar yang memuat kartunya.
   *
   * Tanpa ini, menunjuk sebuah rute selagi berada di layar Rekomendasi
   * menyorot kartu yang tidak dirender di mana pun: panel peta terbuka,
   * tetapi "detail transfer dapat dibuka pada UI" berhenti di situ.
   */
  const pilihDariPeta = useCallback(
    (id: number | null) => {
      sorot.dariPeta(id);
      if (id !== null) setLayar("dokumen");
    },
    [sorot],
  );

  const aktif = layar === "rekomendasi" ? rekomendasi : dokumen;
  if (aktif.error) return <ErrorBox message={aktif.error} />;

  return (
    <>
      <PageHeader
        icon={<ArrowLeftRight size={20} />}
        eyebrow={t("nav.ai")}
        title={t("tf.title")}
        description={t("tf.desc")}
      >
        <SaringanTransfer
          gudang={daftarGudang}
          warehouseId={warehouseId}
          setWarehouseId={setWarehouseId}
          cari={cari}
          setCari={setCari}
          fuzzy={fuzzy}
          setFuzzy={setFuzzy}
          periode={hari}
          setPeriode={setHari}
          model={model}
          setModel={setModel}
        />
      </PageHeader>

      {/*
        PETA LEBIH DULU, DAN SELALU.
        Sampai 4 September 2026 ia tinggal di dalam layar Dokumen, sementara
        halaman ini membuka pada layar Rekomendasi -- sehingga membuka
        /transfer menampilkan nol peta, dan satu-satunya cara melihatnya adalah
        menekan tab yang tidak menjanjikan peta apa pun. Sebuah gambar yang
        harus dicari lebih dulu tidak menjawab pertanyaan yang seharusnya
        dijawabnya sekali lihat.

        Sekarang ia berdiri tepat di bawah penyaring, di atas kedua layar, dan
        menggambar dokumen yang benar-benar berjalan pada kedua-duanya. Pada
        layar Rekomendasi ia menjawab "apa yang sudah bergerak" selagi kartu di
        bawahnya menjawab "apa yang sebaiknya digerakkan".
      */}
      <div className="mb-4">
        <PetaDokumen
          items={daftarDokumen}
          gudang={daftarGudang}
          /*
            Usulan mesin datang dari permintaan yang SAMA dengan kartu
            Rekomendasi -- tidak ada permintaan kedua, dan tidak ada angka
            kedua.
            
            HANYA DIGAMBAR PADA LAYAR REKOMENDASI, dan pembatasan itu menutup
            satu cara diam-diam menampilkan saran yang salah. /api/transfer
            berhenti ditarik ulang begitu pembaca pindah ke layar Dokumen --
            permintaannya menjalankan rantai prakiraan untuk setiap pasangan
            barang/gudang, dan menjalankannya ulang setiap kali orang membalik
            halaman dokumen adalah ongkos yang tidak dibayar siapa pun. Tetapi
            penyaring gudang berlaku untuk KEDUA layar: mengubahnya dari layar
            Dokumen akan menyisakan busur usulan milik gudang yang sudah tidak
            disaring lagi, tergambar penuh keyakinan di atas peta, tanpa satu
            pun galat yang terbit. Lebih baik lapisannya absen di sana daripada
            hadir dengan jawaban untuk pertanyaan yang sudah berganti.
          */
          usulan={layar === "rekomendasi" ? (rekomendasi.data?.items ?? TANPA_USULAN) : TANPA_USULAN}
          memuat={gudang.loading || (dokumen.loading && !dokumen.data)}
          galat={gudang.error ?? (layar === "rekomendasi" ? dokumen.error : null)}
          pilih={sorot.pilih}
          onPilih={pilihDariPeta}
        />
      </div>

      {/* Pemilih layar. Dua kata, bukan dua halaman: yang mengajukan transfer
          dan yang menyetujuinya sering orang yang sama, dan memisahkannya ke
          dua alamat menuntutnya mengingat jalan pulang. */}
      <div
        role="tablist"
        className="mb-4 inline-flex gap-1 rounded-xl p-1"
        style={{ background: "var(--surface-sunken)" }}
      >
        {(["rekomendasi", "dokumen"] as Layar[]).map((l) => {
          const on = l === layar;
          return (
            <button
              key={l}
              role="tab"
              aria-selected={on}
              onClick={() => setLayar(l)}
              className="rounded-lg px-3.5 py-1.5 t-small font-semibold transition"
              style={{
                background: on ? "var(--surface-1)" : "transparent",
                color: on ? "var(--text-primary)" : "var(--text-secondary)",
                boxShadow: on ? "var(--elev-1)" : "none",
              }}
            >
              {t(`tf.screen.${l}`)}
            </button>
          );
        })}
      </div>

      {aktif.loading && !aktif.data ? (
        <PageSkeleton tiles={layar === "rekomendasi" ? 4 : 0} rows={4} cols={3} />
      ) : layar === "rekomendasi" ? (
        !rekomendasi.data ? null : (
          <div>
            <RingkasanTransfer ringkas={rekomendasi.data.summary} />

            {rekomendasi.data.truncated && (
              <PeringatanTerpotong batas={rekomendasi.data.row_limit} />
            )}

            <div className="mt-5">
              <TabTransfer aktif={tab} setAktif={setTab} ringkas={rekomendasi.data.summary} />
            </div>

            <div className="mt-3">
              <DaftarKartuTransfer
                items={rekomendasi.data.items}
                tab={tab}
                onSegar={rekomendasi.reload}
              />
            </div>

            {rekomendasi.data.pages > 1 && (
              <Pager
                page={rekomendasi.data.page}
                pages={rekomendasi.data.pages}
                total={rekomendasi.data.total}
                onPage={setPage}
              />
            )}
          </div>
        )
      ) : !dokumen.data ? null : (
        <div>
          <DaftarKartuDokumen
            items={dokumen.data.items}
            onSegar={dokumen.reload}
            pilih={sorot.pilih}
            onPilih={sorot.dariDaftar}
          />
          {dokumen.data.pages > 1 && (
            <Pager
              page={dokumen.data.page}
              pages={dokumen.data.pages}
              total={dokumen.data.total}
              onPage={setPage}
            />
          )}
        </div>
      )}
    </>
  );
}
