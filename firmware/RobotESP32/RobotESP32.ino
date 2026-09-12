#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <esp_arduino_version.h>

// Puente H L298N: motor A es el lado izquierdo y motor B el lado derecho.
constexpr uint8_t PIN_ENA = 25;
constexpr uint8_t PIN_IN1 = 26;
constexpr uint8_t PIN_IN2 = 27;
constexpr uint8_t PIN_ENB = 32;
constexpr uint8_t PIN_IN3 = 33;
constexpr uint8_t PIN_IN4 = 18;

// Estas constantes permiten adaptar el sentido si se cambia el cableado.
constexpr bool INVERT_LEFT = false;
constexpr bool INVERT_RIGHT = false;

constexpr uint32_t PWM_FREQUENCY = 5000;
constexpr uint8_t PWM_RESOLUTION = 8;
constexpr uint8_t PWM_DUTY = 180;
constexpr uint8_t PWM_CHANNEL_LEFT = 0;
constexpr uint8_t PWM_CHANNEL_RIGHT = 1;
constexpr uint32_t DIRECTION_SETTLE_MS = 30;
constexpr uint32_t COMMAND_WATCHDOG_MS = 500;

const char AP_SSID[] = "Robot-ESP32";
const char AP_PASSWORD[] = "robot-esp32";

WebServer server(80);

enum Motion : uint8_t {
  MOTION_STOP = 0,
  MOTION_FORWARD,
  MOTION_BACKWARD,
  MOTION_LEFT,
  MOTION_RIGHT
};

Motion currentMotion = MOTION_STOP;
Motion requestedMotion = MOTION_STOP;
uint32_t lastCommandAt = 0;
portMUX_TYPE motionMux = portMUX_INITIALIZER_UNLOCKED;

// Interfaz completa embebida para que el robot funcione sin archivos externos.
static const char INDEX_HTML[] PROGMEM = R"rawliteral(
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <title>Robot ESP32</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center;
      background: #10151d; color: #f5f7fa; touch-action: none; }
    main { width: min(94vw, 460px); text-align: center; padding: 1.25rem; }
    h1 { margin: 0 0 .35rem; font-size: clamp(1.5rem, 6vw, 2.1rem); }
    p { margin: 0 0 1.3rem; color: #aab4c3; }
    .pad { display: grid; grid-template-columns: repeat(3, 1fr); gap: .7rem;
      max-width: 360px; margin: auto; }
    button { min-height: 76px; border: 0; border-radius: 16px; color: white;
      background: #1f6feb; font-size: 2rem; font-weight: 700;
      user-select: none; -webkit-user-select: none; touch-action: none;
      -webkit-tap-highlight-color: transparent; }
    button[data-dir="S"] { background: #b42318; font-size: 1.1rem; }
    button:active, button.pressed { filter: brightness(1.25); transform: scale(.97); }
    .empty { visibility: hidden; }
    #status { min-height: 1.5em; margin-top: 1rem; font-size: .95rem; color: #81d4a7; }
  </style>
</head>
<body>
  <main>
    <h1>Control del robot</h1>
    <p>Mantené presionado un botón para moverlo</p>
    <section class="pad" aria-label="Controles de movimiento">
      <span class="empty" aria-hidden="true"></span>
      <button type="button" data-dir="F" aria-label="Avanzar">▲</button>
      <span class="empty" aria-hidden="true"></span>
      <button type="button" data-dir="L" aria-label="Girar a la izquierda">◀</button>
      <button type="button" data-dir="S" aria-label="Detener">STOP</button>
      <button type="button" data-dir="R" aria-label="Girar a la derecha">▶</button>
      <span class="empty" aria-hidden="true"></span>
      <button type="button" data-dir="B" aria-label="Retroceder">▼</button>
      <span class="empty" aria-hidden="true"></span>
    </section>
    <div id="status" role="status" aria-live="polite">Listo</div>
  </main>
  <script>
    (() => {
      let active = null;
      let timer = null;
      let generation = 0;
      let movementRequest = null;
      const status = document.getElementById('status');
      const buttons = document.querySelectorAll('button[data-dir]');

      async function send(dir, keepalive = false, signal = undefined) {
        try {
          const response = await fetch('/command?dir=' + encodeURIComponent(dir), {
            method: 'POST', cache: 'no-store', credentials: 'same-origin',
            keepalive, signal
          });
          if (!response.ok) throw new Error('HTTP ' + response.status);
          status.textContent = dir === 'S' ? 'Detenido' : 'Comando: ' + dir;
          return true;
        } catch (error) {
          if (error.name !== 'AbortError') status.textContent = 'Sin conexión';
          return false;
        }
      }

      function clearActive() {
        if (timer !== null) { clearTimeout(timer); timer = null; }
        if (active !== null) { active.classList.remove('pressed'); active = null; }
        if (movementRequest !== null) {
          movementRequest.abort();
          movementRequest = null;
        }
      }

      function stop() {
        const releasedDir = active === null ? null : active.dataset.dir;
        generation++;
        clearActive();
        if (releasedDir !== null) {
          console.log('[RobotESP32] Botón liberado:', releasedDir, '-> STOP');
        }
        // Solo STOP usa keepalive para tener una oportunidad extra al cerrar la página.
        send('S', true);
      }

      async function renew(dir, token) {
        if (token !== generation || active === null) return;
        const controller = new AbortController();
        movementRequest = controller;
        await send(dir, false, controller.signal);
        if (movementRequest === controller) movementRequest = null;
        if (token === generation && active !== null) {
          timer = setTimeout(() => renew(dir, token), 150);
        }
      }

      function start(button) {
        // Cancela el control anterior sin enviar un STOP que pueda competir
        // en la red con el nuevo comando.
        clearActive();
        const token = ++generation;
        active = button;
        active.classList.add('pressed');
        const dir = active.dataset.dir;
        console.log('[RobotESP32] Botón presionado:', dir);
        // Espera cada respuesta antes de renovar: nunca acumula comandos viejos.
        renew(dir, token);
      }

      buttons.forEach(button => {
        button.addEventListener('pointerdown', event => {
          event.preventDefault();
          start(button);
        });
        button.addEventListener('pointerup', event => {
          event.preventDefault();
          stop();
        });
        button.addEventListener('pointercancel', stop);
        button.addEventListener('pointerleave', stop);
      });
      window.addEventListener('blur', stop);
      document.addEventListener('visibilitychange', () => {
        if (document.visibilityState !== 'visible') stop();
      });
      window.addEventListener('pagehide', stop);
    })();
  </script>
</body>
</html>
)rawliteral";

void addNoCacheHeaders() {
  server.sendHeader("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
  server.sendHeader("Pragma", "no-cache");
  server.sendHeader("Expires", "0");
}

void sendText(int statusCode, const char *body) {
  addNoCacheHeaders();
  server.send(statusCode, "text/plain; charset=utf-8", body);
}

bool attachMotorPwm(uint8_t pin, uint8_t channel) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  (void)channel;
  return ledcAttach(pin, PWM_FREQUENCY, PWM_RESOLUTION);
#else
  const double configuredFrequency =
      ledcSetup(channel, PWM_FREQUENCY, PWM_RESOLUTION);
  ledcAttachPin(pin, channel);
  return configuredFrequency > 0;
#endif
}

void writeMotorPwm(uint8_t pin, uint8_t channel, uint8_t duty) {
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  (void)channel;
  ledcWrite(pin, duty);
#else
  (void)pin;
  ledcWrite(channel, duty);
#endif
}

void stopMotors() {
  // Primero se quita el PWM y después se dejan las entradas en estado seguro.
  writeMotorPwm(PIN_ENA, PWM_CHANNEL_LEFT, 0);
  writeMotorPwm(PIN_ENB, PWM_CHANNEL_RIGHT, 0);
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_IN3, LOW);
  digitalWrite(PIN_IN4, LOW);
}

