"use client";

/**
 * Kerangka satu halaman master data: daftar, tambah, ubah, nonaktifkan, hapus.
 *
 * SATU KOMPONEN, LIMA HALAMAN. Kategori, satuan, gudang, supplier, dan barang
 * berbeda hanya pada ruas isiannya; alur kerjanya sama persis. Menuliskannya
 * lima kali berarti lima salinan dari penanganan galat, keadaan sibuk,
 * penyegaran daftar, dan konfirmasi hapus -- dan lima tempat yang harus ikut
 * disunting setiap kali salah satunya diperbaiki. Ruasnya dilewatkan sebagai
 * data; halamannya sendiri tinggal beberapa baris.
 *
 * SATU FORMULIR UNTUK TAMBAH DAN UBAH. Menekan "Ubah" mengisi formulir yang
 * sama, bukan membuka jendela terpisah. Alasannya bukan hemat kode: formulir
 * ubah yang berbeda dari formulir tambah adalah tempat aturan pengisian mulai
 * menyimpang diam-diam di antara keduanya.
 *
 * MENGHAPUS vs MENONAKTIFKAN. Backend hanya mengizinkan menghapus data yang
 * belum dirujuk apa pun, dan menjawab 409 beserta alasannya bila sudah. Layar
 * ini tidak menebak-nebak lebih dulu -- ia menampilkan kedua tombol dan
 * membiarkan jawaban backend yang menjelaskan, karena hanya backend yang tahu
 * berapa transaksi yang sudah menyebut baris itu.
 */

import { ReactNode, useEffect, useState } from "react";
import { Check, Pencil, Plus, Trash2, X } from "lucide-react";

import {
  Badge,
  Button,
  Card,
  DialogKonfirmasi,
  Empty,
  ErrorBox,
  Field,
  PageHeader,
  Pager,
  Select,
  SkeletonRows,
  Table,
  Td,
  TextInput,
  Th,
} from "@/components/ui";
import { GalatApi, apiDelete, apiPatch, apiPost, useApi } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { num } from "@/lib/format";

export interface RuasMaster {
  key: string;
  /** kunci kamus, bukan teks jadi */
  label: string;
  jenis?: "teks" | "angka" | "panjang" | "pilihan" | "opsi";
  wajib?: boolean;
  /** contoh isian; tampil sebagai placeholder DAN sebagai keterangan di bawah kolom */
  petunjuk?: string;
  /**
   * Kunci kamus untuk keterangan di bawah kolom, menggantikan `petunjuk`.
   *
   * Dipakai ketika contoh isian dan keterangannya adalah dua hal yang berbeda:
   * "-7.2575" menjelaskan BENTUKNYA dan tidak menjelaskan sama sekali apa
   * akibatnya bila dikosongkan, dan justru akibat itulah yang menentukan
   * apakah orang mengisinya.
   */
  keterangan?: string;
  /** ikut ditampilkan sebagai kolom tabel */
  diTabel?: boolean;
  rata?: "kiri" | "kanan";
  /** khusus "opsi": nilai tetap beserta kunci kamus labelnya */
  opsi?: { value: string; label: string }[];
  /** khusus "pilihan": alamat daftar pilihannya */
  sumber?: string;
  nilaiDari?: string;
  labelDari?: string;
  /** kolom pada baris daftar yang memuat label terbaca, mis. category_name */
  labelKolom?: string;
}

interface Props {
  judul: string;
  deskripsi: string;
  ikon: ReactNode;
  /** mis. "/api/categories" */
  jalur: string;
  ruas: RuasMaster[];
  /** kolom yang memuat nama baris, dipakai pada konfirmasi hapus */
  namaKolom?: string;
  /** kolom hitungan pemakaian yang ikut ditampilkan, mis. item_count */
  kolomPemakaian?: { key: string; label: string };
}

type Isian = Record<string, string>;

function kosong(ruas: RuasMaster[]): Isian {
  return Object.fromEntries(ruas.map((r) => [r.key, ""]));
}

