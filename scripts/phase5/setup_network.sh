#!/usr/bin/env bash
# setup_network.sh
# Fase 5 — Topología de Red Simulada con GNS3 + c3660
#
# Crea 3 bridges Linux (uno por VLAN), los asocia como redes Docker
# y conecta los contenedores existentes a la VLAN correspondiente.
#
# VLANs:
#   VLAN 10 — VIDEO  (10.10.10.0/24) → detector, chatbot
#   VLAN 20 — DATOS  (10.20.20.0/24) → Minikube / SuperTuxKart
#   VLAN 30 — MGMT   (10.30.30.0/24) → Grafana, Prometheus
#
# Uso:
#   sudo bash scripts/phase5/setup_network.sh

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[*]${RESET} $*"; }
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }
err()  { echo -e "${RED}[✗]${RESET} $*"; exit 1; }

# ── Verificaciones previas ─────────────────────────────────────────────────────

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════╗"
echo "║   Fase 5 — Topología de Red GNS3 + c3660        ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${RESET}"

[ "$EUID" -ne 0 ] && err "Ejecuta con sudo: sudo bash $0"

if ! command -v docker &>/dev/null; then
  err "Docker no encontrado"
fi
ok "Docker disponible"

# ── Configuración de VLANs ────────────────────────────────────────────────────

declare -A VLAN_NAME=( [10]="VIDEO" [20]="DATOS" [30]="MGMT" )
declare -A VLAN_NET=(  [10]="10.10.10" [20]="10.20.20" [30]="10.30.30" )

# IP del host en cada bridge (último usable .254, el router c3660 tendrá .1)
HOST_SUFFIX=254

# ── PASO 1 — Crear bridges Linux por VLAN ────────────────────────────────────

log "PASO 1 — Creando bridges Linux por VLAN"

for VID in 10 20 30; do
  BR="br-vlan${VID}"
  NET="${VLAN_NET[$VID]}"
  NAME="${VLAN_NAME[$VID]}"

  if ip link show "$BR" &>/dev/null; then
    warn "Bridge $BR ya existe — omitiendo creación"
  else
    ip link add name "$BR" type bridge
    ip link set "$BR" up
    ip addr add "${NET}.${HOST_SUFFIX}/24" dev "$BR"
    ok "Bridge $BR creado (${NET}.0/24) — VLAN ${VID} ${NAME}"
  fi
done

# ── PASO 2 — Habilitar IP forwarding ─────────────────────────────────────────

log "PASO 2 — Habilitando IP forwarding"

sysctl -w net.ipv4.ip_forward=1 > /dev/null
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.d/99-phase5.conf
ok "IP forwarding activo"

# ── PASO 3 — Crear redes Docker sobre los bridges ─────────────────────────────

log "PASO 3 — Creando redes Docker por VLAN"

create_docker_net() {
  local name="$1" bridge="$2" subnet="$3" gateway="$4"
  if docker network inspect "$name" &>/dev/null; then
    warn "Red Docker '$name' ya existe — omitiendo"
  else
    docker network create \
      --driver bridge \
      --opt "com.docker.network.bridge.name=${bridge}" \
      --subnet "${subnet}" \
      --gateway "${gateway}" \
      "$name"
    ok "Red Docker '$name' creada (gateway: ${gateway})"
  fi
}

# Gateway = c3660 en GNS3 (se configura en el router IOS)
create_docker_net "vlan10-video" "br-vlan10" "10.10.10.0/24" "10.10.10.1"
create_docker_net "vlan20-datos" "br-vlan20" "10.20.20.0/24" "10.20.20.1"
create_docker_net "vlan30-mgmt"  "br-vlan30" "10.30.30.0/24" "10.30.30.1"

# ── PASO 4 — Conectar contenedores a sus VLANs ────────────────────────────────

log "PASO 4 — Conectando contenedores a las VLANs"

connect_container() {
  local container="$1" network="$2" ip="$3"
  if docker inspect "$container" &>/dev/null; then
    # Verificar si ya está conectado
    if docker inspect "$container" \
        --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' \
        | grep -q "$network"; then
      warn "$container ya está en $network"
    else
      docker network connect --ip "$ip" "$network" "$container"
      ok "$container → $network ($ip)"
    fi
  else
    warn "Contenedor '$container' no está corriendo — omitiendo"
  fi
}

