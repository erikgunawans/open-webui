/** Chat timestamps arrive in seconds from most routes, in nanoseconds from some; read either. */
export const toMillis = (value: number): number =>
	value > 1e15 ? Math.floor(value / 1e6) : value > 1e12 ? value : value * 1000;

/** "12 minutes ago", "yesterday", then a short date, in the user's language. */
export const relativeTime = (value: number, language: string, now = Date.now()): string => {
	const at = toMillis(value);
	const minutes = Math.floor((now - at) / 60_000);
	const rtf = new Intl.RelativeTimeFormat(language, { numeric: 'auto' });
	if (minutes < 1) return rtf.format(0, 'second');
	if (minutes < 60) return rtf.format(-minutes, 'minute');
	const hours = Math.floor(minutes / 60);
	if (hours < 24) return rtf.format(-hours, 'hour');
	if (hours < 48) return rtf.format(-1, 'day');
	return new Intl.DateTimeFormat(language, { day: 'numeric', month: 'short' }).format(at);
};
