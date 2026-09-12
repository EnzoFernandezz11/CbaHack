# Relay de cámara teléfono–computadora

Este módulo implementa la primera etapa de la aplicación web: captura JPEG desde
la cámara de un teléfono y muestra los frames en una computadora en tiempo real.
Todavía no ejecuta YOLO; el backend utiliza un procesador `passthrough` que deja
cada imagen sin modificar.

## Requisitos

- Windows 10/11 y PowerShell.
- Python 3.10 o superior.
- Internet para instalar las dependencias y crear el túnel.
- Un navegador moderno en el teléfono y la computadora.
- `cloudflared` para acceder a la cámara del teléfono mediante HTTPS.

## Instalación

Desde la raíz del repositorio:

```powershell
.\web\setup.ps1
```

El script crea `web/.venv`, instala las versiones fijadas en `requirements.txt`
y ejecuta las pruebas automáticas.

Si PowerShell bloquea los scripts locales, habilítelos solamente para la terminal
actual:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

## Ejecución local

Terminal 1:

```powershell
.\web\run.ps1
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
.\web\start_tunnel.ps1
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

Los valores iniciales son 640 px de ancho, calidad JPEG del 70 % y 8 FPS. Se
pueden ajustar desde `/camera` antes de iniciar. Si la red se congestiona, el
cliente deja de producir temporalmente y el servidor reemplaza frames pendientes
para no acumular latencia.

## Configuración del servidor

El límite de tamaño de un JPEG es 2,5 MB. Puede cambiarse antes de arrancar:

```powershell
$env:WEB_MAX_FRAME_BYTES = '4000000'
.\web\run.ps1
```

También se puede cambiar host y puerto:

```powershell
.\web\run.ps1 -ServerHost 127.0.0.1 -Port 8080
.\web\start_tunnel.ps1 -Port 8080
```

La aplicación debe ejecutarse con un solo worker porque las conexiones y el
último frame se conservan en memoria dentro del proceso.

## Pruebas

```powershell
.\web\.venv\Scripts\python.exe -m pytest -c .\web\pytest.ini .\web\tests -q
```

Las pruebas validan las páginas HTTP, el estado del servicio, la conexión de la
cámara, la conexión del viewer y la retransmisión binaria exacta de un JPEG.

Con el servidor iniciado también puede ejecutar una comprobación real contra
Uvicorn:

```powershell
.\web\.venv\Scripts\python.exe .\web\tests\live_smoke.py
```

## Integración futura de YOLO

`backend/frame_processor.py` define el punto de extensión. Actualmente:

```text
JPEG recibido → PassthroughFrameProcessor → mismo JPEG
```

La siguiente etapa podrá cargar una sola vez el modelo de `cv/`, ejecutar la
inferencia y devolver un JPEG con bounding boxes sin cambiar el protocolo ni las
páginas existentes.

## Referencias

- <https://fastapi.tiangolo.com/advanced/websockets/>
- <https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia>
- <https://developers.cloudflare.com/tunnel/setup/>
