import os
import json
import datetime
import smtplib
from typing import List, Optional
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv
from fpdf import FPDF

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
    shipping_address: str
    shipping_notes: Optional[str] = ""
    payment_method: str
    products: List[dict]
    total: float

# --- Utilidades de Cotizaciones ---

def clean_pdf_text(text: str) -> str:
    """Evita errores de codificación unicode convirtiendo a Latin-1 de forma segura."""
    if not text:
        return ""
    try:
        return text.encode("latin-1", "replace").decode("latin-1")
    except Exception:
        return text

class QuotePDF(FPDF):
    def header(self):
        # Banner superior color azul Futunet
        self.set_fill_color(10, 112, 162)
        self.rect(0, 0, 215.9, 12, 'F')
        self.ln(15)

    def footer(self):
        self.set_y(-25)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        # Línea divisoria
        self.set_draw_color(220, 220, 220)
        self.line(10, self.get_y(), 205, self.get_y())
        self.ln(2)
        
        self.cell(0, 4, clean_pdf_text("FUTUNET SRL | RNC: 132-70207-7 | Tel: 829-741-1041 | Email: ventas@futunet.com"), align="C", ln=True)
        self.cell(0, 4, clean_pdf_text("Santo Domingo, República Dominicana | www.futunet.com"), align="C", ln=True)
        self.cell(0, 4, clean_pdf_text(f"Página {self.page_no()}/{{nb}}"), align="C")

