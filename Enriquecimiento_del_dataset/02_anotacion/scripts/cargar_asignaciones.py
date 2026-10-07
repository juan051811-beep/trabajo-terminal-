import csv
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


# ============================================================
# CONFIGURACIÓN
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

PLAN_CSV = (
    BASE_DIR
    / "02_anotacion"
    / "database"
    / "seed"
    / "assignments_plan.csv"
)

EXPECTED_TOTAL = 2200
EXPECTED_CASES = 2000
EXPECTED_SHARED_CASES = 100
EXPECTED_EXCLUSIVE_CASES = 1900

EXPECTED_BY_SPECIALIST = {
    "SPECIALIST_01": 734,
    "SPECIALIST_02": 733,
    "SPECIALIST_03": 733,
}

INSERT_BATCH_SIZE = 100
PAGE_SIZE = 1000


# ============================================================
# FUNCIONES
# ============================================================

def fetch_all_rows(
    table_name,
    columns,
    order_column="id",
    page_size=PAGE_SIZE,
):
    """
    Recupera todas las filas de una tabla usando paginación.
    Evita el límite de 1000 registros por consulta.
    """

    rows = []
    offset = 0

    while True:

        start = offset
        end = offset + page_size - 1

        response = (
            supabase
            .table(table_name)
            .select(columns)
            .order(order_column)
            .range(start, end)
            .execute()
        )

        batch = response.data or []

        if not batch:
            break

        rows.extend(batch)

        if len(batch) < page_size:
            break

        offset += page_size

    return rows


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
# LEER PLAN
# ============================================================

if not PLAN_CSV.exists():
    print(f"ERROR: no existe:\n{PLAN_CSV}")
    sys.exit(1)

with PLAN_CSV.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as f:
    plan = list(csv.DictReader(f))


print("\n========== VALIDACIÓN DEL PLAN ==========")
print(f"Filas encontradas: {len(plan)}")


if len(plan) != EXPECTED_TOTAL:
    print(
        f"ERROR: se esperaban {EXPECTED_TOTAL} "
        f"asignaciones."
    )
    sys.exit(1)


if not plan:
    print("ERROR: el plan está vacío.")
    sys.exit(1)


required_columns = {
    "specialist_code",
    "annotation_case_id",
    "assignment_type",
    "presentation_order",
}

missing_columns = required_columns - set(plan[0].keys())

if missing_columns:
    print(
        f"ERROR: faltan columnas: "
        f"{sorted(missing_columns)}"
    )
    sys.exit(1)


# ============================================================
# VALIDAR CARGA POR ESPECIALISTA
# ============================================================

plan_counts = Counter(
    row["specialist_code"]
    for row in plan
)

for code, expected in EXPECTED_BY_SPECIALIST.items():

    obtained = plan_counts[code]

    if obtained != expected:
        print(
            f"ERROR: {code} tiene {obtained} "
            f"asignaciones; se esperaban {expected}."
        )
        sys.exit(1)


unexpected_specialists = (
    set(plan_counts)
    - set(EXPECTED_BY_SPECIALIST)
)

if unexpected_specialists:
    print(
        f"ERROR: especialistas inesperados: "
        f"{sorted(unexpected_specialists)}"
    )
    sys.exit(1)


# ============================================================
# VALIDAR DUPLICADOS ESPECIALISTA/CASO
# ============================================================

pairs = [
    (
        row["specialist_code"],
        row["annotation_case_id"],
    )
    for row in plan
]

if len(set(pairs)) != EXPECTED_TOTAL:
    print(
        "ERROR: existen pares especialista/caso "
        "duplicados."
    )
    sys.exit(1)


# ============================================================
# VALIDAR PRESENTATION_ORDER
# ============================================================

