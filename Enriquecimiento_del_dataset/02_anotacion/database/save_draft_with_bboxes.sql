CREATE OR REPLACE FUNCTION public.save_annotation_draft_with_bboxes(
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
BEGIN

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

    IF v_assignment.status = 'COMPLETED' THEN
        RAISE EXCEPTION
            'La evaluación ya fue finalizada.';
    END IF;


    IF p_fracture_status NOT IN (
        'PRESENT',
        'ABSENT',
        'INDETERMINATE'
    ) THEN
        RAISE EXCEPTION
            'Estado de fractura inválido.';
    END IF;

    IF p_degenerative_status NOT IN (
        'PRESENT',
        'ABSENT',
        'INDETERMINATE'
    ) THEN
        RAISE EXCEPTION
            'Estado de cambios degenerativos inválido.';
    END IF;

    IF p_hardware_status NOT IN (
        'PRESENT',
        'ABSENT',
        'INDETERMINATE'
    ) THEN
        RAISE EXCEPTION
            'Estado de material quirúrgico inválido.';
    END IF;

    IF p_other_status NOT IN (
        'PRESENT',
        'ABSENT',
        'INDETERMINATE'
    ) THEN
        RAISE EXCEPTION
            'Estado de otro hallazgo inválido.';
    END IF;


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


    IF p_bboxes IS NULL THEN
        p_bboxes := '[]'::JSONB;
    END IF;

    IF jsonb_typeof(p_bboxes) <> 'array' THEN
        RAISE EXCEPTION
            'p_bboxes debe ser un arreglo JSON.';
    END IF;


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


    DELETE FROM public.bounding_boxes
    WHERE annotation_id = v_annotation_id;


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
                'Tipo de hallazgo inválido en bounding box.';
        END IF;


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
                'Existe una bounding box asociada a un hallazgo que no está marcado como PRESENT.';
        END IF;


        IF v_image_width <= 0
           OR v_image_height <= 0
        THEN
            RAISE EXCEPTION
                'Dimensiones de imagen inválidas.';
        END IF;


        IF NOT (
            0 <= v_x_min
            AND v_x_min < v_x_max
            AND v_x_max <= 1
            AND 0 <= v_y_min
            AND v_y_min < v_y_max
            AND v_y_max <= 1
        ) THEN
            RAISE EXCEPTION
                'Las coordenadas normalizadas de la bounding box deben estar entre 0 y 1.';
        END IF;


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
            v_finding_type,
            v_bbox_index,
            v_x_min,
            v_y_min,
            v_x_max,
            v_y_max,
            v_image_width,
            v_image_height
        );

    END LOOP;


    UPDATE public.assignments
    SET
        status = 'IN_PROGRESS',
        started_at = COALESCE(
            started_at,
            NOW()
        ),
        updated_at = NOW()
    WHERE id = p_assignment_id;


    RETURN v_annotation_id;

END;
$$;
