import csv
import random
from collections import Counter, defaultdict
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

SEED = 2026

SPECIALISTS = [
    "SPECIALIST_01",
    "SPECIALIST_02",
    "SPECIALIST_03",
]

EXCLUSIVE_TARGETS = {
    "SPECIALIST_01": 634,
    "SPECIALIST_02": 633,
    "SPECIALIST_03": 633,
}

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_CSV = (
    BASE_DIR
    / "01_muestreo"
    / "sampling_final"
    / "sampling_2000_internal.csv"
)

SHARED_CSV = (
    BASE_DIR
    / "02_anotacion"
    / "database"
    / "seed"
    / "shared_cases.csv"
)

OUTPUT_DIR = (
    BASE_DIR
    / "02_anotacion"
    / "database"
    / "seed"
)

OUTPUT_ASSIGNMENTS = OUTPUT_DIR / "assignments_plan.csv"

OUTPUT_AUDIT = (
    OUTPUT_DIR
    / "assignments_internal_audit.csv"
)


# ============================================================
# CARGAR DATOS
# ============================================================

random.seed(SEED)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with INPUT_CSV.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as f:
    rows = list(csv.DictReader(f))

with SHARED_CSV.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as f:
    shared_rows = list(csv.DictReader(f))


if len(rows) != 2000:
    raise ValueError(
        f"Se esperaban 2000 casos y se encontraron {len(rows)}."
    )

if len(shared_rows) != 100:
    raise ValueError(
        f"Se esperaban 100 compartidos y se encontraron "
        f"{len(shared_rows)}."
    )


# ============================================================
# IDENTIFICAR COMPARTIDOS Y EXCLUSIVOS
# ============================================================

shared_ids = {
    row["annotation_case_id"]
    for row in shared_rows
}

if len(shared_ids) != 100:
    raise ValueError(
        "Hay annotation_case_id duplicados entre los compartidos."
    )


all_ids = {
    row["annotation_case_id"]
    for row in rows
}

if not shared_ids.issubset(all_ids):
    raise ValueError(
        "Hay casos compartidos que no aparecen en "
        "sampling_2000_internal.csv."
    )


exclusive_rows = [
    row
    for row in rows
    if row["annotation_case_id"] not in shared_ids
]


if len(exclusive_rows) != 1900:
    raise ValueError(
        f"Se esperaban 1900 exclusivos y se encontraron "
        f"{len(exclusive_rows)}."
    )


# ============================================================
# AGRUPAR EXCLUSIVOS POR ESTRATO
# region + cluster + sampling_zone
# ============================================================

strata = defaultdict(list)

for row in exclusive_rows:

    key = (
        row["region"],
        int(row["cluster"]),
        row["sampling_zone"],
    )

    strata[key].append(row)


# Aleatorización reproducible dentro de cada estrato.
for key in strata:
    random.shuffle(strata[key])


# ============================================================
# ESTRUCTURAS DE ASIGNACIÓN
# ============================================================

exclusive_assignments = {
    specialist: []
    for specialist in SPECIALISTS
}

# Conteo por estrato y especialista.
stratum_counts = {
    specialist: Counter()
    for specialist in SPECIALISTS
}


# ============================================================
# DISTRIBUIR EXCLUSIVOS
# ============================================================

# Procesamos primero los estratos pequeños.
strata_order = sorted(
    strata,
    key=lambda key: (
        len(strata[key]),
        key[0],
        key[1],
        key[2],
    )
)


for stratum in strata_order:

    cases = strata[stratum]

    for row in cases:

        available = [
            specialist
            for specialist in SPECIALISTS
            if (
                len(exclusive_assignments[specialist])
                < EXCLUSIVE_TARGETS[specialist]
            )
        ]

        if not available:
            raise RuntimeError(
                "No quedan especialistas con capacidad."
            )

        # Prioridad 1:
        # especialista con menor cantidad de casos
        # de este mismo estrato.
        #
        # Prioridad 2:
        # especialista con menor carga relativa.
        #
        # Prioridad 3:
        # desempate aleatorio reproducible.

        random_tiebreak = {
            specialist: random.random()
            for specialist in available
        }

        chosen = min(
            available,
            key=lambda specialist: (
                stratum_counts[specialist][stratum],
                (
                    len(exclusive_assignments[specialist])
                    / EXCLUSIVE_TARGETS[specialist]
                ),
                random_tiebreak[specialist],
            ),
        )

        exclusive_assignments[chosen].append(row)

        stratum_counts[chosen][stratum] += 1


# ============================================================
# VALIDAR CARGAS EXCLUSIVAS
# ============================================================

for specialist in SPECIALISTS:

    obtained = len(
        exclusive_assignments[specialist]
    )

    expected = EXCLUSIVE_TARGETS[specialist]

    if obtained != expected:
        raise RuntimeError(
            f"{specialist}: se esperaban {expected} "
            f"exclusivos y se obtuvieron {obtained}."
        )


assigned_exclusive_ids = [
    row["annotation_case_id"]
    for specialist in SPECIALISTS
    for row in exclusive_assignments[specialist]
]


if len(assigned_exclusive_ids) != 1900:
    raise RuntimeError(
        "El total de asignaciones exclusivas no es 1900."
    )


if len(set(assigned_exclusive_ids)) != 1900:
    raise RuntimeError(
        "Hay casos exclusivos asignados a más de "
        "un especialista."
    )


if set(assigned_exclusive_ids) != {
    row["annotation_case_id"]
    for row in exclusive_rows
}:
    raise RuntimeError(
        "Los casos exclusivos asignados no coinciden "
        "con los 1900 esperados."
    )


