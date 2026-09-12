# Contexto del entrenamiento de visión por computadora

## Objetivo

El componente de visión por computadora debe detectar vainas de maní visibles sobre la superficie. Las detecciones serán consumidas por el backend para dibujar bounding boxes sobre los frames enviados por el celular y, opcionalmente, calcular un conteo y una estimación demostrativa de pérdida superficial.

El trabajo de entrenamiento se plantea en dos etapas:

1. Entrenamiento inicial con datos públicos descargados de Internet.
2. Fine-tuning de los modelos obtenidos con imágenes representativas del escenario real de la demo: celular y altura de montaje definitivos, tierra, rastrojo, iluminación y vainas utilizadas por el equipo.

Para la primera implementación se utilizará YOLO26 de Ultralytics, con `yolo26n.pt` como valor inicial recomendado por su relación entre latencia y precisión. La variante, los hiperparámetros y los pesos de partida permanecerán configurables en el script.

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

## Diseño e implementación del entrenamiento YOLO26

Esta sección registra el diseño acordado y la implementación verificada del pipeline. Los scripts, archivos de dependencias y documentación mencionados a continuación forman parte de `cv/` desde el 2026-09-12.

### Configuración del experimento

El script principal será `cv/scripts/train_yolo26.py` y tendrá al comienzo un bloque de configuración editable. Como mínimo expondrá:

```python
DATASET_PERCENT = 100.0

TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

MODEL = "yolo26n.pt"
EPOCHS = 100
IMAGE_SIZE = 640
GPU_BATCH_SIZE = -1
CPU_BATCH_SIZE = 4
PATIENCE = 20
WORKERS = 4
SEED = 42
DEVICE = "auto"
RUN_NAME = "yolo26n-peanut"
RUN_TEST_EVALUATION = True
```

También podrán exponerse el optimizador, learning rate, caché, AMP, augmentations, reanudación desde checkpoint y otras opciones admitidas por Ultralytics. Antes de entrenar se validarán los tipos, rangos y compatibilidad de todos los valores.

### Porcentaje configurable del dataset

`DATASET_PERCENT` determinará qué porcentaje del dataset completo participará en una corrida. El subconjunto seleccionado pasará a considerarse el nuevo 100 % y recién entonces se calcularán las cantidades de `train`, `val` y `test` usando sus ratios configurados.

Ejemplo:

```text
Dataset disponible: 500 imágenes
DATASET_PERCENT:     50 %
Nuevo total:         250 imágenes

TRAIN_RATIO:         70 % -> 175 imágenes
VAL_RATIO:           15 % -> 38 imágenes
TEST_RATIO:          15 % -> 37 imágenes
```

Cuando haya fracciones, se utilizará una asignación determinista por restos mayores para que la suma de los tres splits coincida exactamente con el nuevo total. Con el dataset actual, `DATASET_PERCENT = 50` seleccionaría 294 de las 588 imágenes y produciría 206 imágenes de entrenamiento, 44 de validación y 44 de test.

La selección deberá cumplir estas reglas:

- Aceptar porcentajes mayores que 0 y menores o iguales que 100.
- Exigir que `TRAIN_RATIO + VAL_RATIO + TEST_RATIO == 1`.
- Conservar la separación por captura ya definida; ninguna captura podrá cruzar de un split a otro.
- Seleccionar dentro de cada split de manera reproducible usando `SEED`.
- Procurar representación de todas las capturas disponibles y balancear la densidad de anotaciones.
- Rechazar configuraciones tan pequeñas que dejen algún split vacío y advertir cuando `val` o `test` resulten insuficientes para una métrica estable.
- Usar todas las imágenes sin muestreo cuando `DATASET_PERCENT = 100`.

Cada subconjunto generará un `subset_manifest.json` con la configuración y los nombres exactos de las imágenes. Esto permitirá repetir el experimento en otra computadora y comparar corridas sin ambigüedad.

### Preparación COCO a YOLO

Las anotaciones actuales están en COCO JSON. Antes del entrenamiento, `cv/scripts/prepare_yolo_dataset.py` generará automáticamente una vista en formato YOLO solo con las imágenes seleccionadas:

