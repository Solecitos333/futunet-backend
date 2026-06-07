import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

# --- Inicialización de Firebase ---
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
    except Exception as e:
        print(f"Error con FIREBASE_CREDENTIALS: {e}")
else:
    service_account_path = os.path.join(os.path.dirname(__file__), "firebase-service-account.json")
    if os.path.exists(service_account_path):
        try:
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
            db = firestore.client()
            firebase_initialized = True
        except Exception as e:
            print(f"Error con archivo local: {e}")

if not firebase_initialized:
    print("❌ Error: No se encontraron credenciales de Firebase. Configura la variable de entorno FIREBASE_CREDENTIALS o coloca el archivo firebase-service-account.json en esta carpeta.")
    exit(1)

# Ruta del archivo JSON de respaldo de productos
json_path = os.path.join("..", "proyecto_github_pages", "scratch_products.json")

def parse_array_field(field_data):
    if not field_data:
        return []
    array_val = field_data.get("arrayValue", {})
    if not array_val:
        return []
    vals = array_val.get("values", [])
    result = []
    if isinstance(vals, list):
        for v in vals:
            if isinstance(v, dict) and "stringValue" in v:
                result.append(v["stringValue"])
            elif isinstance(v, str):
                result.append(v)
    elif isinstance(vals, dict) and "stringValue" in vals:
        result.append(vals["stringValue"])
    elif isinstance(vals, str):
        cleaned = vals.strip()
        if cleaned:
            result.append(cleaned)
    return result

def seed_database():
    if not os.path.exists(json_path):
        print(f"❌ Error: No se encontró el archivo de datos en {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = data.get("documents", [])
    print(f"📖 Leyendo {len(documents)} productos del respaldo JSON...")

    products_ref = db.collection("products")
    batch = db.batch()
    count = 0
    total_committed = 0

    for doc in documents:
        fields = doc.get("fields", {})
        if not fields:
            continue

        p_id = fields.get("id", {}).get("stringValue")
        if not p_id:
            name_path = doc.get("name", "")
            p_id = name_path.split("/")[-1] if name_path else None

        if not p_id:
            continue

        title = fields.get("title", {}).get("stringValue", "Producto sin título")
        brand = fields.get("brand", {}).get("stringValue", "Genérico")
        category = fields.get("category", {}).get("stringValue", "General")
        department = fields.get("department", {}).get("stringValue", "general")
        price = fields.get("price", {}).get("stringValue", "Cotizar")
        img = fields.get("img", {}).get("stringValue", "")
        desc = fields.get("desc", {}).get("stringValue", "")
        
        is_active = fields.get("isActive", {}).get("booleanValue")
        if is_active is None:
            is_active = True

        specs = parse_array_field(fields.get("specs"))
        gallery = parse_array_field(fields.get("gallery"))

        doc_ref = products_ref.document(p_id)
        
        product_data = {
            "id": p_id,
            "title": title,
            "brand": brand,
            "category": category,
            "department": department,
            "price": price,
            "img": img,
            "desc": desc,
            "specs": specs,
            "gallery": gallery,
            "isActive": is_active
        }

        batch.set(doc_ref, product_data)
        count += 1
        total_committed += 1

        if count >= 450:
            batch.commit()
            print(f"📦 Lote de {count} productos guardado en Firestore...")
            batch = db.batch()
            count = 0

    if count > 0:
        batch.commit()
        print(f"📦 Último lote de {count} productos guardado en Firestore...")

    print(f"✅ Seeding completado. {total_committed} productos actualizados/cargados en Firebase Firestore.")

if __name__ == "__main__":
    seed_database()
