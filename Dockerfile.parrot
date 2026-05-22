# ── Imagen base oficial de Parrot OS ─────────────────────────────────────────
FROM parrotsec/core:latest

# ── Variables de entorno ───────────────────────────────────────────────────────
ENV DEBIAN_FRONTEND=noninteractive \
    AUDIT_TARGETS="detector chatbot" \
    AUDIT_SUBNET="172.20.0.0/24"

# ── Herramientas necesarias ────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        nmap \
        curl \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

# ── Directorio de trabajo ──────────────────────────────────────────────────────
WORKDIR /app

# ── Scripts de auditoría ───────────────────────────────────────────────────────
COPY parrot_app/audit.sh  /app/audit.sh
COPY parrot_app/report.py /app/report.py
RUN chmod +x /app/audit.sh

# ── Carpeta de reportes (montada como volumen en runtime) ─────────────────────
RUN mkdir -p /reports

# ── El contenedor ejecuta la auditoría y termina ──────────────────────────────
CMD ["bash", "/app/audit.sh"]
