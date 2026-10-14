"use client";

/**
 * Aset 3D untuk gudang: pemuat GLB, pallet kayu, kardus, dan rangka rak.
 *
 * SUMBER DAN LISENSI (semuanya CC0, tanpa kewajiban atribusi; lihat
 * public/models/KREDIT.md):
 *   - Poly Haven   props/*.glb      kardus, drum, peti, APAR, hand truck, barrier
 *   - Kenney       kenney/*.glb     truk pengantar (Car Kit)
 *   - Quaternius   worker/human.fbx pekerja beranimasi (Animated Human)
 *
 * Berkas GLB sudah dioptimasi (meshopt + tekstur WebP 512 px) -- total di
 * bawah 1 MB untuk seluruh properti. Semua model dinormalisasi ukurannya saat
 * dimuat (skala ke meter dan alas di y=0), jadi tidak bergantung satuan asal.
 *
 * Geometri yang dipakai berulang (pallet, kardus, rangka rak) DIGABUNG satu
 * kali (mergeGeometries) dan dipakai bersama: satu draw call per bagian, bukan
 * satu per papan atau per kotak.
 */

import { ThreeElements } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import { Component, ReactNode, Suspense, useEffect, useMemo } from "react";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

import { UKURAN } from "@/lib/twin";

export const URL_ASET = {
  kardus: "/models/props/cardboard_box_01.glb",
  drum: "/models/props/Barrel_01.glb",
  petiPlastik: "/models/props/plastic_crate_02.glb",
  petiKayu: "/models/props/wooden_crate_01.glb",
  handTruck: "/models/props/hand_truck.glb",
  apar: "/models/props/korean_fire_extinguisher_01.glb",
  barrier: "/models/props/concrete_road_barrier_02.glb",
  truk: "/models/kenney/delivery.glb",
  /** opsional: letakkan berkas ini bila punya forklift berlisensi; dipakai otomatis */
  forklift: "/models/forklift.glb",
} as const;

/** Tangkap galat pemuatan satu aset; tampilkan cadangan, jangan matikan scene. */
class BatasAset extends Component<{ cadangan: ReactNode; children: ReactNode }, { gagal: boolean }> {
  state = { gagal: false };
  static getDerivedStateFromError() { return { gagal: true }; }
  componentDidCatch(e: unknown) { console.warn("[3D] aset gagal dimuat, memakai cadangan:", e); }
  render() { return this.state.gagal ? this.props.cadangan : this.props.children; }
}

export function AsetAman({ cadangan = null, children }: { cadangan?: ReactNode; children: ReactNode }) {
  return (
    <BatasAset cadangan={cadangan}>
      <Suspense fallback={cadangan}>{children}</Suspense>
    </BatasAset>
  );
}

export interface Fit {
  /** salah satu: ukuran akhir terpanjang pada sumbu itu, dalam meter */
  tinggi?: number;
  panjang?: number;
  lebar?: number;
}

/** Skala + pusat sehingga alas di y=0 dan tengah di x=z=0. */
export function matriksNormal(obj: THREE.Object3D, fit: Fit): { m: THREE.Matrix4; ukuran: THREE.Vector3 } {
  const kotak = new THREE.Box3().setFromObject(obj);
  const u = kotak.getSize(new THREE.Vector3());
  const s =
    fit.tinggi ? fit.tinggi / u.y
    : fit.panjang ? fit.panjang / u.z
    : fit.lebar ? fit.lebar / u.x
    : 1;
  const c = kotak.getCenter(new THREE.Vector3());
  const m = new THREE.Matrix4()
    .makeScale(s, s, s)
    .multiply(new THREE.Matrix4().makeTranslation(-c.x, -kotak.min.y, -c.z));
  return { m, ukuran: u.multiplyScalar(s) };
}

/** Salinan model siap taruh; geometri dan material dibagi dengan sumbernya. */
export function ModelGLB({
  url, fit, bayangan = true, ...rest
}: { url: string; fit: Fit; bayangan?: boolean } & Omit<ThreeElements["group"], "ref">) {
  const { scene } = useGLTF(url, false, true);
  const { klon, ukuran } = useMemo(() => {
    const k = scene.clone(true);
    const { m, ukuran } = matriksNormal(k, fit);
    const pembungkus = new THREE.Group();
    pembungkus.add(k);
    k.applyMatrix4(m);
    pembungkus.userData.ukuran = ukuran;
    return { klon: pembungkus, ukuran };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene, fit.tinggi, fit.panjang, fit.lebar]);
  useEffect(() => {
    klon.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) { m.castShadow = bayangan; m.receiveShadow = bayangan; }
    });
  }, [klon, bayangan]);
  void ukuran;
  return <primitive object={klon} {...rest} />;
}

