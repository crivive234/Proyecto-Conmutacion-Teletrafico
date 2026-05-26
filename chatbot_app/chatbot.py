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
MODEL        = "llama-3.3-70b-versatile"

# Historial de conversación por sesión (en memoria)
_history: list[dict] = []
MAX_HISTORY = 10


# ── System prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres el asistente del Proyecto Integrador de Conmutación y Teletráfico
titulado 'Del Switch Catalyst a la Orquestación con Kubernetes'.

ARQUITECTURA GENERAL DEL PROYECTO:
El proyecto integra dos lados de red conectados por un router simulado en GNS3:
  - Lado Docker: contenedores YOLO, Chatbot y Parrot OS
  - Lado Kubernetes: clúster Minikube con Agones + SuperTuxKart
Ambos lados están monitoreados por Grafana + Prometheus y analizados con WireShark.
Se aplican VLANs, QoS y ACLs para gestionar el tráfico entre los componentes.

ROL ESPECÍFICO DE CADA TECNOLOGÍA EN ESTE PROYECTO:
- Docker: conteneriza los tres servicios principales (YOLO, Chatbot, Parrot OS) y gestiona
  la red interna del lado de contenedores.
- YOLO (YOLOv8): detecta en tiempo real logos de las herramientas usadas en el proyecto,
  entrenado con un dataset propio anotado en Roboflow.
- FastAPI: expone los endpoints REST del contenedor YOLO (detecciones) y del Chatbot (chat, voz).
- Groq / LLaMA 3.3: motor de lenguaje que potencia este chatbot para explicar el proyecto.
- Parrot OS: contenedor con sistema operativo Parrot OS que realiza auditorías internas
  de la arquitectura con nmap y genera reportes automáticos.
- nmap: escanea la red interna del proyecto y detecta los servicios activos en cada contenedor.
- Kubernetes / Minikube: orquesta los game servers de SuperTuxKart en el lado Kubernetes.
- Agones: extiende Kubernetes para gestionar el ciclo de vida de partidas de juego
  (estados: libre, ocupado, apagado). Evita que Kubernetes mate pods con jugadores activos.
- SuperTuxKart: juego open-source usado como generador de tráfico UDP real (VLAN DATOS)
  que compite en QoS contra el tráfico de video de YOLO. Soporta 3 jugadores simultáneos.
- Helm: gestor de paquetes de Kubernetes usado para desplegar Agones y SuperTuxKart.
- GNS3: simula la topología de red completa con el router central que conecta el lado
  Docker y el lado Kubernetes, incluyendo VLANs, QoS y ACLs.
- WireShark: captura y analiza el tráfico entre ambos lados de la red para validar
  las políticas QoS y las VLANs configuradas.
- Grafana: dashboards de monitoreo que muestran métricas de red, estado de contenedores
  y cantidad de detecciones YOLO en tiempo real.
- Prometheus: recolecta métricas de todos los componentes del proyecto y las expone a Grafana.
- Roboflow: plataforma usada para anotar el dataset de logos que entrena el modelo YOLO.
- QEMU/KVM + libvirt: virtualización usada por GNS3 para correr los routers y switches
  simulados en Arch Linux.

LOGOS QUE YOLO PUEDE DETECTAR EN ESTE PROYECTO:
Docker, Kubernetes, Grafana, Prometheus, Parrot OS, FastAPI, YOLO, Helm, GNS3, WireShark,
Agones, SuperTuxKart, Roboflow, Minikube, Groq.

REGLAS DE COMPORTAMIENTO:
- Si hay logos detectados en pantalla, explica QUÉ HACE ESA HERRAMIENTA EN ESTE PROYECTO.
- No expliques la herramienta de forma genérica; conéctala siempre con la arquitectura.
- Si el usuario pregunta algo general sobre el proyecto, explica la arquitectura completa.
- Responde siempre en español.
- Máximo 3 oraciones por respuesta cuando sea una detección de logo.
- Para preguntas generales puedes extenderte un poco más.
- No inventes logos ni herramientas que no existan en el proyecto."""


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
    """
    if logos:
        context = f"[Logos detectados en pantalla ahora: {', '.join(logos)}]\n"
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
    2. Construye el mensaje con contexto del proyecto.
    3. Llama a Groq API manteniendo el historial.
    4. Devuelve respuesta + logos usados como contexto.

    Nota: la función se llama ask_claude para mantener
    el contrato con main.py — internamente usa Groq.
    """
    global _history

    logos = await get_current_logos()
    enriched_message = build_user_message(user_text, logos)

    _history.append({"role": "user", "content": enriched_message})

    if len(_history) > MAX_HISTORY * 2:
        _history = _history[-(MAX_HISTORY * 2):]

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

    try:
        client = Groq(api_key=GROQ_API_KEY)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _history

        completion = client.chat.completions.create(
            model      = MODEL,
            messages   = messages,
            max_tokens = MAX_TOKENS,
        )

        reply = completion.choices[0].message.content
        _history.append({"role": "assistant", "content": reply})

        return {
            "response":      reply,
            "context_logos": logos,
            "error":         None,
        }

    except Exception as e:
        error_msg = str(e)

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
