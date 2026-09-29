FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tools ./tools

# Berkas model TIDAK ikut ke dalam image -- lihat .dockerignore. Direktorinya
# dibuat kosong sebagai titik pasang, dan diisi saat kontainer dijalankan:
#
#   docker run -v <direktori model di host>:/models:ro \
#              -e FORECAST_MODEL_DIR=/models ...
#
# Dipasang read-only: aplikasi hanya pernah membaca berkas ini, dan tidak ada
# alasan satu proses yang menghadap jaringan bisa menimpanya.
RUN mkdir -p /models

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
