"use client";

/**
 * Scene 3D untuk 3D Warehouse Twin (React Three Fiber).
 *
 * Dimuat lewat next/dynamic tanpa SSR dari halamannya, supaya three.js hanya
 * terunduh di halaman ini dan tidak membebani modul lain.
 *
 * `frameloop="demand"`: kanvas hanya menggambar saat ada yang berubah (kamera
 * digerakkan, sorotan, pilihan). Gudang yang didiamkan tidak memakai GPU, jadi
 * tetap nyaman di perangkat tanpa GPU kuat.
 *
 * Geometri dan material dibuat SEKALI per scene (useMemo) dan dipakai bersama
 * semua rak/kotak; dibuang lewat dispose saat scene dilepas.
 */

import { Canvas, ThreeEvent, useThree } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";

import AktorGudang from "@/components/warehouse-twin/aktor";
import AreaDock from "@/components/warehouse-twin/dock";
import RuteView from "@/components/warehouse-twin/rute";
import type { HasilRute } from "@/lib/picking";
import { AsetAman, URL_ASET, buatGeometriRak, paletBersama, useGeometriGLB } from "@/components/warehouse-twin/aset";
import { Dock, RakTwin, StatusTwin, TataLetak, UKURAN, WARNA_STATUS, layoutDock } from "@/lib/twin";

export interface Pilihan {
  rakId: string;
  /** item_id kotak terpilih, atau null bila hanya rak */
  itemId: number | null;
}

interface Props {
  tata: TataLetak;
  pilihan: Pilihan | null;
  onPilih: (p: Pilihan | null) => void;
  /** naik setiap tombol reset ditekan */
  resetKe: number;
  /** true = pekerja dan forklift bergerak (kanvas menggambar terus) */
  animasi: boolean;
  /** bayangan dinamis; matikan pada perangkat tanpa GPU kuat */
  bayangan: boolean;
  /** hasil optimasi rute picking, atau null */
  rute?: HasilRute | null;
  tampilPembanding?: boolean;
  /** barang yang dipindah pada skenario what-if; diberi sorotan ungu */
  ditandai?: Set<number>;
}

function posisiAwal(tata: TataLetak, dock: Dock, aspek = 1.2): [number, number, number] {
  // Layar sempit (tablet tegak) butuh jarak lebih jauh supaya lebar gudang muat.
  const jauh = Math.max(dock.bentang, 8) * Math.max(1, 1.25 / aspek) * 0.9;
  return [jauh * 0.45, jauh * 0.8, dock.pusatZ + jauh * 0.6];
}

/* ------------------------------------------------------------------ */
/* Bahan dan geometri bersama                                           */
/* ------------------------------------------------------------------ */

let _beton: THREE.CanvasTexture | null = null;
/** Lantai beton: bintik halus + garis sambungan pelat tiap 6 m. */
function teksturBeton(): THREE.CanvasTexture {
  if (_beton) return _beton;
  const c = document.createElement("canvas");
  c.width = c.height = 512;
  const g = c.getContext("2d")!;
  g.fillStyle = "#c9ced6"; g.fillRect(0, 0, 512, 512);
  let seed = 11;
  const r = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  for (let i = 0; i < 9000; i++) {
    const v = 150 + r() * 70;
    g.fillStyle = `rgba(${v},${v},${v + 4},${0.05 + r() * 0.12})`;
    g.fillRect(r() * 512, r() * 512, 1 + r() * 3, 1 + r() * 3);
  }
  for (let i = 0; i < 14; i++) { // noda halus
    g.fillStyle = `rgba(90,95,105,${0.012 + r() * 0.02})`; g.beginPath();
    g.ellipse(r() * 512, r() * 512, 20 + r() * 60, 10 + r() * 30, r() * 3, 0, Math.PI * 2); g.fill();
  }
  g.strokeStyle = "rgba(60,66,78,0.4)"; g.lineWidth = 2; g.strokeRect(1.5, 1.5, 509, 509);
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 4;
  t.colorSpace = THREE.SRGBColorSpace;
  _beton = t;
  return t;
}