void setMotor(uint8_t enablePin, uint8_t pwmChannel,
              uint8_t inputA, uint8_t inputB, bool forward, bool invert) {
  if (invert) forward = !forward;
  digitalWrite(inputA, forward ? HIGH : LOW);
  digitalWrite(inputB, forward ? LOW : HIGH);
  writeMotorPwm(enablePin, pwmChannel, PWM_DUTY);
}

void applyMotion(Motion requested) {
  if (requested == currentMotion) {
    // Un comando STOP siempre reafirma el estado seguro, incluso si ya constaba detenido.
    if (requested == MOTION_STOP) stopMotors();
    return;
  }

  // Evita invertir el puente H instantáneamente al cambiar de dirección.
  stopMotors();
  if (requested != MOTION_STOP) delay(DIRECTION_SETTLE_MS);

  switch (requested) {
    case MOTION_FORWARD:
      setMotor(PIN_ENA, PWM_CHANNEL_LEFT, PIN_IN1, PIN_IN2, true, INVERT_LEFT);
      setMotor(PIN_ENB, PWM_CHANNEL_RIGHT, PIN_IN3, PIN_IN4, true, INVERT_RIGHT);
      break;
    case MOTION_BACKWARD:
      setMotor(PIN_ENA, PWM_CHANNEL_LEFT, PIN_IN1, PIN_IN2, false, INVERT_LEFT);
      setMotor(PIN_ENB, PWM_CHANNEL_RIGHT, PIN_IN3, PIN_IN4, false, INVERT_RIGHT);
      break;
    case MOTION_LEFT:
      // Giro sobre el eje: izquierda atrás y derecha adelante.
      setMotor(PIN_ENA, PWM_CHANNEL_LEFT, PIN_IN1, PIN_IN2, false, INVERT_LEFT);
      setMotor(PIN_ENB, PWM_CHANNEL_RIGHT, PIN_IN3, PIN_IN4, true, INVERT_RIGHT);
      break;
    case MOTION_RIGHT:
      // Giro sobre el eje: izquierda adelante y derecha atrás.
      setMotor(PIN_ENA, PWM_CHANNEL_LEFT, PIN_IN1, PIN_IN2, true, INVERT_LEFT);
      setMotor(PIN_ENB, PWM_CHANNEL_RIGHT, PIN_IN3, PIN_IN4, false, INVERT_RIGHT);
      break;
    case MOTION_STOP:
    default:
      break;
  }
  currentMotion = requested;
}

