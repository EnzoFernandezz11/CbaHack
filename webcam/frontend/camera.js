"use strict";

const preview = document.querySelector("#cameraPreview");
const canvas = document.querySelector("#captureCanvas");
const context = canvas.getContext("2d", { alpha: false, desynchronized: true });
const placeholder = document.querySelector("#cameraPlaceholder");
const startButton = document.querySelector("#startButton");
const stopButton = document.querySelector("#stopButton");
const fpsSetting = document.querySelector("#fpsSetting");
const widthSetting = document.querySelector("#widthSetting");
const qualitySetting = document.querySelector("#qualitySetting");
const qualityValue = document.querySelector("#qualityValue");
const connectionStatus = document.querySelector("#connectionStatus");
const connectionDot = document.querySelector("#connectionDot");
const secureStatus = document.querySelector("#secureStatus");
const errorMessage = document.querySelector("#errorMessage");
const sentFps = document.querySelector("#sentFps");
const sentFrames = document.querySelector("#sentFrames");
const frameResolution = document.querySelector("#frameResolution");
const bufferedBytes = document.querySelector("#bufferedBytes");

let mediaStream = null;
let socket = null;
let transmitting = false;
let encodingFrame = false;
let inFlightFrames = 0;
const maximumInFlightFrames = 2;
let captureTimer = null;
let reconnectTimer = null;
let totalFrames = 0;
let framesThisSecond = 0;
let lastCaptureAt = 0;

function websocketUrl(path) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

function setStatus(message, tone = "neutral") {
  connectionStatus.textContent = message;
  connectionDot.className = `status-dot ${tone}`;
}

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function clearError() {
  errorMessage.hidden = true;
  errorMessage.textContent = "";
}

function updateSecureContextNotice() {
  if (window.isSecureContext) {
    secureStatus.textContent = "Conexión segura";
    return;
  }
  secureStatus.textContent = "Se requiere HTTPS en el teléfono";
}

function connectSocket() {
  if (!transmitting || socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) {
    return;
  }

  setStatus("Conectando con el servidor…", "warning");
  const currentSocket = new WebSocket(websocketUrl("/ws/camera"));
  socket = currentSocket;
  currentSocket.binaryType = "arraybuffer";

  currentSocket.addEventListener("open", () => {
    if (socket !== currentSocket) return;
    inFlightFrames = 0;
    setStatus("Transmitiendo", "online");
    clearError();
    scheduleCapture(0);
  });

  currentSocket.addEventListener("message", (event) => {
    if (typeof event.data !== "string") return;
    try {
      const message = JSON.parse(event.data);
      if (message.type === "error") showError(message.message);
      if (message.type === "frame_ack") {
        inFlightFrames = Math.max(0, inFlightFrames - 1);
        scheduleCapture();
      }
    } catch {
      // Los mensajes no JSON no forman parte del protocolo actual.
    }
  });

  currentSocket.addEventListener("close", (event) => {
    if (socket === currentSocket) socket = null;
    inFlightFrames = 0;
    if (!transmitting) return;
    setStatus("Reconectando…", "warning");
    if (event.code === 1008) {
      showError("Ya existe otra cámara conectada al servidor.");
    }
    window.clearTimeout(reconnectTimer);
    reconnectTimer = window.setTimeout(connectSocket, 1500);
  });

  currentSocket.addEventListener("error", () => {
    setStatus("Error de conexión", "offline");
  });
}

function targetInterval() {
  return 1000 / Number(fpsSetting.value);
}

function scheduleCapture(delay) {
  window.clearTimeout(captureTimer);
  if (!transmitting) return;
  const elapsed = performance.now() - lastCaptureAt;
  const nextDelay = delay ?? Math.max(0, targetInterval() - elapsed);
  captureTimer = window.setTimeout(captureFrame, nextDelay);
}

