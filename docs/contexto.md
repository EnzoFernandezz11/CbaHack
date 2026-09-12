# Contexto del proyecto

## Hackathon

Este proyecto se desarrolla durante HackCórdoba, dentro del track de Agro. El objetivo de la hackathon no es construir una máquina agrícola lista para producción, sino demostrar mediante un prototipo integrado que la detección y recuperación asistida de vainas de maní es técnicamente posible.

La demostración combinará robótica, visión por computadora y una aplicación web en tiempo real.

## Problema

La cosecha del maní ocurre en dos etapas principales: arrancado y recolección o descapotado. Durante estas operaciones, una parte de las vainas, también llamadas cajas, puede desprenderse y quedar en el campo.

Las pérdidas dependen del estado del cultivo, el momento de cosecha, las condiciones del suelo y la regulación de la maquinaria. Como orden de magnitud, distintos relevamientos sitúan las pérdidas alrededor del 4 % al 10 % del rendimiento. Este prototipo se concentra exclusivamente en las vainas visibles sobre la superficie.

Debido a la superficie destinada al cultivo y al volumen producido en Argentina, incluso un porcentaje relativamente pequeño puede representar una cantidad importante de producto no recolectado.

Como referencia de escala, la Secretaría de Agricultura estimó para la campaña 2025/26 aproximadamente 416.000 hectáreas implantadas y 1,3 millones de toneladas de maní en caja. Estas cifras contextualizan el problema, pero no deben utilizarse para afirmar que todo el volumen perdido es visible o recuperable por el prototipo.

## Hipótesis

Una cámara montada sobre una plataforma móvil puede observar el suelo y transmitir imágenes a un modelo de visión por computadora. El modelo puede detectar las vainas visibles y producir información útil para:

- Identificar vainas potencialmente recuperables.
- Contar las vainas presentes en un área conocida.
- Estimar la pérdida superficial en kg/ha.
- Visualizar el funcionamiento y la latencia del sistema en tiempo real.

En un desarrollo futuro, estas detecciones podrían dirigir un cabezal de aspiración u otro mecanismo de recolección. Ese mecanismo industrial no forma parte del alcance de esta hackathon.

## Alcance de la demostración

El MVP debe demostrar el siguiente flujo completo:

1. Un robot controlado por una ESP32 se desplaza sobre una bandeja con tierra, rastrojo y vainas de maní.
2. Un celular montado en el robot captura imágenes reales del suelo.
3. El celular envía frames a un backend de inferencia.
4. Un modelo YOLO entrenado para este caso detecta las vainas visibles.
5. El backend dibuja las cajas de detección sobre cada imagen.
6. La pantalla de la computadora muestra en tiempo real los frames procesados.

```text
Celular sobre el robot
          |
          | frames JPEG por WebSocket
          v
Backend Python + YOLO
          |
          | frames procesados con boxes
          v
Pantalla de la computadora

Celular de control -- Wi-Fi local --> ESP32 --> motores del robot
```

La conducción del robot y el procesamiento de imágenes son dos canales independientes. Pueden utilizarse uno o dos celulares según la topología de red disponible durante la presentación.

## Arquitectura de transmisión y visualización

Para la demo se utilizará WebSocket y se transmitirán imágenes JPEG sucesivas, en lugar de implementar streaming mediante WebRTC. Este enfoque reduce la complejidad y permite que una frecuencia aproximada de 5 a 10 FPS se perciba como video en tiempo real.

La aplicación expondrá dos páginas:

- `/camera`: se abrirá en el celular montado sobre el robot, solicitará acceso a su cámara y enviará los frames JPEG al backend mediante WebSocket.
- `/viewer`: se abrirá en la computadora utilizada para la presentación y mostrará los frames procesados con las cajas de detección dibujadas.

Por cada frame recibido, el backend realizará el siguiente flujo:

1. Recibir el frame enviado desde `/camera`.
2. Ejecutar la inferencia con el modelo YOLO.
3. Dibujar las boxes sobre el frame.
4. Enviar el frame procesado a los clientes conectados a `/viewer`.

El servidor web, el backend Python y el modelo YOLO se ejecutarán juntos en la notebook. Para que el celular pueda acceder a la aplicación mediante una URL HTTPS, el servidor local se expondrá temporalmente con Cloudflare Tunnel:

