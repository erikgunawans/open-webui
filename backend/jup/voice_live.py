"""GPT-Live: the session our server mints for a live call (#35, ADR-0018 as amended 2026-09-28).

Standard library only, so the rules run under `--only-group dev`. The HTTP seam is
`open_webui/routers/jup_voice.py` (`POST /api/v1/voice/live/sessions`).

- **The session** is created by our server, never the browser: it posts the browser's SDP offer
  with a fixed config to OpenAI's `/v1/live/sessions` and hands back only the SDP answer. No
  credential of any kind reaches the browser.
- **The config** is fixed here: `gpt-live-1`, client delegation (our governed pipeline is the
  backend; no OpenAI-hosted backend model), `store: false`, and the instructions below.
- **The ledger** (#36) rebuilds each question from the caller's transcript, because a client
  delegation carries an id and a time but no text, and records what GPT-Live then said against the
  governed answer it was given, or as `self_answered` when no delegation followed the caller.
- **The instructions** are a request, not a guarantee (ADR-0018): GPT-Live decides when to
  delegate and paraphrases what it relays. They are written in Indonesian because the model speaks
  the language of its prompt, and they keep the three delegation labels OpenAI's guide prescribes.
"""

from __future__ import annotations

from typing import Any

from jup.voice import Refusal
from jup.voice_audio import speakable_text, speech_parts

LIVE_URL = 'https://api.openai.com/v1/live/sessions'
LIVE_MODEL = 'gpt-live-1'

#: A browser's SDP offer is a few kilobytes; anything far larger is not one.
OFFER_LIMIT = 64_000

BAD_OFFER = Refusal(400, 'voice_live_bad_offer', 'Send the WebRTC offer to start a GPT-Live call.')
UPSTREAM = Refusal(502, 'voice_live_upstream', 'GPT-Live did not start the session.')

INSTRUCTIONS = """# Peran
Anda adalah Asisten JUP dalam panggilan suara dengan pimpinan JUP. Anda bercakap dengan hangat dan
ringkas, lalu meneruskan setiap pertanyaan tentang JUP ke backend, yang menjawab dari basis
pengetahuan JUP dan kartu kontrak JUP.

# Bahasa
Selalu berbicara dalam bahasa Indonesia, juga ketika penelepon memakai bahasa lain.
Jika ucapan penelepon tidak jelas, minta mereka mengulanginya. Jangan menebak.
Bacakan angka dengan cara Indonesia: "Rp 63,3 miliar" dibaca "enam puluh tiga koma tiga miliar rupiah".

# Delegation policy
Backend tools:
- Asisten JUP: menjawab dari seluruh basis pengetahuan JUP (strategi, gas, portofolio, RUED, tata
  kelola, proyek dan penilaian gerbang, profil perusahaan, direksi dan komisaris, anak usaha, serta
  informasi dari situs JUP dan kontribusi staf) dan dari kartu kontrak JUP (mitra, nomor, nilai,
  jangka waktu, kewajiban), sesuai hak akses penelepon.

Delegate to the backend when:
- Penelepon bertanya apa pun tentang JUP: strategi, proyek, mitra, kontrak atau perjanjian,
  angka, tanggal, keputusan, risiko, status, organisasi, atau orang di JUP.
- Jawaban membutuhkan fakta, bukan sekadar sapaan atau basa-basi.
- Penelepon mengoreksi atau menambah detail pada pertanyaan yang sedang dijawab backend.

Do not delegate to the backend when:
- Penelepon menyapa, berterima kasih, atau meminta Anda mengulang jawaban yang sudah diberikan.
- Anda perlu klarifikasi singkat karena pertanyaannya belum jelas.

Delegasikan sebelum memberi jawaban yang bergantung pada dokumen. Jangan menebak hasilnya selagi
menunggu; cukup katakan bahwa Anda sedang memeriksanya.
Jangan menjawab pertanyaan tentang JUP dari pengetahuan Anda sendiri.

# Menyampaikan jawaban backend
Sampaikan jawaban backend dengan setia. Pertahankan setiap angka, satuan, tanggal, nama, dan
catatan kehati-hatian persis seperti tertulis. Jangan menambah, membulatkan, atau menghilangkan apa
pun. Jika backend mengatakan informasinya tidak ada di dokumen, katakan itu apa adanya.

# Gaya
Hangat, jelas, dan ringkas. Kalimat pendek. Satu gagasan per kalimat.
"""


