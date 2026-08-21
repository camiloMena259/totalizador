from __future__ import annotations
from typing import Any
from services.extractor import _log_fila_descartada, _filtrar_columnas

import logging
import re
import pdfplumber

logger = logging.getLogger(__name__)

_RE_DIA_MES_DAVIVIENDA = re.compile(r'^\d{2}$')                      # "04", "05"
_RE_DOC_DAVIVIENDA = re.compile(r'^\d{3,6}$')                         # "5902"
_RE_MONTO_DAVIVIENDA = re.compile(r'^\$[\d,]+\.\d{2}[+-]$')           # "$103,800.00+"

# Frases conocidas de "Clase de Movimiento". Se matchean por prefijo
# exacto (tokenizado) contra el inicio del texto intermedio. Lista
# corta a propósito: solo lo observado en la muestra real. Ampliar
# a medida que aparezcan clases nuevas (quedan logueadas como
# advertencia cuando no se reconocen).
CLASES_DAVIVIENDA = [
    "Consignacion Efectivo en Oficina",
    "Abono Por Pago Factura",
]


def _limpiar_monto_davivienda(token: str) -> str:
    """'$1,080,000.00+' -> '1080000.00' (el signo +/- se usa aparte para clasificar)."""
    if not token:
        return ""
    return token.replace("$", "").replace(",", "").rstrip("+-")


def _match_clase_davivienda(medio: list[str]) -> tuple[str, int] | None:
    """Busca la clase de movimiento conocida más larga al inicio de `medio`."""
    mejor: tuple[str, int] | None = None
    for clase in CLASES_DAVIVIENDA:
        clase_tokens = clase.split()
        n = len(clase_tokens)
        if len(medio) < n:
            continue
        if [t.lower() for t in medio[:n]] == [t.lower() for t in clase_tokens]:
            if mejor is None or n > mejor[1]:
                mejor = (clase, n)
    return mejor


def _parse_fila_davivienda(buffer: list[str], year: str) -> dict[str, Any] | None:
    if len(buffer) < 5:
        return None
    if not (_RE_DIA_MES_DAVIVIENDA.match(buffer[0]) and _RE_DIA_MES_DAVIVIENDA.match(buffer[1])):
        return None
    if not (
        _RE_DOC_DAVIVIENDA.match(buffer[-3])
        and _RE_MONTO_DAVIVIENDA.match(buffer[-2])
        and _RE_MONTO_DAVIVIENDA.match(buffer[-1])
    ):
        return None

    dia, mes = buffer[0], buffer[1]
    documento, valor, saldo = buffer[-3], buffer[-2], buffer[-1]
    medio = buffer[2:-3]  # Clase de Movimiento + Oficina, sin separador fijo

    match = _match_clase_davivienda(medio)
    if match is None:
        logger.warning(
            "[DAVIVIENDA] 'Clase de Movimiento' no reconocida, se deja todo "
            "como CONCEPTO y OFICINA vacía (agregar a CLASES_DAVIVIENDA): %r",
            " ".join(medio),
        )
        concepto = " ".join(medio).strip()
        oficina = ""
    else:
        _clase, n = match
        idx = n
        concepto_tokens = medio[:n]

        # Caso observado: "Abono Por Pago Factura" viene seguido del
        # número de factura (token largo solo dígitos) antes de la
        # Oficina. Se conserva como parte del concepto.
        if idx < len(medio) and medio[idx].isdigit() and len(medio[idx]) >= 6:
            concepto_tokens = concepto_tokens + [medio[idx]]
            idx += 1

        concepto = " ".join(concepto_tokens).strip()
        oficina = " ".join(medio[idx:]).strip()

    if not concepto:
        _log_fila_descartada("DAVIVIENDA", "concepto vacío", buffer)
        return None

    signo_valor = valor[-1]  # '+' o '-'
    tipo = "CREDITO" if signo_valor == "+" else "DEBITO"
    valor_limpio = _limpiar_monto_davivienda(valor)

    return {
        "DIA": dia,
        "MES": mes,
        "HORA": "",
        "CONCEPTO": concepto,
        "DEBITO": valor_limpio if tipo == "DEBITO" else "",
        "CREDITO": valor_limpio if tipo == "CREDITO" else "",
        "SALDO": _limpiar_monto_davivienda(saldo),
        "OFICINA_CANAL": oficina,
        "MOVIMIENTO": documento,
        "FECHA_OPERACION": f"{dia}/{mes}/{year}",
        "FECHA_VALOR": f"{dia}/{mes}/{year}",
    }


def extract_extracto_davivienda(
    pdf_path_or_file,
    columns: list[str] | None = None,
    year: str | None = None,
) -> list[dict]:
    """
    Extrae movimientos del extracto de Davivienda.

    La fecha viene como dos tokens sueltos "DD MM" sin año, así que
    (igual que Bogotá y Caja Social) se requiere `year`. El signo al
    final de Valor/Saldo ('+' / '-') es quien determina si el
    movimiento es CREDITO o DEBITO — a diferencia de Bogotá, aquí sí
    hay una señal explícita y no hace falta adivinar por texto.
    """
    if year is None:
        import datetime
        year = str(datetime.date.today().year)
        logger.warning(
            "[DAVIVIENDA] no se especificó 'year'; se usa el año actual "
            "(%s) por defecto. Pase year explícitamente si el extracto "
            "corresponde a otro período.", year,
        )

    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            buffer: list[str] = []

            for raw_line in text.split("\n"):
                tokens = raw_line.split()
                if not tokens:
                    continue

                es_inicio_fila = (
                    len(tokens) > 1
                    and _RE_DIA_MES_DAVIVIENDA.match(tokens[0])
                    and _RE_DIA_MES_DAVIVIENDA.match(tokens[1])
                )

                if es_inicio_fila:
                    if buffer:
                        _log_fila_descartada("DAVIVIENDA", "fila sin cierre antes de la siguiente fecha", buffer)
                    buffer = tokens
                else:
                    if not buffer:
                        continue
                    buffer.extend(tokens)

                row = _parse_fila_davivienda(buffer, year)
                if row:
                    rows.append(row)
                    buffer = []

            if buffer:
                _log_fila_descartada("DAVIVIENDA", "fila sin cierre al final de la página", buffer)

    return _filtrar_columnas(rows, columns)