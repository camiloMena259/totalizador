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


def extract_extracto_popular(pdf_path_or_file, columns=None):
    """
    Devuelve una lista de dicts con las columnas:
    DIA, MES, HORA, CONCEPTO, DEBITO, CREDITO, SALDO
    """
    rows = []

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

    if columns:
        rows = [{col: row.get(col, "") for col in columns} for row in rows]

    return rows


# Banco de Occidente

_TOKEN_DIA_OCC = re.compile(r'^\d{2}$')
_TOKEN_MONTO_OCC = re.compile(r'^[\d.,]+\.\d{2}$')       # "3,167,922.00" / "0.00"
_TOKEN_IDENT_OCC = re.compile(r'^(?=[A-Z0-9]+$)(?=.*\d)[A-Z0-9]{4,}$')

# dia + al menos 1 palabra de concepto + 3 montos
MIN_TOKENS_OCC = 5


def _parse_monto_occidente(token: str) -> str:
    """'3,167,922.00' -> '3167922.00' (quita separadores de miles)."""
    return token.replace(",", "")


def extract_extracto_occidente(pdf_path_or_file, columns=None):
    """
    Devuelve una lista de dicts con las columnas:
    DIA, CONCEPTO, IDENTIFICACION, DEBITO, CREDITO, SALDO

    (se agregan MES="" y HORA="" para mantener compatibilidad con el resto
    del pipeline, que solo usa DIA/CONCEPTO/DEBITO/CREDITO/SALDO).
    """
    rows = []

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

    if columns:
        rows = [{col: row.get(col, "") for col in columns} for row in rows]

    return rows

# ============================================================
# BBVA (formato real: tabla "Detalles de transacciones")
# ============================================================

_RE_MOVIMIENTO_BBVA = re.compile(r'^\d{4,7}$')
_RE_FECHA_BBVA = re.compile(r'^\d{2}-\d{2}-\d{4}$')
_RE_MONTO_BBVA = re.compile(r'^[\d.,]+\.\d{2}$')


def _limpiar_monto_bbva(token: str) -> str:
    if not token:
        return ""
    return token.replace(",", "")


def _agrupar_por_linea_bbva(words, y_tolerance=3):
    """
    Agrupa 'words' de pdfplumber (que traen x0/top) en líneas según su
    coordenada vertical 'top'. Necesario porque acá no usamos
    page.extract_text(), sino extract_words(), para conservar la posición
    x de cada palabra y poder distinguir Cargos de Abonos.
    """
    lineas = []
    actual = []
    last_top = None
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if last_top is None or abs(w["top"] - last_top) <= y_tolerance:
            actual.append(w)
        else:
            lineas.append(actual)
            actual = [w]
        last_top = w["top"]
    if actual:
        lineas.append(actual)
    return lineas


def _headers_columnas_bbva(words):
    """
    Ubica la posición x0 de los headers 'Cargos' y 'Abonos' en la página
    para usarlos como referencia y clasificar montos sueltos por columna.
    Se recalcula por página porque el header no siempre se repite igual.
    """
    headers = {}
    for w in words:
        texto = w["text"].strip().lower().rstrip(":")
        if texto in ("cargos", "abonos", "saldo") and texto not in headers:
            headers[texto] = w["x0"]
    return headers


def extract_extracto_bbva(pdf_path_or_file, columns=None):
    rows = []

    with pdfplumber.open(pdf_path_or_file) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue

            headers = _headers_columnas_bbva(words)
            x_cargo = headers.get("cargos")
            x_abono = headers.get("abonos")

            for linea in _agrupar_por_linea_bbva(words):
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
                        # continuación), fallback conservador: lo tratamos
                        # como cargo si es el único monto extra.
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

    if columns:
        rows = [{col: row.get(col, "") for col in columns} for row in rows]

    return rows
