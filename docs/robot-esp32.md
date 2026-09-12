# Robot de dos motores con ESP32 y L298N

Esta guía describe el montaje, la carga del programa y la primera prueba de un robot de dos ruedas. Está escrita para hacer las conexiones de forma segura. La tabla de cableado es la referencia: no conectes un pin por parecido de nombre.

> **Importante:** los motores de este montaje son **motores DC con escobillas**, no servomotores. No se conectan a los pines de un servo ni se controlan con `servo.write()`. El L298N es el puente H que invierte el sentido y regula la potencia de cada motor mediante PWM.

> **La pieza de protoboard que aparece en la foto no se usa.** No hace falta colocarla en el circuito ni pasar por ella la corriente de los motores.

## Piezas

- ESP32 DevKit (la placa que se programa por USB).
- Módulo controlador de motores L298N.
- Dos motores DC con sus ruedas y un chasis.
- Portapilas de **6 pilas AA NiMH** (7,2 V nominales) para los motores.
- Powerbank USB y cable USB para alimentar el ESP32.
- Cables Dupont adecuados y, de ser posible, un interruptor para la batería de motores.
- Un condensador electrolítico de 470–1000 µF para la entrada de motor y un condensador cerámico de 100 nF por motor.
- Ordenador con Arduino IDE y un cable USB de datos.

No uses una pila rectangular de 9 V: entrega poca corriente para el arranque de los motores y puede calentarse o caer de tensión. Tampoco alimentes los motores desde el ESP32, desde el pin 3V3 ni desde una protoboard. La protoboard no está destinada a la corriente de arranque de estos motores.

## Cableado

### Señales L298N–ESP32

Antes de conectar la batería, retira los jumpers **ENA** y **ENB** del L298N. Así esos pines quedan disponibles para PWM y el programa puede regular la velocidad.

| L298N | ESP32 DevKit | Función |
|---|---:|---|
| ENA | GPIO25 | PWM y habilitación del motor izquierdo |
| IN1 | GPIO26 | Dirección del motor izquierdo |
| IN2 | GPIO27 | Dirección del motor izquierdo |
| ENB | GPIO32 | PWM y habilitación del motor derecho |
| IN3 | GPIO33 | Dirección del motor derecho |
| IN4 | GPIO18 | Dirección del motor derecho |
| GND | GND | Tierra común |

En el L298N, conecta el motor izquierdo entre **OUT1 y OUT2** y el motor derecho entre **OUT3 y OUT4**. Cada salida debe ir a los dos terminales de su motor; no conectes un terminal del motor a GND ni a 5 V.

### Alimentación

| L298N | Conectar a | Condición |
|---|---|---|
| `VS`, `+12V` o entrada de motor | Positivo del pack de 6 AA NiMH | Es la alimentación de los motores; 7,2 V nominales |
| `GND` de potencia | Negativo del pack de 6 AA NiMH | Este GND también debe unirse al GND del ESP32 |
| `5V` de lógica | Pin rotulado `5V`/`VIN` del DevKit | Solo con el DevKit alimentado por USB y después de retirar `5V-EN` |

Los nombres `VS`, `+12V` y `5V` pueden estar serigrafiados de forma distinta según el fabricante, pero las funciones son las de la tabla. Comprueba la serigrafía del módulo antes de insertar un cable.

#### Regla especial del 5 V del L298N

Muchos módulos L298N tienen un jumper llamado **5V-EN**. Ese jumper selecciona el regulador de 5 V de la placa, no es el mismo que ENA o ENB.

1. Con todo apagado, **quita `5V-EN` antes de conectar cualquier 5 V externo**.
2. Alimenta el DevKit por USB desde el powerbank.
3. Conecta **solo la lógica de 5 V** del L298N al pin del DevKit rotulado `5V` o `VIN`, según la serigrafía de esa placa. Ese pin debe tener la alimentación USB presente.
4. Nunca conectes el `5V` del L298N al pin **3V3** del ESP32.
5. Nunca mezcles dos fuentes en el mismo pin o rail de 5 V: no conectes a la vez el regulador del L298N (`5V-EN`) y el 5 V externo del DevKit.

La conexión de GND común es obligatoria para que las señales IN1–IN4 y PWM tengan una referencia compartida. El pack de pilas alimenta la etapa de motores; el powerbank alimenta el ESP32 por USB.

