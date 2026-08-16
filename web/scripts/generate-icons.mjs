/* Generates the PWA PNG icons from an inline design using only Node built-ins. */
import { deflateSync } from "node:zlib";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const outDir = join(__dirname, "..", "public", "icons");
mkdirSync(outDir, { recursive: true });

function crc32(buf) {
  let table = crc32.table;
  if (!table) {
    table = crc32.table = new Int32Array(256);
    for (let n = 0; n < 256; n++) {
      let c = n;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      table[n] = c;
    }
  }
  let c = -1;
  for (let i = 0; i < buf.length; i++) c = table[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const typeBuf = Buffer.from(type, "ascii");
  const body = Buffer.concat([typeBuf, data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}

function encodePNG(width, height, rgba) {
  const raw = Buffer.alloc((width * 4 + 1) * height);
  for (let y = 0; y < height; y++) {
    raw[y * (width * 4 + 1)] = 0; // filter: none
    rgba.copy(raw, y * (width * 4 + 1) + 1, y * width * 4, (y + 1) * width * 4);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // RGBA
  ihdr[10] = 0;
  ihdr[11] = 0;
  ihdr[12] = 0;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

function hex(c) {
  return [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)];
}

const lerp = (a, b, t) => a + (b - a) * t;
const mix = (c1, c2, t) => [
  Math.round(lerp(c1[0], c2[0], t)),
  Math.round(lerp(c1[1], c2[1], t)),
  Math.round(lerp(c1[2], c2[2], t)),
];

function drawIcon(size, radius) {
  const bg = hex("#0f172a");
  const ring = hex("#4ade80");
  const leaf = hex("#fb923c");
  const wave = hex("#38bdf8");
  const text = hex("#e2e8f0");
  const px = Buffer.alloc(size * size * 4);

  const cx = size / 2;
  const ringR = size * 0.30;
  const ringW = size * 0.036;
  const leafStart = { x: size * 0.34, y: size * 0.60 };
  const leafMid = { x: size * 0.56, y: size * 0.46 };
  const leafEnd = { x: size * 0.56, y: size * 0.59 };

  const inRoundedRect = (x, y) => {
    const r = radius;
    const dx = Math.max(Math.abs(x - cx) - (cx - r), 0);
    const dy = Math.max(Math.abs(y - cx) - (cx - r), 0);
    return dx * dx + dy * dy <= r * r;
  };

  const pointOnQuad = (p0, p1, p2, t) => {
    const x = (1 - t) * (1 - t) * p0.x + 2 * (1 - t) * t * p1.x + t * t * p2.x;
    const y = (1 - t) * (1 - t) * p0.y + 2 * (1 - t) * t * p1.y + t * t * p2.y;
    return { x, y };
  };
  const distToSeg = (x, y, a, b) => {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len2 = dx * dx + dy * dy;
    let t = len2 ? ((x - a.x) * dx + (y - a.y) * dy) / len2 : 0;
    t = Math.max(0, Math.min(1, t));
    const px = a.x + t * dx - x;
    const py = a.y + t * dy - y;
    return Math.sqrt(px * px + py * py);
  };

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      let color = mix(bg, hex("#1e293b"), 0.35);
      if (!inRoundedRect(x + 0.5, y + 0.5)) {
        px[i + 3] = 0;
        continue;
      }

      const dx = x + 0.5 - cx;
      const dy = y + 0.5 - cx;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (Math.abs(dist - ringR) <= ringW) {
        color = mix(ring, hex("#22c55e"), Math.sin((x + y) * 0.3) * 0.3 + 0.5);
      }

      const arcT = Math.atan2(dy, dx) / Math.PI;
      const leafDist = Math.min(
        distToSeg(x + 0.5, y + 0.5, leafStart, leafMid),
        distToSeg(x + 0.5, y + 0.5, leafMid, leafEnd),
        distToSeg(x + 0.5, y + 0.5, leafStart, leafEnd)
      );
      if (leafDist < size * 0.02) color = mix(leaf, hex("#ea580c"), 0.3);

      const waveA = { x: size * 0.40, y: size * 0.68 };
      const waveB = { x: size * 0.60, y: size * 0.65 };
      const waveC = { x: size * 0.54, y: size * 0.63 };
      const waveDist = Math.min(distToSeg(x + 0.5, y + 0.5, waveA, waveB), distToSeg(x + 0.5, y + 0.5, waveB, waveC));
      if (waveDist < size * 0.016) color = mix(wave, hex("#0ea5e9"), 0.3);

      px[i] = color[0];
      px[i + 1] = color[1];
      px[i + 2] = color[2];
      px[i + 3] = 255;
    }
  }
  return px;
}

const sizes = [
  { size: 192, file: "icon-192.png", radius: 36 },
  { size: 512, file: "icon-512.png", radius: 96 },
  { size: 512, file: "icon-maskable-512.png", radius: 256 }, // full-bleed for maskable
];

for (const { size, file, radius } of sizes) {
  const rgba = drawIcon(size, radius);
  const png = encodePNG(size, size, rgba);
  const dest = join(outDir, file);
  writeFileSync(dest, png);
  console.log(`generated ${dest} (${png.length} bytes)`);
}
