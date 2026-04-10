import os

import json
import smtplib
import io
import firebase_admin
# -----------------------------------------------------------
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# -----------------------------------------------------------
from firebase_admin import auth as admin_auth, credentials
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from firebase_admin import auth as admin_auth, credentials, firestore
load_dotenv()

# Inicialización de OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(title="CertificaAI Engine - Full Stack Pro")

# Configuración de CORS - Blindado
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
# Función para enviar credenciales por correo
def send_credentials_email(user_email, password, name):
    try:
        # Configuración desde variables de entorno (.env)
        smtp_user = os.getenv("SMTP_USER")
        smtp_pass = os.getenv("SMTP_PASS")
        
        msg = MIMEMultipart()
        msg['From'] = f"CertificaAI Support <{smtp_user}>"
        msg['To'] = user_email
        msg['Subject'] = "🚀 Tus credenciales de acceso - CertificaAI"

        html = f"""
        <div style="font-family: sans-serif; background-color: #020617; color: #ffffff; padding: 40px; border-radius: 20px;">
            <h2 style="color: #06b6d4;">¡Bienvenido, {name}!</h2>
            <p style="color: #94a3b8;">Tu cuenta para el simulador Certifica AI ha sido creada por el administrador, Se recomienda cambiar la contraseña.</p>
            <div style="background-color: #0f172a; padding: 20px; border-radius: 15px; border: 1px solid #1e293b; margin: 20px 0;">
                <p style="margin: 5px 0;"><strong>Usuario:</strong> {user_email}</p>
                <p style="margin: 5px 0;"><strong>Contraseña Temporal:</strong> <span style="color: #06b6d4;">{password}</span></p>
            </div>
            <p style="font-size: 11px; color: #64748b;">* Por seguridad, se te pedirá cambiar tu contraseña al ingresar.</p>
        </div>
        """
        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as e:
        print(f"Error enviando correo: {e}")
# ----------------------------------------------------
# 1. MODELOS DE DATOS (ESTRUCTURA COMPLETA)
# ----------------------------------------------------

class ModuleRequest(BaseModel):
    type: str
    level: str

class WritingRequest(BaseModel):
    content: str
    level: str
    prompt: str

class SkillEvaluationRequest(BaseModel):
    level: str
    answers: list
    questions: list
    type: str

class SpeakingAttempt(BaseModel):
    target: str
    transcript: str

class BatchSpeakingEvaluation(BaseModel):
    attempts: list[SpeakingAttempt]

class FinalReportRequest(BaseModel):
    reading: int = 0
    writing: int = 0
    listening: int = 0
    speaking: int = 0
    level: str

class UserCreateRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: str


# ----------------------------------------------------
# 2. GENERACIÓN DE CONTENIDO (MÓDULOS)
# ----------------------------------------------------

@app.post("/api/v1/generate-questions")
async def generate_questions(req: ModuleRequest):
    grammar_prompt = (
        f"Act as a senior IELTS Examiner. Generate 5 grammar MCQs for level {req.level}. "
        "Each question MUST include a '___' (three underscores) where the answer goes. "
        "Return EXACT JSON: {'questions': [{'question': '...', 'options': ['A', 'B', 'C', 'D'], 'correctAnswer': '...'}]}"
    )

    prompts = {
        "reading": f"Act as an IELTS Examiner. Generate an IELTS academic reading passage and 5 questions for level {req.level}. JSON: {{'title': '...', 'passage': '...', 'questions': [{{'question': '...', 'options': [], 'correctAnswer': '...'}}]}}",
        "listening": f"Act as an IELTS Examiner. Generate a transcript of an IELTS listening section and 5 questions for level {req.level}. JSON: {{'passage': '...', 'questions': [{{'question': '...', 'options': [], 'correctAnswer': '...'}}]}}",
        "writing": f"Act as an IELTS Examiner. Generate an IELTS Task 2 prompt for level {req.level}. JSON: {{'title': 'Writing Task 2', 'prompt': '...'}}",
        "speaking": f"Act as an IELTS Examiner. Generate 5 short pronunciation sentences for level {req.level}. JSON: {{'prompts': ['...', '...', '...', '...', '...']}}",
        "grammar": grammar_prompt
    }

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a senior IELTS Certified Examiner. You only output valid JSON."},
                {"role": "user", "content": prompts.get(req.type, "Generate general English exercises.")}
            ]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------
# 3. CALIFICACIÓN (WRITING, READING, LISTENING)
# ----------------------------------------------------

@app.post("/api/v1/grade-writing")
async def grade_writing(req: WritingRequest):
    prompt_eval = f"""
    Act as an IELTS Writing Examiner. Grade this response for level {req.level}.
    Task Prompt: {req.prompt}
    Student Content: {req.content}
    Return ONLY JSON:
    {{
        "score": int,
        "feedback": "Professional feedback including band score and tips"
    }}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a professional IELTS Writing Examiner."},
                {"role": "user", "content": prompt_eval}
            ]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/grade-skill")
async def grade_skill(req: SkillEvaluationRequest):
    prompt_eval = f"""
    Act as an IELTS Examiner. Grade this {req.type} test for level {req.level}.
    Questions and Correct Answers: {req.questions}
    User Answers: {req.answers}
    Compare them and calculate a score from 0 to 100.
    Return JSON: {{"score": int, "feedback": "Detailed feedback"}}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": "IELTS Examiner."}, {"role": "user", "content": prompt_eval}]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------
