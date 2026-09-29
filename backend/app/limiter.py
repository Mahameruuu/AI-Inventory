# -*- coding: utf-8 -*-
"""
Pembatas laju untuk endpoint yang berat secara komputasi.

Dipisah dari main.py supaya router (mis. forecast_api.py) bisa mengimpor
`limiter` untuk memasang `@limiter.limit(...)` pada endpoint tanpa membuat
impor melingkar dengan main.py.

DIKUNCI PER PENGGUNA, BUKAN PER ALAMAT IP. Aplikasi ini dipakai dari jaringan
kantor yang lazimnya keluar lewat satu alamat IP bersama (NAT); membatasi per
IP berarti satu pengguna yang memanggil endpoint berulang bisa menghabiskan
jatah seluruh kantor. `tenant.penyewa()` sudah terisi pada titik ini karena
pembatas dievaluasi setelah FastAPI menuntaskan seluruh dependency endpoint,
termasuk `pengguna_saat_ini` yang menyetelnya -- lihat app/auth.py. Jatuh ke
alamat IP hanya terjadi pada permintaan yang entah bagaimana lolos tanpa
penyewa (semestinya tidak pernah terjadi di balik WAJIB_MASUK pada main.py).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from . import tenant


def _kunci_pembatas(request: Request) -> str:
    p = tenant.penyewa()
    if p and p.user_id:
        return f"pengguna:{p.user_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=_kunci_pembatas)