for code, expected_total in EXPECTED_BY_SPECIALIST.items():

    try:
        orders = sorted(
            int(row["presentation_order"])
            for row in plan
            if row["specialist_code"] == code
        )

    except ValueError:
        print(
            f"ERROR: presentation_order contiene "
            f"valores no numéricos para {code}."
        )
        sys.exit(1)

    expected_orders = list(
        range(1, expected_total + 1)
    )

    if orders != expected_orders:
        print(
            f"ERROR: presentation_order incorrecto "
            f"para {code}."
        )
        sys.exit(1)


# ============================================================
# VALIDAR SHARED Y EXCLUSIVE
# ============================================================

valid_assignment_types = {
    "SHARED",
    "EXCLUSIVE",
}

found_assignment_types = {
    row["assignment_type"]
    for row in plan
}

unexpected_types = (
    found_assignment_types
    - valid_assignment_types
)

if unexpected_types:
    print(
        f"ERROR: assignment_type inesperados: "
        f"{sorted(unexpected_types)}"
    )
    sys.exit(1)


shared_rows = [
    row
    for row in plan
    if row["assignment_type"] == "SHARED"
]

exclusive_rows = [
    row
    for row in plan
    if row["assignment_type"] == "EXCLUSIVE"
]


if len(shared_rows) != 300:
    print(
        f"ERROR: se esperaban 300 filas SHARED "
        f"y hay {len(shared_rows)}."
    )
    sys.exit(1)


if len(exclusive_rows) != EXPECTED_EXCLUSIVE_CASES:
    print(
        f"ERROR: se esperaban "
        f"{EXPECTED_EXCLUSIVE_CASES} filas EXCLUSIVE "
        f"y hay {len(exclusive_rows)}."
    )
    sys.exit(1)


shared_case_counts = Counter(
    row["annotation_case_id"]
    for row in shared_rows
)


if len(shared_case_counts) != EXPECTED_SHARED_CASES:
    print(
        f"ERROR: se esperaban "
        f"{EXPECTED_SHARED_CASES} casos compartidos únicos."
    )
    sys.exit(1)


if any(
    count != 3
    for count in shared_case_counts.values()
):
    print(
        "ERROR: algún caso compartido no aparece "
        "exactamente tres veces."
    )
    sys.exit(1)


exclusive_ids = [
    row["annotation_case_id"]
    for row in exclusive_rows
]


if len(set(exclusive_ids)) != EXPECTED_EXCLUSIVE_CASES:
    print(
        "ERROR: hay duplicación entre los casos "
        "exclusivos."
    )
    sys.exit(1)


# Ningún caso exclusivo debe estar también en shared.

if set(exclusive_ids) & set(shared_case_counts):
    print(
        "ERROR: existen casos marcados simultáneamente "
        "como SHARED y EXCLUSIVE."
    )
    sys.exit(1)


plan_case_ids = {
    row["annotation_case_id"]
    for row in plan
}


if len(plan_case_ids) != EXPECTED_CASES:
    print(
        f"ERROR: el plan contiene "
        f"{len(plan_case_ids)} casos únicos "
        f"en vez de {EXPECTED_CASES}."
    )
    sys.exit(1)


print("✓ Plan local válido.")
print("✓ 1900 asignaciones exclusivas.")
print("✓ 100 casos compartidos × 3 especialistas.")
print("✓ 2000 casos únicos cubiertos por el plan.")


# ============================================================
# OBTENER ESPECIALISTAS
# ============================================================

response = (
    supabase
    .table("specialists")
    .select("id,specialist_code")
    .execute()
)

specialists = {
    row["specialist_code"]: row["id"]
    for row in response.data
}


if set(specialists) != set(EXPECTED_BY_SPECIALIST):
    print(
        "\nERROR: los especialistas de Supabase "
        "no coinciden con los esperados."
    )
    print(
        f"Encontrados: {sorted(specialists)}"
    )
    sys.exit(1)


print("✓ Especialistas encontrados en Supabase.")


