from __future__ import annotations
from decimal import Decimal, InvalidOperation
from services.extractor import _log_fila_descartada, _filtrar_columnas
from typing import Any

import logging
import re
import pdfplumber

logger = logging.getLogger(__name__)

def _extraer_saldo_inicial_bogota(page) -> Decimal | None:
    text = page.extract_text() or ""

    match = re.search(
        r"Saldo\s+Inicial\s*:\s*([\d,]+\.\d{2})",
        text,
        re.IGNORECASE,
    )

    if not match:
        logger.warning(
            "[BOGOTA] No se encontró 'Saldo Inicial' "
            "en la primera página del extracto."
        )
        return None

    saldo_texto = match.group(1)

    saldo = _decimal_bogota(saldo_texto)

    logger.info(
        "[BOGOTA] Saldo inicial detectado: %s",
        saldo,
    )

    return saldo

# REGEX
_RE_FECHA_BOGOTA = re.compile(r"^\d{2}/\d{2}$")
_RE_CODTRANS_BOGOTA = re.compile(r"^\d{3,4}$")
_RE_MONTO_BOGOTA = re.compile(r"^[\d,]+\.\d{2}$")
_RE_DOC_BOGOTA = re.compile(r"^\d{4,8}$")


# LIMPIAR MONTO
def _limpiar_monto_bogota(token: str) -> str:
    """ Convierte: 1,066,000.00 en:1066000.00"""
    return token.replace(",", "") if token else ""

def _decimal_bogota(valor: str) -> Decimal:
    """ Convierte un monto del extractor a Decimal """
    try:
        return Decimal(
            _limpiar_monto_bogota(valor)
        )

    except (InvalidOperation, ValueError):
        return Decimal("0")


# PARSEAR UNA FILA
def _parse_fila_bogota(
    buffer: list[str],
    year: str,
) -> dict[str, Any] | None:
    """
    extrae:
        Fecha
        Concepto
        Documento
        Valor
        Saldo
        Ciudad
        Oficina/Canal
    """
    if len(buffer) < 6:
        return None

    indices_cierre = []

    for i in range(2, len(buffer) - 2):

        if (
            _RE_DOC_BOGOTA.match(buffer[i])
            and _RE_MONTO_BOGOTA.match(buffer[i + 1])
            and _RE_MONTO_BOGOTA.match(buffer[i + 2])
        ):
            indices_cierre.append(i)

    # No encontramos Documento + Valor + Saldo
    if not indices_cierre:
        return None

    # USAR EL ÚLTIMO CIERRE ENCONTRADO
    indice_cierre = indices_cierre[-1]

    fecha = buffer[0]

    documento = buffer[indice_cierre]

    valor = buffer[indice_cierre + 1]

    saldo = buffer[indice_cierre + 2]

    # TOKENS ANTES DEL DOCUMENTO
    medio = buffer[2:indice_cierre]

    texto_posterior = buffer[indice_cierre + 3:]

    if texto_posterior:
        medio.extend(texto_posterior)

    # CIUDAD / OFICINA
    ciudad = ""
    oficina = ""

    if (
        len(medio) >= 2
        and medio[-1].isalpha()
        and medio[-2].isalpha()
        and medio[-1].lower() == medio[-2].lower()
    ):
        ciudad = medio[-1]
        oficina = medio[-1]

        concepto_tokens = medio[:-2]

    else:
        concepto_tokens = medio

    concepto = " ".join(
        concepto_tokens
    ).strip()

    # VALIDAR CONCEPTO
    if not concepto:

        _log_fila_descartada(
            "BOGOTA",
            "concepto vacío",
            buffer,
        )

        return None

    # FECHA
    try:

        dia, mes = fecha.split("/")

    except ValueError:

        _log_fila_descartada(
            "BOGOTA",
            "fecha inválida",
            buffer,
        )

        return None

    # LIMPIAR MONTOS
    valor_limpio = _limpiar_monto_bogota(
        valor
    )

    saldo_limpio = _limpiar_monto_bogota(
        saldo
    )
    return {
        "DIA": dia,
        "MES": mes,
        "HORA": "",

        "CONCEPTO": concepto,

        "DEBITO": "", #se llenan sin debito por el momento 
        "CREDITO": "", #se llenan sin credito por el momento

        "SALDO": saldo_limpio,

        "OFICINA_CANAL": oficina,

        "MOVIMIENTO": documento,

        "FECHA_OPERACION": f"{dia}/{mes}/{year}",
        "FECHA_VALOR": f"{dia}/{mes}/{year}",

        "CIUDAD": ciudad,

        # Campos internos para diagnóstico
        "_VALOR_MOVIMIENTO": valor_limpio,
        "_TIPO_MOVIMIENTO": "",
    }


