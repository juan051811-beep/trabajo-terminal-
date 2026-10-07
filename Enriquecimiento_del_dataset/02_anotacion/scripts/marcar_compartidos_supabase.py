import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


# ============================================================
# RUTAS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

SHARED_CSV = (
    BASE_DIR
    / "02_anotacion"
    / "database"
    / "seed"
    / "shared_cases.csv"
)


# ============================================================
# CREDENCIALES
# ============================================================

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url or not supabase_key:
    print("ERROR: faltan credenciales de Supabase en .env")
    sys.exit(1)

supabase = create_client(
    supabase_url,
    supabase_key,
)


# ============================================================
# LEER LOS 100 CASOS COMPARTIDOS
# ============================================================

if not SHARED_CSV.exists():
    print(f"ERROR: no existe:\n{SHARED_CSV}")
    sys.exit(1)

with SHARED_CSV.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as f:
    rows = list(csv.DictReader(f))

case_ids = [
    row["annotation_case_id"]
    for row in rows
]


# ============================================================
# VALIDACIONES LOCALES
# ============================================================

if len(case_ids) != 100:
    print(
        f"ERROR: shared_cases.csv contiene "
        f"{len(case_ids)} casos en vez de 100."
    )
    sys.exit(1)

if len(set(case_ids)) != 100:
    print("ERROR: hay annotation_case_id duplicados.")
    sys.exit(1)

print("\n========== VERIFICACIÓN PREVIA ==========")
print(f"Casos en shared_cases.csv: {len(case_ids)}")


# ============================================================
# COMPROBAR QUE LOS 100 EXISTEN EN SUPABASE
# ============================================================

existing_ids = set()

# Consultamos en bloques para mantener la operación sencilla.
BATCH_SIZE = 50

for start in range(0, len(case_ids), BATCH_SIZE):

    batch = case_ids[start:start + BATCH_SIZE]

    response = (
        supabase
        .table("cases")
        .select("annotation_case_id")
        .in_("annotation_case_id", batch)
        .execute()
    )

    for row in response.data:
        existing_ids.add(
            row["annotation_case_id"]
        )


missing = set(case_ids) - existing_ids

if missing:
    print("\nERROR: algunos casos no existen en Supabase:")

    for case_id in sorted(missing):
        print(f"  - {case_id}")

    sys.exit(1)


print("✓ Los 100 casos existen en Supabase.")


# ============================================================
# MARCAR COMO COMPARTIDOS
# ============================================================

updated = 0

for start in range(0, len(case_ids), BATCH_SIZE):

    batch = case_ids[start:start + BATCH_SIZE]

    response = (
        supabase
        .table("cases")
        .update({
            "is_shared": True
        })
        .in_("annotation_case_id", batch)
        .execute()
    )

    updated += len(response.data)


print(f"✓ Filas actualizadas: {updated}")


# ============================================================
# VERIFICACIÓN FINAL
# ============================================================

response = (
    supabase
    .table("cases")
    .select(
        "annotation_case_id",
        count="exact"
    )
    .eq("is_shared", True)
    .execute()
)

shared_count = response.count


print("\n========== RESULTADO ==========")
print(f"Casos compartidos en Supabase: {shared_count}")


if shared_count != 100:
    print(
        "\nERROR: Supabase no contiene exactamente "
        "100 casos compartidos."
    )
    sys.exit(1)


# Verificar además que sean exactamente los seleccionados.
response = (
    supabase
    .table("cases")
    .select("annotation_case_id")
    .eq("is_shared", True)
    .execute()
)

database_shared_ids = {
    row["annotation_case_id"]
    for row in response.data
}

expected_ids = set(case_ids)

if database_shared_ids != expected_ids:

    unexpected = database_shared_ids - expected_ids
    absent = expected_ids - database_shared_ids

    print("\nERROR: los casos compartidos no coinciden.")

    if unexpected:
        print("\nCompartidos inesperados:")
        for case_id in sorted(unexpected):
            print(f"  - {case_id}")

    if absent:
        print("\nCompartidos faltantes:")
        for case_id in sorted(absent):
            print(f"  - {case_id}")

    sys.exit(1)


print("✓ Los 100 casos coinciden exactamente con la selección.")
print("✓ Actualización completada correctamente.")
