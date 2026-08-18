from __future__ import annotations
from services.extractor import _filtrar_columnas, _agrupar_por_lineas 

import logging
import re
import pdfplumber

logger = logging.getLogger(__name__)

_RE_FECHA_AVV = re.compile(r"^\d{4}/\d{2}/\d{2}$")
_RE_MONTO_AVV = re.compile(r"^\$?[\d,]+\.\d{2}$")

REGLAS_AVV = {
    "DEB": "DEBITO",
    "NOTA CREDITO": "CREDITO",
    "CRE": "CREDITO",
    "CREDITO": "CREDITO",
    "DEBITO": "DEBITO",
    "NOTA DEBITO": "DEBITO",
    "REND": "CREDITO",
}


def _limpiar_monto_avv(token: str) -> str:
    if not token:
        return ""
    return token.replace("$", "").replace(",", "")


def _clasificar_movimiento_avv(detalle: str) -> str:
    texto = detalle.upper()
    for prefijo, tipo in REGLAS_AVV.items():
        if texto.startswith(prefijo):
            return tipo
    return ""


def extract_extracto_avvillas(pdf_path_or_file, columns: list[str] | None = None) -> list[dict]:
    """Extrae movimientos del extracto de Banco AV Villas (tabla 'Movimientos')."""
    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue

            for linea in _agrupar_por_lineas(words):
                linea = sorted(linea, key=lambda w: w["x0"])
                tokens = [w["text"] for w in linea]

                if len(tokens) < 4:
                    continue

                # La fila siempre inicia por la fecha
                if not _RE_FECHA_AVV.match(tokens[0]):
                    continue
                fecha = tokens[0]

                montos = [w for w in linea if _RE_MONTO_AVV.match(w["text"])]
                if len(montos) < 2:
                    continue

                valor = montos[-2]
                saldo = montos[-1]
                detalle_tokens = [
                    w["text"] for w in linea
                    if w["text"] != fecha and w not in montos
                ]
                detalle = " ".join(detalle_tokens).strip()

                tipo = _clasificar_movimiento_avv(detalle)
                credito = ""
                debito = ""
                if tipo == "CREDITO":
                    credito = _limpiar_monto_avv(valor["text"])
                elif tipo == "DEBITO":
                    debito = _limpiar_monto_avv(valor["text"])
                else:
                    # Antes esto se perdía en silencio (DEBITO y CREDITO
                    # quedaban vacíos sin ningún rastro). Se deja el log
                    # para poder ampliar REGLAS_AVV con el prefijo que falte.
                    logger.warning(
                        "[AV VILLAS] no se pudo clasificar el movimiento "
                        "como DEBITO/CREDITO (prefijo desconocido): %r",
                        detalle,
                    )

                anio, mes, dia = fecha.split("/")
                rows.append({
                    "DIA": dia,
                    "MES": mes,
                    "HORA": "",
                    "CONCEPTO": detalle,
                    "DEBITO": debito,
                    "CREDITO": credito,
                    "SALDO": _limpiar_monto_avv(saldo["text"]),
                    "MOVIMIENTO": "",
                    "FECHA_OPERACION": fecha,
                    "FECHA_VALOR": fecha,
                })

    return _filtrar_columnas(rows, columns)