"""
services/totalizer.py
Toma movimientos ya clasificados (con ETIQUETA) y produce:
  - el listado de movimientos normalizado
  - el resumen totalizado por etiqueta
  - los totales puntuales de GRAVAMEN e INTERESES que pidió el usuario
"""

from collections import defaultdict
from typing import List, Dict

from models.schemas import Movimiento, ResumenEtiqueta, TotalizacionResponse


def _to_float(valor) -> float:
    """
    El extractor ya entrega los montos limpios como 'entero.centavos'
    (ej. '34288.00'), así que aquí solo se convierte directo a float.
    """
    if valor in (None, ""):
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    try:
        return float(valor)
    except ValueError:
        return 0.0


def totalizar(rows: List[Dict]) -> TotalizacionResponse:
    resumen = defaultdict(lambda: {"total_debitos": 0.0, "total_creditos": 0.0, "cantidad": 0})
    movimientos: List[Movimiento] = []
    total_debitos = 0.0
    total_creditos = 0.0

    for row in rows:
        debito = _to_float(row.get("DEBITO"))
        credito = _to_float(row.get("CREDITO"))
        saldo_raw = row.get("SALDO")
        saldo = _to_float(saldo_raw) if saldo_raw else None
        etiqueta = row.get("ETIQUETA", "OTROS")

        movimientos.append(Movimiento(
            dia=row.get("DIA", ""),
            concepto=row.get("CONCEPTO", ""),
            debito=debito,
            credito=credito,
            saldo=saldo,
            etiqueta=etiqueta,
        ))

        resumen[etiqueta]["total_debitos"] += debito
        resumen[etiqueta]["total_creditos"] += credito
        resumen[etiqueta]["cantidad"] += 1

        total_debitos += debito
        total_creditos += credito

    resumen_por_etiqueta = [
        ResumenEtiqueta(
            etiqueta=etiqueta,
            total_debitos=valores["total_debitos"],
            total_creditos=valores["total_creditos"],
            cantidad=valores["cantidad"],
        )
        for etiqueta, valores in sorted(resumen.items())
    ]

    # El gravamen (4x1000) y los intereses casi siempre aparecen como
    # débito y crédito respectivamente, pero se suman ambos lados por
    # seguridad en caso de que el banco los reporte al revés.
    total_gravamen = resumen.get("GRAVAMEN", {}).get("total_debitos", 0.0) \
        + resumen.get("GRAVAMEN", {}).get("total_creditos", 0.0)
    total_intereses = resumen.get("INTERESES", {}).get("total_creditos", 0.0) \
        + resumen.get("INTERESES", {}).get("total_debitos", 0.0)

    return TotalizacionResponse(
        movimientos=movimientos,
        resumen_por_etiqueta=resumen_por_etiqueta,
        total_gravamen=total_gravamen,
        total_intereses=total_intereses,
        total_debitos=total_debitos,
        total_creditos=total_creditos,
    )
