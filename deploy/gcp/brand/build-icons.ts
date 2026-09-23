/**
 * Build every Asisten JUP icon and mark from the official logogram PNGs.
 *
 * Source: the "Logo Asisten JUP" logo system (2026-09-23), whose rule is that the logogram is used
 * from the official file and never redrawn, recoloured or reproportioned. So this only trims,
 * scales and places the two supplied rasters: the full-colour logogram for light surfaces and the
 * white one for dark. App icons follow the system's panel 1c: the white logogram on Rich Black,
 * at 60/112 of the tile.
 *
 * Usage: bun deploy/gcp/brand/build-icons.ts
 * Writes into static/static and backend/open_webui/static, which must stay identical.
 */
import sharp from "sharp";
import { join } from "node:path";

const HERE = import.meta.dir;
const ROOT = join(HERE, "..", "..", "..");
const OUT = [join(ROOT, "static", "static"), join(ROOT, "backend", "open_webui", "static")];
const COLOR = join(HERE, "logogram-color.png");
const WHITE = join(HERE, "logogram-white.png");
const RICH_BLACK = { r: 1, g: 22, b: 39, alpha: 1 };
const CLEAR = { r: 0, g: 0, b: 0, alpha: 0 };

async function mark(src: string, box: number): Promise<Buffer> {
  const trimmed = await sharp(src).trim().toBuffer();
  return sharp(trimmed).resize(box, box, { fit: "contain", background: CLEAR }).png().toBuffer();
}

/** The logogram centred on a square canvas, occupying `share` of its side. */
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

const favicon128 = await placed(COLOR, 128, 0.9);
const files: Record<string, Buffer | string> = {
  "asisten-jup-mark.png": await mark(COLOR, 128),
  "asisten-jup-mark-white.png": await mark(WHITE, 128),
  "favicon.png": await placed(COLOR, 512, 0.9),
  "favicon-96x96.png": await placed(COLOR, 96, 0.9),
  "favicon.ico": ico(await placed(COLOR, 32, 0.94), 32),
  "favicon.svg":
    '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 128 128" width="128" height="128">' +
    `<image width="128" height="128" xlink:href="data:image/png;base64,${favicon128.toString("base64")}"/></svg>\n`,
  "logo.png": await placed(COLOR, 500, 0.8),
  "splash.png": await placed(COLOR, 500, 0.7),
  "splash-dark.png": await placed(WHITE, 500, 0.7),
  "apple-touch-icon.png": await placed(WHITE, 180, 60 / 112, RICH_BLACK),
  "web-app-manifest-192x192.png": await placed(WHITE, 192, 60 / 112, RICH_BLACK),
  "web-app-manifest-512x512.png": await placed(WHITE, 512, 60 / 112, RICH_BLACK),
};

for (const dir of OUT) {
  for (const [name, body] of Object.entries(files)) await Bun.write(join(dir, name), body);
}
console.log(`wrote ${Object.keys(files).length} files into ${OUT.length} directories`);
