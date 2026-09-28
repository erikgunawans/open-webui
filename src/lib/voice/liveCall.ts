/**
 * The browser side of a GPT-Live call (#37, ADR-0018 as amended 2026-09-28).
 *
 * Audio runs on WebRTC straight to OpenAI; the offer goes through our server, which mints the
 * session and holds the request open for the whole call while it answers delegations (#35, #36).
 * The browser never answers a delegation: it only greets, shows captions and hangs up. The browser
 * APIs are injected so the sequence is testable.
 */
import { addCaption, greetingEvent, type Caption } from './live';

export type LiveState = 'connecting' | 'live' | 'ending' | 'ended' | 'failed';

export type LiveDeps = {
	getUserMedia: (constraints: MediaStreamConstraints) => Promise<MediaStream>;
	createPeer: () => RTCPeerConnection;
	/** Our server: posts the offer, resolves with the SDP answer once the call-long stream starts. */
	startSession: (
		sdp: string
	) => Promise<{ session_id: string; sdp: string; ended: Promise<void>; hangUp: () => void }>;
	/** Where the assistant's voice plays. */
	playRemote: (stream: MediaStream) => void;
	/** How long to wait for `session.closed` after asking the session to close. */
	closeWaitMs?: number;
};

export type LiveHandlers = {
	onState: (state: LiveState) => void;
	onCaptions: (captions: Caption[]) => void;
};

export type LiveCall = { hangUp: () => Promise<void> };

const waitForIce = (peer: RTCPeerConnection) =>
	new Promise<void>((resolve) => {
		if (peer.iceGatheringState === 'complete') return resolve();
		const done = () => {
			if (peer.iceGatheringState === 'complete') {
				peer.removeEventListener('icegatheringstatechange', done);
				resolve();
			}
		};
		peer.addEventListener('icegatheringstatechange', done);
		// A slow network still gets an offer with the candidates gathered so far.
		setTimeout(resolve, 3000);
	});

export const startLiveCall = async (deps: LiveDeps, handlers: LiveHandlers): Promise<LiveCall> => {
	handlers.onState('connecting');
	let captions: Caption[] = [];
	let finished = false;
	let resolveClosed: () => void = () => {};
	const closed = new Promise<void>((resolve) => (resolveClosed = resolve));

	const mic = await deps.getUserMedia({ audio: true });
	const peer = deps.createPeer();
	let session: Awaited<ReturnType<LiveDeps['startSession']>> | null = null;

	const cleanup = (state: LiveState) => {
		if (finished) return;
		finished = true;
		mic.getTracks().forEach((track) => track.stop());
		try {
			peer.close();
		} catch {
			// already closed
		}
		session?.hangUp();
		handlers.onState(state);
	};

	try {
		mic.getTracks().forEach((track) => peer.addTrack(track, mic));
		peer.addEventListener('track', (event) => {
			const stream = (event as RTCTrackEvent).streams?.[0];
			if (stream) deps.playRemote(stream);
		});

		const channel = peer.createDataChannel('oai-events');
		channel.addEventListener('message', (message) => {
			let event: { type?: string } | null = null;
			try {
				event = JSON.parse((message as MessageEvent).data);
			} catch {
				return;
			}
			if (event?.type === 'session.started') {
				channel.send(JSON.stringify(greetingEvent()));
				handlers.onState('live');
			} else if (event?.type === 'session.closed') {
				resolveClosed();
			} else {
				const next = addCaption(captions, event);
				if (next !== captions) {
					captions = next;
					handlers.onCaptions(captions);
				}
			}
		});

		const offer = await peer.createOffer();
		await peer.setLocalDescription(offer);
		await waitForIce(peer);
		session = await deps.startSession(peer.localDescription?.sdp ?? offer.sdp ?? '');
		await peer.setRemoteDescription({ type: 'answer', sdp: session.sdp });

		// The server ending the call (an hour at most, or the session closing) ends it here too.
		session.ended.then(() => cleanup('ended'));

		const hangUp = async () => {
			if (finished) return;
			handlers.onState('ending');
			if (channel.readyState === 'open') {
				channel.send(JSON.stringify({ type: 'session.close', event_id: 'jup_hangup' }));
				await Promise.race([closed, new Promise((r) => setTimeout(r, deps.closeWaitMs ?? 3000))]);
			}
			cleanup('ended');
		};
		return { hangUp };
	} catch (error) {
		cleanup('failed');
		throw error;
	}
};
