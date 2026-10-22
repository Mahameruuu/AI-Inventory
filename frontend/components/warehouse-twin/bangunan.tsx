"use client";

/**
 * Bangunan gudang: dinding, atap, rangka baja, lampu high-bay, dan marka jalur
 * pejalan kaki -- supaya rak berdiri DI DALAM gudang, bukan di lapangan.
 *
 * DINDING SATU SISI, MENGHADAP KE DALAM. Bidang dinding dan atap hanya
 * digambar dari sisi dalamnya (FrontSide, normal ke dalam). Dinding yang
 * berada di antara kamera dan isi gudang terlihat dari luar, jadi tidak
 * digambar sama sekali; dinding di seberang dan atap terlihat dari dalam.
 * Hasilnya seperti rumah boneka yang dibuka di sisi pengamat, tanpa logika
 * per frame. Atap dilihat dari atas pun tidak digambar, sehingga isi gudang
 * selalu terlihat dari sudut pandang awal.
 *
 * Semua tekstur dibuat di kanvas (tanpa berkas unduhan) dan geometri berulang
 * digabung sekali (mergeGeometries): rangka atap seluruh gudang = satu draw call.
 */

import { useEffect, useMemo } from "react";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

import { Dock } from "@/lib/twin";

export const GEDUNG = {
  tinggi: 8.5,
  tinggiBeton: 1.2,
  jarakPortal: 6,
  sisaSamping: 1.4,
  sisaBelakang: 2.5,
} as const;

export interface BatasGedung {
  xKiri: number;
  xKanan: number;
  zDepan: number;
  zBelakang: number;
  lebar: number;
  dalam: number;
  pusatZ: number;
}

export function batasGedung(d: Dock): BatasGedung {
  const xKanan = d.lebarLantai / 2 + GEDUNG.sisaSamping;
  const zDepan = d.zDinding;
  const zBelakang = d.zMaks + GEDUNG.sisaBelakang;
  return {
    xKiri: -xKanan, xKanan, zDepan, zBelakang,
    lebar: 2 * xKanan, dalam: zBelakang - zDepan, pusatZ: (zDepan + zBelakang) / 2,
  };
}

/* ------------------------------------------------------------------ */
/* Tekstur kanvas                                                       */
/* ------------------------------------------------------------------ */

const acak = (seed: number) => () => ((seed = (seed * 16807) % 2147483647) / 2147483647);

function kanvas(w: number, h: number, gambar: (g: CanvasRenderingContext2D) => void): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = w; c.height = h;
  gambar(c.getContext("2d")!);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 4;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Panel baja bergelombang (trapesium) abu-putih; satu ubin = 1 m lebar x 1 m tinggi. */
function teksturPanel(): THREE.CanvasTexture {
  return kanvas(256, 256, (g) => {
    g.fillStyle = "#d9dde3"; g.fillRect(0, 0, 256, 256);
    // empat rusuk per meter: sisi kiri terang, kanan gelap, puncak datar
    for (let i = 0; i < 4; i++) {
      const x = i * 64;
      g.fillStyle = "#c3c9d1"; g.fillRect(x + 6, 0, 8, 256);
      g.fillStyle = "#eef1f4"; g.fillRect(x + 14, 0, 14, 256);
      g.fillStyle = "#b4bac4"; g.fillRect(x + 28, 0, 6, 256);
    }
    const r = acak(5);
    for (let i = 0; i < 900; i++) {
      g.fillStyle = `rgba(80,86,96,${r() * 0.05})`;
      g.fillRect(r() * 256, r() * 256, 1, 2 + r() * 6);
    }
  });
}