def generate_quote_pdf(quote: QuoteRequest, order_id: str) -> bytes:
    pdf = QuotePDF(orientation="P", unit="mm", format="letter")
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # 1. Cabecera de la Empresa
    pdf.set_font("helvetica", "B", 20)
    pdf.set_text_color(10, 112, 162)
    pdf.cell(110, 8, clean_pdf_text("FUTUNET SRL"), ln=False)
    
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(85, 8, clean_pdf_text("COTIZACIÓN"), align="R", ln=True)
    
    # Subtítulo e Información
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(110, 4, clean_pdf_text("Soluciones Tecnológicas e Infraestructura de Redes"), ln=False)
    
    # Fecha y ID
    now_str = datetime.datetime.now().strftime("%d/%m/%Y")
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(85, 4, clean_pdf_text(f"Fecha: {now_str}"), align="R", ln=True)
    
    pdf.cell(110, 4, "", ln=False)
    pdf.cell(85, 4, clean_pdf_text(f"Cotización No: {order_id}"), align="R", ln=True)
    
    pdf.ln(8)
    
    # Línea Divisoria
    pdf.set_draw_color(220, 220, 220)
    pdf.line(10, pdf.get_y(), 205, pdf.get_y())
    pdf.ln(5)
    
    # 2. Información del Cliente y Pago (Dos columnas)
    y_before_card = pdf.get_y()
    
    # Columna 1: Cliente
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(10, 112, 162)
    pdf.cell(100, 5, clean_pdf_text("CLIENTE"), ln=True)
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(100, 4.5, clean_pdf_text(f"Nombre: {quote.client_name}"), ln=True)
    pdf.cell(100, 4.5, clean_pdf_text(f"Teléfono: {quote.client_phone}"), ln=True)
    pdf.cell(100, 4.5, clean_pdf_text(f"Correo: {quote.client_email}"), ln=True)
    
    # Dirección multilinea
    pdf.set_x(10)
    pdf.write(4.5, clean_pdf_text("Dirección: "))
    pdf.write(4.5, clean_pdf_text(quote.shipping_address or "No especificada"))
    pdf.ln(6)
    
    y_after_customer = pdf.get_y()
    
    # Columna 2: Detalles de Pago
    pdf.set_y(y_before_card)
    pdf.set_x(120)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(10, 112, 162)
    pdf.cell(85, 5, clean_pdf_text("DETALLES DE PAGO"), align="R", ln=True)
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(40, 40, 40)
    pm_name = "Transferencia Bancaria" if quote.payment_method == "bank_transfer" else "WhatsApp (Pedido Rápido)"
    pdf.set_x(120)
    pdf.cell(85, 4.5, clean_pdf_text(f"Método de Pago: {pm_name}"), align="R", ln=True)
    pdf.set_x(120)
    pdf.cell(85, 4.5, clean_pdf_text("Validez: 15 días"), align="R", ln=True)
    pdf.set_x(120)
    pdf.cell(85, 4.5, clean_pdf_text("Moneda: Pesos Dominicanos (DOP)"), align="R", ln=True)
    
    pdf.set_y(max(y_after_customer, pdf.get_y()) + 6)
    
    # 3. Tabla de Productos
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(10, 112, 162)
    pdf.set_text_color(255, 255, 255)
    
    # Ancho total imprimible: 195mm (márgenes de 10mm a cada lado en hoja Letter)
    # Columnas: Producto (90), Marca (30), Cant. (15), Precio (30), Subtotal (30)
    col_widths = [90, 30, 15, 30, 30]
    headers = ["Producto", "Marca", "Cant.", "Precio Unit.", "Subtotal"]
    
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, clean_pdf_text(h), border=1, align="C" if h != "Producto" else "L", fill=True)
    pdf.ln(7)
    
    pdf.set_text_color(40, 40, 40)
    pdf.set_font("helvetica", "", 9)
    
    bg_light = True
    for p in quote.products:
        if bg_light:
            pdf.set_fill_color(248, 250, 252)
        else:
            pdf.set_fill_color(255, 255, 255)
        bg_light = not bg_light
        
        # Limitar longitud para evitar desbordes en celdas de una sola línea
        p_title = p.get('title', '')
        if len(p_title) > 45:
            p_title = p_title[:42] + "..."
        p_brand = p.get('brand', '')
        if len(p_brand) > 16:
            p_brand = p_brand[:14] + ".."
            
        qty = p.get('qty', 1)
        price = p.get('price', 0.0)
        subtotal = price * qty
        
        pdf.cell(90, 6.5, clean_pdf_text(f" {p_title}"), border=1, fill=True)
        pdf.cell(30, 6.5, clean_pdf_text(p_brand), border=1, align="C", fill=True)
        pdf.cell(15, 6.5, str(qty), border=1, align="C", fill=True)
        pdf.cell(30, 6.5, f"RD$ {price:,.2f}", border=1, align="R", fill=True)
        pdf.cell(30, 6.5, f"RD$ {subtotal:,.2f}", border=1, align="R", fill=True)
        pdf.ln(6.5)
        
    # Fila de Totales
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(10, 112, 162)
    pdf.cell(135, 6, "", ln=False)
    pdf.cell(30, 6, clean_pdf_text("TOTAL:"), align="R", ln=False)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(30, 6, f"RD$ {quote.total:,.2f}", align="R", ln=True)
    
    # 4. Datos de Cuenta / Instrucciones
    if quote.payment_method == "bank_transfer":
        pdf.ln(6)
        pdf.set_fill_color(245, 247, 250)
        pdf.set_draw_color(10, 112, 162)
        pdf.rect(10, pdf.get_y(), 195, 24, 'FD')
        
        pdf.set_y(pdf.get_y() + 2)
        pdf.set_x(12)
        pdf.set_font("helvetica", "B", 9)
        pdf.set_text_color(10, 112, 162)
        pdf.cell(0, 4.5, clean_pdf_text("INSTRUCCIONES DE PAGO - TRANSFERENCIA BANCARIA:"), ln=True)
        
        pdf.set_font("helvetica", "", 8.5)
        pdf.set_text_color(40, 40, 40)
        pdf.set_x(12)
        pdf.cell(0, 4, clean_pdf_text("Por favor, realice la transferencia a la cuenta oficial de Futunet SRL:"), ln=True)
        pdf.set_x(12)
        pdf.cell(0, 4, clean_pdf_text("Banco: Banreservas | Cuenta Corriente: 9605759674 | RNC: 132702077 | Beneficiario: FUTUNET SRL"), ln=True)
        pdf.set_x(12)
        pdf.cell(0, 4, clean_pdf_text("Importante: Suba el comprobante de pago en el formulario web una vez finalizada la transferencia."), ln=True)
        pdf.ln(10)
    else:
        pdf.ln(6)
        pdf.set_fill_color(245, 247, 250)
        pdf.rect(10, pdf.get_y(), 195, 12, 'F')
        pdf.set_y(pdf.get_y() + 2)
        pdf.set_x(12)
        pdf.set_font("helvetica", "I", 8.5)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 4, clean_pdf_text("Nota: Su pedido ha sido solicitado vía WhatsApp. Un representante se pondrá en contacto con usted"), ln=True)
        pdf.set_x(12)
        pdf.cell(0, 4, clean_pdf_text("para coordinar los detalles de entrega y confirmar disponibilidad de los artículos."), ln=True)
        pdf.ln(8)
        
    # Notas adicionales del envío
    if quote.shipping_notes:
        pdf.set_font("helvetica", "B", 9)
        pdf.set_text_color(10, 112, 162)
        pdf.cell(0, 4.5, clean_pdf_text("Notas de Envío / Referencias de Entrega:"), ln=True)
        pdf.set_font("helvetica", "", 8.5)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 4, clean_pdf_text(quote.shipping_notes))
        
    return pdf.output()

