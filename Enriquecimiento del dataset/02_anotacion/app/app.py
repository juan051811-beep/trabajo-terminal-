import hashlib
import os
import tempfile
from collections import Counter
from io import BytesIO
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from PIL import Image
from streamlit_image_annotation.Detection import detection
from supabase import create_client


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="MURA - Anotación radiográfica",
    page_icon="🩻",
    layout="wide",
    initial_sidebar_state="collapsed",
)

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)

BUCKET_NAME = "mura-radiographs"

EXPECTED_ASSIGNMENTS = {
    "SPECIALIST_01": 734,
    "SPECIALIST_02": 733,
    "SPECIALIST_03": 733,
}

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    st.error(
        "La aplicación no tiene configurada correctamente "
        "la conexión con Supabase."
    )
    st.stop()


# ============================================================
# SUPABASE
# ============================================================

@st.cache_resource
def get_supabase_client():
    return create_client(
        SUPABASE_URL,
        SUPABASE_SERVICE_ROLE_KEY,
    )


supabase = get_supabase_client()


# ============================================================
# SESIÓN
# ============================================================

DEFAULT_SESSION_VALUES = {
    "authenticated": False,
    "specialist_id": None,
    "specialist_code": None,
    "display_name": None,
    "loaded_assignment_id": None,
    "bbox_assignment_id": None,
    "bbox_items": [],
    "confirm_finalize": False,
    "evaluation_completed_successfully": False,
    "current_assignment_id": None,
}

for key, value in DEFAULT_SESSION_VALUES.items():
    if key not in st.session_state:
        if isinstance(value, list):
            st.session_state[key] = []
        else:
            st.session_state[key] = value


# ============================================================
# AUTENTICACIÓN
# ============================================================

def normalize_access_code(code):
    return code.strip().upper()


def hash_access_code(code):
    return hashlib.sha256(
        normalize_access_code(code).encode("utf-8")
    ).hexdigest()


def authenticate_specialist(access_code):

    if not access_code:
        return None

    access_hash = hash_access_code(access_code)

    try:
        response = (
            supabase
            .table("specialists")
            .select(
                "id,"
                "specialist_code,"
                "display_name,"
                "is_active"
            )
            .eq("access_code_hash", access_hash)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )

    except Exception:
        return None

    rows = response.data or []

    if len(rows) != 1:
        return None

    return rows[0]


def login_specialist(specialist):

    st.session_state.authenticated = True
    st.session_state.specialist_id = specialist["id"]
    st.session_state.specialist_code = (
        specialist["specialist_code"]
    )
    st.session_state.display_name = (
        specialist.get("display_name")
        or specialist["specialist_code"]
    )
    st.session_state.loaded_assignment_id = None
    st.session_state.bbox_assignment_id = None
    st.session_state.bbox_items = []


def logout_specialist():

    keys_to_delete = [
        "fracture_status",
        "degenerative_status",
        "hardware_status",
        "other_status",
        "other_description",
        "not_evaluable",
        "comments",
    ]

    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]

    for key, value in DEFAULT_SESSION_VALUES.items():
        if isinstance(value, list):
            st.session_state[key] = []
        else:
            st.session_state[key] = value


# ============================================================
# ASIGNACIONES
# ============================================================

def get_specialist_assignments(specialist_id):

    page_size = 1000
    offset = 0
    assignments = []

    while True:

        response = (
            supabase
            .table("assignments")
            .select(
                "id,"
                "case_id,"
                "presentation_order,"
                "status,"
                "started_at,"
                "completed_at"
            )
            .eq("specialist_id", specialist_id)
            .order("presentation_order")
            .range(
                offset,
                offset + page_size - 1,
            )
            .execute()
        )

        batch = response.data or []

        if not batch:
            break

        assignments.extend(batch)

        if len(batch) < page_size:
            break

        offset += page_size

    return assignments


# ============================================================
# CASOS Y ANOTACIONES
# ============================================================

def get_case(case_id):

    response = (
        supabase
        .table("cases")
        .select(
            "id,"
            "annotation_case_id,"
            "region,"
            "image_filename,"
            "storage_path"
        )
        .eq("id", case_id)
        .limit(1)
        .execute()
    )

    rows = response.data or []

    if len(rows) != 1:
        return None

    return rows[0]


def get_annotation(assignment_id):

    response = (
        supabase
        .table("annotations")
        .select(
            "id,"
            "fracture_status,"
            "degenerative_status,"
            "hardware_status,"
            "other_status,"
            "other_description,"
            "not_evaluable,"
            "comments"
        )
        .eq("assignment_id", assignment_id)
        .limit(1)
        .execute()
    )

    rows = response.data or []

    if not rows:
        return None

    return rows[0]


def get_bounding_boxes(annotation_id):

    response = (
        supabase
        .table("bounding_boxes")
        .select(
            "id,"
            "finding_type,"
            "bbox_index,"
            "x_min,"
            "y_min,"
            "x_max,"
            "y_max,"
            "image_width,"
            "image_height"
        )
        .eq("annotation_id", annotation_id)
        .order("bbox_index")
        .execute()
    )

    return response.data or []


