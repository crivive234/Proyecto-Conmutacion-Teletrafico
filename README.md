# DevOps Logo Detector

Detección en tiempo real de logos de herramientas DevOps usando **YOLOv8** + **FastAPI** + **Groq**, todo containerizado en **Docker**.

Proyecto final de la asignatura **Conmutación y Teletráfico** — Fundación Universitaria Compensar.

---

## Logos detectables

| Logo | Herramienta |
|------|-------------|
| 🐳 | Docker |
| 🦭 | Podman |
| 🟣 | Terraform |
| 🖥️ | QEMU |
| 🔴 | Ansible |
| 🐇 | RabbitMQ |
| ☸️ | Kubernetes |

---

## Arquitectura

```
Browser (localhost:8001)
  └── Web UI (video + chat)
        ├── Video stream ──→ detector:8000/stream   (MJPEG)
        └── Chat ──────────→ chatbot:8001/chat      (POST)
                                  └── consulta ────→ detector:8000/detections
                                  └── respuesta ───→ Groq API (LLaMA 3.1)
```

Dos contenedores Docker en la misma red interna `devops-net`:

| Contenedor | Puerto | Función |
|------------|--------|---------|
| `detector` | 8000 | Captura cámara, corre YOLOv8, expone detecciones |
| `chatbot`  | 8001 | Sirve la UI, gestiona el chat con contexto de logos |

---

## Requisitos

