from __future__ import annotations
from services.extractor import _log_fila_descartada, _filtrar_columnas

import re
import pdfplumber

_TOKEN_FECHA = re.compile(r'^\d{2}$')       # "05", "01"...
_TOKEN_ENTERO = re.compile(r'^[\d.,]+$')    # "3,663,764" / "0"
_TOKEN_CENTAVOS = re.compile(r'^\d{2}$')    # "79" / "00"

# mes, dia, hora + al menos 1 token de concepto + 6 tokens de montos
MIN_TOKENS = 10


def _parse_monto(entero: str, centavos: str) -> str:
    entero_limpio = entero.replace(".", "").replace(",", "")
    return f"{entero_limpio}.{centavos}"


def extract_extracto_popular(pdf_path_or_file, columns: list[str] | None = None) -> list[dict]:
    """
    Extrae movimientos del extracto de Banco Popular.

    Formato de línea esperado (tokens separados por espacio):
        MES DIA HORA CONCEPTO... DEBITO_ENTERO DEBITO_CENT CREDITO_ENTERO
        CREDITO_CENT SALDO_ENTERO SALDO_CENT
    """
    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.split("\n"):
                tokens = raw_line.split()
                if len(tokens) < MIN_TOKENS:
                    continue

                mes, dia = tokens[0], tokens[1]
                if not (_TOKEN_FECHA.match(mes) and _TOKEN_FECHA.match(dia)):
                    continue

                cola = tokens[-6:]
                if not (
                    _TOKEN_ENTERO.match(cola[0]) and _TOKEN_CENTAVOS.match(cola[1]) and
                    _TOKEN_ENTERO.match(cola[2]) and _TOKEN_CENTAVOS.match(cola[3]) and
                    _TOKEN_ENTERO.match(cola[4]) and _TOKEN_CENTAVOS.match(cola[5])
                ):
                    _log_fila_descartada("POPULAR", "cola de montos inválida", tokens)
                    continue

                hora = tokens[2]
                concepto = " ".join(tokens[3:-6]).strip()

                rows.append({
                    "DIA": dia,
                    "MES": mes,
                    "HORA": hora,
                    "CONCEPTO": concepto,
                    "DEBITO": _parse_monto(cola[0], cola[1]),
                    "CREDITO": _parse_monto(cola[2], cola[3]),
                    "SALDO": _parse_monto(cola[4], cola[5]),
                })

    return _filtrar_columnas(rows, columns)