"use client";

/**
 * Kegiatan pekerja di gudang: naik tangga memeriksa kardus di rak atas,
 * mencatat di papan klip, memindai barcode, mendorong hand truck, dan
 * forklift yang menaruh pallet ke slot rak.
 *
 * SIMULASI VISUAL, BUKAN PELACAKAN. Lokasi kegiatan diturunkan dari tata letak
 * virtual (lib/twin.ts) dan siklusnya tetap; tidak ada yang berasal dari data
 * orang atau kendaraan sungguhan, dan tidak ada yang mengubah stok.
 *
 * Setiap lorong dipakai paling banyak satu jenis kegiatan supaya tidak ada
 * yang saling tembus -- lihat `rencanaKegiatan`.
 */

import { useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";

import { BadanForklift } from "@/components/warehouse-twin/forklift";
import { AsetAman, ModelGLB, PaletBermuatan, URL_ASET } from "@/components/warehouse-twin/aset";
import { tempelKeTulang, useManusia } from "@/components/warehouse-twin/pekerja";
import { RakTwin, TataLetak, UKURAN, jalurGudang } from "@/lib/twin";

/* ------------------------------------------------------------------ */
/* Rencana: kegiatan apa di lorong mana                                 */
/* ------------------------------------------------------------------ */

export interface RencanaKegiatan {
  /** posisi kaki tangga (dunia) dan rak yang dihadapinya */
  tangga: { x: number; zMuka: number; arah: 1 | -1 } | null;
  catat: { x: number; zMuka: number; arah: 1 | -1 } | null;
  pindai: { x0: number; x1: number; zMuka: number; arah: 1 | -1 } | null;
  forklift: { x: number; zMuka: number; arah: 1 | -1; ySlot: number } | null;
  handTruck: { x0: number; x1: number; z: number } | null;
  /** indeks lorong yang dipakai kegiatan; pekerja berjalan memakai lorong lain */
  lorongTerpakai: Set<number>;
}

const stepZ = UKURAN.slotD + UKURAN.lorong;

/** Rak pada satu baris (z sama), urut dari kiri ke kanan. */
function rakDiBaris(tata: TataLetak, z: number): RakTwin[] {
  return tata.rak.filter((r) => Math.abs(r.z - z) < 0.01).sort((a, b) => a.x - b.x);
}

export function rencanaKegiatan(tata: TataLetak): RencanaKegiatan {
  const j = jalurGudang(tata);
  const terpakai = new Set<number>();
  const hasil: RencanaKegiatan = {
    tangga: null, catat: null, pindai: null, forklift: null, handTruck: null, lorongTerpakai: terpakai,
  };
  if (!tata.rak.length) return hasil;

  // Lorong di ANTARA dua baris rak lebih dulu (indeks 1..baris-1), lalu tepi.
  const urut = [
    ...Array.from({ length: Math.max(0, tata.baris - 1) }, (_, i) => i + 1),
    0, tata.baris,
  ].filter((v, i, a) => a.indexOf(v) === i && v >= 0 && v < j.lorongZ.length);

  // Lorong 1: tangga (rak di sisi -z lorong) + pencatat (rak di sisi +z)
  const l1 = urut[0];
  if (l1 != null) {
    const zc = j.lorongZ[l1];
    const depan = rakDiBaris(tata, zc - stepZ / 2); // rak di sisi -z, mukanya menghadap +z
    const belakang = rakDiBaris(tata, zc + stepZ / 2);
    const rakT = depan[0] ?? belakang[0];
    if (rakT) {
      const arah: 1 | -1 = depan[0] ? 1 : -1;
      hasil.tangga = { x: rakT.x - rakT.lebar / 4, zMuka: rakT.z + arah * rakT.dalam / 2, arah };
    }
    const rakC = (arah1(depan, belakang));
    if (rakC) {
      const arah: 1 | -1 = rakC.z < zc ? 1 : -1;
      hasil.catat = { x: rakC.x + rakC.lebar / 4, zMuka: rakC.z + arah * rakC.dalam / 2, arah };
    }
    terpakai.add(l1);
  }

  // Lorong 2: forklift menaruh pallet ke slot kosong + pemindai
  const l2 = urut[1];
  if (l2 != null) {
    const zc = j.lorongZ[l2];
    const kandidat = [...rakDiBaris(tata, zc + stepZ / 2), ...rakDiBaris(tata, zc - stepZ / 2)];
    // slot kosong teratas: rak yang isinya belum penuh tiga tingkat
    const kosong = kandidat.find((r) => r.slots.length <= UKURAN.slotPerTingkat * (UKURAN.tingkat - 1))
      ?? kandidat.find((r) => r.slots.length < UKURAN.slotPerTingkat * UKURAN.tingkat);
    if (kosong) {
      const tingkat = Math.min(UKURAN.tingkat - 1, Math.floor(kosong.slots.length / UKURAN.slotPerTingkat) + (kosong.slots.length % UKURAN.slotPerTingkat ? 1 : 0));
      const kolom = kosong.slots.length % UKURAN.slotPerTingkat === 0
        ? 0 : UKURAN.slotPerTingkat - 1;
      const xSlot = kosong.x + (kolom - (UKURAN.slotPerTingkat - 1) / 2) * UKURAN.slotW;
      const arah: 1 | -1 = kosong.z < zc ? 1 : -1;
      hasil.forklift = {
        x: xSlot, zMuka: kosong.z + arah * kosong.dalam / 2, arah,
        ySlot: tingkat * UKURAN.slotH + UKURAN.papan + 0.125,
      };
      const lain = kandidat.find((r) => r !== kosong && Math.abs(r.x - kosong.x) > 2) ?? null;
      if (lain) {
        const a2: 1 | -1 = lain.z < zc ? 1 : -1;
        hasil.pindai = {
          x0: lain.x - lain.lebar / 2 + 0.6, x1: lain.x + lain.lebar / 2 - 0.6,
          zMuka: lain.z + a2 * lain.dalam / 2, arah: a2,
        };
      }
    }
    terpakai.add(l2);
  }

  // hand truck: koridor depan, di antara area dock dan lorong pertama
  const z0 = j.lorongZ[0] - 2.4;
  hasil.handTruck = { x0: j.koridorKiri + 1.5, x1: j.koridorKanan - 1.5, z: z0 };
  return hasil;
}

function arah1(depan: RakTwin[], belakang: RakTwin[]): RakTwin | undefined {
  // pencatat di ujung lain lorong supaya tidak berdiri di sebelah tangga
  return belakang[belakang.length - 1] ?? depan[depan.length - 1];
}

/* ------------------------------------------------------------------ */
/* Benda: tangga gudang, papan klip, pemindai                           */
/* ------------------------------------------------------------------ */

export const TANGGA = { platform: 1.75, sudut: (64 * Math.PI) / 180, lebar: 0.62, dalamPlatform: 0.55 };
const panjangKaki = TANGGA.platform / Math.tan(TANGGA.sudut);

type G = THREE.BufferGeometry;
let _benda: null | {
  rangka: G; anakTangga: G; roda: G; papanKlip: G; kertas: G; pemindai: G; laser: G;
  m: Record<"kuning" | "hitam" | "abu" | "klip" | "kertas" | "pemindai" | "laser", THREE.Material>;
} = null;

function benda() {
  if (_benda) return _benda;
  const kotak = (w: number, h: number, d: number, x: number, y: number, z: number, rx = 0): G => {
    const g = new THREE.BoxGeometry(w, h, d);
    if (rx) g.rotateX(rx);
    return g.translate(x, y, z);
  };
  const pipa = (a: THREE.Vector3, b: THREE.Vector3, r = 0.02): G => {
    const len = a.distanceTo(b);
    const g = new THREE.CylinderGeometry(r, r, len, 10);
    g.translate(0, len / 2, 0);
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize());
    g.applyQuaternion(q);
    return g.translate(a.x, a.y, a.z);
  };
  const P = TANGGA.platform, W = TANGGA.lebar / 2, Dp = TANGGA.dalamPlatform;
  const V = (x: number, y: number, z: number) => new THREE.Vector3(x, y, z);
  // Koordinat lokal: rak di sisi -z, platform z 0..Dp, anak tangga turun ke +z.
  const rangka: G[] = [];
  for (const sx of [-W, W]) {
    rangka.push(pipa(V(sx, 0.1, Dp + panjangKaki), V(sx, P, Dp), 0.025));       // ibu tangga
    rangka.push(pipa(V(sx, 0.1, 0.02), V(sx, P, 0.02), 0.025));                  // kaki belakang (sisi rak)
    rangka.push(pipa(V(sx, P, 0.02), V(sx, P + 1.0, 0.02), 0.02));               // pagar platform belakang
    rangka.push(pipa(V(sx, P, Dp), V(sx, P + 1.0, Dp), 0.02));                   // pagar platform depan
    rangka.push(pipa(V(sx, P + 1.0, 0.02), V(sx, P + 1.0, Dp), 0.02));           // pegangan atas
    rangka.push(pipa(V(sx, P + 0.5, 0.02), V(sx, P + 0.5, Dp), 0.015));          // pegangan tengah
    rangka.push(pipa(V(sx, P + 1.0, Dp), V(sx, 1.0, Dp + panjangKaki), 0.02));      // pegangan sejajar ibu tangga
    rangka.push(pipa(V(sx, 0.4, 0.02), V(sx, 0.4, Dp + panjangKaki * (1 - 0.4 / P)), 0.015)); // penguat bawah
  }
  rangka.push(pipa(V(-W, P + 1.0, 0.02), V(W, P + 1.0, 0.02), 0.02));             // palang pagar belakang
  rangka.push(pipa(V(-W, 0.4, 0.02), V(W, 0.4, 0.02), 0.015));
  const anak: G[] = [];
  anak.push(kotak(TANGGA.lebar, 0.035, Dp, 0, P, Dp / 2));                        // platform
  const n = 7;
  for (let i = 1; i < n; i++) {
    const y = (P * i) / n;
    const z = Dp + panjangKaki * (1 - y / P);
    anak.push(kotak(TANGGA.lebar - 0.04, 0.03, 0.2, 0, y, z - 0.05));
  }
  const roda: G[] = [];
  for (const sx of [-W, W]) for (const z of [0.02, Dp + panjangKaki]) {
    const g = new THREE.CylinderGeometry(0.06, 0.06, 0.04, 14); g.rotateZ(Math.PI / 2); roda.push(g.translate(sx, 0.06, z));
  }
  const satukan = (a: G[]) => {
    const rata = a.map((x) => { const y = x.index ? x.toNonIndexed() : x; for (const k of Object.keys(y.attributes)) if (!["position", "normal", "uv"].includes(k)) y.deleteAttribute(k); return y; });
    const g = mergeGeometries(rata, false)!; a.forEach((x) => x.dispose()); return g;
  };
  const laser = new THREE.CylinderGeometry(0.004, 0.004, 1, 6); laser.rotateX(Math.PI / 2); laser.translate(0, 0, 0.5);
  _benda = {
    rangka: satukan(rangka), anakTangga: satukan(anak), roda: satukan(roda),
    papanKlip: new THREE.BoxGeometry(0.23, 0.32, 0.012),
    kertas: new THREE.BoxGeometry(0.2, 0.26, 0.004).translate(0, -0.015, 0.008),
    pemindai: satukan([kotak(0.05, 0.13, 0.04, 0, -0.04, 0), kotak(0.07, 0.05, 0.12, 0, 0.03, 0.04)]),
    laser,
    m: {
      kuning: new THREE.MeshStandardMaterial({ color: "#f2b01e", roughness: 0.45, metalness: 0.35 }),
      hitam: new THREE.MeshStandardMaterial({ color: "#23272f", roughness: 0.85 }),
      abu: new THREE.MeshStandardMaterial({ color: "#9aa3b2", roughness: 0.4, metalness: 0.8 }),
      klip: new THREE.MeshStandardMaterial({ color: "#6b4a2b", roughness: 0.7 }),
      kertas: new THREE.MeshStandardMaterial({ color: "#f8f8f2", roughness: 0.95 }),
      pemindai: new THREE.MeshStandardMaterial({ color: "#2b2f38", roughness: 0.5 }),
      laser: new THREE.MeshBasicMaterial({ color: "#ff2a2a", transparent: true, opacity: 0.85 }),
    },
  };
  return _benda;
}

