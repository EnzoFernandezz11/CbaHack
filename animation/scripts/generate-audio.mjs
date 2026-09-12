import fs from 'node:fs';
import path from 'node:path';

const rate = 48000;
const seconds = 15;
const total = rate * seconds;
const outDir = path.resolve('public/audio');
fs.mkdirSync(outDir, {recursive: true});

function writeWav(name, sample) {
  const data = Buffer.alloc(total * 2);
  for (let i = 0; i < total; i++) data.writeInt16LE(Math.max(-1, Math.min(1, sample(i / rate, i))) * 32767, i * 2);
  const header = Buffer.alloc(44);
  header.write('RIFF', 0); header.writeUInt32LE(36 + data.length, 4); header.write('WAVE', 8); header.write('fmt ', 12);
  header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20); header.writeUInt16LE(1, 22); header.writeUInt32LE(rate, 24); header.writeUInt32LE(rate * 2, 28); header.writeUInt16LE(2, 32); header.writeUInt16LE(16, 34); header.write('data', 36); header.writeUInt32LE(data.length, 40);
  fs.writeFileSync(path.join(outDir, name), Buffer.concat([header, data]));
}
const noise = (i) => Math.sin(i * 12.9898) * 0.5 + Math.sin(i * 78.233) * 0.25;
writeWav('wind.wav', (t, i) => (noise(i) * 0.055 + Math.sin(t * 0.42) * 0.025));
writeWav('engine.wav', (t) => Math.sin(t * 2 * Math.PI * 62) * 0.18 + Math.sin(t * 2 * Math.PI * 124) * 0.07 + noise(Math.floor(t * rate)) * 0.025);
writeWav('machinery.wav', (t) => Math.sin(t * 2 * Math.PI * 9) * 0.12 + Math.sin(t * 2 * Math.PI * 440) * 0.025 * (0.5 + 0.5 * Math.sin(t * 2 * Math.PI * 1.3)));
writeWav('transition.wav', (t) => Math.sin(2 * Math.PI * (180 + t * 900) * t) * Math.min(1, t / 1.2) * Math.max(0, 1 - t / 2));
