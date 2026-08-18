from __future__ import annotations
from services.extractor import _filtrar_columnas, _agrupar_por_lineas 

import logging
import re
import pdfplumber

logger = logging.getLogger(__name__)

_RE_MOVIMIENTO_BBVA = re.compile(r'^\d{4,7}$')
_RE_FECHA_BBVA = re.compile(r'^\d{2}-\d{2}-\d{4}$')
_RE_MONTO_BBVA = re.compile(r'^[\d.,]+\.\d{2}$')


def _limpiar_monto_bbva(token: str) -> str:
    if not token:
        return ""
    return token.replace(",", "")


def _headers_columnas_bbva(words: list[dict]) -> dict[str, float]:
    """
    Ubica la posición x0 de los headers 'Cargos' y 'Abonos' en la página
    para usarlos como referencia y clasificar montos sueltos por columna.
    Se recalcula por página porque el header no siempre se repite igual.
    """
    headers: dict[str, float] = {}
    for w in words:
        texto = w["text"].strip().lower().rstrip(":")
        if texto in ("cargos", "abonos", "saldo") and texto not in headers:
            headers[texto] = w["x0"]
    return headers


def extract_extracto_bbva(pdf_path_or_file, columns: list[str] | None = None) -> list[dict]:
    """Extrae movimientos del extracto BBVA (tabla 'Detalles de transacciones')."""
    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue

            headers = _headers_columnas_bbva(words)
            x_cargo = headers.get("cargos")
            x_abono = headers.get("abonos")

            for linea in _agrupar_por_lineas(words):
                linea = sorted(linea, key=lambda w: w["x0"])
                tokens = [w["text"] for w in linea]

                if len(tokens) < 5:
                    continue
                if not _RE_MOVIMIENTO_BBVA.match(tokens[0]):
                    continue
                if not (_RE_FECHA_BBVA.match(tokens[1]) and _RE_FECHA_BBVA.match(tokens[2])):
                    continue

                movimiento = tokens[0]
                fecha_operacion = tokens[1]
                fecha_valor = tokens[2]

                montos = [w for w in linea if _RE_MONTO_BBVA.match(w["text"])]
                if not montos:
                    continue

                # El saldo siempre es el monto más a la derecha de la fila.
                saldo_w = max(montos, key=lambda w: w["x0"])
                extras = [w for w in montos if w is not saldo_w]

                cargo = ""
                abono = ""
                for w in extras:
                    if x_cargo is not None and x_abono is not None:
                        if abs(w["x0"] - x_cargo) <= abs(w["x0"] - x_abono):
                            cargo = w["text"]
                        else:
                            abono = w["text"]
                    else:
                        # Sin headers detectados en la página (ej. página de
                        # continuación): no podemos saber con certeza si es
                        # cargo o abono. Se deja constancia en el log en vez
                        # de asumir "cargo" en silencio como antes, para que
                        # el dato dudoso sea auditable.
                        logger.warning(
                            "[BBVA] monto %s sin headers Cargos/Abonos en la "
                            "página; se clasifica como CARGO por defecto "
                            "(revisar manualmente). Fila: %r",
                            w["text"], tokens,
                        )
                        cargo = w["text"]

                concepto_tokens = [
                    w["text"] for w in linea
                    if w not in linea[:3] and w not in montos
                ]
                concepto = " ".join(concepto_tokens).strip()

                dia, mes, _anio = fecha_operacion.split("-")

                rows.append({
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
                })

    return _filtrar_columnas(rows, columns)

