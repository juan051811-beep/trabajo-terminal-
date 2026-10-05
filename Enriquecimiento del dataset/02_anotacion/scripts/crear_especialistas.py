import os
import sys

from dotenv import load_dotenv
from supabase import create_client


# ============================================================
# CONFIGURACIÓN
# ============================================================

SPECIALISTS = [
    {
        "specialist_code": "SPECIALIST_01",
        "display_name": "Especialista 1",
        "is_active": True,
    },
    {
        "specialist_code": "SPECIALIST_02",
        "display_name": "Especialista 2",
        "is_active": True,
    },
    {
        "specialist_code": "SPECIALIST_03",
        "display_name": "Especialista 3",
        "is_active": True,
    },
]


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
# CONSULTAR ESTADO ACTUAL
# ============================================================

expected_codes = {
    specialist["specialist_code"]
    for specialist in SPECIALISTS
}

response = (
    supabase
    .table("specialists")
    .select(
        "id,"
        "auth_user_id,"
        "specialist_code,"
        "display_name,"
        "is_active"
    )
    .execute()
)

existing_rows = response.data

existing_by_code = {
    row["specialist_code"]: row
    for row in existing_rows
}


print("\n========== ESTADO INICIAL ==========")
print(
    f"Registros actuales en specialists: "
    f"{len(existing_rows)}"
)


# ============================================================
# SEGURIDAD
# ============================================================

unexpected_codes = (
    set(existing_by_code.keys())
    - expected_codes
)

if unexpected_codes:
    print(
        "\nERROR: existen especialistas inesperados "
        "en la tabla:"
    )

    for code in sorted(unexpected_codes):
        print(f"  - {code}")

    print(
        "\nNo se realizó ninguna inserción."
    )

    sys.exit(1)


# ============================================================
# CREAR LOS QUE FALTEN
# ============================================================

created = 0
already_existing = 0

for specialist in SPECIALISTS:

    code = specialist["specialist_code"]

    if code in existing_by_code:

        already_existing += 1

        print(
            f"↪ Ya existe: {code}"
        )

        continue

    response = (
        supabase
        .table("specialists")
        .insert(specialist)
        .execute()
    )

    if len(response.data) != 1:
        print(
            f"ERROR: no se pudo verificar la creación "
            f"de {code}."
        )
        sys.exit(1)

    created += 1

    print(
        f"✓ Creado: {code}"
    )


# ============================================================
# VERIFICACIÓN FINAL
# ============================================================

response = (
    supabase
    .table("specialists")
    .select(
        "id,"
        "auth_user_id,"
        "specialist_code,"
        "display_name,"
        "is_active"
    )
    .execute()
)

final_rows = response.data

final_by_code = {
    row["specialist_code"]: row
    for row in final_rows
}


if set(final_by_code.keys()) != expected_codes:
    print(
        "\nERROR: la tabla specialists no contiene "
        "exactamente los tres códigos esperados."
    )
    sys.exit(1)


if len(final_rows) != 3:
    print(
        f"\nERROR: se esperaban 3 registros y hay "
        f"{len(final_rows)}."
    )
    sys.exit(1)


for code in sorted(expected_codes):

    row = final_by_code[code]

    if row["auth_user_id"] is not None:
        print(
            f"\nERROR: {code} ya tiene un auth_user_id "
            "asociado."
        )
        sys.exit(1)

    if row["is_active"] is not True:
        print(
            f"\nERROR: {code} no está activo."
        )
        sys.exit(1)


# ============================================================
# RESULTADO
# ============================================================

print("\n========== RESULTADO ==========")

print(f"Creados ahora:       {created}")
print(f"Ya existentes:       {already_existing}")
print(f"Total especialistas: {len(final_rows)}")

print("\nEspecialistas:")

for code in sorted(expected_codes):

    row = final_by_code[code]

    print(
        f"  {code}: "
        f"id={row['id']} | "
        f"auth_user_id=NULL | "
        f"activo={row['is_active']}"
    )


print(
    "\n✓ Los tres especialistas administrativos "
    "están preparados."
)

print(
    "✓ Todavía no se han creado cuentas de acceso."
)