function captureFrame() {
  if (!transmitting) return;

  if (
    encodingFrame ||
    inFlightFrames >= maximumInFlightFrames ||
    preview.readyState < HTMLMediaElement.HAVE_CURRENT_DATA ||
    socket?.readyState !== WebSocket.OPEN ||
    socket.bufferedAmount > 0
  ) {
    scheduleCapture(Math.min(50, targetInterval()));
    return;
  }

  const sourceWidth = preview.videoWidth;
  const sourceHeight = preview.videoHeight;
  if (!sourceWidth || !sourceHeight) {
    scheduleCapture(Math.min(50, targetInterval()));
    return;
  }

  const requestedWidth = Number(widthSetting.value);
  const outputWidth = Math.min(sourceWidth, requestedWidth);
  const outputHeight = Math.max(1, Math.round(sourceHeight * (outputWidth / sourceWidth)));
  if (canvas.width !== outputWidth || canvas.height !== outputHeight) {
    canvas.width = outputWidth;
    canvas.height = outputHeight;
    frameResolution.textContent = `${outputWidth} × ${outputHeight}`;
  }

  context.drawImage(preview, 0, 0, outputWidth, outputHeight);
  lastCaptureAt = performance.now();
  encodingFrame = true;
  canvas.toBlob(
    (blob) => {
      encodingFrame = false;
      if (!blob || !transmitting || socket?.readyState !== WebSocket.OPEN) {
        scheduleCapture();
        return;
      }
      if (socket.bufferedAmount > 0) {
        scheduleCapture(Math.min(50, targetInterval()));
        return;
      }
      inFlightFrames += 1;
      try {
        socket.send(blob);
      } catch (error) {
        inFlightFrames = Math.max(0, inFlightFrames - 1);
        showError(`No se pudo enviar el frame: ${error?.message ?? error}`);
        scheduleCapture();
        return;
      }
      totalFrames += 1;
      framesThisSecond += 1;
      sentFrames.textContent = String(totalFrames);
      scheduleCapture();
    },
    "image/jpeg",
    Number(qualitySetting.value) / 100,
  );
}

async function startTransmission() {
  clearError();
  if (!window.isSecureContext) {
    showError("Abra esta página mediante HTTPS para que el teléfono permita usar la cámara.");
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    showError("Este navegador no ofrece acceso a la cámara mediante getUserMedia().");
    return;
  }

  startButton.disabled = true;
  setStatus("Solicitando cámara…", "warning");
  try {
    const requestedWidth = Number(widthSetting.value);
    const requestedFps = Number(fpsSetting.value);
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: { ideal: "environment" },
        width: { ideal: requestedWidth },
        height: { ideal: Math.round(requestedWidth * 9 / 16) },
        frameRate: { ideal: requestedFps, max: Math.max(requestedFps, 15) },
      },
    });
    preview.srcObject = mediaStream;
    await preview.play();
    transmitting = true;
    placeholder.hidden = true;
    stopButton.disabled = false;
    fpsSetting.disabled = true;
    widthSetting.disabled = true;
    connectSocket();
  } catch (error) {
    startButton.disabled = false;
    setStatus("No se pudo iniciar", "offline");
    if (error?.name === "NotAllowedError") {
      showError("El permiso de cámara fue rechazado. Habilítelo en la configuración del navegador.");
    } else {
      showError(`No se pudo abrir la cámara: ${error?.message ?? error}`);
    }
  }
}

function stopTransmission() {
  transmitting = false;
  encodingFrame = false;
  inFlightFrames = 0;
  lastCaptureAt = 0;
  window.clearTimeout(captureTimer);
  window.clearTimeout(reconnectTimer);
  const closingSocket = socket;
  socket = null;
  closingSocket?.close(1000, "Transmisión detenida");
  mediaStream?.getTracks().forEach((track) => track.stop());
  mediaStream = null;
  preview.srcObject = null;
  placeholder.hidden = false;
  startButton.disabled = false;
  stopButton.disabled = true;
  fpsSetting.disabled = false;
  widthSetting.disabled = false;
  frameResolution.textContent = "—";
  setStatus("Transmisión detenida", "neutral");
}

qualitySetting.addEventListener("input", () => {
  qualityValue.textContent = `${qualitySetting.value} %`;
});
startButton.addEventListener("click", startTransmission);
stopButton.addEventListener("click", stopTransmission);
window.addEventListener("pagehide", stopTransmission);

window.setInterval(() => {
  sentFps.textContent = framesThisSecond.toFixed(1);
  framesThisSecond = 0;
  bufferedBytes.textContent = `${Math.round((socket?.bufferedAmount ?? 0) / 1024)} KB`;
}, 1000);

updateSecureContextNotice();
