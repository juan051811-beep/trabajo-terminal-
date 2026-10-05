import csv
import random
from collections import Counter, defaultdict
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

SEED = 2026
N_SHARED = 100

TARGET_ZONES = {
    "central": 60,
    "intermediate": 20,
    "peripheral": 20,
}

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_CSV = (
    BASE_DIR
    / "01_muestreo"
    / "sampling_final"
    / "sampling_2000_internal.csv"
)

OUTPUT_DIR = (
    BASE_DIR
    / "02_anotacion"
    / "database"
    / "seed"
)

OUTPUT_SHARED = OUTPUT_DIR / "shared_cases.csv"
OUTPUT_AUDIT = OUTPUT_DIR / "shared_cases_internal_audit.csv"


# ============================================================
# FUNCIONES
# ============================================================

def largest_remainder_allocation(cluster_sizes, total_slots):
    """
    Asigna total_slots proporcionalmente al tamaño de cada cluster
    mediante el método del mayor residuo.
    """

    total_size = sum(cluster_sizes.values())

    exact = {
        cluster: total_slots * size / total_size
        for cluster, size in cluster_sizes.items()
    }

    allocation = {
        cluster: int(exact[cluster])
        for cluster in cluster_sizes
    }

    remaining = total_slots - sum(allocation.values())

    order = sorted(
        cluster_sizes,
        key=lambda cluster: (
            -(exact[cluster] - allocation[cluster]),
            cluster,
        ),
    )

    for cluster in order[:remaining]:
        allocation[cluster] += 1

    return allocation


def choose_zone(zone_counts):
    """
    Elige la zona que todavía necesita más casos respecto
    al objetivo global.
    """

    candidates = []

    for zone, target in TARGET_ZONES.items():
        deficit = target - zone_counts[zone]

        if deficit > 0:
            candidates.append((deficit, zone))

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: (
            -x[0],
            x[1],
        )
    )

    return candidates[0][1]


# ============================================================
# CARGAR DATOS
# ============================================================

random.seed(SEED)

if not INPUT_CSV.exists():
    raise FileNotFoundError(
        f"No se encontró el archivo:\n{INPUT_CSV}"
    )

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with INPUT_CSV.open(
    "r",
    encoding="utf-8-sig",
    newline=""
) as f:
    rows = list(csv.DictReader(f))


if len(rows) != 2000:
    raise ValueError(
        f"Se esperaban 2000 casos y se encontraron {len(rows)}."
    )


# ============================================================
# VALIDACIONES INICIALES
# ============================================================

required_columns = {
    "annotation_case_id",
    "region",
    "cluster",
    "sampling_zone",
    "study_id",
}

missing_columns = required_columns - set(rows[0].keys())

if missing_columns:
    raise ValueError(
        f"Faltan columnas necesarias: {sorted(missing_columns)}"
    )


valid_zones = set(TARGET_ZONES)

found_zones = {
    row["sampling_zone"]
    for row in rows
}

unexpected_zones = found_zones - valid_zones

if unexpected_zones:
    raise ValueError(
        f"Se encontraron sampling_zone inesperadas: "
        f"{sorted(unexpected_zones)}"
    )


# ============================================================
# DEFINIR CLUSTERS
# ============================================================

clusters = defaultdict(list)

for row in rows:
    key = (
        row["region"],
        int(row["cluster"]),
    )

    clusters[key].append(row)


cluster_sizes = {
    key: len(values)
    for key, values in clusters.items()
}


if len(cluster_sizes) != 43:
    raise ValueError(
        f"Se esperaban 43 clusters y se encontraron "
        f"{len(cluster_sizes)}."
    )


# ============================================================
# ASIGNAR CUOTAS POR CLUSTER
# ============================================================

# Primero garantizamos 1 caso por cluster.
cluster_quota = {
    key: 1
    for key in cluster_sizes
}

remaining_slots = N_SHARED - len(cluster_quota)

# Las plazas restantes se distribuyen proporcionalmente.
extra_allocation = largest_remainder_allocation(
    cluster_sizes,
    remaining_slots,
)

for key in cluster_quota:
    cluster_quota[key] += extra_allocation[key]


if sum(cluster_quota.values()) != N_SHARED:
    raise RuntimeError(
        "La asignación por cluster no suma 100."
    )


# ============================================================
# PREPARAR CANDIDATOS
# ============================================================

for key in clusters:
    random.shuffle(clusters[key])


selected = []
selected_case_ids = set()
selected_studies = set()
zone_counts = Counter()


# ============================================================
# SELECCIÓN
# ============================================================

# Procesamos primero los clusters con menor cantidad de casos.
cluster_order = sorted(
    clusters,
    key=lambda key: (
        len(clusters[key]),
        key[0],
        key[1],
    )
)


