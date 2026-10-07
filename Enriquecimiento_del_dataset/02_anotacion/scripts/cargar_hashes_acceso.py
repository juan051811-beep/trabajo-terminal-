import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


# ============================================================
# CONFIGURACIÓN
# ============================================================

EXPECTED_SPECIALISTS = {
    "SPECIALIST_01",
    "SPECIALIST_02",
    "SPECIALIST_03",
}

BASE_DIR = Path(__file__).resolve().parents[2]

HASH_FILE = (
    BASE_DIR
    / "02_anotacion"
    / "secrets"
    / "specialist_access_hashes.txt"
)


# ============================================================
# CARGAR CREDENCIALES DE SUPABASE
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
# COMPROBAR ARCHIVO LOCAL
# ============================================================

if not HASH_FILE.exists():
    print("ERROR: no se encontró el archivo local de hashes.")
    print(HASH_FILE)
    sys.exit(1)


# ============================================================
# LEER HASHES
# ============================================================

hashes = {}

with HASH_FILE.open(
    "r",
    encoding="utf-8",
) as f:

    for line_number, line in enumerate(f, start=1):

        line = line.strip()

        if not line:
            continue

        if "=" not in line:
            print(
                f"ERROR: formato inválido en la línea "
                f"{line_number}."
            )
            sys.exit(1)

        specialist_code, access_hash = line.split(
            "=",
            1,
        )

        specialist_code = specialist_code.strip()
        access_hash = access_hash.strip()

        if specialist_code in hashes:
            print(
                f"ERROR: {specialist_code} aparece "
                "más de una vez."
            )
            sys.exit(1)

        # SHA-256 hexadecimal = 64 caracteres
        if len(access_hash) != 64:
            print(
                f"ERROR: el hash de {specialist_code} "
                "no tiene una longitud válida."
            )
            sys.exit(1)

        try:
            int(access_hash, 16)
        except ValueError:
            print(
                f"ERROR: el hash de {specialist_code} "
                "no es hexadecimal."
            )
            sys.exit(1)

        hashes[specialist_code] = access_hash.lower()


# ============================================================
# VALIDAR ESPECIALISTAS DEL ARCHIVO
# ============================================================

if set(hashes.keys()) != EXPECTED_SPECIALISTS:

    print("ERROR: los especialistas del archivo no coinciden.")

    print(
        "Esperados:",
        sorted(EXPECTED_SPECIALISTS),
    )

    print(
        "Encontrados:",
        sorted(hashes.keys()),
    )

    sys.exit(1)


if len(set(hashes.values())) != 3:
    print(
        "ERROR: los tres especialistas no tienen "
        "hashes únicos."
    )
    sys.exit(1)


print("\n========== VALIDACIÓN LOCAL ==========")
print("✓ Se encontraron exactamente 3 especialistas.")
print("✓ Los 3 hashes tienen formato SHA-256 válido.")
print("✓ Los 3 hashes son diferentes.")


# ============================================================
# COMPROBAR ESPECIALISTAS EN SUPABASE
# ============================================================

response = (
    supabase
    .table("specialists")
    .select(
        "id,"
        "specialist_code,"
        "access_code_hash"
    )
    .execute()
)

rows = response.data or []

database_specialists = {
    row["specialist_code"]: row
    for row in rows
}


if set(database_specialists.keys()) != EXPECTED_SPECIALISTS:

    print(
        "\nERROR: los especialistas existentes "
        "en Supabase no coinciden con los esperados."
    )

    print(
        "Encontrados:",
        sorted(database_specialists.keys()),
    )

    sys.exit(1)


print("✓ Los 3 especialistas existen en Supabase.")


# ============================================================
# COMPROBAR ESTADO ACTUAL
# ============================================================

existing_hashes = {
    code: row.get("access_code_hash")
    for code, row in database_specialists.items()
}


configured = [
    code
    for code, value in existing_hashes.items()
    if value
]


if configured:

    # Si ya existen hashes, solo aceptamos que sean
    # exactamente los mismos. Esto hace el script idempotente.

    mismatches = []

    for code in EXPECTED_SPECIALISTS:

        if existing_hashes[code] != hashes[code]:
            mismatches.append(code)

    if mismatches:

        print(
            "\nERROR: Supabase ya contiene hashes "
            "diferentes para uno o más especialistas."
        )

        print(
            "No se modificará ningún registro."
        )

        print(
            "Especialistas afectados:",
            ", ".join(sorted(mismatches)),
        )

        sys.exit(1)

    print(
        "\n↪ Los hashes correctos ya están "
        "configurados en Supabase."
    )

    print(
        "↪ No es necesario actualizar ningún registro."
    )

else:

    # ========================================================
    # CARGAR HASHES
    # ========================================================

    print("\n========== CARGA EN SUPABASE ==========")

    for code in sorted(EXPECTED_SPECIALISTS):

        response = (
            supabase
            .table("specialists")
            .update({
                "access_code_hash": hashes[code]
            })
            .eq(
                "specialist_code",
                code,
            )
            .execute()
        )

        updated = response.data or []

        if len(updated) != 1:

            print(
                f"\nERROR: no se pudo actualizar "
                f"correctamente {code}."
            )

            print(
                "No vuelvas a ejecutar el script "
                "hasta revisar el estado de Supabase."
            )

            sys.exit(1)

        print(
            f"✓ {code} configurado."
        )


# ============================================================
# VERIFICACIÓN FINAL
# ============================================================

response = (
    supabase
    .table("specialists")
    .select(
        "specialist_code,"
        "access_code_hash"
    )
    .execute()
)

final_rows = response.data or []

final_hashes = {
    row["specialist_code"]:
        row.get("access_code_hash")
    for row in final_rows
}


if set(final_hashes.keys()) != EXPECTED_SPECIALISTS:

    print(
        "\nERROR: la verificación final encontró "
        "especialistas inesperados."
    )
    sys.exit(1)


for code in EXPECTED_SPECIALISTS:

    if final_hashes.get(code) != hashes[code]:

        print(
            f"\nERROR: el hash almacenado para "
            f"{code} no coincide."
        )

        sys.exit(1)


if len(set(final_hashes.values())) != 3:

    print(
        "\nERROR: los hashes almacenados "
        "no son únicos."
    )

    sys.exit(1)


# ============================================================
# RESULTADO
# ============================================================

print("\n========== VERIFICACIÓN FINAL ==========")

for code in sorted(EXPECTED_SPECIALISTS):
    print(
        f"✓ {code}: código de acceso configurado"
    )

print(
    "\n✓ Los tres hashes fueron verificados "
    "correctamente en Supabase."
)

print(
    "✓ Ningún código de acceso original "
    "fue enviado a la base de datos."
)

print(
    "✓ Los especialistas ya tienen "
    "credenciales de acceso preparadas."
)
