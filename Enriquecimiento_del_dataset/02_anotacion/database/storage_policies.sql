-- ============================================================
-- TRABAJO TERMINAL
-- Políticas de Supabase Storage
-- Bucket privado: mura-radiographs
-- ============================================================


-- ============================================================
-- LECTURA DE RADIOGRAFÍAS ASIGNADAS
--
-- Los archivos se almacenarán con nombres:
--
-- MURA_TT_0001.png
-- MURA_TT_0002.png
-- ...
-- MURA_TT_2000.png
--
-- La columna cases.storage_path contendrá exactamente
-- el nombre/ruta del archivo dentro del bucket.
--
-- Un especialista autenticado podrá leer una imagen
-- solamente si existe una asignación de ese caso para él.
-- ============================================================

CREATE POLICY "radiographs_select_assigned"
ON storage.objects
FOR SELECT
TO authenticated
USING (
    bucket_id = 'mura-radiographs'
    AND EXISTS (
        SELECT 1
        FROM public.cases c
        JOIN public.assignments a
          ON a.case_id = c.id
        WHERE c.storage_path = storage.objects.name
          AND a.specialist_id = public.current_specialist_id()
    )
);


-- ============================================================
-- SEGURIDAD
--
-- No se crean políticas INSERT, UPDATE ni DELETE para
-- authenticated.
--
-- Por lo tanto, los especialistas no podrán:
--
-- - subir radiografías;
-- - reemplazar radiografías;
-- - modificar archivos;
-- - eliminar radiografías.
--
-- La carga inicial será realizada administrativamente.
-- ============================================================
