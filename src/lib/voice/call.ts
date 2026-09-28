import type { LiveCapabilities } from './live';

/**
 * The voice call a director starts (#29, ADR-0017).
 *
 * A call is a new voice chat made by `POST /api/v1/voice/calls`, and only after the disclosure
 * below was acknowledged. With OpenAI or Google as the TTS engine the server reads only the answer
 * it stored and sealed, by `{chat_id, message_id, part}`; the streamed sentences are never sent.
 */

/** The server's `voice.DISCLOSURE_VERSION`. Bump both whenever the text below changes. */
export const DISCLOSURE_VERSION = '2026-09-28';

/** The disclosure, Indonesian first. Fixed text, not translated per locale: it is what was acknowledged. */
export const DISCLOSURE = {
	id: [
		'Panggilan suara memakai OpenAI untuk mengubah suara Anda menjadi teks. OpenAI memproses suara di Amerika Serikat dan dapat menyimpannya hingga 30 hari.',
		'Jawaban dibacakan dengan Google Text-to-Speech. Google menyatakan tidak mencatat teks maupun audio jawaban tersebut.',
		'Kata-kata Anda juga melewati OpenRouter dan Xiaomi, penyedia model yang menyusun jawaban.',
		'Asisten suara hanya menjawab dari dokumen strategi yang ditetapkan.',
		'Apa pun yang Anda ucapkan tetap terkirim. Jangan sebutkan angka atau informasi yang belum publik.'
	],
	en: [
		'Voice calls use OpenAI to turn your speech into text. OpenAI processes speech in the United States and may keep it for up to 30 days.',
		'Answers are read aloud with Google Text-to-Speech. Google states that it does not log that text or audio.',
		'Your words also pass through OpenRouter and Xiaomi, the providers of the model that writes the answer.',
		'Voice answers only from the named strategy documents.',
		'Whatever you say is sent regardless. Do not speak figures or information that are not public.'
	]
} as const;

export type VoiceCapabilities = {
	enabled: boolean;
	granted: boolean;
	acknowledged: boolean;
	disclosure_version: string;
	/** GPT-Live's own grant and acknowledgement (#34); absent from a server older than it. */
	live?: LiveCapabilities;
};

export type CallButton = 'hidden' | 'disclose' | 'call';

export type StartedCall = { chat_id: string; model: string };

/** What the call button does: nothing without the switch and the grant, else disclose or call. */
export const callButton = (capabilities: VoiceCapabilities | null | undefined): CallButton => {
	if (!capabilities?.enabled || !capabilities.granted) return 'hidden';
	return capabilities.acknowledged ? 'call' : 'disclose';
};

export type CallSteps = {
	capabilities: () => Promise<VoiceCapabilities | null>;
	/** Shows the disclosure; true when the user accepts it. */
	disclose: () => Promise<boolean>;
	acknowledge: (version: string) => Promise<void>;
	startCall: () => Promise<StartedCall>;
};

/** Disclosure if needed, acknowledgement, then the start-call route. `null` when nothing started. */
export const beginCall = async (steps: CallSteps): Promise<StartedCall | null> => {
	const button = callButton(await steps.capabilities());
	if (button === 'hidden') return null;
	if (button === 'disclose') {
		if (!(await steps.disclose())) return null;
		await steps.acknowledge(DISCLOSURE_VERSION);
	}
	return steps.startCall();
};

/**
 * The visible first line of every new call. The voice model's instructions
 * (`deploy/gcp/sync-voice-model.ts`) answer exactly this line with a greeting by name and a Betawi
 * pantun, so the call opens with her voice. Change both together.
 */
export const CALL_OPENING = 'Halo, saya memulai panggilan.';

/** Only the call the start-call route just made opens with the greeting, never a reopened one. */
export const opensWithGreeting = (
	justStarted: string | null | undefined,
	chatId: string | null | undefined
): boolean => !!chatId && justStarted === chatId;

/** Whether the call reads the sealed answer by message id rather than the streamed sentences. */
export const speaksSealedAnswers = (engine: string | null | undefined): boolean =>
	engine === 'openai' || engine === 'google';

/** The seal is written when the turn finishes on the server, which can trail the browser's finish. */
const NOT_SEALED_YET = new Set(['voice_tts_not_ready', 'voice_tts_unsealed']);

/** The answer's part count, retried while the server has not sealed it yet. */
export const sealedAnswerParts = async (
	parts: () => Promise<number>,
	{
		tries = 10,
		wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)),
		delayMs = 500
	}: { tries?: number; wait?: (ms: number) => Promise<void>; delayMs?: number } = {}
): Promise<number> => {
	for (let attempt = 1; ; attempt++) {
		try {
			return await parts();
		} catch (error) {
			const code = (error as { code?: string } | null)?.code;
			if (attempt >= tries || !code || !NOT_SEALED_YET.has(code)) throw error;
			await wait(delayMs);
		}
	}
};
