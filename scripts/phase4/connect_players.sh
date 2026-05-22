#!/usr/bin/env bash
# connect_players.sh
# Muestra la IP y puerto para que los 3 jugadores se conecten a SuperTuxKart.
#
# Uso:
#   bash scripts/phase4/connect_players.sh

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[*]${RESET} $*"; }
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════╗"
echo "║     SuperTuxKart — Conexión de Jugadores         ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── IP del nodo Minikube ───────────────────────────────────────────────────────

log "Obteniendo IP del nodo Minikube..."
MINIKUBE_IP=$(minikube ip 2>/dev/null)

if [ -z "${MINIKUBE_IP}" ]; then
  warn "No se pudo obtener la IP de Minikube. ¿Está corriendo?"
  warn "Verifica con: minikube status"
  exit 1
fi

ok "IP del nodo Minikube: ${MINIKUBE_IP}"

# ── Estado de los GameServers ─────────────────────────────────────────────────

log "Estado de los servidores de juego..."
echo ""
kubectl get gameservers -o wide
echo ""

# ── Información de conexión ───────────────────────────────────────────────────

echo -e "${BOLD}── Cómo conectarse desde SuperTuxKart ───────────────────${RESET}"
echo ""
echo "  1. Descarga SuperTuxKart desde: https://supertuxkart.net"
echo "  2. Abre el juego en cada computadora"
echo "  3. Ve a: Online → Enter server address"
echo "  4. Ingresa la siguiente dirección:"
echo ""
echo -e "     ${GREEN}IP:    ${MINIKUBE_IP}${RESET}"
echo -e "     ${GREEN}PORT:  7654${RESET}"
echo ""
echo "  Para 3 jugadores desde la misma máquina:"
echo "  Opción A: 3 ventanas distintas del juego"
echo "  Opción B: Abre el juego 3 veces con:"
echo "    supertuxkart &; supertuxkart &; supertuxkart"
echo ""

# ── Verificar que el puerto esté accesible ────────────────────────────────────

log "Verificando acceso al puerto 7654 UDP..."

if nc -zu "${MINIKUBE_IP}" 7654 -w 2 &>/dev/null; then
  ok "Puerto 7654 UDP accesible en ${MINIKUBE_IP}"
else
  warn "Puerto 7654 UDP no accesible todavía"
  warn "El servidor puede estar iniciando. Espera 30 segundos y vuelve a intentar."
fi

# ── Comandos útiles ───────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}── Comandos útiles ──────────────────────────────────────${RESET}"
echo "  Ver logs del servidor:    kubectl logs <nombre-gameserver>"
echo "  Ver estado de la flota:   kubectl get fleet"
echo "  Ver todos los servidores: kubectl get gameservers"
echo "  Escalar la flota:         kubectl scale fleet supertuxkart --replicas=5"
echo "  Detener todo:             kubectl delete fleet supertuxkart"
echo ""
echo -e "${BOLD}── Apagar el cluster al terminar ────────────────────────${RESET}"
echo "  minikube stop             ← pausa el cluster (guarda el estado)"
echo "  minikube delete           ← elimina el cluster completamente"