- Docker y Docker Compose
- Cámara USB conectada (o archivo de video)
- Clave de API de Groq (gratis en [console.groq.com](https://console.groq.com))
- Modelo entrenado `models/best.pt`

---

## Instalación y primer uso

### 1. Clonar el repositorio

```bash
git clone <repo>
cd devops-logo-detector
```

### 2. Configurar la API key de Groq

```bash
echo "GROQ_API_KEY=gsk_tu-clave-aqui" > .env
```

### 3. Generar el dataset y entrenar el modelo

```bash
# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependencias de entrenamiento
pip install -r requirements-dev.txt

# Generar dataset sintético (logos sobre fondos variados)
python scripts/generate_dataset.py

# Entrenar (~30-60 min en CPU)
python scripts/train.py
```

El modelo entrenado queda en `models/best.pt` automáticamente.

### 4. Agregar logos PNG con fondo transparente

Coloca un archivo PNG por cada herramienta en la carpeta `logos/`:

```
logos/
├── docker.png
├── podman.png
├── terraform.png
├── qemu.png
├── ansible.png
├── rabbitmq.png
└── kubernetes.png
```

> Los logos deben tener **fondo transparente** (canal alpha). Puedes obtenerlos desde los repositorios oficiales de cada herramienta o desde Wikimedia Commons.

### 5. Levantar los contenedores

```bash
docker compose up --build
```

La primera vez descarga las imágenes base y puede tardar varios minutos.

### 6. Abrir la interfaz

Abre en el browser: **http://localhost:8001**

---

## Uso de la interfaz

```
┌─────────────────────────────┬──────────────────┐
│                             │  Asistente DevOps│
│   Stream de la cámara       │                  │
│   (con bounding boxes)      │  [mensajes...]   │
│                             │                  │
├─────────────────────────────│                  │
│ Logos detectados en pantalla│                  │
│  ● docker  ● kubernetes     │  [escribe aquí]  │
└─────────────────────────────┴──────────────────┘
```

1. **Apunta la cámara** hacia un logo de herramienta DevOps
2. El panel inferior izquierdo muestra los **logos detectados en tiempo real**
3. **Escribe una pregunta** en el chat sobre cualquier herramienta
4. El asistente responde sabiendo **qué logos hay en pantalla** en ese momento

**Ejemplo de interacción:**
> *[Cámara detectando: docker, kubernetes]*
> Usuario: "¿Qué diferencia hay entre estos dos?"
> Asistente: "Docker es un motor de contenedores... Kubernetes es un orquestador..."

---

## Endpoints de la API

### Contenedor detector (puerto 8000)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/stream` | GET | Stream MJPEG de la cámara con bounding boxes |
| `/detections` | GET | JSON con logos detectados actualmente |
| `/health` | GET | Estado del modelo y la cámara |

Ejemplo de `/detections`:
```json
{
  "logos": ["docker", "kubernetes"],
  "count": 2,
  "model_ready": true,
  "timestamp": 1718000000.0
}
```

### Contenedor chatbot (puerto 8001)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Interfaz web completa |
| `/chat` | POST | Enviar mensaje y recibir respuesta |
| `/clear` | POST | Limpiar historial de conversación |
| `/health` | GET | Estado del servicio |

Ejemplo de `/chat`:
```bash
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "¿Qué es Docker?"}'
```

---

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | Clave de API de Groq (obligatoria) |
| `MODEL_PATH` | `models/best.pt` | Ruta al modelo entrenado |
| `CONFIDENCE_THRESHOLD` | `0.50` | Confianza mínima para detectar |
| `VIDEO_SOURCE` | `0` | Fuente de video (0 = cámara, ruta = archivo) |
| `MAX_FPS` | `15` | FPS máximos del stream |
| `DETECTOR_URL` | `http://detector:8000` | URL interna del detector |

---

## Estructura del proyecto

```
devops-logo-detector/
├── app/                        ← Contenedor detector (Fase 1)
│   ├── main.py                 ← Endpoints FastAPI
│   └── detector.py             ← Wrapper YOLOv8 + cámara
├── chatbot_app/                ← Contenedor chatbot (Fase 2)
│   ├── main.py                 ← Endpoints FastAPI
│   ├── chatbot.py              ← Lógica Groq + detecciones
│   └── templates/
│       └── index.html          ← Web UI
├── parrot_app/                 ← Contenedor auditoría (Fase 3)
│   ├── audit.sh                ← Script nmap
│   └── report.py               ← Generador de reporte HTML
├── scripts/
│   ├── generate_dataset.py     ← Dataset sintético
│   ├── train.py                ← Entrenamiento YOLOv8
│   └── phase4/                 ← Scripts Kubernetes
├── logos/                      ← PNGs con fondo transparente
├── models/
│   └── best.pt                 ← Modelo entrenado
├── dataset/                    ← Imágenes y anotaciones
├── runs/                       ← Resultados del entrenamiento
├── reports/                    ← Reportes de auditoría Parrot
├── Dockerfile.detector
├── Dockerfile.chatbot
├── Dockerfile.parrot
├── docker-compose.yml
├── requirements.txt            ← Dependencias del detector
├── requirements-chatbot.txt    ← Dependencias del chatbot
├── requirements-dev.txt        ← Dependencias para entrenar (host)
└── .env                        ← GROQ_API_KEY (no subir a git)
```

---

## Comandos útiles

```bash
# Levantar todo
docker compose up

# Levantar en segundo plano
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f

# Ver logs de un contenedor específico
docker compose logs -f detector
docker compose logs -f chatbot

# Reiniciar un contenedor
docker compose restart detector

# Detener todo
docker compose down

# Reconstruir después de cambios en el código
docker compose up --build

# Ejecutar auditoría Parrot OS
docker compose --profile audit run --rm parrot

# Entrenar el modelo
docker compose --profile train up trainer
```

---

## Ajustar la cámara

Si tu cámara no está en `/dev/video0`:

```bash
# Ver dispositivos de video disponibles
ls /dev/video*

# Cambiar en docker-compose.yml
devices:
  - /dev/video1:/dev/video0
```

Para usar un archivo de video en lugar de cámara:

```yaml
environment:
  - VIDEO_SOURCE=/videos/demo.mp4
volumes:
  - ./videos:/videos
```

---

## Solución de problemas

**El chatbot no responde:**
- Verifica que `GROQ_API_KEY` esté en el `.env`
- Comprueba el estado: `curl http://localhost:8001/health`

**El modelo no detecta logos:**
- Verifica que `models/best.pt` existe
- Comprueba el estado: `curl http://localhost:8000/health`
- Si el mAP50 del entrenamiento fue menor a 0.70, regenera el dataset con más fondos en `backgrounds/`

**La cámara no abre:**
- Verifica que está conectada: `ls /dev/video*`
- Ajusta el device en `docker-compose.yml`

**Error de red Docker en Arch Linux:**
```bash
sudo modprobe veth
sudo systemctl restart docker
```

---

## Licencia

MIT — Proyecto educativo / Fundación Universitaria Compensar.
