"""
chatbot.py
Lógica del chatbot: consulta /detections al detector
y genera respuestas contextuales usando la API de Groq (gratis).
"""

import os
import httpx
from groq import Groq

# ── Configuración ──────────────────────────────────────────────────────────────

DETECTOR_URL = os.getenv("DETECTOR_URL", "http://detector:8000")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MAX_TOKENS   = 512
MODEL        = "llama-3.3-70b-versatile"   # gratis en Groq, muy capaz

# Historial de conversación por sesión (en memoria)
_history: list[dict] = []
MAX_HISTORY = 10


# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres el asistente del proyecto 'Visualizador Computacional DevOps'.
Tu función es explicar herramientas DevOps de forma clara y concisa.

Contexto del proyecto:
- Una cámara detecta logos de herramientas DevOps en tiempo real usando YOLOv8.
- Los logos que puede detectar son: Docker, Podman, Terraform, QEMU, Ansible, RabbitMQ y Kubernetes.
- Cuando el usuario pregunta algo, sabes exactamente qué logos hay en pantalla en ese momento.

Reglas de comportamiento:
- Si hay logos detectados en pantalla, úsalos como contexto principal de tu respuesta.
- Si el usuario pregunta por un logo específico que NO está en pantalla, respóndele igual.
- Responde siempre en español.
- Sé directo: máximo 3 párrafos por respuesta.
- Puedes usar ejemplos de comandos cuando sea útil.
- No inventes logos ni herramientas que no existan."""


# ─────────────────────────────────────────────────────────────────────────────
# OBTENER DETECCIONES ACTUALES
# ─────────────────────────────────────────────────────────────────────────────

async def get_current_logos() -> list[str]:
    """
    Llama al endpoint /detections del contenedor detector.
    Devuelve la lista de logos actualmente en pantalla.
    Si el detector no responde, devuelve lista vacía sin crashear.
    """
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{DETECTOR_URL}/detections")
            data = response.json()
            return data.get("logos", [])
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUIR MENSAJE CON CONTEXTO
# ─────────────────────────────────────────────────────────────────────────────

def build_user_message(user_text: str, logos: list[str]) -> str:
    """
    Añade el contexto de logos detectados al mensaje del usuario.

    Ejemplo de salida:
        [Logos en pantalla ahora: docker, kubernetes]
        ¿Qué diferencia hay entre estos dos?
    """
    if logos:
        context = f"[Logos en pantalla ahora: {', '.join(logos)}]\n"
    else:
        context = "[Sin logos detectados en pantalla ahora mismo]\n"

    return context + user_text


# ─────────────────────────────────────────────────────────────────────────────
# LLAMADA A GROQ
# ─────────────────────────────────────────────────────────────────────────────

async def ask_claude(user_text: str) -> dict:
    """
    Flujo completo:
    1. Obtiene logos detectados actualmente.
    2. Construye el mensaje con contexto.
    3. Llama a Groq API manteniendo el historial.
    4. Devuelve respuesta + logos usados como contexto.

    Nota: la función se llama ask_claude para no cambiar
    el contrato con main.py — internamente usa Groq.
    """
    global _history

    # Paso 1 — logos actuales
    logos = await get_current_logos()

    # Paso 2 — mensaje enriquecido
    enriched_message = build_user_message(user_text, logos)

    # Paso 3 — agregar al historial
    _history.append({"role": "user", "content": enriched_message})

    # Mantener historial acotado
    if len(_history) > MAX_HISTORY * 2:
        _history = _history[-(MAX_HISTORY * 2):]

    # Paso 4 — verificar API key
    if not GROQ_API_KEY:
        _history.append({
            "role": "assistant",
            "content": "Error: GROQ_API_KEY no configurada."
        })
        return {
            "response":      "Error: falta configurar GROQ_API_KEY en el .env",
            "context_logos": logos,
            "error":         "missing_api_key",
        }

    # Paso 5 — llamar a Groq
    try:
        client = Groq(api_key=GROQ_API_KEY)

        # Groq sigue el formato OpenAI: system va como primer mensaje
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _history

        completion = client.chat.completions.create(
            model      = MODEL,
            messages   = messages,
            max_tokens = MAX_TOKENS,
        )

        reply = completion.choices[0].message.content

        # Guardar respuesta en el historial
        _history.append({"role": "assistant", "content": reply})

        return {
            "response":      reply,
            "context_logos": logos,
            "error":         None,
        }

    except Exception as e:
        error_msg = str(e)

        # Mensaje amigable para errores comunes
        if "401" in error_msg or "invalid_api_key" in error_msg:
            msg = "Error de autenticación con Groq. Verifica tu GROQ_API_KEY."
            err = "auth_error"
        elif "429" in error_msg:
            msg = "Límite de requests alcanzado. Espera un momento e intenta de nuevo."
            err = "rate_limit"
        else:
            msg = f"Error inesperado: {error_msg}"
            err = "unexpected"

        return {
            "response":      msg,
            "context_logos": logos,
            "error":         err,
        }


# ─────────────────────────────────────────────────────────────────────────────
# GESTIÓN DEL HISTORIAL
# ─────────────────────────────────────────────────────────────────────────────

def clear_history() -> None:
    """Limpia el historial de conversación."""
    global _history
    _history = []


def get_history() -> list[dict]:
    """Devuelve el historial actual (para debug)."""
    return _history.copy()
