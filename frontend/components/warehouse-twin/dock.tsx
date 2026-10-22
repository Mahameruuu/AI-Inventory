"use client";

/**
 * Area dock: dinding berpintu, jalan, truk, forklift dock, dan pallet.
 *
 * SIMULASI VISUAL, BUKAN DATA. Jadwal truk dan pallet yang berpindah adalah
 * siklus tetap (lib/twin.ts: fasaTruk, kegiatanDock); tidak berasal dari
 * dokumen penerimaan atau pengeluaran, dan tidak mengubah stok. Dua pintu:
 * PENERIMAAN (truk membongkar ke area staging) dan PENGELUARAN (pallet dari
 * staging dimuat ke truk).
 */

import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import { createContext, useContext, useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { Alat, Kotak, useAlat } from "@/components/warehouse-twin/aktor";
import { BadanForklift } from "@/components/warehouse-twin/forklift";
import { GEDUNG, bahanGedung, kotakBerUV } from "@/components/warehouse-twin/bangunan";
import { AsetAman, ModelGLB, PaletBermuatan, URL_ASET, matriksNormal } from "@/components/warehouse-twin/aset";
import { useGLTF } from "@react-three/drei";
import { useT } from "@/lib/i18n";
import {
  BayDock, DOCK, Dock, TataLetak, bukaPintu, fasaTruk, kegiatanDock, layoutDock, offsetTruk,
  xSlotStaging, zPaletStaging, zPaletTrailer,
} from "@/lib/twin";

/** Tinggi lantai kargo truk (m) -- forklift menanjak ke sini lewat dock leveler. */
const LANTAI_TRUK = 0.62;
const PANJANG_TRUK = 6.4;

/** Truk pengantar (Kenney Car Kit, CC0): pintu belakang dilepas agar kargo terlihat. */
function ModelTruk() {
  const { scene } = useGLTF(URL_ASET.truk, false, true);
  const klon = useMemo(() => {
    const k = scene.clone(true);
    const buang: THREE.Object3D[] = [];
    k.traverse((o) => { if (/door/i.test(o.name)) buang.push(o); });
    buang.forEach((o) => o.parent?.remove(o));
    const { m } = matriksNormal(k, { panjang: PANJANG_TRUK });
    const bungkus = new THREE.Group();
    bungkus.add(k);
    k.applyMatrix4(m);
    // model: moncong +z, belakang -z. Kita butuh belakang di z=0 dan moncong ke -z.
    k.rotateY(Math.PI);
    k.position.z -= PANJANG_TRUK / 2;
    k.traverse((o) => { const x = o as THREE.Mesh; if (x.isMesh) { x.castShadow = true; x.receiveShadow = true; } });
    return bungkus;
  }, [scene]);
  return <primitive object={klon} />;
}

function BadanTruk({
  a, slotTrailer,
}: {
  a: Alat;
  slotTrailer: React.RefObject<(THREE.Group | null)[]>;
}) {
  return (
    <group>
      <AsetAman cadangan={<Kotak a={a} m={a.bahan.trailerA} p={[0, 1.4, -PANJANG_TRUK / 2]} s={[2.5, 2.8, PANJANG_TRUK]} />}>
        <ModelTruk />
      </AsetAman>
      {/* slot pallet di dalam kargo (dihidupkan per frame) */}
      {Array.from({ length: DOCK.jumlahPalet }, (_, j) => (
        <AsetAman key={j}>
          <PaletBermuatan ref={(g) => { if (g) { (slotTrailer.current ??= [])[j] = g; } }} />
        </AsetAman>
      ))}
    </group>
  );
}

function BayDockView({ a, d, bay }: { a: Alat; d: Dock; bay: BayDock }) {
  const t = useT();
  const jalanRef = useContext(JalanCtx);
  const jam = useRef(0);
  const truk = useRef<THREE.Group>(null);
  const pintu = useRef<THREE.Mesh>(null);
  const pFork = useRef<THREE.Group>(null);
  const garpu = useRef<THREE.Group>(null);
  const muatan = useRef<THREE.Group>(null);
  const lampu = useRef<THREE.Mesh>(null);
  const slotTrailer = useRef<(THREE.Group | null)[]>([]);
  const slotStaging = useRef<(THREE.Group | null)[]>([]);
  const arahHalus = useRef<number | null>(null);
  const buka = useRef(0);
  const zonaMat = bay.jenis === "terima" ? a.bahan.zonaBiru : a.bahan.zonaHijau;

  // posisi pallet tetap; yang berubah hanya `visible`
  const trailerZ = useMemo(
    () => Array.from({ length: DOCK.jumlahPalet }, (_, j) => zPaletTrailer(d, j) - d.zTruk),
    [d]
  );

  useFrame((_, dt) => {
    // jam disimpan di sini; jeda dikendalikan induk lewat `jalan` pada AreaDock
    jam.current += Math.min(dt, 0.1) * (jalanRef.current ? 1 : 0);
    const { fase, f } = fasaTruk(jam.current, bay.mulai);
    if (truk.current) {
      truk.current.position.set(bay.x, 0, d.zTruk + offsetTruk(fase, f));
      truk.current.visible = fase !== "jeda";
    }
    // pintu bergulir naik saat truk mendekat dan turun setelah pergi
    const target = bukaPintu(fase, f);
    buka.current += (target - buka.current) * Math.min(1, dt * 4);
    // pintu menggulung: tinggi panel mengecil dan tetap menempel di atas bukaan
    if (pintu.current) {
      const h = DOCK.pintuTinggi * (1 - 0.92 * buka.current);
      pintu.current.scale.y = h;
      pintu.current.position.y = DOCK.pintuTinggi - h / 2;
    }

    const pose = kegiatanDock(d, bay, fase, f);
    if (pFork.current) {
      // dock leveler: forklift menanjak ke lantai kargo saat melewati dinding
      const naik = LANTAI_TRUK * Math.min(1, Math.max(0, (d.zDinding + 0.5 - pose.z) / 1.0));
      pFork.current.position.set(pose.x, naik, pose.z);
      if (arahHalus.current === null) arahHalus.current = pose.arah;
      let s = ((pose.arah - arahHalus.current + Math.PI) % (2 * Math.PI)) - Math.PI;
      if (s < -Math.PI) s += 2 * Math.PI;
      arahHalus.current += s * Math.min(1, dt * 8);
      pFork.current.rotation.y = arahHalus.current;
    }
    if (garpu.current) garpu.current.position.y = 0.15 + 1.5 * pose.garpu;
    if (muatan.current) muatan.current.visible = pose.bawa;
    if (lampu.current) {
      (lampu.current.material as THREE.MeshStandardMaterial).emissiveIntensity =
        0.3 + 1.2 * (Math.sin(jam.current * 8) > 0 ? 1 : 0);
    }
    pose.trailer.forEach((v, j) => {
      const g = slotTrailer.current[j];
      if (g) { g.visible = v; g.position.set(0, LANTAI_TRUK, trailerZ[j]); }
    });
    pose.staging.forEach((v, i) => { const g = slotStaging.current[i]; if (g) g.visible = v; });
  });

  const zStag = zPaletStaging(d);
  const nama = bay.jenis === "terima" ? t("tw.dock.receiving") : t("tw.dock.shipping");

  return (
    <group>
      {/* zona lantai di depan pintu */}
      <mesh geometry={a.kotak} material={zonaMat} position={[bay.x, 0.008, d.zDinding + 3.3]} scale={[5.4, 0.004, 5.4]} />
      {/* pintu gulung: panel naik ke atas bukaan */}
      <mesh ref={pintu} geometry={a.kotak} material={a.bahan.pintu}
        position={[bay.x, DOCK.pintuTinggi / 2, d.zDinding]} scale={[DOCK.pintuLebar, DOCK.pintuTinggi, 0.12]} />
      {/* kusen pintu bergaris kuning-hitam dan bumper dock karet */}
      {[-1, 1].map((sx) => (
        <group key={sx}>
          <mesh material={bahanGedung().bahaya} position={[bay.x + sx * (DOCK.pintuLebar / 2 + 0.08), DOCK.pintuTinggi / 2, d.zDinding + 0.17]}>
            <boxGeometry args={[0.16, DOCK.pintuTinggi, 0.04]} />
          </mesh>
          <mesh material={a.bahan.hitam} position={[bay.x + sx * (DOCK.pintuLebar / 2 - 0.25), 0.55, d.zDinding + 0.2]} castShadow>
            <boxGeometry args={[0.25, 0.4, 0.12]} />
          </mesh>
        </group>
      ))}
      <mesh material={bahanGedung().bahaya} position={[bay.x, DOCK.pintuTinggi + 0.08, d.zDinding + 0.17]}>
        <boxGeometry args={[DOCK.pintuLebar + 0.32, 0.16, 0.04]} />
      </mesh>
      <Html position={[bay.x, DOCK.pintuTinggi + 0.7, d.zDinding + 0.3]} center distanceFactor={14}
        zIndexRange={[10, 0]} style={{ pointerEvents: "none" }}>
        <div style={{
          whiteSpace: "nowrap", fontSize: 12, fontWeight: 700, padding: "2px 10px", borderRadius: 6,
          background: bay.jenis === "terima" ? "#2563eb" : "#16a34a", color: "#fff",
        }}>{nama}</div>
      </Html>

      {/* pallet di area staging */}
      {Array.from({ length: DOCK.jumlahPalet }, (_, i) => (
        <AsetAman key={i}>
          <PaletBermuatan posisi={[xSlotStaging(bay.x, i), 0, zStag]}
            ref={(g) => { if (g) slotStaging.current[i] = g; }} />
        </AsetAman>
      ))}

      {/* truk */}
      <group ref={truk} name="truk" rotation={[0, 0, 0]}>
        <BadanTruk a={a} slotTrailer={slotTrailer} />
      </group>

      {/* forklift dock */}
      <BadanForklift grup={pFork} garpu={garpu} muatan={muatan} lampu={lampu} />
    </group>
  );
}

const JalanCtx = createContext<{ current: boolean }>({ current: true });

/** Dinding dock setinggi gedung: beton di bawah, panel baja di atas, lintel di atas tiap pintu. */
function DindingDock({ segmen, lubang, z }: { segmen: [number, number][]; lubang: (readonly [number, number])[]; z: number }) {
  const m = bahanGedung();
  const H = GEDUNG.tinggi, Hb = GEDUNG.tinggiBeton, T = 0.3;
  const geo = useMemo(() => ({
    beton: segmen.map(([l, r]) => kotakBerUV(r - l, Hb, T)),
    panel: segmen.map(([l, r]) => kotakBerUV(r - l, H - Hb, T)),
    lintel: lubang.map(([l, r]) => kotakBerUV(r - l, H - DOCK.pintuTinggi, T)),
    // kunci isi, bukan identitas larik: data disegarkan tiap 30 dtk dengan bentuk sama
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [JSON.stringify(segmen), JSON.stringify(lubang), H, Hb]);
  useEffect(() => () => [...geo.beton, ...geo.panel, ...geo.lintel].forEach((x) => x.dispose()), [geo]);
  return (
    <group>
      {segmen.map(([l, r], i) => (
        <group key={i}>
          <mesh geometry={geo.beton[i]} material={m.beton} position={[(l + r) / 2, Hb / 2, z]} receiveShadow />
          <mesh geometry={geo.panel[i]} material={m.panel} position={[(l + r) / 2, Hb + (H - Hb) / 2, z]} receiveShadow />
        </group>
      ))}
      {lubang.map(([l, r], i) => (
        <mesh key={`l${i}`} geometry={geo.lintel[i]} material={m.panel}
          position={[(l + r) / 2, (DOCK.pintuTinggi + H) / 2, z]} receiveShadow />
      ))}
    </group>
  );
}

/** Properti statis berupa model nyata Poly Haven (CC0); semuanya opsional. */
function Properti({ d }: { d: Dock }) {
  const zW = d.zDinding;
  const xKiri = -d.lebarLantai / 2;
  const [b0, b1] = d.bay;
  const tiap = (url: string, fit: object, posisi: [number, number, number], putar = 0, key?: string) => (
    <AsetAman key={key ?? `${url}${posisi.join()}`}>
      <ModelGLB url={url} fit={fit} position={posisi} rotation={[0, putar, 0]} />
    </AsetAman>
  );
  return (
    <group>
      {/* drum di sudut kiri depan */}
      {tiap(URL_ASET.drum, { tinggi: 0.9 }, [xKiri + 1.0, 0, zW + 1.0])}
      {tiap(URL_ASET.drum, { tinggi: 0.9 }, [xKiri + 1.75, 0, zW + 0.9], 0.6)}
      {tiap(URL_ASET.drum, { tinggi: 0.9 }, [xKiri + 1.3, 0, zW + 1.8], 1.2)}
      {/* APAR di kedua sisi tiap pintu */}
      {[b0.x, b1.x].flatMap((x) => [-1, 1].map((sx) =>
        tiap(URL_ASET.apar, { tinggi: 0.62 }, [x + sx * (DOCK.pintuLebar / 2 + 0.5), 0, zW + 0.4], sx * 0.4, `apar${x}${sx}`)))}
      {/* hand truck di dekat staging penerimaan */}
      {tiap(URL_ASET.handTruck, { tinggi: 1.25 }, [b0.x - 3.4, 0, zW + 2.6], -0.5)}
      {/* peti plastik dan kayu di dekat staging pengeluaran */}
      {[0, 1].map((k) => tiap(URL_ASET.petiPlastik, { lebar: 0.6 }, [b1.x + 3.3, k * 0.32, zW + 2.0], 0.15 * k, `pp${k}`))}
      {tiap(URL_ASET.petiKayu, { lebar: 0.75 }, [b1.x + 3.5, 0, zW + 3.0], 0.4)}
    </group>
  );
}

export default function AreaDock({ tata, jalan }: { tata: TataLetak; jalan: boolean }) {
  const a = useAlat();
  const d = useMemo(() => layoutDock(tata), [tata]);
  const ref = useRef(jalan);
  ref.current = jalan;

  const panjang = d.lebarLantai;
  const xs = d.bay.map((b) => b.x);
  // dinding dibagi menjadi segmen di antara bukaan pintu
  const lubang = xs.map((x) => [x - DOCK.pintuLebar / 2, x + DOCK.pintuLebar / 2] as const);
  const tepi = [-panjang / 2, ...lubang.flatMap(([l, r]) => [l, r]), panjang / 2];
  const segmen: [number, number][] = [];
  for (let i = 0; i < tepi.length; i += 2) segmen.push([tepi[i], tepi[i + 1]]);

  return (
    <JalanCtx.Provider value={ref}>
      <group>
        {/* halaman dock di luar dinding: hanya selebar gedung, terlihat lewat pintu */}
        <mesh geometry={a.kotak} material={a.bahan.aspal}
          position={[0, -0.02, d.zDinding - DOCK.jalanDalam / 2 - 0.2]} scale={[panjang + 2, 0.02, DOCK.jalanDalam]} />
        <DindingDock segmen={segmen} lubang={lubang} z={d.zDinding} />
        <Properti d={d} />
        {d.bay.map((b, i) => (
          <BayDockView key={i} a={a} d={d} bay={b} />
        ))}
      </group>
    </JalanCtx.Provider>
  );
}
