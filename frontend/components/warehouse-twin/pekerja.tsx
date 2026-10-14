"use client";

/**
 * Pekerja gudang: model manusia beranimasi (Quaternius "Animated Human", CC0)
 * dengan helm keselamatan. Animasi Walk/Idle berasal dari berkas modelnya;
 * jalur dan jedanya ditentukan lib/twin.ts. SIMULASI, bukan pelacakan.
 *
 * FBX dimuat saat dibutuhkan (FBXLoader bawaan three). Tekstur modelnya hanya
 * palet warna 1 piksel, dialihkan lewat URL modifier ke public/models/worker.
 */

import { useFrame, useLoader } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { FBXLoader } from "three/examples/jsm/loaders/FBXLoader.js";
import { clone as klonSkinned } from "three/examples/jsm/utils/SkeletonUtils.js";

import { matriksNormal } from "@/components/warehouse-twin/aset";
import { JalurGudang, jarakBolakBalik, panjangJalur, posisiPadaJalur } from "@/lib/twin";

const URL_PEKERJA = "/models/worker/human.fbx";
const TINGGI = 1.75;
const V_PEKERJA = 1.15;
const JEDA = 2.2;
/** langkah per meter pada klip Walk; dipakai menyamakan kecepatan kaki dengan gerak */
const LANGKAH_PER_METER = 0.72;

const PALET_WARNA = [
  "/models/worker/ClothedLightSkin.png",
  "/models/worker/ClothedDarkSkin.png",
  "/models/worker/ClothedLightSkin1.png",
  "/models/worker/ClothedDarkSkin1.png",
];

export default function PekerjaFBX({
  rute, mulai, jalan, varian = 0,
}: { rute: JalurGudang["pekerja"][number]; mulai: number; jalan: boolean; varian?: number }) {
  const fbx = useLoader(FBXLoader, URL_PEKERJA);
  // FBX tidak membawa rujukan tekstur; modelnya memakai palet warna 32x32 yang dipasang di sini
  const palet = useLoader(THREE.TextureLoader, PALET_WARNA[varian % PALET_WARNA.length]);
  useMemo(() => {
    palet.magFilter = THREE.NearestFilter;
    palet.minFilter = THREE.NearestFilter;
    palet.colorSpace = THREE.SRGBColorSpace;
    palet.generateMipmaps = false;
  }, [palet]);

  const { aktor, klip, kepala, helm } = useMemo(() => {
    const k = klonSkinned(fbx) as THREE.Group;
    const { m } = matriksNormal(k, { tinggi: TINGGI });
    const akar = new THREE.Group();
    akar.add(k);
    k.applyMatrix4(m);
    k.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (mesh.isMesh) {
        mesh.castShadow = true; mesh.receiveShadow = true; mesh.frustumCulled = false;
        mesh.material = new THREE.MeshStandardMaterial({ map: palet, roughness: 0.8, metalness: 0 });
      }
    });
    let kep: THREE.Object3D | null = null;
    k.traverse((o) => { if (o.name === "Head") kep = o; });
    // helm keselamatan kuning: setengah bola + pinggiran
    const h = new THREE.Group();
    const kubah = new THREE.Mesh(
      new THREE.SphereGeometry(0.125, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: "#facc15", roughness: 0.35, metalness: 0.1 }));
    const tepi = new THREE.Mesh(
      new THREE.CylinderGeometry(0.15, 0.15, 0.012, 24),
      new THREE.MeshStandardMaterial({ color: "#eab308", roughness: 0.4 }));
    kubah.castShadow = true;
    h.add(kubah, tepi);
    akar.add(h);
    return { aktor: akar, klip: fbx.animations, kepala: kep as THREE.Object3D | null, helm: h };
  }, [fbx, palet]);

  const mixer = useMemo(() => new THREE.AnimationMixer(aktor.children[0]), [aktor]);
  const aksi = useRef<{ jalan?: THREE.AnimationAction; diam?: THREE.AnimationAction }>({});
  useEffect(() => {
    const cari = (re: RegExp) => klip.find((c) => re.test(c.name));
    const cj = cari(/walk/i) ?? cari(/run/i);
    const cd = cari(/idle/i);
    aksi.current.jalan = cj ? mixer.clipAction(cj) : undefined;
    aksi.current.diam = cd ? mixer.clipAction(cd) : undefined;
    aksi.current.jalan?.play();
    return () => { mixer.stopAllAction(); mixer.uncacheRoot(aktor.children[0]); };
  }, [mixer, klip, aktor]);

  const jam = useRef(mulai);
  const sedangDiam = useRef<boolean | null>(null);
  const { kumulatif, total } = useMemo(() => panjangJalur(rute, false), [rute]);
  const tmp = useMemo(() => new THREE.Vector3(), []);
  const posisiKepala = useMemo(() => new THREE.Vector3(), []);

  useFrame((_, dt) => {
    const d = Math.min(dt, 0.1);
    if (jalan) jam.current += d;
    const g = jarakBolakBalik(jam.current, total, V_PEKERJA, JEDA);
    const p = posisiPadaJalur(rute, kumulatif, total, g.d, false);
    aktor.position.set(p.x, 0, p.z);
    // model menghadap +z; saat diam di ujung, menghadap rak
    aktor.rotation.y = g.diam ? Math.PI : g.maju ? p.arah : p.arah + Math.PI;

    if (sedangDiam.current !== g.diam) {
      sedangDiam.current = g.diam;
      const dari = g.diam ? aksi.current.jalan : aksi.current.diam;
      const ke = g.diam ? aksi.current.diam : aksi.current.jalan;
      ke?.reset().fadeIn(0.25).play();
      dari?.fadeOut(0.25);
    }
    if (jalan) {
      if (aksi.current.jalan && !g.diam) aksi.current.jalan.timeScale = V_PEKERJA * LANGKAH_PER_METER * 1.4;
      mixer.update(d);
    }
    // helm mengikuti tulang kepala
    if (kepala) {
      kepala.getWorldPosition(tmp);
      posisiKepala.copy(tmp);
      aktor.updateMatrixWorld();
      aktor.worldToLocal(posisiKepala);
      helm.position.set(posisiKepala.x, posisiKepala.y + 0.06, posisiKepala.z + 0.0);
    }
  });
  return <primitive object={aktor} />;
}
