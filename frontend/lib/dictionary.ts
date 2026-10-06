/**
 * Kamus dwibahasa / bilingual dictionary.
 *
 * SATU BERKAS, DUA BAHASA BERSEBELAHAN. Setiap kunci membawa pasangan
 * id/en pada baris yang sama, supaya terjemahan yang tertinggal langsung
 * kelihatan saat membaca -- bukan tersembunyi di berkas lain yang harus
 * dibandingkan berdampingan.
 *
 * ONE FILE, BOTH LANGUAGES SIDE BY SIDE. Every key carries its id/en pair on
 * the same line so a missing translation is visible while reading, instead of
 * hiding in a second file that has to be diffed.
 *
 * Kalimat yang disusun BACKEND (deskripsi temuan, alasan status reorder,
 * jawaban asisten) tidak ada di sini: sumbernya satu, dan menerjemahkannya di
 * layar akan membuat angka dan kalimat berasal dari dua tempat berbeda.
 * Sentences composed by the BACKEND are deliberately absent: they have a single
 * source of truth, and translating them on screen would split figure and
 * wording across two origins.
 */

export type Lang = "id" | "en";

type Entry = { id: string; en: string };

export const DICT: Record<string, Entry> = {
  /* ---------------- kerangka aplikasi / app shell ---------------- */
  "brand.name": { id: "Inventory AI", en: "Inventory AI" },
  "brand.tagline": {
    id: "Sistem Pendukung Keputusan Persediaan",
    en: "Inventory Decision Intelligence",
  },
  "shell.collapse": { id: "Ciutkan sidebar", en: "Collapse sidebar" },
  /* Laci navigasi layar sempit. Namanya "menu", bukan "sidebar": di ponsel
     benda itu tidak pernah berdiri di sisi mana pun, dan orang mencarinya
     dengan kata yang sudah dikenalnya dari aplikasi lain. */
  "shell.menu": { id: "Menu navigasi", en: "Navigation menu" },
  "shell.open_menu": { id: "Buka menu navigasi", en: "Open navigation menu" },
  "shell.close_menu": { id: "Tutup menu navigasi", en: "Close navigation menu" },
  "shell.expand": { id: "Bentangkan sidebar", en: "Expand sidebar" },
  "shell.theme": { id: "Ganti tema terang/gelap", en: "Toggle light and dark theme" },
  "shell.lang": { id: "Ganti bahasa", en: "Change language" },

  /* ---------------- masuk dan akun / sign-in and account ---------------- */
  "auth.sign_in": { id: "Masuk", en: "Sign in" },
  "auth.sign_up": { id: "Daftar", en: "Sign up" },
  "auth.sign_out": { id: "Keluar", en: "Sign out" },
  "auth.account_menu": { id: "Menu akun", en: "Account menu" },
  "auth.sign_out_title": { id: "Keluar dari akun ini?", en: "Sign out of this account?" },
  /* Menyebut AKIBATNYA, bukan sekadar "Anda yakin?". Yang perlu diketahui
     pembacanya adalah bahwa isian yang belum tersimpan ikut hilang -- itulah
     satu-satunya alasan pertanyaan ini pantas diajukan. */
  "auth.sign_out_confirm": {
    id: "Sesi ditutup dan Anda kembali ke halaman masuk. Isian yang belum disimpan akan hilang.",
    en: "Your session will end and you will return to the sign-in page. Any unsaved input will be lost.",
  },
  "auth.email": { id: "Email", en: "Email" },
  "auth.password": { id: "Kata sandi", en: "Password" },
  "auth.full_name": { id: "Nama lengkap", en: "Full name" },
  "auth.company_name": { id: "Nama perusahaan", en: "Company name" },
  "auth.welcome": { id: "Masuk ke akun Anda", en: "Sign in to your account" },
  "auth.welcome_sub": {
    id: "Gunakan email dan kata sandi yang diberikan admin perusahaan Anda.",
    en: "Use the email and password issued by your company admin.",
  },
  "auth.signup_title": { id: "Buat perusahaan baru", en: "Create a new company" },
  "auth.signup_sub": {
    id: "Anda menjadi pemilik akun dan dapat menambahkan anggota tim setelahnya.",
    en: "You become the account owner and can add team members afterwards.",
  },
  "auth.no_account": { id: "Belum punya perusahaan?", en: "No company yet?" },
  "auth.have_account": { id: "Sudah punya akun?", en: "Already have an account?" },
  "auth.password_hint": {
    id: "Minimal 10 karakter.",
    en: "At least 10 characters.",
  },
  "auth.working": { id: "Memproses…", en: "Working…" },
  "auth.checking": { id: "Memeriksa sesi…", en: "Checking your session…" },
  "auth.role.owner": { id: "Pemilik", en: "Owner" },
  "auth.role.admin": { id: "Admin", en: "Admin" },
  "auth.role.staff": { id: "Staf", en: "Staff" },
  "auth.role.viewer": { id: "Peninjau", en: "Viewer" },
  "auth.account": { id: "Akun", en: "Account" },

  /* ---------------- pengguna / users ---------------- */
  "us.title": { id: "Pengguna", en: "Users" },
  "us.desc": {
    id: "Siapa saja yang dapat masuk ke perusahaan ini, dan sebatas apa haknya.",
    en: "Who can sign in to this company, and how far their access reaches.",
  },
  "us.list": { id: "Daftar pengguna", en: "User list" },
  "us.list_sub": {
    id: "Menonaktifkan pengguna langsung memutus sesinya di semua perangkat.",
    en: "Deactivating a user immediately ends their session on every device.",
  },
  "us.add": { id: "Tambah pengguna", en: "Add user" },
  "us.add_sub": {
    id: "Kata sandi awal Anda sampaikan sendiri kepada yang bersangkutan.",
    en: "You hand the initial password to the person yourself.",
  },
  "us.name": { id: "Nama", en: "Name" },
  "us.role": { id: "Peran", en: "Role" },
  "us.status": { id: "Status", en: "Status" },
  "us.last_login": { id: "Terakhir masuk", en: "Last sign-in" },
  "us.never": { id: "Belum pernah", en: "Never" },
  "us.active": { id: "Aktif", en: "Active" },
  "us.inactive": { id: "Nonaktif", en: "Inactive" },
  "us.activate": { id: "Aktifkan", en: "Activate" },
  "us.deactivate": { id: "Nonaktifkan", en: "Deactivate" },
  "us.save": { id: "Simpan", en: "Save" },
  "us.created": { id: "Pengguna dibuat.", en: "User created." },
  "us.updated": { id: "Perubahan tersimpan.", en: "Changes saved." },
  "us.you": { id: "Anda", en: "You" },
  "us.owner_locked": {
    id: "Pemilik akun tidak dapat diubah dari sini.",
    en: "The account owner cannot be changed from here.",
  },
  /* ---------------- data induk / master data ---------------- */
  "md.list": { id: "Daftar", en: "List" },
  "md.search": { id: "Cari…", en: "Search…" },
  "md.empty": { id: "Belum ada data. Tambahkan lewat tombol tambah di atas.", en: "Nothing here yet. Add one with the add button above." },
  "md.item_add": { id: "Tambah Barang", en: "Add item" },
  "md.wh_add": { id: "Tambah Gudang", en: "Add warehouse" },
  "md.add": { id: "Tambah Baru", en: "Add new" },
  "md.add_sub": { id: "Kolom yang dikosongkan tidak akan diisi.", en: "Fields left blank stay empty." },
  "md.edit": { id: "Ubah", en: "Edit" },
  "md.edit_title": { id: "Ubah Data", en: "Edit record" },
  "md.edit_sub": { id: "Kolom yang dikosongkan dibiarkan seperti semula.", en: "Fields left blank keep their current value." },
  "md.save": { id: "Simpan", en: "Save" },
  "md.saving": { id: "Menyimpan…", en: "Saving…" },
  "md.cancel": { id: "Batal", en: "Cancel" },
  "md.actions": { id: "Tindakan", en: "Actions" },
  "md.active": { id: "Aktif", en: "Active" },
  "md.inactive": { id: "Nonaktif", en: "Inactive" },
  "md.activate": { id: "Aktifkan", en: "Activate" },
  "md.deactivate": { id: "Nonaktifkan", en: "Deactivate" },
  "md.delete": { id: "Hapus", en: "Delete" },
  "md.delete_title": { id: "Hapus data ini?", en: "Delete this record?" },
  /* Kalimatnya menyebut NAMANYA dan menyebut bahwa tindakannya permanen.
     Dialog yang hanya berbunyi "Anda yakin?" tidak memberi pembacanya satu pun
     bahan untuk menjawab. */
  "md.delete_confirm": {
    id: "'{nama}' akan dihapus permanen dan tidak dapat dikembalikan.",
    en: "'{nama}' will be permanently deleted and cannot be restored.",
  },
  "md.created": { id: "Data ditambahkan.", en: "Record added." },
  "md.updated": { id: "Perubahan tersimpan.", en: "Changes saved." },
  "md.deleted": { id: "Data dihapus.", en: "Record deleted." },
  "md.used_by": { id: "Dipakai", en: "In use" },

  "md.name": { id: "Nama", en: "Name" },
  "md.code": { id: "Kode", en: "Code" },
  "md.description": { id: "Keterangan", en: "Description" },
  "md.location": { id: "Lokasi", en: "Location" },
  /* Koordinat dan waktu tempuh dipakai modul Transfer Antar Gudang untuk
     memeringkat gudang sumber. Petunjuknya menyebut AKIBAT mengosongkannya,
     bukan sekadar "opsional": gudang tanpa koordinat tetap dapat menjadi
     sumber, hanya komponen jaraknya dinilai netral -- dan itu keterangan yang
     mengubah apakah orang mengisinya atau tidak. */
  "md.latitude": { id: "Lintang", en: "Latitude" },
  "md.longitude": { id: "Bujur", en: "Longitude" },
  "md.coord_hint": {
    id: "Dipakai menghitung jarak antar gudang. Dikosongkan, gudang ini tetap dapat menjadi sumber transfer tetapi komponen jaraknya dinilai netral.",
    en: "Used to compute distance between warehouses. Left empty, this warehouse can still be a transfer source but its distance component scores neutral.",
  },
  "md.transfer_lead": { id: "Waktu tempuh (hari)", en: "Transit time (days)" },
  "md.transfer_lead_hint": {
    id: "Berapa hari kiriman biasanya sampai KE gudang ini.",
    en: "How many days a shipment usually takes to reach this warehouse.",
  },
  "md.phone": { id: "Telepon", en: "Phone" },
  "md.email": { id: "Email", en: "Email" },
  "md.address": { id: "Alamat", en: "Address" },
  "md.lead_time": { id: "Waktu Tunggu (hari)", en: "Lead time (days)" },
  "md.sku": { id: "SKU", en: "SKU" },
  "md.category": { id: "Kategori", en: "Category" },
  "md.unit": { id: "Satuan", en: "Unit" },
  "md.price": { id: "Harga Satuan", en: "Unit price" },
  "md.min_stock": { id: "Stok Minimum", en: "Minimum stock" },
  "md.max_stock": { id: "Stok Maksimum", en: "Maximum stock" },
  "md.reorder_point": { id: "Titik Pesan", en: "Reorder point" },
  "md.safety_stock": { id: "Stok Pengaman", en: "Safety stock" },
  "md.criticality": { id: "Kekritisan", en: "Criticality" },

  "md.cat_title": { id: "Kategori Barang", en: "Item categories" },
  "md.cat_desc": { id: "Pengelompokan barang. Dipakai untuk menyaring laporan dan analisis.", en: "How items are grouped. Used to filter reports and analysis." },
  "md.unit_title": { id: "Satuan Barang", en: "Units of measure" },
  "md.unit_desc": { id: "Satuan pengukuran barang, mis. PCS, BOX, LTR.", en: "Units items are measured in, e.g. PCS, BOX, LTR." },
  "md.wh_title": { id: "Gudang", en: "Warehouses" },
  "md.wh_desc": { id: "Tempat penyimpanan fisik. Setiap saldo stok melekat pada satu gudang.", en: "Physical storage locations. Every stock balance belongs to one warehouse." },
  "md.sup_title": { id: "Supplier", en: "Suppliers" },
  "md.sup_desc": { id: "Pemasok barang. Waktu tunggu di sini dipakai perhitungan pemesanan ulang.", en: "Goods suppliers. The lead time here feeds reorder calculations." },
  "md.item_title": { id: "Master Barang", en: "Item master" },
  "md.item_desc": { id: "Katalog barang beserta ambang perencanaannya.", en: "The item catalogue and its planning thresholds." },
  /* ---------------- impor / import ---------------- */
  "im.title": { id: "Impor Data Barang", en: "Import items" },
  "im.desc": { id: "Masukkan katalog barang dari berkas CSV atau Excel, tanpa mengetik ulang satu per satu.", en: "Load your item catalogue from a CSV or Excel file instead of typing it in." },
  "im.step1": { id: "1. Unduh berkas contoh", en: "1. Download the template" },
  "im.step1_sub": { id: "Berisi judul kolom yang dikenali beserta dua baris teladan.", en: "It carries the recognised column headings and two example rows." },
  "im.download": { id: "Unduh Contoh CSV", en: "Download CSV template" },
  "im.step2": { id: "2. Pilih berkas Anda", en: "2. Choose your file" },
  "im.step2_sub": { id: "CSV atau Excel (.xlsx). Nama kolom boleh berbahasa Indonesia atau Inggris.", en: "CSV or Excel (.xlsx). Column names may be in Indonesian or English." },
  "im.pick": { id: "Pilih berkas…", en: "Choose a file…" },
  "im.create_master": { id: "Buat kategori dan satuan yang belum terdaftar", en: "Create categories and units that do not exist yet" },
  "im.create_master_hint": { id: "Bila dimatikan, kategori yang belum terdaftar dilaporkan sebagai kesalahan — sehingga salah ketik tidak diam-diam menjadi kategori baru.", en: "When off, unknown categories are reported as errors, so a typo never quietly becomes a new category." },
  "im.step3": { id: "3. Periksa dulu", en: "3. Check first" },
  "im.check": { id: "Periksa Berkas", en: "Check file" },
  "im.checking": { id: "Memeriksa…", en: "Checking…" },
  "im.apply": { id: "Impor Sekarang", en: "Import now" },
  "im.applying": { id: "Mengimpor…", en: "Importing…" },
  "im.result": { id: "Hasil pemeriksaan", en: "Check result" },
  "im.result_done": { id: "Hasil impor", en: "Import result" },
  "im.read": { id: "Baris dibaca", en: "Rows read" },
  "im.will_create": { id: "Akan dibuat", en: "To create" },
  "im.will_update": { id: "Akan diperbarui", en: "To update" },
  "im.created": { id: "Dibuat", en: "Created" },
  "im.updated": { id: "Diperbarui", en: "Updated" },
  "im.problems": { id: "Bermasalah", en: "With problems" },
  "im.new_master": { id: "Master baru yang akan dibuat", en: "New master records to create" },
  "im.errors": { id: "Baris yang bermasalah", en: "Rows with problems" },
  "im.row": { id: "Baris", en: "Row" },
  "im.more_errors": { id: "…dan {n} baris bermasalah lainnya.", en: "…and {n} more problem rows." },
  "im.ready": { id: "Berkas siap diimpor.", en: "The file is ready to import." },
  "im.none_valid": { id: "Tidak ada satu baris pun yang dapat diimpor. Perbaiki berkasnya terlebih dahulu.", en: "No row can be imported. Fix the file first." },
  "im.partial": { id: "Baris yang sah tetap akan diimpor; baris bermasalah dilewati.", en: "Valid rows will still be imported; problem rows are skipped." },
  /* ---------------- transfer antar gudang / inter-warehouse transfer -------
     Kunci lama modul Transfer yang dihapus 31 Agustus 2026 ("tf.new",
     "tf.saved", "tf.list") DIBUANG di sini, bukan dibiarkan menumpuk: modul
     baru memakai awalan yang sama, dan dua kelompok kunci berawalan sama yang
     satunya sudah mati adalah cara paling mudah memakai kalimat yang salah
     tanpa ada yang menyadarinya.

     KALIMAT YANG MENYEBUT ANGKA TIDAK ADA DI SINI. Alasan pemilihan gudang,
     rincian skor, dan kalimat keputusan seluruhnya disusun backend bersama
     angkanya -- menerjemahkannya kembali di layar berarti membongkar kalimat
     jadi untuk mengambil angkanya. Lihat catatan di kepala berkas ini. */
  "tf.title": { id: "Transfer Antar Gudang", en: "Warehouse Transfers" },
  "tf.desc": {
    id: "Sebelum membeli, periksa dulu gudang sendiri: mesin mencari gudang yang benar-benar berlebih, memeringkatnya menurut kecukupan, jarak, dan waktu tempuh, lalu menyisakan hanya yang memang harus dibeli.",
    en: "Before buying, look in your own warehouses first: the engine finds the ones with genuine spare stock, ranks them by sufficiency, distance and transit time, and leaves only the true remainder to purchasing.",
  },

  "tf.screen.rekomendasi": { id: "Rekomendasi", en: "Recommendations" },
  "tf.screen.dokumen": { id: "Dokumen Transfer", en: "Transfer documents" },

  "tf.kpi.movable": { id: "Dapat dipindahkan", en: "Movable" },
  "tf.kpi.movable_hint": {
    id: "Tidak perlu dibeli; barangnya sudah dimiliki",
    en: "No purchase needed; the stock is already owned",
  },
  "tf.kpi.full": { id: "Tertutup penuh", en: "Fully covered" },
  "tf.kpi.full_hint": { id: "Cukup dari gudang sendiri", en: "Covered from own warehouses" },
  "tf.kpi.partial": { id: "Tertutup sebagian", en: "Partly covered" },
  "tf.kpi.partial_hint": {
    id: "Perlu transfer DAN pembelian",
    en: "Needs both a transfer and a purchase",
  },
  "tf.kpi.buy": { id: "Tetap harus dibeli", en: "Still to purchase" },
  "tf.kpi.buy_hint": { id: "{n} barang tanpa sumber transfer", en: "{n} items with no transfer source" },
  "tf.kpi.units": { id: "unit", en: "units" },

  "tf.tab.all": { id: "Semua", en: "All" },
  "tf.tab.full": { id: "Tertutup penuh", en: "Fully covered" },
  "tf.tab.partial": { id: "Sebagian", en: "Partial" },
  "tf.tab.buy": { id: "Harus dibeli", en: "Purchase" },

  /* --- kartu alur pengirim -> penerima (3 September 2026) ---------------
     Peran dicetak sebagai kata, bukan hanya diisyaratkan lewat posisi kiri dan
     kanan: separuh pembaca layar ini membukanya di tablet, tempat kedua blok
     bertumpuk dan "kiri/kanan" berhenti berarti apa pun. */
  "tf.role.sender": { id: "Pengirim", en: "Sender" },
  "tf.role.receiver": { id: "Penerima", en: "Receiver" },
  "tf.role.sender_none": { id: "Tidak ada gudang pengirim", en: "No sending warehouse" },
  "tf.role.sender_blocked": {
    id: "{n} gudang menyimpan barang ini, tetapi tidak satu pun boleh mengirim — lihat rincian.",
    en: "{n} warehouse(s) hold this item, but none may send — see details.",
  },
  "tf.role.sender_absent": {
    id: "Tidak ada gudang lain yang menyimpan barang ini.",
    en: "No other warehouse stocks this item.",
  },

  "tf.card.stock": { id: "Stok tersedia", en: "Available" },
  "tf.card.spare": { id: "Boleh diambil", en: "Spare" },
  "tf.card.need": { id: "Kebutuhan", en: "Needed" },
  "tf.card.more_sources": { id: "+{n} gudang pengirim lagi", en: "+{n} more sending warehouse(s)" },
  "tf.card.details": { id: "Rincian & {n} kandidat gudang", en: "Details & {n} candidate warehouses" },
  "tf.card.hide": { id: "Tutup rincian", en: "Hide details" },

  "tf.flow.shipped": { id: "dikirim", en: "to ship" },
  "tf.flow.nothing": { id: "tidak ada kiriman", en: "nothing to ship" },
  "tf.flow.score": { id: "skor {n}", en: "score {n}" },

  "tf.col.item": { id: "Barang", en: "Item" },
  "tf.col.from": { id: "Gudang asal", en: "From" },
  "tf.col.to": { id: "Gudang tujuan", en: "To" },
  "tf.col.source_stock": { id: "Stok asal", en: "Source stock" },
  "tf.col.need": { id: "Kebutuhan", en: "Needed" },
  "tf.col.distance": { id: "Jarak", en: "Distance" },
  "tf.col.score": { id: "Skor", en: "Score" },
  "tf.col.decision": { id: "Keputusan", en: "Decision" },
  "tf.col.qty": { id: "Qty transfer", en: "Transfer qty" },
  "tf.col.surplus": { id: "Surplus", en: "Spare" },
  "tf.col.plus_more": { id: "+{n} gudang lagi", en: "+{n} more" },

  "tf.detail.available": { id: "Stok tersedia", en: "Available stock" },
  "tf.detail.demand": { id: "Kebutuhan {n} hari", en: "{n}-day demand" },
  "tf.detail.need": { id: "Kekurangan", en: "Shortfall" },
  "tf.detail.need_basis": {
    id: "angka yang sama dengan halaman Pemesanan Ulang",
    en: "the same figure the Reorder page quotes",
  },
  "tf.detail.plan": { id: "Rencana kiriman", en: "Shipment plan" },
  "tf.detail.alternatives": { id: "Pilihan lain", en: "Other options" },
  "tf.detail.rejected": { id: "Tidak dipakai", en: "Not used" },

  "tf.dist.unknown": { id: "belum diketahui", en: "not known" },
  "tf.dist.straight": { id: "garis lurus", en: "straight line" },
  "tf.dist.straight_hint": {
    id: "Dihitung dari koordinat gudang. Isi jarak jalan darat pada master gudang bila ingin angka yang ditempuh.",
    en: "Computed from warehouse coordinates. Enter the road distance in the warehouse master for the figure trucks actually travel.",
  },

  "tf.score.breakdown": { id: "Rincian skor", en: "Score breakdown" },
  "tf.score.sufficiency": { id: "Kecukupan", en: "Sufficiency" },
  "tf.score.surplus_ratio": { id: "Kedalaman surplus", en: "Spare depth" },
  "tf.score.distance": { id: "Jarak", en: "Distance" },
  "tf.score.lead_time": { id: "Waktu tempuh", en: "Transit time" },

  "tf.fuzzy.badge": { id: "mirip {n}%", en: "{n}% match" },
  "tf.fuzzy.badge_hint": {
    id: "Nomor barangnya berbeda; kesamaannya ditebak dari nama. Periksa sebelum barang dikirim.",
    en: "The item numbers differ; sameness was inferred from the name. Check before anything ships.",
  },
  "tf.fuzzy.sends": { id: "Mengirim {sku} — {nama}", en: "Ships {sku} — {nama}" },

  "tf.filter.destination": { id: "Gudang tujuan", en: "Destination" },
  "tf.filter.all_warehouse": { id: "Semua gudang", en: "All warehouses" },
  "tf.filter.fuzzy": { id: "Pencocokan nama", en: "Name matching" },
  "tf.filter.fuzzy_label": { id: "Cocokkan barang serupa", en: "Match similar items" },
  "tf.filter.fuzzy_hint": {
    id: "Untuk barang yang sama tetapi terdaftar dua nomor. Nomor yang sudah pasti cocok tidak tersentuh.",
    en: "For one item registered under two numbers. Exact number matches are untouched.",
  },
  "tf.search": { id: "Cari SKU atau nama barang", en: "Search SKU or item name" },

  "tf.qty_none": { id: "belum dapat dihitung", en: "not yet computable" },
  "tf.qty_zero": { id: "tidak ada", en: "none" },

  "tf.route.items_unit": { id: "barang", en: "item(s)" },
  "tf.route.manifest": { id: "Barang yang dikirim ({n})", en: "Items in this shipment ({n})" },
  "tf.route.propose": { id: "Terapkan rekomendasi ({n} barang)", en: "Apply recommendation ({n} items)" },
  "tf.action.propose": { id: "Terapkan rekomendasi", en: "Apply recommendation" },
  "tf.action.propose_many": { id: "Terapkan {n} rekomendasi", en: "Apply {n} recommendations" },
  "tf.action.raised": { id: "Diajukan: {v}", en: "Proposed: {v}" },
  "tf.action.still_buy": {
    id: "Sisa {n} {unit} tetap harus dibeli",
    en: "The remaining {n} {unit} still needs purchasing",
  },

  "tf.empty": {
    id: "Tidak ada baris yang cocok dengan saringan ini.",
    en: "No rows match this filter.",
  },
  "tf.empty_none_short": {
    id: "Tidak ada gudang yang sedang kekurangan. Tidak ada yang perlu dipindahkan hari ini.",
    en: "No warehouse is short. Nothing needs moving today.",
  },
  "tf.truncated": {
    id: "Katalognya melebihi {n} pasangan barang/gudang, jadi daftar ini sebagian. Persempit dengan saringan gudang atau pencarian.",
    en: "The catalogue exceeds {n} item/warehouse pairs, so this list is partial. Narrow it with the warehouse filter or search.",
  },

  "tf.doc.title": { id: "Dokumen transfer", en: "Transfer documents" },
  "tf.doc.empty": {
    id: "Belum ada transfer yang diajukan. Ajukan dari tab Rekomendasi.",
    en: "No transfer has been proposed yet. Raise one from the Recommendations tab.",
  },
  "tf.doc.step.draft": { id: "Diajukan", en: "Proposed" },
  "tf.doc.step.approved": { id: "Disetujui", en: "Approved" },
  "tf.doc.step.in_transit": { id: "Dikirim", en: "Shipped" },
  "tf.doc.step.completed": { id: "Diterima", en: "Received" },
  "tf.doc.step.cancelled": { id: "Dibatalkan", en: "Cancelled" },

  "tf.doc.qty_hint": { id: "unit · {n} baris", en: "units · {n} line(s)" },
  "tf.doc.items": { id: "Barang yang dikirim ({n})", en: "Items shipped ({n})" },
  "tf.doc.lines_title": { id: "Isi kiriman", en: "Shipment contents" },
  "tf.doc.for_item": { id: "menutup kebutuhan {sku} — {nama}", en: "covers {sku} — {nama}" },

  "tf.doc.col.number": { id: "Nomor", en: "Number" },
  "tf.doc.col.route": { id: "Perpindahan", en: "Route" },
  "tf.doc.col.lines": { id: "Baris", en: "Lines" },
  "tf.doc.col.qty": { id: "Total qty", en: "Total qty" },
  "tf.doc.col.status": { id: "Status", en: "Status" },
  "tf.doc.col.action": { id: "Aksi", en: "Action" },
  /* Kata kerjanya menyebut TAHAP TUJUAN, bukan tahap sekarang: tombol pada
     dokumen berstatus "diajukan" berbunyi "Setujui", karena itulah yang akan
     terjadi bila ditekan. */
  "tf.doc.act.draft": { id: "Ajukan", en: "Propose" },
  "tf.doc.act.approve": { id: "Setujui", en: "Approve" },
  "tf.doc.act.ship": { id: "Kirim", en: "Ship" },
  "tf.doc.act.receive": { id: "Terima", en: "Receive" },
  "tf.doc.act.cancel": { id: "Batalkan", en: "Cancel" },

  /* ---- peta rute / route map ----
     KALIMATNYA MENYEBUT APA YANG TERGAMBAR, bukan apa yang dapat diklik.
     "Klik garis untuk melihat rincian" adalah petunjuk memakai aplikasi;
     "tujuh rute di antara empat gudang" adalah keterangan isi, dan yang kedua
     tetap berguna bagi orang yang sudah tahu cara mengkliknya. */
  "tf.map.title": { id: "Peta transfer antar gudang", en: "Inter-warehouse transfer map" },
  "tf.map.subtitle": {
    id: "{g} gudang berkoordinat · {r} rute pada halaman ini",
    en: "{g} located warehouses · {r} routes on this page",
  },
  "tf.map.reset": { id: "Tampilkan semua", en: "Show all" },
  "tf.map.zoom_in": { id: "Perbesar", en: "Zoom in" },
  "tf.map.zoom_out": { id: "Perkecil", en: "Zoom out" },
  "tf.map.wheel_hint": {
    id: "Tahan Ctrl sambil menggulir untuk memperbesar peta",
    en: "Hold Ctrl while scrolling to zoom the map",
  },
  "tf.map.loading": { id: "Menyiapkan peta…", en: "Preparing the map…" },
  /* Bukan "peta tidak tersedia": yang kurang adalah koordinat gudangnya, dan
     kalimat ini menyebut tempat memperbaikinya. */
  "tf.map.no_coords": {
    id: "Belum ada gudang yang punya koordinat, jadi tidak ada yang dapat digambar. Isi lintang dan bujurnya pada Master Gudang.",
    en: "No warehouse has coordinates yet, so there is nothing to draw. Fill in latitude and longitude under Warehouses.",
  },
  "tf.map.no_routes": {
    id: "Tidak ada transfer pada halaman ini; peta hanya menampilkan gudangnya.",
    en: "No transfer on this page; the map shows the warehouses only.",
  },
  "tf.map.missing": {
    id: "{d} transfer tidak digambar karena {g} gudang belum punya koordinat. Letak gudang tidak ditebak; isikan lintang dan bujurnya pada Master Gudang.",
    en: "{d} transfer(s) are not drawn because {g} warehouse(s) have no coordinates. Locations are never guessed; fill in latitude and longitude under Warehouses.",
  },
  "tf.map.road_fallback": {
    id: "Sebagian rute digambar sebagai garis perkiraan karena data jalan belum dapat diambil.",
    en: "Some routes are drawn as approximate lines because road data could not be fetched.",
  },
  "tf.map.paths": { id: "Pilihan jalur ({n})", en: "Route options ({n})" },
  "tf.map.path_fastest": { id: "Tercepat", en: "Fastest" },
  "tf.map.path_shortest": { id: "Terpendek", en: "Shortest" },
  "tf.map.path_both": { id: "Tercepat & terpendek", en: "Fastest & shortest" },
  "tf.map.path_via": { id: "via {v}", en: "via {v}" },
  "tf.map.path_alt": { id: "Alternatif", en: "Alternative" },
  "tf.map.unit_h": { id: "j", en: "h" },
  "tf.map.unit_min": { id: "mnt", en: "min" },
  "tf.map.ai_rec": { id: "Rekomendasi AI", en: "AI recommendation" },
  "tf.map.ai_rec_pick": { id: "Pilih jalur {n}", en: "Take route {n}" },
  "tf.map.ai_badge": { id: "Disarankan", en: "Suggested" },
  "tf.map.toll_km": { id: "{n} km tol", en: "{n} km toll" },
  "tf.map.cost_fuel": { id: "Solar ", en: "Diesel " },
  "tf.map.cost_toll": { id: "Tol ", en: "Toll " },
  "tf.map.cost_total": { id: "Total ", en: "Total " },
  "tf.map.why.single": {
    id: "Hanya satu jalur yang tersedia, jadi tidak ada pembanding.",
    en: "Only one route is available, so there is nothing to compare.",
  },
  "tf.map.why.fast_cheap": {
    id: "Tercepat sekaligus total biaya terendah: lebih hemat {h} dan {rp} dibanding jalur lain.",
    en: "Fastest and lowest total cost: saves {h} and {rp} versus the other route.",
  },
  "tf.map.why.fast": {
    id: "Tercepat. Total biayanya {rp} lebih mahal dari yang termurah, tetapi selisih waktunya sepadan.",
    en: "Fastest. Total cost is {rp} above the cheapest, but the time saved is worth it.",
  },
  "tf.map.why.cheap": {
    id: "Lebih lama {h} dari yang tercepat, tetapi menghemat {rp} setelah waktu ikut dihitung. Selisih waktunya tidak sepadan dengan biayanya.",
    en: "{h} slower than the fastest, but saves {rp} once time is priced in. The time saved would not justify the cost.",
  },
  "tf.map.why.toll": {
    id: "Ruas tolnya tidak paling sedikit; biaya tol sudah masuk hitungan.",
    en: "Its toll stretch is not the shortest; toll cost is already counted.",
  },
  "tf.map.why.ferry": {
    id: "Melewati penyeberangan feri; tarif feri belum termasuk dalam estimasi.",
    en: "Crosses a ferry; the ferry fare is not included in the estimate.",
  },
  "tf.map.assume": {
    id: "Asumsi truk box (tol Gol. {gol}): {kml} km/liter, solar {solar}/liter, tol rata-rata {tol}/km, biaya operasional {jam}/jam. Perkiraan, bukan tarif resmi.",
    en: "Box-truck assumptions (toll class {gol}): {kml} km/L, diesel {solar}/L, average toll {tol}/km, operating cost {jam}/h. Estimates, not official rates.",
  },
  "tf.map.path_note": {
    id: "Lama tempuh adalah perkiraan jalan lengang, tanpa lalu lintas langsung; ruas tol dikenali dari nama ruasnya sehingga bisa kurang dari sebenarnya. Pilihan jalur hanya mengubah tampilan peta; penilaian keamanan jalur belum tersedia.",
    en: "Travel time assumes free-flowing roads, without live traffic; toll stretches are recognised by road name and may be under-counted. Choosing a route only changes the map view; route safety ratings are not available.",
  },
  "tf.map.track": { id: "Tahap pengiriman", en: "Shipment progress" },
  "tf.map.warehouse": { id: "Gudang", en: "Warehouse" },
  "tf.map.route": { id: "Rute transfer", en: "Transfer route" },
  "tf.map.wh_items": { id: "Jenis barang", en: "Item types" },
  "tf.map.wh_stock": { id: "Total stok", en: "Total stock" },
  "tf.map.wh_out": { id: "Mengirim", en: "Sending" },
  "tf.map.wh_in": { id: "Menerima", en: "Receiving" },
  "tf.map.wh_traffic": { id: "{n} dok · {q} unit", en: "{n} doc · {q} units" },
  "tf.map.wh_coord": { id: "Koordinat", en: "Coordinates" },
  "tf.map.docs_on_route": { id: "Dokumen pada rute ini ({n})", en: "Documents on this route ({n})" },

  /* ---- lapisan usulan mesin / machine suggestion layer ----
     KATANYA "USULAN", BUKAN "TRANSFER". Yang digambar lapisan ini belum
     menggerakkan satu unit pun dan belum disetujui siapa pun; menamainya
     dengan kata yang sama seperti dokumen yang sedang berjalan adalah cara
     paling mudah membuat orang gudang mengira barangnya sudah berangkat. */
  "tf.map.ai_layer": { id: "Usulan mesin ({n})", en: "Engine suggestions ({n})" },
  "tf.map.ai_legend": { id: "Usulan mesin", en: "Engine suggestion" },
  "tf.map.ai_title": { id: "Usulan mesin", en: "Engine suggestion" },
  "tf.map.ai_hint": {
    id: "Belum diajukan dan belum menggerakkan stok. Ajukan dari kartu Rekomendasi di bawah peta.",
    en: "Not yet raised and no stock has moved. Raise it from the recommendation cards below the map.",
  },
  "tf.map.ai_items": { id: "{n} barang", en: "{n} item(s)" },
  "tf.map.ai_others": { id: "Gudang lain yang ditimbang ({n})", en: "Other warehouses weighed ({n})" },

  "tf.doc.on_map": { id: "Lihat di peta", en: "Show on map" },
  "tf.doc.selected": { id: "Sedang disorot di peta", en: "Highlighted on the map" },

  "adj.title": { id: "Penyesuaian Stok", en: "Stock adjustments" },
  "adj.desc": { id: "Menyelaraskan catatan sistem dengan hasil pencacahan fisik. Yang dimasukkan adalah hasil hitungan, bukan selisihnya.", en: "Reconcile the recorded balance with a physical count. You enter the counted quantity, not the difference." },
  "adj.new": { id: "Pencacahan Baru", en: "New count" },
  "adj.new_sub": { id: "Selisih dihitung sistem terhadap saldo saat dokumen disimpan.", en: "The difference is computed against the balance at the moment the document is saved." },
  "adj.list": { id: "Riwayat Penyesuaian", en: "Adjustment history" },
  "adj.reason": { id: "Alasan", en: "Reason" },
  "adj.reason_hint": { id: "mis. Stock opname bulanan", en: "e.g. Monthly stock count" },
  "adj.system": { id: "Menurut sistem", en: "Recorded" },
  "adj.actual": { id: "Hasil hitungan", en: "Counted" },
  "adj.difference": { id: "Selisih", en: "Difference" },
  "adj.changed": { id: "Berubah", en: "Changed" },
  "adj.saved": { id: "Penyesuaian {nomor} tercatat, {n} barang berubah.", en: "Adjustment {nomor} recorded, {n} items changed." },

  "tx.item": { id: "Barang", en: "Item" },
  "tx.qty": { id: "Jumlah", en: "Quantity" },
  "tx.add_line": { id: "Tambah Baris", en: "Add line" },
  "tx.save": { id: "Simpan", en: "Save" },
  "tx.saving": { id: "Menyimpan…", en: "Saving…" },
  "tx.notes": { id: "Catatan", en: "Notes" },
  "tx.date": { id: "Tanggal", en: "Date" },
  "tx.lines": { id: "Baris", en: "Lines" },
  "tx.warehouse": { id: "Gudang", en: "Warehouse" },
  "tx.choose_warehouse": { id: "Pilih gudang terlebih dahulu.", en: "Choose a warehouse first." },
  "us.forbidden": {
    id: "Hanya pemilik dan admin perusahaan yang dapat membuka halaman ini.",
    en: "Only the company owner and admins can open this page.",
  },
  "us.role.admin_help": {
    id: "Admin mengelola pengguna dan master data. Staf mencatat transaksi. Peninjau hanya membaca.",
    en: "Admins manage users and master data. Staff record transactions. Viewers only read.",
  },

  /* ---------------- navigasi / navigation ---------------- */
  /* Label bagian pertama sidebar. Kelompok satu-tautan dulu tidak punya judul
     sama sekali; sejak sidebar memakai label bagian, tautan tanpa label
     berdiri menggantung di atas tiga bagian yang berlabel. */
  "nav.section.main": { id: "Utama", en: "Main" },
  "nav.dashboard": { id: "Dasbor", en: "Dashboard" },
  "nav.inventory": { id: "Persediaan", en: "Inventory" },
  "nav.stock_overview": { id: "Ringkasan Stok", en: "Stock Overview" },
  "nav.items": { id: "Master Barang", en: "Items" },
  "nav.low_stock": { id: "Stok Menipis", en: "Low Stock" },
  "nav.warehouse": { id: "Gudang", en: "Warehouse" },
  "nav.warehouse_list": { id: "Daftar Gudang", en: "Warehouse List" },
  "nav.transactions": { id: "Transaksi", en: "Transactions" },
  "nav.receipt": { id: "Penerimaan Barang", en: "Stock Receipt" },
  "nav.issue": { id: "Pengeluaran Barang", en: "Stock Issue" },
  "nav.history": { id: "Riwayat Transaksi", en: "Transaction History" },
  "nav.purchase_orders": { id: "Pesanan Pembelian", en: "Purchase Orders" },
  "nav.ai": { id: "Kecerdasan AI", en: "AI Intelligence" },
  "nav.chat": { id: "Asisten AI", en: "AI Assistant" },
  "nav.forecasting": { id: "Prakiraan Permintaan", en: "Demand Forecasting" },
  "nav.reorder": { id: "Pemesanan Ulang", en: "Reorder" },
  "nav.lifetime": { id: "Analisis Umur Pakai", en: "Lifetime Analysis" },
  "nav.transfer": { id: "Transfer Antar Gudang", en: "Warehouse Transfers" },
  "nav.reports": { id: "Laporan", en: "Reports" },
  "nav.report_stock": { id: "Laporan Stok", en: "Stock Report" },
  "nav.report_receipts": { id: "Laporan Penerimaan", en: "Receipt Report" },
  "nav.report_issues": { id: "Laporan Pengeluaran", en: "Issue Report" },
  "nav.settings": { id: "Pengaturan", en: "Settings" },
  "nav.users": { id: "Pengguna", en: "Users" },
  "ro.cond.rop_strategy": {
    id: "Titik pesan — strategi {strategi}",
    en: "Reorder point — {strategi} strategy",
  },
  "ro.cond.rop_strategy_detail": {
    id: "dari simpangan permintaan & tingkat layanan; master: {master} {u}",
    en: "from demand deviation & service level; master: {master} {u}",
  },

  /* ---------------- strategi layanan & titik pesan ---------------- */
  "ro.strategy": { id: "Strategi", en: "Strategy" },

  /* ---------------- pemilihan & perlombaan model ---------------- */
  "fc.model": { id: "Model", en: "Model" },
  "fc.board.title": {
    id: "Perbandingan model — dipakai: {model}",
    en: "Model comparison — used: {model}",
  },
  "fc.board.sub": {
    id: "{n} model diadu pada riwayat barang ini, {lipatan} periode uji",
    en: "{n} models scored on this item's history, {lipatan} test periods",
  },
  "fc.board.model": { id: "Model", en: "Model" },
  "fc.board.error": { id: "Galat terskala", en: "Scaled error" },
  "fc.board.vs_naive": { id: "Terhadap tebakan naif", en: "Against naive guess" },
  "fc.board.winner": { id: "dipakai", en: "in use" },
  "fc.board.better": { id: "lebih baik", en: "better" },
  "fc.board.worse": { id: "lebih buruk", en: "worse" },
  "fc.board.note": {
    id: "Galat terskala (MASE) membandingkan model dengan tebakan “besok sama seperti hari ini”. Di bawah 1 berarti lebih baik daripada tebakan itu. Diukur dengan memotong riwayat pada beberapa titik, meramal ke depan, lalu membandingkannya dengan yang benar-benar terjadi.",
    en: "Scaled error (MASE) compares each model against the guess “tomorrow equals today”. Below 1 means better than that guess. Measured by cutting the history at several points, forecasting forward, then comparing with what actually happened.",
  },

  "nav.basic_data": { id: "Data Dasar", en: "Basic Data" },
  "nav.manual_input": { id: "Input Manual", en: "Manual Input" },
  "nav.master": { id: "Data Induk", en: "Master data" },
  "nav.md_items": { id: "Barang", en: "Items" },
  "nav.md_categories": { id: "Kategori", en: "Categories" },
  "nav.md_units": { id: "Satuan", en: "Units" },
  "nav.md_warehouses": { id: "Gudang", en: "Warehouses" },
  "nav.md_suppliers": { id: "Supplier", en: "Suppliers" },
  "nav.md_import": { id: "Impor Data", en: "Import data" },
  "nav.adjustments": { id: "Penyesuaian Stok", en: "Stock adjustments" },
  "nav.transfers": { id: "Transfer Gudang", en: "Warehouse transfers" },

  /* ---------------- umum / common ---------------- */
  "c.loading": { id: "Memuat…", en: "Loading…" },
  "c.saving": { id: "Menyimpan…", en: "Saving…" },
  "c.retry": { id: "Coba lagi", en: "Try again" },
  "c.recheck": { id: "Periksa ulang", en: "Re-check" },
  "c.close": { id: "Tutup", en: "Close" },
  "c.search": { id: "Cari", en: "Search" },
  "c.warehouse": { id: "Gudang", en: "Warehouse" },
  "c.all_warehouses": { id: "Semua gudang", en: "All warehouses" },
  "c.item": { id: "Barang", en: "Item" },
  "jenis.label": { id: "Jenis", en: "Type" },
  "tf.map.alt_paths": { id: "Jalur alternatif ({n})", en: "Alternative routes ({n})" },
  "tf.map.vehicle_rule": {
    id: "Kendaraan bergerak hanya pada dokumen Dikirim; Disetujui terparkir di gudang asal",
    en: "Vehicles move only on In transit documents; Approved ones are parked at the origin",
  },
  "rt.title": { id: "Rute terbaik (model ML)", en: "Best route (ML model)" },
  "rt.best": { id: "Direkomendasikan", en: "Recommended" },
  "rt.compare": { id: "Lihat {n} alternatif", en: "See {n} alternative(s)" },
  "rt.arrive": { id: "Tiba dalam", en: "Arrives in" },
  "rt.combined": {
    id: "Kiriman gabungan {n} barang, {q} unit: satu moda untuk seluruhnya; biaya dibagi menurut jumlah.",
    en: "Combined shipment of {n} items, {q} units: one mode for all; cost shared by quantity.",
  },
  "rt.why.single": {
    id: "Satu-satunya moda yang tersedia untuk pasangan gudang ini.",
    en: "The only mode available for this warehouse pair.",
  },
  "rt.why.late": {
    id: "Dipilih karena {m} melewati batas {d} hari (lebih lambat dari membeli baru).",
    en: "Chosen because {m} exceeds the {d}-day limit (slower than buying new).",
  },
  "rt.why.best": {
    id: "Skor tertinggi ({s}) dari {n} moda: menimbang waktu, biaya, jumlah yang sampai, dan jarak.",
    en: "Highest score ({s}) of {n} modes: weighing time, cost, units delivered, and distance.",
  },
  "rt.hide": { id: "Sembunyikan alternatif", en: "Hide alternatives" },
  "rt.loading": { id: "Menghitung rekomendasi rute...", en: "Computing route recommendation..." },
  "rt.none": { id: "Tidak ada moda angkut yang tersedia untuk pasangan gudang ini.", en: "No transport mode is available for this warehouse pair." },
  "rt.priority": { id: "Prioritas", en: "Priority" },
  "rt.p.seimbang": { id: "Seimbang", en: "Balanced" },
  "rt.p.tercepat": { id: "Tercepat", en: "Fastest" },
  "rt.p.termurah": { id: "Termurah", en: "Cheapest" },
  "rt.p.terpenuh": { id: "Paling utuh", en: "Most complete" },
  "rt.mode.darat": { id: "Darat (truk)", en: "Road (truck)" },
  "rt.mode.laut": { id: "Laut (kapal kargo)", en: "Sea (cargo ship)" },
  "rt.mode.udara": { id: "Udara (kargo)", en: "Air (cargo)" },
  "rt.badge.tercepat": { id: "Tercepat", en: "Fastest" },
  "rt.badge.termurah": { id: "Termurah", en: "Cheapest" },
  "rt.badge.terpenuh": { id: "Paling utuh", en: "Most complete" },
  "rt.badge.terdekat": { id: "Terdekat", en: "Shortest" },
  "rt.col.mode": { id: "Moda", en: "Mode" },
  "rt.col.distance": { id: "Jarak", en: "Distance" },
  "rt.col.days": { id: "Lama di jalan", en: "Transit time" },
  "rt.col.cost": { id: "Biaya angkut", en: "Freight cost" },
  "rt.col.received": { id: "Diterima", en: "Received" },
  "rt.col.score": { id: "Skor", en: "Score" },
  "rt.days": { id: "{n} hari", en: "{n} days" },
  "rt.of": { id: "{a} dari {b}", en: "{a} of {b}" },
  "rt.late": { id: "Lebih lambat dari batas {n} hari (pembelian baru)", en: "Slower than the {n}-day limit (a new purchase)" },
  "rt.loss": { id: "perkiraan kerugian barang {v}", en: "expected goods loss {v}" },
  "rt.model.ml": {
    id: "Model ML (gradient boosting) dilatih dari {n} pengiriman selesai, {dari} - {sampai}. Galat rata-rata: ±{h} hari, biaya ±{b}%, jumlah diterima ±{t} poin.",
    en: "ML model (gradient boosting) trained on {n} completed shipments, {dari} - {sampai}. Mean error: ±{h} days, cost ±{b}%, received ±{t} points.",
  },
  "rt.model.std": {
    id: "Riwayat pengiriman belum cukup ({n} dari {min}); perkiraan memakai tarif standar. Model ML aktif otomatis setelah riwayat mencukupi.",
    en: "Not enough shipment history ({n} of {min}); estimates use standard rates. The ML model turns on automatically once history is sufficient.",
  },
  "rt.picked": { id: "Moda dicatat pada dokumen: {m}", en: "Mode recorded on the document: {m}" },
  "tf.recv.title": { id: "Konfirmasi penerimaan", en: "Confirm receipt" },
  "tf.recv.hint": {
    id: "Hitung barang yang benar-benar sampai. Selisihnya dicatat rusak atau hilang di jalan.",
    en: "Count what actually arrived. The difference is recorded as damaged or lost in transit.",
  },
  "tf.recv.line": { id: "Diterima (dari {n} dikirim)", en: "Received (of {n} shipped)" },
  "tf.recv.short": {
    id: "Selisih {n} unit akan dicatat rusak/hilang di perjalanan.",
    en: "A difference of {n} unit(s) will be recorded as damaged/lost in transit.",
  },
  "tf.recv.over": { id: "Tidak boleh melebihi jumlah dikirim.", en: "Cannot exceed the shipped quantity." },
  "tf.recv.cost": { id: "Biaya angkut (Rp), boleh dikosongkan", en: "Freight cost (Rp), optional" },
  "tf.recv.cost_hint": {
    id: "Bila tagihan ekspedisi belum ada, isi nanti dari kartu dokumen.",
    en: "If the carrier's invoice has not arrived, fill it in later from the document card.",
  },
  "tf.recv.confirm": { id: "Konfirmasi diterima", en: "Confirm received" },
  "tf.recv.cancel": { id: "Batal", en: "Cancel" },
  "tf.cost.missing": { id: "Biaya angkut belum dicatat", en: "Freight cost not recorded" },
  "tf.cost.record": { id: "Catat biaya", en: "Record cost" },
  "tf.cost.edit": { id: "Ubah", en: "Edit" },
  "tf.cost.save": { id: "Simpan", en: "Save" },
  "tf.doc.mode": { id: "Moda", en: "Mode" },
  "tf.doc.cost": { id: "Biaya angkut", en: "Freight cost" },
  "tf.doc.promised": { id: "Janji", en: "Promised" },
  "tf.doc.actual": { id: "Aktual", en: "Actual" },
  "tf.doc.received_of": { id: "diterima {a} dari {b}", en: "received {a} of {b}" },
  "jenis.all": { id: "Semua jenis", en: "All types" },
  "jenis.berumur_pakai": { id: "Berumur pakai", en: "Service-life" },
  "jenis.habis_pakai": { id: "Habis pakai", en: "Consumable" },
  "jenis.hint.berumur_pakai": {
    id: "Diganti menurut umur pakai: dijadwalkan, bukan diprakirakan",
    en: "Replaced on a service-life schedule: scheduled, not forecast",
  },
  "jenis.hint.habis_pakai": {
    id: "Keluar rutin: diprakirakan dari riwayat pemakaian",
    en: "Used routinely: forecast from usage history",
  },
  "fc.na.title_umur": {
    id: "Barang ini dijadwalkan, bukan diprakirakan",
    en: "This item is scheduled, not forecast",
  },
  "fc.na.body_umur": {
    id: "Barang berumur pakai hanya keluar sekali dalam beberapa bulan atau tahun, jadi riwayat pemakaiannya tidak cukup rapat untuk diprakirakan. Yang pasti diketahui adalah umur pakainya; jadwal penggantiannya ada di bawah.",
    en: "Service-life items leave stock once every few months or years, so their usage history is too sparse to forecast. What is known for certain is the service life; the replacement schedule is below.",
  },
  "c.items_in_wh": { id: "{n} di gudang ini", en: "{n} in this warehouse" },
  "c.items_recent": { id: "{n} teraktif di gudang ini", en: "{n} most recent in this warehouse" },
  "c.items_group": { id: "{g} \u2014 {n} teraktif", en: "{g} \u2014 {n} most recent" },
  "c.no_items": { id: "Tidak ada barang", en: "No items" },
  "c.search_item": { id: "Cari barang", en: "Find item" },
  "c.sku_or_name": { id: "SKU atau nama…", en: "SKU or name…" },
  "c.status": { id: "Status", en: "Status" },
  "c.type": { id: "Jenis", en: "Type" },
  "c.qty": { id: "Jumlah", en: "Quantity" },
  "c.value": { id: "Nilai", en: "Value" },
  "c.stock": { id: "Stok", en: "Stock" },
  "c.available": { id: "Tersedia", en: "Available" },
  "c.reserved": { id: "Dipesan", en: "Reserved" },
  "c.threshold": { id: "Ambang", en: "Threshold" },
  "c.shortage": { id: "Kekurangan", en: "Shortage" },
  "c.unit_price": { id: "Harga satuan", en: "Unit price" },
  "c.date": { id: "Tanggal", en: "Date" },
  "c.time": { id: "Waktu", en: "Time" },
  "c.updated": { id: "Diperbarui", en: "Updated" },
  "c.document": { id: "Dokumen", en: "Document" },
  "c.batch": { id: "Batch", en: "Batch" },
  "c.number": { id: "Nomor", en: "Number" },
  "c.name": { id: "Nama", en: "Name" },
  "c.code": { id: "Kode", en: "Code" },
  "c.location": { id: "Lokasi", en: "Location" },
  "c.category": { id: "Kategori", en: "Category" },
  "c.supplier": { id: "Supplier", en: "Supplier" },
  "c.purpose": { id: "Keperluan", en: "Purpose" },
  "c.action": { id: "Aksi", en: "Action" },
  "c.detail": { id: "Detail", en: "Detail" },
  "c.back": { id: "Kembali", en: "Back" },
  "c.rows": { id: "Baris", en: "Lines" },
  "c.from": { id: "Dari", en: "From" },
  "c.to": { id: "Sampai", en: "To" },
  "c.period": { id: "Periode", en: "Period" },
  "c.days": { id: "{n} hari", en: "{n} days" },
  "c.active": { id: "Aktif", en: "Active" },
  "c.inactive": { id: "Nonaktif", en: "Inactive" },
  "c.safe": { id: "Aman", en: "Healthy" },
  "c.low": { id: "Menipis", en: "Low" },
  "c.criticality": { id: "Kritikalitas", en: "Criticality" },
  "c.select_warehouse": { id: "Pilih gudang…", en: "Select warehouse…" },
  "c.select_item": { id: "Pilih barang…", en: "Select item…" },
  "c.select_supplier": { id: "Pilih supplier…", en: "Select supplier…" },
  "c.add_row": { id: "Tambah baris", en: "Add line" },
  "c.remove_row": { id: "Hapus baris", en: "Remove line" },
  "c.optional": { id: "opsional", en: "optional" },
  "c.no_match": { id: "Tidak ada data yang cocok.", en: "Nothing matches this filter." },
  "c.value_basis": {
    id: "Harga referensi master barang",
    en: "Item master reference price",
  },
  "c.page_only": { id: "Halaman {page} dari {pages}", en: "Page {page} of {pages}" },
  "c.prev": { id: "Sebelumnya", en: "Previous" },
  "c.next": { id: "Berikutnya", en: "Next" },
  "c.movement_in": { id: "Masuk", en: "Inbound" },
  "c.movement_out": { id: "Keluar", en: "Outbound" },

  "err.title": { id: "Data belum tersedia.", en: "Data unavailable." },
  "err.hint": {
    id: "Periksa koneksi ke layanan backend, lalu muat ulang halaman ini.",
    en: "Check the backend connection, then reload this page.",
  },

  /* ---------------- dasbor / dashboard ----------------
     Dasbor menjawab tiga pertanyaan dan hanya tiga: bagaimana kondisinya
     sekarang, apa yang perlu ditangani, apa yang diprakirakan terjadi.
     Kunci untuk kartu Penerimaan/Pengeluaran/Pergerakan, gauge Kesiapan
     Operasional, dan tabel Transaksi Terakhir dicabut pada 2 September 2026:
     tak satu pun menjawab salah satu dari ketiganya, dan dua di antaranya
     mengulang angka yang sudah ada di halaman Transaksi. */
  "dash.title": { id: "Dasbor", en: "Dashboard" },
  "dash.desc": {
    id: "Kondisi persediaan seluruh gudang, dihitung dari data terkini.",
    en: "Inventory health across every warehouse, computed from live data.",
  },

  /* 1. Bagaimana kondisi sekarang */
  "dash.kpi.items": { id: "Total SKU", en: "Total SKUs" },
  "dash.kpi.items_hint": { id: "Barang aktif", en: "Active items" },
  "dash.kpi.stock": { id: "Total Stok", en: "Total Stock" },
  "dash.kpi.stock_hint": { id: "Unit di {n} gudang", en: "Units across {n} warehouses" },

  /* 2. Apa yang perlu perhatian */
  "dash.kpi.reorder": { id: "Perlu Pesan Ulang", en: "Need Reorder" },
  "dash.kpi.reorder_hint": { id: "Sudah menyentuh titik pesan", en: "At or below reorder point" },
  "dash.kpi.reorder_ok": { id: "Tidak ada", en: "None" },
  "dash.kpi.stockout": { id: "Risiko Kehabisan", en: "Stockout Risk" },
  "dash.kpi.stockout_hint": {
    id: "Habis sebelum kiriman tiba \u00b7 {n} prioritas tinggi",
    en: "Runs out before delivery arrives \u00b7 {n} high priority",
  },
  "dash.kpi.stockout_ok": { id: "Tidak ada", en: "None" },

  "dash.status": { id: "Status Persediaan", en: "Inventory Status" },
  "dash.status_sub": {
    id: "Menurut mesin pemesanan ulang, bukan hitungan tersendiri",
    en: "As classified by the reorder engine, not a separate calculation",
  },
  "dash.status.healthy": { id: "Aman", en: "Healthy" },
  "dash.status.reorder": { id: "Perlu pesan ulang", en: "Need reorder" },
  "dash.status.stockout": { id: "Risiko kehabisan", en: "Stockout risk" },

  "dash.by_warehouse": { id: "Stok per Gudang", en: "Stock by Warehouse" },
  "dash.by_warehouse_sub": {
    id: "Nilai memakai harga referensi master barang",
    en: "Valued at item master reference price",
  },

  "dash.attention": { id: "Perlu Perhatian", en: "Requiring Attention" },
  "dash.attention_sub": {
    id: "Barang paling mendesak, diurutkan mesin pemesanan ulang",
    en: "The most urgent items, ordered by the reorder engine",
  },
  "dash.attention_empty": {
    id: "Tidak ada barang yang menuntut tindakan hari ini.",
    en: "No item requires action today.",
  },
  "dash.attention_all": { id: "Buka Pemesanan Ulang", en: "Open Reorder" },

  /* 3. Apa yang diprakirakan terjadi */
  "dash.forecast": { id: "Kebutuhan {n} Hari ke Depan", en: "Demand Over the Next {n} Days" },
  "dash.forecast_sub": {
    id: "Periode bawaan pemesanan ulang; di halaman Pemesanan Ulang periodenya dapat diganti",
    en: "The default reorder period; it can be changed on the Reorder page",
  },
  "dash.forecast.usage": { id: "Prakiraan pemakaian", en: "Forecast usage" },
  "dash.forecast.qty": { id: "Disarankan dipesan", en: "Recommended to order" },
  /* Tenggatnya DISEBUT, dan itu bukan kosmetik: kartu "Risiko Kehabisan" di
     atas menjawab pertanyaan yang berbeda -- habis sebelum KIRIMAN tiba --
     sehingga kedua angka memang boleh berbeda. Dua label yang sama-sama
     berbunyi "habis" tanpa menyebut tenggatnya membuat selisih itu terbaca
     sebagai kesalahan. */
  "dash.forecast.stockout": { id: "Habis dalam {n} hari", en: "Runs out within {n} days" },
  "dash.forecast.unknown": {
    id: "{n} barang belum dapat diprakirakan karena riwayatnya belum cukup.",
    en: "{n} items cannot be forecast yet: their history is not sufficient.",
  },
  "dash.forecast_open": { id: "Buka Prakiraan", en: "Open Forecasting" },

  "dash.truncated": {
    id: "Katalog melebihi batas hitung, sehingga angka di atas dihitung atas sebagian barang saja.",
    en: "The catalogue exceeds the compute limit, so the figures above cover only part of it.",
  },
  "dash.empty_stock": { id: "Belum ada stok tercatat.", en: "No stock recorded yet." },
  "dash.units": { id: "unit", en: "units" },

  /* ---------------- ringkasan stok / stock overview ---------------- */
  "inv.title": { id: "Ringkasan Stok", en: "Stock Overview" },
  "inv.desc": {
    id: "Kondisi stok saat ini untuk setiap kombinasi barang dan gudang.",
    en: "Current stock for every item and warehouse combination.",
  },
  "inv.rows": { id: "Baris stok", en: "Stock lines" },
  "inv.rows_hint": { id: "Barang × gudang", en: "Item × warehouse" },
  "inv.total_qty": { id: "Total kuantitas", en: "Total quantity" },
  "inv.total_qty_hint": { id: "Sesuai filter aktif", en: "Matching the active filter" },
  "inv.value": { id: "Nilai persediaan", en: "Inventory value" },
  "inv.list": { id: "Daftar stok", en: "Stock list" },
  "inv.empty": {
    id: "Tidak ada stok yang cocok dengan filter.",
    en: "No stock matches this filter.",
  },
  "inv.rows_label": { id: "baris stok", en: "stock lines" },

  /* ---------------- master barang / items ---------------- */
  "items.title": { id: "Master Barang", en: "Items" },
  "items.desc": {
    id: "Satuan, harga referensi, ambang stok, dan total stok berjalan.",
    en: "Units, reference price, stock thresholds and running totals.",
  },
  "items.search": { id: "SKU atau nama barang…", en: "SKU or item name…" },
  "items.list": { id: "Daftar barang", en: "Item list" },
  "items.count": { id: "{n} barang", en: "{n} items" },
  "items.empty": { id: "Tidak ada barang yang cocok.", en: "No item matches." },
  "items.ref_price": { id: "Harga referensi", en: "Reference price" },
  "items.min": { id: "Min", en: "Min" },
  "items.reorder": { id: "Titik pesan", en: "Reorder" },
  "items.total_stock": { id: "Total stok", en: "Total stock" },
  "items.wh_count": { id: "{n} gudang", en: "{n} warehouses" },
  "items.label": { id: "barang", en: "items" },

  /* ---------------- stok menipis / low stock ---------------- */
  "low.title": { id: "Stok Menipis", en: "Low Stock" },
  "low.desc": {
    id: "Ambang yang dipakai adalah titik pesan ulang; bila belum diisi, dipakai stok minimum.",
    en: "The threshold is the reorder point; where unset, minimum stock is used.",
  },
  "low.headline": {
    id: "{n} baris stok berada pada atau di bawah ambang",
    en: "{n} stock lines sit at or below their threshold",
  },
  "low.note": {
    id: "Angka di bawah adalah data aktual. Keputusan pembelian tetap di tangan Anda — sebagian barang mungkin memang sengaja disimpan tipis.",
    en: "The figures below are actuals. The buying decision stays yours — some items are held thin on purpose.",
  },
  "low.none": {
    id: "Tidak ada barang yang menyentuh ambang pemesanan ulang.",
    en: "No item is touching its reorder threshold.",
  },
  "low.list": { id: "Daftar stok menipis", en: "Low stock list" },
  "low.empty": { id: "Semua stok masih di atas ambang.", en: "All stock is above threshold." },
  "low.level": { id: "Tingkat", en: "Severity" },
  "low.sev.habis": { id: "Habis", en: "Out of stock" },
  "low.sev.kritis": { id: "Kritis", en: "Critical" },
  "low.sev.menipis": { id: "Menipis", en: "Low" },

  /* ---------------- gudang / warehouses ---------------- */
  "wh.title": { id: "Daftar Gudang", en: "Warehouse List" },
  "wh.desc": {
    id: "Seluruh gudang beserta jumlah barang, kuantitas, dan nilai stok tersimpan.",
    en: "Every warehouse with its item count, quantity and stock value.",
  },
  "wh.search": { id: "Kode atau nama gudang…", en: "Warehouse code or name…" },
  "wh.list": { id: "Daftar gudang", en: "Warehouse list" },
  "wh.count": { id: "{n} gudang", en: "{n} warehouses" },
  "wh.empty": { id: "Tidak ada gudang yang cocok.", en: "No warehouse matches." },
  "wh.item_kinds": { id: "Jenis barang", en: "Item kinds" },
  "wh.total_stock": { id: "Total stok", en: "Total stock" },
  "wh.stock_value": { id: "Nilai stok", en: "Stock value" },
  "wh.label": { id: "gudang", en: "warehouses" },
  "wh.rows_here": { id: "Baris stok di gudang ini", en: "Stock lines in this warehouse" },
  "wh.all_units": { id: "Seluruh unit", en: "All units" },
  "wh.allocated": { id: "Sudah dialokasikan", en: "Already allocated" },
  "wh.stock_here": { id: "Stok di gudang ini", en: "Stock in this warehouse" },
  "wh.stock_here_sub": { id: "Maksimal 100 baris teratas", en: "Top 100 lines at most" },
  "wh.recent_moves": { id: "Pergerakan terakhir", en: "Recent movements" },
  "wh.recent_moves_sub": { id: "Sepuluh catatan terbaru", en: "Ten latest records" },
  "wh.empty_stock": { id: "Belum ada stok di gudang ini.", en: "No stock in this warehouse yet." },
  "wh.empty_moves": { id: "Belum ada pergerakan.", en: "No movement yet." },

  /* ---------------- riwayat transaksi / transaction history ---------------- */
  "tx.title": { id: "Riwayat Transaksi", en: "Transaction History" },
  "tx.desc": {
    id: "Seluruh pergerakan stok. Nilai positif menandakan barang masuk, negatif barang keluar.",
    en: "Every stock movement. Positive is inbound, negative is outbound.",
  },
  "tx.all_types": { id: "Semua jenis", en: "All types" },
  "tx.count": { id: "Jumlah pergerakan", en: "Movement count" },
  "tx.count_hint": { id: "Sesuai filter", en: "Matching the filter" },
  "tx.total_in": { id: "Total masuk", en: "Total inbound" },
  "tx.total_out": { id: "Total keluar", en: "Total outbound" },
  "tx.unit": { id: "Unit", en: "Units" },
  "tx.ledger": { id: "Buku besar pergerakan", en: "Movement ledger" },
  "tx.empty": { id: "Tidak ada pergerakan pada filter ini.", en: "No movement under this filter." },
  "tx.label": { id: "pergerakan", en: "movements" },
  "tx.price_note": {
    id: "Harga satuan kosong pada barang keluar karena penentuan harga pokok keluar adalah perhitungan valuasi yang belum menjadi lingkup sistem ini.",
    en: "Unit price is blank on outbound lines: costing an issue is a valuation calculation outside this system's scope.",
  },

  /* ---------------- penerimaan / stock receipt ---------------- */
  "rc.title": { id: "Penerimaan Barang", en: "Stock Receipt" },
  "rc.desc": {
    id: "Pencatatan barang masuk. Setiap penerimaan otomatis membuat catatan pergerakan dan menambah stok.",
    en: "Inbound recording. Every receipt writes a movement record and raises stock.",
  },
  "rc.add": { id: "Tambah Penerimaan", en: "Add receipt" },
  "rc.need": {
    id: "Isi gudang, pemasok, tanggal, dan minimal satu barang beserta jumlahnya.",
    en: "Fill in warehouse, supplier, date, and at least one item with a quantity.",
  },
  "tx.step_doc": { id: "1. Data dokumen", en: "1. Document details" },
  "tx.step_items": { id: "2. Daftar barang", en: "2. Items" },
  "tx.step_items_sub": {
    id: "Satu baris untuk satu barang. Tekan Tambah baris bila barangnya lebih dari satu.",
    en: "One line per item. Press Add line for more than one item.",
  },
  "rc.new_sub": {
    id: "Semua baris disimpan dalam satu transaksi",
    en: "All lines are saved in a single transaction",
  },
  "rc.received_date": { id: "Tanggal terima", en: "Received date" },
  "rc.reference": { id: "No. referensi", en: "Reference no." },
  "rc.save": { id: "Simpan penerimaan", en: "Save receipt" },
  "rc.history": { id: "Riwayat penerimaan", en: "Receipt history" },
  "rc.search": { id: "Cari nomor…", en: "Search number…" },
  "rc.empty": { id: "Belum ada penerimaan.", en: "No receipt yet." },
  "rc.saved": {
    id: "{no} tersimpan — {lines} baris, {qty} unit, {value}.",
    en: "{no} saved — {lines} lines, {qty} units, {value}.",
  },

  /* ---------------- pengeluaran / stock issue ---------------- */
  "is.title": { id: "Pengeluaran Barang", en: "Stock Issue" },
  "is.desc": {
    id: "Pencatatan barang keluar. Backend menolak pengeluaran yang melebihi stok tersedia.",
    en: "Outbound recording. The backend rejects any issue beyond available stock.",
  },
  "is.add": { id: "Tambah Pengeluaran", en: "Add issue" },
  "is.need": {
    id: "Isi gudang, tanggal, dan minimal satu barang beserta jumlahnya.",
    en: "Fill in warehouse, date, and at least one item with a quantity.",
  },
  "is.issue_date": { id: "Tanggal keluar", en: "Issue date" },
  "is.purpose_ph": { id: "Pemakaian produksi…", en: "Production consumption…" },
  "is.pick_wh_first": {
    id: "Pilih gudang lebih dulu; daftar barang dan stok tersedianya muncul setelah itu.",
    en: "Pick a warehouse first to see available stock.",
  },
  "is.over_stock": { id: "melebihi stok tersedia", en: "exceeds available stock" },
  "is.save": { id: "Simpan pengeluaran", en: "Save issue" },
  "is.history": { id: "Riwayat pengeluaran", en: "Issue history" },
  "is.search": { id: "Cari nomor / keperluan…", en: "Search number or purpose…" },
  "is.empty": { id: "Belum ada pengeluaran.", en: "No issue yet." },
  "is.saved": { id: "{no} tersimpan — {detail}.", en: "{no} saved — {detail}." },

  /* ---------------- laporan stok / stock report ---------------- */
  "rs.title": { id: "Laporan Stok", en: "Stock Report" },
  "rs.desc": {
    id: "Rekapitulasi stok berjalan, dihitung langsung dari tabel operasional tanpa tabel laporan terpisah.",
    en: "Running stock recap, computed straight from operational tables with no separate report table.",
  },
  "rs.low": { id: "Stok menipis", en: "Low stock" },
  "rs.low_hint": { id: "Di bawah ambang", en: "Below threshold" },
  "rs.by_warehouse": { id: "Nilai per gudang", en: "Value by warehouse" },
  "rs.by_category": { id: "Nilai per kategori", en: "Value by category" },
  "rs.breakdown": { id: "Rincian stok", en: "Stock breakdown" },
  "rs.breakdown_sub": {
    id: "Diurutkan dari nilai terbesar, maksimal 200 baris",
    en: "Ordered by value, 200 lines at most",
  },
  "rs.empty": { id: "Belum ada data.", en: "No data yet." },
  "rs.empty_stock": { id: "Belum ada stok.", en: "No stock yet." },
  "rs.qty_unit": { id: "Unit", en: "Units" },

  /* ---------------- laporan penerimaan / receipt report ---------------- */
  "rr.title": { id: "Laporan Penerimaan", en: "Receipt Report" },
  "rr.desc": {
    id: "Rekapitulasi barang masuk. Nilai memakai harga penerimaan sebenarnya, bukan harga master.",
    en: "Inbound recap. Valued at the actual receipt price, not the master price.",
  },
  "rr.docs": { id: "Dokumen", en: "Documents" },
  "rr.docs_hint": { id: "Penerimaan", en: "Receipts" },
  "rr.lines_hint": { id: "Total baris barang", en: "Total item lines" },
  "rr.qty_hint": { id: "Unit masuk", en: "Units inbound" },
  "rr.value_hint": { id: "Harga penerimaan", en: "Receipt price" },
  "rr.by_supplier": { id: "Per supplier", en: "By supplier" },
  "rr.by_date": { id: "Per tanggal", en: "By date" },
  "rr.by_item": { id: "Per barang", en: "By item" },
  "rr.by_item_sub": {
    id: "Lima puluh teratas berdasarkan nilai",
    en: "Top fifty by value",
  },
  "rr.qty_received": { id: "Qty diterima", en: "Qty received" },
  "rr.empty": { id: "Belum ada penerimaan.", en: "No receipt yet." },

  /* ---------------- laporan pengeluaran / issue report ---------------- */
  "ri.title": { id: "Laporan Pengeluaran", en: "Issue Report" },
  "ri.desc": {
    id: "Rekapitulasi barang keluar. Nilai rupiah tidak ditampilkan karena harga pokok keluar membutuhkan perhitungan valuasi.",
    en: "Outbound recap. Rupiah value is withheld: costing an issue requires a valuation calculation.",
  },
  "ri.docs_hint": { id: "Pengeluaran", en: "Issues" },
  "ri.qty_hint": { id: "Unit keluar", en: "Units outbound" },
  "ri.by_purpose": { id: "Per keperluan", en: "By purpose" },
  "ri.qty_issued": { id: "Qty keluar", en: "Qty issued" },
  "ri.by_item_sub": {
    id: "Lima puluh teratas berdasarkan kuantitas",
    en: "Top fifty by quantity",
  },
  "ri.empty": { id: "Belum ada pengeluaran.", en: "No issue yet." },

  /* ---------------- prakiraan / forecasting ---------------- */
  "fc.title": { id: "Prakiraan Permintaan", en: "Demand Forecasting" },
  "fc.desc": {
    id: "Prediksi kebutuhan dan proyeksi stok dari histori pergerakan persediaan.",
    en: "Demand prediction and stock projection from inventory movement history.",
  },
  "fc.pick": {
    id: "Pilih gudang dan barang untuk melihat prakiraan.",
    en: "Pick a warehouse and item to see the forecast.",
  },
  "fc.need.title": { id: "Prediksi Kebutuhan", en: "Demand Prediction" },
  "fc.need.note": {
    id: "Stok saat ini dibandingkan dengan perkiraan kebutuhan {n} hari ke depan. Seluruh angka mengikuti periode yang dipilih.",
    en: "Current stock compared with estimated demand for the next {n} days. Every figure follows the selected period.",
  },
  "fc.need.usage": { id: "Kebutuhan {n} hari", en: "{n}-day demand" },
  "fc.need.usage_detail": {
    id: "Total kebutuhan sepanjang periode yang dipilih",
    en: "Total demand across the selected period",
  },
  "fc.need.rate": { id: "Rata-rata pemakaian", en: "Average consumption" },
  "fc.need.per_day": { id: "{v} {u}/hari", en: "{v} {u}/day" },
  "fc.need.rate_detail": {
    id: "Rata-rata dari histori {n} hari",
    en: "Averaged over {n} days of history",
  },
  "fc.need.left": { id: "Perkiraan sisa stok", en: "Projected stock left" },
  "fc.need.left_detail": { id: "Di akhir periode {n} hari", en: "At the end of the {n}-day period" },
  "fc.need.stockout": { id: "Perkiraan stok habis", en: "Projected stockout" },
  "fc.need.days_pm": { id: "±{n} hari", en: "±{n} days" },
  "fc.need.stockout_detail": {
    id: "Dihitung dari hari ini pada laju pemakaian saat ini",
    en: "Counted from today at the current consumption rate",
  },
  "fc.need.stockout_beyond": { id: "> {n} hari", en: "> {n} days" },
  "fc.need.stockout_beyond_detail": {
    id: "Tidak habis di dalam periode {n} hari yang dipilih",
    en: "Does not run out within the selected {n}-day period",
  },
  "fc.need.stockout_idle_detail": {
    id: "Tanpa pemakaian tercatat, stok tidak diproyeksikan berkurang",
    en: "With no recorded consumption, stock is not projected to fall",
  },

  /* --- banner status prakiraan --- */
  "fc.banner.stockout": {
    id: "Stok diperkirakan habis dalam ±{n} hari",
    en: "Stock is projected to run out in ±{n} days",
  },
  "fc.banner.rop": {
    id: "Stok diperkirakan menyentuh titik pesan dalam ±{n} hari",
    en: "Stock is projected to reach the reorder point in ±{n} days",
  },
  "fc.banner.safe": {
    id: "Stok diperkirakan masih cukup sepanjang {n} hari ke depan",
    en: "Stock is projected to last through the next {n} days",
  },
  "fc.banner.idle": {
    id: "Belum ada pemakaian tercatat — stok diperkirakan tidak bergerak",
    en: "No consumption on record — stock is projected to stay flat",
  },
  "fc.banner.short": {
    id: "Stok tidak cukup untuk {n} hari ke depan — kurang {q}",
    en: "Stock will not cover the next {n} days — short by {q}",
  },
  "fc.banner.exact": {
    id: "Stok hanya pas untuk {n} hari ke depan — tidak ada sisa",
    en: "Stock only just covers the next {n} days — nothing left over",
  },
  "fc.banner.enough": {
    id: "Stok cukup untuk {n} hari ke depan — masih tersisa {q}",
    en: "Stock covers the next {n} days — {q} left over",
  },
  "fc.banner.none": {
    id: "Tidak ada pemakaian yang diperkirakan dalam {n} hari ke depan",
    en: "No consumption is expected in the next {n} days",
  },
  "fc.banner.runout": {
    id: "Stok diperkirakan habis pada {d} (hari ke-{h}).",
    en: "Stock is projected to run out on {d} (day {h}).",
  },
  "fc.banner.order_note": {
    id: "Angka ini selisih kebutuhan dan stok saja. Jumlah pesanan di halaman Pemesanan Ulang adalah kekurangan ini ditambah stok pengaman.",
    en: "This is only demand minus stock. The order quantity on the Reorder page is this shortfall plus safety stock.",
  },
  "fc.need.stock_detail": { id: "Yang tersedia di gudang hari ini", en: "Available in the warehouse today" },
  "fc.need.stock_reserved": {
    id: "Di rak {a}, sudah dicadangkan {b}",
    en: "{a} on the shelf, {b} already reserved",
  },
  "fc.need.short": { id: "Perlu ditambah", en: "Needs to be added" },
  "fc.need.math": { id: "Kebutuhan {a} − stok {b}", en: "Demand {a} − stock {b}" },
  "fc.need.left_after": { id: "Sisa stok setelah {n} hari", en: "Stock left after {n} days" },
  "fc.need.left_math": { id: "Stok {a} − kebutuhan {b}", en: "Stock {a} − demand {b}" },
  "fc.daily.title": { id: "Pemakaian per Hari", en: "Daily Usage" },
  "fc.daily.title_week": { id: "Pemakaian per Minggu", en: "Weekly Usage" },
  "fc.daily.note": {
    id: "Perkiraan jumlah yang terpakai tiap hari dan stok yang tersisa sesudahnya. Semua angka bilangan bulat; hari bertanda 0 berarti tidak ada pemakaian yang diperkirakan.",
    en: "Estimated quantity used each day and the stock left afterwards. Every figure is a whole number; a day showing 0 means no consumption is expected.",
  },
  "fc.daily.note_week": {
    id: "Periode di atas 14 hari diringkas per minggu: jumlah yang diperkirakan terpakai dan stok yang tersisa di akhir minggu itu. Semua angka bilangan bulat.",
    en: "Periods longer than 14 days are summarised by week: the quantity expected to be used and the stock left at the end of that week. Every figure is a whole number.",
  },
  "fc.daily.col_date": { id: "Tanggal", en: "Date" },
  "fc.daily.col_week": { id: "Minggu", en: "Week" },
  "fc.daily.col_usage": { id: "Perkiraan pemakaian ({u})", en: "Expected usage ({u})" },
  "fc.daily.col_left": { id: "Sisa stok ({u})", en: "Stock left ({u})" },
  "fc.daily.short": { id: "Kurang {q}", en: "Short {q}" },
  "fc.daily.empty": { id: "Habis", en: "Out" },
  "fc.daily.total": { id: "Total {n} hari", en: "{n}-day total" },
  "fc.banner.reorder_btn": { id: "Pesan ulang barang ini", en: "Reorder this item" },
  "fc.banner.stock": { id: "Stok saat ini", en: "Current stock" },
  "fc.banner.need": { id: "Perkiraan kebutuhan {n} hari", en: "{n}-day demand estimate" },
  "fc.banner.cta": { id: "Lihat saran pemesanan", en: "See the order suggestion" },
  "fc.proj.title": { id: "Proyeksi Stok", en: "Stock Projection" },
  "fc.proj.note": {
    id: "Garis penuh adalah stok aktual, garis putus-putus adalah proyeksi hasil prakiraan. Garis titik pesan hanya referensi visual — keputusan pemesanan ada di halaman Pemesanan Ulang.",
    en: "The solid line is actual stock, the dashed line is the forecast projection. The reorder line is visual reference only — the ordering decision lives on the Reorder page.",
  },
  "fc.proj.meta": {
    id: "Histori {n} hari · mutu data {q}",
    en: "{n} days of history · data quality {q}",
  },
  "fc.chart.actual": { id: "Stok historis", en: "Historical stock" },
  "fc.chart.forecast": { id: "Prakiraan", en: "Forecast" },
  "fc.chart.after_rop": { id: "Setelah titik pesan", en: "Past reorder point" },
  "fc.chart.today": { id: "Hari ini", en: "Today" },
  "fc.chart.rop_master": {
    id: "Titik pesan ulang master ({v})",
    en: "Master reorder point ({v})",
  },
  "fc.chart.actual_stock": { id: "Stok aktual", en: "Actual stock" },
  "fc.chart.forecast_stock": { id: "Prakiraan stok", en: "Forecast stock" },
  "fc.chart.rop_short": { id: "Titik pesan ulang (master)", en: "Reorder point (master)" },
  "fc.chart.demand_actual": { id: "Permintaan aktual", en: "Actual demand" },
  "fc.chart.demand_forecast": { id: "Ramalan", en: "Forecast" },
  "fc.chart.band": { id: "Rentang keyakinan", en: "Confidence band" },
  "fc.chart.days_left": { id: "±{n} hari lagi", en: "±{n} days away" },
  "fc.calc.title": { id: "Detail perhitungan", en: "Calculation detail" },
  "fc.calc.sub": {
    id: "Dari mana angka kartu di atas berasal. Seluruhnya bilangan bulat, sama seperti kartunya.",
    en: "Where the figures above come from. Whole numbers throughout, exactly as on the cards.",
  },
  "fc.calc.params": { id: "Parameter pengadaan (referensi)", en: "Procurement parameters (reference)" },
  "fc.calc.lead_time": { id: "Waktu tunggu kiriman", en: "Supplier lead time" },
  "fc.calc.safety": { id: "Stok pengaman", en: "Safety stock" },
  "fc.calc.params_note": {
    id: "Kedua angka ini berpatokan masa tunggu, bukan periode yang dipilih di atas, jadi mengganti periode tidak menggesernya. Keduanya ditampilkan sebagai sumber angka saja — keputusan pemesanan ada di halaman Pemesanan Ulang.",
    en: "Both figures are anchored to lead time rather than the period selected above, so changing the period does not move them. They appear here only as inputs — the ordering decision lives on the Reorder page.",
  },
  "fc.na.title": { id: "Prakiraan belum tersedia", en: "Forecast not available yet" },
  "fc.na.body": {
    id: "Histori transaksi belum cukup untuk menghasilkan prediksi yang dapat diandalkan.",
    en: "Transaction history is not yet long enough for a dependable prediction.",
  },
  "fc.na.available": { id: "Data tersedia", en: "History available" },
  "fc.na.minimum": { id: "Minimum data", en: "Minimum required" },
  "fc.na.outflow_days": { id: "Hari ada pengeluaran", en: "Days with outflow" },
  "fc.na.of_min": { id: "{a} dari minimum {b}", en: "{a} of {b} required" },
  "fc.na.current": { id: "Stok saat ini", en: "Current stock" },
  "fc.na.footer": {
    id: "Gunakan sistem lebih dahulu untuk mengumpulkan histori pergerakan stok. Prakiraan akan muncul sendiri begitu ambang di atas terpenuhi.",
    en: "Keep using the system to accumulate movement history. The forecast appears on its own once the thresholds above are met.",
  },
  "fc.life.title": { id: "Jadwal penggantian", en: "Replacement schedule" },
  "fc.life.body": {
    id: "Komponen yang diganti sekali dalam beberapa tahun tidak akan pernah punya cukup riwayat untuk diramal — satu penggantian tidak membentuk satu pun selang. Yang di bawah ini bukan ramalan, melainkan umur pakai yang tercatat pada master barang.",
    en: "A component replaced once every few years will never have enough history to forecast — a single replacement forms no interval at all. What follows is not a prediction but the service life recorded on the item master.",
  },
  "fc.life.note": {
    id: "Dari umur pakai yang tercatat pada master barang, bukan dari prakiraan. Keduanya menjawab pertanyaan yang berbeda: prakiraan menakar pemakaian, jadwal ini menakar usia.",
    en: "From the service life recorded on the item master, not from the forecast. They answer different questions: the forecast gauges usage, this schedule gauges age.",
  },
  "fc.life.service_life": { id: "Umur pakai", en: "Service life" },
  "fc.life.last": { id: "Penggantian terakhir", en: "Last replacement" },
  "fc.life.due": { id: "Jatuh tempo berikutnya", en: "Next due" },
  "fc.life.remaining": { id: "Sisa umur", en: "Remaining" },
  "fc.life.overdue": { id: "Terlewat {n} hari", en: "{n} days overdue" },
  "fc.life.never": { id: "Belum pernah tercatat", en: "Not recorded yet" },
  /* Kalimat ini diperbarui pada 2 September 2026. Bunyinya yang lama --
     "angka itu belum dicatat di sistem" -- menjadi TIDAK BENAR begitu
     OPERATING_HOURS_PER_DAY lahir di app/config.py dan tercetak di kepala
     halaman Analisis Umur Pakai. Halaman Prakiraan tetap TIDAK memakainya:
     memakainya berarti menerbitkan tanggal jatuh tempo baru pada layar yang
     sudah berjalan, atas asumsi yang belum diminta siapa pun untuk dipakai di
     sana. Yang berubah hanya kalimatnya, supaya jujur soal di mana angkanya
     sekarang berada. */
  "fc.life.hours_note": {
    id: "Tanggal jatuh tempo tidak dihitung untuk umur pakai bersatuan jam: mengubahnya menjadi tanggal menuntut jam operasi mesin per hari. Angka itu dipakai halaman Analisis Umur Pakai dan tercetak di sana, tetapi sengaja tidak dibawa ke halaman ini — prakiraan menakar pemakaian, bukan usia.",
    en: "No due date is derived for an hour-based service life: converting it to a date requires the machine's operating hours per day. That figure is used and printed on the Lifetime Analysis page, but is deliberately not carried over here — a forecast gauges usage, not age.",
  },

  /* ---------------- pemesanan ulang / reorder ---------------- */
  "po.title": { id: "Pesanan Pembelian", en: "Purchase Orders" },
  "po.desc": {
    id: "Pesanan yang belum menyentuh stok. Stok baru bertambah saat PO ditandai diterima, dan tindakan itulah yang menerbitkan penerimaan barang.",
    en: "Orders that have not touched stock. Stock only rises when a PO is marked received, and that action is what issues the goods receipt.",
  },
  "po.search": { id: "Cari nomor PO", en: "Search PO number" },
  "po.number": { id: "Nomor PO", en: "PO number" },
  "po.order_date": { id: "Tanggal pesan", en: "Order date" },
  "po.expected": { id: "Perkiraan datang", en: "Expected" },
  "po.value": { id: "Nilai", en: "Value" },
  "po.status": { id: "Status", en: "Status" },
  "po.status_all": { id: "Semua status", en: "All statuses" },
  "po.wh_all": { id: "Semua gudang", en: "All warehouses" },
  "po.action": { id: "Tindakan", en: "Action" },
  "po.lines": { id: "({n} baris)", en: "({n} lines)" },
  "po.empty": { id: "Belum ada pesanan pembelian.", en: "No purchase orders yet." },
  "po.st.draft": { id: "Draft", en: "Draft" },
  "po.st.sent": { id: "Dikirim", en: "Sent" },
  "po.st.received": { id: "Diterima", en: "Received" },
  "po.st.cancelled": { id: "Dibatalkan", en: "Cancelled" },
  "po.send": { id: "Kirim", en: "Send" },
  "po.cancel": { id: "Batalkan", en: "Cancel" },
  "po.receive": { id: "Terima", en: "Receive" },
  "po.busy": { id: "Memproses…", en: "Working…" },
  "po.pick_supplier": { id: "Pemasok", en: "Supplier" },
  "po.send_confirm": { id: "Konfirmasi kirim", en: "Confirm send" },
  "po.receive_confirm": { id: "Konfirmasi terima", en: "Confirm receipt" },
  "po.received_date": { id: "Tanggal terima", en: "Received date" },
  "po.reference": { id: "Nomor referensi", en: "Reference number" },
  "po.send_note": {
    id: "PO yang dikirim wajib punya pemasok — pemasok itu pula yang tercatat pada penerimaan barangnya nanti. Stok tidak berubah.",
    en: "A sent PO must have a supplier — the same one recorded on its goods receipt later. Stock does not change.",
  },
  "po.receive_note": {
    id: "Menerbitkan penerimaan barang dan MENAIKKAN STOK sebanyak yang dipesan. Tidak dapat dibatalkan; pengembalian barang adalah retur, bukan pembatalan.",
    en: "Issues a goods receipt and RAISES STOCK by the ordered amount. Cannot be undone; returning goods is a return, not a cancellation.",
  },
  "po.detail_open": { id: "Lihat rincian barang", en: "Show item lines" },
  "po.source": { id: "Asal", en: "Source" },
  "po.source_reorder": { id: "Panel Pemesanan Ulang", en: "Reorder panel" },
  "po.gr_title": {
    id: "Penerimaan barang yang lahir dari PO ini",
    en: "The goods receipt this PO produced",
  },
  "po.sent_ok": { id: "{no} ditandai dikirim.", en: "{no} marked as sent." },
  "po.cancelled_ok": { id: "{no} dibatalkan.", en: "{no} cancelled." },
  "po.received_ok": {
    id: "{no} diterima. Penerimaan {gr} terbit dan stok bertambah {qty}.",
    en: "{no} received. Goods receipt {gr} issued and stock rose by {qty}.",
  },
  "ro.title": { id: "Pemesanan Ulang", en: "Reorder" },
  "ro.desc": {
    id: "Kapan stok perlu dipesan dan berapa jumlahnya, berdasarkan lead time dan stok tersedia.",
    en: "When to order and how much, based on lead time and available stock.",
  },
  "ro.pick": {
    id: "Pilih gudang dan barang untuk melihat keputusan pemesanan.",
    en: "Pick a warehouse and item to see the ordering decision.",
  },
  "ro.norate.title": {
    id: "Laju pemakaian belum dapat dihitung",
    en: "Consumption rate cannot be computed yet",
  },
  "ro.norate.body": {
    id: "Histori pergerakan belum cukup, sehingga kebutuhan selama masa tunggu belum dapat diperkirakan.",
    en: "Movement history is too short to estimate demand during the lead time.",
  },
  "ro.norate.tail": {
    id: "Kondisi persediaan di bawah tetap berlaku; angka keputusan dan pengadaan menyusul begitu histori mencukupi.",
    en: "The inventory condition below still holds; decision and procurement figures follow once history suffices.",
  },
  "ro.cond.title": { id: "Kondisi Persediaan", en: "Inventory Condition" },
  "ro.cond.note": {
    id: "Stok saat ini dan parameter pada master barang. Tidak dipengaruhi periode prakiraan.",
    en: "Current stock and item master parameters. Unaffected by the forecast period.",
  },
  "ro.cond.available": { id: "Stok tersedia", en: "Available stock" },
  "ro.cond.available_split": {
    id: "Fisik {a} · tercadang {b} {u}",
    en: "Physical {a} · reserved {b} {u}",
  },
  "ro.cond.available_free": {
    id: "Seluruh stok fisik ({a} {u}) bebas dipakai",
    en: "All physical stock ({a} {u}) is free to use",
  },
  "ro.cond.below_min_badge": { id: "Di bawah minimum", en: "Below minimum" },
  "ro.cond.below_min_title": {
    id: "Stok tersedia berada di bawah stok minimum pada master barang ({v}).",
    en: "Available stock is below the minimum stock on the item master ({v}).",
  },
  "ro.cond.rop_master": { id: "Titik pesan ulang (master)", en: "Reorder point (master)" },
  "ro.cond.rop_master_detail": {
    id: "Ambang yang ditetapkan pada master barang",
    en: "Threshold set on the item master",
  },
  "ro.cond.lead": { id: "Lead time", en: "Lead time" },
  "ro.cond.lead_empty": { id: "Belum diisi", en: "Not set" },
  "ro.cond.lead_empty_detail": {
    id: "Master barang belum memuat waktu tunggu kiriman",
    en: "The item master carries no supplier lead time",
  },
  "ro.cond.lead_detail": {
    id: "Waktu tunggu kiriman dari pemasok",
    en: "Supplier delivery lead time",
  },
  "ro.cond.safety": { id: "Safety stock", en: "Safety stock" },
  "ro.dec.eff_rop": { id: "Titik pesan efektif", en: "Effective reorder point" },
  "ro.proc.lead_demand": { id: "Kebutuhan selama lead time", en: "Demand during lead time" },
  "ro.proc.fill_to": { id: "Diisi sampai", en: "Fill up to" },
  "ro.proc.order_qty": { id: "Jumlah yang perlu dipesan", en: "Quantity to order" },
  // Penerus blok "Titik pesan menurut strategi layanan" yang dihapus. Isinya
  // dipadatkan menjadi satu baris catatan di bawah safety stock: Z dan
  // simpangan permintaan adalah satu-satunya dua angka yang tidak diucapkan di
  // tempat lain, dan keduanya menjelaskan baris tepat di atasnya. Seluruh
  // sisanya -- permintaan harian, masa tunggu, titik pesan efektif -- sudah
  // berdiri sebagai baris tersendiri pada rangkaian hitung yang sama.
  "ro.proc.safety_from": {
    id: "Z {z} × simpangan permintaan {s} × √{lead} hari masa tunggu",
    en: "Z {z} × demand deviation {s} × √{lead} days lead time",
  },
  "ro.proc.no_lead": {
    id: "Masa tunggu barang ini belum diisi pada Data Dasar, sedangkan seluruh rantai di atas bertumpu padanya: permintaan dikali masa tunggu, dan safety stock dikali akar masa tunggu. Isi kolom waktu tunggu pada barang ini, lalu angkanya muncul dengan sendirinya.",
    en: "This item has no lead time recorded in Basic Data, and the whole chain above rests on it: demand times lead time, and safety stock times the square root of lead time. Fill in the item's lead time and the figures will appear on their own.",
  },
  "ro.proc.basis": { id: "Dasar perhitungan", en: "How it was derived" },
  "ro.panel.head_qty": { id: "{s} — {v}", en: "{s} — {v}" },
  "ro.panel.badge_reached": {
    id: "Titik pesan efektif terlampaui",
    en: "Effective reorder point reached",
  },
  "ro.panel.badge_eta": { id: "Menuju titik pesan: {v}", en: "To reorder point: {v}" },
  "ro.panel.cover": { id: "Estimasi habis", en: "Estimated depletion" },
  "ro.panel.pickups": { id: "±{n} pengambilan", en: "±{n} pickings" },
  "ro.panel.round_note": {
    id: "Jumlah pesanan dibulatkan ke atas dari selisih desimalnya, jadi dapat satu unit lebih besar daripada pengurangan angka bulat di atasnya.",
    en: "The order quantity is rounded up from the underlying decimals, so it may be one unit larger than subtracting the whole numbers above.",
  },
  // Kalimat penutup "Sarankan dinaikkan ke {e}" dihapus: tombol tepat di
  // sebelahnya sudah berbunyi "Update ke {e}", dan angka yang sama dua kali
  // dalam satu strip selebar satu baris membuat pembaca memeriksa apakah
  // keduanya sama alih-alih menekannya.
  "ro.panel.warn": {
    id: "Titik pesan master {m} berada di bawah kebutuhan masa tunggu + safety stock, jadi pemesanan akan selalu terpicu terlambat.",
    en: "The master reorder point {m} sits below lead time demand + safety stock, so ordering will always trigger late.",
  },
  // Tombol penyimpannya sudah dicabut, jadi warn_action / warn_busy /
  // warn_scope ikut dihapus. Yang menggantikannya kalimat penunjuk di bawah:
  // peringatan tanpa jalan keluar hanya akan muncul lagi di kunjungan
  // berikutnya, dan pembacanya tidak pernah tahu harus ke mana.
  "ro.panel.warn_where": {
    id: "Perbaiki titik pesan barang ini di Data Dasar → Barang; ambang master berlaku untuk seluruh gudang yang menyimpannya.",
    en: "Fix this item's reorder point in Basic Data → Items; the master threshold applies to every warehouse holding it.",
  },
  // Tanpa jumlah. Angkanya sudah berdiri di headline panel yang sama, beberapa
  // baris di atas tombol ini, dan sekali lagi pada dasar perhitungannya --
  // mengulangnya di label tombol membuat satu panel menyebut satu angka tiga
  // kali. Yang dipesan tetap tidak menjadi kejutan: nomor PO yang terbit
  // sesudahnya dicetak apa adanya, dan judul tombolnya menerangkan cakupannya.
  "ro.panel.make_po": { id: "Buat PO", en: "Create PO" },
  "ro.panel.po_busy": { id: "Membuat PO…", en: "Creating PO…" },
  "ro.panel.po_scope": {
    id: "Mencatat pesanan pembelian berstatus draft untuk gudang dan barang yang sedang dilihat. Stok TIDAK berubah — stok baru bertambah saat barangnya benar-benar diterima.",
    en: "Records a draft purchase order for the warehouse and item on screen. Stock does NOT change — it only rises when the goods are actually received.",
  },
  "ro.panel.po_done": {
    id: "PO {v} dibuat, berstatus draft. Stok belum berubah; pemasoknya diisi saat PO diterbitkan.",
    en: "PO {v} created as a draft. Stock is unchanged; the supplier is filled in when the PO is issued.",
  },
  "ro.proc.footer": {
    id: "Selama stok tersedia masih di atas titik pesan efektif, jumlahnya nol. Perkiraan kebutuhan periode pada halaman Prakiraan menjawab pertanyaan lain dan tidak pernah menjadi jumlah pesanan.",
    en: "While available stock stays above the effective reorder point, the quantity is zero. Period demand on the Forecasting page answers a different question and never becomes an order quantity.",
  },
  /* Label sumbu status. Statusnya sendiri berupa enum dari backend; yang
     diterjemahkan di layar hanya katanya, bukan keputusannya. Kunci warisan
     PANTAU/SEGERA_PESAN dipertahankan supaya jawaban lama tetap terlabeli. */
  "ro.status.AMAN": { id: "Stok aman", en: "Stock healthy" },
  "ro.status.PERLU_REORDER": { id: "Perlu reorder", en: "Needs reorder" },
  "ro.status.RISIKO_STOCKOUT": { id: "Risiko stockout", en: "Stockout risk" },
  "ro.status.PANTAU": { id: "Perlu dipantau", en: "Watch closely" },
  "ro.status.SEGERA_PESAN": { id: "Segera pesan", en: "Order now" },
  "ro.action.AMAN": { id: "Belum perlu pengadaan", en: "No procurement needed" },
  "ro.action.PERLU_REORDER": {
    id: "Pesan sekarang untuk kebutuhan ke depan",
    en: "Order now to cover upcoming demand",
  },
  "ro.action.RISIKO_STOCKOUT": {
    id: "Pesan hari ini dan cari penutup sementara",
    en: "Order today and arrange a stopgap",
  },
  "ro.action.PANTAU": {
    id: "Belum perlu pengadaan, siapkan rencana",
    en: "No procurement yet, prepare a plan",
  },
  "ro.action.SEGERA_PESAN": { id: "Buat pesanan sekarang", en: "Raise the order now" },

  "ro.prio.TINGGI": { id: "Tinggi", en: "High" },
  "ro.prio.SEDANG": { id: "Sedang", en: "Medium" },
  "ro.prio.RENDAH": { id: "Rendah", en: "Low" },

  /* ---------------- daftar pemesanan ulang ---------------- */
  "rl.desc": {
    id: "Cukup tidaknya stok untuk periode yang dipilih, dan berapa yang perlu dipesan. Paling mendesak lebih dulu.",
    en: "Whether stock covers the chosen period, and how much to order. Most urgent first.",
  },
  "rl.kpi.need": { id: "Perlu reorder", en: "Needs reorder" },
  "rl.kpi.need_hint": { id: "Stok kurang untuk periode ini", en: "Stock falls short for this period" },
  "rl.kpi.high": { id: "Prioritas tinggi", en: "High priority" },
  "rl.kpi.high_hint": { id: "Dikerjakan lebih dulu", en: "Handle these first" },
  "rl.kpi.stockout": { id: "Risiko stockout", en: "Stockout risk" },
  "rl.kpi.stockout_hint": { id: "Habis sebelum kiriman tiba", en: "Runs out before delivery lands" },
  "rl.kpi.qty": { id: "Total rekomendasi", en: "Total recommended" },
  "rl.kpi.qty_hint": { id: "Jumlah seluruh baris yang perlu dipesan", en: "Summed across every row that needs ordering" },
  "rl.kpi.qty_pending": { id: "{n} barang belum dapat dihitung", en: "{n} items not yet computable" },
  "rl.kpi.units": { id: "unit", en: "units" },

  "rl.tab.all": { id: "Semua", en: "All" },
  "rl.tab.need": { id: "Perlu reorder", en: "Needs reorder" },
  "rl.tab.stockout": { id: "Risiko stockout", en: "Stockout risk" },
  "rl.tab.safe": { id: "Aman", en: "Healthy" },

  "rl.filter.priority": { id: "Prioritas", en: "Priority" },
  "rl.filter.all_priority": { id: "Semua prioritas", en: "Any priority" },
  "rl.filter.all_warehouse": { id: "Semua gudang", en: "All warehouses" },
  "rl.search": { id: "Cari SKU atau nama barang", en: "Search SKU or item name" },

  "rl.col.item": { id: "Barang", en: "Item" },
  "rl.col.warehouse": { id: "Gudang", en: "Warehouse" },
  "rl.col.stock": { id: "Stok tersedia", en: "Available stock" },
  "rl.col.forecast": { id: "Kebutuhan {n} hari", en: "{n}-day demand" },
  "rl.col.gap": { id: "Kurang / sisa", en: "Short / left" },
  "rl.col.status": { id: "Status", en: "Status" },
  "rl.col.qty": { id: "Pesan", en: "Order" },
  "rl.gap.short": { id: "Kurang {q}", en: "Short {q}" },
  "rl.gap.left": { id: "Sisa {q}", en: "{q} left" },

  "rl.empty": { id: "Tidak ada barang yang cocok dengan saringan ini.", en: "No items match these filters." },
  "rl.empty_safe": {
    id: "Tidak ada barang yang perlu dipesan. Stok semuanya cukup untuk periode ini.",
    en: "Nothing needs ordering. Stock covers this period for every item.",
  },
  "rl.qty_none": { id: "Belum dapat dihitung", en: "Not yet computable" },
  "rl.qty_zero": { id: "Tidak perlu", en: "Not needed" },
  "rl.no_cover": { id: "Tidak bergerak", en: "Not moving" },
  "rl.truncated": {
    id: "Daftar dipotong pada {n} baris pertama. Persempit dengan saringan gudang atau pencarian agar tidak ada barang yang terlewat.",
    en: "The list is capped at the first {n} rows. Narrow it with the warehouse filter or search so nothing is missed.",
  },

  /* --- detail perhitungan per baris --- */
  "rl.detail.open": { id: "Detail perhitungan", en: "Calculation detail" },
  "rl.detail.chain": { id: "Rantai perhitungan", en: "Derivation chain" },
  "rl.detail.ltd": { id: "Kebutuhan selama masa tunggu", en: "Lead time demand" },
  "rl.detail.ltd_basis": { id: "{laju} × {lead} hari", en: "{laju} × {lead} days" },
  "rl.detail.safety": { id: "Stok pengaman", en: "Safety stock" },
  "rl.detail.rop_master": { id: "Titik pesan master", en: "Master reorder point" },
  "rl.detail.erop": { id: "Titik pesan efektif", en: "Effective reorder point" },
  "rl.detail.erop_basis": {
    id: "yang tertinggi antara titik pesan master dan kebutuhan masa tunggu + stok pengaman",
    en: "the higher of the master reorder point and lead time demand + safety stock",
  },
  "rl.detail.horizon": { id: "Kebutuhan {n} hari ke depan", en: "Demand over the next {n} days" },
  "rl.detail.horizon_basis": {
    id: "Angka yang sama dengan halaman Prakiraan untuk periode ini",
    en: "The same figure as the Forecasting page for this period",
  },
  "rl.detail.cover": { id: "Stok bertahan", en: "Stock lasts" },
  "rl.detail.cover_basis": { id: "pada rata-rata pemakaian di atas", en: "at the average consumption above" },
  "rl.detail.target": { id: "Sasaran pengisian", en: "Order-up-to level" },
  "rl.detail.target_basis": {
    id: "kebutuhan periode + stok pengaman, tidak pernah di bawah titik pesan efektif",
    en: "period demand + safety stock, never below the effective reorder point",
  },
  "rl.detail.qty": { id: "Jumlah yang direkomendasikan", en: "Recommended quantity" },
  "rl.detail.qty_basis": { id: "sasaran pengisian − stok tersedia, dibulatkan ke atas, tidak pernah negatif", en: "order-up-to level − available stock, rounded up, never negative" },
  "rl.detail.available": { id: "Stok tersedia", en: "Available stock" },
  "rl.detail.lead": { id: "Waktu tunggu kiriman", en: "Supplier lead time" },
  "rl.detail.rate": { id: "Rata-rata pemakaian", en: "Average consumption" },
  "rl.detail.forecast_link": { id: "Buka di Prakiraan", en: "Open in Forecasting" },
  "rl.detail.po": { id: "Buat PO", en: "Create PO" },
  "rl.detail.po_done": { id: "PO {v} dibuat", en: "PO {v} created" },
  "rl.detail.unset": { id: "belum diisi", en: "not set" },

  /* Tingkat keyakinan halaman. Hanya LABEL yang tinggal di sini; kalimatnya
     sendiri (confidence_note) disusun backend, karena ia menyebut panjang
     histori dan sebab penurunan mutu yang dinilai di sana. */

  /* ---------------- analisis umur pakai / lifetime analysis ----------------

     KALIMAT DI HALAMAN INI TIDAK BOLEH MENYEBUT SEBAB. Yang diukur adalah
     selisih antara umur pakai harapan dan umur pakai aktual; kenapa selisih
     itu ada menuntut data beban, suhu, pelumasan, dan jadwal pemeliharaan
     yang tidak dimiliki basis data ini. Kalimat sependek "karena oli telat
     diganti" menuduh berdasarkan satu-satunya angka yang kebetulan tersedia.

     Status, kalimat dasar, dan kalimat dampak SELURUHNYA datang dari backend
     bersama angkanya (app/lifetime.py). Yang tinggal di sini hanyalah label
     kolom dan judul -- kata yang tidak membawa angka apa pun. */
  /* Label kategori. SATU-SATUNYA hal pada modul ini yang memang ditulis dua
     kali -- di sini dan di backend/app/i18n.py. Sebabnya: saringan status
     harus punya label SEBELUM satu baris pun tiba, sedangkan `status_label`
     pada tiap baris datang bersama angkanya. Yang digandakan hanyalah KATA
     dari sebuah enum, tanpa satu angka pun di dalamnya, sehingga keduanya
     tidak bisa berselisih nilai -- hanya bisa berselisih ejaan, dan itu
     terlihat seketika di layar. Bunyinya wajib sama persis. */
  "lt.status.PREMATURE": { id: "Penggantian dini", en: "Premature replacement" },
  "lt.status.NORMAL": { id: "Wajar", en: "Normal" },
  "lt.status.EXTENDED": { id: "Umur lebih panjang", en: "Extended lifetime" },
  "lt.status.INSUFFICIENT": { id: "Belum cukup data", en: "Not enough data" },

  "lt.title": { id: "Analisis Umur Pakai", en: "Lifetime Analysis" },
  "lt.desc": {
    id: "Perbandingan umur pakai aktual komponen terhadap umur pakai yang diharapkan.",
    en: "Actual component lifetime measured against its expected lifetime.",
  },

  /* kartu ringkas */
  "lt.kpi.premature": { id: "Penggantian Dini", en: "Premature Replacement" },
  "lt.kpi.premature_hint": { id: "Di bawah batas bawah", en: "Below the lower bound" },
  "lt.kpi.normal": { id: "Wajar", en: "Normal" },
  "lt.kpi.normal_hint": { id: "Di dalam pita umur pakai", en: "Within the lifetime band" },
  "lt.kpi.extended": { id: "Umur Lebih Panjang", en: "Extended Lifetime" },
  "lt.kpi.extended_hint": { id: "Di atas batas atas", en: "Above the upper bound" },
  "lt.kpi.insufficient": { id: "Belum Terukur", en: "Not Yet Measurable" },
  "lt.kpi.insufficient_hint": {
    id: "{n} belum punya umur pakai referensi",
    en: "{n} have no reference lifetime",
  },

  /* saringan */
  "lt.filter.status": { id: "Status", en: "Status" },
  "lt.filter.all": { id: "Semua status", en: "All statuses" },
  "lt.filter.warehouse": { id: "Gudang", en: "Warehouse" },
  "lt.filter.all_warehouses": { id: "Semua gudang", en: "All warehouses" },
  "lt.filter.search": { id: "Cari", en: "Search" },
  "lt.filter.search_hint": { id: "SKU atau nama komponen", en: "SKU or component name" },

  /* kolom tabel */
  "lt.col.component": { id: "Komponen", en: "Component" },
  "lt.col.expected": { id: "Umur harapan", en: "Expected lifetime" },
  "lt.col.actual": { id: "Umur aktual", en: "Actual lifetime" },
  "lt.col.deviation": { id: "Simpangan", en: "Deviation" },
  "lt.col.replacements": { id: "Penggantian", en: "Replacements" },
  "lt.col.status": { id: "Status", en: "Status" },

  /* satuan & bentuk angka */
  "lt.unit.days": { id: "hari", en: "days" },
  "lt.unit.years": { id: "thn", en: "yr" },
  "lt.unit.hours": { id: "jam", en: "h" },
  "lt.per_year": { id: "{n}×/tahun", en: "{n}×/yr" },
  "lt.times": { id: "{n}×", en: "{n}×" },
  "lt.unmeasured": { id: "belum terukur", en: "not measurable" },

  /* panel detail */
  "lt.detail.title": { id: "Riwayat penggantian", en: "Replacement history" },
  "lt.detail.band": { id: "Pita umur pakai", en: "Lifetime band" },
  "lt.detail.lower": { id: "Batas bawah", en: "Lower lifetime" },
  "lt.detail.expected": { id: "Umur harapan", en: "Expected lifetime" },
  "lt.detail.upper": { id: "Batas atas", en: "Upper lifetime" },
  "lt.detail.shortest": { id: "Terpendek", en: "Shortest" },
  "lt.detail.longest": { id: "Terpanjang", en: "Longest" },
  "lt.detail.frequency": { id: "Frekuensi penggantian", en: "Replacement frequency" },
  "lt.detail.last": { id: "Penggantian terakhir", en: "Last replacement" },
  "lt.detail.events": { id: "Kejadian penggantian", en: "Replacement events" },
  "lt.detail.events_note": {
    id: "Menampilkan {n} dari {total} kejadian, terbaru lebih dulu.",
    en: "Showing {n} of {total} events, most recent first.",
  },
  "lt.detail.col_date": { id: "Tanggal", en: "Date" },
  "lt.detail.col_document": { id: "Dokumen", en: "Document" },
  "lt.detail.col_lifetime": { id: "Umur pakai", en: "Lifetime" },
  "lt.detail.first_event": {
    id: "Penggantian pertama yang tercatat; tidak ada pendahulunya untuk diukur.",
    en: "The first recorded replacement; there is no predecessor to measure against.",
  },
  "lt.detail.close": { id: "Tutup", en: "Close" },
  "lt.detail.open": { id: "Lihat riwayat", en: "View history" },
  /* Panel detail yang belum dipilih apa-apa. Sebelumnya memakai
     "lt.detail.open" -- label TOMBOL yang dipakai sebagai kalimat, sehingga
     panelnya berbunyi "Lihat riwayat" tanpa memberi tahu caranya. */
  "lt.detail.empty": {
    id: "Pilih satu komponen pada grafik untuk melihat riwayat penggantiannya.",
    en: "Pick a component in the chart to see its replacement history.",
  },

  /* --- grafik standar vs aktual, per komponen --- */
  "lt.chart.title": { id: "Standar vs Aktual", en: "Standard vs Actual" },
  "lt.chart.subtitle": {
    id: "Umur aktual tiap komponen terhadap standarnya. Tekan Lihat grafik pada satu baris untuk grafik komponen itu.",
    en: "Each component's actual lifetime against its standard. Press View chart on a row for that component's chart.",
  },
  "lt.col.chart": { id: "Grafik", en: "Chart" },
  "lt.chart.open": { id: "Lihat grafik", en: "View chart" },
  "lt.chart.close": { id: "Tutup grafik", en: "Hide chart" },
  "lt.chart.standard": { id: "Standar", en: "Standard" },
  "lt.chart.actual": { id: "Aktual", en: "Actual" },
  "lt.chart.legend_standard": { id: "Standar ({n} hari)", en: "Standard ({n} days)" },
  "lt.chart.legend_actual": { id: "Aktual (umur tiap unit)", en: "Actual (each unit's lifetime)" },
  "lt.chart.history_title": { id: "Grafik standar vs aktual", en: "Standard vs actual chart" },
  "lt.chart.history_note": {
    id: "Satu titik = satu penggantian; tingginya lama unit itu bertahan (hari). Warna titik mengikuti statusnya.",
    en: "One dot = one replacement; its height is how long that unit lasted (days). Dot colour follows its status.",
  },
  "lt.chart.no_data": {
    id: "Belum ada grafik: perlu standar umur pakai dan sedikitnya dua penggantian.",
    en: "No chart yet: it needs a standard lifetime and at least two replacements.",
  },
  "lt.chart.events_table": { id: "Lihat sebagai tabel", en: "View as table" },

  /* tautan ke modul yang memang memakai polanya */
  "lt.link.forecast": { id: "Lihat prakiraan", en: "View forecast" },
  "lt.link.reorder": { id: "Lihat pemesanan ulang", en: "View reorder" },

  /* keadaan kosong */
  "lt.empty": {
    id: "Tidak ada komponen yang cocok dengan saringan ini.",
    en: "No component matches this filter.",
  },
  /* KETERANGAN INI TERBIT DI ATAS TABEL, bukan menggantikannya.
     Penyewa yang belum mengisi satu pun umur pakai TETAP punya baris -- dua
     puluh baris berisi tanda hubung di setiap kolom. Menyembunyikan tabelnya
     akan menghilangkan daftar barangnya; membiarkannya tanpa keterangan
     membuat pembaca menatap dua puluh tanda hubung tanpa tahu apa yang
     kurang maupun di mana memperbaikinya. */
  "lt.no_reference": {
    id: "Belum ada satu pun komponen yang punya umur pakai referensi, sehingga belum ada yang dapat dibandingkan. Isi kolom umur pakai pada Master Barang untuk memulai.",
    en: "Not one component carries a reference lifetime yet, so there is nothing to compare against. Fill in the service life field on the Item Master to begin.",
  },
  "lt.empty_all": {
    id: "Belum ada komponen dengan umur pakai referensi. Isi kolom umur pakai pada Master Barang untuk memulai.",
    en: "No component carries a reference lifetime yet. Fill in the service life field on the Item Master to begin.",
  },

  /* ---------------- asisten / assistant ---------------- */
  "as.title": { id: "Asisten AI Persediaan", en: "Inventory AI Assistant" },
  "as.sub": {
    id: "Analisis stok, barang, gudang, dan transaksi berdasarkan data sistem",
    en: "Stock, item, warehouse and transaction analysis grounded in system data",
  },
  "as.clear": { id: "Bersihkan percakapan", en: "Clear conversation" },
  "as.greet": { id: "Ada yang bisa dibantu?", en: "How can I help?" },
  "as.greet_body": {
    id: "Ajukan pertanyaan dengan bahasa sehari-hari. Setiap jawaban disusun dari data yang diambil langsung dari sistem, bukan dari perkiraan.",
    en: "Ask in plain language. Every answer is built from data pulled straight out of the system, never from guesswork.",
  },
  "as.examples": { id: "Contoh pertanyaan", en: "Example questions" },
  "as.placeholder": {
    id: "Tanyakan sesuatu tentang persediaan…",
    en: "Ask anything about the inventory…",
  },
  "as.placeholder_off": {
    id: "Layanan asisten sedang tidak tersedia",
    en: "The assistant service is unavailable",
  },
  "as.send": { id: "Kirim pertanyaan", en: "Send question" },
  "as.searching": { id: "Menelusuri data persediaan…", en: "Searching inventory data…" },
  "as.sources": { id: "Sumber data", en: "Data sources" },
  "as.source_failed": { id: "Sumber data ini gagal dibaca", en: "This data source failed to read" },
  "as.failed_suffix": { id: " · gagal", en: " · failed" },
  "as.copy": { id: "Salin", en: "Copy" },
  "as.copied": { id: "Tersalin", en: "Copied" },
  "as.you": { id: "Anda", en: "You" },

  /* nama sumber data yang dikenali pengguna / user-facing data source names */
  "as.src.get_dashboard": { id: "Ringkasan persediaan", en: "Inventory summary" },
  "as.src.get_warehouses": { id: "Daftar gudang", en: "Warehouse list" },
  "as.src.get_warehouse": { id: "Detail gudang", en: "Warehouse detail" },
  "as.src.get_items": { id: "Master barang", en: "Item master" },
  "as.src.get_item": { id: "Detail barang", en: "Item detail" },
  "as.src.get_inventory": { id: "Stok per gudang", en: "Stock by warehouse" },
  "as.src.get_low_stock": { id: "Stok menipis", en: "Low stock" },
  "as.src.get_stock_movements": { id: "Pergerakan stok", en: "Stock movements" },
  "as.src.get_stock_receipts": { id: "Penerimaan barang", en: "Stock receipts" },
  "as.src.get_stock_receipt": { id: "Detail penerimaan", en: "Receipt detail" },
  "as.src.get_stock_issues": { id: "Pengeluaran barang", en: "Stock issues" },
  "as.src.get_stock_issue": { id: "Detail pengeluaran", en: "Issue detail" },
  "as.src.get_stock_report": { id: "Laporan stok", en: "Stock report" },
  "as.src.get_receipt_report": { id: "Laporan penerimaan", en: "Receipt report" },
  "as.src.get_issue_report": { id: "Laporan pengeluaran", en: "Issue report" },
  "as.src.create_stock_receipt": { id: "Pencatatan penerimaan", en: "Receipt posting" },
  "as.src.create_stock_issue": { id: "Pencatatan pengeluaran", en: "Issue posting" },

  /* ---------------- pengaturan / settings ---------------- */
  "st.title": { id: "Pengaturan", en: "Settings" },
  "st.desc": {
    id: "Konfigurasi yang sedang berlaku pada aplikasi ini.",
    en: "The configuration currently in force for this application.",
  },
  "st.backend": { id: "Koneksi Backend", en: "Backend Connection" },
  "st.backend_sub": {
    id: "Sumber seluruh data yang ditampilkan aplikasi",
    en: "The origin of every figure this application shows",
  },
  "st.api_url": { id: "Alamat API", en: "API address" },
  "st.checking": { id: "memeriksa…", en: "checking…" },
  "st.disconnected": { id: "Terputus", en: "Disconnected" },
  "st.connected": { id: "Terhubung", en: "Connected" },
  "st.database": { id: "Basis data", en: "Database" },
  "st.unreachable": { id: "tidak terjangkau", en: "unreachable" },
  "st.api_note_1": {
    id: "Alamat API mengikuti host halaman ini pada port 8000. Untuk mengarahkannya ke alamat lain, isi",
    en: "The API address follows this page's host on port 8000. To point it elsewhere, set",
  },
  "st.api_note_2": { id: "pada berkas", en: "in" },
  "st.appearance": { id: "Tampilan", en: "Appearance" },
  "st.appearance_sub": { id: "Tersimpan di peramban ini saja", en: "Stored in this browser only" },
  "st.light": { id: "Terang", en: "Light" },
  "st.dark": { id: "Gelap", en: "Dark" },
  "st.system": { id: "Ikuti sistem", en: "Follow system" },
  "st.language": { id: "Bahasa", en: "Language" },
  "st.language_sub": {
    id: "Berlaku untuk seluruh label antarmuka",
    en: "Applies to every interface label",
  },
  "st.rules": { id: "Aturan yang berlaku", en: "Rules in force" },
  "st.rules_sub": {
    id: "Ditetapkan backend dan basis data — tidak dapat diubah dari layar ini",
    en: "Set by the backend and database — not editable from this screen",
  },
  "st.rule": { id: "Aturan", en: "Rule" },
  "st.rule_value": { id: "Nilai", en: "Value" },
  "st.rule_gr": { id: "Penomoran penerimaan", en: "Receipt numbering" },
  "st.rule_gr_v": { id: "urutan direset tiap hari", en: "sequence resets daily" },
  "st.rule_iss": { id: "Penomoran pengeluaran", en: "Issue numbering" },
  "st.rule_low": { id: "Ambang stok menipis", en: "Low stock threshold" },
  "st.rule_low_v": {
    id: "Titik pesan ulang; bila belum diisi dipakai stok minimum",
    en: "Reorder point; where unset, minimum stock is used",
  },
  "st.rule_value_basis": { id: "Nilai persediaan", en: "Inventory value" },
  "st.rule_value_basis_v": {
    id: "Harga referensi master barang, bukan harga perolehan sebenarnya",
    en: "Item master reference price, not actual acquisition cost",
  },
  "st.rule_over": { id: "Pengeluaran melebihi stok", en: "Issue beyond stock" },
  "st.rule_over_v": {
    id: "Ditolak backend; stok tidak pernah boleh menjadi negatif",
    en: "Rejected by the backend; stock may never go negative",
  },
  "st.rule_atomic": { id: "Atomicity transaksi", en: "Transaction atomicity" },
  "st.rule_atomic_v": {
    id: "Satu dokumen ditulis dalam satu transaksi basis data",
    en: "One document is written in one database transaction",
  },
};
