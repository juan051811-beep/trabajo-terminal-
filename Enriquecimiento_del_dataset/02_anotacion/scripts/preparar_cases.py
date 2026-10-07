from pathlib import Path
import csv
import sys

# --------------------------------------------------
# RUTAS
# --------------------------------------------------

INPUT_CSV = (
    Path("Enriquecimiento del dataset")
    / "01_muestreo"
    / "sampling_final"
    / "sampling_2000_handoff.csv"
)

OUTPUT_DIR = (
    Path("Enriquecimiento del dataset")
    / "02_anotacion"
    / "database"
    / "seed"
)

OUTPUT_CSV = OUTPUT_DIR / "cases.csv"

# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------

VALID_REGIONS = {
    "XR_ELBOW",
    "XR_FINGER",
    "XR_FOREARM",
    "XR_HAND",
    "XR_HUMERUS",
    "XR_SHOULDER",
    "XR_WRIST",
}

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# GENERACIÓN
# --------------------------------------------------

cases = []
case_ids = set()
errors = []

with INPUT_CSV.open("r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    for row_number, row in enumerate(reader, start=2):

        case_id = row["annotation_case_id"].strip()
        region = row["region"].strip()

        # Validar identificador.
        if not case_id:
            errors.append(
                f"Fila {row_number}: annotation_case_id vacío."
            )
            continue

        if case_id in case_ids:
            errors.append(
                f"Fila {row_number}: caso duplicado {case_id}."
            )
            continue

        # Validar región anatómica.
        if region not in VALID_REGIONS:
            errors.append(
                f"Fila {row_number}: región inválida {region}."
            )
            continue

        image_filename = f"{case_id}.png"

        # Al estar los PNG directamente en la raíz del bucket,
        # storage_path coincide con image_filename.
        storage_path = image_filename

        cases.append(
            {
                "annotation_case_id": case_id,
                "region": region,
                "image_filename": image_filename,
                "storage_path": storage_path,
                "is_shared": "false",
            }
        )

        case_ids.add(case_id)

# --------------------------------------------------
# VALIDACIONES
# --------------------------------------------------

if errors:
    print("\nSe encontraron errores:")
    for error in errors[:20]:
        print(f"- {error}")

    if len(errors) > 20:
        print(f"... y {len(errors) - 20} errores adicionales.")

    sys.exit(1)

if len(cases) != 2000:
    print(
        f"\nERROR: se esperaban 2000 casos, "
        f"pero se obtuvieron {len(cases)}."
    )
    sys.exit(1)

# --------------------------------------------------
# ESCRIBIR CSV
# --------------------------------------------------

fieldnames = [
    "annotation_case_id",
    "region",
    "image_filename",
    "storage_path",
    "is_shared",
]

with OUTPUT_CSV.open("w", encoding="utf-8", newline="") as file:
    writer = csv.DictWriter(
        file,
        fieldnames=fieldnames
    )

    writer.writeheader()
    writer.writerows(cases)

# --------------------------------------------------
# RESUMEN
# --------------------------------------------------

region_counts = {}

for case in cases:
    region = case["region"]
    region_counts[region] = region_counts.get(region, 0) + 1

print("\n========== PREPARACIÓN DE CASES ==========")
print(f"Casos generados: {len(cases)}")
print(f"Casos únicos:    {len(case_ids)}")
print(f"Archivo:         {OUTPUT_CSV}")
print("==========================================")

print("\nDistribución por región:")

for region in sorted(region_counts):
    print(f"- {region}: {region_counts[region]}")

print(
    "\n✓ cases.csv generado correctamente."
    "\n✓ Todos los casos permanecen inicialmente "
    "con is_shared = false."
)
