import { describe, expect, it, vi } from 'vitest';

import { startLiveCall, type LiveDeps, type LiveState } from './liveCall';

class FakeTarget {
	listeners: Record<string, ((event: unknown) => void)[]> = {};
	addEventListener(type: string, listener: (event: unknown) => void) {
		(this.listeners[type] ??= []).push(listener);
	}
	removeEventListener(type: string, listener: (event: unknown) => void) {
		this.listeners[type] = (this.listeners[type] ?? []).filter((l) => l !== listener);
	}
	emit(type: string, event: unknown) {
		(this.listeners[type] ?? []).forEach((l) => l(event));
	}
}

class FakeChannel extends FakeTarget {
	readyState = 'open';
	sent: Record<string, unknown>[] = [];
	send(data: string) {
		this.sent.push(JSON.parse(data));
	}
	receive(event: unknown) {
		this.emit('message', { data: JSON.stringify(event) });
	}
}

class FakePeer extends FakeTarget {
	iceGatheringState = 'complete';
	localDescription: { sdp: string } | null = null;
	remote: unknown = null;
	tracks: unknown[] = [];
	closed = false;
	channel = new FakeChannel();
	addTrack(track: unknown) {
		this.tracks.push(track);
	}
	createDataChannel(label: string) {
		expect(label).toBe('oai-events');
		return this.channel;
	}
	async createOffer() {
		return { type: 'offer', sdp: 'v=0 offer' };
	}
	async setLocalDescription(offer: { sdp: string }) {
		this.localDescription = offer;
	}
	async setRemoteDescription(answer: unknown) {
		this.remote = answer;
	}
	close() {
		this.closed = true;
	}
}

const setup = (over: Partial<LiveDeps> = {}) => {
	const peer = new FakePeer();
	const track = {
		stopped: false,
		stop() {
			this.stopped = true;
		}
	};
	let endServer: () => void = () => {};
	const hangUpServer = vi.fn();
	const states: LiveState[] = [];
	const captions: unknown[] = [];
	const deps: LiveDeps = {
		getUserMedia: vi.fn(async () => ({ getTracks: () => [track] }) as unknown as MediaStream),
		createPeer: () => peer as unknown as RTCPeerConnection,
		startSession: vi.fn(async (sdp: string) => ({
			session_id: 'live_1',
			sdp: `answer to ${sdp}`,
			ended: new Promise<void>((resolve) => (endServer = resolve)),
			hangUp: hangUpServer
		})),
		playRemote: vi.fn(),
		closeWaitMs: 20,
		...over
	};
	const handlers = {
		onState: (s: LiveState) => states.push(s),
		onCaptions: (c: unknown) => captions.push(c)
	};
	return {
		peer,
		track,
		deps,
		handlers,
		states,
		captions,
		hangUpServer,
		endServer: () => endServer()
	};
};

describe('a GPT-Live call in the browser (#37)', () => {
	it('sends the offer through our server and applies its answer', async () => {
		const { peer, deps, handlers, track } = setup();
		await startLiveCall(deps, handlers);
		expect(deps.startSession).toHaveBeenCalledWith('v=0 offer');
		expect(peer.remote).toEqual({ type: 'answer', sdp: 'answer to v=0 offer' });
		expect(peer.tracks).toEqual([track]);
	});

	it('greets once the session starts, and never answers a delegation', async () => {
		const { peer, deps, handlers, states } = setup();
		await startLiveCall(deps, handlers);
		peer.channel.receive({ type: 'session.started' });
		peer.channel.receive({
			type: 'session.delegation.created',
			delegation: { id: 'd1', target: 'client' }
		});
		expect(peer.channel.sent.map((e) => e.type)).toEqual(['session.instructions.append']);
		expect(states).toEqual(['connecting', 'live']);
	});

	it('shows captions from the transcript', async () => {
		const { peer, deps, handlers, captions } = setup();
		await startLiveCall(deps, handlers);
		peer.channel.receive({ type: 'session.input_transcript.delta', delta: 'Halo', start_ms: 5 });
		expect(captions).toEqual([[{ who: 'caller', text: 'Halo', start: 5 }]]);
	});

	it('plays the assistant through the remote stream', async () => {
		const { peer, deps, handlers } = setup();
		await startLiveCall(deps, handlers);
		const stream = { id: 'remote' };
		peer.emit('track', { streams: [stream] });
		expect(deps.playRemote).toHaveBeenCalledWith(stream);
	});

	it('hanging up closes the session, the peer, the microphone and our stream', async () => {
		const { peer, deps, handlers, track, hangUpServer, states } = setup();
		const call = await startLiveCall(deps, handlers);
		const ending = call.hangUp();
		peer.channel.receive({ type: 'session.closed' });
		await ending;
		expect(peer.channel.sent.at(-1)).toMatchObject({ type: 'session.close' });
		expect(peer.closed && track.stopped).toBe(true);
		expect(hangUpServer).toHaveBeenCalled();
		expect(states.slice(-2)).toEqual(['ending', 'ended']);
	});

	it('hangs up even when the session never confirms the close', async () => {
		const { deps, handlers, states } = setup();
		const call = await startLiveCall(deps, handlers);
		await call.hangUp();
		expect(states.at(-1)).toBe('ended');
	});

	it('the server ending the call ends it here', async () => {
		const { peer, deps, handlers, endServer, states } = setup();
		await startLiveCall(deps, handlers);
		endServer();
		await Promise.resolve();
		expect(peer.closed).toBe(true);
		expect(states.at(-1)).toBe('ended');
	});

	it('a refused start releases the microphone and reports the failure', async () => {
		const { peer, deps, handlers, track, states } = setup({
			startSession: vi.fn(async () => {
				throw { code: 'voice_live_not_granted' };
			})
		});
		await expect(startLiveCall(deps, handlers)).rejects.toMatchObject({
			code: 'voice_live_not_granted'
		});
		expect(track.stopped && peer.closed).toBe(true);
		expect(states.at(-1)).toBe('failed');
	});
});