@st.cache_data(show_spinner=False)
def download_radiograph(storage_path):

    return (
        supabase
        .storage
        .from_(BUCKET_NAME)
        .download(storage_path)
    )


# ============================================================
# ARCHIVO TEMPORAL PARA EL ANOTADOR
# ============================================================

@st.cache_data(show_spinner=False)
def prepare_local_radiograph(
    image_bytes,
    image_filename,
):

    safe_name = Path(image_filename).name

    digest = hashlib.sha256(
        image_bytes
    ).hexdigest()[:16]

    extension = (
        Path(safe_name).suffix.lower()
        or ".png"
    )

    temp_dir = (
        Path(tempfile.gettempdir())
        / "mura_tt_annotation"
    )

    temp_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    local_path = (
        temp_dir
        / f"{digest}{extension}"
    )

    if not local_path.exists():
        local_path.write_bytes(image_bytes)

    return str(local_path)


def get_image_dimensions(image_bytes):

    with Image.open(BytesIO(image_bytes)) as image:
        return image.size



@st.cache_data(show_spinner=False)
def prepare_display_radiograph(
    image_bytes,
    image_filename,
    target_long_side=1200,
):
    """
    Genera una copia temporal exclusivamente para el visor.

    La radiografía original no se modifica. La copia se amplía
    proporcionalmente cuando es necesario para facilitar la
    anotación visual.
    """

    safe_name = Path(image_filename).name

    digest = hashlib.sha256(
        image_bytes
    ).hexdigest()[:16]

    display_dir = (
        Path(tempfile.gettempdir())
        / "mura_tt_annotation"
        / "display"
    )

    display_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    display_path = (
        display_dir
        / f"{digest}_display.png"
    )

    with Image.open(BytesIO(image_bytes)) as image:

        image = image.convert("RGB")

        original_width, original_height = (
            image.size
        )

        longest_side = max(
            original_width,
            original_height,
        )

        if longest_side <= 0:
            raise ValueError(
                "Dimensiones de imagen inválidas."
            )

        scale = max(
            1.0,
            target_long_side / longest_side,
        )

        display_width = round(
            original_width * scale
        )

        display_height = round(
            original_height * scale
        )

        if (
            display_width != original_width
            or
            display_height != original_height
        ):
            image = image.resize(
                (
                    display_width,
                    display_height,
                ),
                Image.Resampling.LANCZOS,
            )

        image.save(
            display_path,
            format="PNG",
        )

    return (
        str(display_path),
        display_width,
        display_height,
        scale,
    )



def get_annotation_viewer_size(
    image_width,
    image_height,
    max_width=1200,
    max_height=1000,
):
    """
    Calcula el tamaño del visor manteniendo
    la relación de aspecto de la radiografía.
    """

    if image_width <= 0 or image_height <= 0:
        return 500, 500

    scale = min(
        max_width / image_width,
        max_height / image_height,
    )

    # Permitimos ampliar imágenes pequeñas para que
    # aprovechen mejor el espacio disponible en el visor,
    # conservando siempre su relación de aspecto.

    viewer_width = max(
        1,
        round(image_width * scale),
    )

    viewer_height = max(
        1,
        round(image_height * scale),
    )

    return viewer_width, viewer_height


# ============================================================
# CONVERSIONES
# ============================================================

DB_TO_UI = {
    "PRESENT": "Presente",
    "ABSENT": "Ausente",
    "INDETERMINATE": "Indeterminado",
    None: "Seleccionar...",
}

UI_TO_DB = {
    "Presente": "PRESENT",
    "Ausente": "ABSENT",
    "Indeterminado": "INDETERMINATE",
}

FINDING_TO_DB = {
    "Fractura": "FRACTURE",
    "Cambios degenerativos": "DEGENERATIVE",
    "Material quirúrgico": "HARDWARE",
    "Otro hallazgo": "OTHER",
}

DB_TO_FINDING = {
    "FRACTURE": "Fractura",
    "DEGENERATIVE": "Cambios degenerativos",
    "HARDWARE": "Material quirúrgico",
    "OTHER": "Otro hallazgo",
}


# ============================================================
# FORMULARIO
# ============================================================

