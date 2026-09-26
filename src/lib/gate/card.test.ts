import { describe, expect, test } from 'vitest';
import { MASK, gateRiskClass, isSecretKey, maskedArguments, maskedText, maskSecrets } from './card';

describe('isSecretKey', () => {
	test.each([
		'token',
		'password',
		'passwd',
		'pwd',
		'secret',
		'api_key',
		'apiKey',
		'API-KEY',
		'apikey',
		'access_token',
		'refreshToken',
		'client_secret',
		'private_key',
		'Authorization',
		'auth_token',
		'x-api-key',
		'passphrase',
		'secret_key',
		'cookie',
		'session_id',
		'sessionToken',
		'credentials',
		'otp'
	])('%s is a secret', (key) => {
		expect(isSecretKey(key)).toBe(true);
	});

	test.each([
		'text',
		'message',
		'author',
		'keyword',
		'monkey',
		'tokenizer_name',
		'passage',
		'query',
		'spin',
		'key',
		'sort_key',
		'pass_rate',
		'pin',
		'auth',
		'session'
	])('%s is not', (key) => {
		expect(isSecretKey(key)).toBe(false);
	});
});

describe('maskSecrets', () => {
	test('masks a secret key and shows everything else in full', () => {
		expect(maskSecrets({ text: 'uji 22', token: 'abc123' })).toEqual({
			text: 'uji 22',
			token: MASK
		});
	});

	test('masks at any depth, in objects and arrays', () => {
		expect(
			maskSecrets({ headers: { Authorization: 'Bearer x' }, users: [{ name: 'a', password: 'p' }] })
		).toEqual({ headers: { Authorization: MASK }, users: [{ name: 'a', password: MASK }] });
	});

	test('masks a whole value under a secret key, even an object', () => {
		expect(maskSecrets({ credentials: { user: 'a', pass: 'b' } })).toEqual({ credentials: MASK });
	});

	test.each([
		'Bearer eyJhbGciOi.xyz',
		'sk-proj-abcdefghijklmnopqrstuv',
		'ghp_abcdefghijklmnopqrstuvwxyz0123',
		'AKIAABCDEFGHIJKLMNOP',
		'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl',
		'xoxb-1234-5678-abcdefgh',
		'AIzaSyA1234567890abcdefghijklmnopqrstu'
	])('masks a secret-looking value under an ordinary key: %s', (value) => {
		expect(maskSecrets({ note: value })).toEqual({ note: MASK });
	});

	test('leaves ordinary strings, numbers and booleans alone', () => {
		const args = { text: 'Bearer of good news', count: 3, dry_run: true, nothing: null };
		expect(maskSecrets(args)).toEqual(args);
	});

	test('does not modify its input', () => {
		const args = { token: 'abc' };
		maskSecrets(args);
		expect(args.token).toBe('abc');
	});
});

describe('maskedArguments', () => {
	test('gate_probe with a token shows the token masked and the text in full', () => {
		const shown = maskedArguments(JSON.stringify({ text: 'uji 22', token: 'rahasia-123' }));
		expect(JSON.parse(shown)).toEqual({ text: 'uji 22', token: MASK });
		expect(shown).not.toContain('rahasia-123');
	});

	test('unwraps arguments the model double-encoded', () => {
		const shown = maskedArguments(JSON.stringify(JSON.stringify({ password: 'x', text: 'y' })));
		expect(JSON.parse(shown)).toEqual({ password: MASK, text: 'y' });
	});

	test('a secret-looking non-JSON string is masked whole', () => {
		expect(maskedArguments('Bearer abc.def')).toBe(MASK);
	});

	test('an ordinary non-JSON string is shown as is', () => {
		expect(maskedArguments('halo')).toBe('halo');
	});

	test('empty stays empty', () => {
		expect(maskedArguments('')).toBe('');
	});
});

describe('gateRiskClass', () => {
	test('a call the server armed carries its class', () => {
		expect(
			gateRiskClass({ jup_gate: { paused_at: 1, tool_id: 'gate_probe', risk_class: 'external' } })
		).toBe('external');
	});

	test('an ungated call has none, so the card shows no label', () => {
		expect(gateRiskClass({ name: 'portfolio_status' })).toBe('');
		expect(gateRiskClass({ jup_gate: 'external' })).toBe('');
		expect(gateRiskClass({ jup_gate: { risk_class: 42 } })).toBe('');
	});

	test('a call armed before #22 stored no class and is gated, so it reads as external', () => {
		expect(gateRiskClass({ jup_gate: { paused_at: 1, tool_id: 'gate_probe' } })).toBe('external');
	});
});

describe('secrets written inside a value', () => {
	test.each([
		['password=hunter2 tolong simpan', 'password=' + MASK + ' tolong simpan'],
		['https://x.test/a?api_key=abc123&page=2', 'https://x.test/a?api_key=' + MASK + '&page=2'],
		["token: 'rahasia' lalu kirim", "token: '" + MASK + "' lalu kirim"],
		['Authorization: Bearer abc.def', 'Authorization: ' + MASK],
		['kunci Bearer abc.def di sini', 'kunci ' + MASK + ' di sini']
	])('%s', (value, shown) => {
		expect(maskedText(value)).toBe(shown);
	});

	test('ordinary key=value text is left alone', () => {
		expect(maskedText('page=2 sort_key=date pass_rate: 90%')).toBe(
			'page=2 sort_key=date pass_rate: 90%'
		);
	});

	test('gate_probe asked for password=… in its message shows the message with the password masked', () => {
		const shown = JSON.parse(
			maskedArguments(JSON.stringify({ message: 'uji 22 password=hunter2' }))
		);
		expect(shown).toEqual({ message: 'uji 22 password=' + MASK });
	});

	test("gate_probe's echoed result masks the token it echoes", () => {
		expect(
			maskedText("gate_probe ran and did nothing. It received message='uji' token='abc123'.")
		).toBe("gate_probe ran and did nothing. It received message='uji' token='" + MASK + "'.");
	});
});

describe('quoted keys in text that is not valid JSON', () => {
	test('a JSON-looking fragment still has its secret masked', () => {
		expect(maskedText('{"password": "hunter2", "text": "ok"')).toBe(
			'{"password": "' + MASK + '", "text": "ok"'
		);
	});

	test('a JSON result goes through the key rule', () => {
		expect(JSON.parse(maskedArguments('{"token": "abc", "echo": "hi"}'))).toEqual({
			token: MASK,
			echo: 'hi'
		});
	});
});