function useBersama() {
  const bersama = useMemo(() => {
    const kotak = new THREE.BoxGeometry(1, 1, 1);
    const lebarRak = UKURAN.slotW * UKURAN.slotPerTingkat;
    const rak = buatGeometriRak(lebarRak, UKURAN.slotD);
    const bahan = {
      tiang: new THREE.MeshStandardMaterial({ color: "#1d4f9c", metalness: 0.45, roughness: 0.45 }),
      balok: new THREE.MeshStandardMaterial({ color: "#e8731a", metalness: 0.4, roughness: 0.5 }),
      dek: new THREE.MeshStandardMaterial({ color: "#aeb6c4", metalness: 0.5, roughness: 0.55 }),
      label: new THREE.MeshBasicMaterial({ color: "#ffffff" }),
      // putih; warna per-instance datang dari instanceColor
      filmDasar: new THREE.MeshStandardMaterial({ color: "#ffffff", transparent: true, opacity: 0.4, roughness: 0.25, depthWrite: false }),
      stripDasar: new THREE.MeshStandardMaterial({ color: "#ffffff", roughness: 0.5 }),
    };
    const status = Object.fromEntries(
      (Object.keys(WARNA_STATUS) as StatusTwin[]).map((k) => [
        k,
        new THREE.MeshStandardMaterial({ color: WARNA_STATUS[k], roughness: 0.5, emissive: WARNA_STATUS[k], emissiveIntensity: 0.35 }),
      ])
    ) as Record<StatusTwin, THREE.MeshStandardMaterial>;
    const film = Object.fromEntries(
      (Object.keys(WARNA_STATUS) as StatusTwin[]).map((k) => [
        k,
        new THREE.MeshStandardMaterial({ color: WARNA_STATUS[k], transparent: true, opacity: 0.34, roughness: 0.25, depthWrite: false }),
      ])
    ) as Record<StatusTwin, THREE.MeshStandardMaterial>;
    const palet = paletBersama();
    return { kotak, rak, bahan, status, film, palet };
  }, []);
  useEffect(
    () => () => {
      bersama.kotak.dispose();
      bersama.rak.tiang.dispose(); bersama.rak.balok.dispose(); bersama.rak.alas.dispose();
      Object.values(bersama.bahan).forEach((m) => m.dispose());
      Object.values(bersama.status).forEach((m) => m.dispose());
      Object.values(bersama.film).forEach((m) => m.dispose());
    },
    [bersama]
  );
  return bersama;
}

type Bersama = ReturnType<typeof useBersama>;

/** Tumpukan kardus asli (Poly Haven) di satu rak: satu InstancedMesh per rak. */
function KardusRak({ rak }: { rak: RakTwin }) {
  const { geometri, bahan } = useGeometriGLB(URL_ASET.kardus, { lebar: 0.44 });
  const ref = useRef<THREE.InstancedMesh>(null);
  const tinggiKotak = useMemo(() => {
    geometri.computeBoundingBox();
    return geometri.boundingBox!.max.y;
  }, [geometri]);
  const matriks = useMemo(() => {
    const out: THREE.Matrix4[] = [];
    const m = new THREE.Matrix4();
    for (const s of rak.slots) {
      const q = Number(s.item.quantity);
      if (q <= 0) continue; // stok habis: pallet kosong
      const lapis = Math.max(1, Math.round((s.isi ?? 0.67) * 3));
      const yDasar = s.y + 0.125 + 0.145;
      for (let l = 0; l < lapis; l++) {
        for (const dx of [-0.24, 0.24]) for (const dz of [-0.2, 0.2]) {
          // sedikit variasi putaran supaya tidak terlihat seperti cetakan
          const rot = (((s.item.item_id * 31 + l * 7 + (dx > 0 ? 3 : 0) + (dz > 0 ? 5 : 0)) % 7) - 3) * 0.018;
          m.makeRotationY(rot).setPosition(s.x + dx, yDasar + l * tinggiKotak, dz);
          out.push(m.clone());
        }
      }
    }
    return out;
  }, [rak, tinggiKotak]);
  useEffect(() => {
    const im = ref.current;
    if (!im) return;
    matriks.forEach((m, i) => im.setMatrixAt(i, m));
    im.instanceMatrix.needsUpdate = true;
    im.count = matriks.length;
  }, [matriks]);
  if (!matriks.length) return null;
  return <instancedMesh ref={ref} args={[geometri, bahan, matriks.length]} castShadow receiveShadow frustumCulled={false} />;
}

/**
 * Pallet, film status, dan penanda balok untuk SELURUH slot satu rak dalam
 * tiga InstancedMesh (bukan tiga mesh per slot): warna status lewat instanceColor.
 */
