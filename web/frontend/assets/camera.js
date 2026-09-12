const TARGET_FPS = 8;
const FRAME_INTERVAL_MS = 1000 / TARGET_FPS;
const JPEG_QUALITY = 0.72;
const MAX_WIDTH = 960;
const MAX_BUFFERED_BYTES = 2 * 1024 * 1024;
const SEND_FRAME_METADATA = new URLSearchParams(location.search).get('metadata') === '1';

const video = document.querySelector('#camera-preview');
const canvas = document.querySelector('#capture-canvas');
const toggleButton = document.querySelector('#toggle-camera');
const connection = document.querySelector('#camera-connection');
const connectionText = connection.querySelector('span:last-child');
const badge = document.querySelector('#capture-badge');
const fpsElement = document.querySelector('#sent-fps');
const countElement = document.querySelector('#sent-count');
const queueElement = document.querySelector('#queue-state');
const context = canvas.getContext('2d', { alpha: false });

let stream;
let socket;
let captureTimer;
let running = false;
let frameId = 0;
let sentThisSecond = 0;
let fpsStartedAt = performance.now();
let captureInFlight = false;

function websocketUrl() {
  const explicit = new URLSearchParams(location.search).get('ws');
  if (explicit) return explicit;
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${location.host}/ws/camera`;
}

function setConnection(state, label) {
  connection.className = `pill ${state}`;
  connectionText.textContent = label;
}

function configureCanvas() {
  const sourceWidth = video.videoWidth;
  const sourceHeight = video.videoHeight;
  const scale = Math.min(1, MAX_WIDTH / sourceWidth);
  canvas.width = Math.round(sourceWidth * scale);
  canvas.height = Math.round(sourceHeight * scale);
}

function canvasBlob() {
  return new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', JPEG_QUALITY));
}

function updateFps() {
  const now = performance.now();
  const elapsed = now - fpsStartedAt;
  if (elapsed < 1000) return;
  fpsElement.textContent = (sentThisSecond * 1000 / elapsed).toFixed(1).replace('.', ',');
  sentThisSecond = 0;
  fpsStartedAt = now;
}

async function captureFrame() {
  if (!running || captureInFlight || socket?.readyState !== WebSocket.OPEN) return;

  if (socket.bufferedAmount > MAX_BUFFERED_BYTES) {
    queueElement.textContent = 'Descartando frame';
    return;
  }

  captureInFlight = true;
  try {
    if (!canvas.width) configureCanvas();
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const jpeg = await canvasBlob();
    if (!jpeg || !running || socket?.readyState !== WebSocket.OPEN) return;

    frameId += 1;
  if (SEND_FRAME_METADATA) {
    socket.send(JSON.stringify({
      type: 'frame_meta',
      frame_id: frameId,
      captured_at: Date.now(),
      width: canvas.width,
      height: canvas.height,
    }));
  }
    socket.send(jpeg);
    sentThisSecond += 1;
    countElement.textContent = String(frameId);
    queueElement.textContent = socket.bufferedAmount ? 'Enviando' : 'Cola libre';
    updateFps();
  } finally {
    captureInFlight = false;
  }
}

function connectSocket() {
  return new Promise((resolve, reject) => {
    socket = new WebSocket(websocketUrl());
    socket.addEventListener('open', () => {
      socket.send(JSON.stringify({ type: 'camera_config', target_fps: TARGET_FPS, jpeg_quality: JPEG_QUALITY }));
      setConnection('connected', 'Transmitiendo');
      resolve();
    }, { once: true });
    socket.addEventListener('error', () => reject(new Error('No se pudo conectar con el backend')), { once: true });
    socket.addEventListener('close', () => {
      if (running) stopCapture('Conexión perdida');
    });
  });
}

async function startCapture() {
  toggleButton.disabled = true;
  setConnection('', 'Solicitando cámara');
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    video.srcObject = stream;
    await video.play();
    configureCanvas();
    setConnection('', 'Conectando');
    await connectSocket();
    running = true;
    frameId = 0;
    fpsStartedAt = performance.now();
    badge.textContent = 'ENVIANDO AL MODELO';
    toggleButton.textContent = 'Detener transmisión';
    toggleButton.classList.remove('primary');
    toggleButton.classList.add('danger');
    captureTimer = setInterval(captureFrame, FRAME_INTERVAL_MS);
  } catch (error) {
    stopCapture(error.message || 'No se pudo iniciar');
    setConnection('error', 'Error');
  } finally {
    toggleButton.disabled = false;
  }
}

function stopCapture(reason = 'Sin iniciar') {
  running = false;
  clearInterval(captureTimer);
  captureTimer = undefined;
  if (socket && socket.readyState < WebSocket.CLOSING) socket.close(1000, 'camera stopped');
  socket = undefined;
  stream?.getTracks().forEach(track => track.stop());
  stream = undefined;
  video.srcObject = null;
  badge.textContent = 'CÁMARA APAGADA';
  toggleButton.textContent = 'Iniciar transmisión';
  toggleButton.classList.add('primary');
  toggleButton.classList.remove('danger');
  setConnection('', reason);
  queueElement.textContent = 'Cola libre';
}

toggleButton.addEventListener('click', () => running ? stopCapture() : startCapture());
window.addEventListener('pagehide', () => stopCapture());

if (!navigator.mediaDevices?.getUserMedia) {
  toggleButton.disabled = true;
  setConnection('error', 'Cámara no disponible');
}
