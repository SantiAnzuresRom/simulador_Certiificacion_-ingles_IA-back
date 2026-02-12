import os
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
from datetime import datetime
from app.core.firebase_config import db 

# Cargar variables de entorno (.env)
load_dotenv()

app = FastAPI(title="Certifica AI - Backend")

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

# --- MODELOS DE DATOS (PYDANTIC) ---

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

# FIX: Campos opcionales para evitar error 422 si falta un módulo
class FinalResults(BaseModel):
    reading: Optional[float] = 0.0
    writing: Optional[float] = 0.0
    listening: Optional[float] = 0.0
    speaking: Optional[float] = 0.0
    level: str

# --- ENDPOINTS ---

# 1. REGISTRO EN FIREBASE
@app.post("/api/v1/users/register")
async def register_user(user: UserRegister):
    try:
        db.collection("users").document(user.uid).set({
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "birth_date": user.birth_date,
            "created_at": datetime.now()
        })
        return {"status": "success", "message": "Perfil guardado en Firebase"}
    except Exception as e:
        print(f"Error Firestore: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# 2. GENERADOR DE EXÁMENES (IA)
@app.post("/api/v1/generate-questions")
async def generate_questions(req: ModuleRequest):
    prompt_templates = {
        "reading": "Generate a title, a 3-paragraph passage, and 5 multiple choice questions. JSON format: { 'title': '...', 'passage': '...', 'questions': [{ 'question': '...', 'options': ['...', '...'], 'correctAnswer': '...' }] }",
        "listening": "Generate a conversational transcript (passage) and 5 questions. JSON format: { 'passage': '...', 'questions': [{ 'question': '...', 'options': ['...', '...'], 'correctAnswer': '...' }] }",
        "writing": "Generate a writing prompt. JSON format: { 'title': '...', 'passage': '...' }",
        # FIX: Ajuste de estructura para Speaking
        "speaking": "Generate 1 clear English sentence for pronunciation practice. JSON format: { 'targetSentence': '...', 'prompt': 'Pronounce the following sentence clearly.' }"
    }

    instruction = prompt_templates.get(req.type, "General English task.")
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional CEFR language examiner. Return ONLY valid JSON."},
                {"role": "user", "content": f"Level: {req.level}. Task: {instruction}"}
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error OpenAI: {e}")
        raise HTTPException(status_code=500, detail="Error con el motor de IA")

# 3. EVALUADOR DE WRITING
@app.post("/api/v1/grade-writing")
async def grade_writing(req: GradeWritingRequest):
    try:
        prompt_grade = f"""
        Actúa como un examinador oficial de nivel {req.level}.
        Consigna: {req.prompt}
        Texto del alumno: {req.content}
        
        Evalúa gramática, vocabulario y coherencia. 
        Devuelve ÚNICAMENTE un JSON con:
        1. "score": Un número entero del 0 al 100.
        2. "feedback": Un párrafo breve (máximo 3 líneas) en español con consejos específicos.
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
        print(f"Error Grading: {e}")
        return {"score": 0, "feedback": "No se pudo procesar la evaluación técnica."}

# 4. REPORTE FINAL INTELIGENTE (Integración de Scores)
@app.post("/api/v1/generate-report")
async def generate_final_report(data: FinalResults):
    # Consolidamos los resultados para el prompt
    prompt_report = f"""
    Actúa como un coach experto en idiomas. Nivel: {data.level}.
    Scores actuales: 
    - Reading: {data.reading}%
    - Writing: {data.writing}%
    - Listening: {data.listening}%
    - Speaking: {data.speaking}%
    
    Analiza las debilidades y fortalezas basándote en estos números. 
    Genera feedback en español motivador.
    Devuelve JSON:
    1. "ai_advice": Párrafo de análisis profundo.
    2. "steps": Lista de 3 acciones concretas para subir de nivel.
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
            "scores": data.model_dump(), # model_dump() es el nuevo dict() en Pydantic V2
            "ai_advice": report_content.get("ai_advice"),
            "steps": report_content.get("steps")
        }
    except Exception as e:
        print(f"Error Reporte: {e}")
        return {
            "scores": data.model_dump(),
            "ai_advice": "¡Buen trabajo en tus módulos! Sigue practicando de manera constante.",
            "steps": ["Practica 15 min diarios", "Escucha podcasts en inglés", "Escribe un diario corto"]
        }

# 5. CHATBOT ASISTENTE
@app.post("/api/v1/chatbot")
async def chatbot_helper(data: ChatMessage):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres el asistente de Certifica_AI. Responde de forma amable, breve y técnica si es necesario."},
                {"role": "user", "content": data.message}
            ],
            max_tokens=150
        )
        return {"reply": response.choices[0].message.content}
    except Exception as e:
        return {"reply": "Lo siento, tengo un problema de conexión temporal con mi cerebro de IA."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)