MURA_TT - RESUMEN DEL MUESTREO FINAL
====================================

Fecha de congelamiento:
2026-10-05 03:53:34

OBJETIVO
--------
Construir un subconjunto enriquecido de radiografías anormales
del conjunto de entrenamiento de MURA para posterior revisión
y anotación por especialistas.

UNIVERSO DE MUESTREO
--------------------
Dataset: MURA-v1.1
Split utilizado para clustering/muestreo: train
Clase utilizada: abnormal/positive

Radiografías anormales de train: 14,873
Estudios anormales de train: 5,177

El conjunto valid oficial de MURA NO fue utilizado para
clustering ni para seleccionar este subconjunto.

REPRESENTACIÓN VISUAL
---------------------
Extractor de características:
DenseNet121 preentrenada en ImageNet.

La capa clasificadora fue retirada y se utilizaron embeddings
visuales de 1024 dimensiones.

La red fue utilizada únicamente como extractor de
características visuales, no como clasificador clínico.

REDUCCIÓN DE DIMENSIONALIDAD
----------------------------
Se aplicó StandardScaler y PCA de forma independiente para
cada región anatómica.

Se conservaron componentes suficientes para explicar
aproximadamente el 95% de la varianza.

CLUSTERING
----------
Algoritmo: K-Means
Semilla principal: 42

K final por región:

XR_ELBOW:    6
XR_FINGER:   6
XR_FOREARM:  6
XR_HAND:     6
XR_HUMERUS:  4
XR_SHOULDER: 6
XR_WRIST:    9

Total de clusters: 43

La elección de K consideró:
- Silhouette Score
- Davies-Bouldin Index
- Calinski-Harabasz Index
- distribución de tamaños de cluster
- estabilidad mediante Adjusted Rand Index (ARI)
- inspección visual de representantes

Los clusters se utilizaron para representar diversidad visual.
No deben interpretarse como categorías diagnósticas.

ESTRATEGIA DE ASIGNACIÓN
------------------------
Tamaño objetivo del subconjunto: 2,000 radiografías.

Se utilizó una asignación híbrida por región que combinó:
- representación proporcional al tamaño de la región
- cobertura equilibrada entre regiones

Dentro de cada región se garantizó cobertura de los clusters
y posteriormente se distribuyó el resto de manera proporcional.

MUESTREO DENTRO DE CLUSTERS
---------------------------
Las imágenes fueron ordenadas según su distancia al centroide.

Zonas consideradas:

Central:
percentil de distancia 0-50.

Intermedia:
percentil de distancia 50-80.

Periférica:
percentil de distancia 80-95.

Extrema:
percentil 95-100, no priorizada para el muestreo ordinario.

Distribución final:

Central:
1200 imágenes
(60.00%)

Intermedia:
410 imágenes
(20.50%)

Periférica:
390 imágenes
(19.50%)

RESULTADO FINAL
---------------
Radiografías seleccionadas: 2000

Estudios únicos:
1980

Imágenes duplicadas:
0

Regiones anatómicas:
7

Clusters representados:
43

Se priorizó una imagen por estudio siempre que fue posible.

Los pocos estudios con múltiples imágenes seleccionadas
corresponden a clusters visuales pequeños en los que no había
suficientes estudios independientes para cubrir la cuota
establecida.

AUDITORÍA VISUAL
----------------
Se realizó una auditoría visual estratificada con ejemplos
centrales, intermedios y periféricos de los clusters finales.

La auditoría se utilizó para comprobar la coherencia visual
del muestreo y verificar que los casos periféricos no
correspondieran sistemáticamente a imágenes inutilizables.

INTERPRETACIÓN
--------------
Este subconjunto NO pretende preservar la prevalencia natural
de los hallazgos de MURA.

Se trata de una muestra enriquecida orientada a maximizar
cobertura anatómica y diversidad visual para la posterior
revisión por especialistas.

ARCHIVOS
--------
sampling_2000_internal.csv
    Manifiesto interno completo del muestreo.
    No entregar a los especialistas.

sampling_2000_handoff.csv
    Archivo simplificado para transferencia al responsable
    de la etapa posterior.

sampling_summary.csv
    Resumen del muestreo por región.

cluster_summary.csv
    Resumen de los 43 clusters seleccionados.

sampling_zone_summary.csv
    Distribución central/intermedia/periférica.

INTEGRIDAD
----------
SHA-256 de sampling_2000_internal.csv:

6e67b8ceb4f6fba5a689a1f7480d186e24371b208fede1417203bb13b6cc1857
