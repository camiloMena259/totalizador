# models/etiquetas.py

from pydantic import BaseModel
from typing import List, Optional

class EtiquetaCreate(BaseModel):
    etiqueta: str
    palabras_clave: List[str]
    posicion: Optional[int] = None


class EtiquetaUpdate(BaseModel):
    nuevo_nombre: Optional[str] = None
    palabras_clave: Optional[List[str]] = None