function TanggaGudang() {
  const b = benda();
  return (
    <group>
      <mesh geometry={b.rangka} material={b.m.kuning} castShadow receiveShadow />
      <mesh geometry={b.anakTangga} material={b.m.hitam} castShadow receiveShadow />
      <mesh geometry={b.roda} material={b.m.hitam} />
    </group>
  );
}

function papanKlip(): THREE.Group {
  const b = benda();
  const g = new THREE.Group();
  const p = new THREE.Mesh(b.papanKlip, b.m.klip); p.castShadow = true;
  g.add(p, new THREE.Mesh(b.kertas, b.m.kertas));
  return g;
}

/* ------------------------------------------------------------------ */
/* Pekerja-pekerja yang berkegiatan                                    */
/* ------------------------------------------------------------------ */

const smooth = (t: number) => t * t * (3 - 2 * t);

/** Naik tangga, memeriksa kardus di rak atas, turun, mencatat sebentar. */
function PekerjaTangga({ x, zMuka, arah, jalan, varian }: { x: number; zMuka: number; arah: 1 | -1; jalan: boolean; varian: number }) {
  const m = useManusia(varian);
  const jam = useRef(varian * 3.1);
  const klip = useMemo(() => papanKlip(), []);
  useEffect(() => tempelKeTulang(m, "LeftHand", klip, [0.02, 0.1, 0.05], [0.3, 0, 1.4]), [m, klip]);
  // siklus 26 dtk: diam 3 | naik 4 | periksa 11 | turun 4 | catat 4
  const P = TANGGA.platform, Dp = TANGGA.dalamPlatform;
  useFrame((_, dt) => {
    const d = Math.min(dt, 0.1);
    if (jalan) jam.current += d;
    const t = jam.current % 26;
    let y = 0, z = Dp + panjangKaki + 0.35, klipAktif: "diam" | "jalan" | "kerja" = "diam", catat = false, skala = 1;
    if (t < 3) { klipAktif = "diam"; }
    else if (t < 7) { const f = smooth((t - 3) / 4); y = P * f; z = Dp + panjangKaki * (1 - f) + 0.35 * (1 - f) + 0.25 * f; klipAktif = "jalan"; skala = 0.7; }
    else if (t < 18) { y = P; z = 0.25; klipAktif = "diam"; catat = true; }
    else if (t < 22) { const f = smooth((t - 18) / 4); y = P * (1 - f); z = 0.25 + (Dp + panjangKaki + 0.1) * f; klipAktif = "jalan"; skala = -0.7; }
    else { z = Dp + panjangKaki + 0.35; klipAktif = "diam"; catat = true; }
    m.main(klipAktif);
    if (m.aksi.jalan) m.aksi.jalan.timeScale = skala;
    // posisi lokal tangga -> dunia (tangga diputar menurut arah rak)
    m.aktor.position.set(x, y + 0.02, zMuka + arah * z);
    m.aktor.rotation.y = arah === 1 ? Math.PI : 0;
    klip.visible = catat;
    if (jalan) m.mixer.update(d);
  });
  return (
    <group>
      <group position={[x, 0, zMuka + arah * 0.02]} rotation={[0, arah === 1 ? 0 : Math.PI, 0]}>
        <TanggaGudang />
      </group>
      <primitive object={m.aktor} />
    </group>
  );
}

