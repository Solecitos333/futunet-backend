# Futunet Backend - API & Sincronización (Firebase Edition)

Este repositorio contiene la API dinámica y los scripts de automatización para **Futunet** desarrollados en Python con **FastAPI** y **Firebase Firestore** (Base de Datos permanente y gratuita).

---

## Estructura del Proyecto

*   `main.py`: Código del servidor FastAPI con los endpoints de consulta de productos y cotizaciones.
*   `seed.py`: Script para cargar/restaurar los productos del catálogo desde el JSON estático de la web directamente hacia Firebase.
*   `requirements.txt`: Dependencias de Python necesarias.

---

## Configuración y Despliegue en Render

### 1. Obtener la clave privada de Firebase
1. Ve a la consola de Firebase: [console.firebase.google.com](https://console.firebase.google.com).
2. Haz clic en el ícono de engranaje (Configuración) -> **Configuración del proyecto**.
3. Ve a la pestaña **Cuentas de servicio** (Service accounts).
4. Haz clic en **Generar nueva clave privada**. Esto descargará un archivo `.json` privado a tu computadora.

### 2. Desplegar en Render
1. Sube este repositorio a tu cuenta de GitHub.
2. En Render, haz clic en **New** -> **Web Service** y selecciona este repositorio.
3. Configura las siguientes opciones:
    *   **Name**: `futunet-api`
    *   **Environment**: `Python`
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. En la pestaña **Environment**, añade la siguiente variable de entorno:
    *   **Clave**: `FIREBASE_CREDENTIALS`
    *   **Valor**: Abre el archivo `.json` descargado de Firebase, copia **todo su contenido** (debe ser un JSON completo con `{ ... }`) y pégalo completo en el valor de esta variable.
    *   *(Opcional)* **Clave**: `SYNC_TOKEN` | **Valor**: `un_token_secreto_para_sincronizaciones` (sirve para proteger el endpoint de carga).
5. Haz clic en **Deploy Web Service**.

---

## Ejecución y Pruebas Locales

Para ejecutar el servidor o el script de carga localmente en tu computadora:

1. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. Renombra el archivo `.json` descargado de Firebase como `firebase-service-account.json` y colócalo en la raíz de esta carpeta.
3. Ejecuta el script de carga inicial:
   ```bash
   python seed.py
   ```
4. Para iniciar el servidor de desarrollo localmente:
   ```bash
   uvicorn main:app --reload
   ```
