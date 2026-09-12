# Frontend del MVP

El frontend usa HTML, CSS y JavaScript nativo. No requiere instalar dependencias ni ejecutar un paso de compilación.

## Vistas

- `/camera/`: solicita la cámara tras una acción del usuario, comprime frames JPEG y los envía al backend.
- `/viewer/`: recibe los frames procesados y actualiza las métricas en vivo.
- `/viewer/?demo=1`: simula video y telemetría para presentar la interfaz sin backend.
- `/viewer/?mock_metrics=1`: usa la cámara desplegada y simula solamente las métricas de YOLO.

Para revisar el frontend localmente:

```bash
python3 -m http.server 8080 --directory web/frontend
```

Luego abrir `http://localhost:8080/viewer/?demo=1`. El acceso real a la cámara desde otro dispositivo requiere HTTPS; en la demo se obtendrá mediante Cloudflare Tunnel.

Mientras se ejecute localmente, el visor se conecta por defecto al backend temporal actual:

```text
wss://entrance-could-aye-que.trycloudflare.com/ws/viewer
```

Para mostrar la cámara real con analítica simulada durante la preparación de la demo, abrir `http://localhost:8080/viewer/?mock_metrics=1`.

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
