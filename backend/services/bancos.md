ESTE ARCHIVO RECOPILA TODA LA LOGICA DE EXTRACION DE LOS DIFERENTES BANCOS
ESTAN JUNTOS PERO ESTOS DEBEN IR EN ARCHIVOS .PY DIFERENTES 

banco de bogota:
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

bancoomeva:

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

caja social:
from __future__ import annotations
from services.extractor import _filtrar_columnas, _agrupar_por_lineas, _normalizar_texto, _quitar_tildes

import logging
import re
from typing import Any
import pdfplumber

logger = logging.getLogger(__name__)

_RE_FECHA_CAJA_SOCIAL = re.compile(
    r"^(ENE|FEB|MAR|ABR|MAY|JUN|JUL|AGO|SEP|OCT|NOV|DIC)\s+\d{2}$",
    re.IGNORECASE,
)
_RE_MONTO_CAJA_SOCIAL = re.compile(r"^-?[\d,]+\.\d{2}$")

_MESES_CAJA_SOCIAL = {
    "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04",
    "MAY": "05", "JUN": "06", "JUL": "07", "AGO": "08",
    "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12",
}

# Límites relativos de columnas (fracción del ancho de página). Calibrados
# sobre la plantilla estándar del extracto de Banco Caja Social; si el
# banco cambia el layout del PDF, estos porcentajes son el primer lugar
# a revisar.
_LIMITES_COLUMNAS_CAJA_SOCIAL = {
    "fecha": (0.037, 0.095),
    "transaccion": (0.095, 0.302),
    "documento": (0.302, 0.395),
    "lugar": (0.395, 0.558),
    "debito": (0.558, 0.704),
    "credito": (0.704, 0.839),
    "saldo": (0.839, 0.970),
}


def _parse_monto_caja_social(token: str) -> str:
    """'208,400.00' -> '208400.00'; '-89,207.00' -> '-89207.00'."""
    if not token:
        return ""

    token = token.strip()
    if not _RE_MONTO_CAJA_SOCIAL.match(token):
        return ""

    negativo = token.startswith("-")
    if negativo:
        token = token[1:]
    token = token.replace(",", "")
    return f"-{token}" if negativo else token


def _es_fecha_caja_social(token: str) -> bool:
    """True si el token tiene formato 'JUN 01', 'JUL 15', etc."""
    return bool(_RE_FECHA_CAJA_SOCIAL.match(token.strip()))


def _parse_fila_caja_social(
    fecha: str,
    tokens_transaccion: list[str],
    tokens_documento: list[str],
    tokens_lugar: list[str],
    tokens_debito: list[str],
    tokens_credito: list[str],
    tokens_saldo: list[str],
    year: str,
) -> dict[str, Any] | None:
    """
    Construye un movimiento de Banco Caja Social.
    Estructura: FECHA, TRANSACCIÓN, DOCUMENTO, LUGAR, DÉBITOS, CRÉDITOS, SALDOS.
    """
    if not fecha:
        return None

    fecha = fecha.strip().upper()
    match = re.match(r"^([A-Z]{3})\s+(\d{2})$", fecha)
    if not match:
        return None

    mes_texto, dia = match.group(1), match.group(2)
    mes = _MESES_CAJA_SOCIAL.get(mes_texto)
    if not mes:
        return None

    concepto = _normalizar_texto(" ".join(tokens_transaccion))
    documento = _normalizar_texto(" ".join(tokens_documento))
    lugar = _normalizar_texto(" ".join(tokens_lugar))

    debito = next((v for t in tokens_debito if (v := _parse_monto_caja_social(t))), "")
    credito = next((v for t in tokens_credito if (v := _parse_monto_caja_social(t))), "")
    saldo = next((v for t in tokens_saldo if (v := _parse_monto_caja_social(t))), "")

    if not concepto:
        return None

    fecha_completa = f"{dia}/{mes}/{year}"

    return {
        "DIA": dia,
        "MES": mes,
        "HORA": "",
        "CONCEPTO": concepto,
        "DEBITO": debito,
        "CREDITO": credito,
        "SALDO": saldo,
        "OFICINA_CANAL": lugar,
        "VALOR_UNIDAD": "",
        "UNIDADES": "",
        "TIPO_PARTICIPACION": "",
        "MOVIMIENTO": documento,
        "FECHA_OPERACION": fecha_completa,
        "FECHA_VALOR": fecha_completa,
    }