### Condensadores y ruido

- Coloca el electrolítico de **470–1000 µF** entre `VS` y `GND`, lo más cerca posible de los bornes de alimentación del L298N. Respeta la polaridad: `+` a `VS` y `−` a `GND`.
- Coloca un cerámico de **100 nF directamente entre los dos terminales de cada motor**, con cables cortos. No lo conectes entre un terminal y GND.
- Mantén los cables de motor y de batería cortos y separados de los cables de señal cuando sea práctico.

## Preparar Arduino IDE

1. Instala Arduino IDE 2.x y ábrelo.
2. En el gestor de placas, instala **`esp32` de Espressif Systems, versión 3.3.11**. No mezcles esta prueba con otra versión del core.
3. En **Herramientas → Placa**, selecciona **ESP32 Dev Module**.
4. Conecta el DevKit al ordenador con un cable USB de datos y elige el puerto serie correcto en **Herramientas → Puerto**.
5. Abre el sketch del robot. Selecciona la placa y el puerto antes de compilar.
6. Pulsa **Verificar**. Si el IDE pide mantener BOOT durante la carga, mantén pulsado **BOOT** mientras aparece “Connecting…” y suéltalo cuando comience la escritura.
7. Pulsa **Subir** y espera el mensaje de carga completada. El monitor serie se puede abrir a **115200 baudios** para ver la dirección de control o un error de inicio.

Para programar, deja desconectado el pack de motores o mantén las ruedas elevadas. El cable USB debe ser de datos; un cable que solo carga no permite subir el sketch.

## Primera puesta en marcha y Wi‑Fi

Haz la primera prueba con las ruedas levantadas del suelo y el chasis sujeto para que no salte. No pongas dedos, ropa ni herramientas cerca de las ruedas.

1. Con el interruptor de motores apagado, conecta el powerbank al USB del ESP32 y espera unos segundos.
2. Desde el teléfono u ordenador, busca la red Wi‑Fi **`Robot-ESP32`** y conéctate con la clave **`robot-esp32`**.
3. Abre `http://192.168.4.1` en el navegador. Si el teléfono avisa que la red no tiene Internet, conserva la conexión a esa red.
4. Comprueba que el control está en reposo y que al soltarlo se ordena detener los motores.
5. Enciende la alimentación de los motores y prueba ambos lados con pulsaciones muy breves de avance y giro. El firmware usa un límite conservador de `PWM_DUTY = 140` sobre 255 (aproximadamente 55 %); aumenta ese valor únicamente después de comprobar el comportamiento y la temperatura de los motores y del L298N.
6. Cuando cada lado responda correctamente, baja las ruedas al suelo y prueba a muy baja velocidad en un área despejada.

El orden recomendado para apagar es el inverso: detén el robot desde la página, apaga o desconecta el pack de motores y luego desconecta el powerbank. Si el control o el Wi‑Fi se pierde, corta primero la alimentación de motores.

La contraseña está escrita en el sketch para facilitar el primer uso. Cámbiala en `AP_PASSWORD` si vas a utilizar el robot cerca de otras personas; debe tener como mínimo ocho caracteres.

## Ajuste de sentido y velocidad

El sentido real depende de cómo estén montados los motores y de la polaridad de sus cables. Si un lado gira al revés:

- Revisa primero que ese motor esté en la pareja correcta: izquierdo en OUT1/OUT2 y derecho en OUT3/OUT4.
- Cambia el ajuste `INVERT` del lado correspondiente en el sketch, si el firmware ofrece esos flags. Invierte solo el lado necesario (`INVERT_LEFT` o `INVERT_RIGHT`, o el nombre equivalente que tenga el sketch).
- Como alternativa, con todo apagado, intercambia los dos cables de ese motor en su pareja OUT. No intercambies cables con el circuito energizado.

Para limitar la velocidad, reduce `PWM_DUTY` en el sketch. Con los jumpers ENA y ENB quitados, el duty se aplica a los pines GPIO25 y GPIO32. Un duty alto puede hacer que el robot arranque bruscamente y aumenta el consumo; ajusta en pasos pequeños.

## Diagnóstico

