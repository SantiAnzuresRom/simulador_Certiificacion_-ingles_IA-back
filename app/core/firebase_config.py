import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JSON_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")

def initialize_firebase():
    try:
        if not firebase_admin._apps:
            if not os.path.exists(JSON_PATH):
                print(f"❌ Error: No se encontró el JSON en {JSON_PATH}")
                return None
            
            cred = credentials.Certificate(JSON_PATH)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase conectado con éxito desde core.")
        
        return firestore.client()
    except Exception as e:
        print(f"❌ Error al inicializar Firebase: {e}")
        return None

db = initialize_firebase()