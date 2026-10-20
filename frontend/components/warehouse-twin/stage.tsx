"use client";

/**
 * Panggung 3D di dalam Dasbor: kanvas, tombol reset, dan petunjuk.
 *
 * Bukan halaman dan bukan dashboard: hanya satu bagian dari Dasbor. State
 * pilihan rak dipegang Dasbor supaya panel detail dan daftar perhatian dapat
 * membacanya; komponen ini murni tampilan.
 *
 * `memo` + pembungkus Scene: panel yang dilipat atau dibuka di sekitarnya
 * tidak membuat kanvas WebGL menggambar ulang.
 */

import dynamic from "next/dynamic";
import { Component, ReactNode, memo, useEffect, useRef, useState } from "react";
import { Maximize, Minimize, Pause, Play, RotateCcw, Sun } from "lucide-react";

import type { Pilihan } from "@/components/warehouse-twin/scene";
import { Button, ErrorBox, Skeleton } from "@/components/ui";
import { useT } from "@/lib/i18n";
import type { HasilRute } from "@/lib/picking";
import { TataLetak } from "@/lib/twin";

const Scene = dynamic(() => import("@/components/warehouse-twin/scene"), {
  ssr: false,
  loading: () => <Skeleton h="100%" radius={0} />,
});

/** WebGL yang gagal dibuat melempar galat saat render; tangkap, jangan matikan halaman. */
class BatasGalat extends Component<{ pesan: string; children: ReactNode }, { gagal: boolean }> {
  state = { gagal: false };
  static getDerivedStateFromError() { return { gagal: true }; }
  render() { return this.state.gagal ? <ErrorBox message={this.props.pesan} /> : this.props.children; }
}

function PanggungTwin({
  tata, pilihan, onPilih, rute = null, tampilPembanding = false, ditandai,
}: {
  ditandai?: Set<number>;
  tata: TataLetak;
  pilihan: Pilihan | null;
  onPilih: (p: Pilihan | null) => void;
  rute?: HasilRute | null;
  tampilPembanding?: boolean;
}) {
  const t = useT();
  const [resetKe, setResetKe] = useState(0);
  const [animasi, setAnimasi] = useState(true);
  const [bayangan, setBayangan] = useState(true);
  // Layar penuh seperti pemutar video: tombol di pojok kanan bawah, Esc untuk keluar.
  const bingkai = useRef<HTMLDivElement>(null);
  const [penuh, setPenuh] = useState(false);
  useEffect(() => {
    const ubah = () => setPenuh(document.fullscreenElement === bingkai.current);
    document.addEventListener("fullscreenchange", ubah);
    return () => document.removeEventListener("fullscreenchange", ubah);
  }, []);
  const alihPenuh = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void bingkai.current?.requestFullscreen?.();
  };
  return (
    <div
      ref={bingkai}
      className={penuh ? "relative h-screen w-screen overflow-hidden" : "relative h-[420px] overflow-hidden rounded-[inherit] sm:h-[520px] xl:h-[600px]"}
      style={penuh ? { background: "var(--surface-1)" } : undefined}
    >
      <BatasGalat pesan={t("tw.webgl_error")}>
        <Scene tata={tata} pilihan={pilihan} onPilih={onPilih} resetKe={resetKe} animasi={animasi} bayangan={bayangan} rute={rute} tampilPembanding={tampilPembanding} ditandai={ditandai} />
      </BatasGalat>
      <div className="absolute left-3 top-3 flex gap-2">
        <Button variant="solid" onClick={() => { setResetKe((n) => n + 1); onPilih(null); }}>
          <RotateCcw size={14} /> {t("tw.reset")}
        </Button>
        <Button variant="ghost" onClick={() => setAnimasi((v) => !v)} title={t("tw.sim_note")}>
          {animasi ? <Pause size={14} /> : <Play size={14} />} {animasi ? t("tw.anim.pause") : t("tw.anim.play")}
        </Button>
        <Button variant="ghost" onClick={() => setBayangan((v) => !v)} title={t("tw.shadow.hint")}>
          <Sun size={14} /> {bayangan ? t("tw.shadow.on") : t("tw.shadow.off")}
        </Button>
      </div>
      {ditandai && (
        <div className="pointer-events-none absolute right-3 top-3 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-white" style={{ background: "#7c3aed" }}>
          {t("wi.badge", { n: ditandai.size })}
        </div>
      )}
      <button
        type="button"
        onClick={alihPenuh}
        title={penuh ? t("tw.fs.exit") : t("tw.fs.enter")}
        aria-label={penuh ? t("tw.fs.exit") : t("tw.fs.enter")}
        className="absolute bottom-2 right-3 z-10 rounded-md bg-black/55 p-2 text-white hover:bg-black/75"
      >
        {penuh ? <Minimize size={16} /> : <Maximize size={16} />}
      </button>
      <p className="pointer-events-none absolute bottom-2 left-3 right-14 t-small text-muted">
        {t("tw.hint")} · {t("tw.sim_note")}
      </p>
    </div>
  );
}

export default memo(PanggungTwin);
