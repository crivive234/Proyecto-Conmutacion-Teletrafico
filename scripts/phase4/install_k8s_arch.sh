#!/usr/bin/env bash
# install_k8s_arch.sh
# Instala kubectl, Minikube y Helm en Arch Linux.
# Usa el driver Docker para Minikube (no necesita VM separada).
#
# Uso:
#   bash scripts/phase4/install_k8s_arch.sh

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
echo "║     Fase 4 — Kubernetes Setup (Arch Linux)       ║"
echo "╚══════════════════════════════════════════════════╝"
echo -e "${RESET}"

# Docker debe estar corriendo
if ! docker info &>/dev/null; then
  err "Docker no está corriendo. Ejecuta: sudo systemctl start docker"
fi
ok "Docker activo"

# El usuario debe estar en el grupo docker
if ! groups "$USER" | grep -q docker; then
  err "Agrega tu usuario al grupo docker: sudo usermod -aG docker \$USER && newgrp docker"
fi
ok "Usuario en grupo docker"

# ── PASO 1: kubectl ────────────────────────────────────────────────────────────

log "PASO 1 — Instalando kubectl"

if command -v kubectl &>/dev/null; then
  ok "kubectl ya instalado: $(kubectl version --client --short 2>/dev/null | head -1)"
else
  sudo pacman -S --noconfirm --needed kubectl
  ok "kubectl instalado: $(kubectl version --client --short 2>/dev/null | head -1)"
fi

# ── PASO 2: Minikube ───────────────────────────────────────────────────────────

log "PASO 2 — Instalando Minikube"

if command -v minikube &>/dev/null; then
  ok "Minikube ya instalado: $(minikube version --short)"
else
  # minikube-bin está en AUR
  yay -S --noconfirm --needed minikube-bin
  ok "Minikube instalado: $(minikube version --short)"
fi

# ── PASO 3: Helm ───────────────────────────────────────────────────────────────

log "PASO 3 — Instalando Helm"

if command -v helm &>/dev/null; then
  ok "Helm ya instalado: $(helm version --short)"
else
  sudo pacman -S --noconfirm --needed helm
  ok "Helm instalado: $(helm version --short)"
fi

# ── PASO 4: Arrancar el cluster ────────────────────────────────────────────────

log "PASO 4 — Arrancando cluster Minikube con driver Docker"

# CPUs y memoria razonables para tu hardware (Intel Core Ultra 5, 15GB RAM)
minikube start \
  --driver=docker \
  --cpus=2 \
  --memory=4096 \
  --disk-size=20g \
  --kubernetes-version=stable

ok "Cluster arrancado"

# ── PASO 5: Verificar el cluster ───────────────────────────────────────────────

log "PASO 5 — Verificando el cluster"

echo ""
kubectl get nodes
echo ""

STATUS=$(kubectl get nodes --no-headers | awk '{print $2}' | head -1)
if [ "${STATUS}" = "Ready" ]; then
  ok "Nodo listo — el cluster está operativo"
else
  warn "El nodo aún no está Ready. Espera unos segundos y verifica con: kubectl get nodes"
fi

# ── Resumen ────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}── Herramientas instaladas ──────────────────────────────${RESET}"
echo "  kubectl  : $(kubectl version --client --short 2>/dev/null | head -1)"
echo "  minikube : $(minikube version --short)"
echo "  helm     : $(helm version --short)"
echo ""
echo -e "${GREEN}Siguiente paso:${RESET}"
echo "  bash scripts/phase4/setup_agones.sh"
