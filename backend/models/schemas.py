"""
models/schemas.py
Modelos Pydantic para la API de totalización de extractos.
"""

from pydantic import BaseModel
from typing import List, Optional


class Movimiento(BaseModel):
    dia: str
    concepto: str
    debito: float
    credito: float
    saldo: Optional[float] = None
    etiqueta: str


class ResumenEtiqueta(BaseModel):
    etiqueta: str
    total_debitos: float
    total_creditos: float
    cantidad: int


class TotalizacionResponse(BaseModel):
    movimientos: List[Movimiento]
    resumen_por_etiqueta: List[ResumenEtiqueta]
    total_gravamen: float
    total_intereses: float
    total_debitos: float
    total_creditos: float

