import json
from pathlib import Path
from typing import List, Dict
import shutil


_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_ETIQUETAS_PATH = _DATA_DIR / "etiquetas.json"
_ETIQUETAS_DEFAULT_PATH = _DATA_DIR / "etiquetas.default.json"

def _cargar_reglas() -> List[Dict]:
    if not _ETIQUETAS_PATH.exists():
        if not _ETIQUETAS_DEFAULT_PATH.exists():
            raise FileNotFoundError(
                f"No existe {_ETIQUETAS_PATH} ni la semilla {_ETIQUETAS_DEFAULT_PATH}. "
                "Creá data/etiquetas.default.json con las reglas iniciales."
            )
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(_ETIQUETAS_DEFAULT_PATH, _ETIQUETAS_PATH)

    with open(_ETIQUETAS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _guardar_reglas(reglas: List[Dict]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_ETIQUETAS_PATH, "w", encoding="utf-8") as f:
        json.dump(reglas, f, ensure_ascii=False, indent=2)


def resetear_a_default() -> List[Dict]:
    """Restaura data/etiquetas.json desde la semilla versionada en git.
    Útil si alguien rompe el JSON en caliente desde el endpoint y hay
    que volver a un estado conocido."""
    if not _ETIQUETAS_DEFAULT_PATH.exists():
        raise FileNotFoundError(f"No existe la semilla {_ETIQUETAS_DEFAULT_PATH}")
    shutil.copy(_ETIQUETAS_DEFAULT_PATH, _ETIQUETAS_PATH)
    return _cargar_reglas()

def _guardar_reglas(reglas: List[Dict]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_ETIQUETAS_PATH, "w", encoding="utf-8") as f:
        json.dump(reglas, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# API pública del módulo (usada por main.py para el CRUD, y por
# clasificar_movimientos para aplicar las reglas)
# ---------------------------------------------------------------------------

def obtener_etiquetas() -> List[Dict]:
    """Devuelve la lista de reglas tal como está guardada, en orden."""
    return _cargar_reglas()


def agregar_etiqueta(etiqueta: str, palabras_clave: List[str], posicion: int = None) -> List[Dict]:
    """
    Crea una etiqueta nueva (o falla si ya existe). `posicion` permite
    insertarla en un punto específico de la lista (el orden define
    prioridad); si no se indica, se agrega al final.
    """
    reglas = _cargar_reglas()
    if any(r["etiqueta"] == etiqueta for r in reglas):
        raise ValueError(f"La etiqueta '{etiqueta}' ya existe")

    nueva = {"etiqueta": etiqueta, "palabras_clave": palabras_clave}
    if posicion is None:
        reglas.append(nueva)
    else:
        reglas.insert(posicion, nueva)

    _guardar_reglas(reglas)
    return reglas


def actualizar_etiqueta(etiqueta: str, palabras_clave: List[str] = None, nuevo_nombre: str = None) -> List[Dict]:
    """Edita las palabras clave y/o el nombre de una etiqueta existente."""
    reglas = _cargar_reglas()
    for regla in reglas:
        if regla["etiqueta"] == etiqueta:
            if palabras_clave is not None:
                regla["palabras_clave"] = palabras_clave
            if nuevo_nombre:
                regla["etiqueta"] = nuevo_nombre
            _guardar_reglas(reglas)
            return reglas

    raise ValueError(f"La etiqueta '{etiqueta}' no existe")


def eliminar_etiqueta(etiqueta: str) -> List[Dict]:
    """Elimina una etiqueta. Los movimientos que matcheaban con ella caen en OTROS."""
    reglas = _cargar_reglas()
    reglas_filtradas = [r for r in reglas if r["etiqueta"] != etiqueta]

    if len(reglas_filtradas) == len(reglas):
        raise ValueError(f"La etiqueta '{etiqueta}' no existe")

    _guardar_reglas(reglas_filtradas)
    return reglas_filtradas

def reordenar_etiquetas(nuevo_orden: List[str]) -> List[Dict]:
    reglas = _cargar_reglas()
    reglas_por_nombre = {r["etiqueta"]: r for r in reglas}

    if set(nuevo_orden) != set(reglas_por_nombre.keys()):
        faltantes = set(reglas_por_nombre) - set(nuevo_orden)
        sobrantes = set(nuevo_orden) - set(reglas_por_nombre)
        raise ValueError(
            f"El nuevo orden no coincide con las etiquetas existentes. "
            f"Faltan: {faltantes or '-'} | No existen: {sobrantes or '-'}"
        )

    reglas_reordenadas = [reglas_por_nombre[nombre] for nombre in nuevo_orden]
    _guardar_reglas(reglas_reordenadas)
    return reglas_reordenadas


def clasificar_concepto(concepto: str) -> str:
    """Devuelve la etiqueta correspondiente a un texto de concepto."""
    concepto_norm = (concepto or "").upper()
    for regla in _cargar_reglas():
        if any(palabra in concepto_norm for palabra in regla["palabras_clave"]):
            return regla["etiqueta"]
    return "OTROS"


def clasificar_movimientos(rows: List[Dict]) -> List[Dict]:
    """Agrega la clave ETIQUETA a cada fila extraída del PDF."""
    for row in rows:
        row["ETIQUETA"] = clasificar_concepto(row.get("CONCEPTO", ""))
    return rows

















