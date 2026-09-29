# Dokumentasi Inventory System

Tiga dokumen, dan masing-masing punya pembaca yang berbeda. Yang pertama menjelaskan
**seluruh sistem**; dua sisanya membedah satu bagian sampai dalam.

| Berkas | Untuk siapa | Isinya |
|---|---|---|
| [`anatomi-sistem.html`](anatomi-sistem.html) | Pengembang, penerap, pemilik produk | Peta lapis sistem, perjalanan satu permintaan, alur tiga tahap, **seluruh modul satu per satu** (12 halaman + 5 modul tanpa halaman), enam mesin hitung, batas peran AI, banyak-penyewa, model data, permukaan API, seluruh ambang beserta sumbernya, glosarium. |
| [`anatomi-prakiraan-stok.html`](anatomi-prakiraan-stok.html) | Petugas gudang, perencana | Pembedahan halaman Prakiraan: empat kartu keputusan, glosarium istilah Inggris–Indonesia, cara tiap angka dihitung, contoh nyata, dan keadaan saat datanya belum cukup. |
| [`multi-tenant-penerapan.md`](multi-tenant-penerapan.md) | Operator basis data | Langkah penerapan fondasi banyak-penyewa yang harus dijalankan manual: cadangan, migrasi 024–028, pembuatan role aplikasi, dan jalan pulang bila diperlukan. |

## Cara membaca berkas HTML

Keduanya berkas tunggal tanpa proses build — buka langsung di peramban:

```bash
xdg-open docs/anatomi-sistem.html
```

Keduanya mengikuti tema terang/gelap peramban, memakai palet yang sama dengan
`frontend/app/globals.css`, dan seluruh diagramnya berupa SVG sebaris sehingga
tetap tajam saat diperbesar maupun dicetak.

## Aturan yang berlaku pada dokumen di sini

- **Kode yang benar, bukan dokumen.** Setiap angka, ambang, dan batas yang disebut
  dapat ditelusuri ke berkas yang namanya tercetak di sebelahnya. Bila keduanya
  berselisih, dokumen yang diperbaiki.
- **Yang *tidak* dikerjakan ikut ditulis.** Tiap bab modul memuat blok batas —
  apa yang sengaja tidak dihitung, tidak disimpulkan, atau tidak ditampilkan
  modul itu, beserta alasannya.
- **Ambang tanpa sumber tidak boleh masuk.** Setiap konstanta yang disebut harus
  menyertakan dari mana angkanya berasal.