```text
Notebook
|-- Backend Python + YOLO
|-- /camera
`-- /viewer
          |
          v
Cloudflare Tunnel
          |
          v
URL pública HTTPS
```

Cloudflare Tunnel establece una conexión saliente desde la notebook hacia Cloudflare, por lo que no es necesario que el celular y la notebook estén conectados a la misma red. Ambos dispositivos sí necesitan acceso a Internet durante la demo. La URL pública permitirá abrir `/camera` desde el celular y `/viewer` desde la computadora sin desplegar el modelo en la nube ni abrir puertos del router.

Si el celular utilizado como cámara también se conecta al punto de acceso de la ESP32 y esa red no brinda Internet, perderá el acceso al túnel. Para evitarlo, se utilizará preferentemente otro dispositivo para controlar el robot o se conectarán la ESP32, el celular y la notebook a una red con Internet.

## Cálculo demostrativo de kg/ha

La estimación se obtendrá a partir de:

- La cantidad de vainas detectadas en el frame actual.
- El área real cubierta por la imagen, obtenida mediante una calibración previa.
- Un peso promedio configurable por vaina.

```text
kg/ha = vainas_detectadas * peso_promedio_vaina_g * 10 / area_observada_m2
```

Este valor será una estimación para demostrar el concepto, no una medición agronómica certificada. El conteo inicial será por frame y no acumulativo, ya que sumar detecciones entre frames sin seguimiento produciría duplicados. Estas métricas podrán incorporarse como información complementaria, pero la visualización principal del MVP será el video procesado con las cajas de detección.

## Organización del repositorio

El repositorio se divide por responsabilidad. El nombre existente de la carpeta de visión es `cv/`, en minúsculas, y debe mantenerse así para evitar problemas en sistemas sensibles a mayúsculas y minúsculas.

### `cv/`

Contendrá todo lo relacionado con visión por computadora y entrenamiento de YOLO:

- Preparación y configuración de datasets.
- Convenciones y clases utilizadas para el etiquetado.
- Scripts o notebooks de entrenamiento y fine-tuning.
- Evaluación del modelo.
- Pruebas de inferencia sobre imágenes y videos.
- Pesos entrenados o instrucciones para obtenerlos cuando sean demasiado grandes para Git.
- Exportaciones del modelo necesarias para inferencia.

El código de entrenamiento permanecerá separado del servidor web. El backend consumirá el modelo producido en esta carpeta mediante una ruta o variable de configuración.

### `firmware/`

Contendrá el firmware de la ESP32 y el control de la plataforma móvil:

- Configuración de Wi-Fi en modo punto de acceso, estación o ambos.
- Servidor local o WebSocket para recibir comandos.
- Control de motores y dirección.
- Comandos de avance, retroceso, giro y detención.
- Watchdog y parada automática ante pérdida de conexión.
- Configuración de pines, drivers y componentes del robot.

La ESP32 no ejecutará el modelo YOLO. Su responsabilidad durante el MVP es controlar el movimiento del robot de forma segura.

### `docs/`

Contendrá la documentación de soporte:

- Arquitectura del sistema.
- Diagrama de conexiones electrónicas.
- Lista de materiales.
- Instrucciones de armado y configuración.
- Procedimiento de calibración de la cámara y del área observada.
- Decisiones técnicas y limitaciones conocidas.
- Guion, checklist y plan de contingencia para la demo.
- Fuentes agronómicas y datasets utilizados.

### `webcam/`

Esta carpeta reúne la experiencia web completa:

```text
webcam/
|-- frontend/   # páginas /camera y /viewer
|-- backend/    # WebSocket, recepción de frames e inferencia YOLO
`-- README.md   # ejecución local y exposición con Cloudflare Tunnel
```

El frontend será responsable de:

- Implementar `/camera`, solicitar acceso a la cámara del celular, capturar los frames y enviarlos como imágenes JPEG mediante WebSocket.
- Implementar `/viewer` y mostrar los frames procesados que devuelve el backend.
- Indicar el estado de la conexión durante la demostración.

El backend será responsable de:

- Recibir los frames JPEG en vivo mediante WebSocket.
- Decodificar y preparar las imágenes.
- Cargar una sola vez el modelo generado en `cv/`.
- Ejecutar la inferencia.
- Dibujar las cajas de detección sobre cada frame.
- Enviar los frames procesados a `/viewer`.
- Calcular conteos y métricas complementarias si se incorporan a la demo.

