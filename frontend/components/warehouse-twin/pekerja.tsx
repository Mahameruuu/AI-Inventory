"use client";

/**
 * Pekerja gudang: model manusia beranimasi (Quaternius "Animated Human", CC0)
 * berseragam kerja (rompi oranye/stabilo, celana dongker) dan helm keselamatan.
 *
 * `useManusia` memuat dan menyiapkan SATU pekerja: model, mixer animasi
 * (Walk, Idle, Working dari berkas modelnya), tulang yang bisa ditekuk untuk
 * pose tambahan, dan cara menempelkan benda ke tangan. Dipakai pekerja yang
 * berjalan di lorong (berkas ini) maupun pekerja yang sedang berkegiatan
 * (kegiatan.tsx). SIMULASI VISUAL, bukan pelacakan.
 */

import { useFrame, useLoader } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader.js";
import { clone as klonSkinned } from "three/examples/jsm/utils/SkeletonUtils.js";

import { matriksNormal } from "@/components/warehouse-twin/aset";
import { JalurGudang, jarakBolakBalik, panjangJalur, posisiPadaJalur } from "@/lib/twin";

const URL_PEKERJA = "/models/worker/human.fbx";
export const TINGGI_PEKERJA = 1.75;
const V_PEKERJA = 1.15;
const JEDA = 2.2;
/** langkah per meter pada klip Walk; dipakai menyamakan kecepatan kaki dengan gerak */
const LANGKAH_PER_METER = 0.72;

/** Palet 32x32 asli dengan baju diganti rompi keselamatan dan celana kerja. */
const PALET_SERAGAM = [
  "/models/worker/KerjaLightOranye.png",
  "/models/worker/KerjaDarkStabilo.png",
  "/models/worker/KerjaDarkOranye.png",
  "/models/worker/KerjaLightStabilo.png",
];

export type NamaKlip = "jalan" | "diam" | "kerja";

export interface Manusia {
  aktor: THREE.Group;
  mixer: THREE.AnimationMixer;
  aksi: Partial<Record<NamaKlip, THREE.AnimationAction>>;
  tulang: Record<string, THREE.Object3D>;
  /** ganti klip dengan transisi halus; tidak melakukan apa-apa bila sudah aktif */
  main: (klip: NamaKlip, transisi?: number) => void;
}

/** Bahan bersama helm, sekali per halaman. */
let _helm: { kubah: THREE.SphereGeometry; tepi: THREE.CylinderGeometry; mat: THREE.MeshStandardMaterial } | null = null;
function helmBersama() {
  return (_helm ??= {
    kubah: new THREE.SphereGeometry(0.125, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2),
    tepi: new THREE.CylinderGeometry(0.15, 0.15, 0.012, 24),
    mat: new THREE.MeshStandardMaterial({ color: "#facc15", roughness: 0.35, metalness: 0.1 }),
  });
}