/**
 * Memeriksa kardus di rak paling bawah: berlutut (klip "Working" model),
 * berdiri mencatat di papan klip, lalu pindah ke slot berikutnya.
 */
function PekerjaCatat({ x, zMuka, arah, jalan, varian }: { x: number; zMuka: number; arah: 1 | -1; jalan: boolean; varian: number }) {
  const m = useManusia(varian);
  const jam = useRef(varian * 1.7);
  const klip = useMemo(() => papanKlip(), []);
  useEffect(() => tempelKeTulang(m, "LeftHand", klip, [0.02, 0.1, 0.05], [0.3, 0, 1.4]), [m, klip]);
  useFrame((_, dt) => {
    const d = Math.min(dt, 0.1);
    if (jalan) jam.current += d;
    const t = jam.current % 22;
    // periksa 5 | catat 3 | geser 2 | periksa 5 | catat 3 | kembali 2  (detik)
    const fase = t < 5 ? "periksa" : t < 8 ? "catat" : t < 10 ? "maju" : t < 15 ? "periksa" : t < 18 ? "catat" : t < 20 ? "mundur" : "catat";
    const geser = t < 8 ? 0 : t < 10 ? smooth((t - 8) / 2) : t < 18 ? 1 : t < 20 ? 1 - smooth((t - 18) / 2) : 0;
    m.main(fase === "periksa" ? "kerja" : fase === "catat" ? "diam" : "jalan");
    m.aktor.position.set(x + geser * 1.2, 0, zMuka + arah * 0.75);
    m.aktor.rotation.y = fase === "maju" ? Math.PI / 2 : fase === "mundur" ? -Math.PI / 2 : arah === 1 ? Math.PI : 0;
    klip.visible = fase !== "periksa";
    if (jalan) m.mixer.update(d);
  });
  return <primitive object={m.aktor} />;
}

