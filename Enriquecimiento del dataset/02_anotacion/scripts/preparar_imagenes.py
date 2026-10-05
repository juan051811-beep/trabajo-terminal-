from pathlib import Path
import csv
import shutil
import sys

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

OUTPUT_DIR = Path.home() / "Desktop" / "MURA_TT_anotacion" / "imagenes"

# --------------------------------------------------
# PREPARACIÓN
# --------------------------------------------------

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

copied = 0
errors = []
expected_cases = set()

with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as file:
    reader = csv.DictReader(file)

    for row in reader:
        case_id = row["annotation_case_id"].strip()
        source_path = row["source_image_path"].strip()

        expected_cases.add(case_id)

        marker = "MURA-v1.1/"

        if marker not in source_path:
            errors.append(
                (case_id, "La ruta no contiene MURA-v1.1/")
            )
            continue

        relative_path = source_path.split(marker, 1)[1]
        local_source = MURA_ROOT / relative_path

        if not local_source.is_file():
            errors.append(
                (case_id, f"No se encontró: {local_source}")
            )
            continue

        destination = OUTPUT_DIR / f"{case_id}.png"

        try:
            shutil.copy2(local_source, destination)
            copied += 1
        except Exception as exc:
            errors.append(
                (case_id, f"Error al copiar: {exc}")
            )

# --------------------------------------------------
# VERIFICACIÓN FINAL
# --------------------------------------------------

output_files = list(OUTPUT_DIR.glob("MURA_TT_*.png"))

output_case_ids = {
    file.stem
    for file in output_files
}

missing_after_copy = expected_cases - output_case_ids
unexpected_files = output_case_ids - expected_cases

total_bytes = sum(
    file.stat().st_size
    for file in output_files
)

total_mb = total_bytes / (1024 ** 2)

print("\n========== PREPARACIÓN DE IMÁGENES ==========")
print(f"Casos esperados:          {len(expected_cases)}")
print(f"Copias realizadas:        {copied}")
print(f"Archivos en destino:      {len(output_files)}")
print(f"Errores durante la copia: {len(errors)}")
print(f"Casos faltantes:          {len(missing_after_copy)}")
print(f"Archivos inesperados:     {len(unexpected_files)}")
print(f"Tamaño total:             {total_mb:.2f} MB")
print("=============================================")

if errors:
    print("\nPrimeros errores:")
    for case_id, error in errors[:20]:
        print(f"- {case_id}: {error}")

if missing_after_copy:
    print("\nPrimeros casos faltantes:")
    for case_id in sorted(missing_after_copy)[:20]:
        print(f"- {case_id}")

if unexpected_files:
    print("\nPrimeros archivos inesperados:")
    for case_id in sorted(unexpected_files)[:20]:
        print(f"- {case_id}")

# --------------------------------------------------
# RESULTADO
# --------------------------------------------------

if (
    len(expected_cases) == 2000
    and len(output_files) == 2000
    and not errors
    and not missing_after_copy
    and not unexpected_files
):
    print(
        "\n✓ Preparación completada correctamente."
        "\n✓ Las 2,000 imágenes están listas para la etapa de anotación."
    )
else:
    print(
        "\n✗ La preparación no pasó todas las verificaciones."
        "\nRevisa los mensajes anteriores antes de continuar."
    )
    sys.exit(1)
