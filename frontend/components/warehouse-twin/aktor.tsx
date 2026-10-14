"use client";

/**
 * Forklift, pekerja, dan marka lantai untuk scene gudang.
 *
 * INI SIMULASI VISUAL, BUKAN PELACAKAN. Posisi dan gerak pekerja/forklift
 * ditentukan jalur yang diturunkan dari tata letak (lib/twin.ts: jalurGudang)
 * dan tidak mencerminkan orang atau kendaraan sungguhan. Halamannya wajib
 * mengatakan itu.
 *
 * Semua bentuk dibuat prosedural dari satu BoxGeometry/CylinderGeometry
 * bersama; tidak ada berkas model yang diunduh. Material dibuat sekali dan
 * dibuang saat dilepas.
 */

import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { BadanForklift } from "@/components/warehouse-twin/forklift";
import PekerjaFBX from "@/components/warehouse-twin/pekerja";
import { AsetAman } from "@/components/warehouse-twin/aset";
import {
  JalurGudang, TataLetak, UKURAN, jalurGudang, jarakBolakBalik, jarakForklift, panjangJalur, posisiPadaJalur,
} from "@/lib/twin";

const V_FORKLIFT = 1.9; // m/s
const T_HENTI = 2.6; // detik
const V_PEKERJA = 1.15; // m/s
const JEDA_PEKERJA = 2.2;

export function useAlat() {
  const a = useMemo(() => {
    const kotak = new THREE.BoxGeometry(1, 1, 1);
    const silinder = new THREE.CylinderGeometry(1, 1, 1, 14);
    const bola = new THREE.SphereGeometry(1, 14, 10);
    const topi = new THREE.SphereGeometry(1, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2);
    const m = (c: string, o: Partial<THREE.MeshStandardMaterialParameters> = {}) =>
      new THREE.MeshStandardMaterial({ color: c, roughness: 0.7, ...o });
    const bahan = {
      badan: m("#f5b014", { metalness: 0.2 }),
      hitam: m("#1f2530", { roughness: 0.9 }),
      abu: m("#6b7587", { metalness: 0.5, roughness: 0.5 }),
      kayu: m("#b98a52"),
      kardus: m("#c9a26b"),
      rompi: m("#f97316"),
      celana: m("#2b3a55"),
      kulit: m("#e0ac84"),
      helm: m("#facc15"),
      lampu: new THREE.MeshStandardMaterial({ color: "#f59e0b", emissive: "#f59e0b", emissiveIntensity: 0.2 }),
      marka: new THREE.MeshBasicMaterial({ color: "#eab308" }),
      beton: m("#dfe4ec", { roughness: 1 }),
      aspal: m("#3a4250", { roughness: 1 }),
      dinding: m("#c4ccd9", { roughness: 0.9 }),
      pintu: m("#8a96a8", { metalness: 0.4, roughness: 0.5 }),
      kaca: m("#1c2b3a", { metalness: 0.6, roughness: 0.2 }),
      trailerA: m("#e6ebf3"),
      trailerB: m("#f4f5f7"),
      cabA: m("#2563eb", { metalness: 0.2 }),
      cabB: m("#dc2626", { metalness: 0.2 }),
      lampuMerah: new THREE.MeshStandardMaterial({ color: "#ef4444", emissive: "#ef4444", emissiveIntensity: 0.6 }),
      zonaBiru: new THREE.MeshBasicMaterial({ color: "#2563eb", transparent: true, opacity: 0.14, depthWrite: false }),
      zonaHijau: new THREE.MeshBasicMaterial({ color: "#16a34a", transparent: true, opacity: 0.14, depthWrite: false }),
    };
    return { kotak, silinder, bola, topi, bahan };
  }, []);
  useEffect(
    () => () => {
      a.kotak.dispose(); a.silinder.dispose(); a.bola.dispose(); a.topi.dispose();
      Object.values(a.bahan).forEach((x) => x.dispose());
    },
    [a]
  );
  return a;
}
export type Alat = ReturnType<typeof useAlat>;

