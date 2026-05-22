"""
train.py
Entrena YOLOv8 con el dataset sintético de logos DevOps.

Uso:
    python scripts/train.py
    python scripts/train.py --epochs 60 --batch 8

Requisito previo:
    Haber corrido generate_dataset.py para tener dataset/ con data.yaml.

El modelo entrenado queda en:
    models/best.pt
"""

import shutil
import argparse
from pathlib import Path

from ultralytics import YOLO

# ── Rutas ──────────────────────────────────────────────────────────────────────

ROOT       = Path(__file__).parent.parent
DATASET    = ROOT / "dataset" / "data.yaml"
MODELS_DIR = ROOT / "models"
RUNS_DIR   = ROOT / "runs"

# ── Configuración de entrenamiento ─────────────────────────────────────────────

CONFIG = {
    # Modelo base — yolov8n es el más ligero, ideal para CPU
    # Opciones: yolov8n, yolov8s, yolov8m (más precisión, más lento)
    "model":   "yolov8n.pt",

    # Épocas — con dataset sintético de ~560 imágenes, 50 épocas es un buen inicio
    "epochs":  50,

    # Imágenes por batch — en CPU sin GPU dedicada, 4 u 8 es lo recomendable
    "batch":   4,

    # Resolución de entrada — debe coincidir con img_size en generate_dataset.py
    "imgsz":   640,

    # Dispositivo: "cpu" siempre para tu setup (Intel integrado)
    "device":  "cpu",

    # Nombre del experimento (se guarda en runs/)
    "name":    "devops_logos",

    # Paciencia para early stopping
    # Si no mejora en N épocas, para el entrenamiento
    "patience": 15,

    # Augmentaciones de YOLOv8 — habilitadas por defecto, ayudan mucho
    # con datasets pequeños como el nuestro
    "flipud":  0.3,   # probabilidad de flip vertical
    "fliplr":  0.5,   # probabilidad de flip horizontal
    "degrees": 10.0,  # rotación máxima adicional durante entrenamiento
    "scale":   0.3,   # variación de escala
    "mosaic":  0.8,   # mezcla de 4 imágenes (muy útil con pocos datos)
}


# ─────────────────────────────────────────────────────────────────────────────
# VALIDACIONES PREVIAS
# ─────────────────────────────────────────────────────────────────────────────

def check_prerequisites() -> bool:
    """Verifica que el dataset exista antes de entrenar."""
    if not DATASET.exists():
        print("Error: no se encontró dataset/data.yaml")
        print("Corre primero: python scripts/generate_dataset.py")
        return False

    train_images = ROOT / "dataset" / "images" / "train"
    if not train_images.exists() or not any(train_images.iterdir()):
        print("Error: dataset/images/train/ está vacío")
        print("Corre primero: python scripts/generate_dataset.py")
        return False

    n_train = len(list(train_images.glob("*.jpg")))
    n_val   = len(list((ROOT / "dataset" / "images" / "val").glob("*.jpg")))
    print(f"  ✓  Dataset encontrado: {n_train} train / {n_val} val")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# ENTRENAMIENTO
# ─────────────────────────────────────────────────────────────────────────────

def train() -> None:
    print("Cargando modelo base YOLOv8...")
    model = YOLO(CONFIG["model"])

    print(f"\nIniciando entrenamiento — {CONFIG['epochs']} épocas en {CONFIG['device']}")
    print(f"Batch: {CONFIG['batch']}  |  Resolución: {CONFIG['imgsz']}px\n")

    results = model.train(
        data      = str(DATASET),
        epochs    = CONFIG["epochs"],
        batch     = CONFIG["batch"],
        imgsz     = CONFIG["imgsz"],
        device    = CONFIG["device"],
        project   = str(RUNS_DIR),
        name      = CONFIG["name"],
        patience  = CONFIG["patience"],

        # Augmentaciones
        flipud    = CONFIG["flipud"],
        fliplr    = CONFIG["fliplr"],
        degrees   = CONFIG["degrees"],
        scale     = CONFIG["scale"],
        mosaic    = CONFIG["mosaic"],

        # Sin interfaz gráfica (headless)
        plots     = True,
        verbose   = True,
    )

    return results


# ─────────────────────────────────────────────────────────────────────────────
# COPIAR MODELO A models/best.pt
# ─────────────────────────────────────────────────────────────────────────────

def copy_best_model() -> None:
    """
    YOLOv8 guarda el mejor modelo en runs/devops_logos/weights/best.pt.
    Lo copiamos a models/best.pt que es donde el detector lo espera.
    """
    # Buscar el último run si hay varios (por si se reentrenó antes)
    run_dirs = sorted(RUNS_DIR.glob(f"{CONFIG['name']}*"))
    if not run_dirs:
        print("No se encontró carpeta de runs. Algo salió mal.")
        return

    best_src = run_dirs[-1] / "weights" / "best.pt"
    if not best_src.exists():
        print(f"No se encontró best.pt en {best_src}")
        return

    MODELS_DIR.mkdir(exist_ok=True)
    best_dst = MODELS_DIR / "best.pt"
    shutil.copy2(best_src, best_dst)
    print(f"\n✓ Modelo copiado a: {best_dst}")


# ─────────────────────────────────────────────────────────────────────────────
# MÉTRICAS FINALES
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(results) -> None:
    """Muestra las métricas principales al finalizar."""
    try:
        metrics = results.results_dict
        print("\n── Resumen del entrenamiento ─────────────────────")
        print(f"  mAP50:      {metrics.get('metrics/mAP50(B)', 0):.3f}")
        print(f"  mAP50-95:   {metrics.get('metrics/mAP50-95(B)', 0):.3f}")
        print(f"  Precisión:  {metrics.get('metrics/precision(B)', 0):.3f}")
        print(f"  Recall:     {metrics.get('metrics/recall(B)', 0):.3f}")
        print("──────────────────────────────────────────────────")
        print("\nValores de referencia:")
        print("  mAP50 > 0.85 → modelo listo para producción")
        print("  mAP50 > 0.70 → aceptable para demo")
        print("  mAP50 < 0.60 → necesita más imágenes o épocas")
    except Exception:
        print("(métricas no disponibles — revisa runs/devops_logos/results.csv)")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entrenamiento YOLOv8 para logos DevOps")
    parser.add_argument("--epochs",  type=int, default=CONFIG["epochs"],
                        help=f"Épocas de entrenamiento (default: {CONFIG['epochs']})")
    parser.add_argument("--batch",   type=int, default=CONFIG["batch"],
                        help=f"Tamaño de batch (default: {CONFIG['batch']})")
    parser.add_argument("--model",   type=str, default=CONFIG["model"],
                        help="Modelo base (default: yolov8n.pt)")
    args = parser.parse_args()

    CONFIG["epochs"] = args.epochs
    CONFIG["batch"]  = args.batch
    CONFIG["model"]  = args.model

    print("── Entrenamiento de logos DevOps con YOLOv8 ──────────\n")

    if not check_prerequisites():
        exit(1)

    results = train()
    copy_best_model()
    print_summary(results)

    print("\nSiguiente paso:")
    print("  Copia models/best.pt al contenedor detector y reinícialo:")
    print("  docker compose restart detector")