/** Panel beton pracetak di bagian bawah dinding. */
function teksturBetonDinding(): THREE.CanvasTexture {
  return kanvas(256, 256, (g) => {
    g.fillStyle = "#a7acb3"; g.fillRect(0, 0, 256, 256);
    const r = acak(19);
    for (let i = 0; i < 5000; i++) {
      const v = 120 + r() * 70;
      g.fillStyle = `rgba(${v},${v},${v},${0.06 + r() * 0.1})`;
      g.fillRect(r() * 256, r() * 256, 1 + r() * 2, 1 + r() * 2);
    }
    g.fillStyle = "rgba(60,64,70,0.5)"; g.fillRect(0, 0, 2, 256); // sambungan panel
  });
}

/** Lembaran atap dengan jalur skylight (polikarbonat bening) tiap 6 ubin. */
function teksturAtap(): THREE.CanvasTexture {
  return kanvas(256, 256, (g) => {
    g.fillStyle = "#b9bfc8"; g.fillRect(0, 0, 256, 256);
    for (let i = 0; i < 8; i++) { g.fillStyle = "#a7aeb8"; g.fillRect(i * 32 + 10, 0, 8, 256); }
  });
}

/** Garis zebra kuning-hitam (diagonal) untuk area bahaya. */
function teksturBahaya(): THREE.CanvasTexture {
  return kanvas(128, 128, (g) => {
    g.fillStyle = "#1f2228"; g.fillRect(0, 0, 128, 128);
    g.fillStyle = "#f2b81e";
    for (let i = -128; i < 256; i += 32) {
      g.beginPath(); g.moveTo(i, 0); g.lineTo(i + 16, 0); g.lineTo(i + 16 + 128, 128); g.lineTo(i + 128, 128); g.fill();
    }
  });
}

/** Dek kawat rak: kisi kawat dengan celah transparan (alphaTest). */
export function teksturKawat(): THREE.CanvasTexture {
  const t = kanvas(64, 64, (g) => {
    g.clearRect(0, 0, 64, 64);
    g.fillStyle = "#ffffff";
    g.fillRect(0, 0, 64, 6); g.fillRect(0, 0, 6, 64);
  });
  t.colorSpace = THREE.NoColorSpace;
  return t;
}

let _bahan: null | Record<"panel" | "beton" | "atap" | "baja" | "lampuBadan" | "lampuNyala" | "skylight" | "bahaya" | "hijau" | "putih" | "pelindung", THREE.Material> = null;
export function bahanGedung() {
  if (_bahan) return _bahan;
  _bahan = {
    panel: new THREE.MeshStandardMaterial({ map: teksturPanel(), roughness: 0.55, metalness: 0.35, side: THREE.FrontSide }),
    beton: new THREE.MeshStandardMaterial({ map: teksturBetonDinding(), roughness: 0.95 }),
    atap: new THREE.MeshStandardMaterial({ map: teksturAtap(), roughness: 0.6, metalness: 0.4 }),
    baja: new THREE.MeshStandardMaterial({ color: "#4f5d70", roughness: 0.45, metalness: 0.7 }),
    lampuBadan: new THREE.MeshStandardMaterial({ color: "#3a3f47", roughness: 0.4, metalness: 0.8 }),
    lampuNyala: new THREE.MeshStandardMaterial({ color: "#fff6e0", emissive: "#fff1cf", emissiveIntensity: 2.4 }),
    skylight: new THREE.MeshStandardMaterial({ color: "#eaf3ff", emissive: "#dbeaff", emissiveIntensity: 0.9, transparent: true, opacity: 0.92 }),
    bahaya: new THREE.MeshStandardMaterial({ map: teksturBahaya(), roughness: 0.6 }),
    hijau: new THREE.MeshStandardMaterial({ color: "#2f8f4e", roughness: 0.55 }),
    putih: new THREE.MeshStandardMaterial({ color: "#f3f4f6", roughness: 0.5 }),
    pelindung: new THREE.MeshStandardMaterial({ color: "#f2b81e", roughness: 0.45, metalness: 0.2 }),
  };
  return _bahan;
}

/**
 * Kotak dengan UV dalam METER (1 ubin tekstur = 1 m), supaya panel dan beton
 * tidak melar pada dinding yang panjangnya berbeda-beda.
 */