export function Kotak({ a, m, p, s }: { a: Alat; m: THREE.Material; p: [number, number, number]; s: [number, number, number] }) {
  return <mesh geometry={a.kotak} material={m} position={p} scale={s} />;
}

/** Forklift menghadap +z secara lokal. */
function Forklift({ a, jalur, jalan }: { a: Alat; jalur: JalurGudang; jalan: boolean }) {
  const grup = useRef<THREE.Group>(null);
  const garpu = useRef<THREE.Group>(null);
  const muatan = useRef<THREE.Group>(null);
  const lampu = useRef<THREE.Mesh>(null);
  const arahHalus = useRef<number | null>(null);
  const jam = useRef(0);
  const { kumulatif, total } = useMemo(() => panjangJalur(jalur.forklift, true), [jalur]);
  // jarak tiap titik henti; yang ganjil sendirian dibuang supaya angkat-taruh berpasangan
  const henti = useMemo(() => {
    const semua = jalur.hentiForklift.map((i) => kumulatif[i]);
    return semua.slice(0, semua.length - (semua.length % 2));
  }, [jalur, kumulatif]);

  useFrame((_, dt) => {
    if (!grup.current) return;
    if (jalan) jam.current += Math.min(dt, 0.1);
    const g = jarakForklift(jam.current, total, V_FORKLIFT, henti, T_HENTI);
    const p = posisiPadaJalur(jalur.forklift, kumulatif, total, g.d, true);
    // belok halus: arah mengejar arah ruas, lewat jalur terpendek
    const target = p.arah;
    if (arahHalus.current === null) arahHalus.current = target;
    let selisih = ((target - arahHalus.current + Math.PI) % (2 * Math.PI)) - Math.PI;
    if (selisih < -Math.PI) selisih += 2 * Math.PI;
    arahHalus.current += selisih * Math.min(1, dt * 6);
    grup.current.position.set(p.x, 0, p.z);
    grup.current.rotation.y = arahHalus.current;

    const ganjil = g.indeks >= 0 ? g.indeks % 2 === 1 : g.terakhir % 2 === 0;
    let tinggi = 0;
    let bawa = ganjil && g.indeks < 0; // sesudah angkat, sebelum taruh
    if (g.indeks >= 0) {
      const f = g.fase;
      const naik = f < 0.5 ? f * 2 : (1 - f) * 2; // naik lalu turun
      tinggi = 1.5 * Math.min(1, naik * 1.6);
      // henti genap = ambil (muatan muncul saat garpu naik); ganjil = taruh (hilang saat turun)
      bawa = g.indeks % 2 === 0 ? f > 0.5 : f < 0.5;
    }
    if (garpu.current) garpu.current.position.y = 0.15 + tinggi;
    if (muatan.current) muatan.current.visible = bawa;
    if (lampu.current) {
      (lampu.current.material as THREE.MeshStandardMaterial).emissiveIntensity =
        0.3 + 1.2 * (Math.sin(jam.current * 8) > 0 ? 1 : 0);
    }
  });

  return <BadanForklift grup={grup} garpu={garpu} muatan={muatan} lampu={lampu} />;
}

