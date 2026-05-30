#!/usr/bin/env bash
# teardown_network.sh
# Elimina todos los recursos creados por setup_network.sh
#
# Uso:
#   sudo bash scripts/phase5/teardown_network.sh

set -euo pipefail

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[*]${RESET} $*"; }
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════╗"
echo "║   Fase 5 — Limpieza de Red                      ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${RESET}"

[ "$EUID" -ne 0 ] && echo "[!] Ejecuta con sudo" && exit 1

# ── Desconectar contenedores de las VLANs ────────────────────────────────────

log "Desconectando contenedores de las redes VLAN"

CONTAINERS=("detector" "chatbot" "grafana" "prometheus" "cadvisor" "node-exporter" "yolo-exporter")
NETWORKS=("vlan10-video" "vlan20-datos" "vlan30-mgmt")

for container in "${CONTAINERS[@]}"; do
  for network in "${NETWORKS[@]}"; do
    docker network disconnect "$network" "$container" 2>/dev/null && \
      ok "$container desconectado de $network" || true
  done
done

# ── Eliminar redes Docker ─────────────────────────────────────────────────────

log "Eliminando redes Docker de fase 5"

for network in "${NETWORKS[@]}"; do
  docker network rm "$network" 2>/dev/null && ok "Red '$network' eliminada" || \
    warn "Red '$network' no encontrada o en uso"
done

# ── Detener dnsmasq ───────────────────────────────────────────────────────────

log "Deteniendo dnsmasq"

pkill -f "dnsmasq.*vlan" 2>/dev/null && ok "dnsmasq detenido" || \
  warn "dnsmasq no estaba corriendo"

rm -f /tmp/dnsmasq-vlan*.pid /tmp/dnsmasq-vlan*.log

# ── Eliminar bridges ──────────────────────────────────────────────────────────

log "Eliminando bridges Linux"

for VID in 10 20 30; do
  BR="br-vlan${VID}"
  if ip link show "$BR" &>/dev/null; then
    ip link set "$BR" down
    ip link delete "$BR" type bridge
    ok "Bridge $BR eliminado"
  else
    warn "Bridge $BR no encontrado"
  fi
done

# ── Limpiar sysctl ────────────────────────────────────────────────────────────

rm -f /etc/sysctl.d/99-phase5.conf
ok "Configuración sysctl eliminada"

echo ""
ok "Limpieza de Fase 5 completada"
