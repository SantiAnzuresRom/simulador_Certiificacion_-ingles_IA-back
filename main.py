import os
import sys
import json
import random
import resend
from datetime import datetime
from typing import Optional, List

# --- CONFIGURACIÓN DE RUTAS ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = FastAPI(title="Certifica AI - Full Backend")

# Configuración de Resend (Para envío de correos reales)
# Asegúrate de tener RESEND_API_KEY en tu archivo .env
resend.api_key = os.getenv("RESEND_API_KEY")

# Inicializar cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Importación de Firebase
try:
    from app.core.firebase_config import db 
except Exception as e:
    db = None
    print(f"❌ Error al conectar Firebase: {e}")

# --- CONFIGURACIÓN DE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- BASE DE DATOS ÚNICA PARA OTP (Soluciona el error de código incorrecto) ---
otp_storage = {}

# --- MODELOS DE DATOS ---
class OTPRequest(BaseModel):
    email: str

class OTPVerify(BaseModel):
    email: str
    code: str

class UserRegister(BaseModel):
    uid: str
    full_name: str
    email: str
    phone: Optional[str] = ""
    birth_date: Optional[str] = ""

class ModuleRequest(BaseModel):
    type: str 
    level: str 

class GradeWritingRequest(BaseModel):
    content: str
    level: str
    prompt: str

class ChatMessage(BaseModel):
    message: str

class FinalResults(BaseModel):
    reading: Optional[float] = 0.0
    writing: Optional[float] = 0.0
    listening: Optional[float] = 0.0
    speaking: Optional[float] = 0.0
    level: str

# --- ENDPOINTS DE AUTENTICACIÓN (OTP) ---

@app.post("/api/v1/auth/send-otp")
async def send_otp(request: OTPRequest):
    try:
        email_clean = request.email.strip().lower()
        code = str(random.randint(10000000, 99999999))
        
        # Guardamos en la memoria del servidor
        otp_storage[email_clean] = code
        
        # ENVÍO DE CORREO REAL CON RESEND
        try:
            resend.Emails.send({
                "from": "CertificaAI <onboarding@resend.dev>",
                "to": [email_clean],
                "subject": f"{code} es tu código de verificación",
                "html": f"""
                    <div style="font-family: sans-serif; max-width: 400px; margin: auto; border: 1px solid #eee; padding: 20px; border-radius: 15px; text-align: center;">
                        <h2 style="color: #0f172a;">Verifica tu identidad</h2>
                        <p style="color: #64748b;">Copia este código para completar tu registro en CertificaAI:</p>
                        <div style="background: #f1f5f9; padding: 15px; border-radius: 10px; margin: 20px 0;">
                            <h1 style="letter-spacing: 8px; color: #000; margin: 0;">{code}</h1>
                        </div>
                        <p style="font-size: 11px; color: #94a3b8;">Este código expirará pronto. Si no solicitaste esto, ignora este mensaje.</p>
                    </div>
                """
            })
        except Exception as email_err:
            print(f"⚠️ Error enviando correo: {email_err}. Se mantiene el DEBUG en consola.")

        print(f"🔥 [DEBUG] Código OTP para {email_clean}: {code}")
        return {"status": "success", "message": "Código enviado con éxito"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar OTP: {str(e)}")

@app.post("/api/v1/auth/verify-otp")
async def verify_otp(request: OTPVerify):
    email_clean = request.email.strip().lower()
    input_code = request.code.strip()
    
    saved_code = otp_storage.get(email_clean)
    
    print(f"🔍 [VERIFY] Email: {email_clean} | Recibido: {input_code} | Esperado: {saved_code}")

    if saved_code and str(saved_code) == str(input_code):
        del otp_storage[email_clean]
        return {"status": "success", "message": "Verificación exitosa"}
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, 
        detail="Código incorrecto o expirado, bro"
    )

# --- ENDPOINTS DE USUARIO ---

@app.post("/api/v1/users/register")
async def register_user(user: UserRegister):
    if not db:
        raise HTTPException(status_code=500, detail="Firestore no configurado")
    try:
        db.collection("users").document(user.uid).set({
            "full_name": user.full_name.strip().title(),
            "email": user.email.strip().lower(),
            "phone": user.phone,
            "birth_date": user.birth_date,
            "created_at": datetime.now()
        })
        return {"status": "success", "message": "Perfil guardado correctamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINTS DE INTELIGENCIA ARTIFICIAL (GPT-4o) ---

@app.post("/api/v1/generate-questions")
async def generate_questions(req: ModuleRequest):
    prompt_templates = {
        "reading": "Generate a title, a 3-paragraph passage, and 5 multiple choice questions. JSON format: { 'title': '...', 'passage': '...', 'questions': [{ 'question': '...', 'options': ['...', '...'], 'correctAnswer': '...' }] }",
        "listening": "Generate a conversational transcript (passage) and 5 questions. JSON format: { 'passage': '...', 'questions': [{ 'question': '...', 'options': ['...', '...'], 'correctAnswer': '...' }] }",
        "writing": "Generate a writing prompt. JSON format: { 'title': '...', 'passage': '...' }",
        "speaking": "Generate 1 clear English sentence for pronunciation practice. JSON format: { 'targetSentence': '...', 'prompt': 'Pronounce the following sentence clearly.' }"
    }
    instruction = prompt_templates.get(req.type, "General English task.")
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional CEFR language examiner. Return ONLY valid JSON."},
                {"role": "user", "content": f"Level: {req.level.upper()}. Task: {instruction}"}
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error con el motor de IA")

@app.post("/api/v1/chatbot")
async def chatbot_helper(data: ChatMessage):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres el asistente de Certifica_AI. Responde usando Markdown."},
                {"role": "user", "content": data.message}
            ],
            max_tokens=250
        )
        return {"reply": response.choices[0].message.content}
    except Exception:
        return {"reply": "**Error de conexión** con la IA."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)