# ============================================================
# OBTENER LOS 2000 CASOS CON PAGINACIÓN
# ============================================================

print("\n========== CARGA DE CASOS ==========")

all_case_rows = []
offset = 0

while True:

    start = offset
    end = offset + PAGE_SIZE - 1

    response = (
        supabase
        .table("cases")
        .select("id,annotation_case_id")
        .order("id")
        .range(start, end)
        .execute()
    )

    batch = response.data or []

    if not batch:
        break

    all_case_rows.extend(batch)

    print(
        f"✓ Recuperados {len(all_case_rows)} casos"
    )

    if len(batch) < PAGE_SIZE:
        break

    offset += PAGE_SIZE


if len(all_case_rows) != EXPECTED_CASES:
    print(
        f"\nERROR: se esperaban {EXPECTED_CASES} casos "
        f"y se recuperaron {len(all_case_rows)}."
    )
    sys.exit(1)


cases = {
    row["annotation_case_id"]: row["id"]
    for row in all_case_rows
}


if len(cases) != EXPECTED_CASES:
    print(
        f"\nERROR: existen annotation_case_id "
        f"duplicados. Casos únicos: {len(cases)}."
    )
    sys.exit(1)


missing_cases = (
    plan_case_ids
    - set(cases.keys())
)

if missing_cases:

    print(
        "\nERROR: faltan casos del plan en Supabase:"
    )

    for case_id in sorted(missing_cases):
        print(f"  - {case_id}")

    sys.exit(1)


unexpected_cases = (
    set(cases.keys())
    - plan_case_ids
)

if unexpected_cases:

    print(
        "\nERROR: existen casos en Supabase "
        "que no aparecen en el plan:"
    )

    for case_id in sorted(unexpected_cases):
        print(f"  - {case_id}")

    sys.exit(1)


print("✓ Se recuperaron los 2000 casos de Supabase.")
print("✓ Los 2000 annotation_case_id son únicos.")
print("✓ Los 2000 casos coinciden exactamente con el plan.")


# ============================================================
# COMPROBAR ESTADO ACTUAL DE ASSIGNMENTS
# ============================================================

response = (
    supabase
    .table("assignments")
    .select("id", count="exact")
    .limit(1)
    .execute()
)

current_count = response.count or 0


print("\n========== ESTADO DE SUPABASE ==========")
print(f"Asignaciones existentes: {current_count}")


# Si hay 0, realizamos la primera carga.
# Si ya hay 2200, no insertamos de nuevo y verificamos.
# Cualquier cantidad intermedia requiere detenerse.

if current_count not in (0, EXPECTED_TOTAL):

    print(
        "\nERROR: assignments contiene un número "
        "parcial o inesperado de registros."
    )

    print(
        "No se insertará ni modificará nada."
    )

    sys.exit(1)


# ============================================================
# PREPARAR REGISTROS
# ============================================================

records = []

for row in plan:

    records.append({
        "case_id":
            cases[row["annotation_case_id"]],

        "specialist_id":
            specialists[row["specialist_code"]],

        "presentation_order":
            int(row["presentation_order"]),

        "status":
            "PENDING",
    })


if len(records) != EXPECTED_TOTAL:
    print(
        "\nERROR: no se prepararon exactamente "
        "2200 registros."
    )
    sys.exit(1)


# ============================================================
# INSERTAR ASIGNACIONES
# ============================================================

if current_count == 0:

    print("\n========== INSERCIÓN ==========")

    inserted = 0

    for start in range(
        0,
        len(records),
        INSERT_BATCH_SIZE
    ):

        batch = records[
            start:start + INSERT_BATCH_SIZE
        ]

        response = (
            supabase
            .table("assignments")
            .insert(batch)
            .execute()
        )

        inserted_now = len(response.data or [])

        inserted += inserted_now

        print(
            f"✓ Insertadas "
            f"{inserted}/{EXPECTED_TOTAL}"
        )

        if inserted_now != len(batch):
            print(
                "\nERROR: Supabase no devolvió el mismo "
                "número de registros que se intentó insertar."
            )
            print(
                "NO vuelvas a ejecutar el script."
            )
            sys.exit(1)


    if inserted != EXPECTED_TOTAL:
        print(
            "\nERROR: el número insertado "
            "no coincide con 2200."
        )
        print(
            "NO vuelvas a ejecutar el script."
        )
        sys.exit(1)

