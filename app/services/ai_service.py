from openai import OpenAI
import os
from dotenv import load_dotenv
import json
from app.core.config import MODULES_CONFIG # Importamos la config

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_exam(module_id: str, content: str):
    # Buscamos la configuración del módulo (o usamos una por defecto)
    module_info = MODULES_CONFIG.get(module_id.lower(), {
        "system_prompt": "Eres un examinador de inglés general."
    })

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": module_info["system_prompt"]},
                {"role": "user", "content": f"Contenido a evaluar: {content}. Responde en JSON con score, feedback, corrections y suggestions."}
            ],
            response_format={ "type": "json_object" }
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        return {"error": str(e)}