/**
 * GPT-Live, the opt-in second call mode (#34, ADR-0018).
 *
 * It has its own grant (`jup.voice.live`) and its own disclosure, acknowledged apart from the
 * governed call's. The governed call stays the default; this mode is offered only when granted.
 */

/** The server's `voice.LIVE_DISCLOSURE_VERSION`. Bump both whenever the text below changes. */
export const LIVE_DISCLOSURE_VERSION = '2026-10-03';

/** The GPT-Live disclosure, Indonesian first. Fixed text, not translated per locale: it is what was acknowledged. */
export const LIVE_DISCLOSURE = {
	id: [
		'Mode GPT-Live memakai model suara OpenAI untuk bercakap langsung dengan Anda. Seluruh sesi, termasuk suara Anda, diproses OpenAI di Amerika Serikat dan dapat disimpan hingga 30 hari untuk pemantauan penyalahgunaan.',
		'Yang Anda dengar adalah parafrase asisten atas jawaban dari basis pengetahuan JUP, kartu kontrak, dan Ruang Pimpinan, sesuai hak akses Anda. Kata-kata, angka, atau catatan kehati-hatiannya bisa berbeda dari jawaban tertulis.',
		'Asisten dapat menjawab sebagian pertanyaan sendiri, tanpa sumber tersebut. Jawaban itu ditandai dalam catatan audit, tetapi tidak diperiksa terhadap sumber.',
		'Pertanyaan yang diteruskan ke sumber tersebut juga melewati OpenRouter dan Xiaomi, penyedia model yang menyusun jawaban.',
		'Untuk jawaban yang dibacakan kata demi kata, pakai panggilan suara biasa.',
		'Apa pun yang Anda ucapkan tetap terkirim. Jangan sebutkan angka atau informasi yang belum publik.'
	],
	en: [
		"GPT-Live uses OpenAI's voice model to talk with you directly. The whole session, your voice included, is processed by OpenAI in the United States and may be kept for up to 30 days for abuse monitoring.",
		"What you hear is the assistant's paraphrase of the answer from the JUP knowledge base, contract cards and Ruang Pimpinan, within your access rights. Its wording, figures or caveats may differ from the written answer.",
		'The assistant may answer some questions itself, without those sources. Those answers are flagged in the audit log but not checked against a source.',
		'Questions passed to those sources also go through OpenRouter and Xiaomi, the providers of the model that writes the answer.',
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

export type CallMode = 'governed' | 'live';

export type ModeSteps = {
	/** Shows the mode choice; the chosen mode, or `null` when the caller backs out. */
	choose: () => Promise<CallMode | null>;
	/** Shows the GPT-Live disclosure; true when accepted. */
	discloseLive: () => Promise<boolean>;
	acknowledgeLive: (version: string) => Promise<void>;
};

/**
 * Which call to start (#37). Without the live grant nothing is asked: the governed call, as before.
 * Choosing GPT-Live needs its own disclosure acknowledged first; backing out of either starts nothing.
 */
export const chooseCallMode = async (
	capabilities: { enabled: boolean; live?: LiveCapabilities } | null | undefined,
	steps: ModeSteps
): Promise<CallMode | null> => {
	const live = liveMode(capabilities);
	if (live === 'hidden') return 'governed';
	const mode = await steps.choose();
	if (mode !== 'live') return mode;
	if (live === 'disclose') {
		if (!(await steps.discloseLive())) return null;
		await steps.acknowledgeLive(LIVE_DISCLOSURE_VERSION);
	}
	return 'live';
};

/** Sent on the data channel once the session starts: GPT-Live opens the call in Indonesian. */
export const LIVE_GREETING =
	'Sapa penelepon sekarang dalam bahasa Indonesia. Perkenalkan diri Anda sebagai Asisten JUP, lalu tanyakan apa yang bisa Anda bantu. Setelah itu berhenti dan dengarkan.';

export const greetingEvent = () => ({
	type: 'session.instructions.append',
	event_id: 'jup_greeting',
	delegation_id: null,
	content: LIVE_GREETING
});

export type Caption = { who: 'caller' | 'assistant'; text: string; start: number };

/**
 * Captions from the data channel's transcript deltas, for display only (the server keeps the record).
 * Consecutive fragments from the same speaker join one caption; the last `keep` captions are kept.
 */
export const addCaption = (captions: Caption[], event: unknown, keep = 6): Caption[] => {
	const e = event as { type?: string; delta?: unknown; start_ms?: unknown };
	const who: Caption['who'] | null =
		e?.type === 'session.input_transcript.delta'
			? 'caller'
			: e?.type === 'session.output_transcript.delta'
				? 'assistant'
				: null;
	if (!who || typeof e.delta !== 'string' || !e.delta) return captions;
	const last = captions[captions.length - 1];
	const next =
		last && last.who === who
			? [...captions.slice(0, -1), { ...last, text: last.text + e.delta }]
			: [...captions, { who, text: e.delta, start: Number(e.start_ms) || 0 }];
	return next.slice(-keep);
};
