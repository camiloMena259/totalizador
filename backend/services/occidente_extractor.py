from __future__ import annotations
from typing import Any
from services.extractor import _log_fila_descartada, _filtrar_columnas

import re
import pdfplumber

_TOKEN_DIA_OCC = re.compile(r'^\d{2}$')
_TOKEN_MONTO_OCC = re.compile(r'^[\d.,]+\.\d{2}$')       # "3,167,922.00" / "0.00"
_TOKEN_IDENT_OCC = re.compile(r'^(?=[A-Z0-9]+$)(?=.*\d)[A-Z0-9]{4,}$')

# dia + al menos 1 palabra de concepto + 3 montos
MIN_TOKENS_OCC = 5


def _parse_monto_occidente(token: str) -> str:
    """'3,167,922.00' -> '3167922.00' (quita separadores de miles)."""
    return token.replace(",", "")


def extract_extracto_occidente(pdf_path_or_file, columns: list[str] | None = None) -> list[dict]:
    """
    Extrae movimientos del extracto de Banco de Occidente.

    Devuelve DIA, CONCEPTO, IDENTIFICACION, DEBITO, CREDITO, SALDO
    (MES y HORA quedan vacíos: el formato de origen no los expone,
    pero se incluyen para mantener el esquema común homogéneo).
    """
    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw_line in text.split("\n"):
                tokens = raw_line.split()
                if len(tokens) < MIN_TOKENS_OCC:
                    continue

                dia = tokens[0]
                if not _TOKEN_DIA_OCC.match(dia):
                    continue

                cola = tokens[-3:]
                if not all(_TOKEN_MONTO_OCC.match(tok) for tok in cola):
                    _log_fila_descartada("OCCIDENTE", "cola de montos inválida", tokens)
                    continue

                medio = tokens[1:-3]
                if not medio:
                    continue

                identificacion = ""
                if len(medio) > 1 and _TOKEN_IDENT_OCC.match(medio[-1]):
                    identificacion = medio[-1]
                    concepto = " ".join(medio[:-1]).strip()
                else:
                    concepto = " ".join(medio).strip()

                debito, credito, saldo = cola

                rows.append({
                    "DIA": dia,
                    "MES": "",
                    "HORA": "",
                    "CONCEPTO": concepto,
                    "IDENTIFICACION": identificacion,
                    "DEBITO": _parse_monto_occidente(debito),
                    "CREDITO": _parse_monto_occidente(credito),
                    "SALDO": _parse_monto_occidente(saldo),
                })

    return _filtrar_columnas(rows, columns)