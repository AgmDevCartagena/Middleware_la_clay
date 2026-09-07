# =====================================================================
# Dockerfile para FastAPI - API Gateway Zeus & Reportes
# =====================================================================
FROM python:3.10-slim

# Evitar la generación de archivos .pyc y habilitar logs inmediatos
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Directorio de trabajo en el contenedor
WORKDIR /app

# Instalar dependencias del sistema requeridas por:
# - pyodbc y SQL Server (unixodbc, msodbcsql17, freetds)
# - opencv-python (libgl1, libglib2.0-0)
# - wkhtmltopdf (pdfkit)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg2 \
    ca-certificates \
    build-essential \
    unixodbc \
    unixodbc-dev \
    freetds-dev \
    freetds-bin \
    tdsodbc \
    libgl1 \
    libglib2.0-0 \
    wkhtmltopdf \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql17 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependencias de Python (aprovechando caché de capas)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copiar el código fuente de la aplicación
COPY . .

# Crear directorio para reportes locales
RUN mkdir -p /app/generated_reports

# Exponer el puerto de la aplicación
EXPOSE 8000

# Iniciar FastAPI con Uvicorn (compatible con variable PORT para Cloud Run / Docker)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
