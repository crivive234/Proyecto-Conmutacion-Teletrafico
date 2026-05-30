#!/usr/bin/env bash
# setup_monitoring.sh
# Levanta el stack de monitoreo: Prometheus + Grafana + cAdvisor + Node Exporter + YOLO Exporter
#
# Uso:
#   bash scripts/phase6/setup_monitoring.sh

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[*]${RESET} $*"; }
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════╗"
echo "║     Fase 6 — Grafana + Prometheus Setup          ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Verificaciones previas ─────────────────────────────────────────────────────

if ! docker info &>/dev/null; then
  echo "[✗] Docker no está corriendo."; exit 1
fi
ok "Docker activo"

if ! docker compose version &>/dev/null; then
  echo "[✗] Docker Compose no está disponible."; exit 1
fi
ok "Docker Compose disponible"

# ── PASO 1 — Crear estructura de directorios ───────────────────────────────────

log "PASO 1 — Creando estructura de directorios de monitoreo"

mkdir -p monitoring/grafana/provisioning/datasources
mkdir -p monitoring/grafana/provisioning/dashboards
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/yolo_exporter

ok "Directorios creados"

# ── PASO 2 — Verificar archivos de configuración ───────────────────────────────

log "PASO 2 — Verificando archivos de configuración"

REQUIRED_FILES=(
  "monitoring/prometheus.yml"
  "monitoring/grafana/provisioning/datasources/datasource.yml"
  "monitoring/grafana/provisioning/dashboards/dashboards.yml"
  "monitoring/grafana/dashboards/devops.json"
  "monitoring/yolo_exporter/exporter.py"
  "monitoring/yolo_exporter/Dockerfile"
  "monitoring/yolo_exporter/requirements.txt"
  "docker-compose.monitoring.yml"
)

ALL_OK=true
for f in "${REQUIRED_FILES[@]}"; do
  if [ -f "$f" ]; then
    ok "  $f"
  else
    warn "  FALTA: $f"
    ALL_OK=false
  fi
done

if [ "$ALL_OK" = false ]; then
  warn "Algunos archivos de configuración faltan."
  warn "Asegúrate de copiar todos los archivos de monitoring/ al proyecto."
  exit 1
fi

# ── PASO 3 — Levantar el stack de monitoreo ────────────────────────────────────

log "PASO 3 — Levantando el stack de monitoreo"

docker compose \
  -f docker-compose.yml \
  -f docker-compose.monitoring.yml \
  up -d --build

ok "Stack de monitoreo levantado"

# ── PASO 4 — Esperar que los servicios estén listos ────────────────────────────

log "PASO 4 — Esperando que los servicios inicien (30 seg)"

sleep 10
echo -n "Esperando Prometheus"
for i in $(seq 1 10); do
  if curl -s http://localhost:9090/-/ready &>/dev/null; then
    echo ""
    ok "Prometheus listo"
    break
  fi
  echo -n "."
  sleep 2
done

echo -n "Esperando Grafana"
for i in $(seq 1 10); do
  if curl -s http://localhost:3000/api/health &>/dev/null; then
    echo ""
    ok "Grafana listo"
    break
  fi
  echo -n "."
  sleep 2
done

# ── PASO 5 — Verificar targets de Prometheus ───────────────────────────────────

log "PASO 5 — Verificando targets de Prometheus"

echo ""
TARGETS=$(curl -s http://localhost:9090/api/v1/targets | \
  python3 -c "
import sys, json
data = json.load(sys.stdin)
for t in data.get('data', {}).get('activeTargets', []):
    job    = t['labels'].get('job', 'unknown')
    health = t['health']
    state  = '✓' if health == 'up' else '✗'
    print(f'  [{state}] {job}: {health}')
" 2>/dev/null || echo "  (no se pudo consultar aún)")
echo "$TARGETS"
echo ""

# ── Resumen ────────────────────────────────────────────────────────────────────

echo -e "${BOLD}── Servicios disponibles ────────────────────────────────${RESET}"
echo ""
echo -e "  ${GREEN}Grafana:${RESET}    http://localhost:3000"
echo -e "             Usuario: admin | Contraseña: admin"
echo ""
echo -e "  ${GREEN}Prometheus:${RESET} http://localhost:9090"
echo ""
echo -e "  ${GREEN}cAdvisor:${RESET}   http://localhost:8081"
echo ""
echo -e "${BOLD}── Comandos útiles ──────────────────────────────────────${RESET}"
echo "  Ver logs de Grafana:     docker compose -f docker-compose.yml -f docker-compose.monitoring.yml logs -f grafana"
echo "  Ver logs de Prometheus:  docker compose -f docker-compose.yml -f docker-compose.monitoring.yml logs -f prometheus"
echo "  Detener monitoreo:       docker compose -f docker-compose.yml -f docker-compose.monitoring.yml down"
echo "  Detener todo:            docker compose -f docker-compose.yml -f docker-compose.monitoring.yml down -v"
