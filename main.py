import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

# --- Configuración de Base de Datos ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback para desarrollo local (puedes cambiarlo si deseas usar sqlite localmente)
    DATABASE_URL = "sqlite:///./futunet.db"

# Si es postgres, nos aseguramos de usar psycopg2
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Creamos el motor de base de datos
# Para sqlite necesitamos connect_args={"check_same_thread": False}
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Modelos de SQLAlchemy ---
class ProductModel(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False, index=True)
    brand = Column(String, index=True)
    category = Column(String, index=True)
    department = Column(String, index=True)
    price = Column(String)
    img = Column(String)
    desc = Column(Text)
    specs = Column(JSON, default=[])
    gallery = Column(JSON, default=[])
    isActive = Column(Boolean, default=True)

# Crear tablas
Base.metadata.create_all(bind=engine)

# --- Esquemas de Pydantic ---
class ProductSchema(BaseModel):
    id: str
    title: str
    brand: Optional[str] = None
    category: Optional[str] = None
    department: Optional[str] = None
    price: Optional[str] = None
    img: Optional[str] = None
    desc: Optional[str] = None
    specs: List[str] = []
    gallery: List[str] = []
    isActive: bool = True

    class Config:
        from_attributes = True

class QuoteRequest(BaseModel):
    client_name: str
    client_email: str
    client_phone: str
    message: str
    products: List[dict] # Lista de productos solicitados con cantidad

# --- Inicialización de FastAPI ---
app = FastAPI(
    title="Futunet API",
    description="Backend dinámico para catálogo y automatizaciones de Futunet",
    version="1.0.0"
)

# Configuración de CORS para permitir peticiones desde GitHub Pages
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción puedes especificar tu dominio de GitHub Pages
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dependencia de Sesión de Base de Datos ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Endpoints ---

@app.get("/")
def read_root():
    return {"status": "online", "message": "Bienvenido a la API de Futunet"}

@app.get("/api/products", response_model=List[ProductSchema])
def get_products(
    category: Optional[str] = None,
    department: Optional[str] = None,
    brand: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ProductModel).filter(ProductModel.isActive == True)
    
    if department:
        query = query.filter(ProductModel.department == department)
    if category:
        query = query.filter(ProductModel.category == category)
    if brand:
        query = query.filter(ProductModel.brand.ilike(brand))
        
    products = query.all()
    
    # Búsqueda manual simple si se especifica término de búsqueda
    if search:
        search_lower = search.lower()
        products = [
            p for p in products
            if search_lower in p.title.lower() or (p.desc and search_lower in p.desc.lower())
        ]
        
    return products

@app.get("/api/products/{product_id}", response_model=ProductSchema)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = db.query(ProductModel).filter(ProductModel.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product

@app.post("/api/quote")
def create_quote(quote: QuoteRequest):
    # Aquí puedes procesar la cotización: guardar en BD, enviar correo, etc.
    # Por ahora registramos la cotización simulando éxito
    print(f"Cotización recibida de: {quote.client_name} ({quote.client_email})")
    print(f"Productos cotizados: {quote.products}")
    return {
        "success": True,
        "message": f"Cotización recibida exitosamente. Nos comunicaremos contigo a {quote.client_email}."
    }
