"""
Clave de los extractos bancarios cifrados.

Solo aplica al PDF del banco que sube la persona.
Si el extracto tiene contraseña, se prueba la variable de entorno ``nit``.
Si no abre, el llamador pide otra clave al usuario.
"""
from __future__ import annotations

import io
import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

_backend = Path(__file__).resolve().parents[1]
load_dotenv(_backend / ".env")
load_dotenv(_backend.parent / ".env")

_clave_extracto: ContextVar[str | None] = ContextVar("clave_extracto_bancario", default=None)


class ExtractoConClave(Exception):
    """El extracto está cifrado y todavía no hay una clave que lo abra."""

    def __init__(self, clave_invalida: bool):
        self.clave_invalida = clave_invalida
        if clave_invalida:
            mensaje = "La contraseña no abre el extracto bancario."
        else:
            mensaje = "El extracto bancario está protegido con contraseña."
        super().__init__(mensaje)


def _documento(pdf_bytes: bytes, password: str):
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfparser import PDFParser

    return PDFDocument(PDFParser(io.BytesIO(pdf_bytes)), password=password)


def pdf_requiere_clave(pdf_bytes: bytes) -> bool:
    from pdfminer.pdfdocument import PDFPasswordIncorrect

    try:
        _documento(pdf_bytes, "")
    except PDFPasswordIncorrect:
        return True
    return False


def _clave_abre(pdf_bytes: bytes, clave: str) -> bool:
    from pdfminer.pdfdocument import PDFPasswordIncorrect

    try:
        _documento(pdf_bytes, clave)
    except PDFPasswordIncorrect:
        return False
    return True


def resolver_clave_extracto(pdf_bytes: bytes, clave_usuario: str | None = None) -> str | None:
    """
    None si el PDF no está cifrado.
    La clave que abre, si el NIT o la clave del usuario sirven.
    """
    if not pdf_requiere_clave(pdf_bytes):
        return None

    nit = os.getenv("nit", "").strip()
    if nit and _clave_abre(pdf_bytes, nit):
        logger.info("Extracto bancario cifrado. Se abrió con la clave por defecto.")
        return nit

    usuario = (clave_usuario or "").strip()
    if usuario and _clave_abre(pdf_bytes, usuario):
        logger.info("Extracto bancario cifrado. Se abrió con la clave indicada por el usuario.")
        return usuario

    raise ExtractoConClave(clave_invalida=bool(usuario))


@contextmanager
def usar_clave_extracto(clave: str | None):
    token = _clave_extracto.set(clave)
    try:
        yield
    finally:
        _clave_extracto.reset(token)


def abrir_extracto(fuente):
    """Abre el PDF del extracto bancario, con clave si el pipeline ya la resolvió."""
    import pdfplumber

    clave = _clave_extracto.get()
    if clave:
        return pdfplumber.open(fuente, password=clave)
    return pdfplumber.open(fuente)
