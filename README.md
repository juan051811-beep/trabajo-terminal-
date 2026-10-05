# Trabajo Terminal

Repositorio para el desarrollo del Trabajo Terminal enfocado en el análisis de radiografías musculoesqueléticas mediante técnicas de aprendizaje profundo e interpretabilidad visual.

## Estructura del repositorio

### Enriquecimiento del dataset

Esta sección contiene el proceso utilizado para seleccionar y enriquecer un subconjunto del conjunto de datos MURA.

El proceso se divide en cuatro etapas:

1. **Muestreo:** selección de un subconjunto de radiografías anormales procurando diversidad visual y anatómica.
2. **Anotación:** revisión de las radiografías seleccionadas por especialistas y registro de hallazgos y regiones de interés.
3. **Consenso:** análisis de concordancia y generación de etiquetas de consenso para los casos evaluados por múltiples especialistas.
4. **Dataset enriquecido:** integración de las etiquetas clínicas y anotaciones espaciales obtenidas durante el proceso.

## Dataset

El proyecto utiliza el conjunto de datos MURA (Musculoskeletal Radiographs).

Las imágenes originales del conjunto de datos no se distribuyen en este repositorio. El repositorio contiene código, documentación y archivos derivados necesarios para documentar y reproducir la metodología desarrollada.

## Organización

Enriquecimiento del dataset/
├── 01_muestreo/
├── 02_anotacion/
├── 03_consenso/
└── 04_dataset_enriquecido
