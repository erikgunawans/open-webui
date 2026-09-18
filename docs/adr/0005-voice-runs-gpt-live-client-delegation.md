# Voice runs GPT-Live in client delegation mode

The voice interface uses OpenAI **GPT-Live** (`gpt-live-1`) in **client delegation** mode: the Live
session is a conversational shell that hears and speaks, and every substantive turn is handed to our
backend, which runs the same governed completion pipeline as the typed chat (ADR-0002).

The documented happy path — a browser WebRTC session with tools declared on OpenAI's side — was
rejected because it makes voice an eighth bypass of the completion chokepoint, alongside the seven
internal callers that already forge a synthetic `Request`. Audio, transcript and tool calls would
never touch our server, and none of the governance would apply to the surface a director actually
uses.

## Consequences

We pay a full pipeline round trip of latency per turn, held with `session.thinking.append` /
`session.commentary.append` — capped at 500 tokens, they hold the floor, they do not deliver the
answer.

Because our backend sees the complete answer before a word is spoken, **voice is the more governable
surface, not the less**: the tier check that cannot block a websocket-streamed chat response
(ADR-0002) *can* block a spoken one.

GPT-Live's own transcript deltas carry no item ID and no authoritative turn-completed event, and
user and assistant intervals may overlap by design. The audit record of record is therefore built
from pipeline turns; the Live transcript is a secondary artefact of the spoken surface only.
