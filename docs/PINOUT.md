# Pinout del robot ESP32

Este documento corresponde al cableado definido en `src/RobotESP32.ino` para un
ESP32 clásico y un controlador de motores L298N.

## ESP32 a L298N

| Función | Pin L298N | GPIO ESP32 | Descripción |
|---|---:|---:|---|
| PWM motor izquierdo | ENA | GPIO 25 | Control de velocidad del motor A |
| Dirección izquierda 1 | IN1 | GPIO 26 | Sentido del motor A |
| Dirección izquierda 2 | IN2 | GPIO 27 | Sentido del motor A |
| PWM motor derecho | ENB | GPIO 32 | Control de velocidad del motor B |
| Dirección derecha 1 | IN3 | GPIO 33 | Sentido del motor B |
| Dirección derecha 2 | IN4 | GPIO 18 | Sentido del motor B |
| Referencia eléctrica | GND | GND | Masa común obligatoria |

Para que el ESP32 controle la velocidad por PWM, hay que retirar los jumpers de
`ENA` y `ENB` del módulo L298N antes de conectar los GPIO 25 y 32.

## L298N a motores

| Salida L298N | Conexión |
|---|---|
| OUT1 y OUT2 | Motor izquierdo (motor A) |
| OUT3 y OUT4 | Motor derecho (motor B) |

Si un motor gira al revés, se pueden intercambiar sus dos cables o cambiar la
constante correspondiente en el firmware:

```cpp
constexpr bool INVERT_LEFT = false;
constexpr bool INVERT_RIGHT = false;
```

## Alimentación

- Conectar la fuente de los motores al borne de alimentación de motores del
  L298N (`12V`, `VIN` o `Vs`, según el módulo).
- Conectar el negativo de esa fuente a `GND` del L298N.
- Unir `GND` del L298N con `GND` del ESP32.
- No alimentar los motores desde los pines `3V3` o `5V` del ESP32.
- No conectar la tensión de los motores directamente al ESP32.
- Verificar la configuración del jumper/regulador de `5V` del módulo L298N según
  la tensión utilizada y las indicaciones del fabricante.

## Resumen visual

```text
ESP32                         L298N
GPIO 25  ------------------>  ENA
GPIO 26  ------------------>  IN1       OUT1/OUT2 --> Motor izquierdo
GPIO 27  ------------------>  IN2

GPIO 32  ------------------>  ENB
GPIO 33  ------------------>  IN3       OUT3/OUT4 --> Motor derecho
GPIO 18  ------------------>  IN4

GND      -------------------  GND       <-- negativo de fuente de motores
                                      
Fuente + ------------------>  12V/VIN/Vs del L298N
```

## Control Wi-Fi

Una vez iniciado el ESP32:

- Red: `Robot-ESP32`
- Contraseña: `robot-esp32`
- Panel de control: <http://192.168.4.1>

