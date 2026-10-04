/**
 * ent-os answers in Markdown, which Teams and the web render. WhatsApp has its own, smaller syntax
 * (`*bold*`, `_italic_`, `~strike~`, `` `code` ``, ``` ```block``` ```), and shows Markdown's
 * `##`, `**` and `[label](url)` literally (seen live 2026-10-05). This turns one into the other,
 * leaving code untouched: what is inside backticks is shown as written.
 */

const BOLD = '\u0001';

/** Rewrites one run of text that holds no code. */
function inline(text: string): string {
	return (
		text
			// [label](url) → label (url); a bare link stays as it is.
			.replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, label, url) =>
				label === url ? url : `${label} (${url})`
			)
			// Markdown bold, kept aside so the italic rule below cannot touch it.
			.replace(/\*\*(?=\S)([^\n]*?\S)\*\*/g, `${BOLD}$1${BOLD}`)
			.replace(/__(?=\S)([^\n]*?\S)__/g, `${BOLD}$1${BOLD}`)
			// Markdown italic `*x*` would read as bold on WhatsApp.
			.replace(/(^|[^\w*])\*(?=\S)([^*\n]*?\S)\*(?![\w*])/g, '$1_$2_')
			.replace(/~~(?=\S)([^\n]*?\S)~~/g, '~$1~')
			.replaceAll(BOLD, '*')
	);
}

/** Rewrites one line outside a code block; null drops it. */
function line(text: string): string | null {
	if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(text)) return ''; // a rule: ---, ***, ___
	if (/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/.test(text)) return null; // table separator

	const heading = text.match(/^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/);
	if (heading) {
		const title = heading[1].replace(/\*\*|__/g, '');
		return title ? `*${title}*` : '';
	}

	const bullet = text.match(/^(\s*)[-*+]\s+(.*)$/);
	const body = bullet ? `${bullet[1]}• ${bullet[2]}` : text;

	// Inline code stays as written; everything around it is rewritten.
	return body
		.split(/(`[^`\n]+`)/)
		.map((part, i) => (i % 2 ? part : inline(part)))
		.join('');
}

export function toWhatsApp(markdown: string): string {
	let inFence = false;
	const out: string[] = [];
	for (const raw of markdown.split('\n')) {
		if (/^\s*```/.test(raw)) {
			inFence = !inFence;
			out.push('```');
			continue;
		}
		const rewritten = inFence ? raw : line(raw);
		if (rewritten !== null) out.push(rewritten);
	}
	return out
		.join('\n')
		.replace(/\n{3,}/g, '\n\n')
		.trim();
}
