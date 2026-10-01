from __future__ import annotations

import logging
import re
from decimal import Decimal

import pdfplumber

from services.extractor import _agrupar_por_lineas, _filtrar_columnas

logger = logging.getLogger(__name__)

_RE_FECHA = re.compile(r"^\d{2}-\d{2}-\d{4}$")
_RE_MONTO = re.compile(r"^-?\d+\.\d{2}$")
# Referencias internas (0000101006R01, P6403760, C0026). No describen el movimiento.
_RE_CODIGO_INTERNO = re.compile(r"^(?=.*\d)[A-Z0-9]{5,}$")

# Cortes medidos sobre el histórico de movimientos BBVA en A4.
# El importe y el saldo se parten entre la fila y la siguiente cuando no caben.
_X_FECHA_VALOR = 112
_X_CODIGO = 162
_X_DESCRIPCION = 202
_X_MOVIMIENTO = 348
_X_IMPORTE = 408
_X_SALDO = 470


def _es_inicio_movimiento(linea: list[dict]) -> bool:
    izquierda = [w for w in linea if w["x0"] < _X_FECHA_VALOR]
    if not izquierda:
        return False
    primero = min(izquierda, key=lambda w: w["x0"])
    return bool(_RE_FECHA.match(primero["text"]))


def _textos(words: list[dict], x_min: float, x_max: float) -> list[str]:
    return [
        w["text"]
        for w in sorted(words, key=lambda w: (w["top"], w["x0"]))
        if x_min <= w["x0"] < x_max
    ]


def _unir_monto(tokens: list[str]) -> str:
    """Junta un monto partido ('-' + '453,439,400.00', o saldo + centavos)."""
    return "".join(tokens).replace(",", "").replace(" ", "")


def _concepto(words: list[dict]) -> str:
    utiles = [
        w["text"]
        for w in sorted(words, key=lambda w: (w["top"], w["x0"]))
        if _X_DESCRIPCION <= w["x0"] < _X_MOVIMIENTO
        and not _RE_CODIGO_INTERNO.match(w["text"])
    ]
    return re.sub(r"\s+", " ", " ".join(utiles)).strip()


def _fila_desde_palabras(words: list[dict]) -> dict | None:
    fechas = _textos(words, 0, _X_FECHA_VALOR)
    if not fechas or not _RE_FECHA.match(fechas[0]):
        return None

    importe = _unir_monto(_textos(words, _X_IMPORTE, _X_SALDO))
    saldo = _unir_monto(_textos(words, _X_SALDO, 10_000))
    if not (_RE_MONTO.match(importe) and _RE_MONTO.match(saldo)):
        logger.warning(
            "[BBVA-DETALLE] monto ilegible en %s: importe=%r saldo=%r",
            fechas[0], importe, saldo,
        )
        return None

    valor = Decimal(importe)
    dia, mes, _anio = fechas[0].split("-")
    fecha_valor = next(
        (token for token in _textos(words, _X_FECHA_VALOR, _X_CODIGO) if _RE_FECHA.match(token)),
        "",
    )

    return {
        "DIA": dia,
        "MES": mes,
        "HORA": "",
        "CONCEPTO": _concepto(words),
        "DEBITO": f"{abs(valor):.2f}" if valor < 0 else "",
        "CREDITO": f"{valor:.2f}" if valor > 0 else "",
        "SALDO": saldo,
        "MOVIMIENTO": "".join(_textos(words, _X_MOVIMIENTO, _X_IMPORTE)),
        "FECHA_OPERACION": fechas[0],
        "FECHA_VALOR": fecha_valor,
    }


def extract_detalle_bbva(pdf_path_or_file, columns: list[str] | None = None) -> list[dict]:
    """
    Extrae el histórico de movimientos BBVA.

    Columnas de origen: fecha de operación, descripción, número de movimiento,
    importe y saldo. El importe negativo entra como débito y el positivo como
    crédito, que es el esquema del totalizador.
    """
    bloques: list[list[dict]] = []
    actual: list[dict] | None = None

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue
            for linea in _agrupar_por_lineas(words, y_tolerance=2.5):
                if _es_inicio_movimiento(linea):
                    if actual:
                        bloques.append(actual)
                    actual = list(linea)
                elif actual is not None:
                    actual.extend(linea)

    if actual:
        bloques.append(actual)

    rows: list[dict] = []
    for bloque in bloques:
        fila = _fila_desde_palabras(bloque)
        if fila:
            rows.append(fila)
    return _filtrar_columnas(rows, columns)
