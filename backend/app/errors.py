# -*- coding: utf-8 -*-
"""
Kesalahan yang aman ditampilkan ke pengguna.

Aturan: galat mentah dari basis data TIDAK PERNAH sampai ke klien. Pesan SQL
membocorkan nama tabel, nama constraint, dan struktur internal. Yang keluar
hanya pesan yang sudah ditulis untuk dibaca manusia; detail teknisnya masuk
log server.
"""

from . import i18n


class AppError(Exception):
    """Kesalahan yang sudah dirumuskan untuk pengguna."""

    def __init__(self, status_code: int, code: str, message: str,
                 field: str | None = None, detail: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.field = field
        # Keterangan tambahan yang bisa DIPAKAI klien, bukan sekadar dibaca --
        # misalnya daftar id yang ditolak pada konfirmasi massal, supaya
        # antarmuka dapat menyorot baris yang bersangkutan alih-alih hanya
        # menampilkan kalimat galat.
        self.detail = detail or {}

    def body(self) -> dict:
        out: dict = {"error": {"code": self.code, "message": self.message}}
        if self.field:
            out["error"]["field"] = self.field
        if self.detail:
            out["error"]["detail"] = self.detail
        return out


def not_found(entity: str, value, field: str | None = None) -> AppError:
    """
    `entity` adalah KUNCI entitas ("item", "warehouse"), bukan kata yang tampil.
    Bahasanya diambil dari permintaan yang sedang berjalan, sehingga pemanggil
    yang jauh di dalam lapisan data tidak perlu tahu apa-apa tentangnya.
    """
    lang = i18n.bahasa_permintaan()
    return AppError(
        404, "NOT_FOUND",
        i18n.t("err.not_found", lang,
               entitas=i18n.t(f"err.entity.{entity}", lang), id=value),
        field,
    )


def inactive(entity: str, name: str, field: str | None = None) -> AppError:
    lang = i18n.bahasa_permintaan()
    return AppError(
        422, "INACTIVE",
        i18n.t("err.inactive", lang,
               entitas=i18n.t(f"err.entity.{entity}", lang), nama=name),
        field,
    )


def invalid(message: str, field: str | None = None) -> AppError:
    return AppError(422, "VALIDATION_ERROR", message, field)
