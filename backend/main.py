import io

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from services.extractor import extract_extracto_bbva, extract_extracto_occidente,extract_extracto_popular
from services.classifier import clasificar_movimientos
from services.totalizer import totalizar
from models.schemas import TotalizacionResponse
from typing import List
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
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


async def _procesar_extracto(file: UploadFile, extractor_fn) -> TotalizacionResponse:
    """
    Pipeline compartido por todos los bancos: valida el archivo, corre el
    extractor específico del banco recibido y luego el classifier/totalizer,
    que sí son comunes a todos los bancos por ahora.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF")

    contenido = await file.read()

    try:
        rows = extractor_fn(io.BytesIO(contenido))
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
async def totalizar_extracto_popular(file: UploadFile = File(...)) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_popular)

@app.post("/api/extractos/totalizar/bbva", response_model=TotalizacionResponse)
async def totalizar_extracto_bbva(file: UploadFile = File(...)) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_bbva)

@app.post("/api/extractos/totalizar/occidente", response_model=TotalizacionResponse)
async def totalizar_extracto_occidente(file: UploadFile = File(...)) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_occidente)


# Se mantiene el endpoint original (sin banco en la URL) por compatibilidad
# hacia atrás; equivale al de Popular, que era el comportamiento previo.
@app.post("/api/extractos/totalizar", response_model=TotalizacionResponse)
async def totalizar_extracto(file: UploadFile = File(...)) -> TotalizacionResponse:
    return await _procesar_extracto(file, extract_extracto_popular)

@app.post("/api/etiquetas")
async def crear_etiqueta(etiqueta: EtiquetaCreate):
    return agregar_etiqueta(
        etiqueta=etiqueta.etiqueta,
        palabras_clave=etiqueta.palabras_clave,
        posicion=etiqueta.posicion
    )

@app.put("/api/etiquetas/{etiqueta}")
async def actualizar_etiqueta_endpoint(etiqueta: str, update_data: EtiquetaUpdate):
    return actualizar_etiqueta(
        etiqueta=etiqueta,
        palabras_clave=update_data.palabras_clave,
        nuevo_nombre=update_data.nuevo_nombre
    )

@app.delete("/api/etiquetas/{etiqueta}")
async def eliminar_etiqueta_endpoint(etiqueta: str):
    return eliminar_etiqueta(etiqueta)

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
