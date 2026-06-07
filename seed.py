import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from main import Base, ProductModel

load_dotenv()

# --- Configuración de Base de Datos ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./futunet.db"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

print(f"Conectando a base de datos para seeding: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

# Asegurar que las tablas existan
Base.metadata.create_all(bind=engine)

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
        print(f"Error: No se encontró el archivo de datos en {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = data.get("documents", [])
    print(f"Encontrados {len(documents)} documentos en el archivo JSON.")

    count = 0
    for doc in documents:
        fields = doc.get("fields", {})
        if not fields:
            continue

        # Extraer campos de forma segura
        p_id = fields.get("id", {}).get("stringValue")
        if not p_id:
            # Si no tiene ID, lo obtenemos de la ruta del nombre del documento
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
        
        # El booleano puede venir como booleanValue
        is_active = fields.get("isActive", {}).get("booleanValue")
        if is_active is None:
            is_active = True

        specs = parse_array_field(fields.get("specs"))
        gallery = parse_array_field(fields.get("gallery"))

        # Crear o actualizar en la base de datos
        existing_product = db.query(ProductModel).filter(ProductModel.id == p_id).first()
        if existing_product:
            existing_product.title = title
            existing_product.brand = brand
            existing_product.category = category
            existing_product.department = department
            existing_product.price = price
            existing_product.img = img
            existing_product.desc = desc
            existing_product.specs = specs
            existing_product.gallery = gallery
            existing_product.isActive = is_active
        else:
            new_product = ProductModel(
                id=p_id,
                title=title,
                brand=brand,
                category=category,
                department=department,
                price=price,
                img=img,
                desc=desc,
                specs=specs,
                gallery=gallery,
                isActive=is_active
            )
            db.add(new_product)
        
        count += 1

    try:
        db.commit()
        print(f"Seeding completado con éxito. {count} productos procesados en la base de datos.")
    except Exception as e:
        db.rollback()
        print(f"Error al guardar los datos en la base de datos: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