for key in cluster_order:

    quota = cluster_quota[key]

    for _ in range(quota):

        desired_zone = choose_zone(zone_counts)

        candidates = [
            row
            for row in clusters[key]
            if row["annotation_case_id"] not in selected_case_ids
            and row["study_id"] not in selected_studies
        ]

        if not candidates:
            raise RuntimeError(
                f"No hay candidatos con study_id único "
                f"para {key}."
            )

        # Primero intentamos respetar la zona que más necesitamos.
        zone_candidates = [
            row
            for row in candidates
            if row["sampling_zone"] == desired_zone
        ]

        if zone_candidates:
            candidates = zone_candidates

        else:
            # Si esa zona no está disponible en este cluster,
            # priorizamos la zona con mayor déficit.
            candidates.sort(
                key=lambda row: (
                    -(
                        TARGET_ZONES[row["sampling_zone"]]
                        - zone_counts[row["sampling_zone"]]
                    ),
                    row["annotation_case_id"],
                )
            )

        chosen = candidates[0]

        selected.append(chosen)

        selected_case_ids.add(
            chosen["annotation_case_id"]
        )

        selected_studies.add(
            chosen["study_id"]
        )

        zone_counts[
            chosen["sampling_zone"]
        ] += 1


# ============================================================
# VALIDACIONES FINALES
# ============================================================

if len(selected) != N_SHARED:
    raise RuntimeError(
        f"Se seleccionaron {len(selected)} casos en vez de 100."
    )


if len(selected_case_ids) != N_SHARED:
    raise RuntimeError(
        "Hay annotation_case_id duplicados."
    )


if len(selected_studies) != N_SHARED:
    raise RuntimeError(
        "Hay study_id repetidos entre los compartidos."
    )


selected_cluster_counts = Counter(
    (
        row["region"],
        int(row["cluster"]),
    )
    for row in selected
)


missing_clusters = (
    set(cluster_sizes)
    - set(selected_cluster_counts)
)

if missing_clusters:
    raise RuntimeError(
        f"Hay clusters sin representación: {missing_clusters}"
    )


# ============================================================
# ORDENAR SALIDA
# ============================================================

selected.sort(
    key=lambda row: row["annotation_case_id"]
)


# ============================================================
# ARCHIVO PARA USO OPERATIVO
# ============================================================

with OUTPUT_SHARED.open(
    "w",
    encoding="utf-8",
    newline=""
) as f:

    fieldnames = [
        "annotation_case_id",
        "region",
        "is_shared",
    ]

    writer = csv.DictWriter(
        f,
        fieldnames=fieldnames,
    )

    writer.writeheader()

    for row in selected:
        writer.writerow({
            "annotation_case_id":
                row["annotation_case_id"],
            "region":
                row["region"],
            "is_shared":
                "true",
        })


# ============================================================
# ARCHIVO INTERNO DE AUDITORÍA
# ============================================================

with OUTPUT_AUDIT.open(
    "w",
    encoding="utf-8",
    newline=""
) as f:

    fieldnames = [
        "annotation_case_id",
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

    for row in selected:
        writer.writerow({
            "annotation_case_id":
                row["annotation_case_id"],
            "region":
                row["region"],
            "cluster":
                row["cluster"],
            "sampling_zone":
                row["sampling_zone"],
            "study_id":
                row["study_id"],
        })


# ============================================================
# RESUMEN
# ============================================================

region_counts = Counter(
    row["region"]
    for row in selected
)


print("\n========== CASOS COMPARTIDOS ==========")

print(f"Semilla:             {SEED}")
print(f"Casos seleccionados: {len(selected)}")
print(f"Estudios únicos:     {len(selected_studies)}")
print(f"Clusters cubiertos:  {len(selected_cluster_counts)} / 43")

print("\nDistribución por zona:")

for zone in [
    "central",
    "intermediate",
    "peripheral",
]:
    print(
        f"  {zone:12}: "
        f"{zone_counts[zone]}"
    )


print("\nDistribución por región:")

for region in sorted(region_counts):
    print(
        f"  {region:12}: "
        f"{region_counts[region]}"
    )


print("\nCuota y selección por cluster:")

for key in sorted(cluster_sizes):
    region, cluster = key

    print(
        f"  {region:12} "
        f"cluster {cluster}: "
        f"{selected_cluster_counts[key]} "
        f"/ {cluster_sizes[key]}"
    )


print("\nArchivos generados:")

print(f"  {OUTPUT_SHARED}")
print(f"  {OUTPUT_AUDIT}")

print("\n✓ Selección de compartidos completada.")