def extract_extracto_caja_social(
    pdf_path_or_file,
    columns: list[str] | None = None,
    year: str | None = None,
) -> list[dict]:
    """
    Extrae movimientos de un extracto de Banco Caja Social.

    IMPORTANTE sobre `year`: el PDF no siempre expone el año de forma
    estructurada junto a cada fecha ("JUN 01"), así que hay que
    indicarlo explícitamente. Si no se pasa, se usa el año actual del
    sistema y se deja un log de advertencia (antes quedaba fijo en
    "2026" sin ningún aviso, lo cual es incorrecto para cualquier otro
    período y fallaba en silencio).

    Estrategia:
        1. Extrae las palabras del PDF por página.
        2. Agrupa las palabras por línea.
        3. Usa la fecha para detectar el inicio de cada movimiento.
        4. Usa la posición X (relativa al ancho de página) para asignar
        cada palabra a su columna.
        5. Permite que TRANSACCIÓN ocupe varias líneas.
        6. Ignora encabezados / pies de página fuera de la tabla.
    """
    if year is None:
        import datetime
        year = str(datetime.date.today().year)
        logger.warning(
            "[CAJA SOCIAL] no se especificó 'year'; se usa el año actual "
            "(%s) por defecto. Pase year explícitamente si el extracto "
            "corresponde a otro período.", year,
        )

    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue

            page_width = page.width
            limites = {
                nombre: (page_width * xmin, page_width * xmax)
                for nombre, (xmin, xmax) in _LIMITES_COLUMNAS_CAJA_SOCIAL.items()
            }

            def obtener_columna(x: float) -> str | None:
                for nombre, (x_min, x_max) in limites.items():
                    if x_min <= x < x_max:
                        return nombre
                return None

            movimiento_actual: dict | None = None
            en_tabla_movimientos = False

            def guardar_movimiento():
                nonlocal movimiento_actual
                if movimiento_actual is None:
                    return
                row = _parse_fila_caja_social(
                    fecha=movimiento_actual["fecha"],
                    tokens_transaccion=movimiento_actual["transaccion"],
                    tokens_documento=movimiento_actual["documento"],
                    tokens_lugar=movimiento_actual["lugar"],
                    tokens_debito=movimiento_actual["debito"],
                    tokens_credito=movimiento_actual["credito"],
                    tokens_saldo=movimiento_actual["saldo"],
                    year=year,
                )
                if row:
                    rows.append(row)
                movimiento_actual = None

            for linea in _agrupar_por_lineas(words):
                linea = sorted(linea, key=lambda w: w["x0"])
                if not linea:
                    continue

                texto_linea = _normalizar_texto(" ".join(w["text"] for w in linea))
                texto_upper = texto_linea.upper()
                texto_sin_tildes = _quitar_tildes(texto_upper)

                # Inicio de la tabla
                if texto_sin_tildes.startswith("FECHA") and "TRANSACCION" in texto_sin_tildes:
                    en_tabla_movimientos = True
                    continue

                # Fin de la tabla en esta página
                if "CONTINUA EN LA SIGUIENTE PAGINA" in texto_sin_tildes:
                    guardar_movimiento()
                    en_tabla_movimientos = False
                    continue

                # Encabezados / pies de página conocidos a ignorar
                if "DETALLE DE PRODUCTOS" in texto_upper:
                    continue
                if texto_sin_tildes.startswith("CONTINUACION CUENTA"):
                    continue
                if texto_upper == "CUENTA DE AHORROS":
                    continue
                if "PERIODO DEL INFORME" in texto_upper:
                    continue
                if "MAS CREDITOS" in texto_sin_tildes:
                    continue
                if "MENOS DEBITOS" in texto_sin_tildes:
                    continue
                if "INTERESES DEL PERIODO" in texto_upper:
                    continue
                if "NUEVO SALDO" in texto_upper:
                    continue

                if not en_tabla_movimientos:
                    continue

                # Detectar fecha en la línea
                fecha_tokens = [
                    w["text"] for w in linea if obtener_columna(w["x0"]) == "fecha"
                ]
                fecha = _normalizar_texto(" ".join(fecha_tokens)).upper()

                if _es_fecha_caja_social(fecha):
                    guardar_movimiento()
                    movimiento_actual = {
                        "fecha": fecha,
                        "transaccion": [], "documento": [], "lugar": [],
                        "debito": [], "credito": [], "saldo": [],
                    }

                if movimiento_actual is None:
                    continue

                destino_por_columna = {
                    "transaccion": movimiento_actual["transaccion"],
                    "documento": movimiento_actual["documento"],
                    "lugar": movimiento_actual["lugar"],
                    "debito": movimiento_actual["debito"],
                    "credito": movimiento_actual["credito"],
                    "saldo": movimiento_actual["saldo"],
                }

                for w in linea:
                    texto = w["text"].strip()
                    if not texto:
                        continue
                    columna = obtener_columna(w["x0"])
                    destino = destino_por_columna.get(columna)
                    if destino is not None:
                        destino.append(texto)

            guardar_movimiento()

    for row in rows:
        row["CONCEPTO"] = _normalizar_texto(row["CONCEPTO"])
        row["OFICINA_CANAL"] = _normalizar_texto(row["OFICINA_CANAL"])
        row["MOVIMIENTO"] = _normalizar_texto(row["MOVIMIENTO"])

    logger.debug("[CAJA SOCIAL] %d movimientos extraídos", len(rows))
    for i, r in enumerate(rows, 1):
        logger.debug(
            "  %d %s %r DOC=%s LUGAR=%r DEBITO=%s CREDITO=%s SALDO=%s",
            i, r["FECHA_OPERACION"], r["CONCEPTO"], r["MOVIMIENTO"],
            r["OFICINA_CANAL"], r["DEBITO"], r["CREDITO"], r["SALDO"],
        )

    return _filtrar_columnas(rows, columns)

