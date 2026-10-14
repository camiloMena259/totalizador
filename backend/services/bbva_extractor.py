from __future__ import annotations

import logging
import re
from decimal import Decimal

from services.extractor import _agrupar_por_lineas, _filtrar_columnas
from services.pdf_clave import abrir_extracto

logger = logging.getLogger(__name__)

_RE_MOVIMIENTO_BBVA = re.compile(r"^\d{3,7}$")
_RE_FECHA_BBVA = re.compile(r"^\d{2}-\d{2}-\d{4}$")
_RE_MONTO_BBVA = re.compile(r"^[\d.,]+\.\d{2}$")

# "Cargos" y "Abonos" del cuadro de resumen quedan a la izquierda.
# Los encabezados de la tabla de movimientos están sobre las columnas de monto.
_X_MIN_COLUMNA_MONTO = 0.35


def _limpiar_monto_bbva(token: str) -> str:
    if not token:
        return ""
    return token.replace(",", "")


def _decimal_bbva(token: str) -> Decimal:
    return Decimal(_limpiar_monto_bbva(token))


def _headers_columnas_bbva(words: list[dict]) -> dict[str, float]:
    """Posición x0 de Cargos, Abonos y Saldo. Se recalcula por página."""
    headers: dict[str, float] = {}
    for w in words:
        texto = w["text"].strip().lower().rstrip(":")
        if texto in ("cargos", "abonos", "saldo") and texto not in headers:
            headers[texto] = w["x0"]
    return headers


def _columnas_monto(
    headers: dict[str, float], ancho: float
) -> tuple[float | None, float | None]:
    """
    Encabezados de Cargos y Abonos solo si están en la zona de montos
    y separados entre sí. El resumen del extracto repite esas palabras
    a la izquierda y no sirven para clasificar la fila.
    """
    x_cargo = headers.get("cargos")
    x_abono = headers.get("abonos")
    if x_cargo is None or x_abono is None:
        return None, None

    limite = ancho * _X_MIN_COLUMNA_MONTO
    if x_cargo < limite or x_abono < limite or abs(x_cargo - x_abono) < 15:
        return None, None
    return x_cargo, x_abono


def _datos_fila_bbva(tokens: list[str]) -> tuple[str, str, str] | None:
    """
    Consecutivo, fecha de operación y fecha valor.

    El consecutivo va de 3 a 7 dígitos. Si el banco lo omite (el abono
    de intereses al cierre suele venir así), la fila empieza por las dos fechas.
    """
    if (
        len(tokens) >= 3
        and _RE_MOVIMIENTO_BBVA.match(tokens[0])
        and _RE_FECHA_BBVA.match(tokens[1])
        and _RE_FECHA_BBVA.match(tokens[2])
    ):
        return tokens[0], tokens[1], tokens[2]

    if (
        len(tokens) >= 2
        and _RE_FECHA_BBVA.match(tokens[0])
        and _RE_FECHA_BBVA.match(tokens[1])
    ):
        return "", tokens[0], tokens[1]

    return None


def _saldo_cierre_anterior(lineas: list[list[dict]]) -> Decimal | None:
    """Saldo con el que abre el período, para saber si el primer monto es cargo o abono."""
    for linea in lineas:
        textos = [w["text"].upper().rstrip(":") for w in linea]
        if not {"SALDO", "CIERRE", "ANTERIOR"} <= set(textos):
            continue
        for w in sorted(linea, key=lambda item: item["x0"]):
            if _RE_MONTO_BBVA.match(w["text"]):
                return _decimal_bbva(w["text"])
    return None


def _es_abono(
    monto: Decimal,
    saldo_anterior: Decimal | None,
    saldo_actual: Decimal,
    x0: float,
    x_cargo: float | None,
    x_abono: float | None,
) -> bool:
    """Un abono acerca el saldo hacia arriba; un cargo lo reduce."""
    if x_cargo is not None and x_abono is not None:
        return abs(x0 - x_abono) <= abs(x0 - x_cargo)

    if saldo_anterior is None:
        logger.warning(
            "[BBVA] monto %s sin columna Cargos/Abonos ni saldo anterior; "
            "se clasifica como CARGO.",
            monto,
        )
        return False

    delta = saldo_actual - saldo_anterior
    return abs(delta - monto) < abs(delta + monto)


def _fila_bbva(
    *,
    linea: list[dict],
    tokens: list[str],
    saldo_anterior: Decimal | None,
    x_cargo: float | None,
    x_abono: float | None,
) -> tuple[dict, Decimal] | None:
    datos = _datos_fila_bbva(tokens)
    if datos is None:
        return None

    movimiento, fecha_operacion, fecha_valor = datos
    corte = 3 if movimiento else 2

    montos = [w for w in linea if _RE_MONTO_BBVA.match(w["text"])]
    if len(montos) < 2:
        return None

    saldo_w = max(montos, key=lambda w: w["x0"])
    saldo_actual = _decimal_bbva(saldo_w["text"])
    extras = [w for w in montos if w is not saldo_w]

    cargo = ""
    abono = ""
    for w in extras:
        monto = _decimal_bbva(w["text"])
        if _es_abono(monto, saldo_anterior, saldo_actual, w["x0"], x_cargo, x_abono):
            abono = w["text"]
        else:
            cargo = w["text"]

    concepto = " ".join(
        w["text"] for w in linea[corte:] if w not in montos
    ).strip()
    dia, mes, _anio = fecha_operacion.split("-")

    fila = {
        "DIA": dia,
        "MES": mes,
        "HORA": "",
        "CONCEPTO": concepto,
        "DEBITO": _limpiar_monto_bbva(cargo),
        "CREDITO": _limpiar_monto_bbva(abono),
        "SALDO": _limpiar_monto_bbva(saldo_w["text"]),
        "MOVIMIENTO": movimiento,
        "FECHA_OPERACION": fecha_operacion,
        "FECHA_VALOR": fecha_valor,
    }
    return fila, saldo_actual


def extract_extracto_bbva(pdf_path_or_file, columns: list[str] | None = None) -> list[dict]:
    """Extrae movimientos del extracto BBVA (tabla de transacciones)."""
    rows: list[dict] = []
    saldo_anterior: Decimal | None = None

    with abrir_extracto(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue

            lineas = [
                sorted(linea, key=lambda w: w["x0"])
                for linea in _agrupar_por_lineas(words)
            ]
            if saldo_anterior is None:
                saldo_anterior = _saldo_cierre_anterior(lineas)

            x_cargo, x_abono = _columnas_monto(
                _headers_columnas_bbva(words), page.width
            )

            for linea in lineas:
                tokens = [w["text"] for w in linea]
                if len(tokens) < 4:
                    continue

                resultado = _fila_bbva(
                    linea=linea,
                    tokens=tokens,
                    saldo_anterior=saldo_anterior,
                    x_cargo=x_cargo,
                    x_abono=x_abono,
                )
                if resultado is None:
                    continue

                fila, saldo_anterior = resultado
                rows.append(fila)

    return _filtrar_columnas(rows, columns)