/** Daftar pilihan satu ruas bertipe "pilihan". */
function usePilihan(r: RuasMaster) {
  const { data } = useApi<{ items: Record<string, unknown>[] }>(
    r.jenis === "pilihan" && r.sumber ? r.sumber : null,
    { page_size: 200, only_active: true },
  );
  return (data?.items ?? []).map((o) => ({
    value: String(o[r.nilaiDari ?? "id"]),
    label: String(o[r.labelDari ?? "name"]),
  }));
}

function IsianRuas({
  r,
  nilai,
  ubah,
  galat,
}: {
  r: RuasMaster;
  nilai: string;
  ubah: (v: string) => void;
  /** kalimat penolakan backend untuk ruas ini, bila ruas inilah yang ditolak */
  galat?: string | null;
}) {
  const { t } = useI18n();
  const pilihan = usePilihan(r);

  if (r.jenis === "opsi") {
    return (
      <Field label={t(r.label)} galat={galat}>
        <Select
          value={nilai}
          onChange={ubah}
          options={[
            { value: "", label: "—" },
            ...(r.opsi ?? []).map((o) => ({ value: o.value, label: t(o.label) })),
          ]}
          className="w-full"
        />
      </Field>
    );
  }
  if (r.jenis === "pilihan") {
    return (
      <Field label={t(r.label)} galat={galat}>
        <Select
          value={nilai}
          onChange={ubah}
          options={[{ value: "", label: "—" }, ...pilihan]}
          className="w-full"
        />
      </Field>
    );
  }
  return (
    <Field
      label={t(r.label)}
      galat={galat}
      petunjuk={r.keterangan ? t(r.keterangan) : r.petunjuk}
    >
      <TextInput value={nilai} onChange={ubah} placeholder={r.petunjuk} className="w-full" />
    </Field>
  );
}

