# Dataset de fotos propias

Dataset de detección de vainas de maní capturado el 12 de septiembre de 2026.
Los originales se conservan sin modificaciones en `raw/`; la vista reproducible
para entrenamiento se genera en `prepared/all/`.

## Resumen auditado

| Colección | Imágenes | Cajas | Resoluciones |
| --- | ---: | ---: | --- |
| `photos_session_01` | 36 | 277 | 960×1280 |
| `video_frames_session_02` | 40 | 278 | 739×1600, 960×1280, 591×1280 y 702×1280 |
| **Total** | **76** | **555** | 4 tamaños |

La anotación fuente está en formato **COCO Detection**:

- una categoría: `peanut`, con ID COCO `1`;
- cajas `bbox = [x_min, y_min, ancho, alto]` en píxeles;
- `segmentation` vacío, `iscrowd = 0`, rotación `0`;
- todas las imágenes están anotadas y ninguna caja tiene área cero ni sale de
  los límites de la imagen.

El modelo anterior usa la clase `pod`. Por eso la vista preparada remapea, sin
modificar los originales, `peanut` a `pod`: ID `1` en COCO e ID `0` en YOLO.

## Estructura

```text
FotosPropias/
├── README.md
├── raw/
│   ├── annotations/coco/  # dos exportaciones COCO originales
│   ├── archives/          # cuatro ZIP originales, renombrados claramente
│   ├── images/            # imágenes agrupadas por colección
│   └── videos/            # video fuente conservado aparte
└── prepared/all/
    ├── annotations/instances_all.coco.json
    ├── images/            # nombres estables y sin espacios
    ├── labels/            # etiquetas YOLO, clase 0 = pod
    ├── manifest.json      # trazabilidad al nombre original y grupo de captura
    └── validation_report.json
```

Los ZIP se mantienen como respaldo exacto. `photos_session_01.annotations.zip`
contiene el mismo JSON que `photos_session_01.instances.json`.

## Regenerar la vista preparada

Desde la raíz del repositorio, después de mover o respaldar una salida anterior:

```bash
/opt/cv-yolo/venv/bin/python cv/scripts/prepare_own_dataset.py
```

El script valida referencias, dimensiones, cajas, clases y duplicados exactos;
luego crea nombres estables, un COCO combinado y etiquetas YOLO normalizadas.
Las imágenes preparadas son hardlinks cuando el sistema de archivos lo permite,
por lo que no duplican los bytes de las originales.
No se deben editar esas imágenes in-place: al ser hardlinks, una modificación
también afectaría el archivo de `raw/`.

## Criterio pendiente para el fine-tuning

No hay un split `train/val/test` todavía. Varias imágenes son tomas sucesivas de
la misma escena —especialmente los frames de video— y una división aleatoria
produciría fuga de datos. El `manifest.json` asigna un `capture_group` a cada
imagen; el próximo paso debe repartir grupos completos entre splits.

Con solo 76 imágenes de un mismo entorno, conviene usar estos datos sobre todo
para adaptación de dominio y conservar una evaluación externa separada. Para
una métrica propia confiable harán falta nuevas sesiones con iluminación,
fondos, distancias y disposiciones diferentes.

## Ejecutar el fine-tuning

El script `cv/scripts/fine_tune_own_yolo26.py` parte automáticamente del mejor
checkpoint de `yolo26n-peanut-50pct-50e-v1`, prepara un split determinista por
grupos y guarda el ajuste en una corrida nueva.

Para comprobar solamente el dataset y el split:

```bash
/opt/cv-yolo/venv/bin/python \
  cv/scripts/fine_tune_own_yolo26.py \
  --prepare-only
```

Para iniciar el fine-tuning recomendado desde la raíz del repositorio:

```bash
/opt/cv-yolo/venv/bin/python \
  cv/scripts/fine_tune_own_yolo26.py \
  --epochs 40 \
  --imgsz 768 \
  --batch -1 \
  --patience 12 \
  --workers 4 \
  --device 0 \
  --freeze 10 \
  --learning-rate 0.001 \
  --run-name yolo26n-peanut-own-finetune-v1 \
  --amp \
  --plots \
  --test-evaluation
```

`imgsz=768` procesa 44 % más píxeles que 640 y puede ayudar con los objetos
pequeños. También aumenta el uso de memoria y el tiempo; `batch=-1` permite que
Ultralytics elija un batch seguro para la GPU. Si hubiera falta de memoria,
repita la corrida con `--imgsz 640`.

Por defecto se congelan las primeras 10 capas para reducir sobreajuste y olvido
del entrenamiento anterior. Se puede ajustar todo el modelo con `--freeze 0`,
aunque no es la primera opción recomendada para solo 53 imágenes de train.

La corrida guarda el checkpoint original, argumentos, entorno, split, métricas
antes y después del ajuste, comparación de métricas, `best.pt` y `last.pt` bajo
`cv/Models-Roboflow/<run-name>/`.

## Observaciones visuales

- Las cajas observadas corresponden a vainas de maní y, en general, están bien
  ajustadas.
- Hay 101 cajas que tocan un borde de imagen. No son inválidas, pero antes del
  entrenamiento se debe fijar una política consistente para objetos parciales.
- Hay movimiento y desenfoque en varios frames; son útiles para robustez si esa
  condición aparecerá en producción.
- No se encontraron imágenes corruptas ni duplicados exactos.
