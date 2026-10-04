/**
 * Product copy decided by Erik (spec #84). Changing a line here is a product change. The texts
 * ent-os owns (the 120 s "masih diproses", the cut, the attachment notice) come back in its reply.
 */

/** Every refusal gets this: unmapped, pending, no grant, kill switch off. The reason is logged only. */
export const NOT_CONNECTED = 'Akun ini belum terhubung ke Asisten JUP. Hubungi admin JUP.';

/** ent-os down, erroring or too slow. Logged, never retried. */
export const UNAVAILABLE = 'Asisten JUP sedang tidak tersedia, coba lagi sebentar lagi.';

/** WhatsApp, after `hubungkan <code>` linked the number (spec #101). */
export const LINKED = 'Nomor ini sudah terhubung ke Asisten JUP.';

/** WhatsApp, after a code ent-os refused: unknown, used, expired or too many tries. */
export const CODE_INVALID = 'Kode tidak berlaku. Buat kode baru di Pengaturan → Akun.';