# CLASIFICAR SEGUN SALDOS
def _clasificar_movimientos_por_saldo_bogota(
    rows: list[dict[str, Any]],
    saldo_inicial: Decimal | None = None,
) -> None:
    
    """ Determina CREDITO / DEBITO utilizando el cambio real del saldo. """
    if not rows:
        return

    # SALDO ANTERIOR DEL PRIMER MOVIMIENTO
    saldo_anterior = saldo_inicial

    for i, actual in enumerate(rows):
        # Si no tenemos saldo anterior, no podemos clasificar
        # este movimiento.

        if saldo_anterior is None:

            actual["_TIPO_MOVIMIENTO"] = "SIN_SALDO_ANTERIOR"

            logger.warning(
                "[BOGOTA] No se pudo determinar crédito/débito "
                "por falta de saldo anterior | "
                "fecha=%s | documento=%s | valor=%s | saldo=%s",
                actual.get("FECHA_OPERACION"),
                actual.get("MOVIMIENTO"),
                actual.get("_VALOR_MOVIMIENTO"),
                actual.get("SALDO"),
            )

            # Intentamos continuar usando el saldo actual
            # como saldo anterior para la siguiente fila.
            try:
                saldo_anterior = _decimal_bogota(
                    actual["SALDO"]
                )
            except Exception:
                saldo_anterior = None

            continue

        # SALDO ACTUAL
        try:

            saldo_actual = _decimal_bogota(
                actual["SALDO"]
            )

            valor_movimiento = _decimal_bogota(
                actual["_VALOR_MOVIMIENTO"]
            )

        except Exception as exc:

            logger.warning(
                "[BOGOTA] No fue posible convertir los "
                "valores monetarios | documento=%s | error=%s",
                actual.get("MOVIMIENTO"),
                exc,
            )

            continue

        # CAMBIO DEL SALDO
        diferencia = (
            saldo_actual - saldo_anterior
        )

        diferencia_absoluta = abs(diferencia)

        # VALIDAR QUE EL VALOR DEL MOVIMIENTO COINCIDA
        # CON EL CAMBIO DEL SALDO
        if diferencia_absoluta != valor_movimiento:

            logger.warning(
                "[BOGOTA] ⚠️ DIFERENCIA ENTRE VALOR Y "
                "CAMBIO DE SALDO | "
                "fecha=%s | "
                "documento=%s | "
                "valor=%s | "
                "saldo_anterior=%s | "
                "saldo_actual=%s | "
                "diferencia=%s",
                actual.get("FECHA_OPERACION"),
                actual.get("MOVIMIENTO"),
                valor_movimiento,
                saldo_anterior,
                saldo_actual,
                diferencia,
            )

        # CLASIFICACIÓN
        if diferencia > 0:

            actual["CREDITO"] = actual["_VALOR_MOVIMIENTO"]
            actual["DEBITO"] = ""
            actual["_TIPO_MOVIMIENTO"] = "CREDITO"

        elif diferencia < 0:

            actual["DEBITO"] = actual["_VALOR_MOVIMIENTO"]
            actual["CREDITO"] = ""
            actual["_TIPO_MOVIMIENTO"] = "DEBITO"

        else:

            actual["DEBITO"] = ""
            actual["CREDITO"] = ""

            actual["_TIPO_MOVIMIENTO"] = (
                "SIN_CAMBIO_SALDO"
            )

            logger.warning(
                "[BOGOTA] ⚠️ Movimiento sin cambio "
                "de saldo | fecha=%s | documento=%s | valor=%s",
                actual.get("FECHA_OPERACION"),
                actual.get("MOVIMIENTO"),
                valor_movimiento,
            )

        # EL SALDO ACTUAL PASA A SER EL SALDO ANTERIOR DE LA SIGUIENTE TRANSACCIÓN
        saldo_anterior = saldo_actual

# LIMPIAR CAMPOS INTERNOS
def _limpiar_campos_internos_bogota(
    rows: list[dict[str, Any]],
) -> None:
    
    """ Elimina los campos utilizados únicamente para diagnóstico antes de devolver el resultado final. """
    for row in rows:

        row.pop(
            "_VALOR_MOVIMIENTO",
            None,
        )

        row.pop(
            "_TIPO_MOVIMIENTO",
            None,
        )