def send_email_with_pdf(quote: QuoteRequest, pdf_data: bytes, pdf_filename: str, order_id: str) -> bool:
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_sender = os.getenv("SMTP_SENDER")
    admin_email = os.getenv("ADMIN_EMAIL")
    
    if not all([smtp_server, smtp_port, smtp_user, smtp_password, smtp_sender]):
        print("⚠️ Advertencia: Configuración SMTP incompleta. No se enviará correo electrónico.")
        return False
        
    try:
        # Contenedor del mensaje
        msg = MIMEMultipart()
        msg['From'] = smtp_sender
        msg['To'] = quote.client_email
        msg['Subject'] = f"Cotización Futunet #{order_id} - {quote.client_name}"
        
        # Destinatarios y Copia a Admin
        recipients = [quote.client_email]
        if admin_email:
            msg['Cc'] = admin_email
            recipients.append(admin_email)
            
        # Cuerpo del correo electrónico en HTML
        pm_display = "Transferencia Bancaria" if quote.payment_method == "bank_transfer" else "WhatsApp (Pedido Rápido)"
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333333; line-height: 1.6; margin: 0; padding: 20px; background-color: #f4f6f9;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; background-color: #ffffff; box-shadow: 0 4px 12px rgba(10, 112, 162, 0.08);">
                <div style="background-color: #0A70A2; padding: 24px; text-align: center; color: white;">
                    <h2 style="margin: 0; font-size: 24px; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">FUTUNET SRL</h2>
                    <p style="margin: 4px 0 0 0; font-size: 14px; opacity: 0.9;">¡Cotización Generada Exitosamente!</p>
                </div>
                <div style="padding: 24px;">
                    <p>Estimado(a) <strong>{quote.client_name}</strong>,</p>
                    <p>Gracias por tu interés en nuestros productos y servicios de redes, tecnología y mobiliario. Hemos procesado tu solicitud de cotización con la referencia <strong>#{order_id}</strong>.</p>
                    <p>Adjunto a este correo encontrarás el documento formal en PDF con los precios, cantidades y términos correspondientes.</p>
                    
                    <div style="margin: 24px 0; padding: 18px; background-color: #f8fafc; border-left: 4px solid #0A70A2; border-radius: 6px;">
                        <h4 style="margin: 0 0 10px 0; color: #0A70A2; font-size: 15px;">Resumen del Pedido:</h4>
                        <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 4px 0; font-weight: bold; width: 120px;">Código:</td>
                                <td style="padding: 4px 0;">#{order_id}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px 0; font-weight: bold;">Cliente:</td>
                                <td style="padding: 4px 0;">{quote.client_name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px 0; font-weight: bold;">Teléfono:</td>
                                <td style="padding: 4px 0;">{quote.client_phone}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px 0; font-weight: bold;">Método de Pago:</td>
                                <td style="padding: 4px 0;">{pm_display}</td>
                            </tr>
                            <tr>
                                <td style="padding: 4px 0; font-weight: bold;">Total Estimado:</td>
                                <td style="padding: 4px 0; color: #0A70A2; font-weight: bold; font-size: 14px;">RD$ {quote.total:,.2f}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <p>Un representante de ventas revisará los detalles a la brevedad para coordinar la facturación formal, stock de los equipos y forma de entrega.</p>
                    
                    <p style="margin-top: 32px; font-size: 12px; color: #888888; border-top: 1px solid #e2e8f0; padding-top: 16px; text-align: center;">
                        Este correo electrónico contiene información referencial generada automáticamente. Por favor, no respondas directamente a este mensaje.
                        Para dudas o asistencia inmediata, contáctanos al 829-741-1041 o escríbenos a ventas@futunet.com.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_body, 'html'))
        
        # Adjuntar PDF
        part = MIMEBase('application', "octet-stream")
        part.set_payload(pdf_data)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{pdf_filename}"')
        msg.attach(part)
        
        # Conexión al servidor SMTP
        port = int(smtp_port)
        if port == 465:
            server = smtplib.SMTP_SSL(smtp_server, port)
        else:
            server = smtplib.SMTP(smtp_server, port)
            server.starttls()
            
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_sender, recipients, msg.as_string())
        server.close()
        print(f"📧 Correo enviado a {quote.client_email} y CC a {admin_email or 'ninguno'}")
        return True
    except Exception as e:
        print(f"❌ Error al enviar el correo SMTP: {e}")
        return False

