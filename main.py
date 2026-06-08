import os
import json
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

# --- Inicialización de Firebase Admin ---
firebase_initialized = False
db = None

cred_json = os.getenv("FIREBASE_CREDENTIALS")
if cred_json:
    try:
        cred_dict = json.loads(cred_json)
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)
        db = firestore.client()
        firebase_initialized = True
        print("🔥 Firebase Admin inicializado mediante variable de entorno.")
    except Exception as e:
        print(f"❌ Error al inicializar Firebase con FIREBASE_CREDENTIALS (intentando fallback de archivo): {e}")

# Si no se pudo inicializar con la variable de entorno, intentar con archivos
if not firebase_initialized:
    service_account_path = os.path.join(os.path.dirname(__file__), "firebase-service-account.json")
    etc_secrets_path = "/etc/secrets/firebase-service-account.json"
    
    selected_path = None
    if os.path.exists(service_account_path):
        selected_path = service_account_path
    elif os.path.exists(etc_secrets_path):
        selected_path = etc_secrets_path

    if selected_path:
        try:
            cred = credentials.Certificate(selected_path)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            firebase_initialized = True
            print(f"🔥 Firebase Admin inicializado mediante archivo en: {selected_path}")
        except Exception as e:
            print(f"❌ Error al inicializar Firebase con archivo: {e}")
            
if not firebase_initialized:
    print("⚠️ Advertencia: No se encontraron credenciales de Firebase válidas. La API funcionará en modo degradado.")

# --- Inicialización de FastAPI ---
app = FastAPI(
    title="Futunet API",
    description="Backend dinámico para sincronización de inventario y utilidades de Futunet",
    version="2.0.0"
)

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Esquemas de Pydantic ---
class ProductSyncItem(BaseModel):
    title: str
    brand: str
    category: str
    price: str
    img: str
    gallery: List[str] = []
    desc: str = ""
    specs: List[str] = []
    department: str = "general"

class QuoteRequest(BaseModel):
    client_name: str
    client_email: str
    client_phone: str
    message: str
    products: List[dict]

# --- Endpoints ---

@app.get("/")
def read_root():
    return {
        "status": "online",
        "firebase_connected": firebase_initialized,
        "message": "Bienvenido a la API de Futunet (Firestore Sync Edition)"
    }

@app.get("/api/debug-firebase")
def debug_firebase():
    import os
    service_account_path = os.path.join(os.path.dirname(__file__), "firebase-service-account.json")
    etc_secrets_path = "/etc/secrets/firebase-service-account.json"
    
    # Capturar también posibles errores de inicialización o excepciones
    global firebase_initialized
    return {
        "firebase_connected": firebase_initialized,
        "env_credentials_exists": os.getenv("FIREBASE_CREDENTIALS") is not None,
        "env_credentials_length": len(os.getenv("FIREBASE_CREDENTIALS")) if os.getenv("FIREBASE_CREDENTIALS") else 0,
        "local_file_exists": os.path.exists(service_account_path),
        "etc_secrets_exists": os.path.exists(etc_secrets_path),
        "current_dir": os.getcwd(),
        "files_in_current_dir": os.listdir(os.getcwd()) if os.path.exists(os.getcwd()) else [],
        "etc_secrets_dir_exists": os.path.exists("/etc/secrets"),
        "files_in_etc_secrets": os.listdir("/etc/secrets") if os.path.exists("/etc/secrets") else []
    }


@app.get("/api/products")
def get_products(category: Optional[str] = None, department: Optional[str] = None):
    """
    Endpoint alternativo para obtener productos desde Firestore en Python.
    Nota: El frontend principal sigue leyendo de Firebase de forma directa.
    """
    if not firebase_initialized:
        raise HTTPException(status_code=500, detail="Firebase no está configurado.")
    
    try:
        ref = db.collection("products")
        query = ref.where("isActive", "==", True)
        
        if department:
            query = query.where("department", "==", department)
        if category:
            query = query.where("category", "==", category)
            
        docs = query.stream()
        products = []
        for doc in docs:
            products.append({"id": doc.id, **doc.to_dict()})
        return products
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando base de datos: {e}")

@app.post("/api/sync-inventory")
def sync_inventory(
    products: List[ProductSyncItem],
    x_sync_token: Optional[str] = Header(None)
):
    """
    Endpoint para sincronizar productos desde fuentes externas (como un scraper de proveedores).
    Se protege usando un token simple en las cabeceras (X-Sync-Token).
    """
    if not firebase_initialized:
        raise HTTPException(status_code=500, detail="Firebase no está configurado.")
        
    # Validar token de seguridad simple
    expected_token = os.getenv("SYNC_TOKEN", "default_secret_token")
    if x_sync_token != expected_token:
        raise HTTPException(status_code=401, detail="No autorizado.")
        
    try:
        batch = db.batch()
        products_ref = db.collection("products")
        
        count = 0
        for item in products:
            # Generar un ID estable a partir del título del producto para evitar duplicados
            clean_title = "".join(c for c in item.title if c.isalnum()).lower()
            doc_id = f"sync_{item.brand.lower()}_{clean_title[:30]}"
            
            doc_ref = products_ref.document(doc_id)
            data = item.dict()
            data["id"] = doc_id
            data["isActive"] = True
            
            batch.set(doc_ref, data)
            count += 1
            
            # Firestore batch tiene un límite de 500 operaciones
            if count >= 450:
                batch.commit()
                batch = db.batch()
                count = 0
                
        batch.commit()
        return {"success": True, "message": f"Sincronizados {len(products)} productos correctamente."}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante la sincronización: {e}")

@app.post("/api/quote")
def create_quote(quote: QuoteRequest):
    print(f"Cotización recibida para: {quote.client_name} ({quote.client_email})")
    # Aquí puedes añadir código para guardar la cotización en Firestore o enviar un email/WhatsApp
    return {
        "success": True,
        "message": f"Cotización procesada exitosamente. Nos comunicaremos al correo {quote.client_email}."
    }
