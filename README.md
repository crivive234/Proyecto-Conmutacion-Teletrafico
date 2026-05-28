# DevOps Logo Detector

Detección en tiempo real de logos de herramientas DevOps usando **YOLOv8** + **FastAPI** + **Groq**, orquestación de servidores de juego con **Kubernetes + Agones**, auditoría de red con **Parrot OS** y monitoreo con **Grafana + Prometheus**.

Proyecto final de la asignatura **Conmutación y Teletráfico** — Fundación Universitaria Compensar.

---

## Fases del proyecto

| Fase | Descripción | Estado |
|------|-------------|--------|
| 1 | Contenedor YOLO + FastAPI + Web UI | ✅ Completa |
| 2 | Chatbot integrado con detecciones | ✅ Completa |
| 3 | Auditoría de red con Parrot OS | ✅ Completa |
| 4 | Kubernetes + Agones + SuperTuxKart | ✅ Completa |
| 5 | Equipos físicos de red (VLANs, QoS, ACLs) | ⏳ Pendiente |
| 6 | Monitoreo con Grafana + Prometheus | ⏳ Pendiente |

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

Kubernetes (Minikube)
  └── Agones
        └── Fleet: supertuxkart (3 réplicas)
              ├── GameServer 1 → 192.168.49.2:<puerto-dinámico>
              ├── GameServer 2 → 192.168.49.2:<puerto-dinámico>
              └── GameServer 3 → 192.168.49.2:<puerto-dinámico>
```

Contenedores Docker en la red interna `devops-net`:

| Contenedor | Puerto | Función |
|------------|--------|---------|
| `detector` | 8000 | Captura cámara, corre YOLOv8, expone detecciones |
| `chatbot`  | 8001 | Sirve la UI, gestiona el chat con contexto de logos |

---

## Requisitos

- Docker y Docker Compose
- Minikube + kubectl + Helm (solo para Fase 4)
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
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# Generar dataset sintético
python scripts/generate_dataset.py

# Entrenar (~30-60 min en CPU)
python scripts/train.py
```

El modelo entrenado queda en `models/best.pt` automáticamente.

### 4. Agregar logos PNG con fondo transparente

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

> Los logos deben tener **fondo transparente** (canal alpha).

### 5. Levantar los contenedores

```bash
docker compose up --build
```

### 6. Abrir la interfaz

Abre en el browser: **http://localhost:8001**

---

## Fase 4 — Kubernetes + Agones + SuperTuxKart

### Requisitos

- Minikube `>= v1.38`
- kubectl
- Helm `>= v4`
- Docker corriendo como driver de Minikube

### Instalación del cluster

```bash
bash scripts/phase4/install_k8s_arch.sh
```

Instala kubectl, Minikube y Helm (si no están), y arranca el cluster con driver Docker.

### Desplegar Agones y la flota de SuperTuxKart

```bash
bash scripts/phase4/setup_agones.sh
```

Instala Agones 1.44.0 vía Helm y despliega una flota de 3 servidores SuperTuxKart.

### Obtener IPs y puertos de conexión

```bash
bash scripts/phase4/connect_players.sh
```

Muestra la IP del nodo Minikube y el puerto dinámico asignado a cada GameServer.

```bash
# Ver el estado de los servidores directamente
kubectl get gameservers
```

Ejemplo de salida cuando los servidores están listos:

```
NAME                       STATE   ADDRESS        PORT   NODE       AGE
supertuxkart-xxxxx-aaaaa   Ready   192.168.49.2   7308   minikube   2m
supertuxkart-xxxxx-bbbbb   Ready   192.168.49.2   7090   minikube   2m
supertuxkart-xxxxx-ccccc   Ready   192.168.49.2   7791   minikube   2m
```

### Conectar jugadores