def initialize_form_for_assignment(assignment_id):

    if (
        st.session_state.loaded_assignment_id
        == assignment_id
    ):
        return

    annotation = get_annotation(assignment_id)

    if annotation:

        st.session_state.fracture_status = (
            DB_TO_UI.get(
                annotation.get("fracture_status"),
                "Seleccionar...",
            )
        )

        st.session_state.degenerative_status = (
            DB_TO_UI.get(
                annotation.get(
                    "degenerative_status"
                ),
                "Seleccionar...",
            )
        )

        st.session_state.hardware_status = (
            DB_TO_UI.get(
                annotation.get("hardware_status"),
                "Seleccionar...",
            )
        )

        st.session_state.other_status = (
            DB_TO_UI.get(
                annotation.get("other_status"),
                "Seleccionar...",
            )
        )

        st.session_state.other_description = (
            annotation.get("other_description")
            or ""
        )

        st.session_state.not_evaluable = bool(
            annotation.get("not_evaluable")
        )

        st.session_state.comments = (
            annotation.get("comments")
            or ""
        )

    else:

        st.session_state.fracture_status = (
            "Seleccionar..."
        )

        st.session_state.degenerative_status = (
            "Seleccionar..."
        )

        st.session_state.hardware_status = (
            "Seleccionar..."
        )

        st.session_state.other_status = (
            "Seleccionar..."
        )

        st.session_state.other_description = ""
        st.session_state.not_evaluable = False
        st.session_state.comments = ""

    st.session_state.loaded_assignment_id = (
        assignment_id
    )


def initialize_bbox_state(
    assignment_id,
):

    if (
        st.session_state.bbox_assignment_id
        == assignment_id
    ):
        return

    st.session_state.bbox_items = []

    annotation = get_annotation(
        assignment_id
    )

    if annotation:

        annotation_id = annotation.get("id")

        if annotation_id is not None:

            saved_boxes = get_bounding_boxes(
                annotation_id
            )

            restored_items = []

            for box in saved_boxes:

                finding = DB_TO_FINDING.get(
                    box.get("finding_type")
                )

                if finding is None:
                    continue

                try:
                    image_width = float(
                        box["image_width"]
                    )
                    image_height = float(
                        box["image_height"]
                    )

                    x_min = (
                        float(box["x_min"])
                        * image_width
                    )

                    y_min = (
                        float(box["y_min"])
                        * image_height
                    )

                    x_max = (
                        float(box["x_max"])
                        * image_width
                    )

                    y_max = (
                        float(box["y_max"])
                        * image_height
                    )

                except (
                    TypeError,
                    ValueError,
                    KeyError,
                ):
                    continue

                width = x_max - x_min
                height = y_max - y_min

                if width <= 0 or height <= 0:
                    continue

                # El componente necesita:
                # [x, y, width, height]
                restored_items.append(
                    {
                        "finding": finding,
                        "bbox": [
                            x_min,
                            y_min,
                            width,
                            height,
                        ],
                    }
                )

            st.session_state.bbox_items = (
                restored_items
            )

    st.session_state.bbox_assignment_id = (
        assignment_id
    )


def validate_form(
    fracture_status,
    degenerative_status,
    hardware_status,
    other_status,
    other_description,
    not_evaluable,
):

    errors = []

    statuses = {
        "Fractura": fracture_status,
        "Cambios degenerativos": (
            degenerative_status
        ),
        "Material quirúrgico": (
            hardware_status
        ),
        "Otro hallazgo": other_status,
    }

    if not_evaluable:

        for label, value in statuses.items():
            if value in {
                "Presente",
                "Ausente",
            }:
                errors.append(
                    "Si la radiografía es no evaluable, "
                    f"{label} no puede marcarse como "
                    f"{value.lower()}."
                )

    else:

        for label, value in statuses.items():
            if value == "Seleccionar...":
                errors.append(
                    f"Selecciona una opción para "
                    f"{label}."
                )

    if (
        other_status == "Presente"
        and not other_description.strip()
    ):
        errors.append(
            "Describe el otro hallazgo observado."
        )

    return errors


def status_to_db(
    value,
    not_evaluable=False,
):

    if (
        not_evaluable
        and value == "Seleccionar..."
    ):
        return "INDETERMINATE"

    return UI_TO_DB.get(value)


def save_draft(
    assignment_id,
    specialist_id,
    fracture_status,
    degenerative_status,
    hardware_status,
    other_status,
    other_description,
    not_evaluable,
    comments,
    bboxes,
):

    params = {
        "p_assignment_id": assignment_id,
        "p_specialist_id": specialist_id,

        "p_fracture_status": status_to_db(
            fracture_status,
            not_evaluable,
        ),

        "p_degenerative_status": status_to_db(
            degenerative_status,
            not_evaluable,
        ),

        "p_hardware_status": status_to_db(
            hardware_status,
            not_evaluable,
        ),

        "p_other_status": status_to_db(
            other_status,
            not_evaluable,
        ),

        "p_other_description": (
            other_description.strip()
            if other_description
            else None
        ),

        "p_not_evaluable": not_evaluable,

        "p_comments": (
            comments.strip()
            if comments
            else None
        ),

        "p_bboxes": bboxes,
    }

    response = (
        supabase
        .rpc(
            "save_annotation_draft_with_bboxes",
            params,
        )
        .execute()
    )

    return response.data