function SlotRak({ rak, bersama }: { rak: RakTwin; bersama: Bersama }) {
  const refPalet = useRef<THREE.InstancedMesh>(null);
  const refFilm = useRef<THREE.InstancedMesh>(null);
  const refStrip = useRef<THREE.InstancedMesh>(null);
  const n = rak.slots.length;
  const warna = useMemo(() => {
    const m: Record<string, THREE.Color> = {};
    for (const k of Object.keys(WARNA_STATUS) as StatusTwin[]) m[k] = new THREE.Color(WARNA_STATUS[k]);
    return m;
  }, []);
  useEffect(() => {
    const m = new THREE.Matrix4(), pos = new THREE.Vector3(), q = new THREE.Quaternion(), sk = new THREE.Vector3();
    rak.slots.forEach((s, i) => {
      const yDek = s.y + 0.125;
      refPalet.current?.setMatrixAt(i, m.makeTranslation(s.x, yDek, 0));
      const th = tinggiFilm(s);
      refFilm.current?.setMatrixAt(i, m.compose(pos.set(s.x, yDek + 0.145 + th / 2, 0), q, sk.set(0.98, th, 0.86)));
      refFilm.current?.setColorAt(i, warna[s.item.status]);
      for (let k = 0; k < 2; k++) {
        const sz = k === 0 ? -1 : 1;
        refStrip.current?.setMatrixAt(i * 2 + k,
          m.compose(pos.set(s.x, s.y + 0.015, sz * (rak.dalam / 2 - 0.065)), q, sk.set(UKURAN.slotW * 0.9, 0.1, 0.02)));
        refStrip.current?.setColorAt(i * 2 + k, warna[s.item.status]);
      }
    });
    for (const r of [refPalet, refFilm, refStrip]) {
      if (!r.current) continue;
      r.current.instanceMatrix.needsUpdate = true;
      if (r.current.instanceColor) {
        r.current.instanceColor.needsUpdate = true;
        // instanceColor baru ada setelah render pertama: shader harus dikompilasi ulang agar memakainya
        (r.current.material as THREE.Material).needsUpdate = true;
      }
    }
  }, [rak, warna]);
  return (
    <>
      <instancedMesh ref={refPalet} args={[bersama.palet.geo, bersama.palet.mat, n]} castShadow receiveShadow frustumCulled={false} />
      <instancedMesh ref={refFilm} args={[bersama.kotak, bersama.bahan.filmDasar, n]} frustumCulled={false} renderOrder={2} />
      <instancedMesh ref={refStrip} args={[bersama.kotak, bersama.bahan.stripDasar, n * 2]} frustumCulled={false} />
    </>
  );
}

/** Tinggi tumpukan kardus pada satu slot (m); 0,06 saat kosong supaya status tetap terbaca. */
const TINGGI_KARDUS = 0.3;
function tinggiFilm(s: { item: { quantity: number | string }; isi: number | null }): number {
  if (Number(s.item.quantity) <= 0) return 0.06;
  return Math.max(1, Math.round((s.isi ?? 0.67) * 3)) * TINGGI_KARDUS;
}

