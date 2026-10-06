from __future__ import annotations

import io

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from services.classifier import clasificar_movimientos
from services.popular_extractor import extract_extracto_popular
from services.occidente_extractor import extract_extracto_occidente
from services.bbva_extractor import extract_extracto_bbva
from services.avVillas_extractor import extract_extracto_avvillas
from services.bancoomeva_extractor import extract_extracto_bancoomeva
from services.figuBogota_extractor import extract_extracto_fidubogota
from services.cajaSocial_extractor import extract_extracto_caja_social
from services.davivienda_extractor import extract_extracto_davivienda
from services.bancoBogota_extractor import extract_extracto_bogota
from services.bbva_detalle_extractor import extract_detalle_bbva
from services.occidente_detalle_extractor import extract_detalle_occidente
from services.popular_detalle_extractor import extract_detalle_popular
from services.totalizer import totalizar
from services.pdf_clave import ExtractoConClave, resolver_clave_extracto, usar_clave_extracto
from models.schemas import TotalizacionResponse, ReporteExportRequest
from services.reporte_excel import generar_excel_reporte, sanitizar_nombre_archivo
from urllib.parse import quote
from typing import List, Optional
import services.classifier as classifier



from services.classifier import (
    obtener_etiquetas,
    agregar_etiqueta,
    actualizar_etiqueta,
    eliminar_etiqueta,
    reordenar_etiquetas,
)

from models.etiquetas import EtiquetaCreate, EtiquetaUpdate

app = FastAPI(title="Totalizador de Extractos Bancarios")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

from pydantic import BaseModel

class ReordenarPayload(BaseModel):
    orden: List[str]

@app.put("/api/etiquetas/reordenar")
def reordenar_etiquetas_endpoint(payload: ReordenarPayload):
    try:
        return classifier.reordenar_etiquetas(payload.orden)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _respuesta_clave_extracto(exc: ExtractoConClave) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "requiere_contrasena": True,
            "clave_invalida": exc.clave_invalida,
            "mensaje": str(exc),
        },
    )


def _clave_extracto_opcional(clave: Optional[str]) -> Optional[str]:
    limpia = (clave or "").strip()
    return limpia or None


