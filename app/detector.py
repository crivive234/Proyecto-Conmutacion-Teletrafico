"""
detector.py
Wrapper de YOLOv8 que captura frames desde la cámara,
ejecuta inferencia y mantiene el estado de detecciones actuales.

El estado current_detections es el puente con el chatbot:
    GET /detections  →  {"logos": ["docker", "kubernetes"], ...}
"""

import time
import threading
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

# ── Configuración ──────────────────────────────────────────────────────────────

MODEL_PATH           = Path("models/best.pt")
CONFIDENCE_THRESHOLD = 0.50   # detectar solo si confianza >= 50 %
MAX_FPS              = 15     # límite de FPS (CPU no puede con más sin lag)
VIDEO_SOURCE         = 0      # 0 = cámara USB por defecto; ruta = archivo de video

# Tiempo en segundos que un logo permanece en current_detections
# después de dejar de verse (evita parpadeos rápidos)
DETECTION_TTL = 2.0

# Colores por clase (BGR para OpenCV)
CLASS_COLORS = {
    "docker":     (255, 100,   0),
    "podman":     (0,   200, 100),
    "terraform":  (150,   0, 255),
    "qemu":       (0,   180, 255),
    "ansible":    (0,    50, 200),
    "rabbitmq":   (0,   100, 255),
    "kubernetes": (255, 180,   0),
}
DEFAULT_COLOR = (200, 200, 200)


# ─────────────────────────────────────────────────────────────────────────────
# CLASE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

class LogoDetector:
    """
    Gestiona la cámara, la inferencia YOLOv8 y el estado de detecciones.

    Uso típico:
        detector = LogoDetector()
        detector.start()

        # en el endpoint /stream:
        for frame in detector.frames():
            yield frame

        # en el endpoint /detections:
        return detector.get_detections()
    """

    def __init__(self) -> None:
        self._model: YOLO | None = None
        self._cap:   cv2.VideoCapture | None = None

        # Frame JPEG actual (bytes) — se actualiza en el hilo de captura
        self._frame_bytes: bytes = b""
        self._frame_lock  = threading.Lock()

        # Detecciones actuales: {nombre_clase: timestamp_ultima_vez_visto}
        self._seen: dict[str, float] = {}
        self._seen_lock = threading.Lock()

        # Estado general
        self._running  = False
        self._model_ok = False
        self._thread: threading.Thread | None = None

    # ── Inicialización ────────────────────────────────────────────────────────

    def start(self) -> None:
        """Carga el modelo y arranca el hilo de captura."""
        self._load_model()
        self._open_camera()
        self._running = True
        self._thread  = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        print("Detector iniciado.")

    def _load_model(self) -> None:
        if not MODEL_PATH.exists():
            print(f"Advertencia: {MODEL_PATH} no encontrado.")
            print("El stream funcionará sin detección hasta que entrenes el modelo.")
            return
        try:
            # Fix para PyTorch 2.6: permite cargar modelos ultralytics
            import torch
            from ultralytics.nn.tasks import DetectionModel
            torch.serialization.add_safe_globals([DetectionModel])

            self._model    = YOLO(str(MODEL_PATH))
            self._model_ok = True
            print(f"Modelo cargado: {MODEL_PATH}")
        except Exception as e:
            print(f"Error cargando modelo: {e}")

    def _open_camera(self) -> None:
        source = VIDEO_SOURCE
        self._cap = cv2.VideoCapture(source)
        if not self._cap.isOpened():
            raise RuntimeError(
                f"No se pudo abrir la fuente de video: {source}\n"
                "Verifica que la cámara esté conectada o que el archivo exista."
            )
        # Ajustar resolución de captura
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print(f"Cámara abierta: {source}")

    # ── Hilo de captura ───────────────────────────────────────────────────────

    def _capture_loop(self) -> None:
        """
        Hilo principal:
        1. Lee frame de la cámara.
        2. Corre inferencia si el modelo está listo.
        3. Dibuja bounding boxes.
        4. Codifica como JPEG y guarda en self._frame_bytes.
        5. Actualiza self._seen con los logos detectados.
        """
        min_interval = 1.0 / MAX_FPS

        while self._running:
            t_start = time.time()

            ok, frame = self._cap.read()
            if not ok:
                # Si es archivo de video, reiniciar al terminar
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            detected_now: list[str] = []

            if self._model_ok:
                results = self._model.predict(
                    source      = frame,
                    conf        = CONFIDENCE_THRESHOLD,
                    device      = "cpu",
                    verbose     = False,
                )
                frame, detected_now = self._draw_boxes(frame, results[0])

            self._update_seen(detected_now)
            self._encode_frame(frame)

            # Respetar MAX_FPS
            elapsed = time.time() - t_start
            wait    = min_interval - elapsed
            if wait > 0:
                time.sleep(wait)

    def _draw_boxes(self, frame: np.ndarray, result) -> tuple:
        """Dibuja bounding boxes y etiquetas sobre el frame."""
        detected: list[str] = []

        for box in result.boxes:
            cls_id     = int(box.cls[0])
            confidence = float(box.conf[0])
            name       = result.names[cls_id]
            color      = CLASS_COLORS.get(name, DEFAULT_COLOR)

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            # Rectángulo
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

            # Etiqueta con fondo sólido para legibilidad
            label = f"{name} {confidence:.0%}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
            cv2.putText(
                frame, label,
                (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1, cv2.LINE_AA,
            )

            detected.append(name)

        return frame, detected

    def _encode_frame(self, frame: np.ndarray) -> None:
        """Codifica el frame como JPEG y lo guarda thread-safe."""
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ok:
            with self._frame_lock:
                self._frame_bytes = buf.tobytes()

    def _update_seen(self, detected_now: list[str]) -> None:
        """
        Actualiza el diccionario de logos vistos con TTL.
        Un logo permanece en el estado DETECTION_TTL segundos
        después de la última vez que se detectó.
        """
        now = time.time()
        with self._seen_lock:
            for name in detected_now:
                self._seen[name] = now
            # Limpiar logos que superaron el TTL
            self._seen = {
                name: ts
                for name, ts in self._seen.items()
                if now - ts < DETECTION_TTL
            }

    # ── API pública ───────────────────────────────────────────────────────────

    def frames(self):
        """
        Generador de frames MJPEG para el endpoint /stream.

        Cada frame va envuelto en el formato multipart que
        los navegadores entienden como video continuo.
        """
        while self._running:
            with self._frame_lock:
                data = self._frame_bytes

            if data:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + data +
                    b"\r\n"
                )
            time.sleep(1.0 / MAX_FPS)

    def get_detections(self) -> dict:
        """
        Devuelve el estado actual de detecciones.
        Esto es lo que el chatbot consulta al preguntar /detections.

        Ejemplo de respuesta:
        {
            "logos": ["docker", "kubernetes"],
            "count": 2,
            "model_ready": true,
            "timestamp": 1718000000.0
        }
        """
        with self._seen_lock:
            logos = list(self._seen.keys())

        return {
            "logos":       logos,
            "count":       len(logos),
            "model_ready": self._model_ok,
            "timestamp":   time.time(),
        }

    def health(self) -> dict:
        """Estado del servicio para el endpoint /health."""
        return {
            "status":      "ok" if self._running else "stopped",
            "model_ready": self._model_ok,
            "model_path":  str(MODEL_PATH),
            "source":      str(VIDEO_SOURCE),
            "max_fps":     MAX_FPS,
        }

    def stop(self) -> None:
        """Detiene el hilo de captura y libera la cámara."""
        self._running = False
        if self._cap:
            self._cap.release()
        print("Detector detenido.")
