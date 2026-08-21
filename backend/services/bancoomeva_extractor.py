from __future__ import annotations
from services.extractor import _filtrar_columnas, _agrupar_por_lineas 

import logging
import re
import pdfplumber

logger = logging.getLogger(__name__)

_RE_FECHA_BANCOOMEVA = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_RE_MONTO_BANCOOMEVA = re.compile(r"^\$?\s?[\d,]+\.\d{2}$")

_INICIO_DESCRIPCION_BANCOOMEVA = {
    "N/C", "RET", "TRASLADO", "CONSIGNACION", "PAGO", "ABONO", "NC", "NOTA",
}


def _limpiar_monto_bancoomeva(token: str) -> str:
    if not token:
        return ""
    return token.replace("$", "").replace(" ", "").replace(",", "")


def _headers_columnas_bancoomeva(words: list[dict]) -> dict[str, float]:
    headers: dict[str, float] = {}
    for w in words:
        texto = w["text"].strip().lower()
        if texto == "descripcion":
            headers["descripcion"] = w["x0"]
        elif texto == "saldo":
            headers["saldo"] = w["x0"]
    return headers


def extract_extracto_bancoomeva(pdf_path_or_file, columns: list[str] | None = None) -> list[dict]:
    """Extrae movimientos del extracto Bancoomeva."""
    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue

            headers = _headers_columnas_bancoomeva(words)

            # FIX: antes se accedía con headers["descripcion"] / headers["saldo"]
            # directamente, lo que lanzaba KeyError en páginas de continuación
            # sin encabezado (el chequeo de None de abajo nunca se alcanzaba).
            # Con .get() el chequeo sí cumple su función.
            x_descripcion = headers.get("descripcion")
            x_saldo = headers.get("saldo")  # noqa: F841 (se conserva por si se
            # necesita en el futuro para clasificar montos por columna, igual
            # que en BBVA; hoy no se usa para no cambiar el comportamiento).

            if x_descripcion is None or x_saldo is None:
                logger.debug(
                    "[BANCOOMEVA] página sin headers Descripcion/Saldo, se omite"
                )
                continue

            for linea in _agrupar_por_lineas(words):
                linea = sorted(linea, key=lambda w: w["x0"])
                tokens = [w["text"] for w in linea]

                if len(tokens) < 6:
                    continue

                # Todas las filas válidas empiezan por una fecha
                if not _RE_FECHA_BANCOOMEVA.match(tokens[0]):
                    continue
                fecha = tokens[0]

                montos = [w for w in linea if _RE_MONTO_BANCOOMEVA.match(w["text"])]

                # Debe existir Debito, Credito y Saldo
                if len(montos) < 3:
                    continue

                debito = montos[-3]["text"]
                credito = montos[-2]["text"]
                saldo = montos[-1]["text"]
                primer_monto_x = montos[-3]["x0"]

                concepto_tokens = []
                inicio = False

                for w in linea:
                    texto = w["text"].strip()

                    if w["x0"] >= primer_monto_x:  # ya llegamos a los montos
                        break
                    if texto == fecha:  # saltar fecha
                        continue
                    if not re.search(r"[A-Za-zÁÉÍÓÚáéíóúÑñ0-9]", texto):
                        continue  # ignorar símbolos sueltos ($, -, etc.)

                    if texto.upper() in _INICIO_DESCRIPCION_BANCOOMEVA:
                        inicio = True
                    if inicio:
                        concepto_tokens.append(texto)

                concepto = " ".join(concepto_tokens)
                dia, mes, anio = fecha.split("/")

                rows.append({
                    "DIA": dia,
                    "MES": mes,
                    "HORA": "",
                    "CONCEPTO": concepto,
                    "DEBITO": _limpiar_monto_bancoomeva(debito),
                    "CREDITO": _limpiar_monto_bancoomeva(credito),
                    "SALDO": _limpiar_monto_bancoomeva(saldo),
                    "MOVIMIENTO": "",
                    "FECHA_OPERACION": fecha,
                    "FECHA_VALOR": "",
                })

    return _filtrar_columnas(rows, columns)

