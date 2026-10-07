# Muestreo del dataset MURA

Esta carpeta contiene los archivos correspondientes al proceso de selección del subconjunto de radiografías utilizado para la etapa de enriquecimiento del dataset.

El proceso parte de las radiografías anormales del conjunto de entrenamiento de MURA y busca obtener un subconjunto con diversidad anatómica y visual para su posterior revisión por especialistas.

## Estructura

- `notebook/`: notebook utilizado para desarrollar y ejecutar el proceso de muestreo.
- `metadata/`: metadatos generados durante el análisis y preparación del conjunto MURA.
- `clustering/`: resultados de la evaluación y estabilidad del proceso de agrupamiento.
- `sampling_final/`: resultado final congelado del muestreo y archivos necesarios para continuar con la etapa de anotación.
- `documentacion/`: documentación complementaria de la metodología de muestreo.

## Resultado del muestreo

El proceso produjo un subconjunto final de 2,000 radiografías anormales provenientes del conjunto de entrenamiento de MURA.

La selección considera las siete regiones anatómicas disponibles en MURA y utiliza agrupamiento sobre representaciones visuales obtenidas mediante una red neuronal convolucional preentrenada.

El agrupamiento se utiliza como mecanismo para favorecer la diversidad visual del subconjunto y no debe interpretarse como una agrupación de patologías o diagnósticos clínicos.

El subconjunto final constituye la entrada para la etapa de anotación por especialistas.

## Importante

Las imágenes originales del dataset MURA no se almacenan ni distribuyen dentro de este repositorio.

Los archivos contenidos en esta carpeta corresponden a código, metadatos, resultados derivados y documentación necesarios para mantener la trazabilidad y reproducibilidad del proceso.