# 4. REPORTE FINAL (ESTRATEGIA IA)
# ----------------------------------------------------

@app.post("/api/v1/generate-report")
async def generate_report(req: FinalReportRequest):
    # Lógica mejorada: Identificamos la debilidad principal para guiar a la IA
    scores = {"Reading": req.reading, "Writing": req.writing, "Listening": req.listening, "Speaking": req.speaking}
    weakest_skill = min(scores, key=scores.get)

    prompt = f"""
    Act as a senior IELTS Career Coach. Analyze these scores for a student at {req.level} level:
    Scores: {scores}
    The weakest area is {weakest_skill}.

    Return EXACTLY this JSON:
    {{
        "ai_advice": "A powerful, personalized one-sentence strategic advice focusing on their profile.",
        "steps": [
            "Actionable step to improve {weakest_skill} specifically",
            "A habit-based step to maintain their strongest skills",
            "A technical tip for the {req.level} exam"
        ]
    }}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "You are a professional IELTS Career Coach and Psychometrician."},
                {"role": "user", "content": prompt}
            ]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------
# 5. MULTIMEDIA (WHISPER & TTS)
# ----------------------------------------------------

@app.post("/api/v1/voice/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    try:
        audio_bytes = await audio.read()
        buffer = io.BytesIO(audio_bytes)
        buffer.name = "audio.webm"
        transcript = client.audio.transcriptions.create(model="whisper-1", file=buffer, language="en")
        return {"text": transcript.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Transcription error")

@app.post("/api/v1/voice/speak")
async def speak(text: str = Query(...)):
    try:
        response = client.audio.speech.create(model="tts-1-hd", voice="nova", input=text, speed=1.02)
        return StreamingResponse(io.BytesIO(response.content), media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------------------------------------------
# 6. SPEAKING EVALUATION (BATCH ANALYSIS)
# ----------------------------------------------------

@app.post("/api/v1/evaluate-speaking")
async def evaluate_batch(data: BatchSpeakingEvaluation):
    attempts_summary = "\n".join([f"Target: {a.target} | Student: {a.transcript}" for a in data.attempts])
    prompt = f"""
    Act as an IELTS Speaking Examiner. Evaluate:
    {attempts_summary}
    Return JSON: {{'overall_score': int, 'general_feedback': '...', 'estimated_band': '...', 'pronunciation_tips': '...'}}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": "Expert IELTS Speaking Examiner."}, {"role": "user", "content": prompt}]
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

# ----------------------------------------------------
# 7. ADMIN OPS (FIREBASE SDK) - ACTUALIZADO PARA USER_PROGRESS
# ----------------------------------------------------

# Inicializar Firebase Admin (Solo si no está inicializado)
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

@app.post("/api/v1/admin/create-user")
async def create_user_as_admin(req: UserCreateRequest):
    try:
        # 1. Crea el usuario en Firebase Auth
        user = admin_auth.create_user(
            email=req.email,
            password=req.password,
            display_name=req.full_name
        )

        # 2. ESTRUCTURA UNIFICADA EN USER_PROGRESS
        # Inicializamos los módulos en 0 para que el Dashboard del alumno no de error
        user_progress_data = {
            "fullName": req.full_name,
            "email": req.email,
            "role": req.role,
            "currentLevel": "A1",
            "access_blocked": False,
            "needs_password_change": True,
            "created_at": firestore.SERVER_TIMESTAMP,
            # Estructura de módulos para que el front tenga qué leer desde el día 1
            "modules_A1": {"reading": 0, "listening": 0, "writing": 0, "speaking": 0},
            "modules_A2": {"reading": 0, "listening": 0, "writing": 0, "speaking": 0},
            "modules_B1": {"reading": 0, "listening": 0, "writing": 0, "speaking": 0},
            "modules_B2": {"reading": 0, "listening": 0, "writing": 0, "speaking": 0},
            "modules_C1": {"reading": 0, "listening": 0, "writing": 0, "speaking": 0},
            "modules_C2": {"reading": 0, "listening": 0, "writing": 0, "speaking": 0}
        }
        
        # Guardamos en la colección user_progress
        db.collection("user_progress").document(user.uid).set(user_progress_data)

        # 3. Envía el correo con las credenciales
        send_credentials_email(req.email, req.password, req.full_name)
        
        return {"uid": user.uid, "status": "success"}

    except Exception as e:
        print(f"Error en creación: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    # Detecta el puerto dinámico de Render o usa el 8000 en local
    port = int(os.environ.get("PORT", 8000))
    # Arranca el servidor con el puerto correcto
    uvicorn.run(app, host="0.0.0.0", port=port)