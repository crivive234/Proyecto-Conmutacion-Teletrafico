"""
main.py
Servidor FastAPI del contenedor chatbot.

Endpoints:
    GET  /              → Web UI completa (video + detecciones + chat)
    POST /chat          → recibe mensaje, devuelve respuesta de Groq
    POST /clear         → limpia el historial de conversación
    GET  /health        → estado del servicio
    GET  /detections-proxy → proxy para evitar CORS con el detector
    POST /speak         → convierte texto a audio MP3 (gTTS) para reproducir en el navegador
"""

import os
from contextlib import asynccontextmanager
from io import BytesIO

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from gtts import gTTS
from pydantic import BaseModel

from chatbot import ask_claude, clear_history, get_history

# ── Configuración ──────────────────────────────────────────────────────────────

DETECTOR_URL = os.getenv("DETECTOR_URL", "http://detector:8000")

templates = Jinja2Templates(directory="templates")


# ── Ciclo de vida ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"Chatbot iniciado. Detector en: {DETECTOR_URL}")
    yield
    print("Chatbot detenido.")


# ── Aplicación ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "DevOps Chatbot",
    description = "Chatbot contextual para el visualizador de logos DevOps",
    version     = "1.1.0",
    lifespan    = lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str

    model_config = {
        "json_schema_extra": {
            "example": {"message": "¿Qué es Docker y para qué sirve en el proyecto?"}
        }
    }


class SpeakRequest(BaseModel):
    text: str

    model_config = {
        "json_schema_extra": {
            "example": {"text": "Docker conteneriza los servicios principales del proyecto."}
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/",
    response_class = HTMLResponse,
    summary        = "Interfaz web principal",
)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request":      request,
            "detector_url": DETECTOR_URL,
        },
    )


@app.post(
    "/chat",
    summary     = "Enviar mensaje al chatbot",
    description = "Recibe el mensaje del usuario y devuelve la respuesta con contexto del proyecto.",
)
async def chat(body: ChatRequest):
    if not body.message.strip():
        return JSONResponse(
            status_code = 400,
            content     = {"error": "El mensaje no puede estar vacío."},
        )

    result = await ask_claude(body.message.strip())
    return JSONResponse(content=result)


@app.post(
    "/speak",
    summary     = "Texto a voz",
    description = "Convierte el texto en audio MP3 usando gTTS. "
                  "El frontend lo recibe y lo reproduce directamente en el navegador, "
                  "sin necesidad de acceso a dispositivos de audio en el contenedor.",
)
async def speak(body: SpeakRequest):
    """
    Ejemplo de uso desde el frontend:
    ```js
    const res = await fetch('/speak', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ text: responseText })
    });
    const blob = await res.blob();
    new Audio(URL.createObjectURL(blob)).play();
    ```
    """
    if not body.text.strip():
        return JSONResponse(
            status_code = 400,
            content     = {"error": "El texto no puede estar vacío."},
        )

    try:
        tts = gTTS(text=body.text.strip(), lang="es", slow=False)
        buf = BytesIO()
        tts.write_to_fp(buf)
        buf.seek(0)
        return StreamingResponse(buf, media_type="audio/mpeg")
    except Exception as e:
        return JSONResponse(
            status_code = 500,
            content     = {"error": f"Error al generar audio: {str(e)}"},
        )


@app.post(
    "/clear",
    summary     = "Limpiar historial",
    description = "Reinicia la conversación desde cero.",
)
async def clear():
    clear_history()
    return JSONResponse(content={"status": "ok", "message": "Historial limpiado."})


@app.get(
    "/health",
    summary     = "Estado del servicio",
)
async def health():
    return JSONResponse(content={
        "status":       "ok",
        "detector_url": DETECTOR_URL,
        "history_len":  len(get_history()),
    })


@app.get(
    "/detections-proxy",
    summary     = "Proxy de detecciones",
    description = "Evita CORS: el browser consulta esto en vez de detector:8000 directamente.",
)
async def detections_proxy():
    import httpx
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            res = await client.get(f"{DETECTOR_URL}/detections")
            return JSONResponse(content=res.json())
    except Exception:
        return JSONResponse(content={"logos": [], "count": 0, "model_ready": False, "timestamp": 0})
