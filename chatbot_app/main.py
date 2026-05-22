"""
main.py
Servidor FastAPI del contenedor chatbot.

Endpoints:
    GET  /        → Web UI completa (video + detecciones + chat)
    POST /chat    → recibe mensaje, devuelve respuesta de Claude
    POST /clear   → limpia el historial de conversación
    GET  /health  → estado del servicio
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
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