/** Pekerja berjalan bolak-balik di satu lorong. */
function Pekerja({
  a, rute, mulai, jalan,
}: { a: Alat; rute: JalurGudang["pekerja"][number]; mulai: number; jalan: boolean }) {
  const grup = useRef<THREE.Group>(null);
  const kakiK = useRef<THREE.Group>(null);
  const kakiR = useRef<THREE.Group>(null);
  const tanganK = useRef<THREE.Group>(null);
  const tanganR = useRef<THREE.Group>(null);
  const jam = useRef(mulai);
  const { kumulatif, total } = useMemo(() => panjangJalur(rute, false), [rute]);

  useFrame((_, dt) => {
    if (!grup.current) return;
    if (jalan) jam.current += Math.min(dt, 0.1);
    const g = jarakBolakBalik(jam.current, total, V_PEKERJA, JEDA_PEKERJA);
    const p = posisiPadaJalur(rute, kumulatif, total, g.d, false);
    grup.current.position.set(p.x, 0, p.z);
    // menghadap ke arah jalan; saat diam di ujung, menghadap rak (+z lokal ke -z dunia)
    grup.current.rotation.y = g.diam ? Math.PI : g.maju ? p.arah : p.arah + Math.PI;
    const ayun = g.diam ? 0 : Math.sin(g.d * 5.2) * 0.65;
    if (kakiK.current) kakiK.current.rotation.x = ayun;
    if (kakiR.current) kakiR.current.rotation.x = -ayun;
    if (tanganK.current) tanganK.current.rotation.x = -ayun * 0.8;
    if (tanganR.current) tanganR.current.rotation.x = ayun * 0.8;
    grup.current.position.y = g.diam ? 0 : Math.abs(Math.sin(g.d * 5.2)) * 0.03;
  });

  return (
    <group ref={grup}>
      {/* kaki: pivot di pinggul */}
      <group ref={kakiK} position={[-0.1, 0.82, 0]}>
        <Kotak a={a} m={a.bahan.celana} p={[0, -0.4, 0]} s={[0.15, 0.8, 0.17]} />
      </group>
      <group ref={kakiR} position={[0.1, 0.82, 0]}>
        <Kotak a={a} m={a.bahan.celana} p={[0, -0.4, 0]} s={[0.15, 0.8, 0.17]} />
      </group>
      {/* badan dengan rompi keselamatan */}
      <Kotak a={a} m={a.bahan.rompi} p={[0, 1.13, 0]} s={[0.4, 0.6, 0.24]} />
      <Kotak a={a} m={a.bahan.abu} p={[0, 1.13, 0.125]} s={[0.4, 0.05, 0.01]} />
      {/* lengan */}
      <group ref={tanganK} position={[-0.27, 1.38, 0]}>
        <Kotak a={a} m={a.bahan.rompi} p={[0, -0.28, 0]} s={[0.1, 0.56, 0.12]} />
      </group>
      <group ref={tanganR} position={[0.27, 1.38, 0]}>
        <Kotak a={a} m={a.bahan.rompi} p={[0, -0.28, 0]} s={[0.1, 0.56, 0.12]} />
      </group>
      {/* kepala + helm */}
      <mesh geometry={a.bola} material={a.bahan.kulit} position={[0, 1.58, 0]} scale={0.12} />
      <mesh geometry={a.topi} material={a.bahan.helm} position={[0, 1.6, 0]} scale={0.145} />
    </group>
  );
}

/** Garis kuning di tepi tiap lorong. */
function Marka({ a, tata, jalur }: { a: Alat; tata: TataLetak; jalur: JalurGudang }) {
  const panjang = jalur.koridorKanan - jalur.koridorKiri;
  return (
    <group position={[0, 0.012, 0]}>
      {jalur.lorongZ.flatMap((z) =>
        [-1, 1].map((sisi) => (
          <mesh
            key={`${z}${sisi}`}
            geometry={a.kotak}
            material={a.bahan.marka}
            position={[0, 0, z + sisi * (UKURAN.lorong / 2 - 0.1)]}
            scale={[panjang, 0.004, 0.08]}
          />
        ))
      )}
    </group>
  );
}

export default function AktorGudang({
  tata, jalan,
}: {
  tata: TataLetak;
  /** false = membeku di tempat (jeda animasi) */
  jalan: boolean;
}) {
  const a = useAlat();
  const jalur = useMemo(() => jalurGudang(tata), [tata]);
  return (
    <group>
      <Marka a={a} tata={tata} jalur={jalur} />
      <Forklift a={a} jalur={jalur} jalan={jalan} />
      {/* satu pekerja per lorong, maksimal empat; fase mulai berbeda-beda */}
      {jalur.pekerja.slice(0, 4).map((rute, i) => (
        <AsetAman key={i} cadangan={<Pekerja a={a} rute={rute} mulai={i * 4.3} jalan={jalan} />}>
          <PekerjaFBX rute={rute} mulai={i * 4.3} jalan={jalan} varian={i} />
        </AsetAman>
      ))}
    </group>
  );
}
