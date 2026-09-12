"use strict";

const remoteFrame = document.querySelector("#remoteFrame");
const placeholder = document.querySelector("#viewerPlaceholder");
const placeholderText = document.querySelector("#placeholderText");
const connectionStatus = document.querySelector("#connectionStatus");
const connectionDot = document.querySelector("#connectionDot");
const cameraStatus = document.querySelector("#cameraStatus");
const receivedFps = document.querySelector("#receivedFps");
const receivedFrames = document.querySelector("#receivedFrames");
const frameAge = document.querySelector("#frameAge");
const viewerCount = document.querySelector("#viewerCount");

let socket = null;
let reconnectTimer = null;
let reconnectDelay = 1000;
let objectUrl = null;
let totalFrames = 0;
let framesThisSecond = 0;
let lastFrameAt = null;
let cameraConnected = false;

function websocketUrl(path) {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

function setConnection(message, tone) {
  connectionStatus.textContent = message;
  connectionDot.className = `status-dot ${tone}`;
}

function updateCameraState(connected) {
  cameraConnected = connected;
  cameraStatus.textContent = connected ? "Cámara conectada" : "Cámara desconectada";
  if (!connected) {
    placeholder.hidden = false;
    placeholderText.textContent = "Esperando que se conecte la cámara…";
  }
}

function showFrame(blob) {
  const nextUrl = URL.createObjectURL(blob);
  const previousUrl = objectUrl;
  objectUrl = nextUrl;
  remoteFrame.addEventListener(
    "load",
    () => {
      if (previousUrl) URL.revokeObjectURL(previousUrl);
      placeholder.hidden = true;
    },
    { once: true },
  );
  remoteFrame.src = nextUrl;
  totalFrames += 1;
  framesThisSecond += 1;
  lastFrameAt = performance.now();
  receivedFrames.textContent = String(totalFrames);
}

function handleTextMessage(rawMessage) {
  try {
    const message = JSON.parse(rawMessage);
    if (message.type === "system_status") {
      updateCameraState(Boolean(message.camera_connected));
      viewerCount.textContent = String(message.viewer_count ?? 1);
    }
  } catch {
    // Los mensajes no JSON no forman parte del protocolo actual.
  }
}

function connect() {
  setConnection("Conectando con el servidor…", "warning");
  const currentSocket = new WebSocket(websocketUrl("/ws/viewer"));
  socket = currentSocket;
  currentSocket.binaryType = "blob";

  currentSocket.addEventListener("open", () => {
    if (socket !== currentSocket) return;
    reconnectDelay = 1000;
    setConnection("Servidor conectado", "online");
  });

  currentSocket.addEventListener("message", (event) => {
    if (typeof event.data === "string") {
      handleTextMessage(event.data);
    } else {
      showFrame(event.data);
    }
  });

  currentSocket.addEventListener("close", () => {
    if (socket === currentSocket) socket = null;
    setConnection("Servidor desconectado", "offline");
    updateCameraState(false);
    window.clearTimeout(reconnectTimer);
    reconnectTimer = window.setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 1.7, 5000);
  });

  currentSocket.addEventListener("error", () => {
    setConnection("Error de conexión", "offline");
  });
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) return;
    const status = await response.json();
    updateCameraState(Boolean(status.camera_connected));
    viewerCount.textContent = String(status.viewer_count ?? 0);
    if (status.last_frame_age_ms !== null) {
      frameAge.textContent = status.last_frame_age_ms < 1000
        ? `${Math.round(status.last_frame_age_ms)} ms`
        : `${(status.last_frame_age_ms / 1000).toFixed(1)} s`;
    }
  } catch {
    // El estado visual del WebSocket ya informa una caída del servidor.
  }
}

window.setInterval(() => {
  receivedFps.textContent = framesThisSecond.toFixed(1);
  framesThisSecond = 0;
  if (lastFrameAt !== null) {
    const localAge = performance.now() - lastFrameAt;
    if (localAge > 3000 && cameraConnected) {
      placeholder.hidden = false;
      placeholderText.textContent = "La cámara está conectada, pero no llegan frames…";
    }
  }
}, 1000);

window.setInterval(refreshStatus, 2000);
window.addEventListener("pagehide", () => {
  window.clearTimeout(reconnectTimer);
  socket?.close(1000, "Viewer cerrado");
  if (objectUrl) URL.revokeObjectURL(objectUrl);
});

connect();
refreshStatus();

