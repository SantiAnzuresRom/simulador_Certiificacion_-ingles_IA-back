import random
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Base de datos temporal en memoria (en producción usarías Redis)
otp_storage = {}

@router.post("/send-otp")
async def send_otp(request: OTPRequest):

    code = str(random.randint(10000000, 99999999))
    
    
    otp_storage[request.email] = code
    
    
    print(f"DEBUG: Enviando código {code} al correo {request.email}")
    
    return {"message": "Código enviado con éxito"}

@router.post("/verify-otp")
async def verify_otp(request: OTPVerify):
    saved_code = otp_storage.get(request.email)
    
    if saved_code and saved_code == request.code:
        # Borramos el código para que no se use dos veces
        del otp_storage[request.email]
        return {"message": "Verificación exitosa"}
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Código incorrecto o expirado, bro"
    )