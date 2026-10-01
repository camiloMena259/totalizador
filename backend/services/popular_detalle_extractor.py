from __future__ import annotations

import re

from services.detalle_portal import extract_detalle_portal
from services.extractor import _normalizar_texto

_RE_RELLENO_CEROS = re.compile(r"^0+$")


def _limpiar_transaccion(texto: str) -> str:
    """
    Popular rellena la columna Transacción con líneas de ceros y deja
    la descripción real al final (por ejemplo 'N.C. INTERESES').
    """
    partes: list[str] = []
    for linea in (texto or "").splitlines():
        linea = _normalizar_texto(linea)
        if not linea or _RE_RELLENO_CEROS.match(linea):
            continue
        linea = re.sub(r"^0+\s+", "", linea).strip()
        if linea:
            partes.append(linea)
    return " ".join(partes)


def extract_detalle_popular(pdf_path_or_file, columns: list[str] | None = None) -> list[dict]:
    """
    Extrae el detalle de movimientos de Banco Popular.

    Mismo reporte de portal que Occidente, con la descripción contaminada
    por relleno de ceros que aquí se descarta.
    """
    return extract_detalle_portal(
        pdf_path_or_file,
        banco="POPULAR",
        limpiar_transaccion=_limpiar_transaccion,
        columns=columns,
    )
