#!/usr/bin/env bash
# capture_traffic.sh
# Captura tráfico diferenciado por VLAN usando tshark
# y genera archivos .pcap para analizar en Wireshark.
#
# Uso:
#   sudo bash scripts/phase5/capture_traffic.sh [vlan10|vlan20|vlan30|all]
#
# Ejemplo:
#   sudo bash scripts/phase5/capture_traffic.sh all

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'
BOLD='\033[1m'; RESET='\033[0m'

log()  { echo -e "${CYAN}[*]${RESET} $*"; }
ok()   { echo -e "${GREEN}[✓]${RESET} $*"; }
warn() { echo -e "${YELLOW}[!]${RESET} $*"; }

CAPTURE_DIR="captures"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DURATION=60   # segundos de captura por defecto
TARGET="${1:-all}"

mkdir -p "$CAPTURE_DIR"

echo -e "${BOLD}"
echo "╔══════════════════════════════════════════════════╗"
echo "║   Fase 5 — Captura de Tráfico por VLAN          ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${RESET}"

[ "$EUID" -ne 0 ] && echo "[!] Recomendado ejecutar con sudo para captura completa"

# ── Función de captura ────────────────────────────────────────────────────────

capture_vlan() {
  local vlan_id="$1"
  local interface="br-vlan${vlan_id}"
  local name="$2"
  local filter="$3"
  local outfile="${CAPTURE_DIR}/vlan${vlan_id}_${name}_${TIMESTAMP}.pcap"
  local txtfile="${CAPTURE_DIR}/vlan${vlan_id}_${name}_${TIMESTAMP}.txt"

  if ! ip link show "$interface" &>/dev/null; then
    warn "Interfaz $interface no encontrada — ¿ejecutaste setup_network.sh?"
    return
  fi

  log "Capturando VLAN ${vlan_id} (${name}) en $interface por ${DURATION}s..."

  # Captura en background
  tshark \
    -i "$interface" \
    -w "$outfile" \
    -a duration:"$DURATION" \
    ${filter:+-f "$filter"} \
    2>/dev/null &

  local PID=$!
  echo "  PID: $PID | Archivo: $outfile"

  # También captura texto para resumen inmediato
  tshark \
    -i "$interface" \
    -a duration:"$DURATION" \
    ${filter:+-f "$filter"} \
    -T fields \
    -e frame.time_relative \
    -e ip.src \
    -e ip.dst \
    -e ip.proto \
    -e tcp.dstport \
    -e udp.dstport \
    -e frame.len \
    -E header=y \
    -E separator=, \
    > "$txtfile" 2>/dev/null &

  ok "Captura iniciada → $outfile"
  echo "  Para ver en Wireshark: wireshark $outfile"
}

# ── Capturas por VLAN ─────────────────────────────────────────────────────────

case "$TARGET" in
  vlan10)
    capture_vlan "10" "VIDEO" "tcp port 8000 or tcp port 8001"
    ;;
  vlan20)
    capture_vlan "20" "DATOS" "udp portrange 7000-8000"
    ;;
  vlan30)
    capture_vlan "30" "MGMT" "tcp port 3000 or tcp port 9090 or tcp port 9100"
    ;;
  all)
    capture_vlan "10" "VIDEO" "tcp port 8000 or tcp port 8001"
    capture_vlan "20" "DATOS" "udp portrange 7000-8000"
    capture_vlan "30" "MGMT"  "tcp port 3000 or tcp port 9090"
    ;;
  *)
    echo "Uso: $0 [vlan10|vlan20|vlan30|all]"
    exit 1
    ;;
esac

# ── Esperar y generar resumen ─────────────────────────────────────────────────

log "Esperando ${DURATION}s para completar las capturas..."
sleep "$DURATION"
wait

echo ""
echo -e "${BOLD}── Archivos generados ───────────────────────────────────${RESET}"
ls -lh "${CAPTURE_DIR}"/*.pcap 2>/dev/null || warn "No se generaron archivos .pcap"

echo ""
echo -e "${BOLD}── Análisis rápido por VLAN ─────────────────────────────${RESET}"

for pcap in "${CAPTURE_DIR}"/*.pcap; do
  [ -f "$pcap" ] || continue
  FNAME=$(basename "$pcap")
  PKTS=$(tshark -r "$pcap" 2>/dev/null | wc -l)
  BYTES=$(ls -lh "$pcap" | awk '{print $5}')
  echo "  $FNAME → $PKTS paquetes ($BYTES)"
done

echo ""
echo -e "${BOLD}── Abrir en Wireshark ───────────────────────────────────${RESET}"
echo "  wireshark ${CAPTURE_DIR}/vlan10_VIDEO_${TIMESTAMP}.pcap &"
echo "  wireshark ${CAPTURE_DIR}/vlan20_DATOS_${TIMESTAMP}.pcap &"
echo "  wireshark ${CAPTURE_DIR}/vlan30_MGMT_${TIMESTAMP}.pcap &"
echo ""
echo -e "${BOLD}── Filtros Wireshark recomendados ───────────────────────${RESET}"
echo "  VIDEO (YOLO stream):    tcp.port == 8000"
echo "  DATOS (SuperTuxKart):   udp && ip.src == 192.168.49.2"
echo "  MGMT (Grafana):         tcp.port == 3000"
echo "  QoS DSCP AF41:          ip.dsfield.dscp == 34"
echo "  QoS DSCP AF21:          ip.dsfield.dscp == 18"
echo "  QoS DSCP CS2:           ip.dsfield.dscp == 16"
