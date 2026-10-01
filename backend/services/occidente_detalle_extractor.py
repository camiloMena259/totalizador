from __future__ import annotations

from services.detalle_portal import extract_detalle_portal
from services.extractor import _normalizar_texto


def extract_detalle_occidente(pdf_path_or_file, columns: list[str] | None = None) -> list[dict]:
    """
    Extrae el detalle de movimientos de Banco de Occidente.

    El PDF es el reporte del portal (Fecha, Transacción, Nro. Documento,
    Débitos, Créditos), no el extracto mensual de una sola línea por movimiento.
    """
    return extract_detalle_portal(
        pdf_path_or_file,
        banco="OCCIDENTE",
        limpiar_transaccion=_normalizar_texto,
        columns=columns,
    )
