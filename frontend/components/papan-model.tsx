"use client";

import { Section } from "@/components/ui";
import { Forecast } from "@/lib/forecast-types";
import { useT } from "@/lib/i18n";

/**
 * Papan skor perlombaan model.
 *
 * KENAPA DITAMPILKAN. "Terbaik" adalah klaim, dan klaim yang tidak dapat
 * diperiksa tidak layak dipercaya untuk keputusan pengadaan. Pembaca yang
 * melihat "Croston SBA menang" berhak tahu ia menang atas apa dan seberapa
 * jauh -- terutama ketika jaraknya tipis, karena itu justru pertanda deretnya
 * belum cukup panjang untuk memisahkan keduanya.
 *
 * TERTUTUP SECARA BAWAAN. Yang dibutuhkan kebanyakan orang hanyalah angkanya;
 * perlombaan modelnya baru dibuka ketika ada yang meragukan. Memaksanya selalu
 * terbuka membuat halaman keputusan berubah menjadi laporan uji.
 *
 * Hanya terbit pada mode "terbaik". Pada model yang dipilih tangan tidak ada
 * perlombaan yang terjadi, dan papan kosong hanya akan membuat pembaca mencari
 * tabel yang memang tidak ada.
 */
export function PapanModel({ data }: { data: Forecast }) {
  const t = useT();
  const papan = data.model_scoreboard ?? [];
  if (!papan.length) return null;

  const menang = papan[0];

  return (
    <Section
      title={t("fc.board.title", { model: data.model_label })}
      subtitle={t("fc.board.sub", { n: papan.length, lipatan: menang.lipatan })}
    >
      <div className="overflow-x-auto">
        <table className="w-full t-body">
          <thead>
            <tr className="text-left text-muted">
              <th className="py-2 pr-4 font-medium">{t("fc.board.model")}</th>
              <th className="py-2 pr-4 font-medium">{t("fc.board.error")}</th>
              <th className="py-2 font-medium">{t("fc.board.vs_naive")}</th>
            </tr>
          </thead>
          <tbody>
            {papan.map((baris, i) => (
              <tr
                key={baris.model}
                className="border-t"
                style={{ borderColor: "var(--border)" }}
              >
                <td className="py-2 pr-4">
                  <span className={i === 0 ? "font-semibold text-ink" : "text-ink-2"}>
                    {baris.label}
                  </span>
                  {i === 0 ? (
                    <span
                      className="ml-2 rounded px-1.5 py-0.5 t-caption font-semibold"
                      style={{
                        background: "color-mix(in srgb, var(--brand) 16%, transparent)",
                        color: "var(--brand)",
                      }}
                    >
                      {t("fc.board.winner")}
                    </span>
                  ) : null}
                </td>
                <td className="py-2 pr-4 tabular-nums text-ink-2">
                  {baris.mase.toFixed(3)}
                </td>
                {/*
                 * MASE dibaca relatif terhadap 1, bukan sebagai persen. Di
                 * bawah 1 berarti model mengalahkan tebakan "besok sama seperti
                 * hari ini"; di atas 1 berarti kalah oleh tebakan itu -- dan
                 * itu keterangan yang jauh lebih berguna daripada angkanya
                 * sendiri bagi orang yang belum pernah mendengar MASE.
                 */}
                <td className="py-2 text-ink-2">
                  {baris.mase < 1 ? t("fc.board.better") : t("fc.board.worse")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-3 t-small leading-relaxed text-muted">
        {t("fc.board.note")}
      </p>
    </Section>
  );
}