export function kotakBerUV(w: number, h: number, d: number): THREE.BoxGeometry {
  const g = new THREE.BoxGeometry(w, h, d);
  const uv = g.getAttribute("uv") as THREE.BufferAttribute;
  // urutan muka BoxGeometry: +x, -x, +y, -y, +z, -z (masing-masing 4 titik)
  const skala: [number, number][] = [[d, h], [d, h], [w, d], [w, d], [w, h], [w, h]];
  for (let f = 0; f < 6; f++) for (let i = 0; i < 4; i++) {
    const k = f * 4 + i;
    uv.setXY(k, uv.getX(k) * skala[f][0], uv.getY(k) * skala[f][1]);
  }
  uv.needsUpdate = true;
  return g;
}

/** Bidang satu sisi dengan UV dalam meter. */
function bidang(w: number, h: number): THREE.PlaneGeometry {
  const g = new THREE.PlaneGeometry(w, h);
  const uv = g.getAttribute("uv") as THREE.BufferAttribute;
  for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getX(i) * w, uv.getY(i) * h);
  return g;
}

/* ------------------------------------------------------------------ */
/* Geometri gedung                                                      */
/* ------------------------------------------------------------------ */

type G = THREE.BufferGeometry;
const rata = (a: G[]): G => {
  const r = a.map((x) => {
    const y = x.index ? x.toNonIndexed() : x;
    for (const k of Object.keys(y.attributes)) if (!["position", "normal", "uv"].includes(k)) y.deleteAttribute(k);
    return y;
  });
  const g = mergeGeometries(r, false)!;
  a.forEach((x) => x.dispose());
  return g;
};

/** Profil I (balok/kolom baja) sepanjang sumbu y, berpusat di titik asal. */
function profilI(panjang: number, tinggi: number, lebar: number): G[] {
  const sayap = 0.025, badan = 0.014;
  return [
    new THREE.BoxGeometry(lebar, panjang, sayap).translate(0, 0, tinggi / 2 - sayap / 2),
    new THREE.BoxGeometry(lebar, panjang, sayap).translate(0, 0, -tinggi / 2 + sayap / 2),
    new THREE.BoxGeometry(badan, panjang, tinggi - 2 * sayap),
  ];
}

export function useGeometriGedung(b: BatasGedung) {
  const geo = useMemo(() => {
    const H = GEDUNG.tinggi;
    const portalZ: number[] = [];
    for (let z = b.zDepan + 0.4; z <= b.zBelakang - 0.2; z += GEDUNG.jarakPortal) portalZ.push(z);
    if (b.zBelakang - 0.4 - portalZ[portalZ.length - 1] > 1.5) portalZ.push(b.zBelakang - 0.4);

    const baja: G[] = [];
    for (const z of portalZ) {
      // kolom di kedua dinding samping
      for (const sx of [-1, 1]) {
        for (const p of profilI(H, 0.36, 0.22)) baja.push(p.translate(sx * (b.xKanan - 0.25), H / 2, z));
      }
      // balok atap melintang (profil I diputar ke sumbu x), sedikit di bawah atap
      // sayap atas-bawah mendatar, badan tegak
      const L = b.lebar - 0.5, yb = H - 0.4;
      baja.push(new THREE.BoxGeometry(L, 0.025, 0.2).translate(0, yb + 0.25, z));
      baja.push(new THREE.BoxGeometry(L, 0.025, 0.2).translate(0, yb - 0.25, z));
      baja.push(new THREE.BoxGeometry(L, 0.475, 0.014).translate(0, yb, z));
      // pengaku miring (haunch) di sambungan kolom-balok
      for (const sx of [-1, 1]) {
        const g = new THREE.BoxGeometry(0.12, 1.6, 0.12);
        g.rotateZ(sx * 0.75);
        baja.push(g.translate(sx * (b.xKanan - 0.85), H - 1.0, z));
      }
    }
    // gording memanjang di bawah atap: jarang, supaya dari atas tidak terlihat seperti kandang
    for (let x = b.xKiri + 3; x < b.xKanan - 1; x += 4.5) {
      baja.push(new THREE.BoxGeometry(0.07, 0.14, b.dalam - 0.2).translate(x, H - 0.08, b.pusatZ));
    }

    // lampu high-bay: badan lonceng + piringan menyala, digantung di antara portal
    const badanLampu: G[] = [], nyala: G[] = [];
    const titikLampu: [number, number, number][] = [];
    for (let i = 0; i < portalZ.length - 1; i++) {
      const z = (portalZ[i] + portalZ[i + 1]) / 2;
      for (let x = b.xKiri + 4; x <= b.xKanan - 3.5; x += 5.5) {
        const y = H - 1.6;
        badanLampu.push(new THREE.CylinderGeometry(0.012, 0.012, 1.3, 6).translate(x, y + 0.85, z));
        badanLampu.push(new THREE.CylinderGeometry(0.12, 0.36, 0.32, 20, 1, true).translate(x, y + 0.16, z));
        badanLampu.push(new THREE.CylinderGeometry(0.13, 0.13, 0.12, 14).translate(x, y + 0.36, z));
        nyala.push(new THREE.CircleGeometry(0.34, 20).rotateX(Math.PI / 2).translate(x, y + 0.01, z));
        titikLampu.push([x, y, z]);
      }
    }

    return {
      baja: rata(baja),
      badanLampu: rata(badanLampu),
      nyala: rata(nyala),
      titikLampu,
      portalZ,
    };
  }, [b]);
  useEffect(() => () => { geo.baja.dispose(); geo.badanLampu.dispose(); geo.nyala.dispose(); }, [geo]);
  return geo;
}

