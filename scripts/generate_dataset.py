"""
generate_dataset.py
Genera un dataset sintético de logos DevOps para entrenar YOLOv8.

Uso:
    python scripts/generate_dataset.py
    python scripts/generate_dataset.py --images 120 --size 640

Estructura esperada antes de correr:
    logos/
        docker.png        ← PNG con fondo transparente
        podman.png
        terraform.png
        qemu.png
        ansible.png
        jenkins.png
        kubernetes.png
    backgrounds/          ← opcional: JPG/PNG de fondos reales
"""

import random
import argparse
from pathlib import Path

import yaml
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw

# ── Clases del modelo (orden = class_id en YOLO) ──────────────────────────────

CLASSES = [
    "docker",       # 0
    "podman",       # 1
    "terraform",    # 2
    "qemu",         # 3
    "ansible",      # 4
    "jenkins",     # 5
    "kubernetes",   # 6
]

# ── Configuración general ──────────────────────────────────────────────────────

CONFIG = {
    "images_per_logo":    80,    # imágenes generadas por cada logo
    "val_split":          0.15,  # fracción destinada a validación
    "img_size":           640,   # resolución de salida en píxeles (cuadrada)
    "logo_scale_min":     0.15,  # escala mínima del logo relativa a la imagen
    "logo_scale_max":     0.55,  # escala máxima
    "rotation_max":       15,    # rotación máxima en grados (± este valor)
    "logos_per_image":    2,     # cuántos logos caben en una sola imagen (máx)
}

# ── Rutas ──────────────────────────────────────────────────────────────────────

ROOT         = Path(__file__).parent.parent
LOGOS_DIR    = ROOT / "logos"
BACKGROUNDS_DIR = ROOT / "backgrounds"
DATASET_DIR  = ROOT / "dataset"


# ─────────────────────────────────────────────────────────────────────────────
# FONDOS SINTÉTICOS
# Se usan cuando no hay imágenes en backgrounds/ o por azar (50 % del tiempo).
# ─────────────────────────────────────────────────────────────────────────────

def _solid(size: int) -> Image.Image:
    """Color sólido aleatorio."""
    color = tuple(random.randint(20, 240) for _ in range(3))
    return Image.new("RGB", (size, size), color)


def _gradient(size: int) -> Image.Image:
    """Gradiente lineal entre dos colores aleatorios."""
    c1 = tuple(random.randint(0, 200) for _ in range(3))
    c2 = tuple(random.randint(50, 255) for _ in range(3))
    vertical = random.choice([True, False])
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    for i in range(size):
        t = i / size
        blended = tuple(int(c1[j] * (1 - t) + c2[j] * t) for j in range(3))
        if vertical:
            arr[i, :] = blended
        else:
            arr[:, i] = blended
    return Image.fromarray(arr, "RGB")


def _noise(size: int) -> Image.Image:
    """Ruido tipo 'pizarrón oscuro' (simula fondo de terminal o slide)."""
    base = random.randint(20, 70)
    arr = np.random.randint(base, base + 40, (size, size, 3), dtype=np.uint8)
    return Image.fromarray(arr, "RGB")


def _grid(size: int) -> Image.Image:
    """Cuadrícula sobre fondo claro (simula pantalla de presentación)."""
    bg = tuple(random.randint(200, 255) for _ in range(3))
    line = tuple(random.randint(150, 195) for _ in range(3))
    img = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(img)
    step = random.choice([40, 60, 80])
    for x in range(0, size, step):
        draw.line([(x, 0), (x, size)], fill=line, width=1)
    for y in range(0, size, step):
        draw.line([(0, y), (size, y)], fill=line, width=1)
    return img


def get_background(size: int) -> Image.Image:
    """
    Devuelve un fondo RGB de (size x size).
    - Si hay archivos en backgrounds/ los usa el 50 % de las veces.
    - El otro 50 % (o si no hay) usa un fondo sintético aleatorio.
    """
    bg_files = []
    if BACKGROUNDS_DIR.exists():
        bg_files = list(BACKGROUNDS_DIR.glob("*.jpg")) + list(BACKGROUNDS_DIR.glob("*.png"))

    if bg_files and random.random() < 0.5:
        path = random.choice(bg_files)
        img = Image.open(path).convert("RGB")
        w, h = img.size
        side = min(w, h)
        x0, y0 = random.randint(0, w - side), random.randint(0, h - side)
        return img.crop((x0, y0, x0 + side, y0 + side)).resize((size, size), Image.LANCZOS)

    return random.choice([_solid, _gradient, _noise, _grid])(size)


# ─────────────────────────────────────────────────────────────────────────────
# COLOCACIÓN DEL LOGO
# ─────────────────────────────────────────────────────────────────────────────

