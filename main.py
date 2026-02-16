import os
import json
import random
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# Importación de Firebase
try:
    from app.core.firebase_config import db 
except ImportError:
    db = None
    print("⚠️ Advertencia: No se pudo cargar Firebase.")

# Cargar variables de entorno
load_dotenv()

app = FastAPI(title="Certifica AI - Full Backend")

# --- CONFIGURACIÓN DE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- BASE DE DATOS TEMPORAL PARA OTP ---
otp_storage = {}

# --- MODELOS DE DATOS (PYDANTIC) ---

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
    type: str # reading, writing, listening, speaking
    level: str # A1, A2, B1, B2, C1, C2

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
        # Limpiamos el email y lo pasamos a minúsculas
        email_clean = request.email.strip().lower()
        code = str(random.randint(10000000, 99999999))
        otp_storage[email_clean] = code
        
        print(f"🔥 [DEBUG] Código OTP para {email_clean}: {code}")
        return {"status": "success", "message": "Código enviado con éxito"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar OTP: {str(e)}")

@app.post("/api/v1/auth/verify-otp")
async def verify_otp(request: OTPVerify):
    email_clean = request.email.strip().lower()
    saved_code = otp_storage.get(email_clean)
    
    if saved_code and saved_code == request.code.strip():
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
        # Guardamos el nombre en formato Título (Juan Perez) y email en minúsculas
        db.collection("users").document(user.uid).set({
            "full_name": user.full_name.strip().title(),
            "email": user.email.strip().lower(),
            "phone": user.phone,
            "birth_date": user.birth_date,
            "created_at": datetime.now()
        })
        return {"status": "success", "message": "Perfil guardado en Firebase"}
    except Exception as e:
        print(f"Error Firestore: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINTS DE INTELIGENCIA ARTIFICIAL ---

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
        
        data = json.loads(response.choices[0].message.content)
        
        # --- FORMATEO A TÍTULOS (Capitalizar respuestas) ---
        if "questions" in data:
            for q in data["questions"]:
                q["options"] = [opt.capitalize() for opt in q["options"]]
                q["correctAnswer"] = q["correctAnswer"].capitalize()
        
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error con el motor de IA")

@app.post("/api/v1/grade-writing")
async def grade_writing(req: GradeWritingRequest):
    try:
        prompt_grade = f"""
        Actúa como un examinador oficial de nivel {req.level.upper()}.
        Consigna: {req.prompt}
        Texto del alumno: {req.content}
        Evalúa gramática, vocabulario y coherencia. 
        Devuelve ÚNICAMENTE un JSON con:
        1. "score": Un número entero del 0 al 100.
        2. "feedback": Un párrafo breve en español con consejos específicos.
        """
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un evaluador profesional de idiomas. Responde estrictamente en JSON."},
                {"role": "user", "content": prompt_grade}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"score": 0, "feedback": "Error técnico en la evaluación."}

@app.post("/api/v1/generate-report")
async def generate_final_report(data: FinalResults):
    prompt_report = f"""
    Actúa como un coach experto en idiomas. Nivel: {data.level.upper()}.
    Scores: Reading {data.reading}%, Writing {data.writing}%, Listening {data.listening}%, Speaking {data.speaking}%.
    Analiza debilidades y fortalezas. Feedback en español motivador.
    JSON: {{"ai_advice": "...", "steps": ["...", "...", "..."]}}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un coach de idiomas profesional. Responde en JSON."},
                {"role": "user", "content": prompt_report}
            ],
            response_format={"type": "json_object"}
        )
        report_content = json.loads(response.choices[0].message.content)
        return {
            "scores": data.model_dump(),
            "ai_advice": report_content.get("ai_advice"),
            "steps": [step.capitalize() for step in report_content.get("steps", [])]
        }
    except Exception:
        return {"ai_advice": "¡Sigue practicando!", "steps": ["Estudia más", "Lee diario"]}

@app.post("/api/v1/chatbot")
async def chatbot_helper(data: ChatMessage):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres el asistente de Certifica_AI. Responde de forma clara."},
                {"role": "user", "content": data.message}
            ],
            max_tokens=150
        )
        return {"reply": response.choices[0].message.content}
    except Exception:
        return {"reply": "Error de conexión con la IA."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)