void requestMotion(Motion requested) {
  const uint32_t now = millis();
  portENTER_CRITICAL(&motionMux);
  requestedMotion = requested;
  lastCommandAt = now;
  portEXIT_CRITICAL(&motionMux);
}

void motorControlTask(void *parameter) {
  (void)parameter;

  for (;;) {
    const uint32_t now = millis();
    Motion target;

    portENTER_CRITICAL(&motionMux);
    target = requestedMotion;
    if (target != MOTION_STOP &&
        (now - lastCommandAt) > COMMAND_WATCHDOG_MS) {
      requestedMotion = MOTION_STOP;
      target = MOTION_STOP;
    }
    portEXIT_CRITICAL(&motionMux);

    // Esta tarea es la única que modifica los motores durante el funcionamiento.
    applyMotion(target);
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

Motion motionFromChar(char command) {
  switch (command) {
    case 'F': return MOTION_FORWARD;
    case 'B': return MOTION_BACKWARD;
    case 'L': return MOTION_LEFT;
    case 'R': return MOTION_RIGHT;
    case 'S': return MOTION_STOP;
    default:  return MOTION_STOP;
  }
}

void handleRoot() {
  addNoCacheHeaders();
  server.send_P(200, "text/html; charset=utf-8", INDEX_HTML);
}

void handleCommand() {
  if (server.method() != HTTP_POST || !server.hasArg("dir")) {
    requestMotion(MOTION_STOP);
    sendText(400, "Comando invalido");
    return;
  }

  String argument = server.arg("dir");
  if (argument.length() != 1) {
    requestMotion(MOTION_STOP);
    sendText(400, "Comando invalido");
    return;
  }

  const char command = argument.charAt(0);
  const Motion requested = motionFromChar(command);
  if (command != 'F' && command != 'B' && command != 'L' &&
      command != 'R' && command != 'S') {
    requestMotion(MOTION_STOP);
    Serial.printf("[WEB] Comando invalido: %c\n", command);
    sendText(400, "Comando invalido");
    return;
  }

  Serial.printf("[WEB] Comando recibido: %c\n", command);
  requestMotion(requested);
  sendText(200, "OK");
}

void handleNotFound() {
  sendText(404, "No encontrado");
}

void setup() {
  Serial.begin(115200);

  // El robot queda detenido antes de iniciar cualquier comunicación inalámbrica.
  pinMode(PIN_ENA, OUTPUT);
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
  pinMode(PIN_ENB, OUTPUT);
  pinMode(PIN_IN3, OUTPUT);
  pinMode(PIN_IN4, OUTPUT);
  digitalWrite(PIN_ENA, LOW);
  digitalWrite(PIN_ENB, LOW);
  digitalWrite(PIN_IN1, LOW);
  digitalWrite(PIN_IN2, LOW);
  digitalWrite(PIN_IN3, LOW);
  digitalWrite(PIN_IN4, LOW);

  // Compatible con las APIs PWM de Arduino-ESP32 2.x y 3.x.
  const bool pwmLeftReady = attachMotorPwm(PIN_ENA, PWM_CHANNEL_LEFT);
  const bool pwmRightReady = attachMotorPwm(PIN_ENB, PWM_CHANNEL_RIGHT);
  stopMotors();
  currentMotion = MOTION_STOP;
  requestedMotion = MOTION_STOP;
  lastCommandAt = millis();

  if (!pwmLeftReady || !pwmRightReady) {
    Serial.println("ERROR: no se pudo iniciar el PWM; motores bloqueados.");
    while (true) delay(1000);
  }

  WiFi.mode(WIFI_AP);
  if (!WiFi.softAP(AP_SSID, AP_PASSWORD, 1, false, 1)) {
    stopMotors();
    Serial.println("ERROR: no se pudo crear la red Wi-Fi; motores bloqueados.");
    while (true) delay(1000);
  }

  server.on("/", HTTP_GET, handleRoot);
  server.on("/command", HTTP_ANY, handleCommand);
  server.onNotFound(handleNotFound);

  const BaseType_t taskReady = xTaskCreate(
      motorControlTask, "motor-control", 3072, nullptr, 2, nullptr);
  if (taskReady != pdPASS) {
    stopMotors();
    Serial.println("ERROR: no se pudo iniciar la seguridad de motores.");
    while (true) delay(1000);
  }

  server.begin();

  Serial.print("Control listo en http://");
  Serial.println(WiFi.softAPIP());
}

void loop() {
  server.handleClient();
  delay(1);
}