def paste_logo(
    background: Image.Image,
    logo: Image.Image,
    class_id: int,
    existing_boxes: list,
) -> tuple | None:
    """
    Pega el logo sobre el fondo en una posición aleatoria libre.

    Devuelve (imagen_actualizada, anotación_yolo) o None si no
    encontró posición sin solapamiento tras 20 intentos.

    Anotación YOLO: (class_id, cx, cy, w, h) — todos normalizados [0, 1].
    """
    bg_size = background.size[0]

    # Tamaño del logo escalado
    scale = random.uniform(CONFIG["logo_scale_min"], CONFIG["logo_scale_max"])
    logo_px = max(32, int(bg_size * scale))

    # Rotación
    angle = random.uniform(-CONFIG["rotation_max"], CONFIG["rotation_max"])

    logo_r = logo.resize((logo_px, logo_px), Image.LANCZOS)
    if abs(angle) > 1:
        logo_r = logo_r.rotate(angle, expand=True, resample=Image.BICUBIC)

    lw, lh = logo_r.size
    margin = 10
    max_x, max_y = bg_size - lw - margin, bg_size - lh - margin

    if max_x < margin or max_y < margin:
        return None  # logo demasiado grande para el fondo

    for _ in range(20):
        x = random.randint(margin, max_x)
        y = random.randint(margin, max_y)

        cx = (x + lw / 2) / bg_size
        cy = (y + lh / 2) / bg_size
        nw = lw / bg_size
        nh = lh / bg_size

        # Verificar solapamiento con cajas ya colocadas
        overlaps = any(
            abs(cx - ex) < (nw + ew) / 2 and abs(cy - ey) < (nh + eh) / 2
            for (_, ex, ey, ew, eh) in existing_boxes
        )
        if overlaps:
            continue

        # Pegar (usa canal alpha si existe)
        mask = logo_r.split()[3] if logo_r.mode == "RGBA" else None
        background.paste(logo_r, (x, y), mask)

        annotation = (class_id, cx, cy, nw, nh)
        existing_boxes.append(annotation)
        return background, annotation

    return None  # no se encontró posición libre


# ─────────────────────────────────────────────────────────────────────────────
# AUGMENTACIONES DE IMAGEN
# ─────────────────────────────────────────────────────────────────────────────

def augment(img: Image.Image) -> Image.Image:
    """
    Aplica modificaciones aleatorias a la imagen ya compuesta.
    Simula condiciones reales: brillo variable, contraste, blur de cámara.
    """
    if random.random() < 0.5:
        img = ImageEnhance.Brightness(img).enhance(random.uniform(0.6, 1.4))
    if random.random() < 0.4:
        img = ImageEnhance.Contrast(img).enhance(random.uniform(0.7, 1.3))
    if random.random() < 0.2:
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.5, 1.5)))
    return img


# ─────────────────────────────────────────────────────────────────────────────
# GENERACIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def generate_dataset() -> None:
    # Crear carpetas de salida
    for split in ("train", "val"):
        (DATASET_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (DATASET_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    # Cargar logos disponibles
    logos: dict[int, Image.Image] = {}
    for class_id, name in enumerate(CLASSES):
        path = LOGOS_DIR / f"{name}.png"
        if not path.exists():
            print(f"  ⚠  {name}.png no encontrado — se omite")
            continue
        logos[class_id] = Image.open(path).convert("RGBA")
        print(f"  ✓  {name}.png cargado")

    if not logos:
        print("\nError: no hay logos en logos/")
        print("Agrega archivos PNG con fondo transparente y vuelve a correr el script.")
        return

    size      = CONFIG["img_size"]
    n_imgs    = CONFIG["images_per_logo"]
    val_split = CONFIG["val_split"]
    total     = 0

    for class_id, logo in logos.items():
        name = CLASSES[class_id]

        for i in range(n_imgs):
            split = "val" if i < int(n_imgs * val_split) else "train"

            bg          = get_background(size)
            annotations = []

            # Pegar entre 1 y logos_per_image logos del mismo tipo
            n_paste = random.randint(1, CONFIG["logos_per_image"])
            for _ in range(n_paste):
                result = paste_logo(bg, logo, class_id, annotations)
                if result is None:
                    break
                bg, _ = result

            if not annotations:
                continue  # si no se pudo colocar ninguno, descartar imagen

            bg = augment(bg)

            # Guardar imagen
            img_name = f"{name}_{i:04d}.jpg"
            bg.save(DATASET_DIR / "images" / split / img_name, quality=90)

            # Guardar anotaciones en formato YOLO
            label_name = f"{name}_{i:04d}.txt"
            with open(DATASET_DIR / "labels" / split / label_name, "w") as f:
                for cid, cx, cy, w, h in annotations:
                    f.write(f"{cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

            total += 1

        print(f"  {name}: {n_imgs} imágenes generadas")

    # Generar data.yaml para YOLOv8
    data_yaml = {
        "path":  str(DATASET_DIR.resolve()),
        "train": "images/train",
        "val":   "images/val",
        "nc":    len(CLASSES),
        "names": CLASSES,
    }
    with open(DATASET_DIR / "data.yaml", "w") as f:
        yaml.dump(data_yaml, f, default_flow_style=False, allow_unicode=True)

    print(f"\n✓ Dataset listo: {total} imágenes en {DATASET_DIR}")
    print("✓ data.yaml generado — ya puedes entrenar con:")
    print("  python scripts/train.py")


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generador de dataset sintético para logos DevOps")
    parser.add_argument("--images", type=int, default=CONFIG["images_per_logo"],
                        help="Imágenes por logo (default: 80)")
    parser.add_argument("--size",   type=int, default=CONFIG["img_size"],
                        help="Resolución de salida en píxeles (default: 640)")
    args = parser.parse_args()

    CONFIG["images_per_logo"] = args.images
    CONFIG["img_size"]        = args.size

    print("Generando dataset sintético de logos DevOps...\n")
    generate_dataset()