/** Memindai barcode tiap slot sepanjang muka rak; laser merah berkedip. */
function PekerjaPindai({ x0, x1, zMuka, arah, jalan, varian }: { x0: number; x1: number; zMuka: number; arah: 1 | -1; jalan: boolean; varian: number }) {
  const m = useManusia(varian);
  const jam = useRef(varian * 2.3);
  const b = benda();
  const { alat, sinar } = useMemo(() => {
    const g = new THREE.Group();
    const badan = new THREE.Mesh(b.pemindai, b.m.pemindai);
    const s = new THREE.Mesh(b.laser, b.m.laser);
    s.position.set(0, 0.03, 0.1);
    s.scale.set(1, 1, 0.9);
    g.add(badan, s);
    return { alat: g, sinar: s };
  }, [b]);
  useEffect(() => tempelKeTulang(m, "RightHand", alat, [0.0, 0.08, 0.04], [-1.2, 0, 0]), [m, alat]);
  const titik = useMemo(() => {
    const n = Math.max(2, Math.round((x1 - x0) / UKURAN.slotW) + 1);
    return Array.from({ length: n }, (_, i) => x0 + ((x1 - x0) * i) / (n - 1));
  }, [x0, x1]);
  useFrame((_, dt) => {
    const d = Math.min(dt, 0.1);
    if (jalan) jam.current += d;
    // tiap titik: pindai 2,5 dtk lalu jalan 1,5 dtk; bolak-balik
    const per = 4, n = titik.length, siklus = per * (2 * n - 2);
    const t = jam.current % siklus;
    const k = Math.floor(t / per), f = (t % per) / per;
    const iA = k < n ? k : 2 * n - 2 - k;
    const iB = k < n - 1 ? k + 1 : k >= n - 1 ? 2 * n - 3 - k : k;
    const pindai = f < 0.62;
    const g = pindai ? 0 : smooth((f - 0.62) / 0.38);
    const xx = titik[iA] + (titik[Math.max(0, Math.min(n - 1, iB))] - titik[iA]) * g;
    m.main(pindai ? "diam" : "jalan");
    m.aktor.position.set(xx, 0, zMuka + arah * 0.7);
    const kanan = titik[Math.max(0, Math.min(n - 1, iB))] > titik[iA];
    m.aktor.rotation.y = pindai ? (arah === 1 ? Math.PI : 0) : kanan ? Math.PI / 2 : -Math.PI / 2;
    sinar.visible = pindai && Math.sin(jam.current * 22) > -0.2;
    alat.visible = true;
    if (jalan) m.mixer.update(d);
  });
  return <primitive object={m.aktor} />;
}

