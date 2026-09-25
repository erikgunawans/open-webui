/**
 * Build every None-JUPe icon and mark from the logo system's vector sources.
 *
 * Source: "Logo None-JUPe" (2026-09-26), option 2a, "Kembang dalam gelembung percakapan": the
 * kembang goyang flower inside a speech-bubble outline. The three SVGs here are copied verbatim
 * from that design, not redrawn:
 *   none-jupe-mark.svg        full colour, with the Rich Black centre point, for light surfaces
 *   none-jupe-mark-small.svg  the same without the centre point, as the design's 24 px test uses;
 *                             the app shows its mark at 20-32 px, so every in-app mark uses it
 *   none-jupe-mark-white.svg  the single-colour reversal for dark surfaces
 * App icons follow the design's tile: the mark on white at 56/88 of the side.
 *
 * Usage: bun deploy/gcp/brand/build-icons.ts
 * Writes into static/static and backend/open_webui/static, which must stay identical.
 */
import sharp from "sharp";
import { join } from "node:path";

const HERE = import.meta.dir;
const ROOT = join(HERE, "..", "..", "..");
const OUT = [join(ROOT, "static", "static"), join(ROOT, "backend", "open_webui", "static")];
const FULL = join(HERE, "none-jupe-mark.svg");
const SMALL = join(HERE, "none-jupe-mark-small.svg");
const WHITE = join(HERE, "none-jupe-mark-white.svg");
const WHITE_TILE = { r: 255, g: 255, b: 255, alpha: 1 };
const CLEAR = { r: 0, g: 0, b: 0, alpha: 0 };

/** The mark rasterised at `box` pixels square, from the vector so every size is sharp. */
async function mark(src: string, box: number): Promise<Buffer> {
  return sharp(src, { density: Math.max(72, Math.ceil((72 * box) / 100) * 2) })
    .resize(box, box, { fit: "contain", background: CLEAR })
    .png()
    .toBuffer();
}

/** The mark centred on a square canvas, occupying `share` of its side. */
async function placed(src: string, size: number, share: number, background = CLEAR): Promise<Buffer> {
  const inner = Math.round(size * share);
  const pad = Math.floor((size - inner) / 2);
  return sharp({ create: { width: size, height: size, channels: 4, background } })
    .composite([{ input: await mark(src, inner), top: pad, left: pad }])
    .png()
    .toBuffer();
}

/** A single-image ICO holding a PNG, which every current browser reads. */
function ico(png: Buffer, size: number): Buffer {
  const head = Buffer.alloc(22);
  head.writeUInt16LE(0, 0);
  head.writeUInt16LE(1, 2);
  head.writeUInt16LE(1, 4);
  head.writeUInt8(size >= 256 ? 0 : size, 6);
  head.writeUInt8(size >= 256 ? 0 : size, 7);
  head.writeUInt16LE(1, 10);
  head.writeUInt16LE(32, 12);
  head.writeUInt32LE(png.length, 14);
  head.writeUInt32LE(22, 18);
  return Buffer.concat([head, png]);
}

const TILE = 56 / 88;
const files: Record<string, Buffer | string> = {
  "none-jupe-mark.png": await mark(SMALL, 128),
  "none-jupe-mark-white.png": await mark(WHITE, 128),
  "favicon.png": await placed(SMALL, 512, 0.9),
  "favicon-96x96.png": await placed(SMALL, 96, 0.9),
  "favicon.ico": ico(await placed(SMALL, 32, 0.94), 32),
  "favicon.svg": (await Bun.file(SMALL).text()).trim() + "\n",
  "logo.png": await placed(FULL, 500, 0.8),
  "splash.png": await placed(FULL, 500, 0.7),
  "splash-dark.png": await placed(WHITE, 500, 0.7),
  "apple-touch-icon.png": await placed(SMALL, 180, TILE, WHITE_TILE),
  "web-app-manifest-192x192.png": await placed(SMALL, 192, TILE, WHITE_TILE),
  "web-app-manifest-512x512.png": await placed(SMALL, 512, TILE, WHITE_TILE),
};

for (const dir of OUT) {
  for (const [name, body] of Object.entries(files)) await Bun.write(join(dir, name), body);
}
console.log(`wrote ${Object.keys(files).length} files into ${OUT.length} directories`);