export default function MasterCrud({
  judul,
  deskripsi,
  ikon,
  jalur,
  ruas,
  namaKolom = "name",
  kolomPemakaian,
}: Props) {
  const { t } = useI18n();

  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [isian, setIsian] = useState<Isian>(() => kosong(ruas));
  const [sedangUbah, setSedangUbah] = useState<number | null>(null);
  const [sibuk, setSibuk] = useState(false);
  const [pesan, setPesan] = useState<{ ok: boolean; teks: string } | null>(null);
  /** ruas -> kalimat penolakan; dikosongkan setiap kali penyimpanan dimulai */
  const [galatRuas, setGalatRuas] = useState<Record<string, string>>({});
  /** baris yang sedang ditanyakan penghapusannya; null berarti dialog tertutup */
  const [kandidatHapus, setKandidatHapus] = useState<Record<string, any> | null>(null);
  const [menghapus, setMenghapus] = useState(false);

  const daftar = useApi<{ items: Record<string, any>[]; total: number; pages: number }>(
    jalur,
    { q: q || undefined, page, page_size: 20 },
  );

  // Pencarian selalu mengembalikan ke halaman pertama: hasil pencarian yang
  // dibuka pada halaman 7 hampir selalu kosong, dan tampak seperti tidak ada
  // hasil sama sekali.
  useEffect(() => setPage(1), [q]);

  const kolomTabel = ruas.filter((r) => r.diTabel !== false);

  function batal() {
    setIsian(kosong(ruas));
    setSedangUbah(null);
    setPesan(null);
  }

  function mulaiUbah(baris: Record<string, any>) {
    const isi: Isian = {};
    for (const r of ruas) {
      const v = baris[r.key];
      isi[r.key] = v === null || v === undefined ? "" : String(v);
    }
    setIsian(isi);
    setSedangUbah(baris.id);
    setPesan(null);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /** Isian layar menjadi muatan JSON: teks kosong berarti "tidak diisi". */
  function muatan(): Record<string, unknown> {
    const keluar: Record<string, unknown> = {};
    for (const r of ruas) {
      const v = (isian[r.key] ?? "").trim();
      if (v === "") {
        // Pada penambahan, ruas kosong memang tidak dikirim. Pada perubahan,
        // TIDAK mengirimnya berarti nilai lamanya dibiarkan -- itulah yang
        // diinginkan, dan itu pula yang dilakukan backend.
        continue;
      }
      keluar[r.key] = r.jenis === "angka" || r.jenis === "pilihan" ? Number(v) : v;
    }
    return keluar;
  }

  async function simpan() {
    if (sibuk) return;
    setSibuk(true);
    setGalatRuas({});
    setPesan(null);
    try {
      if (sedangUbah === null) {
        await apiPost(jalur, muatan());
        setPesan({ ok: true, teks: t("md.created") });
      } else {
        await apiPatch(`${jalur}/${sedangUbah}`, muatan());
        setPesan({ ok: true, teks: t("md.updated") });
      }
      setIsian(kosong(ruas));
      setSedangUbah(null);
      daftar.reload();
    } catch (e) {
      /*
       * Penolakan yang menyebut RUAS tidak lagi menjadi spanduk di kepala
       * formulir: ia dipasang di bawah kolom yang bersangkutan. Spanduk hanya
       * untuk kegagalan yang tidak menunjuk satu kolom pun -- jaringan putus,
       * sesi berakhir, galat server.
       */
      if (e instanceof GalatApi && e.field) {
        setGalatRuas({ [e.field]: e.message });
        setPesan(null);
      } else {
        setPesan({ ok: false, teks: e instanceof Error ? e.message : String(e) });
      }
    } finally {
      setSibuk(false);
    }
  }

  async function ubahAktif(baris: Record<string, any>) {
    setPesan(null);
    try {
      await apiPatch(`${jalur}/${baris.id}`, { is_active: !baris.is_active });
      daftar.reload();
    } catch (e) {
      setPesan({ ok: false, teks: e instanceof Error ? e.message : String(e) });
    }
  }

  async function hapus(baris: Record<string, any>) {
    setPesan(null);
    setMenghapus(true);
    try {
      await apiDelete(`${jalur}/${baris.id}`);
      setPesan({ ok: true, teks: t("md.deleted") });
      if (sedangUbah === baris.id) batal();
      daftar.reload();
    } catch (e) {
      // Termasuk 409 "sudah dipakai" -- kalimatnya datang dari backend dan
      // sudah menyebut berapa data yang merujuknya.
      setPesan({ ok: false, teks: e instanceof Error ? e.message : String(e) });
    } finally {
      setMenghapus(false);
      setKandidatHapus(null);
    }
  }

  return (
    <>
      <PageHeader
        icon={ikon}
        eyebrow={t("nav.master")}
        title={t(judul)}
        description={t(deskripsi)}
      />

      {pesan && (
        <div className="mb-4">
          {pesan.ok ? (
            <div
              className="flex items-center gap-2 rounded-xl border px-3.5 py-2.5 t-small"
              style={{
                borderColor: "color-mix(in srgb, var(--status-good) 40%, var(--border))",
                background: "color-mix(in srgb, var(--status-good) 8%, var(--surface-1))",
              }}
            >
              <Check size={14} aria-hidden />
              {pesan.teks}
            </div>
          ) : (
            <ErrorBox message={pesan.teks} />
          )}
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
        <Card
          icon={ikon}
          title={t("md.list")}
          meta={daftar.data ? `${num(daftar.data.total)}` : undefined}
          right={
            <div className="w-full sm:w-44">
              <TextInput
                value={q}
                onChange={setQ}
                placeholder={t("md.search")}
                className="w-full"
              />
            </div>
          }
        >
          {daftar.loading ? (
            <SkeletonRows rows={6} cols={kolomTabel.length + 2} />
          ) : daftar.error ? (
            <ErrorBox message={daftar.error} />
          ) : !daftar.data?.items.length ? (
            <Empty message={t("md.empty")} />
          ) : (
            <>
              <Table kartuPonsel>
                <thead>
                  <tr>
                    {kolomTabel.map((r) => (
                      <Th key={r.key} align={r.rata === "kanan" ? "right" : "left"}>
                        {t(r.label)}
                      </Th>
                    ))}
                    {kolomPemakaian && <Th align="right">{t(kolomPemakaian.label)}</Th>}
                    <Th align="right">{t("md.actions")}</Th>
                  </tr>
                </thead>
                <tbody>
                  {daftar.data.items.map((baris) => (
                    <tr key={baris.id}>
                      {kolomTabel.map((r) => {
                        const tampil =
                          r.labelKolom && baris[r.labelKolom] != null
                            ? baris[r.labelKolom]
                            : baris[r.key];
                        return (
                          <Td key={r.key} align={r.rata === "kanan" ? "right" : "left"}>
                            {tampil === null || tampil === undefined || tampil === ""
                              ? "—"
                              : r.jenis === "angka"
                                ? num(tampil, 0)
                                : r.jenis === "opsi"
                                  ? t(r.opsi?.find((o) => o.value === tampil)?.label ?? String(tampil))
                                  : String(tampil)}
                          </Td>
                        );
                      })}
                      {kolomPemakaian && (
                        <Td align="right">{num(baris[kolomPemakaian.key] ?? 0)}</Td>
                      )}
                      <Td align="right">
                        <div className="flex items-center justify-end gap-1.5">
                          <Badge
                            label={baris.is_active ? t("md.active") : t("md.inactive")}
                            color={
                              baris.is_active ? "var(--status-good)" : "var(--muted)"
                            }
                          />
                          <Button onClick={() => mulaiUbah(baris)} title={t("md.edit")}>
                            <Pencil size={13} aria-hidden />
                          </Button>
                          <Button
                            onClick={() => ubahAktif(baris)}
                            title={baris.is_active ? t("md.deactivate") : t("md.activate")}
                          >
                            {baris.is_active ? <X size={13} /> : <Check size={13} />}
                          </Button>
                          <Button
                            onClick={() => hapus(baris)}
                            title={t("md.delete")}
                            color="var(--status-critical)"
                          >
                            <Trash2 size={13} aria-hidden />
                          </Button>
                        </div>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pager
                page={page}
                pages={daftar.data.pages}
                onPage={setPage}
                total={daftar.data.total}
              />
            </>
          )}
        </Card>

        <Card
          icon={sedangUbah === null ? <Plus size={15} /> : <Pencil size={15} />}
          title={sedangUbah === null ? t("md.add") : t("md.edit_title")}
          subtitle={sedangUbah === null ? t("md.add_sub") : t("md.edit_sub")}
        >
          <div className="flex flex-col gap-3.5">
            {ruas.map((r) => (
              <IsianRuas
                key={r.key}
                r={r}
                nilai={isian[r.key] ?? ""}
                galat={galatRuas[r.key]}
                ubah={(v) => {
                  setIsian((s) => ({ ...s, [r.key]: v }));
                  // Penolakan hilang begitu kolomnya disentuh: membiarkannya
                  // menempel setelah diperbaiki membuat formulir terlihat
                  // masih salah padahal sudah benar.
                  setGalatRuas((g) => (g[r.key] ? { ...g, [r.key]: "" } : g));
                }}
              />
            ))}
            <div className="flex gap-2">
              <Button variant="solid" onClick={simpan} disabled={sibuk}>
                {sibuk ? t("md.saving") : t("md.save")}
              </Button>
              {sedangUbah !== null && (
                <Button onClick={batal}>{t("md.cancel")}</Button>
              )}
            </div>
          </div>
        </Card>
      </div>

      <DialogKonfirmasi
        terbuka={kandidatHapus !== null}
        judul={t("md.delete_title")}
        pesan={t("md.delete_confirm", {
          nama: String(kandidatHapus?.[namaKolom] ?? kandidatHapus?.id ?? ""),
        })}
        labelLanjut={t("md.delete")}
        labelBatal={t("md.cancel")}
        sibuk={menghapus}
        onBatal={() => setKandidatHapus(null)}
        onLanjut={() => kandidatHapus && hapus(kandidatHapus)}
      />
    </>
  );
}
