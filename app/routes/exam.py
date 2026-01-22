from app.core.firebase_config import db # Nuestra conexión a Firestore
from datetime import datetime

@router.post("/submit")
async def submit_exam(data: ExamSubmission):
    # 1. Obtenemos el análisis de GPT
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