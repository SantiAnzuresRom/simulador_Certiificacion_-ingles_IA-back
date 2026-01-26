from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from app.core.firebase_config import db # Nuestra conexión a Firestore

# 1. DEFINIR EL ROUTER (Esto es lo que te daba el error)
router = APIRouter()

# 2. DEFINIR EL MODELO DE DATOS (Para que FastAPI sepa qué recibir)
class ExamSubmission(BaseModel):
    user_id: str
    module: str
    content: dict  # O list, dependiendo de cómo envíes las respuestas

# 3. FUNCIÓN MOCK DE ANÁLISIS (Sustitúyela luego por tu lógica de GPT)
def analyze_exam(module: str, content: dict):
    # Aquí irá tu lógica con OpenAI o el análisis de resultados
    return {
        "score": 85,
        "feedback": f"Buen trabajo en el módulo {module}. Revisa las preguntas de teoría.",
        "passed": True
    }

# 4. LA RUTA POST
@router.post("/submit")
async def submit_exam(data: ExamSubmission):
    try:
        # 1. Obtenemos el análisis
        analysis = analyze_exam(data.module, data.content)
        
        # 2. Guardamos en Firebase Firestore
        doc_ref = db.collection("exam_results").document()
        exam_data = {
            "user_id": data.user_id,
            "module": data.module,
            "content": data.content,
            "analysis": analysis,
            "timestamp": datetime.now()
        }
        doc_ref.set(exam_data)
        
        return {
            "status": "success", 
            "firebase_id": doc_ref.id, 
            "results": analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))