# --- Endpoints ---

@app.get("/")
def read_root():
    return {
        "status": "online",
        "firebase_connected": firebase_initialized,
        "message": "Bienvenido a la API de Futunet (Firestore Sync Edition)"
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
    
    # Generar un ID de orden/cotización aleatorio y único
    random_part = datetime.datetime.now().strftime("%y%m%d%H%M")
    order_id = f"FT-{random_part}"
    
    try:
        # Generar PDF
        pdf_data = generate_quote_pdf(quote, order_id)
        pdf_filename = f"cotizacion_{order_id}.pdf"
        
        # Enviar correo con el PDF adjunto
        email_sent = send_email_with_pdf(quote, pdf_data, pdf_filename, order_id)
        
        # Guardar registro en Firestore si está inicializado
        if firebase_initialized:
            try:
                db.collection("quotes").document(order_id).set({
                    "orderId": order_id,
                    "clientName": quote.client_name,
                    "clientEmail": quote.client_email,
                    "clientPhone": quote.client_phone,
                    "shippingAddress": quote.shipping_address,
                    "shippingNotes": quote.shipping_notes,
                    "paymentMethod": quote.payment_method,
                    "total": quote.total,
                    "emailSent": email_sent,
                    "createdAt": firestore.SERVER_TIMESTAMP,
                    "products": quote.products
                })
                print(f"✅ Cotización {order_id} guardada en Firestore.")
            except Exception as fe:
                print(f"⚠️ Error al guardar cotización en Firestore: {fe}")
                
        return {
            "success": True,
            "order_id": order_id,
            "email_sent": email_sent,
            "message": f"Cotización #{order_id} procesada exitosamente. Se ha enviado al correo {quote.client_email}."
        }
    except Exception as e:
        print(f"❌ Error al procesar cotización: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno procesando cotización: {e}")
