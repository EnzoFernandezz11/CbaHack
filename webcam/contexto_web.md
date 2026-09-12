# Contexto de la implementación web

## Estado actual

Este documento resume todo lo implementado dentro de `web/` hasta el 2026-09-12
en la rama `feature/HaCBA-webConnection`.

La implementación corresponde a la primera etapa del MVP: validar la conexión
entre un teléfono y una computadora mediante una retransmisión de imágenes JPEG
en tiempo real. Todavía no se ejecuta YOLO, no se dibujan bounding boxes y no se
controla la ESP32.

El flujo actual es:

```text
Teléfono: /camera
    | JPEG binario por WebSocket /ws/camera
    v
Notebook: FastAPI + relay en memoria
    | JPEG binario por WebSocket /ws/viewer
    v
Computadora: /viewer
```

## Arquitectura implementada

### Backend

El backend está construido con FastAPI y se ejecuta con Uvicorn en un único
proceso. Sus responsabilidades actuales son:

- Servir las páginas estáticas del frontend.
- Aceptar una conexión de cámara en `/ws/camera`.
- Aceptar uno o varios viewers en `/ws/viewer`.
- Recibir frames JPEG binarios.
- Validar tamaño y marcadores JPEG (`FFD8` al comienzo y `FFD9` al final).
- Retransmitir los frames a todos los viewers conectados.
- Conservar solo el frame más reciente por viewer para evitar acumular latencia.
- Notificar conexión y desconexión de la cámara.
- Exponer el estado operativo en `/api/status`.
- Exponer una comprobación simple en `/healthz`.

Archivos:

- `backend/main.py`: aplicación FastAPI, páginas, endpoints HTTP y WebSocket.
- `backend/connection_manager.py`: cámara, viewers, estadísticas y relay de
  último frame.
- `backend/frame_processor.py`: interfaz de procesamiento y
  `PassthroughFrameProcessor`, que devuelve el JPEG sin modificar.
- `backend/settings.py`: configuración y límite de tamaño de frame.
- `backend/__init__.py`: paquete Python del backend.

El límite predeterminado por frame es 2.500.000 bytes. Puede modificarse antes
de arrancar el servidor:

```powershell
$env:WEB_MAX_FRAME_BYTES = '4000000'
```

La conexión de estado se mantiene en memoria, por lo que el servidor debe
ejecutarse con un solo worker. `run.ps1` ya fuerza `--workers 1`.

### Frontend

#### `/camera`

`frontend/camera.html` y `frontend/camera.js` implementan el emisor móvil:

- Solicitud explícita de permiso mediante `navigator.mediaDevices.getUserMedia`.
- Preferencia por la cámara trasera (`facingMode: environment`).
- Preview local del video.
- Captura mediante `canvas` y codificación JPEG.
- FPS seleccionable: 5, 8, 10, 12 o 15; 12 FPS iniciales.
- Ancho máximo seleccionable: 480, 640 o 960 píxeles.
- Calidad JPEG configurable entre 40 % y 90 %, con 60 % inicial.
- Indicadores de estado, FPS, frames, resolución y bytes pendientes.
- Reconexión automática del WebSocket si se interrumpe.
- Detención de tracks de cámara y cierre correcto al abandonar la página.
- Control de backpressure: como máximo hay dos frames sin confirmar y no se
  agrega otro mientras el buffer del WebSocket contenga datos.

#### `/viewer`

`frontend/viewer.html` y `frontend/viewer.js` implementan la pantalla receptora:

- Conexión automática al WebSocket `/ws/viewer`.
- Reconexión con espera incremental de 1 a 5 segundos.
- Recepción de JPEG binario y actualización de la imagen mostrada.
- Descarte del JPEG pendiente anterior si la decodificación queda atrasada.
- Liberación de URLs de objetos anteriores para evitar fugas de memoria.
- Indicadores de servidor, cámara conectada, FPS recibidos, frames, antigüedad
  del último frame y cantidad de viewers.
- Consulta periódica de `/api/status`.
- Mensaje diferenciado cuando la cámara todavía no está conectada o dejó de
  enviar frames.

#### `/`

`frontend/index.html` es una portada simple con enlaces a `/camera` y `/viewer`.

#### Estilos

`frontend/styles.css` contiene el diseño responsive para notebook y teléfono,
los estados de conexión, tarjetas de estadísticas, controles y placeholders.

## Protocolo WebSocket

### Cámara → backend

- Endpoint: `/ws/camera`.
- Frames: mensajes binarios con contenido JPEG.
- Por cada frame aceptado, el servidor responde `{"type":"frame_ack"}`. El
  teléfono usa las confirmaciones para mantener una ventana máxima de dos.
- Mensaje de texto opcional `ping`, respondido con JSON `pong`.
- Un segundo emisor recibe un error `camera_already_connected` y cierre 1008.
- Un frame mayor al límite recibe cierre 1009.
- Un frame que no parece JPEG recibe un JSON `invalid_frame` y la conexión
  permanece abierta.

### Backend → viewer

- Endpoint: `/ws/viewer`.
- Al conectar, se recibe un mensaje JSON `system_status`.
- Se reciben actualizaciones JSON cuando cambia el estado de la cámara.
- Los frames se reciben como mensajes binarios JPEG.
- Si no hay viewers lentos, cada viewer recibe el último frame disponible sin
  una cola creciente.

### Estado HTTP

`GET /api/status` devuelve, entre otros campos:

- `camera_connected`.
- `viewer_count`.
- `total_frames`.
- `total_bytes`.
- `last_frame_age_ms`.
- `dropped_frames_by_viewer`.
- `mode`, actualmente `passthrough`.

## Instalación y ejecución

### Instalación en Windows

Desde la raíz del repositorio:

