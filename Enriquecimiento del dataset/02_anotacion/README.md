# Anotación y enriquecimiento por especialistas

Esta etapa corresponde al proceso de anotación clínica y espacial del subconjunto de 2,000 radiografías obtenido durante la etapa de muestreo.

El objetivo es desarrollar un sistema que permita a especialistas revisar las radiografías seleccionadas, identificar los hallazgos presentes y señalar las regiones de la imagen que sustentan dichos hallazgos.

## Entrada

La entrada de esta etapa corresponde al resultado congelado del proceso de muestreo ubicado en:

`../01_muestreo/sampling_final/`

El subconjunto está compuesto por 2,000 radiografías anormales provenientes del conjunto de entrenamiento de MURA.

## Distribución de casos

Participarán tres especialistas.

De las 2,000 radiografías:

- 100 serán evaluadas independientemente por los tres especialistas.
- Las 1,900 restantes serán distribuidas de forma exclusiva entre los tres especialistas.

La distribución prevista es:

| Especialista | Casos exclusivos | Casos compartidos | Evaluaciones |
|---|---:|---:|---:|
| Especialista 1 | 634 | 100 | 734 |
| Especialista 2 | 633 | 100 | 733 |
| Especialista 3 | 633 | 100 | 733 |

Esto produce un total de 2,200 evaluaciones sobre 2,000 radiografías únicas.

Los casos compartidos permitirán posteriormente analizar la concordancia entre especialistas y generar etiquetas mediante votación.

## Anotación clínica

La anotación permitirá registrar los siguientes tipos de hallazgo:

- Fractura.
- Cambios degenerativos.
- Material quirúrgico.
- Otro hallazgo.

Una radiografía podrá contener múltiples hallazgos.

Para evitar obligar al especialista a emitir una clasificación cuando la evidencia no sea suficiente, el sistema también contemplará estados de indeterminación y casos no evaluables.

Cuando se seleccione "otro hallazgo", se deberá proporcionar una descripción.

## Anotación espacial

Los especialistas podrán señalar las regiones de la radiografía asociadas con los hallazgos identificados mediante bounding boxes.

Las cajas serán utilizadas como referencias espaciales proporcionadas por especialistas y se almacenarán mediante coordenadas independientes de la imagen original.

La imagen radiográfica original nunca será modificada para incorporar las cajas.

Se permitirá:

- Dibujar múltiples bounding boxes en una misma imagen.
- Asociar cada bounding box con un tipo de hallazgo.
- Eliminar o modificar bounding boxes antes de completar la anotación.

Las cajas deberán ajustarse, en la medida de lo posible, a la región radiográfica que sustenta el hallazgo identificado, evitando abarcar estructuras no relacionadas.

## Casos compartidos

Las 100 radiografías compartidas serán evaluadas de manera independiente por los tres especialistas.

Durante el proceso de anotación, ningún especialista tendrá acceso a las respuestas de los demás.

La determinación del consenso se realizará posteriormente y de manera independiente para cada hallazgo.

Se conservarán siempre las anotaciones originales de cada especialista.

## Prevención de sesgo

La interfaz de anotación no mostrará información utilizada durante el proceso de muestreo que pueda influir en la evaluación clínica.

Los especialistas no tendrán acceso a:

- Cluster asignado.
- Distancia al centroide.
- Zona de muestreo.
- Etiqueta original de MURA.
- Predicciones de modelos.
- Mapas de activación.
- Anotaciones realizadas por otros especialistas.

## Persistencia

El sistema deberá guardar el progreso de cada especialista.

Si un especialista cierra el navegador o interrumpe una sesión, al volver a ingresar podrá continuar con los casos que tenga pendientes sin perder las anotaciones previamente completadas.

El sistema deberá implementar mecanismos de guardado automático y mantener trazabilidad de las modificaciones realizadas.

## Salidas

Esta etapa deberá producir, como mínimo:

- Asignaciones de casos por especialista.
- Anotaciones clínicas individuales.
- Bounding boxes asociadas con los hallazgos.
- Estado y progreso de cada caso.
- Información necesaria para auditoría y trazabilidad.

Las anotaciones originales no deberán sobrescribirse durante el posterior cálculo de consenso.

## Estructura

- `app/`: código de la aplicación utilizada por los especialistas.
- `scripts/`: scripts auxiliares para preparación, asignación y procesamiento de casos.
- `database/`: definición y migraciones de la base de datos.
- `docs/`: documentación y guía destinada a los especialistas.
- `tests/`: pruebas del sistema de anotación.

