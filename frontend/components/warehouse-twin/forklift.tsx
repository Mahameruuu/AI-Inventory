"use client";

/**
 * Forklift prosedural yang lebih rinci (counterweight melengkung, tiang angkat
 * profil I, pelindung kepala berjeruji, ban bertapak, silinder hidrolik).
 *
 * TIDAK ADA FORKLIFT CC0 yang layak dipakai (sudah dicari: Kenney, Quaternius,
 * Poly Haven, OpenGameArt). Bagian tubuh digabung per bahan menjadi beberapa
 * geometri statis; hanya garpu (naik-turun) dan lampu rotator yang bergerak.
 * Menggantinya dengan model GLB berlisensi bisa dilakukan dengan mengganti
 * isi BadanForklift tanpa menyentuh pengendali gerak (aktor.tsx, dock.tsx).
 */

import { useEffect, useMemo } from "react";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

import { PaletBermuatan, AsetAman } from "@/components/warehouse-twin/aset";

type G = THREE.BufferGeometry;
const kotak = (w: number, h: number, d: number, x: number, y: number, z: number, rx = 0, rz = 0): G => {
  const g = new THREE.BoxGeometry(w, h, d);
  if (rx) g.rotateX(rx);
  if (rz) g.rotateZ(rz);
  return g.translate(x, y, z);
};
const silinder = (r: number, len: number, x: number, y: number, z: number, sumbu: "x" | "y" | "z", seg = 20): G => {
  const g = new THREE.CylinderGeometry(r, r, len, seg);
  if (sumbu === "x") g.rotateZ(Math.PI / 2);
  if (sumbu === "z") g.rotateX(Math.PI / 2);
  return g.translate(x, y, z);
};
const gabung = (a: G[]): G => {
  // semua harus sama-sama tak berindeks (Extrude tak berindeks, Box/Cylinder berindeks)
  const rata = a.map((x) => {
    const n = x.index ? x.toNonIndexed() : x;
    for (const k of Object.keys(n.attributes)) if (!["position", "normal", "uv"].includes(k)) n.deleteAttribute(k);
    return n;
  });
  const g = mergeGeometries(rata, false);
  if (!g) throw new Error("gabung geometri forklift gagal");
  a.forEach((x) => x.dispose());
  return g;
};

function bangun() {
  /* ---- cat kuning: sasis, counterweight, pelindung kaki ---- */
  const kuning: G[] = [];
  kuning.push(kotak(0.92, 0.3, 1.45, 0, 0.42, 0.05));            // sasis
  kuning.push(kotak(0.98, 0.06, 0.9, 0, 0.62, 0.3));             // lantai kabin
  for (const sx of [-1, 1]) kuning.push(kotak(0.08, 0.14, 0.9, sx * 0.52, 0.5, 0.3)); // pijakan samping
  // counterweight: profil samping melengkung (diekstrusi sepanjang x)
  const profil = new THREE.Shape();
  profil.moveTo(-0.15, 0.3); profil.lineTo(-1.0, 0.3); profil.lineTo(-1.04, 0.7);
  profil.quadraticCurveTo(-1.0, 1.08, -0.78, 1.1); profil.lineTo(-0.35, 1.1);
  profil.quadraticCurveTo(-0.2, 0.9, -0.15, 0.6); profil.closePath();
  const cw = new THREE.ExtrudeGeometry(profil, { depth: 0.94, bevelEnabled: true, bevelSize: 0.03, bevelThickness: 0.03, bevelSegments: 2, curveSegments: 10 });
  cw.rotateY(-Math.PI / 2); cw.translate(0.47, 0, 0);
  // diputar sehingga profil (x=z lokal, y=y) membentang pada sumbu z dan lebar pada x
  kuning.push(cw);
  for (const sx of [-1, 1]) {
    kuning.push(kotak(0.12, 0.42, 0.55, sx * 0.5, 0.78, 0.2)); // dinding kabin depan
    kuning.push(kotak(0.12, 0.08, 0.5, sx * 0.5, 1.0, -0.2)); // sandaran lengan samping
  }

  /* ---- karet/hitam: ban, kursi, kemudi, jeruji pelindung ---- */
  const hitam: G[] = [];
  const ban = (x: number, z: number, r: number, w: number) => {
    hitam.push(silinder(r, w, x, r, z, "x", 28));
    for (let i = 0; i < 12; i++) { // tapak
      const a = (i / 12) * Math.PI * 2;
      hitam.push(kotak(w * 1.02, 0.03, 0.05, x, r + Math.sin(a) * r, z + Math.cos(a) * r).rotateX(0));
    }
  };
  for (const sx of [-1, 1]) { ban(sx * 0.5, 0.42, 0.31, 0.24); ban(sx * 0.46, -0.62, 0.24, 0.2); }
  hitam.push(kotak(0.5, 0.1, 0.45, 0, 0.82, -0.18));           // dudukan kursi
  hitam.push(kotak(0.5, 0.5, 0.1, 0, 1.1, -0.42, -0.15));      // sandaran
  hitam.push(silinder(0.025, 0.6, 0, 0.98, 0.18, "y", 10).rotateX(-0.45)); // kolom kemudi
  const roda = new THREE.TorusGeometry(0.17, 0.02, 8, 20); roda.rotateX(Math.PI / 2 - 0.45); roda.translate(0, 1.2, 0.04);
  hitam.push(roda);
  // pelindung kepala: empat tiang + rangka atap berjeruji
  for (const sx of [-1, 1]) for (const [z, t] of [[-0.45, 0], [0.35, 0.03]] as const) {
    hitam.push(kotak(0.05, 1.25, 0.05, sx * 0.45, 1.32 + t, z));
  }
  for (let i = 0; i < 7; i++) hitam.push(kotak(0.94, 0.03, 0.04, 0, 1.96, -0.45 + i * 0.13));
  for (const sx of [-1, 1]) hitam.push(kotak(0.05, 0.04, 0.88, sx * 0.45, 1.96, -0.05));

  /* ---- logam abu: tiang angkat profil I, silinder hidrolik ---- */
  const logam: G[] = [];
  for (const sx of [-1, 1]) {
    logam.push(kotak(0.1, 2.15, 0.04, sx * 0.27, 1.08, 0.78)); // badan I
    logam.push(kotak(0.1, 2.15, 0.04, sx * 0.27, 1.08, 0.64));
    logam.push(kotak(0.03, 2.15, 0.18, sx * 0.27 + (sx > 0 ? 0.045 : -0.045), 1.08, 0.71)); // web
    logam.push(silinder(0.035, 1.1, sx * 0.14, 0.7, 0.62, "y", 12)); // hidrolik
  }
  logam.push(kotak(0.66, 0.06, 0.2, 0, 2.15, 0.72));             // palang atas
  logam.push(kotak(0.66, 0.06, 0.2, 0, 0.2, 0.72));              // palang bawah
  logam.push(kotak(0.5, 0.2, 0.3, 0, 0.55, 0.58));               // kotak transmisi

  /* ---- bagian bergerak: garpu + sandaran muatan ---- */
  const garpuKuas: G[] = [];
  garpuKuas.push(kotak(0.74, 0.06, 0.05, 0, 0.0, 0.0)); // palang bawah carriage
  garpuKuas.push(kotak(0.74, 0.06, 0.05, 0, 0.5, 0.0)); // palang atas
  for (let i = 0; i < 6; i++) garpuKuas.push(kotak(0.03, 0.55, 0.04, -0.3 + i * 0.12, 0.25, 0.02)); // jeruji sandaran
  for (const sx of [-0.23, 0.23]) {
    garpuKuas.push(kotak(0.1, 0.04, 1.0, sx, -0.1, 0.52));     // bilah garpu
    garpuKuas.push(kotak(0.1, 0.16, 0.05, sx, -0.04, 0.03));   // lutut garpu
    garpuKuas.push(kotak(0.08, 0.03, 0.18, sx, -0.1, 1.07).rotateX(0)); // ujung
  }
  return {
    kuning: gabung(kuning), hitam: gabung(hitam), logam: gabung(logam), garpu: gabung(garpuKuas),
    lampuDepan: kotak(0.12, 0.07, 0.03, 0, 0, 0),
  };
}

