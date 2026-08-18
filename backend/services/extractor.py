from __future__ import annotations

import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


# ESQUEMA COMÚN

# Columnas que TODOS los extractores garantizan.
COLUMNAS_BASE = [
    "DIA", "MES", "HORA", "CONCEPTO", "DEBITO", "CREDITO", "SALDO",
]

# Columnas adicionales que algunos bancos agregan (BBVA, AV Villas,
# Bancoomeva, Fidubogotá, Caja Social). Si se piden vía `columns` y el
# banco no las produce, quedan como "".
COLUMNAS_EXTENDIDAS = [
    "IDENTIFICACION", "MOVIMIENTO", "FECHA_OPERACION", "FECHA_VALOR",
    "OFICINA_CANAL", "VALOR_UNIDAD", "UNIDADES", "TIPO_PARTICIPACION",
]


# UTILIDADES COMUNES (antes duplicadas en cada bloque de banco)

def _agrupar_por_lineas(words: list[dict], y_tolerance: float = 3) -> list[list[dict]]:
    """
    Agrupa palabras extraídas por pdfplumber (`page.extract_words`) en
    líneas visuales, según su coordenada vertical ("top").

    Esta función reemplaza las versiones casi idénticas que existían
    por separado para BBVA, AV Villas, Bancoomeva, Fidubogotá y Caja
    Social (`_agrupar_por_linea_bbva`, `_agrupar_por_linea_avv`, etc.).
    """
    lineas: list[list[dict]] = []
    actual: list[dict] = []
    last_top = None

    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if last_top is None or abs(w["top"] - last_top) <= y_tolerance:
            actual.append(w)
        else:
            lineas.append(actual)
            actual = [w]
        last_top = w["top"]

    if actual:
        lineas.append(actual)

    return lineas


def _filtrar_columnas(rows: list[dict], columns: list[str] | None) -> list[dict]:
    """
    Proyecta cada fila sobre el subconjunto de columnas solicitado.
    Antes este bloque estaba copiado y pegado en las 7 funciones.
    """
    if not columns:
        return rows
    return [{col: row.get(col, "") for col in columns} for row in rows]

def _normalizar_texto(texto: str) -> str:
    """Colapsa espacios repetidos / saltos de línea en un texto plano."""
    return re.sub(r"\s+", " ", texto).strip()

def _quitar_tildes(texto: str) -> str:
    """Elimina tildes para comparar texto de forma resistente a variaciones del PDF."""
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")

def _log_fila_descartada(banco: str, motivo: str, tokens: list[str]) -> None:
    """
    Centraliza el log de filas descartadas o campos que no se pudieron
    clasificar. Antes esto pasaba en silencio (AV Villas, BBVA fallback,
    Fidubogotá) y hacía imposible saber por qué faltaba un movimiento.
    """
    logger.debug("[%s] fila descartada (%s): %r", banco, motivo, tokens)