davivienda: 

from __future__ import annotations
from typing import Any
from services.extractor import _log_fila_descartada, _filtrar_columnas

import logging
import re
import pdfplumber

logger = logging.getLogger(__name__)

_RE_DIA_MES_DAVIVIENDA = re.compile(r'^\d{2}$')                      # "04", "05"
_RE_DOC_DAVIVIENDA = re.compile(r'^\d{3,6}$')                         # "5902"
_RE_MONTO_DAVIVIENDA = re.compile(r'^\$[\d,]+\.\d{2}[+-]$')           # "$103,800.00+"

# Frases conocidas de "Clase de Movimiento". Se matchean por prefijo
# exacto (tokenizado) contra el inicio del texto intermedio. Lista
# corta a propósito: solo lo observado en la muestra real. Ampliar
# a medida que aparezcan clases nuevas (quedan logueadas como
# advertencia cuando no se reconocen).
CLASES_DAVIVIENDA = [
    "Consignacion Efectivo en Oficina",
    "Abono Por Pago Factura",
]


def _limpiar_monto_davivienda(token: str) -> str:
    """'$1,080,000.00+' -> '1080000.00' (el signo +/- se usa aparte para clasificar)."""
    if not token:
        return ""
    return token.replace("$", "").replace(",", "").rstrip("+-")


def _match_clase_davivienda(medio: list[str]) -> tuple[str, int] | None:
    """Busca la clase de movimiento conocida más larga al inicio de `medio`."""
    mejor: tuple[str, int] | None = None
    for clase in CLASES_DAVIVIENDA:
        clase_tokens = clase.split()
        n = len(clase_tokens)
        if len(medio) < n:
            continue
        if [t.lower() for t in medio[:n]] == [t.lower() for t in clase_tokens]:
            if mejor is None or n > mejor[1]:
                mejor = (clase, n)
    return mejor