let _gudang: ReturnType<typeof bangun> | null = null;
function geo() { return (_gudang ??= bangun()); }

let _bahan: Record<string, THREE.Material> | null = null;
function bahan() {
  return (_bahan ??= {
    kuning: new THREE.MeshStandardMaterial({ color: "#f2b01e", roughness: 0.4, metalness: 0.3 }),
    hitam: new THREE.MeshStandardMaterial({ color: "#1c2027", roughness: 0.85 }),
    logam: new THREE.MeshStandardMaterial({ color: "#8a94a4", roughness: 0.4, metalness: 0.75 }),
    garpu: new THREE.MeshStandardMaterial({ color: "#5d6574", roughness: 0.5, metalness: 0.7 }),
    lampuDepan: new THREE.MeshStandardMaterial({ color: "#fff7d6", emissive: "#fff2b0", emissiveIntensity: 1.1 }),
    lampuRotator: new THREE.MeshStandardMaterial({ color: "#f59e0b", emissive: "#f59e0b", emissiveIntensity: 0.2 }),
  });
}

/**
 * Forklift (menghadap +z lokal). Pengendalinya -- jalur keliling gudang atau
 * forklift dock -- memegang ref dan menggerakkannya per frame.
 */
export function BadanForklift({
  grup, garpu, muatan, lampu,
}: {
  a?: unknown;
  grup: React.RefObject<THREE.Group | null>;
  garpu: React.RefObject<THREE.Group | null>;
  muatan: React.RefObject<THREE.Group | null>;
  lampu: React.RefObject<THREE.Mesh | null>;
}) {
  const g = geo(), b = bahan();
  const lampuGeo = useMemo(() => new THREE.SphereGeometry(0.07, 14, 10), []);
  useEffect(() => () => lampuGeo.dispose(), [lampuGeo]);
  return (
    <group ref={grup}>
      <mesh geometry={g.kuning} material={b.kuning} castShadow receiveShadow />
      <mesh geometry={g.hitam} material={b.hitam} castShadow receiveShadow />
      <mesh geometry={g.logam} material={b.logam} castShadow />
      {/* lampu depan dan belakang */}
      {[-0.32, 0.32].map((x) => (
        <mesh key={x} geometry={g.lampuDepan} material={b.lampuDepan} position={[x, 0.95, 0.5]} />
      ))}
      <mesh ref={lampu} geometry={lampuGeo} material={b.lampuRotator} position={[0, 2.03, -0.1]} />
      {/* garpu + muatan naik-turun pada tiang */}
      <group ref={garpu} position={[0, 0.2, 0.86]}>
        <mesh geometry={g.garpu} material={b.garpu} castShadow />
        <group ref={muatan} position={[0, 0.045, 0.56]} visible={false}>
          <AsetAman>
            <PaletBermuatan />
          </AsetAman>
        </group>
      </group>
    </group>
  );
}
