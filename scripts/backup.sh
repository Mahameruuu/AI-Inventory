#!/usr/bin/env bash
#
# Cadangan basis data Inventory AI.
#
#   scripts/backup.sh               buat cadangan, periksa, pangkas yang lama
#   scripts/backup.sh --uji-pulih   juga pulihkan ke basis data sementara dan
#                                   bandingkan jumlah barisnya dengan aslinya
#
# KENAPA ADA --uji-pulih. Cadangan yang belum pernah dicoba dipulihkan baru
# sebuah harapan. pg_restore --list hanya membuktikan berkasnya terbaca;
# memulihkannya sungguhan membuktikan isinya utuh. Cron menjalankannya
# seminggu sekali.
#
# FORMAT CUSTOM (-Fc): terkompresi, dan bisa dipulihkan per tabel bila yang
# rusak hanya sebagian.
#
# HAK ADMIN dipakai karena role aplikasi tunduk RLS: pg_dump dengan role itu
# hanya akan melihat baris satu penyewa -- atau nol baris -- tanpa galat apa pun.
#
# Lingkungan (opsional):
#   BACKUP_DIR        tujuan berkas            (bawaan: ~/backups/inventory)
#   BACKUP_HARIAN     cadangan harian disimpan (bawaan: 14)
#   BACKUP_MINGGUAN   cadangan Minggu disimpan (bawaan: 8)
#   BACKUP_SALIN_KE   tujuan rsync kedua di MESIN LAIN, mis. user@host:/cadangan/
#                     (bawaan: kosong -- lihat peringatan di akhir skrip)
#
set -euo pipefail

AKAR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/inventory}"
BACKUP_HARIAN="${BACKUP_HARIAN:-14}"
BACKUP_MINGGUAN="${BACKUP_MINGGUAN:-8}"
BACKUP_SALIN_KE="${BACKUP_SALIN_KE:-}"

log() { echo "[$(date '+%F %T')] $*"; }
gagal() { log "GAGAL: $*"; exit 1; }

URL="$(grep -E '^ADMIN_DATABASE_URL=' "$AKAR/.env" | head -1 | cut -d= -f2- | tr -d "\"'")"
[[ -n "$URL" ]] || gagal "ADMIN_DATABASE_URL tidak ada di $AKAR/.env"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"   # isinya seluruh data, termasuk hash kata sandi pengguna

STEMPEL="$(date '+%Y%m%d-%H%M%S')"
BERKAS="$BACKUP_DIR/inventory-$STEMPEL.dump"
SEMENTARA="$BERKAS.sebagian"
trap 'rm -f "$SEMENTARA"' EXIT

# --- 1. dump -------------------------------------------------------------
# Ditulis ke nama sementara dulu: dump yang terputus di tengah tidak boleh
# tampak seperti cadangan yang sah.
log "membuat cadangan -> $BERKAS"
pg_dump "$URL" -Fc -Z 6 --no-owner --no-privileges -f "$SEMENTARA"

# --- 2. periksa ----------------------------------------------------------
pg_restore --list "$SEMENTARA" > /dev/null || gagal "berkas cadangan tidak terbaca"
JUMLAH_TABEL=$(pg_restore --list "$SEMENTARA" | grep -c ' TABLE DATA ' || true)
(( JUMLAH_TABEL >= 20 )) || gagal "hanya $JUMLAH_TABEL tabel di cadangan; curiga tidak lengkap"

mv "$SEMENTARA" "$BERKAS"
chmod 600 "$BERKAS"
sha256sum "$BERKAS" > "$BERKAS.sha256"
log "selesai: $(du -h "$BERKAS" | cut -f1), $JUMLAH_TABEL tabel"

# --- 3. uji pulih (opsional) ---------------------------------------------
if [[ "${1:-}" == "--uji-pulih" ]]; then
    INDUK="${URL%/*}"
    DB_UJI="inventory_uji_pulih"
    log "uji pulih ke basis data sementara $DB_UJI"
    psql "$INDUK/postgres" -qAtc "DROP DATABASE IF EXISTS $DB_UJI" >/dev/null
    psql "$INDUK/postgres" -qAtc "CREATE DATABASE $DB_UJI" >/dev/null
    trap 'rm -f "$SEMENTARA"; psql "$INDUK/postgres" -qAtc "DROP DATABASE IF EXISTS $DB_UJI" >/dev/null 2>&1 || true' EXIT

    pg_restore --no-owner --no-privileges --exit-on-error -d "$INDUK/$DB_UJI" "$BERKAS" \
        || gagal "pemulihan gagal"

    # Bandingkan jumlah baris tabel-tabel inti. Angka yang berbeda berarti
    # ada yang hilang -- atau ada transaksi yang masuk sesudah dump, yang
    # karena itu hanya boleh menambah, tidak pernah mengurangi.
    HITUNG="SELECT 'companies', count(*) FROM companies UNION ALL
            SELECT 'items', count(*) FROM items UNION ALL
            SELECT 'inventory', count(*) FROM inventory UNION ALL
            SELECT 'stock_movements', count(*) FROM stock_movements UNION ALL
            SELECT 'audit_log', count(*) FROM audit_log"
    ASLI="$(psql "$URL" -qAtF' ' -c "$HITUNG")"
    PULIH="$(psql "$INDUK/$DB_UJI" -qAtF' ' -c "$HITUNG")"
    while read -r tabel n_pulih; do
        n_asli="$(awk -v t="$tabel" '$1==t {print $2}' <<<"$ASLI")"
        (( n_pulih <= n_asli )) || gagal "$tabel: hasil pulih $n_pulih > asli $n_asli"
        (( n_pulih > 0 || n_asli == 0 )) || gagal "$tabel kosong setelah pulih (asli $n_asli)"
        log "  $tabel: asli $n_asli, pulih $n_pulih"
    done <<<"$PULIH"
    log "uji pulih LULUS"
fi

# --- 4. pangkas ----------------------------------------------------------
# Simpan N harian terbaru, ditambah cadangan hari Minggu untuk N minggu.
mapfile -t SEMUA < <(ls -1t "$BACKUP_DIR"/inventory-*.dump 2>/dev/null)
declare -A SIMPAN=()
for f in "${SEMUA[@]:0:$BACKUP_HARIAN}"; do SIMPAN["$f"]=1; done
minggu=0
for f in "${SEMUA[@]}"; do
    tgl="$(basename "$f" | sed -E 's/inventory-([0-9]{8}).*/\1/')"
    if [[ "$(date -d "$tgl" +%u)" == 7 ]] && (( minggu < BACKUP_MINGGUAN )); then
        SIMPAN["$f"]=1; minggu=$((minggu + 1))
    fi
done
for f in "${SEMUA[@]}"; do
    if [[ -z "${SIMPAN[$f]:-}" ]]; then
        rm -f "$f" "$f.sha256"; log "dipangkas: $(basename "$f")"
    fi
done

# --- 5. salinan di luar mesin ini ----------------------------------------
if [[ -n "$BACKUP_SALIN_KE" ]]; then
    rsync -a "$BERKAS" "$BERKAS.sha256" "$BACKUP_SALIN_KE" || gagal "rsync ke $BACKUP_SALIN_KE gagal"
    log "disalin ke $BACKUP_SALIN_KE"
else
    # Cadangan di disk yang sama dengan basis datanya tidak menolong saat
    # disknya yang rusak. Peringatan ini sengaja muncul di setiap log.
    log "PERINGATAN: BACKUP_SALIN_KE kosong; cadangan hanya ada di mesin ini"
fi
