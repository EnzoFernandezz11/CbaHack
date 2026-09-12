# Entrenamiento YOLO26

Este pipeline convierte el dataset COCO reorganizado a formato YOLO, selecciona
un porcentaje reproducible de las imágenes, detecta CPU o CUDA, entrena YOLO26 y
guarda pesos y métricas en `cv/Models-Roboflow/`.

## Archivos principales

- `scripts/train_yolo26.py`: entrenamiento y evaluación.
- `scripts/prepare_yolo_dataset.py`: subset reproducible y conversión COCO a YOLO.
- `scripts/check_training_environment.py`: diagnóstico de dependencias y hardware.
- `requirements-yolo26.txt`: dependencias Python distintas de PyTorch.
- `setup_training.ps1`: instalación guiada en Windows para CPU o CUDA.

## Instalación en Windows

Desde la raíz del repositorio:

```powershell
# Detecta nvidia-smi; usa CUDA si está disponible y CPU en caso contrario.
.\cv\setup_training.ps1 -Backend Auto

# Instalación explícita para CPU.
.\cv\setup_training.ps1 -Backend Cpu

# Instalación explícita para una GPU NVIDIA.
.\cv\setup_training.ps1 -Backend Cuda -CudaIndex cu128
```

El entorno se crea en `cv/.venv`. Los índices CUDA admitidos por el instalador
son `cu118`, `cu126` y `cu128`. Si la computadora usa otra combinación de driver
y CUDA, consulte el selector oficial de PyTorch: <https://pytorch.org/get-started/locally/>.

Para revisar el entorno:

```powershell
.\cv\.venv\Scripts\python.exe .\cv\scripts\check_training_environment.py
```

## Instalación manual en Linux

```bash
python3 -m venv cv/.venv
source cv/.venv/bin/activate
python -m pip install --upgrade pip setuptools wheel

# CPU:
python -m pip install torch==2.7.0 torchvision==0.22.0 \
  --index-url https://download.pytorch.org/whl/cpu

# Para CUDA, reemplace el índice por el indicado por el selector de PyTorch.
python -m pip install -r cv/requirements-yolo26.txt
python cv/scripts/check_training_environment.py
```

## Configuración

Los valores principales se editan al comienzo de `scripts/train_yolo26.py`:

```python
DATASET_PERCENT = 100.0
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15
MODEL = "yolo26n.pt"
EPOCHS = 100
IMAGE_SIZE = 640
DEVICE = "auto"
```

`DATASET_PERCENT` define el nuevo total. Por ejemplo, 50 % de las 588 imágenes
produce un subset de 294 imágenes y luego aplica los ratios: 206 para `train`,
44 para `val` y 44 para `test`.

Los argumentos de línea de comandos permiten hacer pruebas sin modificar los
defaults del archivo:

```powershell
.\cv\.venv\Scripts\python.exe .\cv\scripts\train_yolo26.py `
  --dataset-percent 50 `
  --epochs 20 `
  --imgsz 640 `
  --device auto `
  --run-name yolo26n-peanut-50pct
```

Use `--help` para ver todos los overrides. La misma semilla y configuración
reutilizan el mismo subset preparado.

## Entrenamiento completo

Con los defaults configurados en el script:

```powershell
.\cv\.venv\Scripts\python.exe .\cv\scripts\train_yolo26.py
```

El primer uso puede descargar automáticamente `yolo26n.pt`. Los pesos
preentrenados se cachean en `cv/Models-Roboflow/pretrained/`.

## Smoke test con 10 imágenes

El porcentaje `1.7006802721` sobre 588 imágenes selecciona exactamente 10:

```powershell
.\cv\.venv\Scripts\python.exe .\cv\scripts\train_yolo26.py `
  --dataset-percent 1.7006802721 `
  --epochs 1 `
  --imgsz 160 `
  --batch 1 `
  --workers 0 `
  --device cpu `
  --run-name smoke-yolo26-10img `
  --no-plots
```

La distribución esperada es 7 imágenes de entrenamiento, 2 de validación y 1
de test. Esta corrida solo comprueba el pipeline; sus métricas no representan
la calidad esperable del modelo.

## Resultados

Cada ejecución crea `cv/Models-Roboflow/<run-name>/` con:

- `weights/best.pt` y `weights/last.pt`.
- `training.log`, `results.csv` y archivos producidos por Ultralytics.
- `requested_config.json` y `train_arguments.json`.
- `environment.json` y `dependencies-freeze.txt`.
- `subset_manifest.json`.
- `val_metrics.json`, `test_metrics.json` y `run_summary.json`.

Las métricas principales son precision, recall, mAP50 y mAP50-95. `test` debe
reservarse para evaluar el modelo candidato final; durante experimentación se
deben tomar decisiones usando `val`.

## Fine-tuning posterior

Para continuar desde un checkpoint propio, cambie `MODEL` o use:

```powershell
.\cv\.venv\Scripts\python.exe .\cv\scripts\train_yolo26.py `
  --model .\cv\Models-Roboflow\corrida-anterior\weights\best.pt `
  --run-name fine-tuning-datos-propios
```

## Referencias oficiales

- <https://docs.ultralytics.com/models/yolo26/>
- <https://docs.ultralytics.com/modes/train/>
- <https://docs.ultralytics.com/tasks/detect/>
- <https://pytorch.org/get-started/locally/>
