# Frontend del MVP

El frontend usa HTML, CSS y JavaScript nativo. No requiere instalar dependencias ni ejecutar un paso de compilación.

## Vistas

- `/camera/`: solicita la cámara tras una acción del usuario, comprime frames JPEG y los envía al backend.
- `/viewer/`: recibe los frames procesados y muestra una animación ilustrativa de la tolva. Las métricas solo se actualizan si el backend envía telemetría real.

La vista de cámara muestra el encuadre completo, sin recortar los bordes, y ocupa como máximo el 60 % del alto de la pantalla. El visor usa un marco vertical 9:16 que se ajusta a la altura de la ventana y tiene un ancho máximo de 360 px.
El visor conserva la proporción de cada JPEG: si el celular transmite en vertical, el frame queda centrado con bandas negras a los lados.
En escritorio, Conexiones y Tolva quedan a la izquierda, el video al centro, y el mapa de pérdidas con las métricas a la derecha. Operación queda debajo de ese bloque.

Para revisar el frontend localmente:

```bash
python3 -m http.server 8080 --directory web/frontend
```

Luego abrir `http://localhost:8080/viewer/`. El acceso real a la cámara desde otro dispositivo requiere HTTPS; durante el desarrollo se obtiene mediante Cloudflare Tunnel.

Mientras se ejecute localmente, el visor se conecta por defecto al backend en:

```text
ws://127.0.0.1:8000/ws/viewer
```

El visor permite abrir la transmisión en pantalla completa desde el botón situado sobre el video o haciendo doble clic en la imagen. Se puede salir con el mismo botón o con `Esc`.

## WebSocket esperado

Por defecto, las vistas usan el mismo host desde el cual fueron servidas:

- Cámara: `ws(s)://HOST/ws/camera`
- Visor: `ws(s)://HOST/ws/viewer`

Se puede sobrescribir el endpoint con `?ws=wss://servidor/ruta`.

### Cámara hacia el backend

El backend desplegado actualmente espera cada JPEG como mensaje binario, sin metadatos previos. Este es el comportamiento predeterminado del frontend.

Cuando el backend incorpore asociación explícita por frame, se puede abrir la cámara con `?metadata=1`. En ese modo, antes de cada JPEG envía:

```json
{"type":"frame_meta","frame_id":42,"captured_at":1789189200000,"width":960,"height":540}
```

WebSocket conserva el orden de los mensajes, por lo que el backend debe asociar el JPEG binario con el `frame_meta` inmediatamente anterior. El frontend descarta frames cuando la cola de salida supera 2 MB para no acumular latencia.

### Backend hacia el visor

Para mantener la imagen y las métricas sincronizadas, el backend debe enviar primero un resultado JSON y luego el JPEG procesado correspondiente:

```json
{
  "type": "frame_result",
  "frame_id": 42,
  "detections": 14,
  "kg_ha": 6.8,
  "fps": 8.2,
  "latency_ms": 124,
  "width": 960,
  "height": 540,
  "camera_connected": true,
  "model_ready": true,
  "task_progress": 38
}
```

A continuación debe enviar el frame JPEG como mensaje binario. El visor actualiza las tarjetas al recibir el JSON y muestra el `frame_id` correspondiente al recibir la imagen.

Los controles de tarea y el mapa son interactivos, pero todavía funcionan localmente como mockup. Su integración con persistencia o planificación queda fuera de esta primera implementación.
