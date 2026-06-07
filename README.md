# Futunet Backend - API & Sincronización

Este repositorio contiene la API dinámica y los scripts de automatización para **Futunet** desarrollados en Python con **FastAPI** y **PostgreSQL**.

---

## Estructura del Proyecto

*   `main.py`: Código del servidor FastAPI con los endpoints de productos y cotizaciones.
*   `seed.py`: Script de carga inicial (seeding) para migrar los productos del catálogo desde el JSON estático de la web a PostgreSQL.
*   `requirements.txt`: Dependencias de Python necesarias.

---

## Configuración y Despliegue en Render

### 1. Crear la Base de Datos en Render
1. Ve al panel de control de Render y haz clic en **New** -> **PostgreSQL**.
2. Nómbrala `futunet-db`, selecciona el plan **Free** y haz clic en **Create Database**.
3. Copia el valor de **External Database URL** (se usará localmente para el seed) y **Internal Database URL** (se usará en Render).

### 2. Desplegar el Web Service en Render
1. Sube este repositorio a tu cuenta de GitHub.
2. En Render, haz clic en **New** -> **Web Service** y selecciona este repositorio.
3. Configura las siguientes opciones:
    *   **Name**: `futunet-api`
    *   **Environment**: `Python`
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. En la pestaña **Environment**, añade la siguiente variable de entorno:
    *   `DATABASE_URL`: (Pega la **Internal Database URL** de tu base de datos de Render).
5. Haz clic en **Deploy Web Service**.

---

## Carga de Productos (Seeding) a PostgreSQL

Para importar tus productos actuales a la base de datos de Render:

1. Instala las dependencias localmente:
   ```bash
   pip install -r requirements.txt
   ```
2. Crea un archivo `.env` en la raíz de este proyecto y añade tu URL de base de datos externa:
   ```env
   DATABASE_URL=tu_external_database_url_aqui
   ```
3. Ejecuta el script de seeding:
   ```bash
   python seed.py
   ```
   *(Este script leerá el archivo `scratch_products.json` de tu proyecto web y cargará todos los productos directamente en la base de datos PostgreSQL de Render).*
