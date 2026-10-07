import os
import sys

from dotenv import load_dotenv
from supabase import create_client


# --------------------------------------------------
# CARGAR VARIABLES DE ENTORNO
# --------------------------------------------------

load_dotenv()

supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not supabase_url:
    print("ERROR: No se encontró SUPABASE_URL en .env")
    sys.exit(1)

if not supabase_key:
    print("ERROR: No se encontró SUPABASE_SERVICE_ROLE_KEY en .env")
    sys.exit(1)


# --------------------------------------------------
# CONEXIÓN
# --------------------------------------------------

try:
    supabase = create_client(
        supabase_url,
        supabase_key
    )

    print("✓ Cliente de Supabase creado correctamente.")

except Exception as exc:
    print(f"ERROR al crear el cliente de Supabase: {exc}")
    sys.exit(1)


# --------------------------------------------------
# PRUEBA DE LECTURA
# --------------------------------------------------

try:
    response = (
        supabase
        .table("cases")
        .select("annotation_case_id", count="exact")
        .limit(1)
        .execute()
    )

    print("✓ Conexión con PostgreSQL correcta.")
    print(f"✓ Registros encontrados en cases: {response.count}")

except Exception as exc:
    print("ERROR al consultar la tabla cases.")
    print(f"Detalle: {exc}")
    sys.exit(1)


# --------------------------------------------------
# VALIDACIÓN
# --------------------------------------------------

if response.count == 2000:
    print("\n✓ PRUEBA SUPERADA.")
    print("✓ Supabase contiene los 2,000 casos esperados.")
else:
    print("\nADVERTENCIA:")
    print(
        f"Se esperaban 2000 casos, "
        f"pero Supabase reportó {response.count}."
    )
    sys.exit(1)