```text
cv/Datasets/yolo26_working/
|-- images/
|   |-- train/
|   |-- val/
|   `-- test/
|-- labels/
|   |-- train/
|   |-- val/
|   `-- test/
|-- data.yaml
`-- subset_manifest.json
```

La conversión mapeará la categoría COCO `pod`, ID 1, a la clase YOLO `0`, normalizará las bounding boxes y validará archivos faltantes, coordenadas fuera de rango, clases inesperadas y etiquetas inconsistentes. Las imágenes se reutilizarán mediante hardlinks cuando el sistema lo permita.

### Selección automática de CPU o GPU

Con `DEVICE = "auto"`, el pipeline consultará PyTorch y utilizará la primera GPU CUDA disponible; si no existe una GPU compatible, continuará en CPU. El script mostrará el dispositivo elegido, nombre y memoria de GPU cuando corresponda, versiones de CUDA, PyTorch y Ultralytics, y los parámetros efectivos de batch y workers.

Se podrá forzar `DEVICE = "cpu"` o una GPU concreta. En Windows, el punto de entrada quedará protegido con `if __name__ == "__main__":` para permitir el uso seguro de multiprocessing.

### Logging y trazabilidad

El pipeline será deliberadamente verboso. Mostrará y guardará:

- Inicio y fin de cada etapa.
- Entorno de ejecución y hardware detectado.
- Configuración solicitada y configuración efectiva.
- Estadísticas del dataset completo y del subconjunto.
- Progreso y duración del entrenamiento.
- Rutas de checkpoints y artefactos.
- Métricas finales o errores con contexto suficiente para diagnosticarlos.

Además de la salida de Ultralytics, cada corrida tendrá un log persistente y un resumen serializado del entorno y de los parámetros utilizados.

### Resultados y métricas

Todos los artefactos se guardarán bajo `cv/Models-Roboflow/`, con un subdirectorio independiente por corrida:

```text
cv/Models-Roboflow/<nombre-de-corrida>/
|-- weights/
|   |-- best.pt
|   `-- last.pt
|-- args.yaml
|-- results.csv
|-- training.log
|-- subset_manifest.json
|-- environment.json
|-- val_metrics.json
|-- test_metrics.json
`-- run_summary.json
```

La validación durante el entrenamiento utilizará `val`. Al finalizar se cargará `best.pt` y, cuando `RUN_TEST_EVALUATION = True`, se calcularán sobre `test` precision, recall, mAP50 y mAP50-95, además de la latencia de inferencia disponible. Las curvas, matriz de confusión y demás gráficos producidos por Ultralytics quedarán dentro de la misma corrida.

El conjunto `test` no debe utilizarse para elegir hiperparámetros. Para comparaciones exploratorias se priorizarán las métricas de `val`, reservando la evaluación de `test` para el modelo candidato final.

### Dependencias y ejecución en otra computadora

La implementación incorpora los siguientes archivos de soporte:

```text
cv/
|-- requirements-yolo26.txt
|-- setup_training.ps1
|-- README_entrenamiento.md
`-- scripts/
    |-- check_training_environment.py
    |-- prepare_yolo_dataset.py
    `-- train_yolo26.py
```

- `requirements-yolo26.txt` declara las versiones verificadas de las dependencias Python.
- `setup_training.ps1` crea un entorno virtual e instala dependencias para CPU o CUDA mediante un parámetro explícito, por ejemplo `-Backend Cpu` o `-Backend Cuda`.
- `README_entrenamiento.md` documenta los comandos para Windows y Linux, la instalación, la configuración y la ejecución.
- `check_training_environment.py` muestra Python, sistema operativo, PyTorch, Ultralytics, CUDA, GPU, memoria disponible y dependencias faltantes. Si encuentra un problema, finaliza con un código de error y una indicación para corregirlo.
- Cada corrida guardará las versiones realmente utilizadas para que el resultado sea auditable aunque el entrenamiento se ejecute en otra máquina.

La instalación de PyTorch deberá distinguir CPU de CUDA, porque sus paquetes pueden requerir índices diferentes. El instalador comprobará la presencia de una GPU NVIDIA antes de seleccionar la variante CUDA y fallará con un mensaje claro si el backend solicitado no está disponible.

### Verificación del pipeline

La implementación comprueba:

1. Conversión correcta de COCO a YOLO y mapeo exclusivo de `pod` a la clase 0.
2. Exactitud del porcentaje solicitado y de las cantidades finales por split.
3. Ausencia de imágenes repetidas o capturas compartidas entre splits.
4. Repetibilidad de la selección usando la misma semilla.
5. Detección correcta de CPU y CUDA.
6. Creación de `Models-Roboflow` y de todos los artefactos esperados.
7. Ejecución de un smoke test corto antes de lanzar un entrenamiento completo.
8. Extracción y persistencia de las métricas del mejor checkpoint.

### Smoke test ejecutado

El 2026-09-12 se ejecutó el pipeline completo en CPU con una muestra mínima para comprobar la integración, no para evaluar la calidad final del detector:

| Parámetro | Valor efectivo |
| --- | --- |
| Modelo inicial | `yolo26n.pt` |
| Dataset | 10 de 588 imágenes (`1.7006802721088436 %`) |
| Reparto | 7 `train`, 2 `val`, 1 `test` |
| Entrenamiento | 1 epoch, `imgsz=160`, `batch=1`, `workers=0` |
| Dispositivo | CPU, Intel Core i5-10210U |
| Entorno | Python 3.13.1, PyTorch 2.7.0+cpu, Ultralytics 8.4.147 |
| Duración total | 27,104 segundos |
| Resultado | Pipeline completado; `best.pt`, `last.pt`, métricas y resumen generados |

La corrida quedó en `cv/Models-Roboflow/smoke_test_10/`. Tanto validación como test produjeron precision, recall, mAP50 y mAP50-95 iguales a 0. Este resultado es esperable con solo siete imágenes de entrenamiento, una época y una resolución de 160 píxeles; no debe utilizarse como indicador de calidad. La prueba sí confirmó la descarga y carga de YOLO26n, la conversión COCO a YOLO, la selección porcentual, el entrenamiento, la evaluación separada sobre `val` y `test`, y la persistencia de artefactos.

El subset de prueba contiene 549 anotaciones en `train`, 467 en `val` y 258 en `test`. La conversión recortó dos bounding boxes que excedían levemente los límites de sus imágenes y registró esta corrección en `subset_manifest.json`.

Referencias técnicas previstas:

- <https://docs.ultralytics.com/models/yolo26/>
- <https://docs.ultralytics.com/modes/train/>
- <https://docs.ultralytics.com/tasks/detect/>

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

Última verificación de la ficha pública, del dataset reorganizado y del plan de entrenamiento: 2026-09-12.