async def _procesar_extracto(
    file: UploadFile,
    extractor_fn,
    clave_extracto: Optional[str] = None,
) -> TotalizacionResponse:
    """
    Pipeline compartido por todos los bancos: valida el archivo, corre el
    extractor específico del banco recibido y luego el classifier/totalizer,
    que sí son comunes a todos los bancos por ahora.

    Si el PDF del extracto está cifrado, prueba la clave por defecto (nit)
    y, si no abre, responde 409 para que la pantalla pida la contraseña.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    contenido = await file.read()

    try:
        clave = resolver_clave_extracto(contenido, _clave_extracto_opcional(clave_extracto))
        with usar_clave_extracto(clave):
            rows = extractor_fn(io.BytesIO(contenido))
    except ExtractoConClave as exc:
        return _respuesta_clave_extracto(exc)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"No se pudo procesar el PDF: {exc}")

    if not rows:
        raise HTTPException(
            status_code=422,
            detail="No se encontraron movimientos en el PDF. Revisa el formato del extracto."
        )

    rows = clasificar_movimientos(rows)
    return totalizar(rows)


@app.post("/api/extractos/totalizar/popular", response_model=TotalizacionResponse)
async def totalizar_extracto_popular(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_popular, clave_extracto)

@app.post("/api/extractos/totalizar/bbva", response_model=TotalizacionResponse)
async def totalizar_extracto_bbva(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_bbva, clave_extracto)

@app.post("/api/extractos/totalizar/avvillas", response_model=TotalizacionResponse)
async def totalizar_extracto_avvillas(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_avvillas, clave_extracto)

@app.post("/api/extractos/totalizar/bancoomeva", response_model=TotalizacionResponse)
async def totalizar_extracto_bancoomeva(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_bancoomeva, clave_extracto)

@app.post("/api/extractos/totalizar/occidente", response_model=TotalizacionResponse)
async def totalizar_extracto_occidente(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_occidente, clave_extracto)

@app.post("/api/extractos/totalizar/fidubogota", response_model=TotalizacionResponse)
async def totalizar_extracto_fidubogota(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_fidubogota, clave_extracto)

@app.post("/api/extractos/totalizar/caja_social", response_model=TotalizacionResponse)
async def totalizar_extracto_caja_social(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_caja_social, clave_extracto)

@app.post("/api/extractos/totalizar/davivienda", response_model=TotalizacionResponse)
async def totalizar_extracto_davivienda(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_davivienda, clave_extracto)

@app.post("/api/extractos/totalizar/bogota", response_model=TotalizacionResponse)
async def totalizar_extracto_bogota(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_bogota, clave_extracto)

@app.post("/api/extractos/totalizar/bbva/detalle", response_model=TotalizacionResponse)
async def totalizar_detalle_bbva(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_detalle_bbva, clave_extracto)

@app.post("/api/extractos/totalizar/occidente/detalle", response_model=TotalizacionResponse)
async def totalizar_detalle_occidente(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_detalle_occidente, clave_extracto)

@app.post("/api/extractos/totalizar/popular/detalle", response_model=TotalizacionResponse)
async def totalizar_detalle_popular(
    file: UploadFile = File(...),
    clave_extracto: Optional[str] = Form(None),
) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_detalle_popular, clave_extracto)


@app.post("/api/extractos/reporte")
def descargar_reporte(payload: ReporteExportRequest):
    """Genera un Excel con banco, resumen general, detalle y movimientos."""
    nombre = sanitizar_nombre_archivo(payload.nombre_archivo)
    resultado = TotalizacionResponse(
        movimientos=payload.movimientos,
        resumen_por_etiqueta=payload.resumen_por_etiqueta,
        total_gravamen=payload.total_gravamen,
        total_intereses=payload.total_intereses,
        total_debitos=payload.total_debitos,
        total_creditos=payload.total_creditos,
    )
    contenido = generar_excel_reporte(
        resultado=resultado,
        banco=payload.banco.strip() or "Sin banco",
        nombre_archivo=nombre,
    )
    nombre_header = quote(nombre)
    return StreamingResponse(
        io.BytesIO(contenido),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{nombre_header}",
        },
    )

# Se mantiene el endpoint original (sin banco en la URL) por compatibilidad
# hacia atrás; equivale al de Popular, que era el comportamiento previo.

# @app.post("/api/etiquetas")
# async def crear_etiqueta(etiqueta: EtiquetaCreate):
#     return agregar_etiqueta(
#         etiqueta=etiqueta.etiqueta,
#         palabras_clave=etiqueta.palabras_clave,
#         posicion=etiqueta.posicion
#     )

# @app.put("/api/etiquetas/{etiqueta}")
# async def actualizar_etiqueta_endpoint(etiqueta: str, update_data: EtiquetaUpdate):
#     return actualizar_etiqueta(
#         etiqueta=etiqueta,
#         palabras_clave=update_data.palabras_clave,
#         nuevo_nombre=update_data.nuevo_nombre
#     )

# @app.delete("/api/etiquetas/{etiqueta}")
# async def eliminar_etiqueta_endpoint(etiqueta: str):
#     return eliminar_etiqueta(etiqueta)

@app.post("/api/etiquetas")
async def crear_etiqueta(body: EtiquetaCreate):
    try:
        return agregar_etiqueta(
            etiqueta=body.etiqueta,
            palabras_clave=body.palabras_clave,
            posicion=body.posicion,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.put("/api/etiquetas/{etiqueta}")
async def editar_etiqueta(
    etiqueta: str,
    body: EtiquetaUpdate,
):
    try:
        return actualizar_etiqueta(
            etiqueta=etiqueta,
            nuevo_nombre=body.nuevo_nombre,
            palabras_clave=body.palabras_clave,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))

@app.delete("/api/etiquetas/{etiqueta}")
async def borrar_etiqueta(etiqueta: str):
    try:
        return eliminar_etiqueta(etiqueta)
    except ValueError as e:
        raise HTTPException(404, str(e))

@app.get("/api/etiquetas")
async def listar_etiquetas():
    return obtener_etiquetas()

@app.get("/api/health")
async def health():
    return {"status": "ok"}
