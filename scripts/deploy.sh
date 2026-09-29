#!/usr/bin/env bash
#
# Membangun image dan menjalankan ulang kedua kontainer, dengan konfigurasi
# yang benar.
#
# KENAPA SKRIP, BUKAN CATATAN DI DOKUMEN. Perintah `docker run` untuk backend
# membawa tujuh belas variabel lingkungan dan satu mount berkas model 757 MB.
# Dua di antaranya tidak boleh salah dan tidak akan terlihat bila salah:
#
#   -v <model>:/models:ro   tanpa ini backend menolak menyala (app/main.py),
#                           yang sudah jauh lebih baik daripada versi lama yang
#                           diam-diam turun ke rata-rata bergerak;
#   ADMIN_DATABASE_URL      TIDAK boleh ikut ke dalam kontainer -- kredensial
#                           superuser di proses yang menghadap jaringan
#                           mematikan seluruh Row Level Security.
#
# Menuliskannya sebagai perintah yang harus disalin tangan berarti keduanya
# menunggu giliran untuk terlupa.
#
#   scripts/deploy.sh            bangun image lalu tukar kedua kontainer
#   scripts/deploy.sh --restart  tukar kontainer saja, tanpa membangun ulang
#
set -euo pipefail

AKAR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AKAR"

MODEL_DIR="$AKAR/backend/models"
ENV_KONTAINER="$(mktemp)"
trap 'rm -f "$ENV_KONTAINER"' EXIT

# --- pemeriksaan sebelum menyentuh apa pun -------------------------------
[[ -f .env ]] || { echo "GAGAL: .env tidak ada di $AKAR"; exit 1; }
[[ -d "$MODEL_DIR" ]] || { echo "GAGAL: direktori model tidak ada: $MODEL_DIR"; exit 1; }
if ! compgen -G "$MODEL_DIR/production_tweedie.*" >/dev/null; then
    echo "GAGAL: berkas model tidak ditemukan di $MODEL_DIR"; exit 1
fi

# --- lingkungan kontainer, diturunkan dari .env --------------------------
# Kredensial admin basis data sengaja disaring keluar; letak model ditambahkan.
grep -vE '^\s*(#|$)' .env \
  | grep -v '^ADMIN_DATABASE_URL=' \
  | sed -E 's/^([A-Za-z_][A-Za-z0-9_]*)=["'"'"']?(.*[^"'"'"'])["'"'"']?$/\1=\2/' \
  > "$ENV_KONTAINER"
echo "FORECAST_MODEL_DIR=/models" >> "$ENV_KONTAINER"

if grep -q '^DATABASE_URL=postgresql://inventory_admin' "$ENV_KONTAINER"; then
    echo "GAGAL: DATABASE_URL menunjuk inventory_admin (superuser)."
    echo "       Superuser dibebaskan dari seluruh Row Level Security, sehingga"
    echo "       pemisahan antar perusahaan tidak akan aktif. Arahkan ke"
    echo "       inventory_app pada .env."
    exit 1
fi

# --- bangun --------------------------------------------------------------
if [[ "${1:-}" != "--restart" ]]; then
    echo "== membangun image (kontainer lama masih melayani selama ini) =="
    docker build -t inventory-ai-backend:baru  ./backend
    docker build -t inventory-ai-frontend:baru ./frontend

    # Jalan pulang: image yang sedang berjalan diberi tag sebelum ditimpa.
    CAP="rollback-$(date +%Y%m%d-%H%M)"
    docker tag inventory-ai-backend:latest  "inventory-ai-backend:$CAP"  2>/dev/null || true
    docker tag inventory-ai-frontend:latest "inventory-ai-frontend:$CAP" 2>/dev/null || true
    echo "== image sebelumnya disimpan bertag :$CAP =="

    docker tag inventory-ai-backend:baru  inventory-ai-backend:latest
    docker tag inventory-ai-frontend:baru inventory-ai-frontend:latest
    docker rmi inventory-ai-backend:baru inventory-ai-frontend:baru >/dev/null 2>&1 || true
fi

# --- tukar ---------------------------------------------------------------
echo "== menukar kontainer =="
docker rm -f inventory-ai-backend inventory-ai-frontend >/dev/null 2>&1 || true

docker run -d --name inventory-ai-backend --restart unless-stopped \
    -p 8000:8000 \
    --env-file "$ENV_KONTAINER" \
    -v "$MODEL_DIR:/models:ro" \
    inventory-ai-backend:latest >/dev/null

docker run -d --name inventory-ai-frontend --restart unless-stopped \
    -p 3006:3000 \
    -e NEXT_PUBLIC_API_URL= \
    inventory-ai-frontend:latest >/dev/null

# --- pastikan benar-benar hidup ------------------------------------------
echo -n "== menunggu backend siap "
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
        echo "-- siap =="
        curl -s http://localhost:8000/api/health | python3 -c '
import json, sys
d = json.load(sys.stdin)["forecast_model"]
print("   model prakiraan: %s (%s), aktif=%s"
      % (d.get("method"), d.get("model_file"), d.get("available")))'
        docker ps --filter name=inventory-ai --format '   {{.Names}}  {{.Status}}  {{.Ports}}'
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo
echo "GAGAL: backend tidak siap dalam 60 detik. Log terakhir:"
docker logs --tail 25 inventory-ai-backend
exit 1
