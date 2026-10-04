import { WEBUI_API_BASE_URL } from '$lib/constants';

// Linking a WhatsApp number (backend/open_webui/routers/jup_whatsapp_link.py, E9.2, #103). The user
// sends the code from WhatsApp; the gateway's link call writes the Mapping. Times are epoch ms.

export type WhatsAppLinkStatus =
	| { available: false }
	| { available: true; linked: false }
	| { available: true; linked: true; hint: string; since: number };

export type WhatsAppLinkCode = {
	code: string;
	expires_at: number;
	wa_link: string;
	disclosure: string;
};

const request = async <T>(token: string, path: string, method = 'GET'): Promise<T> => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/whatsapp-link${path}`, {
		method,
		headers: { Accept: 'application/json', authorization: `Bearer ${token}` }
	});
	if (!res.ok) throw new Error(`The WhatsApp link request failed (${res.status}).`);
	return res.json();
};

export const getWhatsAppLink = (token: string) => request<WhatsAppLinkStatus>(token, '');

export const issueWhatsAppLinkCode = (token: string) =>
	request<WhatsAppLinkCode>(token, '/code', 'POST');

export const unlinkWhatsApp = (token: string) =>
	request<{ unlinked: boolean }>(token, '', 'DELETE');