# VLAN 10 — VIDEO: contenedores de detección y chatbot
connect_container "detector"      "vlan10-video" "10.10.10.10"
connect_container "chatbot"       "vlan10-video" "10.10.10.11"

# VLAN 30 — MGMT: monitoreo
connect_container "grafana"        "vlan30-mgmt" "10.30.30.10"
connect_container "prometheus"     "vlan30-mgmt" "10.30.30.11"
connect_container "cadvisor"       "vlan30-mgmt" "10.30.30.12"
connect_container "node-exporter"  "vlan30-mgmt" "10.30.30.13"
connect_container "yolo-exporter"  "vlan30-mgmt" "10.30.30.14"

# ── PASO 5 — Iniciar dnsmasq como DHCP por VLAN ───────────────────────────────

log "PASO 5 — Iniciando dnsmasq para DHCP en cada VLAN"

DNSMASQ_CONF="$(dirname "$0")/dnsmasq.conf"

if [ -f "$DNSMASQ_CONF" ]; then
  # Detener instancias anteriores
  pkill -f "dnsmasq.*phase5" 2>/dev/null || true

  # VLAN 10 — VIDEO
  dnsmasq \
    --interface=br-vlan10 \
    --bind-interfaces \
    --dhcp-range=10.10.10.100,10.10.10.200,24h \
    --dhcp-option=3,10.10.10.1 \
    --dhcp-option=6,8.8.8.8 \
    --pid-file=/tmp/dnsmasq-vlan10.pid \
    --log-facility=/tmp/dnsmasq-vlan10.log \
    --except-interface=lo &

  # VLAN 20 — DATOS
  dnsmasq \
    --interface=br-vlan20 \
    --bind-interfaces \
    --dhcp-range=10.20.20.100,10.20.20.200,24h \
    --dhcp-option=3,10.20.20.1 \
    --dhcp-option=6,8.8.8.8 \
    --pid-file=/tmp/dnsmasq-vlan20.pid \
    --log-facility=/tmp/dnsmasq-vlan20.log \
    --except-interface=lo &

  # VLAN 30 — MGMT
  dnsmasq \
    --interface=br-vlan30 \
    --bind-interfaces \
    --dhcp-range=10.30.30.100,10.30.30.200,24h \
    --dhcp-option=3,10.30.30.1 \
    --dhcp-option=6,8.8.8.8 \
    --pid-file=/tmp/dnsmasq-vlan30.pid \
    --log-facility=/tmp/dnsmasq-vlan30.log \
    --except-interface=lo &

  ok "dnsmasq iniciado en las 3 VLANs"
else
  warn "dnsmasq.conf no encontrado — DHCP no iniciado"
fi

# ── PASO 6 — Rutas hacia Minikube por VLAN 20 ────────────────────────────────

log "PASO 6 — Agregando ruta Minikube → VLAN 20"

MINIKUBE_IP=$(minikube ip 2>/dev/null || echo "")
if [ -n "$MINIKUBE_IP" ]; then
  ip route add "${MINIKUBE_IP}/32" via 10.20.20.1 dev br-vlan20 2>/dev/null || \
    warn "Ruta a Minikube ya existe o c3660 aún no está configurado"
  ok "Ruta agregada: ${MINIKUBE_IP} via VLAN 20"
else
  warn "Minikube no está corriendo — ruta no agregada"
fi

# ── Resumen ────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}── Bridges creados ──────────────────────────────────────${RESET}"
ip link show | grep "br-vlan" | awk '{print "  "$2}' || true
echo ""
echo -e "${BOLD}── Redes Docker ─────────────────────────────────────────${RESET}"
docker network ls | grep "vlan" || true
echo ""
echo -e "${BOLD}── Siguiente paso ───────────────────────────────────────${RESET}"
echo "  1. Abre GNS3 y sigue la guía: scripts/phase5/gns3_guide.md"
echo "  2. Configura el c3660 con:    scripts/phase5/router_config.ios"
echo "  3. Captura tráfico con:       sudo bash scripts/phase5/capture_traffic.sh"
