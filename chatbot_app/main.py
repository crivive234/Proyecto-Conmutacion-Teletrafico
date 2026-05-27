"""
main.py
Servidor FastAPI del contenedor chatbot.

Endpoints:
    GET  /            → Web UI completa (video + detecciones + chat)
    POST /chat        → recibe mensaje, devuelve respuesta de Claude
    POST /clear       → limpia el historial de conversación
    POST /transcribe  → transcribe audio con Groq Whisper (voz → texto)
    POST /speak       → convierte texto a voz con gTTS (texto → MP3)
    GET  /health      → estado del servicio
"""

import io
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from groq import Groq
from gtts import gTTS
from pydantic import BaseModel

from chatbot import ask_claude, clear_history, get_history, get_audit_context

# ── Configuración ──────────────────────────────────────────────────────────────

DETECTOR_URL = os.getenv("DETECTOR_URL", "http://detector:8000")

# Cliente Groq — toma GROQ_API_KEY del entorno automáticamente
_groq_client = Groq()

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
    version     = "1.0.0",
    lifespan    = lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# MODELOS DE DATOS
# ─────────────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str

    model_config = {
        "json_schema_extra": {
            "example": {"message": "¿Qué es Docker y para qué sirve?"}
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/",
    response_class = HTMLResponse,
    summary        = "Interfaz web principal",
    description    = "Sirve la Web UI con video en vivo, panel de detecciones y chat.",
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
    description = "Recibe el mensaje del usuario, consulta los logos detectados "
                  "actualmente y devuelve la respuesta de Claude con ese contexto.",
)
async def chat(body: ChatRequest):
    """
    Ejemplo de request:
    ```json
    { "message": "¿Qué diferencia hay entre Docker y Podman?" }
    ```

    Ejemplo de response:
    ```json
    {
        "response": "Docker y Podman son ambos motores de contenedores...",
        "context_logos": ["docker", "podman"],
        "error": null
    }
    ```
    """
    if not body.message.strip():
        return JSONResponse(
            status_code = 400,
            content     = {"error": "El mensaje no puede estar vacío."},
        )

    result = await ask_claude(body.message.strip())
    return JSONResponse(content=result)


@app.post(
    "/clear",
    summary     = "Limpiar historial",
    description = "Reinicia la conversación desde cero.",
)
async def clear():
    clear_history()
    return JSONResponse(content={"status": "ok", "message": "Historial limpiado."})


@app.get(
    "/audit-context",
    summary     = "Contexto de auditoría Parrot OS",
    description = "Devuelve el resumen del último reporte nmap generado por Parrot OS.",
)
async def audit_context():
    summary = get_audit_context()
    return JSONResponse(content={
        "available": bool(summary),
        "summary":   summary or "Sin reportes de auditoría disponibles.",
    })


@app.get(
    "/health",
    summary     = "Estado del servicio",
    description = "Verifica que el chatbot esté activo.",
)
async def health():
    return JSONResponse(content={
        "status":       "ok",
        "detector_url": DETECTOR_URL,
        "history_len":  len(get_history()),
    })


@app.post(
    "/transcribe",
    summary     = "Transcribir audio con Groq Whisper",
    description = "Recibe un archivo de audio grabado por el navegador (webm/ogg/mp4) "
                  "y devuelve el texto transcrito usando whisper-large-v3-turbo de Groq.",
)
async def transcribe(audio: UploadFile = File(...)):
    """
    Ejemplo de response:
    ```json
    { "transcript": "¿Qué diferencia hay entre Docker y Podman?" }
    ```
    """
    # Validar tipo MIME — MediaRecorder puede enviar "audio/webm;codecs=opus",
    # "audio/ogg;codecs=opus", etc. Se compara solo el tipo base (antes del ";").
    ALLOWED   = {"audio/webm", "audio/ogg", "audio/mp4", "audio/wav", "audio/mpeg"}
    base_type = (audio.content_type or "").split(";")[0].strip().lower()
    if base_type not in ALLOWED:
        raise HTTPException(
            status_code = 415,
            detail      = f"Tipo de audio no soportado: {audio.content_type}. "
                          f"Permitidos: {', '.join(ALLOWED)}",
        )

    audio_bytes = await audio.read()

    # Grabación demasiado corta → el usuario no habló
    if len(audio_bytes) < 1_000:
        raise HTTPException(
            status_code = 400,
            detail      = "Audio demasiado corto o vacío. Intenta hablar más cerca del micrófono.",
        )

    try:
        # Groq espera un file-like con nombre que incluya la extensión correcta
        ext        = (audio.filename or "recording.webm").rsplit(".", 1)[-1]
        audio_file = (f"recording.{ext}", io.BytesIO(audio_bytes), audio.content_type)

        transcription = _groq_client.audio.transcriptions.create(
            file            = audio_file,
            model           = "whisper-large-v3-turbo",
            language        = "es",
            response_format = "text",
        )
        return JSONResponse(content={"transcript": transcription.strip()})

    except Exception as exc:
        raise HTTPException(
            status_code = 500,
            detail      = f"Error al transcribir con Groq Whisper: {exc}",
        )


class SpeakRequest(BaseModel):
    text: str

    model_config = {
        "json_schema_extra": {
            "example": {"text": "Docker es una plataforma de contenedores."}
        }
    }


@app.post(
    "/speak",
    summary     = "Texto a voz con gTTS",
    description = "Recibe un texto y devuelve un stream MP3 listo para reproducir "
                  "en el navegador usando Google Text-to-Speech en español.",
)
async def speak(body: SpeakRequest):
    """
    Ejemplo de request:
    ```json
    { "text": "Docker es una plataforma de contenedores." }
    ```
    Response: stream de audio MP3 (`audio/mpeg`).
    """
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="El texto no puede estar vacío.")

    # Limitar longitud para no generar audios interminables
    if len(text) > 1_000:
        text = text[:1_000] + "..."

    try:
        tts    = gTTS(text=text, lang="es", slow=False)
        buffer = io.BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type = "audio/mpeg",
            headers    = {"Cache-Control": "no-store"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code = 500,
            detail      = f"Error al generar audio con gTTS: {exc}",
        )


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
