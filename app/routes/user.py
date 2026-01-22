from pydantic import BaseModel
from datetime import datetime

class UserCreate(BaseModel):
    uid: str
    full_name: str
    email: str
    phone: str
    birth_date: str 