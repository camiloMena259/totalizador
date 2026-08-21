from __future__ import annotations
from typing import Any
from services.extractor import _log_fila_descartada, _filtrar_columnas, _agrupar_por_lineas, _normalizar_texto

import logging
import re
import pdfplumber

logger = logging.getLogger(__name__)

_RE_FECHA_FIDU = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_RE_MONTO_FIDU = re.compile(r"^-?[\d.]+,\d{2}$")
_RE_TIPO_PART_FIDU = re.compile(r"^\d+(?:\.\d{1,2})?$")

# Canales conocidos. NO se usan para determinar la posición de las
# columnas, solo ayudan a identificar el canal cuando conocemos su texto.
CANALES_FIDU = [
    "OFICINA INTERNET",
    "FIDUCIARIA BOGOTA DG1",
]


def _parse_monto_fidu(token: str) -> str:
    """Formato europeo: miles con '.', decimales con ','. Ej: '1.234,56' -> '1234.56'."""
    if not token:
        return ""

    token = token.strip()
    negativo = token.startswith("-")
    if negativo:
        token = token[1:]

    entero, separador, decimal = token.rpartition(",")
    if not separador:
        return ""

    entero_limpio = entero.replace(".", "")
    resultado = f"{entero_limpio}.{decimal}"
    return f"-{resultado}" if negativo else resultado


def _parse_fila_fidu(tokens: list[str]) -> dict[str, Any] | None:
    """
    Parsea una línea que comienza con fecha.

    En Fidubogotá la línea que comienza con fecha contiene todos los
    campos estructurados del movimiento: FECHA, DESCRIPCIÓN, VALOR
    TRANSACCIÓN, CANAL, VALOR UNIDAD, UNIDADES, TIPO PARTICIPACIÓN.
    La descripción puede continuar en líneas posteriores (se agregan
    aparte, ver `extract_extracto_fidubogota`).
    """
    if not tokens:
        return None

    fecha = tokens[0]
    if not _RE_FECHA_FIDU.match(fecha):
        return None

    dia, mes, anio = fecha.split("/")
    resto = tokens[1:]

    if len(resto) < 5:
        _log_fila_descartada("FIDUBOGOTA", "menos de 5 tokens tras la fecha", tokens)
        return None

    tipo_participacion = resto[-1]
    unidades = resto[-2]
    valor_unidad = resto[-3]

    if not _RE_TIPO_PART_FIDU.match(tipo_participacion):
        _log_fila_descartada("FIDUBOGOTA", "tipo de participación inválido", tokens)
        return None
    if not _RE_MONTO_FIDU.match(unidades):
        _log_fila_descartada("FIDUBOGOTA", "unidades inválidas", tokens)
        return None
    if not _RE_MONTO_FIDU.match(valor_unidad):
        _log_fila_descartada("FIDUBOGOTA", "valor unidad inválido", tokens)
        return None

    medio = resto[:-3]
    if not medio:
        return None

    # Buscar el canal conocido.
    canal = ""
    canal_inicio = None
    for candidato in CANALES_FIDU:
        canal_tokens = candidato.split()
        n = len(canal_tokens)
        if len(medio) < n:
            continue
        for i in range(len(medio) - n + 1):
            bloque = medio[i:i + n]
            if [t.upper() for t in bloque] == [t.upper() for t in canal_tokens]:
                canal = candidato
                canal_inicio = i
                break
        if canal_inicio is not None:
            break

    if canal_inicio is not None:
        antes_canal = medio[:canal_inicio]
        if not antes_canal:
            return None

        valor_transaccion = antes_canal[-1]
        if not _RE_MONTO_FIDU.match(valor_transaccion):
            _log_fila_descartada("FIDUBOGOTA", "valor transacción inválido (canal conocido)", tokens)
            return None

        concepto_tokens = antes_canal[:-1]
    else:
        # Canal no conocido: buscamos el primer monto después de la descripción.
        indice_valor = next(
            (i for i, token in enumerate(medio) if _RE_MONTO_FIDU.match(token)),
            None,
        )
        if indice_valor is None:
            _log_fila_descartada("FIDUBOGOTA", "no se encontró valor transacción (canal desconocido)", tokens)
            return None

        valor_transaccion = medio[indice_valor]
        concepto_tokens = medio[:indice_valor]
        canal = " ".join(medio[indice_valor + 1:]).strip()

    concepto = " ".join(concepto_tokens).strip()
    if not concepto:
        return None

    valor_transaccion_num = _parse_monto_fidu(valor_transaccion)
    if not valor_transaccion_num:
        return None

    debito = valor_transaccion_num[1:] if valor_transaccion_num.startswith("-") else ""
    credito = valor_transaccion_num if not valor_transaccion_num.startswith("-") else ""

    return {
        "DIA": dia,
        "MES": mes,
        "HORA": "",
        "CONCEPTO": concepto,
        "DEBITO": debito,
        "CREDITO": credito,
        "SALDO": "",
        "OFICINA_CANAL": canal,
        "VALOR_UNIDAD": _parse_monto_fidu(valor_unidad),
        "UNIDADES": _parse_monto_fidu(unidades),
        "TIPO_PARTICIPACION": tipo_participacion,
        "MOVIMIENTO": "",
        "FECHA_OPERACION": fecha,
        "FECHA_VALOR": fecha,
    }


def extract_extracto_fidubogota(pdf_path_or_file, columns: list[str] | None = None) -> list[dict]:
    """
    Extrae movimientos del extracto Fidubogotá.

    No depende de coordenadas para identificar columnas. Regla principal:
        Línea con FECHA        -> nuevo movimiento
        Línea SIN FECHA        -> continuación de la descripción anterior
        "DETALLE DE RENTABILIDADES" -> fin de movimientos
    """
    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue

            en_detalle_movimientos = False
            ultimo_row: dict | None = None

            for linea in _agrupar_por_lineas(words):
                linea = sorted(linea, key=lambda w: w["x0"])
                tokens = [w["text"] for w in linea]
                if not tokens:
                    continue

                texto_upper = " ".join(tokens).strip().upper()

                if "DETALLE" in texto_upper and "MOVIMIENTOS" in texto_upper:
                    en_detalle_movimientos = True
                    continue

                if not en_detalle_movimientos:
                    continue

                if "DETALLE" in texto_upper and "RENTABILIDADES" in texto_upper:
                    break

                # NUEVO MOVIMIENTO: toda línea que comienza con fecha.
                if _RE_FECHA_FIDU.match(tokens[0]):
                    row = _parse_fila_fidu(tokens)
                    if row:
                        rows.append(row)
                        ultimo_row = row
                    continue

                # CONTINUACIÓN DE DESCRIPCIÓN
                if ultimo_row is not None:
                    texto_extra = " ".join(tokens).strip()
                    if texto_extra:
                        ultimo_row["CONCEPTO"] = (ultimo_row["CONCEPTO"] + " " + texto_extra).strip()

    for row in rows:
        row["CONCEPTO"] = _normalizar_texto(row["CONCEPTO"])
        row["OFICINA_CANAL"] = _normalizar_texto(row["OFICINA_CANAL"])

    logger.debug("[FIDUBOGOTA] %d movimientos extraídos", len(rows))
    for i, r in enumerate(rows, 1):
        logger.debug(
            "  %d %s %r DEBITO=%s CREDITO=%s",
            i, r["FECHA_OPERACION"], r["CONCEPTO"], r["DEBITO"], r["CREDITO"],
        )

    return _filtrar_columnas(rows, columns)