else:

    print(
        "\n↪ Ya existen 2200 asignaciones."
    )

    print(
        "↪ No se insertará ningún registro nuevo."
    )


# ============================================================
# VERIFICACIÓN DEL TOTAL EN SUPABASE
# ============================================================

response = (
    supabase
    .table("assignments")
    .select("id", count="exact")
    .limit(1)
    .execute()
)

final_count = response.count or 0


print("\n========== VERIFICACIÓN FINAL ==========")
print(f"Asignaciones reportadas por Supabase: {final_count}")


if final_count != EXPECTED_TOTAL:
    print(
        f"ERROR: se esperaban {EXPECTED_TOTAL} "
        f"asignaciones."
    )
    sys.exit(1)


# ============================================================
# RECUPERAR LAS 2200 ASIGNACIONES CON PAGINACIÓN
# ============================================================

print("\nRecuperando asignaciones para validarlas...")

final_rows = []
offset = 0

while True:

    start = offset
    end = offset + PAGE_SIZE - 1

    response = (
        supabase
        .table("assignments")
        .select(
            "id,"
            "case_id,"
            "specialist_id,"
            "presentation_order,"
            "status"
        )
        .order("id")
        .range(start, end)
        .execute()
    )

    batch = response.data or []

    if not batch:
        break

    final_rows.extend(batch)

    print(
        f"✓ Recuperadas "
        f"{len(final_rows)}/{EXPECTED_TOTAL}"
    )

    if len(batch) < PAGE_SIZE:
        break

    offset += PAGE_SIZE


if len(final_rows) != EXPECTED_TOTAL:

    print(
        f"\nERROR: se esperaban recuperar "
        f"{EXPECTED_TOTAL} asignaciones "
        f"y se recuperaron {len(final_rows)}."
    )

    sys.exit(1)


# ============================================================
# VALIDAR CARGAS POR ESPECIALISTA
# ============================================================

id_to_code = {
    specialist_id: code
    for code, specialist_id in specialists.items()
}


unknown_specialist_ids = {
    row["specialist_id"]
    for row in final_rows
    if row["specialist_id"] not in id_to_code
}

if unknown_specialist_ids:

    print(
        "\nERROR: existen specialist_id inesperados:"
    )

    for specialist_id in sorted(
        unknown_specialist_ids
    ):
        print(f"  - {specialist_id}")

    sys.exit(1)


database_counts = Counter(
    id_to_code[row["specialist_id"]]
    for row in final_rows
)


for code, expected in EXPECTED_BY_SPECIALIST.items():

    obtained = database_counts[code]

    if obtained != expected:

        print(
            f"\nERROR: {code}: "
            f"{obtained} != {expected}"
        )

        sys.exit(1)


# ============================================================
# VALIDAR STATUS
# ============================================================

status_counts = Counter(
    row["status"]
    for row in final_rows
)


if status_counts != Counter(
    {"PENDING": EXPECTED_TOTAL}
):
    print(
        "\nERROR: no todas las asignaciones "
        "están en estado PENDING."
    )

    print(status_counts)

    sys.exit(1)


# ============================================================
# VALIDAR PARES CASE + SPECIALIST
# ============================================================

database_pairs = {
    (
        row["case_id"],
        row["specialist_id"],
    )
    for row in final_rows
}


if len(database_pairs) != EXPECTED_TOTAL:

    print(
        "\nERROR: existen pares "
        "caso/especialista duplicados "
        "en Supabase."
    )

    sys.exit(1)


