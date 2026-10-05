from pathlib import Path
import csv

# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------

MURA_ROOT = Path.home() / "Desktop" / "MURA-v1.1"

CSV_PATH = (
    Path("Enriquecimiento del dataset")
    / "01_muestreo"
    / "sampling_final"
    / "sampling_2000_handoff.csv"
)

# --------------------------------------------------
# VERIFICACIÓN
# --------------------------------------------------

total_cases = 0
found = 0
missing = 0
total_bytes = 0

missing_cases = []

with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        total_cases += 1

        case_id = row["annotation_case_id"]
        source_path = row["source_image_path"]

        # Las rutas originales fueron generadas en Google Drive.
        # Conservamos únicamente la parte posterior a MURA-v1.1/
        marker = "MURA-v1.1/"

        if marker not in source_path:
            missing += 1
            missing_cases.append((case_id, "Ruta no contiene MURA-v1.1/"))
            continue

        relative_path = source_path.split(marker, 1)[1]
        local_path = MURA_ROOT / relative_path

        if local_path.is_file():
            found += 1
            total_bytes += local_path.stat().st_size
        else:
            missing += 1
            missing_cases.append((case_id, str(local_path)))

# --------------------------------------------------
# RESULTADOS
# --------------------------------------------------

total_mb = total_bytes / (1024 ** 2)
total_gb = total_bytes / (1024 ** 3)

print("\n========== VERIFICACIÓN DEL MUESTREO ==========")
print(f"Casos en el CSV:       {total_cases}")
print(f"Imágenes encontradas:  {found}")
print(f"Imágenes faltantes:    {missing}")
print(f"Tamaño total:          {total_mb:.2f} MB")
print(f"Tamaño total:          {total_gb:.3f} GB")
print("================================================")

if missing_cases:
    print("\nCasos con problemas:")
    for case_id, path in missing_cases[:20]:
        print(f"- {case_id}: {path}")

    if len(missing_cases) > 20:
        print(f"... y {len(missing_cases) - 20} casos adicionales.")
else:
    print("\n✓ Las 2,000 imágenes seleccionadas fueron localizadas correctamente.")