/** Mendorong hand truck berisi kardus di koridor depan, bolak-balik. */
function PekerjaHandTruck({ x0, x1, z, jalan, varian }: { x0: number; x1: number; z: number; jalan: boolean; varian: number }) {
  const m = useManusia(varian);
  const jam = useRef(varian * 5);
  const ikut = useRef<THREE.Group>(null);
  const V = 0.9, jeda = 3;
  useFrame((_, dt) => {
    const d = Math.min(dt, 0.1);
    if (jalan) jam.current += d;
    const L = x1 - x0, lintas = L / V, siklus = 2 * (lintas + jeda);
    const t = jam.current % siklus;
    let x: number, maju: boolean, diam = false;
    if (t < lintas) { x = x0 + t * V; maju = true; }
    else if (t < lintas + jeda) { x = x1; maju = true; diam = true; }
    else if (t < 2 * lintas + jeda) { x = x1 - (t - lintas - jeda) * V; maju = false; }
    else { x = x0; maju = false; diam = true; }
    const rot = maju ? Math.PI / 2 : -Math.PI / 2;
    m.main(diam ? "diam" : "jalan");
    if (m.aksi.jalan) m.aksi.jalan.timeScale = V * 0.72 * 1.4;
    m.aktor.position.set(x, 0, z);
    m.aktor.rotation.y = rot;
    if (ikut.current) {
      ikut.current.position.set(x + (maju ? 0.75 : -0.75), 0, z);
      ikut.current.rotation.y = rot;
    }
    if (jalan) m.mixer.update(d);
  });
  return (
    <group>
      <primitive object={m.aktor} />
      <group ref={ikut}>
        {/* dimiringkan ke arah pendorong, seperti hand truck yang sedang didorong */}
        <group rotation={[-0.42, Math.PI, 0]}>
          <AsetAman>
            <ModelGLB url={URL_ASET.handTruck} fit={{ tinggi: 1.25 }} />
          </AsetAman>
          <AsetAman>
            {[0, 1, 2].map((i) => (
              <ModelGLB key={i} url={URL_ASET.kardus} fit={{ lebar: 0.42 }} position={[0, 0.1 + i * 0.3, -0.18]} rotation={[0, i * 0.15, 0]} />
            ))}
          </AsetAman>
        </group>
      </group>
    </group>
  );
}

