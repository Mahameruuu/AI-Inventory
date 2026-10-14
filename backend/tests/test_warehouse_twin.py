# -*- coding: utf-8 -*-
"""Pemetaan status 3D Warehouse Twin: murni, tanpa basis data."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import decision  # noqa: E402
from app.routers.warehouse_twin import status_dari_aksi  # noqa: E402


@pytest.mark.parametrize("aksi,harapan", [
    (decision.STATUS_AMAN, "normal"),
    (decision.STATUS_PERLU_REORDER, "perhatian"),
    (decision.STATUS_RISIKO_STOCKOUT, "kritis"),
    (None, "tidak_diketahui"),          # mesin tidak punya barisnya
    ("STATUS_ASING", "tidak_diketahui"),
])
def test_status(aksi, harapan):
    assert status_dari_aksi(aksi) == harapan
