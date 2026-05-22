#!/usr/bin/env bash
# audit.sh
# Auditoría interna de la arquitectura DevOps.
# Escanea los contenedores del proyecto (detector y chatbot)
# y guarda los resultados en /reports para generar el informe.
#
# Uso (dentro del contenedor):
#   bash audit.sh
#   bash audit.sh --target detector   ← solo un objetivo

set -euo pipefail

# ── Configuración ──────────────────────────────────────────────────────────────

REPORTS_DIR="/reports"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
XML_OUT="${REPORTS_DIR}/scan_${TIMESTAMP}.xml"
TXT_OUT="${REPORTS_DIR}/scan_${TIMESTAMP}.txt"

# Objetivos: nombres de servicio Docker (DNS interno de devops-net)
TARGETS="${AUDIT_TARGETS:-detector chatbot}"

# Subred del proyecto para descubrimiento de hosts
SUBNET="${AUDIT_SUBNET:-172.20.0.0/24}"

# ── Colores para la terminal ───────────────────────────────────────────────────

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[*]${RESET} $*"; }
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }
err()  { echo -e "${RED}[✗]${RESET} $*"; }

banner() {
  echo -e "${BOLD}"
  echo "╔══════════════════════════════════════════════════╗"
  echo "║     Auditoría Interna — DevOps Logo Detector     ║"
  echo "║              Contenedor Parrot OS                ║"
  echo "╚══════════════════════════════════════════════════╝"
  echo -e "${RESET}"
  echo "  Fecha  : $(date '+%Y-%m-%d %H:%M:%S')"
  echo "  Targets: ${TARGETS}"
  echo "  Subred : ${SUBNET}"
  echo ""
}

# ── Preparación ────────────────────────────────────────────────────────────────

mkdir -p "${REPORTS_DIR}"

banner

# ── FASE 1: Descubrimiento de hosts en la red interna ─────────────────────────

log "FASE 1 — Descubrimiento de hosts en ${SUBNET}"

nmap -sn "${SUBNET}" \
  -oN "${REPORTS_DIR}/discovery_${TIMESTAMP}.txt" \
  2>/dev/null || warn "Descubrimiento parcial (puede requerir privilegios)"

ok "Hosts activos guardados en discovery_${TIMESTAMP}.txt"

# ── FASE 2: Escaneo de puertos por servicio ───────────────────────────────────

log "FASE 2 — Escaneo de puertos en servicios del proyecto"

# nmap con:
#   -sV  → detectar versión del servicio
#   -sC  → scripts NSE por defecto (no agresivos)
#   -p-  → todos los puertos (limitado a los conocidos del proyecto)
#   -oX  → salida XML para el generador de reporte
#   -oN  → salida legible para humanos

nmap -sV -sC \
  -p 8000,8001 \
  --open \
  --reason \
  -oX "${XML_OUT}" \
  -oN "${TXT_OUT}" \
  ${TARGETS} \
  2>/dev/null

ok "Escaneo de puertos completado"

# ── FASE 3: Scripts NSE específicos ───────────────────────────────────────────

log "FASE 3 — Scripts NSE de seguridad (no invasivos)"

NSE_OUT="${REPORTS_DIR}/nse_${TIMESTAMP}.txt"

nmap -sV \
  -p 8000,8001 \
  --script="http-headers,http-methods,http-title" \
  ${TARGETS} \
  -oN "${NSE_OUT}" \
  2>/dev/null || warn "Algunos scripts NSE fallaron (normal en entorno sin privilegios)"

ok "Scripts NSE guardados en nse_${TIMESTAMP}.txt"

# ── FASE 4: Verificación de servicios HTTP ────────────────────────────────────

log "FASE 4 — Verificación de endpoints HTTP"

HTTP_OUT="${REPORTS_DIR}/http_check_${TIMESTAMP}.txt"

check_endpoint() {
  local host=$1
  local port=$2
  local path=$3
  local url="http://${host}:${port}${path}"

  status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "${url}" 2>/dev/null || echo "000")

  if [ "${status}" = "200" ]; then
    echo "  [OK  ${status}] ${url}" | tee -a "${HTTP_OUT}"
  elif [ "${status}" = "000" ]; then
    echo "  [SIN RESPUESTA] ${url}" | tee -a "${HTTP_OUT}"
  else
    echo "  [HTTP ${status}] ${url}" | tee -a "${HTTP_OUT}"
  fi
}

echo "=== Verificación de endpoints HTTP ===" > "${HTTP_OUT}"
echo "Fecha: $(date)" >> "${HTTP_OUT}"
echo "" >> "${HTTP_OUT}"

check_endpoint "detector" "8000" "/health"
check_endpoint "detector" "8000" "/detections"
check_endpoint "detector" "8000" "/stream"
check_endpoint "chatbot"  "8001" "/health"
check_endpoint "chatbot"  "8001" "/"

ok "Verificación HTTP guardada en http_check_${TIMESTAMP}.txt"

# ── FASE 5: Generar reporte HTML ──────────────────────────────────────────────

log "FASE 5 — Generando reporte HTML"

python3 /app/report.py \
  --xml   "${XML_OUT}" \
  --nse   "${NSE_OUT}" \
  --http  "${HTTP_OUT}" \
  --out   "${REPORTS_DIR}/reporte_${TIMESTAMP}.html" \
  --ts    "${TIMESTAMP}"

ok "Reporte HTML generado: reporte_${TIMESTAMP}.html"

# ── Resumen final ──────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}── Archivos generados en ${REPORTS_DIR} ─────────────────${RESET}"
ls -lh "${REPORTS_DIR}/"*"${TIMESTAMP}"* 2>/dev/null
echo ""
echo -e "${GREEN}Auditoría completada.${RESET}"
echo "Abre reports/reporte_${TIMESTAMP}.html en tu navegador para ver el informe completo."