def finalize_evaluation(
    assignment_id,
    specialist_id,
    fracture_status,
    degenerative_status,
    hardware_status,
    other_status,
    other_description,
    not_evaluable,
    comments,
    bboxes,
):

    params = {
        "p_assignment_id": assignment_id,
        "p_specialist_id": specialist_id,

        "p_fracture_status": status_to_db(
            fracture_status,
            not_evaluable,
        ),

        "p_degenerative_status": status_to_db(
            degenerative_status,
            not_evaluable,
        ),

        "p_hardware_status": status_to_db(
            hardware_status,
            not_evaluable,
        ),

        "p_other_status": status_to_db(
            other_status,
            not_evaluable,
        ),

        "p_other_description": (
            other_description.strip()
            if other_description
            else None
        ),

        "p_not_evaluable": not_evaluable,

        "p_comments": (
            comments.strip()
            if comments
            else None
        ),

        "p_bboxes": bboxes,
    }

    response = (
        supabase
        .rpc(
            "finalize_annotation",
            params,
        )
        .execute()
    )

    return response.data


# ============================================================
# BOUNDING BOXES
# ============================================================

def get_present_findings(
    fracture_status,
    degenerative_status,
    hardware_status,
    other_status,
):

    statuses = {
        "Fractura": fracture_status,
        "Cambios degenerativos": (
            degenerative_status
        ),
        "Material quirúrgico": (
            hardware_status
        ),
        "Otro hallazgo": other_status,
    }

    return [
        label
        for label, status in statuses.items()
        if status == "Presente"
    ]


def prepare_boxes_for_component(
    active_labels,
    display_scale=1.0,
):

    bboxes = []
    labels = []

    for item in st.session_state.bbox_items:

        finding = item.get("finding")

        if finding not in active_labels:
            continue

        bbox = item.get("bbox")

        if (
            not isinstance(bbox, list)
            or len(bbox) != 4
        ):
            continue

        # bbox_items se conserva siempre en coordenadas
        # de la radiografía ORIGINAL.
        #
        # El componente recibirá una copia visual ampliada,
        # por lo que convertimos temporalmente las cajas
        # originales al sistema de coordenadas del visor.
        bboxes.append(
            [
                float(value) * display_scale
                for value in bbox
            ]
        )

        labels.append(
            active_labels.index(finding)
        )

    return bboxes, labels


def update_bbox_state_from_component(
    component_result,
    active_labels,
    display_scale=1.0,
):

    if component_result is None:
        return

    if display_scale <= 0:
        display_scale = 1.0

    new_items = []

    for item in component_result:

        bbox = item.get("bbox", [])
        label_id = item.get("label_id")

        if len(bbox) != 4:
            continue

        try:
            label_id = int(label_id)
        except (TypeError, ValueError):
            continue

        if not (
            0 <= label_id < len(active_labels)
        ):
            continue

        # El componente devuelve coordenadas respecto
        # a la copia visual ampliada.
        #
        # Las regresamos inmediatamente al sistema
        # de coordenadas de la radiografía ORIGINAL.
        original_bbox = [
            float(value) / display_scale
            for value in bbox
        ]

        new_items.append(
            {
                "finding": (
                    active_labels[label_id]
                ),
                "bbox": original_bbox,
            }
        )

    st.session_state.bbox_items = (
        new_items
    )

def remove_inactive_boxes(
    active_labels,
):

    st.session_state.bbox_items = [
        item
        for item
        in st.session_state.bbox_items
        if item.get("finding")
        in active_labels
    ]


def convert_boxes_for_database(
    image_width,
    image_height,
):

    """
    Conversión interna.

    El componente devuelve:
        [x, y, width, height]

    Esta función prepara:
        x_min, y_min, x_max, y_max
        coordenadas normalizadas
        dimensiones originales

    Estos valores NO se muestran al especialista.
    """

    converted = []

    for index, item in enumerate(
        st.session_state.bbox_items,
        start=1,
    ):

        bbox = item.get("bbox", [])

        if len(bbox) != 4:
            continue

        x, y, box_width, box_height = (
            map(float, bbox)
        )

        x_min = min(
            x,
            x + box_width,
        )

        y_min = min(
            y,
            y + box_height,
        )

        x_max = max(
            x,
            x + box_width,
        )

        y_max = max(
            y,
            y + box_height,
        )

        if not (
            0 <= x_min < x_max
            <= image_width
            and
            0 <= y_min < y_max
            <= image_height
        ):
            continue

        finding = item["finding"]

        converted.append(
            {
                "bbox_index": index,
                "finding_type": (
                    FINDING_TO_DB[finding]
                ),
                "x_min": x_min / image_width,
                "y_min": y_min / image_height,
                "x_max": x_max / image_width,
                "y_max": y_max / image_height,
                "x_min_norm": (
                    x_min / image_width
                ),
                "y_min_norm": (
                    y_min / image_height
                ),
                "x_max_norm": (
                    x_max / image_width
                ),
                "y_max_norm": (
                    y_max / image_height
                ),
                "image_width": image_width,
                "image_height": image_height,
            }
        )

    return converted