export function useManusia(varian = 0): Manusia {
  const fbx = useLoader(FBXLoader, URL_PEKERJA);
  const palet = useLoader(THREE.TextureLoader, PALET_SERAGAM[varian % PALET_SERAGAM.length]);
  useMemo(() => {
    palet.magFilter = THREE.NearestFilter;
    palet.minFilter = THREE.NearestFilter;
    palet.colorSpace = THREE.SRGBColorSpace;
    palet.generateMipmaps = false;
  }, [palet]);

  const { aktor, tulang } = useMemo(() => {
    const k = klonSkinned(fbx) as THREE.Group;
    const { m } = matriksNormal(k, { tinggi: TINGGI_PEKERJA });
    const akar = new THREE.Group();
    akar.add(k);
    k.applyMatrix4(m);
    k.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (mesh.isMesh) {
        mesh.castShadow = true; mesh.receiveShadow = true; mesh.frustumCulled = false;
        mesh.material = new THREE.MeshStandardMaterial({ map: palet, roughness: 0.75, metalness: 0 });
      }
    });
    const t: Record<string, THREE.Object3D> = {};
    k.traverse((o) => { if ((o as THREE.Bone).isBone) t[o.name] = o; });
    // helm menempel di tulang kepala; skala tulang dibatalkan supaya ukurannya dalam meter
    const kepala = t["Head"];
    if (kepala) {
      const hb = helmBersama();
      const h = new THREE.Group();
      const kubah = new THREE.Mesh(hb.kubah, hb.mat);
      const tepi = new THREE.Mesh(hb.tepi, hb.mat);
      kubah.castShadow = true;
      h.add(kubah, tepi);
      akar.updateMatrixWorld(true);
      const s = new THREE.Vector3();
      kepala.getWorldScale(s);
      h.scale.setScalar(1 / s.x);
      h.position.set(0, 0.17 / s.y, 0.01 / s.z);
      kepala.add(h);
    }
    return { aktor: akar, tulang: t };
  }, [fbx, palet]);

  const mixer = useMemo(() => new THREE.AnimationMixer(aktor.children[0]), [aktor]);
  const aksi = useMemo(() => {
    const cari = (re: RegExp) => fbx.animations.find((c) => re.test(c.name));
    const a: Partial<Record<NamaKlip, THREE.AnimationAction>> = {};
    const cj = cari(/\|walk$/i), cd = cari(/\|idle$/i), ck = cari(/\|working$/i);
    if (cj) a.jalan = mixer.clipAction(cj);
    if (cd) a.diam = mixer.clipAction(cd);
    if (ck) a.kerja = mixer.clipAction(ck);
    return a;
  }, [mixer, fbx]);
  // Hanya dihentikan, tidak di-uncache: di mode Strict React memasang efek dua
  // kali, dan aksi yang sudah di-uncache tidak bisa dimainkan lagi.
  useEffect(() => () => { mixer.stopAllAction(); }, [mixer]);

  const aktif = useRef<NamaKlip | null>(null);
  const main = useMemo(() => (klip: NamaKlip, transisi = 0.3) => {
    if (aktif.current === klip) return;
    const ke = aksi[klip];
    const dari = aktif.current ? aksi[aktif.current] : undefined;
    aktif.current = klip;
    ke?.reset().fadeIn(dari ? transisi : 0).play();
    dari?.fadeOut(transisi);
  }, [aksi]);

  return { aktor, mixer, aksi, tulang, main };
}

/**
 * Menempelkan benda (papan klip, pemindai, kardus) ke tulang tangan.
 * Benda dijadikan anak tulang dengan skala tulang dibatalkan, sehingga ukuran
 * dan offset-nya ditulis dalam meter, relatif terhadap tangan.
 */
export function tempelKeTulang(
  m: Manusia, namaTulang: string, benda: THREE.Object3D,
  posisi: [number, number, number], rotasi: [number, number, number] = [0, 0, 0],
): () => void {
  const t = m.tulang[namaTulang];
  if (!t) return () => {};
  m.aktor.updateMatrixWorld(true);
  const s = new THREE.Vector3();
  t.getWorldScale(s);
  const wadah = new THREE.Group();
  wadah.scale.setScalar(1 / s.x);
  wadah.position.set(posisi[0] / s.x, posisi[1] / s.y, posisi[2] / s.z);
  wadah.rotation.set(...rotasi);
  wadah.add(benda);
  t.add(wadah);
  return () => { t.remove(wadah); };
}

/** Pekerja yang berjalan bolak-balik di satu lorong dan berhenti sebentar di ujungnya. */
export default function PekerjaFBX({
  rute, mulai, jalan, varian = 0,
}: { rute: JalurGudang["pekerja"][number]; mulai: number; jalan: boolean; varian?: number }) {
  const m = useManusia(varian);
  const jam = useRef(mulai);
  const { kumulatif, total } = useMemo(() => panjangJalur(rute, false), [rute]);

  useFrame((_, dt) => {
    const d = Math.min(dt, 0.1);
    if (jalan) jam.current += d;
    const g = jarakBolakBalik(jam.current, total, V_PEKERJA, JEDA);
    const p = posisiPadaJalur(rute, kumulatif, total, g.d, false);
    m.aktor.position.set(p.x, 0, p.z);
    // model menghadap +z; saat diam di ujung, menghadap rak
    m.aktor.rotation.y = g.diam ? Math.PI : g.maju ? p.arah : p.arah + Math.PI;
    m.main(g.diam ? "diam" : "jalan", 0.25);
    if (jalan) {
      if (m.aksi.jalan && !g.diam) m.aksi.jalan.timeScale = V_PEKERJA * LANGKAH_PER_METER * 1.4;
      m.mixer.update(d);
    }
  });
  return <primitive object={m.aktor} />;
}
