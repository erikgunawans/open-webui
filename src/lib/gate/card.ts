/**
 * What the approval card shows for a gated External Call (ADR-0013 §3, A5 + E5 ticket 4/7).
 *
 * The user is approving their own call and needs to see the real thing, so the arguments are shown
 * in full; only secret-looking values are masked, so approving a call never puts a token, key or
 * password on screen. A value is masked when its key names a secret (`token`, `api_key`,
 * `Authorization`…), and inside any text, a credential shape (`Bearer …`, `sk-…`, a JWT…) or a
 * `secret_key=value` pair (`password=…` in a message, `?api_key=…` in a URL) is masked too. Words
 * that are ordinary alone (`key`, `auth`, `session`, `pin`) are left visible, so the user still
 * sees what they approve. This is display only: the call runs with the arguments the model
 * produced, unmasked.
 */

export const MASK = '••••••';

// Words that name a secret wherever they appear in a key (`client_secret`, `refreshToken`).
const SECRET_WORDS = new Set([
	'token',
	'password',
	'passwd',
	'pwd',
	'passphrase',
	'secret',
	'apikey',
	'authorization',
	'cookie',
	'credential',
	'credentials',
	'otp',
	'bearer'
]);

// Words that are ordinary alone (`key`, `sort_key`, `auth`, `session`) but secret in a pair.
const SECRET_PAIRS: Array<[Set<string>, Set<string>]> = [
	[
		new Set(['api', 'private', 'access', 'secret', 'signing', 'encryption', 'client']),
		new Set(['key'])
	],
	[new Set(['auth', 'session']), new Set(['token', 'key', 'id', 'cookie'])]
];

// Credential shapes, whatever key they sit under or whatever text they sit in.
const SECRET_SHAPES = [
	/Bearer\s+(?=[^\s'",;&]*[\d._~+/=-])[^\s'",;&]{6,}/gi, // a token, not the word "of"
	/\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}/g,
	/\bgh[pousr]_[A-Za-z0-9]{20,}/g,
	/\bAKIA[0-9A-Z]{16}\b/g,
	/\beyJ[\w-]+\.[\w-]+\.[\w-]+/g,
	/\bxox[abprs]-[A-Za-z0-9-]{8,}/g,
	/\bAIza[0-9A-Za-z_-]{30,}/g
];

// `password=hunter2`, `api_key=abc` in a URL, `token: 'x'`: a key, a separator, an optional quote.
// `(?!\/\/)` skips a URL scheme, so `https://x/?api_key=abc` reaches the `api_key` pair.
const INLINE_PAIR = /([A-Za-z][\w-]*)(['"]?\s*[=:]\s*)(?!\/\/)(['"]?)([^\s&'",;]+)/g;

/** The words of a key: `refreshToken`, `API-KEY` and `client_secret` split alike. */
function words(key: string): string[] {
	return key
		.replace(/([a-z0-9])([A-Z])/g, '$1 $2')
		.toLowerCase()
		.split(/[^a-z0-9]+/)
		.filter(Boolean);
}

export function isSecretKey(key: string): boolean {
	const parts = words(key);
	if (parts.some((part) => SECRET_WORDS.has(part)) || SECRET_WORDS.has(parts.join(''))) return true;
	return parts.some((part, i) =>
		SECRET_PAIRS.some(([first, second]) => first.has(part) && second.has(parts[i + 1] ?? ''))
	);
}

/** `value` with every credential shape and every `secret_key=value` inside it masked. */
export function maskedText(value: string): string {
	let shown = value;
	for (const shape of SECRET_SHAPES) shown = shown.replace(shape, MASK);
	return shown.replace(INLINE_PAIR, (whole, key, separator, quote) =>
		isSecretKey(key) ? `${key}${separator}${quote}${MASK}` : whole
	);
}

/** A copy of `value` with every secret-looking value replaced by `MASK`. */
export function maskSecrets(value: unknown): unknown {
	if (typeof value === 'string') return maskedText(value);
	if (Array.isArray(value)) return value.map(maskSecrets);
	if (value !== null && typeof value === 'object') {
		return Object.fromEntries(
			Object.entries(value).map(([key, inner]) => [
				key,
				isSecretKey(key) ? MASK : maskSecrets(inner)
			])
		);
	}
	return value;
}

/** The card's text for a call's raw `arguments`: JSON unwrapped, masked and pretty-printed. */
export function maskedArguments(raw: string): string {
	let value: unknown = raw;
	while (typeof value === 'string') {
		try {
			value = JSON.parse(value);
		} catch {
			break;
		}
	}
	if (typeof value === 'string') return maskedText(value);
	return JSON.stringify(maskSecrets(value), null, 2);
}

/**
 * The Risk Class of a call the server armed for approval (`jup_gate`, `backend/jup/approval.py`),
 * or '' for a call nobody gated. Only `external` calls are ever armed, so an armed call from before
 * the class was recorded is `external`.
 */
export function gateRiskClass(item: Record<string, unknown>): string {
	const gate = item?.jup_gate;
	if (gate === null || typeof gate !== 'object' || Array.isArray(gate)) return '';
	const riskClass = (gate as Record<string, unknown>).risk_class;
	if (riskClass === undefined) return 'external';
	return typeof riskClass === 'string' ? riskClass : '';
}
