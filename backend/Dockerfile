# Usamos la imagen oficial de Python directamente
FROM python:3.11-slim

WORKDIR /app

# Evita que Python escriba archivos .pyc y fuerza que la salida vaya directo a la consola
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copiamos los requerimientos
COPY requirements.txt .

# Truco Pro: Instalamos las dependencias. 
# NOTA: Si usas 'psycopg2', asegúrate en tu requirements.txt de cambiarlo por 'psycopg2-binary' 
# para que no intente compilar nada en el sistema.
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el código de la API
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]