expected_pairs = {
    (
        cases[row["annotation_case_id"]],
        specialists[row["specialist_code"]],
    )
    for row in plan
}


if database_pairs != expected_pairs:

    missing_pairs = (
        expected_pairs
        - database_pairs
    )

    unexpected_pairs = (
        database_pairs
        - expected_pairs
    )

    print(
        "\nERROR: las asignaciones de Supabase "
        "no coinciden exactamente con el plan."
    )

    print(
        f"Pares faltantes: {len(missing_pairs)}"
    )

    print(
        f"Pares inesperados: {len(unexpected_pairs)}"
    )

    sys.exit(1)


# ============================================================
# VALIDAR PRESENTATION_ORDER
# ============================================================

for code, specialist_id in specialists.items():

    orders = sorted(
        row["presentation_order"]
        for row in final_rows
        if row["specialist_id"] == specialist_id
    )

    expected_orders = list(
        range(
            1,
            EXPECTED_BY_SPECIALIST[code] + 1
        )
    )

    if orders != expected_orders:

        print(
            f"\nERROR: presentation_order "
            f"incorrecto para {code}."
        )

        sys.exit(1)


# ============================================================
# VALIDAR QUE CADA CASO TENGA EL NÚMERO CORRECTO
# DE ASIGNACIONES
# ============================================================

case_id_to_annotation_case_id = {
    database_id: annotation_case_id
    for annotation_case_id, database_id
    in cases.items()
}


database_case_counts = Counter(
    row["case_id"]
    for row in final_rows
)


shared_ids = set(shared_case_counts.keys())
exclusive_id_set = set(exclusive_ids)


for case_id, count in database_case_counts.items():

    annotation_case_id = (
        case_id_to_annotation_case_id[case_id]
    )

    if annotation_case_id in shared_ids:

        if count != 3:
            print(
                f"\nERROR: el caso compartido "
                f"{annotation_case_id} tiene "
                f"{count} asignaciones en vez de 3."
            )
            sys.exit(1)

    elif annotation_case_id in exclusive_id_set:

        if count != 1:
            print(
                f"\nERROR: el caso exclusivo "
                f"{annotation_case_id} tiene "
                f"{count} asignaciones en vez de 1."
            )
            sys.exit(1)

    else:

        print(
            f"\nERROR: caso desconocido "
            f"{annotation_case_id}."
        )
        sys.exit(1)


if len(database_case_counts) != EXPECTED_CASES:

    print(
        f"\nERROR: las asignaciones cubren "
        f"{len(database_case_counts)} casos "
        f"en vez de {EXPECTED_CASES}."
    )

    sys.exit(1)


# ============================================================
# RESULTADO
# ============================================================

print("\nCarga por especialista:")

for code in sorted(EXPECTED_BY_SPECIALIST):

    print(
        f"  {code}: "
        f"{database_counts[code]}"
    )


print("\nEstados:")

for status, count in sorted(
    status_counts.items()
):
    print(
        f"  {status}: {count}"
    )


print("\nCobertura:")

print(
    f"  Casos únicos: "
    f"{len(database_case_counts)}"
)

print(
    f"  Exclusivos: "
    f"{EXPECTED_EXCLUSIVE_CASES} × 1 asignación"
)

print(
    f"  Compartidos: "
    f"{EXPECTED_SHARED_CASES} × 3 asignaciones"
)


print(
    "\n✓ Las 2200 asignaciones coinciden "
    "exactamente con el plan."
)

print(
    "✓ No existen pares "
    "caso/especialista duplicados."
)

print(
    "✓ presentation_order es válido."
)

print(
    "✓ Todas comienzan en estado PENDING."
)

print(
    "✓ Los 2000 casos están cubiertos."
)

print(
    "✓ Carga de asignaciones completada correctamente."
)
