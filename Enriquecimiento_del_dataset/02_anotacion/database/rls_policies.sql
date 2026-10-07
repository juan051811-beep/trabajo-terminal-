-- ============================================================
-- TRABAJO TERMINAL
-- Políticas de Row Level Security (RLS)
-- Sistema de anotación MURA
-- ============================================================


-- ============================================================
-- 1. ACTIVAR RLS
-- ============================================================

ALTER TABLE specialists ENABLE ROW LEVEL SECURITY;
ALTER TABLE cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE annotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE bounding_boxes ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;


-- ============================================================
-- 2. FUNCIÓN AUXILIAR
--
-- Devuelve el ID interno del especialista correspondiente
-- al usuario autenticado mediante Supabase Auth.
--
-- SECURITY DEFINER evita problemas de recursión RLS cuando
-- otras políticas necesitan consultar specialists.
-- ============================================================

CREATE OR REPLACE FUNCTION public.current_specialist_id()
RETURNS BIGINT
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
    SELECT id
    FROM public.specialists
    WHERE auth_user_id = auth.uid()
      AND is_active = TRUE
    LIMIT 1;
$$;

REVOKE ALL ON FUNCTION public.current_specialist_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.current_specialist_id()
TO authenticated;


-- ============================================================
-- 3. SPECIALISTS
--
-- Cada especialista solamente puede consultar su propio
-- registro.
-- ============================================================

CREATE POLICY "specialists_select_own"
ON specialists
FOR SELECT
TO authenticated
USING (
    id = public.current_specialist_id()
);


-- ============================================================
-- 4. CASES
--
-- Un especialista únicamente puede consultar radiografías
-- que estén asignadas a él.
--
-- No se permite INSERT, UPDATE ni DELETE desde el cliente.
-- ============================================================

CREATE POLICY "cases_select_assigned"
ON cases
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM assignments a
        WHERE a.case_id = cases.id
          AND a.specialist_id = public.current_specialist_id()
    )
);


-- ============================================================
-- 5. ASSIGNMENTS
--
-- El especialista puede consultar sus propias asignaciones.
--
-- El cambio de estado se realizará posteriormente mediante
-- lógica controlada del backend, no mediante acceso general
-- del cliente.
-- ============================================================

CREATE POLICY "assignments_select_own"
ON assignments
FOR SELECT
TO authenticated
USING (
    specialist_id = public.current_specialist_id()
);


-- ============================================================
-- 6. ANNOTATIONS
--
-- El especialista puede consultar, crear y modificar
-- únicamente la anotación asociada con una asignación propia.
--
-- No puede eliminar anotaciones.
-- ============================================================

CREATE POLICY "annotations_select_own"
ON annotations
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM assignments a
        WHERE a.id = annotations.assignment_id
          AND a.specialist_id = public.current_specialist_id()
    )
);


CREATE POLICY "annotations_insert_own"
ON annotations
FOR INSERT
TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM assignments a
        WHERE a.id = annotations.assignment_id
          AND a.specialist_id = public.current_specialist_id()
    )
);


CREATE POLICY "annotations_update_own"
ON annotations
FOR UPDATE
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM assignments a
        WHERE a.id = annotations.assignment_id
          AND a.specialist_id = public.current_specialist_id()
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM assignments a
        WHERE a.id = annotations.assignment_id
          AND a.specialist_id = public.current_specialist_id()
    )
);


-- ============================================================
-- 7. BOUNDING BOXES
--
-- El especialista solamente puede consultar, crear,
-- modificar o eliminar cajas pertenecientes a sus propias
-- anotaciones.
--
-- DELETE sí se permite porque durante la anotación el
-- especialista debe poder borrar una caja mal dibujada.
-- ============================================================

CREATE POLICY "bounding_boxes_select_own"
ON bounding_boxes
FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM annotations an
        JOIN assignments a
          ON a.id = an.assignment_id
        WHERE an.id = bounding_boxes.annotation_id
          AND a.specialist_id = public.current_specialist_id()
    )
);


CREATE POLICY "bounding_boxes_insert_own"
ON bounding_boxes
FOR INSERT
TO authenticated
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM annotations an
        JOIN assignments a
          ON a.id = an.assignment_id
        WHERE an.id = bounding_boxes.annotation_id
          AND a.specialist_id = public.current_specialist_id()
    )
);


CREATE POLICY "bounding_boxes_update_own"
ON bounding_boxes
FOR UPDATE
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM annotations an
        JOIN assignments a
          ON a.id = an.assignment_id
        WHERE an.id = bounding_boxes.annotation_id
          AND a.specialist_id = public.current_specialist_id()
    )
)
WITH CHECK (
    EXISTS (
        SELECT 1
        FROM annotations an
        JOIN assignments a
          ON a.id = an.assignment_id
        WHERE an.id = bounding_boxes.annotation_id
          AND a.specialist_id = public.current_specialist_id()
    )
);


CREATE POLICY "bounding_boxes_delete_own"
ON bounding_boxes
FOR DELETE
TO authenticated
USING (
    EXISTS (
        SELECT 1
        FROM annotations an
        JOIN assignments a
          ON a.id = an.assignment_id
        WHERE an.id = bounding_boxes.annotation_id
          AND a.specialist_id = public.current_specialist_id()
    )
);


-- ============================================================
-- 8. AUDIT LOG
--
-- Los especialistas no necesitan consultar el historial
-- completo.
--
-- Se permite consultar únicamente sus propios registros.
-- La escritura del audit log se realizará mediante lógica
-- controlada del backend.
-- ============================================================

CREATE POLICY "audit_log_select_own"
ON audit_log
FOR SELECT
TO authenticated
USING (
    specialist_id = public.current_specialist_id()
);


-- ============================================================
-- RESULTADO
--
-- authenticated:
--
-- specialists       SELECT propio
-- cases             SELECT asignados
-- assignments       SELECT propios
-- annotations       SELECT / INSERT / UPDATE propias
-- bounding_boxes    SELECT / INSERT / UPDATE / DELETE propias
-- audit_log         SELECT propio
--
-- No existen políticas públicas para anon.
-- ============================================================