/** Forklift menghadap rak, mengangkat pallet ke slot kosong, lalu mundur. */
function ForkliftKeRak({ x, zMuka, arah, ySlot, jalan }: { x: number; zMuka: number; arah: 1 | -1; ySlot: number; jalan: boolean }) {
  const grup = useRef<THREE.Group>(null);
  const garpu = useRef<THREE.Group>(null);
  const muatan = useRef<THREE.Group>(null);
  const lampu = useRef<THREE.Mesh>(null);
  const tiang = useRef<THREE.Group>(null);
  const diRak = useRef<THREE.Group>(null);
  const jam = useRef(0);
  // pusat pallet berada 1,42 m di depan pusat forklift (lihat BadanForklift)
  const zTaruh = zMuka - arah * 0.5 + arah * 1.42;   // pusat forklift saat pallet tepat di slot
  // lorong hanya 2,6 m: forklift cukup mundur sedikit sebelum menurunkan garpu
  const zMundur = zTaruh + arah * 0.55;
  const naikMaks = ySlot + 0.06 - 0.2 - 0.045;        // tinggi garpu supaya pallet sedikit di atas dek
  useFrame((_, dt) => {
    const d = Math.min(dt, 0.1);
    if (jalan) jam.current += d;
    const t = jam.current % 24;
    // 0-3 diam | 3-7 angkat | 7-10 maju | 10-11.5 turunkan | 11.5-14 mundur | 14-17 turun | 17-24 tunggu lalu ulang (pallet "diambil" kembali)
    let z = zMundur, h = 0, bawa = true, diSlot = false;
    if (t < 3) { h = 0; }
    else if (t < 7) { h = naikMaks * smooth((t - 3) / 4); }
    else if (t < 10) { h = naikMaks; z = zMundur + (zTaruh - zMundur) * smooth((t - 7) / 3); }
    else if (t < 11.5) { h = naikMaks - 0.08 * smooth((t - 10) / 1.5); z = zTaruh; }
    else if (t < 14) { h = naikMaks - 0.08; z = zTaruh + (zMundur - zTaruh) * smooth((t - 11.5) / 2.5); bawa = false; diSlot = true; }
    else if (t < 17) { h = (naikMaks - 0.08) * (1 - smooth((t - 14) / 3)); z = zMundur; bawa = false; diSlot = true; }
    else { h = 0; bawa = false; diSlot = t < 22; }
    if (grup.current) { grup.current.position.set(x, 0, z); grup.current.rotation.y = arah === 1 ? Math.PI : 0; }
    if (garpu.current) garpu.current.position.y = 0.2 + h;
    // tiang dalam ikut naik setelah garpu melewati puncak tiang luar
    if (tiang.current) tiang.current.position.y = Math.max(0, h - 1.55);
    if (muatan.current) muatan.current.visible = bawa;
    if (diRak.current) diRak.current.visible = diSlot;
    if (lampu.current) (lampu.current.material as THREE.MeshStandardMaterial).emissiveIntensity = 0.3 + 1.2 * (Math.sin(jam.current * 8) > 0 ? 1 : 0);
  });
  return (
    <group>
      <BadanForklift grup={grup} garpu={garpu} muatan={muatan} lampu={lampu} tiangDalam={tiang} />
      <group ref={diRak} position={[x, ySlot, zMuka - arah * 0.5]} visible={false}>
        <AsetAman>
          <PaletBermuatan />
        </AsetAman>
      </group>
    </group>
  );
}

export default function KegiatanGudang({ tata, jalan }: { tata: TataLetak; jalan: boolean }) {
  const r = useMemo(() => rencanaKegiatan(tata), [tata]);
  useEffect(() => { (window as unknown as { __twinKegiatan?: unknown }).__twinKegiatan = r; }, [r]);
  return (
    <group>
      {r.tangga && <AsetAman><PekerjaTangga {...r.tangga} jalan={jalan} varian={0} /></AsetAman>}
      {r.catat && <AsetAman><PekerjaCatat {...r.catat} jalan={jalan} varian={1} /></AsetAman>}
      {r.pindai && <AsetAman><PekerjaPindai {...r.pindai} jalan={jalan} varian={2} /></AsetAman>}
      {r.handTruck && <AsetAman><PekerjaHandTruck {...r.handTruck} jalan={jalan} varian={3} /></AsetAman>}
      {r.forklift && <ForkliftKeRak {...r.forklift} jalan={jalan} />}
    </group>
  );
}
