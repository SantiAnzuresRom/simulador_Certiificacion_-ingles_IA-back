from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.firebase_config import db

# ESTO ES LO QUE FALTA
router = APIRouter()

# Modelo para recibir los datos del registro
class UserRegister(BaseModel):
    uid: str
    full_name: str
    email: str
    phone: str = None
    birth_date: str = None

@router.post("/register")
async def register_user(user: UserRegister):
    try:
        # Aquí puedes guardar el perfil extendido en Firestore si quieres
        doc_ref = db.collection("users").document(user.uid)
        doc_ref.set({
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
            "birth_date": user.birth_date,
            "created_at": datetime.now()
        })
        return {"status": "success", "message": "Usuario registrado en backend"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))