def _parse_fila_davivienda(buffer: list[str], year: str) -> dict[str, Any] | None:
    if len(buffer) < 5:
        return None
    if not (_RE_DIA_MES_DAVIVIENDA.match(buffer[0]) and _RE_DIA_MES_DAVIVIENDA.match(buffer[1])):
        return None
    if not (
        _RE_DOC_DAVIVIENDA.match(buffer[-3])
        and _RE_MONTO_DAVIVIENDA.match(buffer[-2])
        and _RE_MONTO_DAVIVIENDA.match(buffer[-1])
    ):
        return None

    dia, mes = buffer[0], buffer[1]
    documento, valor, saldo = buffer[-3], buffer[-2], buffer[-1]
    medio = buffer[2:-3]  # Clase de Movimiento + Oficina, sin separador fijo

    match = _match_clase_davivienda(medio)
    if match is None:
        logger.warning(
            "[DAVIVIENDA] 'Clase de Movimiento' no reconocida, se deja todo "
            "como CONCEPTO y OFICINA vacía (agregar a CLASES_DAVIVIENDA): %r",
            " ".join(medio),
        )
        concepto = " ".join(medio).strip()
        oficina = ""
    else:
        _clase, n = match
        idx = n
        concepto_tokens = medio[:n]

        # Caso observado: "Abono Por Pago Factura" viene seguido del
        # número de factura (token largo solo dígitos) antes de la
        # Oficina. Se conserva como parte del concepto.
        if idx < len(medio) and medio[idx].isdigit() and len(medio[idx]) >= 6:
            concepto_tokens = concepto_tokens + [medio[idx]]
            idx += 1

        concepto = " ".join(concepto_tokens).strip()
        oficina = " ".join(medio[idx:]).strip()

    if not concepto:
        _log_fila_descartada("DAVIVIENDA", "concepto vacío", buffer)
        return None

    signo_valor = valor[-1]  # '+' o '-'
    tipo = "CREDITO" if signo_valor == "+" else "DEBITO"
    valor_limpio = _limpiar_monto_davivienda(valor)

    return {
        "DIA": dia,
        "MES": mes,
        "HORA": "",
        "CONCEPTO": concepto,
        "DEBITO": valor_limpio if tipo == "DEBITO" else "",
        "CREDITO": valor_limpio if tipo == "CREDITO" else "",
        "SALDO": _limpiar_monto_davivienda(saldo),
        "OFICINA_CANAL": oficina,
        "MOVIMIENTO": documento,
        "FECHA_OPERACION": f"{dia}/{mes}/{year}",
        "FECHA_VALOR": f"{dia}/{mes}/{year}",
    }


def extract_extracto_davivienda(
    pdf_path_or_file,
    columns: list[str] | None = None,
    year: str | None = None,
) -> list[dict]:
    """
    Extrae movimientos del extracto de Davivienda.

    La fecha viene como dos tokens sueltos "DD MM" sin año, así que
    (igual que Bogotá y Caja Social) se requiere `year`. El signo al
    final de Valor/Saldo ('+' / '-') es quien determina si el
    movimiento es CREDITO o DEBITO — a diferencia de Bogotá, aquí sí
    hay una señal explícita y no hace falta adivinar por texto.
    """
    if year is None:
        import datetime
        year = str(datetime.date.today().year)
        logger.warning(
            "[DAVIVIENDA] no se especificó 'year'; se usa el año actual "
            "(%s) por defecto. Pase year explícitamente si el extracto "
            "corresponde a otro período.", year,
        )

    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            buffer: list[str] = []

            for raw_line in text.split("\n"):
                tokens = raw_line.split()
                if not tokens:
                    continue

                es_inicio_fila = (
                    len(tokens) > 1
                    and _RE_DIA_MES_DAVIVIENDA.match(tokens[0])
                    and _RE_DIA_MES_DAVIVIENDA.match(tokens[1])
                )

                if es_inicio_fila:
                    if buffer:
                        _log_fila_descartada("DAVIVIENDA", "fila sin cierre antes de la siguiente fecha", buffer)
                    buffer = tokens
                else:
                    if not buffer:
                        continue
                    buffer.extend(tokens)

                row = _parse_fila_davivienda(buffer, year)
                if row:
                    rows.append(row)
                    buffer = []

            if buffer:
                _log_fila_descartada("DAVIVIENDA", "fila sin cierre al final de la página", buffer)

    return _filtrar_columnas(rows, columns)

