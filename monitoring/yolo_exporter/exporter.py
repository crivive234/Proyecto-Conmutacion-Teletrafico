"""
exporter.py
Exportador Prometheus personalizado para las detecciones de YOLO.

Cada 5 segundos consulta GET /detections del contenedor detector
y actualiza las métricas para que Prometheus las pueda scrapear en /metrics.

Métricas que expone:
  yolo_detections_total            — contador total de detecciones acumuladas
  yolo_logo_detections_total{logo} — contador por tipo de logo
  yolo_logos_active                — gauge: cuántos logos distintos hay ahora
  yolo_model_ready                 — gauge: 1 si el modelo está cargado, 0 si no
  yolo_scrape_errors_total         — contador de errores al consultar el detector
"""

import os
import time
import httpx
from prometheus_client import start_http_server, Counter, Gauge, REGISTRY
from prometheus_client.core import CollectorRegistry

# ── Configuración ──────────────────────────────────────────────────────────────

DETECTOR_URL     = os.getenv("DETECTOR_URL", "http://detector:8000")
SCRAPE_INTERVAL  = int(os.getenv("SCRAPE_INTERVAL", "5"))
EXPORTER_PORT    = int(os.getenv("EXPORTER_PORT", "9200"))

# ── Métricas Prometheus ────────────────────────────────────────────────────────

detections_total = Counter(
    "yolo_detections_total",
    "Número total acumulado de detecciones de logos YOLO"
)

logo_detections = Counter(
    "yolo_logo_detections_total",
    "Número total de detecciones por tipo de logo",
    ["logo"]
)

logos_active = Gauge(
    "yolo_logos_active",
    "Número de logos distintos detectados en el frame actual"
)

model_ready = Gauge(
    "yolo_model_ready",
    "1 si el modelo YOLO está cargado y listo, 0 si no"
)

scrape_errors = Counter(
    "yolo_scrape_errors_total",
    "Número de errores al consultar el endpoint /detections del detector"
)

# ── Loop principal ─────────────────────────────────────────────────────────────

def fetch_detections() -> dict:
    """Consulta GET /detections y devuelve el JSON o lanza excepción."""
    with httpx.Client(timeout=3.0) as client:
        resp = client.get(f"{DETECTOR_URL}/detections")
        resp.raise_for_status()
        return resp.json()


def update_metrics(data: dict) -> None:
    """Actualiza las métricas Prometheus con los datos del detector."""
    logos: list[str] = data.get("logos", [])
    count: int       = data.get("count", len(logos))
    ready: bool      = data.get("model_ready", False)

    # Gauge: logos activos ahora
    logos_active.set(len(logos))

    # Gauge: modelo listo
    model_ready.set(1 if ready else 0)

    # Contadores: incrementar por cada detección reportada
    if count > 0:
        detections_total.inc(count)
        for logo in logos:
            logo_detections.labels(logo=logo).inc()


def main() -> None:
    print(f"[yolo-exporter] Iniciando en puerto {EXPORTER_PORT}")
    print(f"[yolo-exporter] Consultando detector en: {DETECTOR_URL}/detections")
    print(f"[yolo-exporter] Intervalo de scraping: {SCRAPE_INTERVAL}s")

    start_http_server(EXPORTER_PORT)
    print(f"[yolo-exporter] Servidor de métricas en http://0.0.0.0:{EXPORTER_PORT}/metrics")

    while True:
        try:
            data = fetch_detections()
            update_metrics(data)
        except Exception as e:
            scrape_errors.inc()
            print(f"[yolo-exporter] Error al consultar detector: {e}")

        time.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    main()
