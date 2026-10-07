from pathlib import Path

import streamlit as st
from PIL import Image
from streamlit_image_annotation.Detection import detection


st.set_page_config(
    page_title="Prueba Bounding Boxes",
    page_icon="🩻",
    layout="wide",
)

st.title("Prueba de Bounding Boxes")
st.caption(
    "Prueba aislada de dibujo, coordenadas y persistencia. "
    "No modifica Supabase ni app.py."
)


# ============================================================
# RADIOGRAFÍA REAL
# ============================================================

IMAGE_DIR = Path.home() / "Desktop" / "MURA_TT_anotacion" / "imagenes"

images = sorted(IMAGE_DIR.glob("*.png"))

if not images:
    st.error(f"No se encontraron radiografías en: {IMAGE_DIR}")
    st.stop()

image_path = images[0]

try:
    with Image.open(image_path) as img:
        original_width, original_height = img.size
except Exception as exc:
    st.error(f"No se pudo abrir la imagen: {exc}")
    st.stop()


st.write(f"**Imagen:** `{image_path.name}`")
st.write(
    f"**Dimensiones originales:** "
    f"{original_width} × {original_height} px"
)


# ============================================================
# ETIQUETAS
# ============================================================

LABELS = [
    "Fractura",
    "Cambios degenerativos",
    "Material quirúrgico",
    "Otro hallazgo",
]


# ============================================================
# ESTADO DE LAS CAJAS
# ============================================================

if "test_saved_bboxes" not in st.session_state:
    st.session_state.test_saved_bboxes = []

if "test_saved_labels" not in st.session_state:
    st.session_state.test_saved_labels = []


# ============================================================
# COMPONENTE
# ============================================================

st.info(
    "Dibuja una o varias cajas. "
    "El componente devuelve cada bbox como [x, y, ancho, alto]."
)

result = detection(
    image_path=str(image_path),
    label_list=LABELS,
    bboxes=st.session_state.test_saved_bboxes,
    labels=st.session_state.test_saved_labels,
    height=450,
    width=450,
    line_width=3.0,
    use_space=False,
    key="bbox_persistence_test",
)


# ============================================================
# MOSTRAR RESULTADO CRUDO
# ============================================================

st.divider()
st.subheader("1. Resultado crudo del componente")

if result is None:
    current_result = []
    st.warning("El componente todavía no devolvió cajas.")
else:
    current_result = result
    st.write(f"**Número de cajas:** {len(current_result)}")
    st.json(current_result)


# ============================================================
# CONVERSIÓN CORRECTA
# ============================================================

st.subheader("2. Conversión a coordenadas para Supabase")

converted_boxes = []
invalid_boxes = []

for index, item in enumerate(current_result, start=1):

    bbox = item.get("bbox", [])

    if len(bbox) != 4:
        invalid_boxes.append(index)
        continue

    # El componente devuelve:
    # [x, y, width, height]
    x, y, bbox_width, bbox_height = map(float, bbox)

    # Permitimos que, internamente, alguna dimensión pudiera
    # llegar con signo negativo.
    x_min = min(x, x + bbox_width)
    y_min = min(y, y + bbox_height)
    x_max = max(x, x + bbox_width)
    y_max = max(y, y + bbox_height)

    x_min_norm = x_min / original_width
    y_min_norm = y_min / original_height
    x_max_norm = x_max / original_width
    y_max_norm = y_max / original_height

    valid = (
        0 <= x_min < x_max <= original_width
        and 0 <= y_min < y_max <= original_height
        and 0 <= x_min_norm < x_max_norm <= 1
        and 0 <= y_min_norm < y_max_norm <= 1
    )

    if not valid:
        invalid_boxes.append(index)

    converted_boxes.append(
        {
            "bbox_index": index,
            "finding": item.get("label"),
            "label_id": item.get("label_id"),

            "component_x": round(x, 3),
            "component_y": round(y, 3),
            "component_width": round(bbox_width, 3),
            "component_height": round(bbox_height, 3),

            "x_min_px": round(x_min, 3),
            "y_min_px": round(y_min, 3),
            "x_max_px": round(x_max, 3),
            "y_max_px": round(y_max, 3),

            "x_min_norm": round(x_min_norm, 6),
            "y_min_norm": round(y_min_norm, 6),
            "x_max_norm": round(x_max_norm, 6),
            "y_max_norm": round(y_max_norm, 6),

            "image_width": original_width,
            "image_height": original_height,

            "valid": valid,
        }
    )

if converted_boxes:
    st.json(converted_boxes)

    if invalid_boxes:
        st.error(
            f"Hay cajas inválidas: {invalid_boxes}"
        )
    else:
        st.success(
            "Todas las cajas tienen coordenadas válidas."
        )
else:
    st.caption("Dibuja alguna caja para comprobar la conversión.")


# ============================================================
# PRUEBA DE PERSISTENCIA
# ============================================================

st.divider()
st.subheader("3. Prueba de persistencia")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button(
        "💾 Guardar cajas en sesión",
        use_container_width=True,
    ):

        saved_bboxes = []
        saved_labels = []

        for item in current_result:
            bbox = item.get("bbox", [])
            label_id = item.get("label_id")

            if len(bbox) == 4 and label_id is not None:
                saved_bboxes.append(
                    [float(value) for value in bbox]
                )
                saved_labels.append(int(label_id))

        st.session_state.test_saved_bboxes = saved_bboxes
        st.session_state.test_saved_labels = saved_labels

        st.success(
            f"Guardadas {len(saved_bboxes)} cajas en la sesión."
        )


with col2:
    if st.button(
        "🔄 Forzar rerun",
        use_container_width=True,
    ):
        st.rerun()


with col3:
    if st.button(
        "🗑️ Borrar cajas guardadas",
        use_container_width=True,
    ):
        st.session_state.test_saved_bboxes = []
        st.session_state.test_saved_labels = []
        st.rerun()


st.write(
    "**Cajas actualmente guardadas en sesión:** "
    f"{len(st.session_state.test_saved_bboxes)}"
)

if st.session_state.test_saved_bboxes:
    st.write("**BBoxes guardadas:**")
    st.json(st.session_state.test_saved_bboxes)

    st.write("**Labels guardados:**")
    st.json(st.session_state.test_saved_labels)