| Síntoma | Comprobaciones seguras |
|---|---|
| El ESP32 no aparece al cargar | Usa un cable USB de datos, prueba otro puerto, verifica que está seleccionado `ESP32 Dev Module` y que el core es 3.3.11. |
| El Wi‑Fi no aparece | Confirma que el sketch se cargó, reinicia el DevKit por USB y busca exactamente `Robot-ESP32`. |
| La página no abre | Mantén el dispositivo conectado a esa red Wi‑Fi y escribe `http://192.168.4.1`; no dependas de Internet móvil. |
| Ningún motor gira | Apaga todo y verifica pack 6×AA en `VS`/GND, GND común, `5V-EN` retirado y que no se haya usado 3V3 para la lógica. |
| Un motor no gira | Revisa la pareja OUT, los dos cables del motor, IN1/IN2 o IN3/IN4 y el jumper ENA/ENB correspondiente. Hazlo siempre sin alimentación. |
| Gira, pero no cambia la velocidad | Comprueba que ENA y ENB no tengan sus jumpers y que estén en GPIO25 y GPIO32; con el jumper puesto el canal queda habilitado fijo. |
| Avanza hacia atrás o gira en círculos | Ajusta el flag `INVERT` del lado que corresponda o invierte la pareja de cables con el sistema apagado. |
| El ESP32 se reinicia al arrancar | Separa las fuentes, confirma GND común, revisa polaridad del condensador y coloca 470–1000 µF entre VS-GND. No alimentes motores desde el ESP32 ni desde la protoboard. |
| Hay ruido o fallos intermitentes | Añade el condensador de 100 nF en cada motor, acorta cables y aprieta conexiones; revisa que ningún terminal de motor toque un rail de alimentación. |

No midas ni cambies conexiones con el pack conectado. Si un L298N, cable, pila o motor se calienta demasiado, desconecta ambas fuentes y deja enfriar antes de investigar.

## Lista de aceptación

Marca cada punto antes de dar por terminado el montaje:

- [ ] Los actuadores son dos motores DC, no servos.
- [ ] El motor izquierdo está en OUT1/OUT2 y el derecho en OUT3/OUT4.
- [ ] El cableado de señales coincide exactamente con ENA=25, IN1=26, IN2=27, ENB=32, IN3=33 e IN4=18.
- [ ] ESP32 GND y L298N GND están unidos; el negativo del pack también comparte ese GND.
- [ ] Los jumpers ENA y ENB fueron retirados para usar PWM.
- [ ] `5V-EN` fue retirado antes de conectar el 5 V externo.
- [ ] La lógica usa únicamente el pin 5V/VIN del DevKit alimentado por USB; nunca 3V3 y nunca dos fuentes en el mismo 5 V.
- [ ] El powerbank alimenta el ESP32 y el pack 6×AA NiMH alimenta los motores.
- [ ] No se usa una pila rectangular de 9 V ni se alimentan motores desde ESP32/protoboard.
- [ ] Hay 470–1000 µF entre VS-GND y 100 nF directamente en cada motor, con polaridad correcta en el electrolítico.
- [ ] Arduino IDE compila y carga con core ESP32 3.3.11 y placa ESP32 Dev Module.
- [ ] La red `Robot-ESP32`, clave `robot-esp32` y `http://192.168.4.1` funcionan.
- [ ] Las ruedas se probaron primero elevadas; el robot se detiene al soltar el control.
- [ ] Al apagar el Wi‑Fi del teléfono mientras se mantiene un movimiento, los motores se detienen en aproximadamente 500–700 ms.
- [ ] `PWM_DUTY` está ajustado a una velocidad controlable y los flags `INVERT` dejan ambos lados con el sentido esperado.

## Seguridad

- Trabaja con el robot inmovilizado y las ruedas elevadas durante el cableado y la primera prueba.
- Desconecta el USB y el pack de motores antes de mover un cable, cambiar un jumper o tocar una salida OUT.
- No cortocircuites `VS`, `5V` ni las salidas OUT. No conectes un motor directamente a un GPIO del ESP32.
- Respeta la polaridad del pack y del electrolítico. Usa únicamente un pack de AA NiMH en buen estado y un cargador apropiado.
- Mantén la batería y el cableado lejos de piezas móviles. Si aparece humo, olor extraño o calor excesivo, corta ambas alimentaciones de inmediato.
- Antes de una prueba en el suelo, deja un interruptor o conector de fácil acceso para cortar la batería de motores.
