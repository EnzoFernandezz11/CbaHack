# Relay de cámara teléfono–computadora

Este módulo implementa la primera etapa de la aplicación web: captura JPEG desde
la cámara de un teléfono y muestra los frames en una computadora en tiempo real.
Si se configura `WEB_MODEL_PATH`, el backend carga un detector YOLO al iniciar y
dibuja sus cajas sobre cada imagen. Sin un checkpoint configurado, utiliza el
procesador `passthrough` y deja cada imagen sin modificar.

## Requisitos

- Windows 10/11 y PowerShell.
- Python 3.10 o superior.
- Internet para instalar las dependencias y crear el túnel.
- Un navegador moderno en el teléfono y la computadora.
- `cloudflared` para acceder a la cámara del teléfono mediante HTTPS.

## Instalación

Desde la raíz del repositorio:

```powershell
.\webcam\setup.ps1
```

El script crea `webcam/.venv`, instala las versiones fijadas en `requirements.txt`
y ejecuta las pruebas automáticas.

Si PowerShell bloquea los scripts locales, habilítelos solamente para la terminal
actual:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## Ejecución local

Terminal 1:

```powershell
.\webcam\run.ps1
```

El servidor queda disponible en:

- <http://localhost:8000/camera>
- <http://localhost:8000/viewer>
- <http://localhost:8000/api/status>
- <http://localhost:8000/docs>

`localhost` sirve para probar ambas páginas en la notebook. Un teléfono no debe
abrir `http://IP-DE-LA-NOTEBOOK:8000/camera`, porque los navegadores normalmente
bloquean el acceso a la cámara fuera de un contexto HTTPS.

## Acceso desde el teléfono

Instale Cloudflare Tunnel una sola vez:

```powershell
winget install --id Cloudflare.cloudflared
```

Con el servidor todavía ejecutándose, abra otra terminal:

```powershell
.\webcam\start_tunnel.ps1
```

El comando mostrará una URL temporal similar a:

```text
https://palabras-aleatorias.trycloudflare.com
```

Abra usando exactamente el mismo dominio:

- Teléfono: `https://...trycloudflare.com/camera`
- Computadora: `https://...trycloudflare.com/viewer`

No se necesita una cuenta de Cloudflare para este Quick Tunnel. La URL cambia
cada vez que se reinicia `cloudflared` y es solamente para desarrollo o demos.
El relay todavía no implementa autenticación: no comparta la URL y cierre el
túnel al terminar la prueba.

## Uso

1. Abra `/viewer` en la computadora.
2. Abra `/camera` en el teléfono.
3. Presione **Iniciar transmisión**.
4. Autorice el permiso de cámara.
5. Verifique que el visor muestre los frames y que los contadores de FPS avancen.

Los valores iniciales son 640 px de ancho, calidad JPEG del 60 % y 12 FPS. Se
pueden ajustar desde `/camera` antes de iniciar. Si la red se congestiona, el
cliente deja de producir temporalmente y el servidor reemplaza frames pendientes
para no acumular latencia.

El emisor mantiene como máximo dos frames sin confirmar y el servidor confirma
cada recepción. Esa pequeña ventana sostiene los FPS aun con el viaje de ida y
vuelta del túnel, sin dejar crecer una cola larga. El visor también
descarta JPEGs pendientes si la decodificación queda atrás. Así se sacrifica un
frame viejo antes de convertir congestión momentánea en varios segundos de
latencia. La compresión WebSocket está desactivada porque los JPEG ya vienen
comprimidos y volver a comprimirlos consume CPU sin reducirlos apreciablemente.

## Configuración del servidor

El límite de tamaño de un JPEG es 2,5 MB. Puede cambiarse antes de arrancar:

```powershell
$env:WEB_MAX_FRAME_BYTES = '4000000'
.\webcam\run.ps1
```

También se puede cambiar host y puerto:

```powershell
.\webcam\run.ps1 -ServerHost 127.0.0.1 -Port 8080
.\webcam\start_tunnel.ps1 -Port 8080
```

La aplicación debe ejecutarse con un solo worker porque las conexiones y el
último frame se conservan en memoria dentro del proceso.

## Pruebas

```powershell
.\webcam\.venv\Scripts\python.exe -m pytest -c .\webcam\pytest.ini .\webcam\tests -q
```

Las pruebas validan las páginas HTTP, el estado del servicio, la conexión de la
cámara, la conexión del viewer y la retransmisión binaria exacta de un JPEG.

Con el servidor iniciado también puede ejecutar una comprobación real contra
Uvicorn:

```powershell
.\webcam\.venv\Scripts\python.exe .\webcam\tests\live_smoke.py
```

## Inferencia YOLO

El checkpoint entrenado para vainas está incluido en el repositorio. Desde la
raíz del proyecto, prepare el entorno y arranque el servidor en PowerShell:

```powershell
.\webcam\setup.ps1 -Inference
$env:WEB_MODEL_PATH = 'cv\Models-Roboflow\yolo26m-peanut-own-finetune-v1\weights\best.pt'
$env:WEB_MODEL_CONFIDENCE = '0.25'
.\webcam\run.ps1
```

`setup.ps1 -Inference` instala `ultralytics`, `torch`, `numpy` y `opencv-python`
junto con el relay. Para GPU, instale primero el PyTorch apropiado.
Compruebe `http://localhost:8000/healthz`: `mode` debe ser `yolo`. El servidor
falla al iniciar si el checkpoint indicado no existe o no es de detección.
Sin `WEB_MODEL_PATH`, el flujo es:

```text
JPEG recibido → PassthroughFrameProcessor → mismo JPEG
```

Con `WEB_MODEL_PATH`, el mismo protocolo entrega un JPEG con las bounding boxes
dibujadas. La velocidad efectiva dependerá del modelo y del hardware disponible.

## Referencias

- <https://fastapi.tiangolo.com/advanced/websockets/>
- <https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia>
- <https://developers.cloudflare.com/tunnel/setup/>
