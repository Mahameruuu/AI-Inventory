# Kredit dan lisensi aset 3D

Semua aset di folder ini berlisensi **CC0 1.0 (domain publik)**: boleh dipakai, diubah, dan
dikomersialkan tanpa kewajiban atribusi. Kredit tetap dicantumkan sebagai itikad baik.

| Berkas | Sumber | Lisensi | Perubahan |
|---|---|---|---|
| `props/cardboard_box_01.glb` | [Poly Haven](https://polyhaven.com/a/cardboard_box_01) | CC0 | disederhanakan ~272 segitiga, tekstur WebP 512 px, meshopt |
| `props/Barrel_01.glb` | [Poly Haven](https://polyhaven.com/a/Barrel_01) | CC0 | idem |
| `props/plastic_crate_02.glb` | [Poly Haven](https://polyhaven.com/a/plastic_crate_02) | CC0 | idem |
| `props/wooden_crate_01.glb` | [Poly Haven](https://polyhaven.com/a/wooden_crate_01) | CC0 | idem |
| `props/hand_truck.glb` | [Poly Haven](https://polyhaven.com/a/hand_truck) | CC0 | idem |
| `props/korean_fire_extinguisher_01.glb` | [Poly Haven](https://polyhaven.com/a/korean_fire_extinguisher_01) | CC0 | idem |
| `props/concrete_road_barrier_02.glb` | [Poly Haven](https://polyhaven.com/a/concrete_road_barrier_02) | CC0 | idem |
| `props/steel_frame_shelves_01.glb` | [Poly Haven](https://polyhaven.com/a/steel_frame_shelves_01) | CC0 | idem (belum dipakai) |
| `kenney/delivery.glb` | [Kenney Car Kit](https://kenney.nl/assets/car-kit) | CC0 | node tidak digabung, tekstur WebP, meshopt |
| `worker/human.fbx`, `worker/*.png` | [Quaternius Animated Human](https://opengameart.org/content/animated-human-low-poly) | CC0 | tidak diubah |

Forklift, pallet kayu, rak baja, dan lantai beton dibuat secara prosedural di kode
(`components/warehouse-twin/forklift.tsx`, `aset.tsx`, `scene.tsx`). Tidak ada forklift CC0 yang
layak ditemukan; model GLB berlisensi dapat menggantikannya tanpa mengubah pengendali gerak.

Optimasi: `gltf-transform optimize --compress meshopt --texture-compress webp --texture-size 512`.
