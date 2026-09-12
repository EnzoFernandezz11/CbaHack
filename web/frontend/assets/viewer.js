const params = new URLSearchParams(location.search);
const metricElements = {
  detections: document.querySelector('#metric-detections'),
  kg_ha: document.querySelector('#metric-loss'),
  fps: document.querySelector('#metric-fps'),
  latency_ms: document.querySelector('#metric-latency'),
};
const frameImage = document.querySelector('#processed-frame');
const placeholder = document.querySelector('#video-placeholder');
const frameInfo = document.querySelector('#frame-info');
const frameLabel = document.querySelector('#frame-label');
const videoStage = document.querySelector('#video-stage');
const fullscreenButton = document.querySelector('#fullscreen-button');
const connection = document.querySelector('#viewer-connection');
const connectionText = connection.querySelector('span:last-child');
const toast = document.querySelector('#toast');
let socket;
let currentFrameUrl;
let reconnectTimer;
let toastTimer;
let pendingTelemetry;
let receivedFrames = 0;
let framesThisSecond = 0;
let telemetryReceived = false;

function websocketUrl() {
  const explicit = params.get('ws');
  if (explicit) return explicit;
  if (location.hostname === 'localhost' || location.hostname === '127.0.0.1' || location.protocol === 'file:') {
    return 'ws://127.0.0.1:8000/ws/viewer';
  }
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${location.host}/ws/viewer`;
}

function setConnection(state, label) {
  connection.className = `pill ${state}`;
  connectionText.textContent = label;
}

function formatNumber(value, decimals = 0) {
  if (!Number.isFinite(Number(value))) return '—';
  return Number(value).toLocaleString('es-AR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

function replaceMetric(element, text, unit = '') {
  element.innerHTML = `${text}${unit ? `<span class="unit">${unit}</span>` : ''}`;
  element.classList.remove('pulse');
  requestAnimationFrame(() => element.classList.add('pulse'));
}

function applyTelemetry(data) {
  telemetryReceived = true;
  pendingTelemetry = data;
  replaceMetric(metricElements.detections, formatNumber(data.detections));
  replaceMetric(metricElements.kg_ha, formatNumber(data.kg_ha, 1), 'kg/ha');
  replaceMetric(metricElements.fps, formatNumber(data.fps, 1), 'FPS');
  replaceMetric(metricElements.latency_ms, formatNumber(data.latency_ms), 'ms');
  document.querySelector('#camera-state').textContent = data.camera_connected === false ? 'OFFLINE' : 'ONLINE';
  document.querySelector('#model-state').textContent = data.model_ready === false ? 'ESPERA' : 'LISTO';
  document.querySelector('#telemetry-state').textContent = 'EN VIVO';
  if (Number.isFinite(Number(data.task_progress))) updateTaskProgress(Number(data.task_progress));
}

function showFrame(blob, metadata = pendingTelemetry) {
  if (currentFrameUrl) URL.revokeObjectURL(currentFrameUrl);
  currentFrameUrl = URL.createObjectURL(blob);
  frameImage.src = currentFrameUrl;
  frameImage.hidden = false;
  placeholder.classList.add('hidden');
  receivedFrames += 1;
  framesThisSecond += 1;
  const id = metadata?.frame_id ?? receivedFrames;
  frameLabel.textContent = `FRAME ${id}`;
  frameInfo.textContent = metadata?.width && metadata?.height ? `${metadata.width} × ${metadata.height}` : 'JPEG procesado';
  pendingTelemetry = undefined;
}

function handleJson(data) {
  if (data.type === 'telemetry' || data.type === 'frame_result') applyTelemetry(data);
  if (data.type === 'status' || data.type === 'system_status') {
    if (data.camera_connected !== undefined) document.querySelector('#camera-state').textContent = data.camera_connected ? 'ONLINE' : 'OFFLINE';
    if (data.model_ready !== undefined) document.querySelector('#model-state').textContent = data.model_ready ? 'LISTO' : 'ESPERA';
  }
}

function connect() {
  clearTimeout(reconnectTimer);
  setConnection('', 'Conectando');
  socket = new WebSocket(websocketUrl());
  socket.binaryType = 'blob';
  socket.addEventListener('open', () => {
    setConnection('connected', 'Datos en vivo');
    socket.send(JSON.stringify({ type: 'viewer_ready', accepts: ['image/jpeg', 'application/json'] }));
  });
  socket.addEventListener('message', event => {
    if (typeof event.data === 'string') {
      try { handleJson(JSON.parse(event.data)); } catch { /* Ignorar mensajes no JSON. */ }
      return;
    }
    showFrame(event.data);
  });
  socket.addEventListener('close', () => {
    setConnection('error', 'Reconectando');
    document.querySelector('#telemetry-state').textContent = 'ESPERA';
    reconnectTimer = setTimeout(connect, 1500);
  });
  socket.addEventListener('error', () => socket.close());
}

function notify(message) {
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 1400);
}

async function toggleFullscreen() {
  try {
    if (document.fullscreenElement) {
      await document.exitFullscreen();
    } else {
      await videoStage.requestFullscreen();
    }
  } catch {
    notify('El navegador no permitió usar pantalla completa');
  }
}

function updateFullscreenButton() {
  const active = document.fullscreenElement === videoStage;
  fullscreenButton.querySelector('[aria-hidden="true"]').textContent = active ? '✕' : '⛶';
  fullscreenButton.querySelector('.fullscreen-text').textContent = active ? 'Salir' : 'Pantalla completa';
  fullscreenButton.setAttribute('aria-label', active ? 'Salir de pantalla completa' : 'Ver cámara en pantalla completa');
}

fullscreenButton.addEventListener('click', toggleFullscreen);
videoStage.addEventListener('dblclick', toggleFullscreen);
document.addEventListener('fullscreenchange', updateFullscreenButton);

function updateTaskProgress(progress) {
  const bounded = Math.max(0, Math.min(100, progress));
  document.querySelector('#task-progress').style.width = `${bounded}%`;
  document.querySelector('#progress-label').textContent = `${Math.round(bounded)}% completado`;
}

const startButton = document.querySelector('#start-task');
const stopButton = document.querySelector('#stop-task');
startButton.addEventListener('click', () => {
  document.querySelector('#task-status').textContent = 'En curso';
  document.querySelector('#task-tag').textContent = 'ACTIVA';
  startButton.disabled = true;
  stopButton.disabled = false;
  updateTaskProgress(8);
  notify('Tarea iniciada');
});
stopButton.addEventListener('click', () => {
  document.querySelector('#task-status').textContent = 'Detenida';
  document.querySelector('#task-tag').textContent = 'PAUSADA';
  startButton.disabled = false;
  startButton.textContent = '▶ Reanudar tarea';
  stopButton.disabled = true;
  notify('Tarea detenida');
});
const scheduleDialog = document.querySelector('#schedule-dialog');
document.querySelector('#schedule-task').addEventListener('click', () => scheduleDialog.showModal());
document.querySelector('#confirm-schedule').addEventListener('click', () => notify('Tarea programada'));
document.querySelectorAll('[data-layer]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-layer]').forEach(item => item.classList.remove('active'));
  button.classList.add('active');
  const heat = document.querySelector('[data-map-content="heat"]');
  const route = document.querySelector('[data-map-content="route"]');
  heat.style.opacity = button.dataset.layer === 'heat' ? '1' : '0';
  route.style.opacity = button.dataset.layer === 'route' ? '1' : '0';
}));

window.addEventListener('pagehide', () => {
  clearTimeout(reconnectTimer);
  socket?.close();
  if (currentFrameUrl) URL.revokeObjectURL(currentFrameUrl);
});

connect();

window.setInterval(() => {
  if (!telemetryReceived) {
    replaceMetric(metricElements.fps, formatNumber(framesThisSecond, 1), 'FPS');
  }
  framesThisSecond = 0;
}, 1000);
