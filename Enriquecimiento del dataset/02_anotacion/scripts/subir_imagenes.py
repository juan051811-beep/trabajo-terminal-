import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


# --------------------------------------------------
# CONFIGURACIÓN
# --------------------------------------------------

BUCKET_NAME = "mura-radiographs"

IMAGES_DIR = (
    Path.home()
    / "Desktop"
    / "MURA_TT_anotacion"
    / "imagenes"
)

EXPECTED_IMAGES = 2000


# --------------------------------------------------
# ARGUMENTOS
# --------------------------------------------------

parser = argparse.ArgumentParser(
    description="Carga las radiografías seleccionadas a Supabase Storage."
)

parser.add_argument(
    "--test",
    action="store_true",
    help="Sube únicamente MURA_TT_0001.png."
)

args = parser.parse_args()


# --------------------------------------------------
# CREDENCIALES
# --------------------------------------------------

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    print("ERROR: faltan credenciales de Supabase en .env")
    sys.exit(1)

supabase = create_client(
    supabase_url,
    supabase_key
)


# --------------------------------------------------
# VERIFICAR CARPETA LOCAL
# --------------------------------------------------

if not IMAGES_DIR.is_dir():
    print(f"ERROR: no existe la carpeta {IMAGES_DIR}")
    sys.exit(1)

all_images = sorted(
    IMAGES_DIR.glob("MURA_TT_*.png")
)

if len(all_images) != EXPECTED_IMAGES:
    print(
        f"ERROR: se esperaban {EXPECTED_IMAGES} imágenes, "
        f"pero se encontraron {len(all_images)}."
    )
    sys.exit(1)


# --------------------------------------------------
# SELECCIONAR ARCHIVOS
# --------------------------------------------------

if args.test:
    images_to_process = [
        IMAGES_DIR / "MURA_TT_0001.png"
    ]

    print("\nMODO DE PRUEBA")
    print("Se procesará únicamente MURA_TT_0001.png.")
else:
    images_to_process = all_images

    print("\nMODO DE CARGA COMPLETA")
    print(f"Imágenes a revisar: {len(images_to_process)}")


# --------------------------------------------------
# CARGA
# --------------------------------------------------

uploaded = 0
already_exists = 0
errors = []

for index, image_path in enumerate(images_to_process, start=1):

    storage_path = image_path.name

    try:
        with image_path.open("rb") as file:
            supabase.storage.from_(BUCKET_NAME).upload(
                path=storage_path,
                file=file,
                file_options={
                    "content-type": "image/png",
                    "upsert": "false",
                },
            )

        uploaded += 1

        print(
            f"[{index}/{len(images_to_process)}] "
            f"✓ {storage_path}"
        )

    except Exception as exc:

        error_text = str(exc)

        # Si el archivo ya existe, no lo sobrescribimos.
        if (
            "Duplicate" in error_text
            or "already exists" in error_text.lower()
            or "409" in error_text
        ):
            already_exists += 1

            print(
                f"[{index}/{len(images_to_process)}] "
                f"↪ Ya existe: {storage_path}"
            )

        else:
            errors.append(
                (storage_path, error_text)
            )

            print(
                f"[{index}/{len(images_to_process)}] "
                f"✗ Error: {storage_path}"
            )


# --------------------------------------------------
# RESUMEN
# --------------------------------------------------

print("\n========== RESULTADO DE STORAGE ==========")
print(f"Procesadas:        {len(images_to_process)}")
print(f"Subidas:           {uploaded}")
print(f"Ya existentes:     {already_exists}")
print(f"Errores:           {len(errors)}")
print("==========================================")

if errors:
    print("\nErrores encontrados:")

    for filename, error in errors[:10]:
        print(f"\n- {filename}")
        print(f"  {error}")

    sys.exit(1)

if args.test:
    print(
        "\n✓ Prueba de carga completada."
        "\nRevisa Storage antes de realizar la carga completa."
    )
else:
    print(
        "\n✓ Proceso de carga completado sin errores."
    )
