/**
 * Which voice reads a typed answer aloud (#28, ADR-0017).
 *
 * With OpenAI as the TTS engine, `/api/v1/audio/speech` reads only a stored answer in the
 * caller's own voice call, by message id, and refuses free text. So read-aloud on any other
 * answer uses the browser's own voice, and a typed answer from the whole KB never reaches
 * OpenAI. An empty engine was always the browser's voice.
 */
export const readAloudUsesBrowser = (engine: string | null | undefined): boolean =>
	!engine || engine === 'openai';
