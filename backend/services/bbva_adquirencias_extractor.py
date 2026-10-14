"""
Extracto de adquirencias BBVA.

Cada fila del detalle es una venta con tarjeta. El PDF puede imprimir ese
detalle dos veces. La copia se descarta solo cuando las compras de las filas
únicas cuadran con el total "Compras" del encabezado. Si el encabezado cuadra
con todas las filas, se conservan: son ventas repetidas de verdad.

De cada venta salen movimientos separados por columna (compra, IVA, propina,
comisión y retenciones) para que el clasificador del totalizador les ponga
etiqueta. El valor abonado no se emite: es el neto de esos importes.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from services.extractor import _filtrar_columnas, _log_fila_descartada
from services.pdf_clave import abrir_extracto

logger = logging.getLogger(__name__)

_BANCO = "BBVA ADQUIRENCIAS"
_CENTAVO = Decimal("0.01")

_RE_FECHA = re.compile(r"^(0[1-9]|[12]\d|3[01])/(0[1-9]|1[0-2])/(\d{2})$")
_RE_FRANQUICIA = re.compile(r"^[A-Z]{2}$")
_RE_ESTABLECIMIENTO = re.compile(r"^\d+$")
_RE_TOTAL_COMPRAS = re.compile(r"Compras:\s*([\d.,]+)", re.IGNORECASE)

_FRANQUICIAS = {
    "VS": "VISA",
    "MC": "MASTERCARD",
    "AE": "AMERICAN EXPRESS",
}

# Mismo orden que las columnas de importe, sin Vr Abono.
# "RETEIVA" no se usa como texto: la regla IVA matchea ese substring
# antes de que RETENCION pueda verlo.
_IMPORTES = (
    ("COMPRA", "CREDITO"),
    ("IVA", "CREDITO"),
    ("PROPINA", "CREDITO"),
    ("COMISION", "DEBITO"),
    ("RETENCION I.V.A", "DEBITO"),
    ("RETEFUENTE", "DEBITO"),
    ("RETEICA", "DEBITO"),
)

_MONTOS = 8
_MIN_TOKENS = _MONTOS + 5


@dataclass(frozen=True)
class _Liquidacion:
    dia: str
    mes: str
    fecha_abono: str
    fecha_operacion: str
    franquicia: str
    autorizacion: str
    establecimiento: str
    compras: Decimal
    montos: tuple[Decimal, ...]
    valor_abono: Decimal

    @property
    def clave(self) -> tuple:
        return (
            self.fecha_abono,
            self.fecha_operacion,
            self.franquicia,
            self.autorizacion,
            self.establecimiento,
            tuple(_texto_monto(valor) for valor in self.montos),
            _texto_monto(self.valor_abono),
        )


def _anio(yy: str) -> str:
    corto = int(yy)
    return str(2000 + corto if corto < 70 else 1900 + corto)


def _texto_monto(valor: Decimal) -> str:
    return format(valor.quantize(_CENTAVO, rounding=ROUND_HALF_UP), "f")


def _parsear_monto(token: str) -> Decimal | None:
    """Acepta 1,234,567.89, 1.234.567,89, 1.080.000 y negativos entre paréntesis."""
    texto = token.strip().replace("$", "").replace(" ", "")
    if not texto or texto in {"-", ".", ",", "-.", "-,"}:
        return None

    negativo = texto.startswith("(") and texto.endswith(")")
    texto = texto.strip("()")
    if texto.startswith("-"):
        negativo = True
        texto = texto[1:]

    texto = "".join(caracter for caracter in texto if caracter.isdigit() or caracter in ",.")
    if not texto or texto in {".", ","}:
        return None

    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto:
        partes = texto.split(",")
        if len(partes[-1]) == 2:
            texto = texto.replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif texto.count(".") > 1:
        texto = texto.replace(".", "")

    if negativo:
        texto = "-" + texto
    try:
        return Decimal(texto).quantize(_CENTAVO, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _partir_fecha(token: str) -> tuple[str, str, str] | None:
    match = _RE_FECHA.match(token)
    if match is None:
        return None
    dia, mes, yy = match.groups()
    return dia, mes, f"{dia}/{mes}/{_anio(yy)}"


def _liquidacion(linea: str) -> _Liquidacion | None:
    """
    Fecha de abono, fecha de operación, franquicia, autorización,
    establecimiento y ocho importes. La autorización puede ocupar
    más de un token.
    """
    tokens = linea.split()
    if len(tokens) < _MIN_TOKENS:
        return None

    abono = _partir_fecha(tokens[0])
    operacion = _partir_fecha(tokens[1])
    if abono is None or operacion is None:
        return None

    franquicia = tokens[2].upper()
    if not _RE_FRANQUICIA.match(franquicia):
        return None

    montos: list[Decimal] = []
    for token in tokens[-_MONTOS:]:
        valor = _parsear_monto(token)
        if valor is None:
            return None
        montos.append(valor)

    establecimiento = tokens[-_MONTOS - 1]
    if not _RE_ESTABLECIMIENTO.match(establecimiento):
        return None

    autorizacion = " ".join(tokens[3:-_MONTOS - 1]).strip().upper()
    if not autorizacion:
        return None

    dia, mes, fecha_abono = abono
    return _Liquidacion(
        dia=dia,
        mes=mes,
        fecha_abono=fecha_abono,
        fecha_operacion=operacion[2],
        franquicia=_FRANQUICIAS.get(franquicia, franquicia),
        autorizacion=autorizacion,
        establecimiento=establecimiento,
        compras=montos[0],
        montos=tuple(montos[: len(_IMPORTES)]),
        valor_abono=montos[-1],
    )


def _cuadra(liquidacion: _Liquidacion) -> bool:
    compras, iva, propina, comision, reteiva, retefuente, reteica = liquidacion.montos
    neto = compras + iva + propina - comision - reteiva - retefuente - reteica
    return neto == liquidacion.valor_abono


def _total_compras(texto: str) -> Decimal | None:
    match = _RE_TOTAL_COMPRAS.search(texto or "")
    if match is None:
        return None
    return _parsear_monto(match.group(1))


def _unicas(liquidaciones: list[_Liquidacion]) -> list[_Liquidacion]:
    vistas: set[tuple] = set()
    resultado: list[_Liquidacion] = []
    for liquidacion in liquidaciones:
        if liquidacion.clave in vistas:
            continue
        vistas.add(liquidacion.clave)
        resultado.append(liquidacion)
    return resultado


def _suma_compras(liquidaciones: list[_Liquidacion]) -> Decimal:
    return sum((liquidacion.compras for liquidacion in liquidaciones), Decimal("0.00"))


def _todo_duplicado(liquidaciones: list[_Liquidacion]) -> bool:
    conteo: dict[tuple, int] = {}
    for liquidacion in liquidaciones:
        conteo[liquidacion.clave] = conteo.get(liquidacion.clave, 0) + 1
    return bool(conteo) and all(veces == 2 for veces in conteo.values())


def _resolver_copia_repetida(
    liquidaciones: list[_Liquidacion],
    total_cabecera: Decimal | None,
) -> list[_Liquidacion]:
    if not liquidaciones:
        return []

    unicas = _unicas(liquidaciones)
    suma_todas = _suma_compras(liquidaciones)
    suma_unicas = _suma_compras(unicas)

    if total_cabecera is not None and suma_unicas == total_cabecera and suma_todas != total_cabecera:
        logger.info(
            "[%s] el PDF repite el detalle. Se deja una copia (%s ventas) porque cuadra con Compras %s.",
            _BANCO,
            len(unicas),
            total_cabecera,
        )
        return unicas

    if total_cabecera is None and len(unicas) < len(liquidaciones) and _todo_duplicado(liquidaciones):
        logger.info(
            "[%s] sin total de compras en cabecera. Cada venta venía repetida; se deja una copia (%s).",
            _BANCO,
            len(unicas),
        )
        return unicas

    if total_cabecera is not None and suma_todas != total_cabecera and suma_unicas != total_cabecera:
        logger.warning(
            "[%s] Compras de cabecera %s no cuadra ni con el detalle (%s) ni con una sola copia (%s).",
            _BANCO,
            total_cabecera,
            suma_todas,
            suma_unicas,
        )
    return liquidaciones


def _lados(lado: str, monto: Decimal) -> tuple[str, str]:
    """Un importe negativo invierte débito y crédito."""
    texto = _texto_monto(abs(monto))
    es_debito = lado == "DEBITO"
    if monto < 0:
        es_debito = not es_debito
    if es_debito:
        return texto, ""
    return "", texto


def _movimientos(liquidacion: _Liquidacion) -> list[dict]:
    if not _cuadra(liquidacion):
        logger.warning(
            "[%s] el valor abonado no cuadra con los importes | aut=%s est=%s abono=%s",
            _BANCO,
            liquidacion.autorizacion,
            liquidacion.establecimiento,
            liquidacion.valor_abono,
        )

    referencia = (
        f"{liquidacion.franquicia} {liquidacion.autorizacion} "
        f"EST {liquidacion.establecimiento}"
    )
    filas: list[dict] = []
    for (concepto, lado), monto in zip(_IMPORTES, liquidacion.montos, strict=True):
        if monto == 0:
            continue
        debito, credito = _lados(lado, monto)
        filas.append({
            "DIA": liquidacion.dia,
            "MES": liquidacion.mes,
            "HORA": "",
            "CONCEPTO": f"{concepto} {referencia}",
            "DEBITO": debito,
            "CREDITO": credito,
            "SALDO": "",
            "MOVIMIENTO": liquidacion.autorizacion,
            "FECHA_OPERACION": liquidacion.fecha_operacion,
            "FECHA_VALOR": liquidacion.fecha_abono,
            "OFICINA_CANAL": liquidacion.establecimiento,
        })
    return filas


def _avisar_anio(filas: list[dict], year) -> None:
    if year is None or not str(year).strip() or not filas:
        return
    esperado = str(year).strip()
    anios = {fila["FECHA_VALOR"].rsplit("/", 1)[-1] for fila in filas}
    if esperado not in anios:
        logger.warning(
            "[%s] el año indicado (%s) no está en las fechas de abono %s.",
            _BANCO,
            esperado,
            sorted(anios),
        )


def extract_extracto_bbva_adquirencias(
    pdf_path_or_file,
    columns: list[str] | None = None,
    year: str | None = None,
) -> list[dict]:
    """Extrae las liquidaciones del extracto BBVA Adquirencias."""
    liquidaciones: list[_Liquidacion] = []
    total_cabecera: Decimal | None = None

    with abrir_extracto(pdf_path_or_file) as pdf:
        for indice, page in enumerate(pdf.pages):
            texto = page.extract_text() or ""
            if indice == 0 and total_cabecera is None:
                total_cabecera = _total_compras(texto)
            for linea in texto.splitlines():
                tokens = linea.split()
                if not tokens or _partir_fecha(tokens[0]) is None:
                    continue
                liquidacion = _liquidacion(linea)
                if liquidacion is None:
                    _log_fila_descartada(_BANCO, "detalle no reconocido", tokens)
                    continue
                liquidaciones.append(liquidacion)

    rows: list[dict] = []
    for liquidacion in _resolver_copia_repetida(liquidaciones, total_cabecera):
        rows.extend(_movimientos(liquidacion))

    _avisar_anio(rows, year)
    return _filtrar_columnas(rows, columns)