/**
 * Meshopt/KHR_mesh_quantization menyimpan atribut sebagai Int16 ternormalisasi.
 * Itu tidak dapat digabung (mergeGeometries) dengan Float32 dan akan terpotong
 * bila ditransformasi; ubah dulu menjadi Float32 biasa.
 */
export function bersihkan(g: THREE.BufferGeometry): THREE.BufferGeometry {
  const out = new THREE.BufferGeometry();
  for (const nama of ["position", "normal", "uv"] as const) {
    const a = g.getAttribute(nama);
    if (!a) continue;
    const f = new Float32Array(a.count * a.itemSize);
    for (let i = 0; i < a.count; i++) {
      f[i * a.itemSize] = a.getX(i);
      f[i * a.itemSize + 1] = a.getY(i);
      if (a.itemSize > 2) f[i * a.itemSize + 2] = a.getZ(i);
    }
    out.setAttribute(nama, new THREE.BufferAttribute(f, a.itemSize));
  }
  if (g.index) out.setIndex(Array.from(g.index.array as ArrayLike<number>));
  return out;
}

/** Geometri tunggal siap pakai dari GLB (mesh pertama), sudah dinormalisasi. */
export function useGeometriGLB(url: string, fit: Fit): { geometri: THREE.BufferGeometry; bahan: THREE.Material } {
  const { scene } = useGLTF(url, false, true);
  return useMemo(() => {
    const k = scene.clone(true);
    k.updateMatrixWorld(true);
    const { m } = matriksNormal(k, fit);
    let mesh: THREE.Mesh | null = null;
    k.traverse((o) => { if (!mesh && (o as THREE.Mesh).isMesh) mesh = o as THREE.Mesh; });
    if (!mesh) throw new Error(`Tidak ada mesh pada ${url}`);
    const mm = mesh as THREE.Mesh;
    const g = bersihkan(mm.geometry);
    g.applyMatrix4(mm.matrixWorld);
    g.applyMatrix4(m);
    return { geometri: g, bahan: mm.material as THREE.Material };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene, fit.tinggi, fit.panjang, fit.lebar]);
}

/* ------------------------------------------------------------------ */
/* Tekstur kayu prosedural                                              */
/* ------------------------------------------------------------------ */

let _kayu: THREE.CanvasTexture | null = null;
function teksturKayu(): THREE.CanvasTexture {
  if (_kayu) return _kayu;
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const g = c.getContext("2d")!;
  g.fillStyle = "#b98a52"; g.fillRect(0, 0, 256, 256);
  let seed = 7;
  const r = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 90; i++) {
    const y = r() * 256, tebal = 0.6 + r() * 2.2;
    g.fillStyle = `rgba(${90 + r() * 40},${55 + r() * 30},${25 + r() * 20},${0.12 + r() * 0.22})`;
    g.fillRect(0, y, 256, tebal);
  }
  for (let i = 0; i < 6; i++) { // mata kayu
    g.fillStyle = "rgba(70,40,18,0.35)"; g.beginPath();
    g.ellipse(r() * 256, r() * 256, 5 + r() * 5, 2 + r() * 2, 0, 0, Math.PI * 2); g.fill();
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  _kayu = t;
  return t;
}

/** Pallet EUR kayu ~1,0 x 0,8 m: 5 papan atas, 3 balok, 3 papan bawah; satu geometri. */
export function buatGeometriPalet(): THREE.BufferGeometry {
  const L = 1.0, D = 0.8, H = 0.145;
  const bagian: THREE.BufferGeometry[] = [];
  const kotak = (w: number, h: number, d: number, x: number, y: number, z: number) => {
    const g = new THREE.BoxGeometry(w, h, d);
    // UV memanjang searah serat supaya tekstur kayu tidak melar
    g.translate(x, y, z);
    bagian.push(g);
  };
  const tebalPapan = 0.022;
  for (let i = 0; i < 5; i++) kotak(0.1, tebalPapan, D, -L / 2 + 0.07 + i * ((L - 0.14) / 4), H - tebalPapan / 2, 0);
  for (let i = 0; i < 3; i++) kotak(0.095, H - 2 * tebalPapan, 0.1, -L / 2 + 0.05 + i * ((L - 0.1) / 2), H / 2, 0);
  for (const dz of [-D / 2 + 0.07, 0, D / 2 - 0.07]) kotak(L, tebalPapan, 0.1, 0, tebalPapan / 2, dz);
  const gabung = mergeGeometries(bagian, false)!;
  bagian.forEach((b) => b.dispose());
  return gabung;
}

let _palet: { geo: THREE.BufferGeometry; mat: THREE.MeshStandardMaterial } | null = null;
export function paletBersama() {
  if (!_palet) {
    _palet = {
      geo: buatGeometriPalet(),
      mat: new THREE.MeshStandardMaterial({ map: teksturKayu(), roughness: 0.85 }),
    };
  }
  return _palet;
}