function Rak({
  rak, bersama, terpilih, itemTerpilih, onPilih, ditandai,
}: {
  ditandai?: Set<number>;
  rak: RakTwin;
  bersama: Bersama;
  terpilih: boolean;
  itemTerpilih: number | null;
  onPilih: (p: Pilihan) => void;
}) {
  const [hover, setHover] = useState(false);
  const { lebar, dalam, tinggi } = rak;

  useEffect(() => {
    if (!hover) return;
    document.body.style.cursor = "pointer";
    return () => { document.body.style.cursor = ""; };
  }, [hover]);

  const klikRak = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    onPilih({ rakId: rak.id, itemId: null });
  };
  const sorot = terpilih || hover;
  // barang berstatus perhatian/kritis pada lapisan yang sedang aktif
  const risiko = rak.slots.filter((x) => x.item.status === "kritis" || x.item.status === "perhatian").length;

  return (
    <group position={[rak.x, 0, rak.z]}>
      {/* badan transparan agar seluruh rak mudah diklik dan disorot */}
      <mesh
        position={[0, tinggi / 2, 0]}
        scale={[lebar, tinggi, dalam]}
        geometry={bersama.kotak}
        onClick={klikRak}
        onPointerOver={(e) => { e.stopPropagation(); setHover(true); }}
        onPointerOut={() => setHover(false)}
      >
        <meshBasicMaterial
          color={sorot ? "#2563eb" : "#ffffff"}
          transparent
          opacity={terpilih ? 0.12 : hover ? 0.08 : 0}
          depthWrite={false}
        />
      </mesh>

      {/* rangka baja: tiang biru, balok beban oranye, dek abu (tiga geometri gabungan) */}
      <mesh geometry={bersama.rak.tiang} material={bersama.bahan.tiang} castShadow receiveShadow />
      <mesh geometry={bersama.rak.balok} material={bersama.bahan.balok} castShadow receiveShadow />
      <mesh geometry={bersama.rak.alas} material={bersama.bahan.dek} receiveShadow />

      {/* pallet, film status, dan penanda balok: instancing per rak */}
      <SlotRak rak={rak} bersama={bersama} />
      {/* area klik per SKU + sorotan pilihan (tidak menggambar apa pun saat tidak dipilih) */}
      {rak.slots.map((s) => {
        const dipilih = itemTerpilih === s.item.item_id;
        const yDek = s.y + 0.125;
        return (
          <mesh
            key={s.item.item_id}
            geometry={bersama.kotak}
            position={[s.x, yDek + 0.45, 0]}
            scale={[UKURAN.slotW * 0.96, 0.9, UKURAN.slotD * 0.98]}
            onClick={(e) => { e.stopPropagation(); onPilih({ rakId: rak.id, itemId: s.item.item_id }); }}
            onPointerOver={(e) => { e.stopPropagation(); setHover(true); }}
            onPointerOut={() => setHover(false)}
          >
            <meshBasicMaterial
              color={dipilih ? "#2563eb" : "#7c3aed"}
              transparent
              opacity={dipilih ? 0.28 : ditandai?.has(s.item.item_id) ? 0.3 : 0}
              depthWrite={false}
            />
          </mesh>
        );
      })}
      <AsetAman>
        <KardusRak rak={rak} />
      </AsetAman>

      {/* label rak; DOM, sehingga tajam dan tidak butuh berkas font */}
      <Html position={[0, tinggi + 0.35, 0]} center distanceFactor={14} zIndexRange={[10, 0]} style={{ pointerEvents: "none" }}>
        <div
          style={{
            whiteSpace: "nowrap", fontSize: 12, fontWeight: 600, padding: "2px 8px", borderRadius: 6,
            background: terpilih ? "#2563eb" : "rgba(255,255,255,0.92)", color: terpilih ? "#fff" : "#0d1526",
            boxShadow: "0 0 0 1px rgba(13,21,38,0.12)",
          }}
        >
          {rak.kode} · {rak.kategori}
          {risiko > 0 && (
            <span style={{
              marginLeft: 6, display: "inline-block", minWidth: 16, padding: "0 4px", borderRadius: 8, textAlign: "center",
              background: WARNA_STATUS.kritis, color: "#fff", fontSize: 11, fontWeight: 700,
            }}>{risiko}</span>
          )}
        </div>
      </Html>
    </group>
  );
}

/**
 * Detak animasi 30 fps. Kanvas berjalan `frameloop="demand"`: tanpa detak ini
 * (animasi dijeda) ia tidak menggambar sama sekali; dengan detak ini ia
 * menggambar 30 kali per detik. Separuh dari 60 fps cukup untuk gerak
 * forklift dan pekerja, dan memberi ruang pada perangkat tanpa GPU kuat.
 */
function Detak({ aktif }: { aktif: boolean }) {
  const { invalidate, gl, scene, camera } = useThree();
  const kontrol = useThree((st) => st.controls);
  useEffect(() => {
    (window as unknown as { __twinGL?: unknown }).__twinGL = gl.info;
    (window as unknown as { __twinScene?: unknown }).__twinScene = scene;
    (window as unknown as { __twinCam?: unknown }).__twinCam = camera;
    (window as unknown as { __twinCtl?: unknown }).__twinCtl = kontrol;
    if (!aktif) return;
    const id = window.setInterval(() => { if (!document.hidden) invalidate(); }, 1000 / 30);
    return () => window.clearInterval(id);
  }, [aktif, invalidate, gl, scene, camera, kontrol]);
  return null;
}