/* ------------------------------------------------------------------ */
/* Komponen                                                            */
/* ------------------------------------------------------------------ */

/** Dinding samping dan belakang: beton di bawah, panel baja di atas, jalur skylight dekat atap. */
function Dinding({ b }: { b: BatasGedung }) {
  const m = bahanGedung();
  const H = GEDUNG.tinggi, Hb = GEDUNG.tinggiBeton;
  const sisi = useMemo(() => {
    // [pusat x, pusat z, panjang, rotasiY]; normal bidang menghadap ke dalam
    const daftar: [number, number, number, number][] = [
      [0, b.zBelakang, b.lebar, Math.PI],          // belakang, normal -z
      [b.xKiri, b.pusatZ, b.dalam, Math.PI / 2],    // kiri, normal +x
      [b.xKanan, b.pusatZ, b.dalam, -Math.PI / 2],  // kanan, normal -x
    ];
    return daftar.map(([x, z, L, r]) => ({
      x, z, r,
      beton: bidang(L, Hb),
      panel: bidang(L, H - Hb - 1.0),
      sky: bidang(L, 0.7),
    }));
  }, [b, H, Hb]);
  useEffect(() => () => sisi.forEach((s) => { s.beton.dispose(); s.panel.dispose(); s.sky.dispose(); }), [sisi]);
  return (
    <group>
      {sisi.map((s, i) => (
        <group key={i} position={[s.x, 0, s.z]} rotation={[0, s.r, 0]}>
          <mesh geometry={s.beton} material={m.beton} position={[0, Hb / 2, 0]} receiveShadow />
          <mesh geometry={s.panel} material={m.panel} position={[0, Hb + (H - Hb - 1.0) / 2, 0]} receiveShadow />
          <mesh geometry={s.sky} material={m.skylight} position={[0, H - 0.75, 0]} />
          <mesh geometry={s.panel} material={m.panel} position={[0, H - 0.2, 0]} scale={[1, 0.4 / (H - Hb - 1.0), 1]} />
        </group>
      ))}
    </group>
  );
}

