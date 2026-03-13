import os
import sys
import json
import io
import re
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv

# --- CONFIGURACIÓN DE RUTAS ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

app = FastAPI(title="Certifica AI - Unified Core & Voice Engine")

# Inicializar cliente OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Importación de Firebase (con manejo de errores)
try:
    from app.core.firebase_config import db 
except Exception as e:
    db = None
    print(f"⚠️ Alerta: Firestore no conectado, modo local activo. Error: {e}")

# --- CONFIGURACIÓN DE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DATOS ---
class UserRegister(BaseModel):
    uid: str
    full_name: str
    email: str
    phone: Optional[str] = ""
    birth_date: Optional[str] = ""

class ModuleRequest(BaseModel):
    type: str 
    level: str 

class VoiceRequest(BaseModel):
    text: str
    voice: Optional[str] = "nova"
    speed: Optional[float] = 1.0

class ChatMessage(BaseModel):
    message: str

class ReportRequest(BaseModel):
    reading: float
    listening: float
    writing: float
    speaking: float
    level: str

# --- UTILIDADES DE VOZ ---
def clean_text_for_speech(text: str) -> str:
    """Añade pausas naturales y limpia el texto para el modelo TTS."""
    text = text.replace(" - ", ", ")
    text = re.sub(r'\.(?=[A-Z])', '. ', text)
    if not text.endswith(('.', '?', '!')):
        text += "."
    return text

# --- ENDPOINTS ---

@app.post("/api/v1/users/register")
async def register_user(user: UserRegister):
    if not db:
        raise HTTPException(status_code=500, detail="Firestore no disponible")
    try:
        db.collection("users").document(user.uid).set({
            "full_name": user.full_name.strip().title(),
            "email": user.email.strip().lower(),
            "phone": user.phone,
            "birth_date": user.birth_date,
            "created_at": datetime.now()
        })
        return {"status": "success", "message": "Perfil sincronizado"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/voice/speak")
async def generate_pro_voice(req: VoiceRequest):
    try:
        clean_text = clean_text_for_speech(req.text)
        response = client.audio.speech.create(
            model="tts-1-hd", 
            voice=req.voice,
            input=clean_text,
            speed=req.speed
        )
        return StreamingResponse(io.BytesIO(response.content), media_type="audio/mpeg")
    except Exception as e:
        print(f"❌ Error en TTS: {e}")
        raise HTTPException(status_code=500, detail="Error en el motor de voz")

@app.post("/api/v1/generate-questions")
async def generate_questions(req: ModuleRequest):
    # Diccionario de Prompts mejorados para asegurar Nivel CEFR y estructura limpia
    prompt_templates = {
        "reading": f"Generate a title, a 3-paragraph passage, and 5 multiple choice questions for CEFR level {req.level.upper()}. JSON format: {{ 'title': '...', 'passage': '...', 'questions': [{{ 'question': '...', 'options': ['...', '...'], 'correctAnswer': '...' }}] }}",
        "listening": f"Generate a conversational transcript (passage) and 5 questions for CEFR level {req.level.upper()}. JSON format: {{ 'passage': '...', 'questions': [{{ 'question': '...', 'options': ['...', '...'], 'correctAnswer': '...' }}] }}",
        "writing": f"Generate a writing prompt for CEFR level {req.level.upper()}. JSON format: {{ 'title': '...', 'passage': '...' }}",
        "speaking": f"Generate 1 clear English sentence for pronunciation practice at {req.level.upper()} level. JSON format: {{ 'targetSentence': '...', 'prompt': 'Pronounce the following sentence.' }}",
        "grammar": f"""
            Generate 5 professional multiple-choice grammar questions strictly for CEFR level {req.level.upper()}.
            Target grammar points specific to {req.level.upper()} level. 
            Use '___' (three underscores) for the blank space.
            Return ONLY JSON: {{ 'questions': [{{ 'question': '...', 'options': ['...', '...', '...', '...'], 'correctAnswer': '...' }}] }}
        """
    }
    
    instruction = prompt_templates.get(req.type, f"Generate 5 {req.level} English questions in JSON format.")
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional CEFR language examiner. Return ONLY valid JSON. Ensure the content matches the requested difficulty level exactly."},
                {"role": "user", "content": instruction}
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ Error generando preguntas: {e}")
        raise HTTPException(status_code=500, detail="Error generando el examen")

@app.post("/api/v1/chatbot")
async def chatbot_helper(data: ChatMessage):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres el asistente de Certifica_AI. Responde usando Markdown de forma concisa."},
                {"role": "user", "content": data.message}
            ],
            max_tokens=250
        )
        return {"reply": response.choices[0].message.content}
    except Exception:
        return {"reply": "**Error de conexión** con la IA."}

@app.post("/api/v1/generate-report")
async def generate_report(req: ReportRequest):
    try:
        prompt = f"""
        Analyze these English proficiency scores for level {req.level}:
        - Reading: {req.reading}%
        - Listening: {req.listening}%
        - Writing: {req.writing}%
        - Speaking: {req.speaking}%
        
        Provide professional, motivating advice (max 30 words) and 3 specific, short action steps for improvement.
        Return ONLY JSON: {{ "ai_advice": "...", "steps": ["...", "...", "..."] }}
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional CEFR academic advisor. Return ONLY valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={ "type": "json_object" }
        )
        
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ Error en Reporte: {e}")
        raise HTTPException(status_code=500, detail="Error generando el análisis de IA")

# --- INICIO ---
if __name__ == "__main__":
    import uvicorn
    # Ejecución en el puerto 8000 para conectar con el frontend
    uvicorn.run(app, host="0.0.0.0", port=8000)