def count_boxes_by_finding():

    counts = Counter()

    for item in st.session_state.bbox_items:
        finding = item.get("finding")

        if finding:
            counts[finding] += 1

    return counts


# ============================================================
# ESTILOS
# ============================================================

st.markdown(
    """
    <style>

    .block-container {
        max-width: 1450px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }

    .login-title {
        text-align: center;
        font-size: 2.1rem;
        font-weight: 700;
        margin-bottom: 0.4rem;
    }

    .login-subtitle {
        text-align: center;
        color: #666666;
        margin-bottom: 2rem;
    }

    .session-box {
        padding: 0.9rem 1.1rem;
        border: 1px solid
            rgba(128, 128, 128, 0.25);
        border-radius: 10px;
        margin-bottom: 1.2rem;
    }

    .case-box {
        padding: 0.9rem 1.1rem;
        border: 1px solid
            rgba(128, 128, 128, 0.25);
        border-radius: 10px;
        margin-bottom: 1rem;
    }

    .annotation-help {
        padding: 0.85rem 1rem;
        border: 1px solid
            rgba(128, 128, 128, 0.25);
        border-radius: 10px;
        margin-bottom: 1rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LOGIN
# ============================================================

if not st.session_state.authenticated:

    st.markdown(
        '<div class="login-title">'
        'Sistema de anotación radiográfica'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="login-subtitle">'
        'Proyecto MURA · Trabajo Terminal'
        '</div>',
        unsafe_allow_html=True,
    )

    left, center, right = st.columns(
        [1, 1.4, 1]
    )

    with center:

        st.subheader("Acceso de especialista")

        st.write(
            "Introduce el código de acceso "
            "que te fue proporcionado."
        )

        with st.form(
            "login_form",
            clear_on_submit=False,
        ):

            access_code = st.text_input(
                "Código de acceso",
                type="password",
                placeholder="MURA-XXXX-XXXX-XXXX",
                autocomplete="off",
            )

            submitted = (
                st.form_submit_button(
                    "Ingresar",
                    use_container_width=True,
                    type="primary",
                )
            )

        if submitted:

            if not normalize_access_code(
                access_code
            ):

                st.warning(
                    "Introduce tu código de acceso."
                )

            else:

                with st.spinner(
                    "Verificando acceso..."
                ):

                    specialist = (
                        authenticate_specialist(
                            access_code
                        )
                    )

                if specialist is None:

                    st.error(
                        "Código de acceso "
                        "incorrecto."
                    )

                else:

                    login_specialist(
                        specialist
                    )
                    st.rerun()

    st.stop()


# ============================================================
# CABECERA
# ============================================================

title_col, logout_col = st.columns(
    [5, 1]
)

with title_col:

    st.title(
        "Sistema de anotación radiográfica"
    )

with logout_col:

    if st.button(
        "Cerrar sesión",
        use_container_width=True,
    ):
        logout_specialist()
        st.rerun()


st.markdown(
    f"""
    <div class="session-box">
        <strong>Sesión activa:</strong>
        {st.session_state.display_name}
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# RECUPERAR LOTE
# ============================================================

try:

    assignments = (
        get_specialist_assignments(
            st.session_state.specialist_id
        )
    )

except Exception:

    st.error(
        "No fue posible recuperar tu lote "
        "de radiografías."
    )

    st.stop()


expected_count = EXPECTED_ASSIGNMENTS.get(
    st.session_state.specialist_code
)

if (
    expected_count is None
    or len(assignments) != expected_count
):

    st.error(
        "El número de casos asignados no "
        "coincide con la configuración "
        "esperada."
    )

    st.stop()


# ============================================================
# CONFIRMACIÓN DE GUARDADO
# ============================================================

if st.session_state.pop(
    "draft_saved_successfully",
    False,
):
    st.success(
        "Borrador guardado correctamente. "
        "Las respuestas y regiones marcadas "
        "se han guardado."
    )


# ============================================================
# PROGRESO
# ============================================================

status_counts = Counter(
    assignment["status"]
    for assignment in assignments
)

total = len(assignments)

pending = status_counts.get(
    "PENDING",
    0,
)

in_progress = status_counts.get(
    "IN_PROGRESS",
    0,
)

completed = status_counts.get(
    "COMPLETED",
    0,
)

flagged = status_counts.get(
    "FLAGGED",
    0,
)

st.subheader("Progreso")

p1, p2, p3, p4 = st.columns(4)

p1.metric("Total", total)
p2.metric("Pendientes", pending)
p3.metric("En progreso", in_progress)
p4.metric("Completadas", completed)

progress_value = (
    completed / total
    if total
    else 0
)

st.progress(progress_value)

st.caption(
    f"{completed} de {total} evaluaciones "
    f"completadas "
    f"({progress_value * 100:.1f}%)."
)

if flagged:
    st.warning(
        "Casos marcados para revisión: "
        f"{flagged}"
    )


# ============================================================
# SIGUIENTE ASIGNACIÓN
# ============================================================

remaining = [
    assignment
    for assignment in assignments
    if assignment["status"]
    in {
        "PENDING",
        "IN_PROGRESS",
        "FLAGGED",
    }
]

if not remaining:

    st.success(
        "Has completado todas las "
        "radiografías asignadas."
    )

    st.stop()


# Orden estable según el orden asignado al especialista.
remaining = sorted(
    remaining,
    key=lambda assignment: (
        assignment["presentation_order"]
    ),
)

remaining_ids = {
    assignment["id"]
    for assignment in remaining
}

current_assignment_id = (
    st.session_state.current_assignment_id
)

# Si todavía no hay un caso seleccionado, intentamos
# reanudar primero una evaluación IN_PROGRESS.
if (
    current_assignment_id is None
    or current_assignment_id not in remaining_ids
):

    in_progress_cases = [
        assignment
        for assignment in remaining
        if assignment["status"]
        == "IN_PROGRESS"
    ]

    if in_progress_cases:
        next_assignment = in_progress_cases[0]
    else:
        next_assignment = remaining[0]

    st.session_state.current_assignment_id = (
        next_assignment["id"]
    )

else:

    next_assignment = next(
        assignment
        for assignment in remaining
        if assignment["id"]
        == current_assignment_id
    )


# ============================================================
# CASO ACTUAL
# ============================================================

try:

    current_case = get_case(
        next_assignment["case_id"]
    )

except Exception:

    st.error(
        "No fue posible recuperar los "
        "datos de la radiografía."
    )

    st.stop()


if current_case is None:

    st.error(
        "No se encontró el caso asignado."
    )

    st.stop()


try:

    initialize_form_for_assignment(
        next_assignment["id"]
    )

    initialize_bbox_state(
        next_assignment["id"]
    )

except Exception:

    st.error(
        "No fue posible recuperar la "
        "anotación del caso."
    )

    st.stop()


# ============================================================
# RADIOGRAFÍA
# ============================================================

try:

    image_bytes = download_radiograph(
        current_case["storage_path"]
    )

except Exception:

    st.error(
        "No fue posible cargar la "
        "radiografía."
    )

    st.stop()


if not image_bytes:

    st.error(
        "La radiografía descargada está "
        "vacía."
    )

    st.stop()


try:

    local_image_path = (
        prepare_local_radiograph(
            image_bytes,
            current_case[
                "image_filename"
            ],
        )
    )

    (
        original_width,
        original_height,
    ) = get_image_dimensions(
        image_bytes
    )

    (
        display_image_path,
        display_width,
        display_height,
        display_scale,
    ) = prepare_display_radiograph(
        image_bytes,
        current_case["image_filename"],
        target_long_side=1200,
    )

    (
        viewer_width,
        viewer_height,
    ) = get_annotation_viewer_size(
        display_width,
        display_height,
    )

except Exception:

    st.error(
        "No fue posible preparar la "
        "radiografía para su evaluación."
    )

    st.stop()


# ============================================================
# INTERFAZ DE EVALUACIÓN
# ============================================================

st.divider()

region_name = (
    current_case["region"]
    .replace("XR_", "")
    .replace("_", " ")
    .title()
)

status_text = (
    " · Borrador guardado"
    if next_assignment["status"] == "IN_PROGRESS"
    else ""
)

st.markdown(
    f"""
    <div class="case-box">
        <strong>Evaluación {next_assignment['presentation_order']} de {total}</strong>
        &nbsp;·&nbsp; {region_name}{status_text}
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# FORMULARIO CLÍNICO COMPACTO
# ============================================================
# Los controles están dentro de un formulario para evitar que cada
# selección vuelva a ejecutar toda la aplicación y haga parpadear
# la radiografía. Los cambios se aplican juntos con un solo botón.

st.markdown("### Hallazgos")
st.caption(
    "Selecciona los cuatro estados y pulsa “Aplicar hallazgos”. "
    "Si marcas alguno como Presente, se habilitará su delimitación "
    "en la radiografía."
)

status_options = [
    "Seleccionar...",
    "Presente",
    "Ausente",
    "Indeterminado",
]

with st.form(
    key=f"clinical_form_{next_assignment['id']}",
    clear_on_submit=False,
):
    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        fracture_status_form = st.selectbox(
            "Fractura",
            status_options,
            key="fracture_status",
        )

    with row1_col2:
        degenerative_status_form = st.selectbox(
            "Cambios degenerativos",
            status_options,
            key="degenerative_status",
        )

    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        hardware_status_form = st.selectbox(
            "Material quirúrgico",
            status_options,
            key="hardware_status",
        )

    with row2_col2:
        other_status_form = st.selectbox(
            "Otro hallazgo",
            status_options,
            key="other_status",
        )

    details_col, evaluable_col = st.columns([2, 1])

    with details_col:
        other_description_form = st.text_input(
            "Descripción de otro hallazgo",
            placeholder="Solo si seleccionaste Otro hallazgo: Presente",
            key="other_description",
        )

    with evaluable_col:
        not_evaluable_form = st.checkbox(
            "Radiografía no evaluable",
            key="not_evaluable",
        )

    with st.expander("Comentarios adicionales", expanded=False):
        comments_form = st.text_area(
            "Comentarios (opcional)",
            placeholder="Observaciones relevantes para este caso...",
            key="comments",
            label_visibility="collapsed",
            height=80,
        )

    apply_findings = st.form_submit_button(
        "Aplicar hallazgos",
        use_container_width=True,
        type="primary",
    )

# Fuera del formulario utilizamos siempre el estado ya confirmado por
# Streamlit. El submit produce un único rerun para todas las respuestas.
fracture_status = st.session_state.get(
    "fracture_status", "Seleccionar..."
)
degenerative_status = st.session_state.get(
    "degenerative_status", "Seleccionar..."
)
hardware_status = st.session_state.get(
    "hardware_status", "Seleccionar..."
)
other_status = st.session_state.get(
    "other_status", "Seleccionar..."
)
other_description = st.session_state.get(
    "other_description", ""
)
not_evaluable = bool(
    st.session_state.get("not_evaluable", False)
)
comments = st.session_state.get("comments", "")


# ============================================================
# HALLAZGOS ACTIVOS PARA BBOX
# ============================================================

active_findings = get_present_findings(
    fracture_status,
    degenerative_status,
    hardware_status,
    other_status,
)

if not_evaluable:
    active_findings = []

remove_inactive_boxes(active_findings)


# ============================================================
# VISOR GRANDE
# ============================================================

st.markdown("### Radiografía")

if not active_findings:
    st.image(
        display_image_path,
        width="stretch",
    )

    if not_evaluable:
        st.caption(
            "Caso marcado como no evaluable; no es necesario "
            "señalar regiones."
        )
    else:
        st.caption(
            "Marca un hallazgo como Presente y pulsa “Aplicar hallazgos” "
            "para habilitar la delimitación de regiones."
        )

else:
    with st.expander(
        "Instrucciones para marcar regiones",
        expanded=False,
    ):
        st.markdown(
            """
1. Selecciona en el visor el **tipo de hallazgo**.
2. Arrastra para dibujar una caja ajustada a la región relevante.
3. Usa **Transform** para mover o cambiar el tamaño de una caja.
4. Usa **Del** para eliminar una caja.
5. Si hay regiones separadas, puedes dibujar varias cajas.

**Criterios:** fractura → alteración ósea directamente relacionada; cambios degenerativos → articulación o región afectada; material quirúrgico → material relevante; otro hallazgo → región que sustenta la descripción.
            """
        )

    initial_bboxes, initial_labels = prepare_boxes_for_component(
        active_findings,
        display_scale=display_scale,
    )

    component_result = detection(
        image_path=display_image_path,
        label_list=active_findings,
        bboxes=initial_bboxes,
        labels=initial_labels,
        height=viewer_height,
        width=viewer_width,
        line_width=3.0,
        use_space=False,
        key=f"bbox_{next_assignment['id']}",
    )

    update_bbox_state_from_component(
        component_result,
        active_findings,
        display_scale=display_scale,
    )

    box_counts = count_boxes_by_finding()
    region_summary = []

    for finding in active_findings:
        count = box_counts.get(finding, 0)
        if count:
            region_summary.append(f"✓ {finding}: {count}")
        else:
            region_summary.append(f"○ {finding}: falta región")

    st.caption(" · ".join(region_summary))


# ============================================================
# PREPARAR COORDENADAS INTERNAMENTE
# ============================================================

database_boxes = convert_boxes_for_database(
    original_width,
    original_height,
)


# ============================================================
# NAVEGACIÓN ENTRE CASOS
# ============================================================

current_remaining_index = next(
    (
        index
        for index, assignment in enumerate(remaining)
        if assignment["id"] == next_assignment["id"]
    ),
    0,
)

has_previous_case = current_remaining_index > 0
has_next_case = current_remaining_index < len(remaining) - 1


def navigate_to_assignment(target_assignment_id):
    """Guarda si el formulario es válido y cambia de caso."""

    errors = validate_form(
        fracture_status,
        degenerative_status,
        hardware_status,
        other_status,
        other_description,
        not_evaluable,
    )

    saved_before_navigation = False

    if not errors:
        try:
            save_draft(
                assignment_id=next_assignment["id"],
                specialist_id=st.session_state.specialist_id,
                fracture_status=fracture_status,
                degenerative_status=degenerative_status,
                hardware_status=hardware_status,
                other_status=other_status,
                other_description=other_description,
                not_evaluable=not_evaluable,
                comments=comments,
                bboxes=database_boxes,
            )
            saved_before_navigation = True
        except Exception as e:
            print(
                "ERROR GUARDANDO ANTES DE NAVEGAR:",
                type(e).__name__,
                str(e),
                flush=True,
            )
            return False, False, [
                "No fue posible guardar el caso actual antes de cambiar "
                "de radiografía."
            ]

    st.session_state.current_assignment_id = target_assignment_id
    st.session_state.loaded_assignment_id = None
    st.session_state.bbox_assignment_id = None
    st.session_state.bbox_items = []
    st.session_state.confirm_finalize = False

    return True, saved_before_navigation, []


# ============================================================
# ACCIONES COMPACTAS
# ============================================================

st.divider()

prev_col, save_col, finish_col, next_col = st.columns(
    [1, 1.25, 1.25, 1]
)

with prev_col:
    previous_clicked = st.button(
        "← Anterior",
        use_container_width=True,
        disabled=not has_previous_case,
    )

with save_col:
    save_clicked = st.button(
        "Guardar borrador",
        use_container_width=True,
    )

with finish_col:
    finalize_clicked = st.button(
        "Finalizar",
        type="primary",
        use_container_width=True,
    )

with next_col:
    next_clicked = st.button(
        "Siguiente →",
        use_container_width=True,
        disabled=not has_next_case,
    )


if previous_clicked or next_clicked:
    if previous_clicked:
        target_assignment = remaining[current_remaining_index - 1]
    else:
        target_assignment = remaining[current_remaining_index + 1]

    success, saved_before_navigation, navigation_errors = (
        navigate_to_assignment(target_assignment["id"])
    )

    if success:
        if saved_before_navigation:
            st.session_state["draft_saved_successfully"] = True
        st.rerun()

    for error in navigation_errors:
        st.error(error)


if save_clicked:
    errors = validate_form(
        fracture_status,
        degenerative_status,
        hardware_status,
        other_status,
        other_description,
        not_evaluable,
    )

    if errors:
        for error in errors:
            st.error(error)
    else:
        try:
            with st.spinner("Guardando..."):
                save_draft(
                    assignment_id=next_assignment["id"],
                    specialist_id=st.session_state.specialist_id,
                    fracture_status=fracture_status,
                    degenerative_status=degenerative_status,
                    hardware_status=hardware_status,
                    other_status=other_status,
                    other_description=other_description,
                    not_evaluable=not_evaluable,
                    comments=comments,
                    bboxes=database_boxes,
                )
            # Evita un rerun adicional solo para mostrar el mensaje.
            st.success("Borrador guardado correctamente.")
        except Exception as e:
            print(
                "ERROR GUARDANDO BORRADOR:",
                type(e).__name__,
                str(e),
                flush=True,
            )
            st.error("No fue posible guardar el borrador.")


if finalize_clicked:
    errors = validate_form(
        fracture_status,
        degenerative_status,
        hardware_status,
        other_status,
        other_description,
        not_evaluable,
    )

    if errors:
        for error in errors:
            st.error(error)
    else:
        box_counts = count_boxes_by_finding()
        missing_boxes = [
            finding
            for finding in active_findings
            if box_counts.get(finding, 0) == 0
        ]

        if missing_boxes:
            st.error(
                "Antes de finalizar, debes marcar al menos una región "
                "para cada hallazgo presente."
            )
            st.caption("Falta: " + ", ".join(missing_boxes))
        else:
            st.session_state.confirm_finalize = True
            st.rerun()


if st.session_state.confirm_finalize:
    st.warning(
        "¿Confirmas que deseas finalizar esta evaluación? "
        "Una vez finalizada, no podrás modificarla desde la interfaz."
    )

    confirm_col, cancel_col = st.columns(2)

    with confirm_col:
        confirm_clicked = st.button(
            "Sí, finalizar",
            type="primary",
            use_container_width=True,
        )

    with cancel_col:
        cancel_clicked = st.button(
            "Cancelar",
            use_container_width=True,
        )

    if cancel_clicked:
        st.session_state.confirm_finalize = False
        st.rerun()

    if confirm_clicked:
        try:
            with st.spinner("Finalizando evaluación..."):
                finalize_evaluation(
                    assignment_id=next_assignment["id"],
                    specialist_id=st.session_state.specialist_id,
                    fracture_status=fracture_status,
                    degenerative_status=degenerative_status,
                    hardware_status=hardware_status,
                    other_status=other_status,
                    other_description=other_description,
                    not_evaluable=not_evaluable,
                    comments=comments,
                    bboxes=database_boxes,
                )

            st.session_state.confirm_finalize = False
            st.session_state["evaluation_completed_successfully"] = True
            st.session_state.loaded_assignment_id = None
            st.session_state.bbox_assignment_id = None
            st.session_state.bbox_items = []
            st.session_state.current_assignment_id = None
            st.rerun()

        except Exception as e:
            print(
                "ERROR FINALIZANDO EVALUACIÓN:",
                type(e).__name__,
                str(e),
                flush=True,
            )
            st.error(
                "No fue posible finalizar la evaluación. "
                "El caso no fue marcado como completado."
            )