#### Estado de implementación del relay de cámara

Desde el 2026-09-12 está implementada la primera integración teléfono–computadora sin inferencia YOLO. El teléfono abre `/camera`, captura JPEG y los envía mediante `/ws/camera`; la computadora abre `/viewer` y recibe los frames mediante `/ws/viewer`. El backend FastAPI retransmite el JPEG sin modificarlo y conserva solamente el frame más reciente para evitar que una conexión lenta acumule latencia.

Esta etapa incluye indicadores de conexión y FPS, reconexión del viewer, configuración de resolución y calidad JPEG, un endpoint `/api/status`, pruebas automáticas y scripts de instalación y ejecución para Windows. `webcam/backend/frame_processor.py` mantiene aislado el punto donde se incorporará YOLO posteriormente.

Para acceder a la cámara desde un teléfono se debe usar la URL HTTPS generada por Cloudflare Tunnel. Las instrucciones operativas se encuentran en `webcam/README.md`.

La implementación fue verificada el 2026-09-12 tanto sobre `localhost` como a través de un Quick Tunnel HTTPS real. La prueba externa confirmó HTTP, WebSocket seguro, retransmisión binaria exacta de un JPEG y notificaciones de conexión y desconexión. El túnel utilizado para la prueba fue cerrado al finalizar.

Para el MVP no se necesita desplegar el frontend en Vercel ni ejecutar YOLO en un servidor externo. Toda la aplicación se servirá desde la notebook y se disponibilizará mediante la URL HTTPS temporal provista por Cloudflare Tunnel.

### `3models/`

La carpeta existe actualmente como placeholder, pero no tiene una responsabilidad definida para este MVP. No debe utilizarse hasta que el equipo decida si tiene un propósito concreto; los modelos YOLO y sus artefactos pertenecen a `cv/`.

### Raíz del repositorio

La raíz contendrá solamente archivos que coordinan el proyecto completo, por ejemplo:

- `README.md` con la introducción y el inicio rápido.
- `contexto.md` con la definición del problema y el alcance.
- Archivos de configuración compartidos.

## Criterios de éxito

La demostración se considerará exitosa si:

- El robot puede desplazarse y detenerse de forma controlada.
- El celular transmite imágenes reales de la bandeja.
- YOLO detecta vainas que no formaron parte del entrenamiento.
- `/viewer` muestra en vivo los frames enviados por el celular con las cajas de detección dibujadas.
- La transmisión se mantiene fluida, idealmente entre 5 y 10 FPS, sin acumular una cola creciente de frames.
- El celular puede acceder a `/camera` mediante la URL HTTPS generada por Cloudflare Tunnel.
- Una interrupción de la conexión detiene el robot de manera segura.

## Fuera de alcance

Durante la hackathon no se intentará demostrar:

- Una máquina agrícola de escala real.
- Navegación autónoma completa.
- Recuperación de vainas enterradas.
- Un sistema industrial de brazos o aspiración.
- Cobertura de hectáreas reales.
- Una estimación agronómica certificada.
- Disponibilidad, seguridad o escalabilidad de nivel productivo.

El resultado esperado es una prueba de concepto integrada que permita observar el recorrido completo desde la imagen capturada hasta la detección y visualización de la pérdida estimada.

## Referencias iniciales

- [Estimaciones Agrícolas, campaña 2025/26 - Secretaría de Agricultura](https://www.magyp.gob.ar/sitio/areas/estimaciones/_archivos/estimaciones/260000_2026/260600_Junio/260618_Informe%20mensual%20al%2018_06_2026.pdf)
- [Evaluación de pérdidas de una cosechadora de maní - Universidad Nacional de Río Cuarto](https://www.unirioeditora.com.ar/wp-content/uploads/2024/02/978-987-688-564-5.pdf)
- [Detección de pérdidas poscosecha de maní con YOLOv8 e imágenes de celular](https://www.sciencedirect.com/science/article/abs/pii/S0168169925003886)
- [Metodología para estimar pérdidas superficiales de maní - University of Georgia](https://precisionagirrigation.extension.uga.edu/2023/10/estimating-peanut-harvest-losses/)
