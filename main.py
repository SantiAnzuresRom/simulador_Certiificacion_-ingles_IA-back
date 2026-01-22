from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# Importación directa del archivo exam.py
from app.routes.exam import router as exam_router 
from app.routes import exam, user
app = FastAPI(title="AI Certification Simulator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conectamos el router
app.include_router(exam_router, prefix="/api/v1/exams", tags=["Exams"])
app.include_router(user.router, prefix="/api/v1/users", tags=["Users"])

@app.get("/")
async def root():
    return {"message": "API is online", "docs": "/docs"}