/* ------------------------------------------------------------------ */
/* Rangka rak baja bergaya pallet racking                               */
/* ------------------------------------------------------------------ */

export interface GeometriRak {
  tiang: THREE.BufferGeometry; // biru: tiang, penahan dan diagonal
  balok: THREE.BufferGeometry; // oranye: balok beban
  alas: THREE.BufferGeometry; // abu: panel dek
}

/** Dibangun sekali untuk ukuran rak yang sama; dipakai bersama semua rak. */
export function buatGeometriRak(lebar: number, dalam: number): GeometriRak {
  const T = UKURAN.tingkat, H = UKURAN.slotH;
  const tinggi = H * T + 0.1;
  const tiang: THREE.BufferGeometry[] = [], balok: THREE.BufferGeometry[] = [], alas: THREE.BufferGeometry[] = [];
  const kotak = (arr: THREE.BufferGeometry[], w: number, h: number, d: number, x: number, y: number, z: number,
    rx = 0, rz = 0) => {
    const g = new THREE.BoxGeometry(w, h, d);
    if (rx) g.rotateX(rx);
    if (rz) g.rotateZ(rz);
    g.translate(x, y, z);
    arr.push(g);
  };
  const xFrame = [-lebar / 2 + 0.05, 0, lebar / 2 - 0.05];
  for (const x of xFrame) {
    for (const sz of [-1, 1]) {
      const z = sz * (dalam / 2 - 0.05);
      kotak(tiang, 0.1, tinggi, 0.08, x, tinggi / 2, z); // tiang
      kotak(tiang, 0.16, 0.02, 0.14, x, 0.01, z); // pelat dasar
    }
    // penahan horizontal dan diagonal antara tiang depan-belakang
    const jar = dalam - 0.1;
    for (let k = 0; k <= T; k++) kotak(tiang, 0.05, 0.04, jar, x, 0.35 + k * (H * 0.98), 0);
    for (let k = 0; k < T; k++) {
      const y0 = 0.35 + k * (H * 0.98), y1 = y0 + H * 0.98;
      const pj = Math.hypot(jar, y1 - y0);
      kotak(tiang, 0.04, pj, 0.04, x, (y0 + y1) / 2, 0, Math.atan2(jar, y1 - y0) * (k % 2 ? 1 : -1) * -1);
    }
  }
  // balok beban oranye depan-belakang tiap tingkat + dek
  for (let t = 0; t < T; t++) {
    const y = t * H + 0.12;
    for (const sz of [-1, 1]) kotak(balok, lebar - 0.1, 0.13, 0.05, 0, y, sz * (dalam / 2 - 0.1));
    kotak(alas, lebar - 0.12, 0.022, dalam - 0.2, 0, y + 0.075, 0);
  }
  const gab = (a: THREE.BufferGeometry[]) => { const g = mergeGeometries(a, false)!; a.forEach((x) => x.dispose()); return g; };
  return { tiang: gab(tiang), balok: gab(balok), alas: gab(alas) };
}

/**
 * Pallet kayu + dua lapis kardus asli, digabung jadi SATU geometri dengan dua
 * grup material (kayu, kardus). Dipakai untuk pallet di staging, di trailer,
 * dan di garpu forklift.
 */
export function usePaletMuatan(): { geo: THREE.BufferGeometry; mat: THREE.Material[] } {
  const { geometri, bahan } = useGeometriGLB(URL_ASET.kardus, { lebar: 0.44 });
  return useMemo(() => {
    const pal = bersihkan(paletBersama().geo);
    geometri.computeBoundingBox();
    const tinggi = geometri.boundingBox!.max.y;
    const kotak: THREE.BufferGeometry[] = [];
    for (let l = 0; l < 2; l++) {
      for (const dx of [-0.24, 0.24]) for (const dz of [-0.2, 0.2]) {
        const g = geometri.clone();
        g.rotateY((((l * 5 + (dx > 0 ? 3 : 0) + (dz > 0 ? 1 : 0)) % 5) - 2) * 0.02);
        g.translate(dx, 0.145 + l * tinggi, dz);
        kotak.push(g);
      }
    }
    const kardus = mergeGeometries(kotak, false)!;
    kotak.forEach((k) => k.dispose());
    const geo = mergeGeometries([pal, kardus], true)!;
    pal.dispose(); kardus.dispose();
    return { geo, mat: [paletBersama().mat, bahan] };
  }, [geometri, bahan]);
}

/** Satu pallet bermuatan kardus; `ref` pada grup agar pemanggil dapat mengatur `visible`. */
export function PaletBermuatan({ posisi, ref }: { posisi?: [number, number, number]; ref?: React.Ref<THREE.Group> }) {
  const { geo, mat } = usePaletMuatan();
  return (
    <group ref={ref} position={posisi}>
      <mesh geometry={geo} material={mat} castShadow receiveShadow />
    </group>
  );
}