fidu bogota:

from __future__ import annotations
from typing import Any
from services.extractor import _log_fila_descartada, _filtrar_columnas, _agrupar_por_lineas, _normalizar_texto

import logging
import re
import pdfplumber

logger = logging.getLogger(__name__)

_RE_FECHA_FIDU = re.compile(r"^\d{2}/\d{2}/\d{4}$")
_RE_MONTO_FIDU = re.compile(r"^-?[\d.]+,\d{2}$")
_RE_TIPO_PART_FIDU = re.compile(r"^\d+(?:\.\d{1,2})?$")

# Canales conocidos. NO se usan para determinar la posición de las
# columnas, solo ayudan a identificar el canal cuando conocemos su texto.
CANALES_FIDU = [
    "OFICINA INTERNET",
    "FIDUCIARIA BOGOTA DG1",
]


def _parse_monto_fidu(token: str) -> str:
    """Formato europeo: miles con '.', decimales con ','. Ej: '1.234,56' -> '1234.56'."""
    if not token:
        return ""

    token = token.strip()
    negativo = token.startswith("-")
    if negativo:
        token = token[1:]

    entero, separador, decimal = token.rpartition(",")
    if not separador:
        return ""

    entero_limpio = entero.replace(".", "")
    resultado = f"{entero_limpio}.{decimal}"
    return f"-{resultado}" if negativo else resultado


def _parse_fila_fidu(tokens: list[str]) -> dict[str, Any] | None:
    """
    Parsea una línea que comienza con fecha.

    En Fidubogotá la línea que comienza con fecha contiene todos los
    campos estructurados del movimiento: FECHA, DESCRIPCIÓN, VALOR
    TRANSACCIÓN, CANAL, VALOR UNIDAD, UNIDADES, TIPO PARTICIPACIÓN.
    La descripción puede continuar en líneas posteriores (se agregan
    aparte, ver `extract_extracto_fidubogota`).
    """
    if not tokens:
        return None

    fecha = tokens[0]
    if not _RE_FECHA_FIDU.match(fecha):
        return None

    dia, mes, anio = fecha.split("/")
    resto = tokens[1:]

    if len(resto) < 5:
        _log_fila_descartada("FIDUBOGOTA", "menos de 5 tokens tras la fecha", tokens)
        return None

    tipo_participacion = resto[-1]
    unidades = resto[-2]
    valor_unidad = resto[-3]

    if not _RE_TIPO_PART_FIDU.match(tipo_participacion):
        _log_fila_descartada("FIDUBOGOTA", "tipo de participación inválido", tokens)
        return None
    if not _RE_MONTO_FIDU.match(unidades):
        _log_fila_descartada("FIDUBOGOTA", "unidades inválidas", tokens)
        return None
    if not _RE_MONTO_FIDU.match(valor_unidad):
        _log_fila_descartada("FIDUBOGOTA", "valor unidad inválido", tokens)
        return None

    medio = resto[:-3]
    if not medio:
        return None

    # Buscar el canal conocido.
    canal = ""
    canal_inicio = None
    for candidato in CANALES_FIDU:
        canal_tokens = candidato.split()
        n = len(canal_tokens)
        if len(medio) < n:
            continue
        for i in range(len(medio) - n + 1):
            bloque = medio[i:i + n]
            if [t.upper() for t in bloque] == [t.upper() for t in canal_tokens]:
                canal = candidato
                canal_inicio = i
                break
        if canal_inicio is not None:
            break

    if canal_inicio is not None:
        antes_canal = medio[:canal_inicio]
        if not antes_canal:
            return None

        valor_transaccion = antes_canal[-1]
        if not _RE_MONTO_FIDU.match(valor_transaccion):
            _log_fila_descartada("FIDUBOGOTA", "valor transacción inválido (canal conocido)", tokens)
            return None

        concepto_tokens = antes_canal[:-1]
    else:
        # Canal no conocido: buscamos el primer monto después de la descripción.
        indice_valor = next(
            (i for i, token in enumerate(medio) if _RE_MONTO_FIDU.match(token)),
            None,
        )
        if indice_valor is None:
            _log_fila_descartada("FIDUBOGOTA", "no se encontró valor transacción (canal desconocido)", tokens)
            return None

        valor_transaccion = medio[indice_valor]
        concepto_tokens = medio[:indice_valor]
        canal = " ".join(medio[indice_valor + 1:]).strip()

    concepto = " ".join(concepto_tokens).strip()
    if not concepto:
        return None

    valor_transaccion_num = _parse_monto_fidu(valor_transaccion)
    if not valor_transaccion_num:
        return None

    debito = valor_transaccion_num[1:] if valor_transaccion_num.startswith("-") else ""
    credito = valor_transaccion_num if not valor_transaccion_num.startswith("-") else ""

    return {
        "DIA": dia,
        "MES": mes,
        "HORA": "",
        "CONCEPTO": concepto,
        "DEBITO": debito,
        "CREDITO": credito,
        "SALDO": "",
        "OFICINA_CANAL": canal,
        "VALOR_UNIDAD": _parse_monto_fidu(valor_unidad),
        "UNIDADES": _parse_monto_fidu(unidades),
        "TIPO_PARTICIPACION": tipo_participacion,
        "MOVIMIENTO": "",
        "FECHA_OPERACION": fecha,
        "FECHA_VALOR": fecha,
    }


