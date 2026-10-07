import hashlib
import secrets
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

SPECIALISTS = [
    "SPECIALIST_01",
    "SPECIALIST_02",
    "SPECIALIST_03",
]

BASE_DIR = Path(__file__).resolve().parents[2]

SECRETS_DIR = (
    BASE_DIR
    / "02_anotacion"
    / "secrets"
)

HASH_FILE = (
    SECRETS_DIR
    / "specialist_access_hashes.txt"
)


# ============================================================
# GENERAR CÓDIGO
# ============================================================

def generate_access_code():
    """
    Genera un código aleatorio con formato:

    MURA-XXXX-XXXX-XXXX

    Se usa secrets para obtener aleatoriedad
    criptográficamente segura.
    """

    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    groups = []

    for _ in range(3):

        group = "".join(
            secrets.choice(alphabet)
            for _ in range(4)
        )

        groups.append(group)

    return "MURA-" + "-".join(groups)


# ============================================================
# GENERAR HASH
# ============================================================

def hash_access_code(code):
    """
    Genera SHA-256 del código.

    El código original no se guarda en el archivo.
    """

    return hashlib.sha256(
        code.encode("utf-8")
    ).hexdigest()


# ============================================================
# PREPARAR DIRECTORIO
# ============================================================

SECRETS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# PROTECCIÓN CONTRA SOBRESCRITURA
# ============================================================

if HASH_FILE.exists():

    print("\nERROR:")
    print(
        "Ya existe un archivo con hashes "
        "de códigos de acceso."
    )

    print(
        "\nNo se generaron códigos nuevos "
        "para evitar reemplazar los existentes."
    )

    raise SystemExit(1)


# ============================================================
# GENERAR CÓDIGOS
# ============================================================

generated = []

used_codes = set()

for specialist in SPECIALISTS:

    while True:

        code = generate_access_code()

        if code not in used_codes:
            used_codes.add(code)
            break

    code_hash = hash_access_code(code)

    generated.append(
        {
            "specialist": specialist,
            "code": code,
            "hash": code_hash,
        }
    )


# ============================================================
# GUARDAR ÚNICAMENTE LOS HASHES
# ============================================================

with HASH_FILE.open(
    "w",
    encoding="utf-8",
) as f:

    for item in generated:

        f.write(
            f"{item['specialist']}="
            f"{item['hash']}\n"
        )


# ============================================================
# RESULTADO
# ============================================================

print()
print("=" * 60)
print("CÓDIGOS DE ACCESO GENERADOS")
print("=" * 60)

print(
    "\nIMPORTANTE: estos códigos se muestran "
    "para que puedas registrarlos de forma segura."
)

print(
    "El archivo local contiene únicamente "
    "sus hashes.\n"
)

for item in generated:

    print(
        f"{item['specialist']}: "
        f"{item['code']}"
    )

print()
print("=" * 60)

print(
    "Hashes guardados localmente en:"
)

print(HASH_FILE)

print()
print(
    "NO compartas los códigos en GitHub."
)

print(
    "NO me pegues aquí los códigos generados."
)

print("=" * 60)