/** Atap: terlihat hanya dari bawah. Jalur skylight memanjang tiap ~6 m. */
function Atap({ b }: { b: BatasGedung }) {
  const m = bahanGedung();
  const H = GEDUNG.tinggi;
  const { atap, jalur } = useMemo(() => {
    const atap = bidang(b.lebar, b.dalam);
    const xs: number[] = [];
    for (let x = b.xKiri + 3.5; x < b.xKanan - 2; x += 6) xs.push(x);
    const jalur = rata(xs.map((x) => new THREE.PlaneGeometry(1.1, b.dalam - 1).translate(x, 0, 0)));
    return { atap, jalur };
  }, [b]);
  useEffect(() => () => { atap.dispose(); jalur.dispose(); }, [atap, jalur]);
  return (
    <group position={[0, H, b.pusatZ]} rotation={[Math.PI / 2, 0, 0]}>
      <mesh geometry={atap} material={m.atap} />
      <mesh geometry={jalur} material={m.skylight} position={[0, 0, 0.01]} />
    </group>
  );
}

/** Jalur pejalan kaki hijau di sepanjang dinding kiri dan penyeberangan zebra di koridor depan. */
function MarkaLantai({ b, zKoridor, xLorongKiri, xLorongKanan }: { b: BatasGedung; zKoridor: number; xLorongKiri: number; xLorongKanan: number }) {
  const m = bahanGedung();
  const x = b.xKiri + 1.0;
  const zebra = useMemo(() => {
    const strip: G[] = [];
    for (let i = 0; i < 6; i++) strip.push(new THREE.BoxGeometry(0.35, 0.004, 1.6).translate(i * 0.7, 0, 0));
    return rata(strip);
  }, []);
  useEffect(() => () => zebra.dispose(), [zebra]);
  return (
    <group position={[0, 0.006, 0]}>
      <mesh position={[x, 0, b.pusatZ + 0.5]} material={m.hijau} receiveShadow>
        <boxGeometry args={[1.1, 0.004, b.dalam - 1.5]} />
      </mesh>
      {[-0.58, 0.58].map((dx) => (
        <mesh key={dx} position={[x + dx, 0.001, b.pusatZ + 0.5]} material={m.putih}>
          <boxGeometry args={[0.07, 0.004, b.dalam - 1.5]} />
        </mesh>
      ))}
      {/* penyeberangan dari jalur hijau melintasi koridor depan */}
      <mesh geometry={zebra} material={m.putih} position={[xLorongKiri + 0.5, 0.001, zKoridor]} />
      <mesh geometry={zebra} material={m.putih} position={[xLorongKanan - 4.0, 0.001, zKoridor]} />
    </group>
  );
}

/** Ambil paling banyak `n` titik yang tersebar merata. */
function pilihLampu(t: [number, number, number][], n: number): [number, number, number][] {
  if (t.length <= n) return t;
  return Array.from({ length: n }, (_, i) => t[Math.round((i * (t.length - 1)) / (n - 1))]);
}

export default function BangunanGudang({
  dock, zKoridor, xLorongKiri, xLorongKanan,
}: { dock: Dock; zKoridor: number; xLorongKiri: number; xLorongKanan: number }) {
  const b = useMemo(() => batasGedung(dock), [dock]);
  const g = useGeometriGedung(b);
  const m = bahanGedung();
  return (
    <group>
      <Dinding b={b} />
      <Atap b={b} />
      <mesh geometry={g.baja} material={m.baja} castShadow={false} receiveShadow />
      <mesh geometry={g.badanLampu} material={m.lampuBadan} />
      <mesh geometry={g.nyala} material={m.lampuNyala} />
      {/* sebagian lampu benar-benar menyinari (tanpa bayangan, supaya ringan) */}
      {pilihLampu(g.titikLampu, 6).map(([x, y, z], i) => (
        <pointLight key={i} position={[x, y - 0.3, z]} color="#ffe9c4" intensity={38} distance={16} decay={1.6} />
      ))}
      <MarkaLantai b={b} zKoridor={zKoridor} xLorongKiri={xLorongKiri} xLorongKanan={xLorongKanan} />
    </group>
  );
}