def extract_extracto_fidubogota(pdf_path_or_file, columns: list[str] | None = None) -> list[dict]:
    """
    Extrae movimientos del extracto Fidubogotá.

    No depende de coordenadas para identificar columnas. Regla principal:
        Línea con FECHA        -> nuevo movimiento
        Línea SIN FECHA        -> continuación de la descripción anterior
        "DETALLE DE RENTABILIDADES" -> fin de movimientos
    """
    rows: list[dict] = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue

            en_detalle_movimientos = False
            ultimo_row: dict | None = None

            for linea in _agrupar_por_lineas(words):
                linea = sorted(linea, key=lambda w: w["x0"])
                tokens = [w["text"] for w in linea]
                if not tokens:
                    continue

                texto_upper = " ".join(tokens).strip().upper()

                if "DETALLE" in texto_upper and "MOVIMIENTOS" in texto_upper:
                    en_detalle_movimientos = True
                    continue

                if not en_detalle_movimientos:
                    continue

                if "DETALLE" in texto_upper and "RENTABILIDADES" in texto_upper:
                    break

                # NUEVO MOVIMIENTO: toda línea que comienza con fecha.
                if _RE_FECHA_FIDU.match(tokens[0]):
                    row = _parse_fila_fidu(tokens)
                    if row:
                        rows.append(row)
                        ultimo_row = row
                    continue

                # CONTINUACIÓN DE DESCRIPCIÓN
                if ultimo_row is not None:
                    texto_extra = " ".join(tokens).strip()
                    if texto_extra:
                        ultimo_row["CONCEPTO"] = (ultimo_row["CONCEPTO"] + " " + texto_extra).strip()

    for row in rows:
        row["CONCEPTO"] = _normalizar_texto(row["CONCEPTO"])
        row["OFICINA_CANAL"] = _normalizar_texto(row["OFICINA_CANAL"])

    logger.debug("[FIDUBOGOTA] %d movimientos extraídos", len(rows))
    for i, r in enumerate(rows, 1):
        logger.debug(
            "  %d %s %r DEBITO=%s CREDITO=%s",
            i, r["FECHA_OPERACION"], r["CONCEPTO"], r["DEBITO"], r["CREDITO"],
        )

    return _filtrar_columnas(rows, columns)

banco popular:
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
    
