// Display-time unmasking of individual parties in an answer (D2). The model only ever writes codes
// such as "Perorangan A"; for a reader the server says may see names (Legal, Direksi), the code is
// shown with the name beside it. Nothing here changes the stored message.

const CODE = /\bPerorangan [A-Z]{1,3}\b/g;

export const findCodes = (text: string): string[] => [...new Set(text.match(CODE) ?? [])];

export const applyNames = (text: string, names: Record<string, string>): string =>
	text.replace(CODE, (code) => (names[code] ? `${names[code]} (${code})` : code));
