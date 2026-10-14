"use client";

/**
 * Rute picking di dalam scene: garis rute, penanda urutan pada slot, dan titik
 * yang berjalan menyusuri rute. Murni tampilan atas hasil lib/picking.ts.
 */

import { Html, Line } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

import { HasilRute } from "@/lib/picking";
import { Titik, panjangJalur, posisiPadaJalur } from "@/lib/twin";

const Y = 0.07;
const V_TITIK = 2.4; // m/dtk; hanya untuk animasi penunjuk arah

function Penunjuk({ jalur, jalan }: { jalur: Titik[]; jalan: boolean }) {
  const ref = useRef<THREE.Mesh>(null);
  const jam = useRef(0);
  const { kumulatif, total } = useMemo(() => panjangJalur(jalur, false), [jalur]);
  useFrame((_, dt) => {
    if (!ref.current || total <= 0) return;
    if (jalan) jam.current += Math.min(dt, 0.1);
    const p = posisiPadaJalur(jalur, kumulatif, total, (jam.current * V_TITIK) % total, false);
    ref.current.position.set(p.x, 0.35, p.z);
  });
  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.2, 16, 12]} />
      <meshStandardMaterial color="#2563eb" emissive="#2563eb" emissiveIntensity={1.2} />
    </mesh>
  );
}

function Lencana({ posisi, teks, warna }: { posisi: [number, number, number]; teks: string; warna: string }) {
  return (
    <Html position={posisi} center distanceFactor={12} zIndexRange={[20, 0]} style={{ pointerEvents: "none" }}>
      <div style={{
        minWidth: 22, height: 22, borderRadius: 11, padding: "0 6px", display: "flex", alignItems: "center",
        justifyContent: "center", background: warna, color: "#fff", fontSize: 12, fontWeight: 700,
        boxShadow: "0 0 0 2px #fff, 0 2px 6px rgba(0,0,0,.35)",
      }}>{teks}</div>
    </Html>
  );
}

export default function RuteView({
  hasil, tampilPembanding, jalan,
}: { hasil: HasilRute; tampilPembanding: boolean; jalan: boolean }) {
  const garis = useMemo(() => hasil.jalur.map(([x, z]) => [x, Y, z] as [number, number, number]), [hasil]);
  // Semua rute berjalan di garis lorong yang SAMA, jadi rute pembanding (yang hanya bolak-balik
  // di lorong itu) tertutup total oleh garis utama. Digeser 0,4 m ke samping agar terlihat sejajar;
  // lorong selebar 2,6 m sehingga geseran ini tetap berada di dalamnya.
  const garisBanding = useMemo(
    () => hasil.pembanding.jalur.map(([x, z]) => [x + 0.4, Y - 0.01, z + 0.4] as [number, number, number]), [hasil]);
  return (
    <group>
      {tampilPembanding && (
        <Line points={garisBanding} color="#64748b" lineWidth={3} dashed dashSize={0.6} gapSize={0.35} />
      )}
      <Line points={garis} color="#2563eb" lineWidth={5} />
      {hasil.urutan.map((l) => (
        <Lencana key={l.itemId} posisi={[l.slot[0], l.slot[1] + 0.5, l.slot[2]]} teks={String(l.urut)} warna="#2563eb" />
      ))}
      <Lencana posisi={[hasil.awal[0], 1.0, hasil.awal[1]]} teks="A" warna="#16a34a" />
      {(Math.abs(hasil.awal[0] - hasil.akhir[0]) > 1e-6 || Math.abs(hasil.awal[1] - hasil.akhir[1]) > 1e-6) && (
        <Lencana posisi={[hasil.akhir[0], 1.0, hasil.akhir[1]]} teks="B" warna="#dc2626" />
      )}
      <Penunjuk jalur={hasil.jalur} jalan={jalan} />
    </group>
  );
}
