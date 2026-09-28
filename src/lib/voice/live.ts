/**
 * GPT-Live, the opt-in second call mode (#34, ADR-0018).
 *
 * It has its own grant (`jup.voice.live`) and its own disclosure, acknowledged apart from the
 * governed call's. The governed call stays the default; this mode is offered only when granted.
 */

/** The server's `voice.LIVE_DISCLOSURE_VERSION`. Bump both whenever the text below changes. */
export const LIVE_DISCLOSURE_VERSION = '2026-09-28';

/** The GPT-Live disclosure, Indonesian first. Fixed text, not translated per locale: it is what was acknowledged. */
export const LIVE_DISCLOSURE = {
	id: [
		'Mode GPT-Live memakai model suara OpenAI untuk bercakap langsung dengan Anda. Seluruh sesi, termasuk suara Anda, diproses OpenAI di Amerika Serikat dan dapat disimpan hingga 30 hari untuk pemantauan penyalahgunaan.',
		'Yang Anda dengar adalah parafrase asisten atas jawaban dari dokumen strategi. Kata-kata, angka, atau catatan kehati-hatiannya bisa berbeda dari jawaban tertulis.',
		'Asisten dapat menjawab sebagian pertanyaan sendiri, di luar dokumen strategi. Jawaban itu ditandai dalam catatan audit, tetapi tidak diperiksa terhadap dokumen.',
		'Pertanyaan yang diteruskan ke dokumen juga melewati OpenRouter dan Xiaomi, penyedia model yang menyusun jawaban.',
		'Untuk jawaban yang dibacakan kata demi kata, pakai panggilan suara biasa.',
		'Apa pun yang Anda ucapkan tetap terkirim. Jangan sebutkan angka atau informasi yang belum publik.'
	],
	en: [
		"GPT-Live uses OpenAI's voice model to talk with you directly. The whole session, your voice included, is processed by OpenAI in the United States and may be kept for up to 30 days for abuse monitoring.",
		"What you hear is the assistant's paraphrase of the answer from the strategy documents. Its wording, figures or caveats may differ from the written answer.",
		'The assistant may answer some questions itself, outside the strategy documents. Those answers are flagged in the audit log but not checked against the documents.',
		'Questions passed to the documents also go through OpenRouter and Xiaomi, the providers of the model that writes the answer.',
		'For answers read word for word, use the standard voice call.',
		'Whatever you say is sent regardless. Do not speak figures or information that are not public.'
	]
} as const;

export type LiveCapabilities = {
	granted: boolean;
	acknowledged: boolean;
	disclosure_version: string;
};

export type LiveMode = 'hidden' | 'disclose' | 'ready';

/** Whether the call UI offers GPT-Live: not without the switch and both grants, else disclose or ready. */
export const liveMode = (
	capabilities: { enabled: boolean; live?: LiveCapabilities } | null | undefined
): LiveMode => {
	const live = capabilities?.live;
	if (!capabilities?.enabled || !live?.granted) return 'hidden';
	return live.acknowledged && live.disclosure_version === LIVE_DISCLOSURE_VERSION
		? 'ready'
		: 'disclose';
};

export type LiveStreamEvent =
	| { type: 'session'; session_id: string; sdp: string }
	| { type: 'ping' }
	| { type: 'ended' };

/** The server's call-long stream (#36) as events, one JSON object per line, split across any chunks. */
export async function* ndjsonEvents(
	chunks: AsyncIterable<string>
): AsyncGenerator<LiveStreamEvent> {
	let buffer = '';
	for await (const chunk of chunks) {
		buffer += chunk;
		let newline = buffer.indexOf('\n');
		while (newline >= 0) {
			const line = buffer.slice(0, newline).trim();
			buffer = buffer.slice(newline + 1);
			if (line) yield JSON.parse(line) as LiveStreamEvent;
			newline = buffer.indexOf('\n');
		}
	}
	if (buffer.trim()) yield JSON.parse(buffer) as LiveStreamEvent;
}
