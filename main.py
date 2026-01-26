from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.core.firebase_config import db 
from datetime import datetime
app = FastAPI()

# Permite que el frontend (localhost:3000) hable con el backend (localhost:8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserRegister(BaseModel):
    uid: str
    full_name: str
    email: str
    phone: Optional[str] = ""
    birth_date: Optional[str] = ""

@app.post("/api/v1/users/register")
async def register_user(user: UserRegister):
    try:
        # Guardar en Firestore
        db.collection("users").document(user.uid).set({
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "birth_date": user.birth_date,
            "created_at": datetime.now()
        })
        return {"status": "success", "message": "Perfil guardado"}
    except Exception as e:
        print(f"Error Firestore: {e}")
        raise HTTPException(status_code=500, detail=str(e))