# ============================================================
# CREAR PLAN COMPLETO
# ============================================================

row_by_id = {
    row["annotation_case_id"]: row
    for row in rows
}

complete_assignments = {
    specialist: []
    for specialist in SPECIALISTS
}


for specialist in SPECIALISTS:

    # Exclusivos
    for row in exclusive_assignments[specialist]:

        complete_assignments[specialist].append({
            "annotation_case_id":
                row["annotation_case_id"],
            "specialist_code":
                specialist,
            "assignment_type":
                "EXCLUSIVE",
        })

    # Los mismos 100 compartidos para los tres.
    for case_id in sorted(shared_ids):

        complete_assignments[specialist].append({
            "annotation_case_id":
                case_id,
            "specialist_code":
                specialist,
            "assignment_type":
                "SHARED",
        })

    # Mezclamos el orden de presentación.
    random.shuffle(
        complete_assignments[specialist]
    )

    # presentation_order comienza en 1.
    for index, assignment in enumerate(
        complete_assignments[specialist],
        start=1
    ):
        assignment["presentation_order"] = index


# ============================================================
# VALIDAR CARGAS TOTALES
# ============================================================

expected_totals = {
    "SPECIALIST_01": 734,
    "SPECIALIST_02": 733,
    "SPECIALIST_03": 733,
}


for specialist in SPECIALISTS:

    total = len(
        complete_assignments[specialist]
    )

    if total != expected_totals[specialist]:
        raise RuntimeError(
            f"{specialist}: total incorrecto. "
            f"Esperado={expected_totals[specialist]}, "
            f"obtenido={total}"
        )


# Cada compartido debe aparecer exactamente tres veces.
shared_assignment_counts = Counter()

for specialist in SPECIALISTS:

    for assignment in complete_assignments[specialist]:

        if assignment["assignment_type"] == "SHARED":
            shared_assignment_counts[
                assignment["annotation_case_id"]
            ] += 1


if len(shared_assignment_counts) != 100:
    raise RuntimeError(
        "No aparecen los 100 casos compartidos."
    )


if any(
    count != 3
    for count in shared_assignment_counts.values()
):
    raise RuntimeError(
        "Algún caso compartido no está asignado "
        "a los tres especialistas."
    )


# ============================================================
# GUARDAR PLAN OPERATIVO
# ============================================================

with OUTPUT_ASSIGNMENTS.open(
    "w",
    encoding="utf-8",
    newline=""
) as f:

    fieldnames = [
        "specialist_code",
        "annotation_case_id",
        "assignment_type",
        "presentation_order",
    ]

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    for specialist in SPECIALISTS:

        assignments = sorted(
            complete_assignments[specialist],
            key=lambda x: x["presentation_order"],
        )

        for assignment in assignments:
            writer.writerow(assignment)


# ============================================================
# GUARDAR AUDITORÍA INTERNA
# ============================================================

with OUTPUT_AUDIT.open(
    "w",
    encoding="utf-8",
    newline=""
) as f:

    fieldnames = [
        "specialist_code",
        "annotation_case_id",
        "assignment_type",
        "presentation_order",
        "region",
        "cluster",
        "sampling_zone",
        "study_id",
    ]

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    for specialist in SPECIALISTS:

        assignments = sorted(
            complete_assignments[specialist],
            key=lambda x: x["presentation_order"],
        )

        for assignment in assignments:

            source = row_by_id[
                assignment["annotation_case_id"]
            ]

            writer.writerow({
                **assignment,
                "region":
                    source["region"],
                "cluster":
                    source["cluster"],
                "sampling_zone":
                    source["sampling_zone"],
                "study_id":
                    source["study_id"],
            })


# ============================================================
# RESUMEN
# ============================================================

print("\n========== DISTRIBUCIÓN DE CASOS ==========")

print(f"Semilla: {SEED}")

print("\nCarga por especialista:")

for specialist in SPECIALISTS:

    exclusive_count = len(
        exclusive_assignments[specialist]
    )

    total_count = len(
        complete_assignments[specialist]
    )

    print(
        f"  {specialist}: "
        f"{exclusive_count} exclusivos + "
        f"100 compartidos = "
        f"{total_count}"
    )


print("\nDistribución EXCLUSIVA por región:")

for specialist in SPECIALISTS:

    counts = Counter(
        row["region"]
        for row in exclusive_assignments[specialist]
    )

    print(f"\n  {specialist}")

    for region in sorted(counts):
        print(
            f"    {region:12}: "
            f"{counts[region]}"
        )


print("\nDistribución EXCLUSIVA por zona:")

for specialist in SPECIALISTS:

    counts = Counter(
        row["sampling_zone"]
        for row in exclusive_assignments[specialist]
    )

    print(
        f"  {specialist}: "
        f"central={counts['central']}, "
        f"intermediate={counts['intermediate']}, "
        f"peripheral={counts['peripheral']}"
    )


print("\nValidaciones:")

print(
    f"  Casos exclusivos únicos: "
    f"{len(set(assigned_exclusive_ids))} / 1900"
)

print(
    f"  Casos compartidos: "
    f"{len(shared_assignment_counts)} / 100"
)

print(
    "  Cada compartido asignado a "
    "3 especialistas: ✓"
)

print(
    "  Duplicación entre asignaciones "
    "exclusivas: 0"
)

print("\nArchivos generados:")

print(f"  {OUTPUT_ASSIGNMENTS}")
print(f"  {OUTPUT_AUDIT}")

print("\n✓ Distribución completada correctamente.")