/** Menggerakkan kamera ke posisi awal tiap `resetKe` berubah. */
function Kamera({ tata, dock, resetKe }: { tata: TataLetak; dock: Dock; resetKe: number }) {
  const kontrol = useRef<OrbitControlsImpl>(null);
  const { camera, invalidate, size } = useThree();
  const aspek = size.width / Math.max(1, size.height);
  // Kunci ukuran layout, BUKAN identitas objek: data disegarkan tiap 30 dtk dan menghasilkan
  // `tata`/`dock` baru yang isinya sama; kamera pengguna tidak boleh ikut ter-reset.
  const kunci = `${tata.rak.length}|${tata.kolom}|${tata.baris}|${Math.round(aspek * 10)}`;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const awal = useMemo(() => posisiAwal(tata, dock, aspek), [kunci]);
  useEffect(() => {
    camera.position.set(...awal);
    camera.lookAt(0, 0.5, dock.pusatZ);
    kontrol.current?.target.set(0, 0.5, dock.pusatZ);
    kontrol.current?.update();
    invalidate();
  }, [awal, resetKe, camera, invalidate]);
  return (
    <OrbitControls
      ref={kontrol}
      makeDefault
      enableDamping={false}
      maxPolarAngle={Math.PI / 2 - 0.03}
      minDistance={4}
      maxDistance={Math.max(dock.bentang, 8) * 3}
    />
  );
}

export default function WarehouseScene({ tata, pilihan, onPilih, resetKe, animasi, bayangan, rute = null, tampilPembanding = false, ditandai }: Props) {
  const bersama = useBersama();
  const dock = useMemo(() => layoutDock(tata), [tata]);
  // lantai beton membentang dari dinding dock sampai ujung belakang deretan rak
  const lebar = dock.lebarLantai;
  const dalam = dock.zMaks - dock.zDinding;
  const batas = useMemo(() => {
    const kotak = new THREE.BoxGeometry(lebar, 0.001, dalam);
    const tepi = new THREE.EdgesGeometry(kotak);
    kotak.dispose();
    return tepi;
  }, [lebar, dalam]);
  useEffect(() => () => batas.dispose(), [batas]);
  const lantai = useMemo(() => {
    const t = teksturBeton().clone();
    t.needsUpdate = true;
    t.repeat.set(lebar / 6, dalam / 6);
    return new THREE.MeshStandardMaterial({ map: t, roughness: 0.92, metalness: 0 });
  }, [lebar, dalam]);
  useEffect(() => () => { lantai.map?.dispose(); lantai.dispose(); }, [lantai]);
  const sh = Math.max(dock.bentang, 20);
  return (
    <Canvas
      shadows={bayangan ? "percentage" : false}
      frameloop="demand"
      dpr={[1, 1.75]}
      camera={{ fov: 45, near: 0.1, far: 500, position: posisiAwal(tata, dock) }}
      gl={{ antialias: true, powerPreference: "low-power" }}
      onPointerMissed={() => onPilih(null)}
    >
      <color attach="background" args={["#e9eef6"]} />
      <hemisphereLight args={["#ffffff", "#8d98aa", 0.85]} />
      <directionalLight
        position={[sh * 0.5, sh * 0.9, sh * 0.35]}
        intensity={2.1}
        castShadow={bayangan}
        shadow-mapSize={[1024, 1024]}
        shadow-camera-left={-sh * 0.7}
        shadow-camera-right={sh * 0.7}
        shadow-camera-top={sh * 0.7}
        shadow-camera-bottom={-sh * 0.7}
        shadow-camera-near={1}
        shadow-camera-far={sh * 3}
        shadow-bias={-0.0006}
        shadow-normalBias={0.04}
      />

      {/* lantai beton dan batas area */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, dock.pusatZ]} material={lantai} receiveShadow>
        <planeGeometry args={[lebar, dalam]} />
      </mesh>
      <lineSegments position={[0, 0.01, dock.pusatZ]} geometry={batas}>
        <lineBasicMaterial color="#2563eb" />
      </lineSegments>

      {tata.rak.map((r) => (
        <Rak
          key={r.id}
          rak={r}
          bersama={bersama}
          terpilih={pilihan?.rakId === r.id}
          itemTerpilih={pilihan?.rakId === r.id ? pilihan.itemId : null}
          ditandai={ditandai}
          onPilih={onPilih}
        />
      ))}
      <AktorGudang tata={tata} jalan={animasi} />
      <AreaDock tata={tata} jalan={animasi} />
      {rute && <RuteView hasil={rute} tampilPembanding={tampilPembanding} jalan={animasi} />}
      <Kamera tata={tata} dock={dock} resetKe={resetKe} />
      <Detak aktif={animasi} />
    </Canvas>
  );
}
