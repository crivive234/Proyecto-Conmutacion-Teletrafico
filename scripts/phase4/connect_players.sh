#!/usr/bin/env bash
# connect_players.sh

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

log "Obteniendo IP del nodo Minikube..."
MINIKUBE_IP=$(minikube ip 2>/dev/null)

if [ -z "${MINIKUBE_IP}" ]; then
  warn "No se pudo obtener la IP de Minikube. ¿Está corriendo?"
  warn "Verifica con: minikube status"
  exit 1
fi
ok "IP del nodo Minikube: ${MINIKUBE_IP}"

log "Estado de los servidores de juego..."
echo ""
kubectl get gameservers -o wide
echo ""

echo -e "${BOLD}── Cómo conectarse desde SuperTuxKart ───────────────────${RESET}"
echo ""
echo "  1. Descarga SuperTuxKart desde: https://supertuxkart.net"
echo "  2. Abre el juego en cada computadora"
echo "  3. Ve a: Online → Enter server address"
echo "  4. Usa la IP y puerto de cada servidor listado arriba"
echo ""

# Leer puertos dinámicos asignados por Agones
mapfile -t PORTS < <(kubectl get gameservers --no-headers 2>/dev/null | awk '{print $5}')
mapfile -t STATES < <(kubectl get gameservers --no-headers 2>/dev/null | awk '{print $3}')

echo -e "  ${GREEN}IP del nodo: ${MINIKUBE_IP}${RESET}"
echo ""
for i in "${!PORTS[@]}"; do
  PORT="${PORTS[$i]}"
  STATE="${STATES[$i]}"
  if [ -n "${PORT}" ]; then
    echo -e "  ${GREEN}Jugador $((i+1)):  ${MINIKUBE_IP}:${PORT}  (${STATE})${RESET}"
  fi
done
echo ""

echo "  Para 3 jugadores desde la misma máquina:"
echo "    supertuxkart &; supertuxkart &; supertuxkart"
echo ""

log "Verificando acceso a los puertos UDP..."
ALL_OK=true
for PORT in "${PORTS[@]}"; do
  if [ -n "${PORT}" ]; then
    if nc -zu "${MINIKUBE_IP}" "${PORT}" -w 2 &>/dev/null; then
      ok "Puerto ${PORT} UDP accesible"
    else
      warn "Puerto ${PORT} UDP no accesible aún"
      ALL_OK=false
    fi
  fi
done

if [ "${ALL_OK}" = false ]; then
  warn "Algunos servidores aún están iniciando. Espera 30 segundos y vuelve a intentar."
fi

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
