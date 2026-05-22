#!/usr/bin/env bash
# setup_agones.sh
# Instala Agones en Minikube y despliega la flota de SuperTuxKart.
#
# Uso:
#   bash scripts/phase4/setup_agones.sh

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[*]${RESET} $*"; }
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }
err()  { echo -e "${RED}[✗]${RESET} $*"; exit 1; }

# Versión de Agones — verifica la última en https://agones.dev/chart/stable
AGONES_VERSION="1.44.0"

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════╗"
echo "║      Agones + SuperTuxKart — Setup               ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── Verificar que el cluster está corriendo ────────────────────────────────────

if ! kubectl get nodes &>/dev/null; then
  err "No hay cluster activo. Ejecuta primero: bash scripts/phase4/install_k8s_arch.sh"
fi
ok "Cluster activo"

# ── PASO 1: Repositorio Helm de Agones ────────────────────────────────────────

log "PASO 1 — Agregando repositorio Helm de Agones"

helm repo add agones https://agones.dev/chart/stable 2>/dev/null || true
helm repo update
ok "Repositorio actualizado"

# ── PASO 2: Instalar Agones ───────────────────────────────────────────────────

log "PASO 2 — Instalando Agones ${AGONES_VERSION}"

helm upgrade --install agones agones/agones \
  --version "${AGONES_VERSION}" \
  --namespace agones-system \
  --create-namespace \
  --set agones.featureGates="" \
  --wait --timeout 5m

ok "Agones instalado"

# ── PASO 3: Verificar pods de Agones ─────────────────────────────────────────

log "PASO 3 — Verificando pods de Agones"

echo ""
kubectl get pods --namespace agones-system
echo ""

READY=$(kubectl get pods --namespace agones-system --no-headers 2>/dev/null \
        | grep -c "Running" || echo "0")

if [ "${READY}" -ge 2 ]; then
  ok "${READY} pods de Agones corriendo"
else
  warn "Algunos pods aún no están Running. Verifica con:"
  warn "kubectl get pods -n agones-system"
fi

# ── PASO 4: Desplegar flota de SuperTuxKart ───────────────────────────────────

log "PASO 4 — Desplegando flota de SuperTuxKart"

# Aplicar el fleet.yaml local (versión personalizada para el proyecto)
FLEET_FILE="$(dirname "$0")/supertuxkart-fleet.yaml"

if [ -f "${FLEET_FILE}" ]; then
  kubectl apply -f "${FLEET_FILE}"
  ok "Flota aplicada desde archivo local"
else
  # Fallback: descargar desde el repositorio oficial de Agones
  warn "fleet.yaml local no encontrado — descargando desde repositorio oficial"
  kubectl apply -f \
    "https://raw.githubusercontent.com/googleforgames/agones/release-${AGONES_VERSION}/examples/supertuxkart/fleet.yaml"
  ok "Flota aplicada desde repositorio oficial"
fi

# ── PASO 5: Esperar a que los servidores estén Ready ─────────────────────────

log "PASO 5 — Esperando servidores de juego (puede tardar 1-2 min)"

echo "Esperando que la flota levante..."
for i in $(seq 1 24); do
  READY_GS=$(kubectl get fleet supertuxkart --no-headers 2>/dev/null \
             | awk '{print $6}' || echo "0")
  if [ "${READY_GS:-0}" -ge 1 ]; then
    ok "Servidores de juego listos"
    break
  fi
  echo -n "."
  sleep 5
done
echo ""

# ── PASO 6: Exponer el juego con minikube tunnel ──────────────────────────────

log "PASO 6 — Estado de los GameServers"

echo ""
kubectl get fleet
echo ""
kubectl get gameservers
echo ""

ok "Flota de SuperTuxKart desplegada"
echo ""
echo -e "${BOLD}── Siguiente paso ───────────────────────────────────────${RESET}"
echo "  Para obtener la IP y puerto de conexión:"
echo "  bash scripts/phase4/connect_players.sh"
