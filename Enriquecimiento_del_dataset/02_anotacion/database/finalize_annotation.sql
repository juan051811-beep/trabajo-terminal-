CREATE OR REPLACE FUNCTION public.finalize_annotation(
    p_assignment_id BIGINT,
    p_specialist_id BIGINT,
    p_fracture_status TEXT,
    p_degenerative_status TEXT,
    p_hardware_status TEXT,
    p_other_status TEXT,
    p_other_description TEXT,
    p_not_evaluable BOOLEAN,
    p_comments TEXT,
    p_bboxes JSONB DEFAULT '[]'::JSONB
)
RETURNS BIGINT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_assignment public.assignments%ROWTYPE;
    v_annotation_id BIGINT;

    v_bbox JSONB;

    v_finding_type TEXT;
    v_bbox_index INTEGER;

    v_x_min DOUBLE PRECISION;
    v_y_min DOUBLE PRECISION;
    v_x_max DOUBLE PRECISION;
    v_y_max DOUBLE PRECISION;

    v_image_width INTEGER;
    v_image_height INTEGER;

    v_fracture_boxes INTEGER := 0;
    v_degenerative_boxes INTEGER := 0;
    v_hardware_boxes INTEGER := 0;
    v_other_boxes INTEGER := 0;
BEGIN

    ------------------------------------------------------------
    -- 1. VERIFICAR ASIGNACIÓN
    ------------------------------------------------------------

    SELECT *
    INTO v_assignment
    FROM public.assignments
    WHERE id = p_assignment_id
      AND specialist_id = p_specialist_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'La asignación no pertenece al especialista.';
    END IF;


    ------------------------------------------------------------
    -- 2. IMPEDIR DOBLE FINALIZACIÓN
    ------------------------------------------------------------

    IF v_assignment.status = 'COMPLETED' THEN
        RAISE EXCEPTION
            'La evaluación ya fue finalizada.';
    END IF;


    ------------------------------------------------------------
    -- 3. VALIDAR ESTADOS CLÍNICOS
    ------------------------------------------------------------

    IF p_fracture_status NOT IN (
        'PRESENT',
        'ABSENT',
        'INDETERMINATE'
    ) THEN
        RAISE EXCEPTION
            'Debe indicar el estado de fractura.';
    END IF;


    IF p_degenerative_status NOT IN (
        'PRESENT',
        'ABSENT',
        'INDETERMINATE'
    ) THEN
        RAISE EXCEPTION
            'Debe indicar el estado de cambios degenerativos.';
    END IF;


    IF p_hardware_status NOT IN (
        'PRESENT',
        'ABSENT',
        'INDETERMINATE'
    ) THEN
        RAISE EXCEPTION
            'Debe indicar el estado de material quirúrgico.';
    END IF;


    IF p_other_status NOT IN (
        'PRESENT',
        'ABSENT',
        'INDETERMINATE'
    ) THEN
        RAISE EXCEPTION
            'Debe indicar el estado de otro hallazgo.';
    END IF;


    ------------------------------------------------------------
    -- 4. VALIDAR OTRO HALLAZGO
    ------------------------------------------------------------

    IF (
        p_other_status = 'PRESENT'
        AND NULLIF(
            BTRIM(p_other_description),
            ''
        ) IS NULL
    ) THEN
        RAISE EXCEPTION
            'Otro hallazgo requiere una descripción.';
    END IF;


    ------------------------------------------------------------
    -- 5. VALIDAR NO EVALUABLE
    ------------------------------------------------------------

    IF p_not_evaluable THEN

        IF p_fracture_status IN ('PRESENT', 'ABSENT')
           OR p_degenerative_status IN ('PRESENT', 'ABSENT')
           OR p_hardware_status IN ('PRESENT', 'ABSENT')
           OR p_other_status IN ('PRESENT', 'ABSENT')
        THEN
            RAISE EXCEPTION
                'Un caso no evaluable no puede contener hallazgos presentes o ausentes.';
        END IF;

    END IF;


    ------------------------------------------------------------
    -- 6. VALIDAR JSON DE BOUNDING BOXES
    ------------------------------------------------------------

    IF p_bboxes IS NULL THEN
        p_bboxes := '[]'::JSONB;
    END IF;

    IF jsonb_typeof(p_bboxes) <> 'array' THEN
        RAISE EXCEPTION
            'Las regiones de interés tienen un formato inválido.';
    END IF;


    ------------------------------------------------------------
    -- 7. VALIDAR CADA BOUNDING BOX Y CONTARLAS
    ------------------------------------------------------------

    FOR v_bbox IN
        SELECT value
        FROM jsonb_array_elements(p_bboxes)
    LOOP

        v_finding_type =
            v_bbox ->> 'finding_type';

        v_bbox_index =
            (v_bbox ->> 'bbox_index')::INTEGER;

        v_x_min =
            (v_bbox ->> 'x_min')::DOUBLE PRECISION;

        v_y_min =
            (v_bbox ->> 'y_min')::DOUBLE PRECISION;

        v_x_max =
            (v_bbox ->> 'x_max')::DOUBLE PRECISION;

        v_y_max =
            (v_bbox ->> 'y_max')::DOUBLE PRECISION;

        v_image_width =
            (v_bbox ->> 'image_width')::INTEGER;

        v_image_height =
            (v_bbox ->> 'image_height')::INTEGER;


        IF v_finding_type NOT IN (
            'FRACTURE',
            'DEGENERATIVE',
            'HARDWARE',
            'OTHER'
        ) THEN
            RAISE EXCEPTION
                'Existe una región con un tipo de hallazgo inválido.';
        END IF;


        IF v_bbox_index IS NULL
           OR v_bbox_index <= 0
        THEN
            RAISE EXCEPTION
                'Existe una región con un índice inválido.';
        END IF;


        IF v_image_width IS NULL
           OR v_image_height IS NULL
           OR v_image_width <= 0
           OR v_image_height <= 0
        THEN
            RAISE EXCEPTION
                'Existen dimensiones de imagen inválidas.';
        END IF;


        --------------------------------------------------------
        -- Coordenadas normalizadas entre 0 y 1
        --------------------------------------------------------

        IF NOT (
            0 <= v_x_min
            AND v_x_min < v_x_max
            AND v_x_max <= 1
            AND 0 <= v_y_min
            AND v_y_min < v_y_max
            AND v_y_max <= 1
        ) THEN
            RAISE EXCEPTION
                'Existe una región con coordenadas inválidas.';
        END IF;


        --------------------------------------------------------
        -- La caja debe corresponder a un hallazgo PRESENT
        --------------------------------------------------------

        IF (
            v_finding_type = 'FRACTURE'
            AND p_fracture_status <> 'PRESENT'
        )
        OR (
            v_finding_type = 'DEGENERATIVE'
            AND p_degenerative_status <> 'PRESENT'
        )
        OR (
            v_finding_type = 'HARDWARE'
            AND p_hardware_status <> 'PRESENT'
        )
        OR (
            v_finding_type = 'OTHER'
            AND p_other_status <> 'PRESENT'
        )
        THEN
            RAISE EXCEPTION
                'Existe una región asociada a un hallazgo que no está marcado como presente.';
        END IF;


        --------------------------------------------------------
        -- CONTAR CAJAS POR HALLAZGO
        --------------------------------------------------------

        CASE v_finding_type

            WHEN 'FRACTURE' THEN
                v_fracture_boxes :=
                    v_fracture_boxes + 1;

            WHEN 'DEGENERATIVE' THEN
                v_degenerative_boxes :=
                    v_degenerative_boxes + 1;

            WHEN 'HARDWARE' THEN
                v_hardware_boxes :=
                    v_hardware_boxes + 1;

            WHEN 'OTHER' THEN
                v_other_boxes :=
                    v_other_boxes + 1;

        END CASE;

    END LOOP;


    ------------------------------------------------------------
    -- 8. EXIGIR CAJA PARA CADA HALLAZGO PRESENTE
    ------------------------------------------------------------

    IF (
        p_fracture_status = 'PRESENT'
        AND v_fracture_boxes = 0
    ) THEN
        RAISE EXCEPTION
            'Debe marcar al menos una región para la fractura.';
    END IF;


    IF (
        p_degenerative_status = 'PRESENT'
        AND v_degenerative_boxes = 0
    ) THEN
        RAISE EXCEPTION
            'Debe marcar al menos una región para los cambios degenerativos.';
    END IF;


    IF (
        p_hardware_status = 'PRESENT'
        AND v_hardware_boxes = 0
    ) THEN
        RAISE EXCEPTION
            'Debe marcar al menos una región para el material quirúrgico.';
    END IF;


    IF (
        p_other_status = 'PRESENT'
        AND v_other_boxes = 0
    ) THEN
        RAISE EXCEPTION
            'Debe marcar al menos una región para el otro hallazgo.';
    END IF;


    ------------------------------------------------------------
    -- 9. NO EVALUABLE NO DEBE TENER CAJAS
    ------------------------------------------------------------

    IF (
        p_not_evaluable
        AND jsonb_array_length(p_bboxes) > 0
    ) THEN
        RAISE EXCEPTION
            'Un caso no evaluable no debe contener regiones marcadas.';
    END IF;


    ------------------------------------------------------------
    -- 10. GUARDAR ANOTACIÓN
    ------------------------------------------------------------

    INSERT INTO public.annotations (
        assignment_id,
        fracture_status,
        degenerative_status,
        hardware_status,
        other_status,
        other_description,
        not_evaluable,
        comments
    )
    VALUES (
        p_assignment_id,
        p_fracture_status,
        p_degenerative_status,
        p_hardware_status,
        p_other_status,
        NULLIF(
            BTRIM(p_other_description),
            ''
        ),
        p_not_evaluable,
        NULLIF(
            BTRIM(p_comments),
            ''
        )
    )
    ON CONFLICT (assignment_id)
    DO UPDATE SET
        fracture_status = EXCLUDED.fracture_status,
        degenerative_status = EXCLUDED.degenerative_status,
        hardware_status = EXCLUDED.hardware_status,
        other_status = EXCLUDED.other_status,
        other_description = EXCLUDED.other_description,
        not_evaluable = EXCLUDED.not_evaluable,
        comments = EXCLUDED.comments,
        updated_at = NOW()
    RETURNING id
    INTO v_annotation_id;


    ------------------------------------------------------------
    -- 11. REEMPLAZAR BOUNDING BOXES
    ------------------------------------------------------------

    DELETE FROM public.bounding_boxes
    WHERE annotation_id = v_annotation_id;


    FOR v_bbox IN
        SELECT value
        FROM jsonb_array_elements(p_bboxes)
    LOOP

        INSERT INTO public.bounding_boxes (
            annotation_id,
            finding_type,
            bbox_index,
            x_min,
            y_min,
            x_max,
            y_max,
            image_width,
            image_height
        )
        VALUES (
            v_annotation_id,
            v_bbox ->> 'finding_type',
            (v_bbox ->> 'bbox_index')::INTEGER,
            (v_bbox ->> 'x_min')::DOUBLE PRECISION,
            (v_bbox ->> 'y_min')::DOUBLE PRECISION,
            (v_bbox ->> 'x_max')::DOUBLE PRECISION,
            (v_bbox ->> 'y_max')::DOUBLE PRECISION,
            (v_bbox ->> 'image_width')::INTEGER,
            (v_bbox ->> 'image_height')::INTEGER
        );

    END LOOP;


    ------------------------------------------------------------
    -- 12. FINALIZAR ASSIGNMENT
    ------------------------------------------------------------

    UPDATE public.assignments
    SET
        status = 'COMPLETED',
        started_at = COALESCE(
            started_at,
            NOW()
        ),
        completed_at = NOW(),
        updated_at = NOW()
    WHERE id = p_assignment_id;


    RETURN v_annotation_id;

END;
$$;
