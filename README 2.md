# Totalizador de Extractos Bancarios

Aplicación pequeña que recibe un extracto bancario en PDF (BBVA),
lo resume por etiquetas (gravamen, intereses, comisiones, transferencias,
retiros, consignaciones, otros) y totaliza cada categoría.

## Arquitectura

```
backend/
  main.py                  -> único endpoint HTTP, orquesta el pipeline
  services/
    extractor.py           -> lee el PDF y devuelve filas crudas
    classifier.py           -> asigna ETIQUETA a cada fila según el concepto
    totalizer.py            -> agrupa/totaliza por etiqueta, gravamen e intereses
  models/
    schemas.py              -> modelos Pydantic de entrada/salida

frontend/
  src/
    App.jsx                        -> maneja el estado y orquesta la llamada al backend
    services/extractoService.js    -> única responsabilidad: hablar con la API
    components/
      ResumenTarjetas.jsx          -> tarjetas con gravamen/intereses/débitos/créditos
      ResumenPorEtiquetaTabla.jsx  -> tabla del resumen por etiqueta
      MovimientosTabla.jsx         -> tabla detallada de movimientos
```

Flujo: `PDF subido -> extractor -> classifier -> totalizer -> JSON -> React`

## Backend (FastAPI)

```bash
cd backend
python -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Endpoint: `POST http://localhost:8000/api/extractos/totalizar`
(multipart/form-data, campo `file` con el PDF)

## Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Abre `http://localhost:5173` (puerto por defecto de Vite).

## Ajustar el extractor a tu PDF real

El regex de `services/extractor.py` (`_LINE_BBVA`) asume líneas con el
patrón `FECHA  DESCRIPCION  DEBITO  CREDITO  SALDO`. El layout exacto
que entrega `pdfplumber` puede variar según el tipo de cuenta o el año
del extracto. Si al probar con un PDF real no se detectan movimientos:

1. Imprime temporalmente `page.extract_text()` para ver el texto crudo.
2. Ajusta el regex `_LINE_BBVA` a ese formato.
3. El resto del pipeline (classifier, totalizer, frontend) no necesita
   cambios, porque solo dependen de las claves DIA/CONCEPTO/DEBITO/
   CREDITO/SALDO que devuelve el extractor.

## Ajustar las reglas de etiquetas

Editar `_REGLAS_ETIQUETAS` en `services/classifier.py`. Es una lista
ordenada de `(ETIQUETA, [palabras_clave])`; la primera coincidencia
gana. Por ejemplo, para afinar la detección del gravamen (4x1000):

```python
("GRAVAMEN", ["GRAVAMEN A LOS MOVIMIENTOS", "GMF", "4X1000"]),
```