1. Descarga SuperTuxKart desde [supertuxkart.net](https://supertuxkart.net)
2. Abre el juego → **Online → Enter server address**
3. Ingresa la `ADDRESS` y el `PORT` de cualquier GameServer en estado `Ready`

**Para probar con 3 ventanas en la misma máquina:**

```bash
supertuxkart & supertuxkart & supertuxkart
```

> **Nota:** La IP `192.168.49.2` es interna de Minikube y solo es accesible desde la máquina host. Para exponer a la red local se requiere `minikube tunnel`.

### Comandos útiles

```bash
# Ver estado de la flota
kubectl get fleet

# Ver todos los servidores y sus puertos
kubectl get gameservers

# Ver logs de un servidor
kubectl logs <nombre-gameserver>

# Escalar la flota
kubectl scale fleet supertuxkart --replicas=5

# Eliminar la flota
kubectl delete fleet supertuxkart

# Pausar el cluster (guarda el estado)
minikube stop

# Eliminar el cluster
minikube delete
```

---

## Uso de la interfaz web

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

**Ejemplo:**
> *[Cámara detectando: docker, kubernetes]*
> Usuario: "¿Qué diferencia hay entre estos dos?"
> Asistente: "Docker es un motor de contenedores... Kubernetes es un orquestador..."

---

## Endpoints de la API

### Detector (puerto 8000)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/stream` | GET | Stream MJPEG con bounding boxes |
| `/detections` | GET | JSON con logos detectados actualmente |
| `/health` | GET | Estado del modelo y la cámara |

### Chatbot (puerto 8001)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/` | GET | Interfaz web |
| `/chat` | POST | Enviar mensaje y recibir respuesta |
| `/clear` | POST | Limpiar historial |
| `/health` | GET | Estado del servicio |

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
│   ├── main.py
│   └── detector.py
├── chatbot_app/                ← Contenedor chatbot (Fase 2)
│   ├── main.py
│   ├── chatbot.py
│   └── templates/
│       └── index.html
├── parrot_app/                 ← Contenedor auditoría (Fase 3)
│   ├── audit.sh
│   └── report.py
├── scripts/
│   ├── generate_dataset.py
│   ├── train.py
│   └── phase4/                 ← Scripts Kubernetes (Fase 4)
│       ├── install_k8s_arch.sh
│       ├── setup_agones.sh
│       ├── connect_players.sh
│       └── supertuxkart-fleet.yaml
├── logos/
├── models/
│   └── best.pt
├── dataset/
├── runs/
├── reports/
├── Dockerfile.detector
├── Dockerfile.chatbot
├── Dockerfile.parrot
├── docker-compose.yml
├── requirements.txt
├── requirements-chatbot.txt
├── requirements-dev.txt
└── .env
```

---

## Comandos Docker útiles

```bash
# Levantar todo
docker compose up

# Levantar en segundo plano
docker compose up -d

# Ver logs en tiempo real
docker compose logs -f

# Ver logs de un contenedor específico
docker compose logs -f detector

# Reconstruir después de cambios
docker compose up --build

# Ejecutar auditoría Parrot OS
docker compose --profile audit run --rm parrot

# Entrenar el modelo
docker compose --profile train up trainer

# Detener todo
docker compose down
```

---

## Solución de problemas

**El chatbot no responde:**
```bash
curl http://localhost:8001/health
# Verifica que GROQ_API_KEY esté en el .env
```

**El modelo no detecta logos:**
```bash
curl http://localhost:8000/health
# Verifica que models/best.pt existe
# Si mAP50 < 0.70, regenera el dataset con más fondos en backgrounds/
```

**La cámara no abre:**
```bash
ls /dev/video*
# Ajusta el device en docker-compose.yml
```

**GameServers en estado Error o Scheduled:**
```bash
kubectl logs <nombre-gameserver>
# Verifica que la imagen del fleet.yaml es compatible con la versión de Agones instalada
```

**Error de red Docker en Arch Linux:**
```bash
sudo modprobe veth
sudo systemctl restart docker
```

---

## Licencia

MIT — Proyecto educativo / Fundación Universitaria Compensar.
