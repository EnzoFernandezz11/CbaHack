# Contexto del entrenamiento de visión por computadora

## Objetivo

El componente de visión por computadora debe detectar vainas de maní visibles sobre la superficie. Las detecciones serán consumidas por el backend para dibujar bounding boxes sobre los frames enviados por el celular y, opcionalmente, calcular un conteo y una estimación demostrativa de pérdida superficial.

El trabajo de entrenamiento se plantea en dos etapas:

1. Entrenamiento inicial con datos públicos descargados de Internet.
2. Fine-tuning de los modelos obtenidos con imágenes representativas del escenario real de la demo: celular y altura de montaje definitivos, tierra, rastrojo, iluminación y vainas utilizadas por el equipo.

La arquitectura y variante exactas de YOLO, los hiperparámetros y los pesos de partida todavía están por definir.

## Dataset público inicial

- Nombre: `peanut_tifton_patch`.
- Fuente: Roboflow Universe.
- Autor/workspace: `zhengkun.li@uga.edu`.
- Versión descargada: `4`.
- Tipo de tarea: detección de objetos.
- Clase efectiva anotada: `pod` (vaina de maní).
- Licencia declarada: CC BY 4.0; se debe conservar la atribución al redistribuir o publicar resultados derivados.
- Página de la versión: <https://universe.roboflow.com/zhengkun-li-uga-edu/peanut_tifton_patch/dataset/4>
- Página del proyecto: <https://universe.roboflow.com/zhengkun-li-uga-edu/peanut_tifton_patch>
- Ubicación actual del dataset reorganizado: `cv/Datasets/peanut_tifton_patch_v4_grouped/`.
- Formato descargado: COCO JSON.
- Fecha indicada para la versión: 2024-03-31 05:55.
- Fecha indicada para la exportación: 2024-06-01 13:45 GMT.

La página pública del proyecto informa 245 imágenes fuente y cuatro versiones. Para este proyecto se utilizó la exportación local de la versión 4, que contenía 588 imágenes derivadas debido a las transformaciones aplicadas al generarla. Después de reorganizar y verificar los datos, la descarga original fue eliminada y se conservó únicamente el dataset preparado.

## Contenido de la descarga utilizada

| Partición | Imágenes | Anotaciones `pod` |
| --- | ---: | ---: |
| `train` | 515 | 51.705 |
| `valid` | 73 | 12.111 |
| Total | 588 | 63.816 |

La descarga original no incluía una partición `test` independiente.

Los archivos COCO declaran dos entradas en `categories`: `peanut-l2jA` con ID 0 y `pod` con ID 1. Todas las anotaciones observadas usan el ID 1, por lo que `pod` es la única clase efectiva para entrenar.

Resoluciones presentes:

- 456 imágenes de 1530 × 1149 píxeles.
- 132 imágenes de 2048 × 1537 píxeles.

## Dataset preparado para entrenamiento

Para evitar fuga de información entre particiones, el dataset utilizado se reorganizó y su versión definitiva quedó en:

`cv/Datasets/peanut_tifton_patch_v4_grouped/`

La versión preparada combina el pool completo y asigna todas las variantes de una misma captura base a un único split. Se eligió una relación objetivo 70/15/15 porque solo existen 20 capturas base; utilizar 80/10/10 dejaría apenas dos capturas para validación y dos para test. La carpeta original `DownLoadDataset/` fue eliminada una vez comprobada la integridad de esta reorganización.

| Partición | Capturas base | Imágenes | Anotaciones `pod` |
| --- | ---: | ---: | ---: |
| `train` | 14 | 412 | 44.643 |
| `val` | 3 | 88 | 9.572 |
| `test` | 3 | 88 | 9.601 |
| Total | 20 | 588 | 63.816 |

La asignación se optimizó de forma determinista para aproximar simultáneamente las proporciones de imágenes y anotaciones. El detalle reproducible está en `split_manifest.json` y el proceso puede repetirse mediante `cv/scripts/split_coco_by_source.py`.

## Generación y augmentations de la versión 4

El archivo de metadatos provisto por Roboflow indica que se generaron tres versiones por imagen fuente mediante:

- Flip horizontal con probabilidad del 50 %.
- Flip vertical con probabilidad del 50 %.
- Ajuste aleatorio de brillo entre -15 % y +15 %.
- Desenfoque gaussiano aleatorio entre 0 y 2,5 píxeles.

No se declara un preprocesamiento adicional en el archivo exportado.

## Riesgos y criterios de evaluación

- La exportación original mezclaba en `train` y `valid` variantes pertenecientes a 18 capturas base. El dataset preparado corrige este riesgo agrupando por captura, pero sigue siendo conveniente confirmar con el autor qué representa exactamente el prefijo de cada archivo.
- La versión 4 ya fue exportada con augmentations. La separación agrupada es la opción más segura con estos archivos, pero el procedimiento ideal es reexportar las imágenes sin augmentar, dividir primero por captura y aplicar augmentations únicamente a `train`. `val` y `test` deberían conservar imágenes naturales.
- Para los experimentos se deben usar exclusivamente `train`, `val` y `test` de la versión preparada.
- El test definitivo debe contener imágenes nunca usadas durante el entrenamiento ni el fine-tuning, capturadas con el montaje real de la demo.
- Durante el fine-tuning se deben incluir fondos difíciles y negativos: tierra sin vainas, rastrojo, piedras, hojas, cambios de luz, oclusiones y vainas parcialmente visibles.
- Además de mAP, precision y recall, interesa medir falsos positivos, falsos negativos y latencia/FPS en la notebook que ejecutará el backend.

## Flujo previsto

```text
Pesos YOLO preentrenados
          |
          v
Entrenamiento con peanut_tifton_patch v4
          |
          v
Pesos iniciales adaptados a la clase pod
          |
          v
Fine-tuning con datos propios de la demo
          |
          v
Evaluación en test propio no visto
          |
          v
Pesos seleccionados para el backend web
```

## Información pendiente de registrar

Cuando comiencen los experimentos se deberá agregar:

- Modelo y tamaño de YOLO utilizados.
- Framework y versiones de dependencias.
- Pesos de partida.
- División definitiva de datos y semilla aleatoria.
- Resolución de entrada, epochs, batch size e hiperparámetros relevantes.
- Métricas y latencia de cada corrida.
- Dataset propio utilizado para fine-tuning y su convención de etiquetado.
- Ruta de los pesos seleccionados y formato de exportación consumido por el backend.

## Atribución del dataset

```bibtex
@misc{peanut_tifton_patch_dataset,
  title        = {peanut_tifton_patch Dataset},
  type         = {Open Source Dataset},
  author       = {zhengkun.li@uga.edu},
  howpublished = {Roboflow Universe},
  url          = {https://universe.roboflow.com/zhengkun-li-uga-edu/peanut_tifton_patch},
  publisher    = {Roboflow},
  year         = {2024},
  month        = {mar}
}
```

Última verificación de la ficha pública y de la descarga local: 2026-09-12.
