"""
main.py
Servidor FastAPI del contenedor detector.

Endpoints:
    GET  /stream      → MJPEG stream de la cámara con bounding boxes
    GET  /detections  → JSON con logos detectados actualmente
    GET  /health      → estado del modelo y la cámara
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse, JSONResponse


# ── Instancia global del detector ──────────────────────────────────────────────
# Se importa aquí para que FastAPI lo arranque junto con el servidor.

from detector import LogoDetector

detector = LogoDetector()


# ── Ciclo de vida de la aplicación ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Arranca el detector al iniciar el servidor
    y lo detiene limpiamente al apagar.
    """
    detector.start()
    yield
    detector.stop()


# ── Aplicación ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "DevOps Logo Detector",
    description = "Detección en tiempo real de logos DevOps con YOLOv8",
    version     = "1.0.0",
    lifespan    = lifespan,
)


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/stream",
    summary     = "Stream de video en vivo",
    description = "MJPEG stream de la cámara con bounding boxes dibujados. "
                  "El browser lo consume directamente con <img src='/stream'>.",
)
def stream():
    return StreamingResponse(
        detector.frames(),
        media_type = "multipart/x-mixed-replace; boundary=frame",
    )


@app.get(
    "/detections",
    summary     = "Logos detectados actualmente",
    description = "El chatbot llama a este endpoint para saber qué logos "
                  "están en pantalla antes de responder al usuario.",
    response_description = "Lista de logos activos con metadatos",
)
def detections():
    """
    Ejemplo de respuesta:
    ```json
    {
        "logos": ["docker", "kubernetes"],
        "count": 2,
        "model_ready": true,
        "timestamp": 1718000000.0
    }
    ```
    """
    return JSONResponse(content=detector.get_detections())


@app.get(
    "/health",
    summary     = "Estado del servicio",
    description = "Verifica que el modelo esté cargado y la cámara activa.",
)
def health():
    """
    Ejemplo de respuesta cuando todo está bien:
    ```json
    {
        "status": "ok",
        "model_ready": true,
        "model_path": "models/best.pt",
        "source": "0",
        "max_fps": 15
    }
    ```
    """
    return JSONResponse(content=detector.health())