```powershell
.\web\setup.ps1
```

El script:

1. Crea `web/.venv`.
2. Actualiza pip.
3. Instala las versiones fijadas en `web/requirements.txt`.
4. Ejecuta las pruebas automáticas.

Dependencias directas fijadas:

- FastAPI 0.141.1.
- Uvicorn 0.52.4 con extras estándar.
- Pytest 9.1.1.

El frontend no requiere Node, npm ni un proceso de compilación.

### Servidor local

```powershell
.\web\run.ps1
```

Por defecto escucha en `127.0.0.1:8000` y muestra:

- <http://localhost:8000/>.
- <http://localhost:8000/camera>.
- <http://localhost:8000/viewer>.
- <http://localhost:8000/docs>.

También se puede cambiar host y puerto:

```powershell
.\web\run.ps1 -ServerHost 127.0.0.1 -Port 8080
```

### Acceso desde un teléfono

La cámara del navegador requiere HTTPS cuando se accede desde un teléfono. Se
incorporó `start_tunnel.ps1` para usar Cloudflare Quick Tunnel.

Instalación única de `cloudflared`:

```powershell
winget install --id Cloudflare.cloudflared
```

Con el backend ejecutándose, abrir otra terminal:

```powershell
.\web\start_tunnel.ps1 -Port 8000
```

El script localiza `cloudflared` mediante `PATH` y también en las ubicaciones
estándar de Windows cuando la instalación de Winget todavía no actualizó la
terminal actual. El comando imprime una URL temporal `https://...trycloudflare.com`.
Debe usarse el mismo dominio para ambas páginas:

- Teléfono: `https://...trycloudflare.com/camera`.
- Computadora: `https://...trycloudflare.com/viewer`.

El Quick Tunnel no requiere una cuenta de Cloudflare, pero la URL es temporal.
El relay no tiene autenticación todavía; no se deben compartir URLs ni enviar
información sensible, y el túnel debe cerrarse al terminar la demo.

## Pruebas y verificaciones realizadas

### Pruebas automáticas

`tests/test_relay.py` levanta un proceso Uvicorn real y verifica:

- Respuesta HTTP de `/`, `/camera`, `/viewer` y recursos estáticos.
- Respuesta de `/healthz`.
- Conexión inicial del viewer.
- Notificación de conexión de la cámara.
- Envío y relay exacto de un frame binario.
- Estado de `/api/status`.
- Notificación de desconexión de la cámara.
- Respuesta clara frente a un frame inválido.

Ejecución:

```powershell
.\web\.venv\Scripts\python.exe -m pytest -c .\web\pytest.ini .\web\tests -q
```

Resultado verificado: `3 passed`. La suite se ejecutó varias veces para
descartar intermitencias de ciclo de vida del servidor.

### Smoke test contra servidor levantado

`tests/live_smoke.py` permite comprobar un servidor Uvicorn ya iniciado:

```powershell
.\web\.venv\Scripts\python.exe .\web\tests\live_smoke.py
```

Verifica healthcheck, dos conexiones WebSocket, relay byte a byte y notificación
de desconexión.

### Verificación externa

El 2026-09-12 se levantó el servidor en el puerto 8765 y se validó el flujo a
través de un Quick Tunnel HTTPS real. La prueba confirmó:

- HTTPS para las páginas.
- WebSocket seguro `wss://`.
- Relay exacto del JPEG.
- Estado y desconexión correctos.
- Respuestas HTTP 200 de las páginas y recursos estáticos.

La prueba utilizó un cliente WebSocket automatizado a través del túnel; todavía
no se realizó una prueba manual con la cámara física de un teléfono. El túnel
temporal fue cerrado después de la verificación.

También se comprobaron la sintaxis de Python, JavaScript y PowerShell, y que no
quedaran procesos ni puertos de prueba abiertos.

## Exclusiones actuales

Todavía no forman parte de `web/`:

- Inferencia YOLO.
- Carga del modelo desde `cv/`.
- Bounding boxes o máscaras.
- Conteo agronómico.
- Cálculo de kg/ha.
- Seguimiento de objetos entre frames.
- Control de motores o comandos a la ESP32.
- Persistencia de imágenes o videos.
- Autenticación de cámara/viewer.
- Despliegue productivo, usuarios múltiples o balanceo.

## Integración futura de YOLO

El punto de extensión es `backend/frame_processor.py`. El flujo actual es:

```text
JPEG recibido
    → PassthroughFrameProcessor
    → mismo JPEG
```

Más adelante se podrá sustituir por un procesador que:

1. Cargue una sola vez el checkpoint seleccionado de `cv/`.
2. Ejecute inferencia sobre cada JPEG.
3. Dibuje las detecciones.
4. Devuelva el JPEG procesado al mismo relay.

El protocolo y las páginas no necesitan cambiar para esa integración. El
conteo, las métricas complementarias y la estimación demostrativa de kg/ha
deberán agregarse como datos separados del frame para no mezclar información de
visualización con el transporte de imágenes.

## Archivos de soporte

```text
web/
├── backend/
│   ├── __init__.py
│   ├── connection_manager.py
│   ├── frame_processor.py
│   ├── main.py
│   └── settings.py
├── frontend/
│   ├── camera.html
│   ├── camera.js
│   ├── index.html
│   ├── styles.css
│   ├── viewer.html
│   └── viewer.js
├── tests/
│   ├── live_smoke.py
│   └── test_relay.py
├── .gitignore
├── pytest.ini
├── README.md
├── requirements.txt
├── run.ps1
├── setup.ps1
├── start_tunnel.ps1
└── contexto_web.md
```

`.gitignore` excluye el entorno virtual, cachés de Python y cachés de pytest.
Los archivos fuente, documentación y pruebas sí deben quedar versionados.