# EXTRACTOR PRINCIPAL
def extract_extracto_bogota(
    pdf_path_or_file,
    columns: list[str] | None = None,
    year: str | None = None,
) -> list[dict]:
    
    if year is None:

        import datetime

        year = str(
            datetime.date.today().year
        )

        logger.warning(
            "[BOGOTA] no se especificó 'year'; se usa el año "
            "actual (%s) por defecto. Pase year explícitamente "
            "si el extracto corresponde a otro período.",
            year,
        )

    rows: list[dict] = []

    # CONTADORES es para pruebas y diagnóstico
    cantidad_creditos = 0
    cantidad_debitos = 0

    suma_credito = Decimal("0")
    suma_debito = Decimal("0")

    with pdfplumber.open(
        pdf_path_or_file
    ) as pdf:
        saldo_inicial = None
        if pdf.pages:
            saldo_inicial = _extraer_saldo_inicial_bogota(
                pdf.pages[0]
            )
    
        # RECORRER PÁGINAS
        for page_num, page in enumerate(
            pdf.pages,
            start=1,
        ):

            text = page.extract_text() or ""

            buffer: list[str] = []

            # RECORRER LÍNEAS
            for raw_line in text.split("\n"):

                tokens = raw_line.split()

                if not tokens:
                    continue

                # BUSCAR TODAS LAS FECHAS + CODIGO
                indices_inicio = []

                for i in range(
                    len(tokens) - 1
                ):

                    if (
                        _RE_FECHA_BOGOTA.match(
                            tokens[i]
                        )
                        and _RE_CODTRANS_BOGOTA.match(
                            tokens[i + 1]
                        )
                    ):

                        indices_inicio.append(i)

                # NO HAY NUEVA TRANSACCIÓN
                if not indices_inicio:

                    if buffer:

                        buffer.extend(tokens)

                        row = _parse_fila_bogota(
                            buffer,
                            year,
                        )

                        if row:

                            rows.append(row)

                            buffer = []

                    continue

                # HAY UNA O MAS TRANSACCIONES
                for posicion, inicio in enumerate(
                    indices_inicio
                ):

                    # SI HABIA BUFFER ANTERIOR
                    if posicion == 0 and buffer:

                        row = _parse_fila_bogota(
                            buffer,
                            year,
                        )

                        if row:

                            rows.append(row)

                        else:

                            _log_fila_descartada(
                                "BOGOTA",
                                "fila sin cierre antes de "
                                "nueva transacción",
                                buffer,
                            )

                        buffer = []

                    # DETERMINAR FINAL DE ESTA TRANSACCION
                    if posicion + 1 < len(
                        indices_inicio
                    ):

                        siguiente_inicio = (
                            indices_inicio[
                                posicion + 1
                            ]
                        )

                        chunk = tokens[
                            inicio:siguiente_inicio
                        ]

                    else:

                        chunk = tokens[
                            inicio:
                        ]

                    # INTENTAR PARSEAR
                    row = _parse_fila_bogota(
                        chunk,
                        year,
                    )

                    if row:

                        rows.append(row)

                    else:

                        # Puede que la descripcion continue en la siguiente línea.
                        buffer = chunk.copy()

            # BUFFER AL FINAL DE LA PAGINA
            if buffer:

                row = _parse_fila_bogota(
                    buffer,
                    year,
                )

                if row:

                    rows.append(row)

                else:

                    _log_fila_descartada(
                        "BOGOTA",
                        "fila sin cierre al final de la página",
                        buffer,
                    )

    # YA TENEMOS TODAS LAS FILAS.
    # AHORA determinamos Credito/Debito mediante SALDOS.
    _clasificar_movimientos_por_saldo_bogota(
        rows,
        saldo_inicial
    )

    # CALCULAR TOTALES
    for row in rows:

        if row["CREDITO"]:

            cantidad_creditos += 1

            suma_credito += _decimal_bogota(
                row["CREDITO"]
            )

        elif row["DEBITO"]:

            cantidad_debitos += 1

            suma_debito += _decimal_bogota(
                row["DEBITO"]
            )

    # RESUMEN
    print("\n")
    print("=" * 70)
    print("[BOGOTA] DIAGNÓSTICO FINAL")
    print("=" * 70)

    print(
        f"[BOGOTA] Filas extraídas: "
        f"{len(rows)}"
    )

    print(
        f"[BOGOTA] Cantidad créditos: "
        f"{cantidad_creditos}"
    )

    print(
        f"[BOGOTA] Cantidad débitos: "
        f"{cantidad_debitos}"
    )

    print(
        f"[BOGOTA] TOTAL CRÉDITOS: "
        f"{suma_credito:,.2f}"
    )

    print(
        f"[BOGOTA] TOTAL DÉBITOS: "
        f"{suma_debito:,.2f}"
    )

    print("=" * 70)

    # ELIMINAR CAMPOS INTERNOS
    _limpiar_campos_internos_bogota(
        rows
    )

    # FILTRAR COLUMNAS
    return _filtrar_columnas(
        rows,
        columns,
    )