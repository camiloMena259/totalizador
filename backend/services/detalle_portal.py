"""
Parser del reporte "Movimientos - Detalles de Movimientos" del portal Aval.

Lo comparten Banco de Occidente y Banco Popular. No es el extracto mensual:
cada página repite el encabezado y la tabla de movimientos es

    Fecha | Transacción | Nro. Documento | Débitos | Créditos

No hay saldo por fila. El concepto se arma con la descripción legible y,
si existe, el número de documento, que es lo que el totalizador puede mostrar.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

import pdfplumber

from services.extractor import _filtrar_columnas, _normalizar_texto, _quitar_tildes

logger = logging.getLogger(__name__)

_RE_FECHA = re.compile(r"^(\d{4})/(\d{2})/(\d{2})$")
_RE_MONTO = re.compile(r"^\d+\.\d{2}$")
_RE_SOLO_CEROS = re.compile(r"^0+$")


def _parse_monto_colombiano(token: str | None) -> str | None:
    """'$2.383.845,00' -> '2383845.00'. Devuelve None si el token no es un monto."""
    if not token:
        return None
    limpio = re.sub(r"\s+", "", token).replace("$", "").replace("-", "")
    if "," not in limpio:
        return None
    normalizado = limpio.replace(".", "").replace(",", ".")
    if not _RE_MONTO.match(normalizado):
        return None
    return normalizado


def _es_tabla_movimientos(tabla: list) -> bool:
    if not tabla or not tabla[0] or len(tabla[0]) < 5:
        return False
    encabezado = [
        _quitar_tildes(_normalizar_texto(celda or "")).upper()
        for celda in tabla[0]
    ]
    return encabezado[0].startswith("FECHA") and encabezado[3].startswith("DEBIT")


def _documento_visible(documento: str) -> str:
    """'0000000' es un relleno del portal, no un número de documento."""
    compacto = re.sub(r"\s+", "", documento or "")
    if not compacto or _RE_SOLO_CEROS.match(compacto):
        return ""
    return _normalizar_texto(documento)


def _fila_portal(
    raw: list,
    banco: str,
    limpiar_transaccion: Callable[[str], str],
) -> dict | None:
    if not raw or len(raw) < 5:
        return None

    fecha = _normalizar_texto(raw[0] or "")
    match = _RE_FECHA.match(fecha)
    if not match:
        return None

    debito = _parse_monto_colombiano(raw[3])
    credito = _parse_monto_colombiano(raw[4])
    if debito is None or credito is None:
        logger.warning(
            "[%s-DETALLE] montos ilegibles en %s: debito=%r credito=%r",
            banco, fecha, raw[3], raw[4],
        )
        return None

    _anio, mes, dia = match.groups()
    documento = _documento_visible(raw[2] or "")
    descripcion = limpiar_transaccion(raw[1] or "")
    concepto = _normalizar_texto(" ".join(parte for parte in (descripcion, documento) if parte))

    return {
        "DIA": dia,
        "MES": mes,
        "HORA": "",
        "CONCEPTO": concepto,
        "IDENTIFICACION": documento,
        "DEBITO": "" if debito == "0.00" else debito,
        "CREDITO": "" if credito == "0.00" else credito,
        "SALDO": "",
    }


def extract_detalle_portal(
    pdf_path_or_file,
    *,
    banco: str,
    limpiar_transaccion: Callable[[str], str],
    columns: list[str] | None = None,
) -> list[dict]:
    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            for tabla in page.extract_tables() or []:
                if not _es_tabla_movimientos(tabla):
                    continue
                for raw in tabla[1:]:
                    fila = _fila_portal(raw, banco, limpiar_transaccion)
                    if fila:
                        rows.append(fila)

    return _filtrar_columnas(rows, columns)