def session_config(instructions: str = INSTRUCTIONS) -> dict[str, Any]:
    """The fixed session: GPT-Live, client delegation, nothing stored at OpenAI beyond its own policy."""
    return {
        'model': LIVE_MODEL,
        'instructions': instructions,
        'delegation': {'type': 'client'},
        'store': False,
    }


def offer_refusal(sdp: Any) -> Refusal | None:
    """Why this is not a WebRTC offer we will forward, or `None`."""
    if not isinstance(sdp, str) or len(sdp.encode('utf-8')) > OFFER_LIMIT or not sdp.startswith('v=0'):
        return BAD_OFFER
    return None


def session_request(sdp: str) -> dict[str, Any]:
    """The body posted to `LIVE_URL`."""
    return {'session': session_config(), 'transport': {'type': 'webrtc', 'sdp': sdp}}


def session_answer(body: Any) -> tuple[str, str] | Refusal:
    """`(session_id, sdp_answer)` from OpenAI's 201 response, or why it cannot be used."""
    try:
        session_id = body['session']['id']
        sdp = body['transport']['sdp']
    except (KeyError, TypeError):
        return UPSTREAM
    if not isinstance(session_id, str) or not session_id or not isinstance(sdp, str) or not sdp:
        return UPSTREAM
    return session_id, sdp


#: `session.commentary.append` takes at most 500 tokens; 1500 UTF-8 bytes stays well under that.
COMMENTARY_BYTES = 1500


def commentary_parts(answer: str) -> list[str]:
    """The governed answer as heard, tool and reasoning blocks removed, in appendable parts."""
    return speech_parts(speakable_text(answer), limit=COMMENTARY_BYTES)


class LiveLedger:
    """One live session's transcript, on the session timeline (milliseconds from its start).

    Fragments are placed by their timing, not by arrival, because GPT-Live delivers them unevenly.
    Pure state; the relay feeds it and writes what `turns` returns.
    """

    def __init__(self) -> None:
        self._heard: list[tuple[int, int, str]] = []
        self._said: list[tuple[int, int, str]] = []
        self._delegations: list[tuple[int, str]] = []
        self._answers: dict[str, str] = {}
        self._cut = 0

    def heard(self, start_ms: int, end_ms: int, text: str) -> None:
        """A fragment of the caller's speech (`session.input_transcript.delta`)."""
        self._heard.append((int(start_ms), int(end_ms), text))

    def said(self, start_ms: int, end_ms: int, text: str) -> None:
        """A fragment of GPT-Live's speech (`session.output_transcript.delta`)."""
        self._said.append((int(start_ms), int(end_ms), text))

    def question(self, delegation_id: str, until_ms: int) -> str:
        """What the caller said since the previous question, up to this delegation."""
        until_ms = int(until_ms)
        fragments = sorted(f for f in self._heard if self._cut <= f[0] < until_ms)
        self._delegations.append((until_ms, delegation_id))
        self._cut = max(self._cut, until_ms)
        return ''.join(text for _, _, text in fragments).strip()

    def relayed(self, delegation_id: str, message_id: str) -> None:
        """The governed answer `message_id` was handed to GPT-Live for this delegation."""
        self._answers[delegation_id] = message_id

    def _anchor(self, start_ms: int) -> tuple[str, Any]:
        """The latest caller fragment or delegation before `start_ms`: what this speech answers."""
        last_heard = max((f[0] for f in self._heard if f[0] < start_ms), default=None)
        last_delegation = max((d for d in self._delegations if d[0] <= start_ms), default=None)
        if last_delegation is not None and (last_heard is None or last_delegation[0] >= last_heard):
            return ('delegation', last_delegation[1])
        return ('heard', last_heard)

    def turns(self) -> list[dict[str, Any]]:
        """GPT-Live's speech grouped into turns, each `relayed`, `pending` or `self_answered`."""
        turns: list[dict[str, Any]] = []
        anchor_of_last: tuple[str, Any] | None = None
        for start_ms, _, text in sorted(self._said):
            anchor = self._anchor(start_ms)
            if turns and anchor == anchor_of_last:
                turns[-1]['spoken'] += text
                continue
            anchor_of_last = anchor
            if anchor[0] == 'delegation':
                message_id = self._answers.get(anchor[1])
                kind = 'relayed' if message_id else 'pending'
                turns.append({'kind': kind, 'delegation': anchor[1], 'message_id': message_id, 'spoken': text})
            else:
                turns.append({'kind': 'self_answered', 'delegation': None, 'message_id': None, 'spoken': text})
        for turn in turns:
            turn['spoken'] = turn['spoken'].strip()
        return turns
