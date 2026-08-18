from __future__ import annotations
from services.extractor import _filtrar_columnas, _agrupar_por_lineas, _normalizar_texto, _quitar_tildes

import logging
import re
from typing import Any
import pdfplumber

logger = logging.getLogger(__name__)

_RE_FECHA_CAJA_SOCIAL = re.compile(
    r"^(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+\d{2}$",
    re.IGNORECASE,
)
_RE_MONTO_CAJA_SOCIAL = re.compile(r"^-?[\d,]+\.\d{2}$")

_MESES_CAJA_SOCIAL = {
    "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AGO": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12",
}

# Límites relativos de columnas (fracción del ancho de página). Calibrados
# sobre la plantilla estándar del extracto de Banco Caja Social; si el
# banco cambia el layout del PDF, estos porcentajes son el primer lugar
# a revisar.
_LIMITES_COLUMNAS_CAJA_SOCIAL = {
    "fecha": (0.037, 0.095),
    "transaccion": (0.095, 0.302),
    "documento": (0.302, 0.395),
    "lugar": (0.395, 0.558),
    "debito": (0.558, 0.704),
    "credito": (0.704, 0.839),
    "saldo": (0.839, 0.970),
}


def _parse_monto_caja_social(token: str) -> str:
    """'208,400.00' -> '208400.00'; '-89,207.00' -> '-89207.00'."""
    if not token:
        return ""

    token = token.strip()
    if not _RE_MONTO_CAJA_SOCIAL.match(token):
        return ""

    negativo = token.startswith("-")
    if negativo:
        token = token[1:]
    token = token.replace(",", "")
    return f"-{token}" if negativo else token


def _es_fecha_caja_social(token: str) -> bool:
    """True si el token tiene formato 'JUN 01', 'JUL 15', etc."""
    return bool(_RE_FECHA_CAJA_SOCIAL.match(token.strip()))


def _parse_fila_caja_social(
    fecha: str,
    tokens_transaccion: list[str],
    tokens_documento: list[str],
    tokens_lugar: list[str],
    tokens_debito: list[str],
    tokens_credito: list[str],
    tokens_saldo: list[str],
    year: str,
) -> dict[str, Any] | None:
    """
    Construye un movimiento de Banco Caja Social.
    Estructura: FECHA, TRANSACCIÓN, DOCUMENTO, LUGAR, DÉBITOS, CRÉDITOS, SALDOS.
    """
    if not fecha:
        return None

    fecha = fecha.strip().upper()
    match = re.match(r"^([A-Z]{3})\s+(\d{2})$", fecha)
    if not match:
        return None

    mes_texto, dia = match.group(1), match.group(2)
    mes = _MESES_CAJA_SOCIAL.get(mes_texto)
    if not mes:
        return None

    concepto = _normalizar_texto(" ".join(tokens_transaccion))
    documento = _normalizar_texto(" ".join(tokens_documento))
    lugar = _normalizar_texto(" ".join(tokens_lugar))

    debito = next((v for t in tokens_debito if (v := _parse_monto_caja_social(t))), "")
    credito = next((v for t in tokens_credito if (v := _parse_monto_caja_social(t))), "")
    saldo = next((v for t in tokens_saldo if (v := _parse_monto_caja_social(t))), "")

    if not concepto:
        return None

    fecha_completa = f"{dia}/{mes}/{year}"

    return {
        "DIA": dia,
        "MES": mes,
        "HORA": "",
        "CONCEPTO": concepto,
        "DEBITO": debito,
        "CREDITO": credito,
        "SALDO": saldo,
        "OFICINA_CANAL": lugar,
        "VALOR_UNIDAD": "",
        "UNIDADES": "",
        "TIPO_PARTICIPACION": "",
        "MOVIMIENTO": documento,
        "FECHA_OPERACION": fecha_completa,
        "FECHA_VALOR": fecha_completa,
    }


def extract_extracto_caja_social(
    pdf_path_or_file,
    columns: list[str] | None = None,
    year: str | None = None,
) -> list[dict]:
    """
    Extrae movimientos de un extracto de Banco Caja Social.

    IMPORTANTE sobre `year`: el PDF no siempre expone el año de forma
    estructurada junto a cada fecha ("JUN 01"), así que hay que
    indicarlo explícitamente. Si no se pasa, se usa el año actual del
    sistema y se deja un log de advertencia (antes quedaba fijo en
    "2026" sin ningún aviso, lo cual es incorrecto para cualquier otro
    período y fallaba en silencio).

    Estrategia:
        1. Extrae las palabras del PDF por página.
        2. Agrupa las palabras por línea.
        3. Usa la fecha para detectar el inicio de cada movimiento.
        4. Usa la posición X (relativa al ancho de página) para asignar
        cada palabra a su columna.
        5. Permite que TRANSACCIÓN ocupe varias líneas.
        6. Ignora encabezados / pies de página fuera de la tabla.
    """
    if year is None:
        import datetime
        year = str(datetime.date.today().year)
        logger.warning(
            "[CAJA SOCIAL] no se especificó 'year'; se usa el año actual "
            "(%s) por defecto. Pase year explícitamente si el extracto "
            "corresponde a otro período.", year,
        )

    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue

            page_width = page.width
            limites = {
                nombre: (page_width * xmin, page_width * xmax)
                for nombre, (xmin, xmax) in _LIMITES_COLUMNAS_CAJA_SOCIAL.items()
            }

            def obtener_columna(x: float) -> str | None:
                for nombre, (x_min, x_max) in limites.items():
                    if x_min <= x < x_max:
                        return nombre
                return None

            movimiento_actual: dict | None = None
            en_tabla_movimientos = False

            def guardar_movimiento():
                nonlocal movimiento_actual
                if movimiento_actual is None:
                    return
                row = _parse_fila_caja_social(
                    fecha=movimiento_actual["fecha"],
                    tokens_transaccion=movimiento_actual["transaccion"],
                    tokens_documento=movimiento_actual["documento"],
                    tokens_lugar=movimiento_actual["lugar"],
                    tokens_debito=movimiento_actual["debito"],
                    tokens_credito=movimiento_actual["credito"],
                    tokens_saldo=movimiento_actual["saldo"],
                    year=year,
                )
                if row:
                    rows.append(row)
                movimiento_actual = None

            for linea in _agrupar_por_lineas(words):
                linea = sorted(linea, key=lambda w: w["x0"])
                if not linea:
                    continue

                texto_linea = _normalizar_texto(" ".join(w["text"] for w in linea))
                texto_upper = texto_linea.upper()
                texto_sin_tildes = _quitar_tildes(texto_upper)

                # Inicio de la tabla
                if texto_sin_tildes.startswith("FECHA") and "TRANSACCION" in texto_sin_tildes:
                    en_tabla_movimientos = True
                    continue

                # Fin de la tabla en esta página
                if "CONTINUA EN LA SIGUIENTE PAGINA" in texto_sin_tildes:
                    guardar_movimiento()
                    en_tabla_movimientos = False
                    continue

                # Encabezados / pies de página conocidos a ignorar
                if "DETALLE DE PRODUCTOS" in texto_upper:
                    continue
                if texto_sin_tildes.startswith("CONTINUACION CUENTA"):
                    continue
                if texto_upper == "CUENTA DE AHORROS":
                    continue
                if "PERIODO DEL INFORME" in texto_upper:
                    continue
                if "MAS CREDITOS" in texto_sin_tildes:
                    continue
                if "MENOS DEBITOS" in texto_sin_tildes:
                    continue
                if "INTERESES DEL PERIODO" in texto_upper:
                    continue
                if "NUEVO SALDO" in texto_upper:
                    continue

                if not en_tabla_movimientos:
                    continue

                # Detectar fecha en la línea
                fecha_tokens = [
                    w["text"] for w in linea if obtener_columna(w["x0"]) == "fecha"
                ]
                fecha = _normalizar_texto(" ".join(fecha_tokens)).upper()

                if _es_fecha_caja_social(fecha):
                    guardar_movimiento()
                    movimiento_actual = {
                        "fecha": fecha,
                        "transaccion": [], "documento": [], "lugar": [],
                        "debito": [], "credito": [], "saldo": [],
                    }

                if movimiento_actual is None:
                    continue

                destino_por_columna = {
                    "transaccion": movimiento_actual["transaccion"],
                    "documento": movimiento_actual["documento"],
                    "lugar": movimiento_actual["lugar"],
                    "debito": movimiento_actual["debito"],
                    "credito": movimiento_actual["credito"],
                    "saldo": movimiento_actual["saldo"],
                }

                for w in linea:
                    texto = w["text"].strip()
                    if not texto:
                        continue
                    columna = obtener_columna(w["x0"])
                    destino = destino_por_columna.get(columna)
                    if destino is not None:
                        destino.append(texto)

            guardar_movimiento()

    for row in rows:
        row["CONCEPTO"] = _normalizar_texto(row["CONCEPTO"])
        row["OFICINA_CANAL"] = _normalizar_texto(row["OFICINA_CANAL"])
        row["MOVIMIENTO"] = _normalizar_texto(row["MOVIMIENTO"])

    logger.debug("[CAJA SOCIAL] %d movimientos extraídos", len(rows))
    for i, r in enumerate(rows, 1):
        logger.debug(
            "  %d %s %r DOC=%s LUGAR=%r DEBITO=%s CREDITO=%s SALDO=%s",
            i, r["FECHA_OPERACION"], r["CONCEPTO"], r["MOVIMIENTO"],
            r["OFICINA_CANAL"], r["DEBITO"], r["CREDITO"], r["SALDO"],
        )

    return _filtrar_columnas(rows, columns)
