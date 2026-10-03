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

import re
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
pengetahuan JUP, kartu kontrak JUP, dan Ruang Pimpinan.

# Bahasa
Selalu berbicara dalam bahasa Indonesia, juga ketika penelepon memakai bahasa lain.
Jika ucapan penelepon tidak jelas, minta mereka mengulanginya. Jangan menebak.
Bacakan angka dengan cara Indonesia: "Rp 63,3 miliar" dibaca "enam puluh tiga koma tiga miliar rupiah".

# Delegation policy
Backend tools:
- Asisten JUP: menjawab dari seluruh basis pengetahuan JUP (strategi, gas, portofolio, RUED, tata
  kelola, proyek dan penilaian gerbang, profil perusahaan, direksi dan komisaris, anak usaha, serta
  informasi dari situs JUP dan kontribusi staf), dari kartu kontrak JUP (mitra, nomor, nilai,
  jangka waktu, kewajiban), dan dari Ruang Pimpinan (realisasi dan anggaran untuk rapat Direksi &
  Komisaris, RKA 2027: target, asumsi, pendorong, tindak lanjut), sesuai hak akses penelepon.

Delegate to the backend when:
- Penelepon bertanya apa pun tentang JUP: strategi, proyek, mitra, kontrak atau perjanjian, RKA,
  anggaran, realisasi, target, angka, tanggal, keputusan, risiko, status, organisasi, atau orang di JUP.
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


#: GPT-Live's own pause longer than this ends an utterance.
UTTERANCE_GAP_MS = 1200
#: A shorter pause ends it too if the caller started speaking in it; below this it is a breath.
CALLER_PAUSE_MS = 250
#: Speech the timing calls `self_answered` is relayed if this share of its content words come from
#: one answer already handed over, and it has at least `GROUNDED_MIN_WORDS` of them.
GROUNDED_SHARE = 0.5
GROUNDED_MIN_WORDS = 3
#: Words too common in spoken Indonesian to show where a sentence came from.
_COMMON_WORDS = frozenset(
    'ada adalah agar akan anda apa atau bagi baik bahwa banyak beberapa belum bisa boleh bukan '
    'dalam dan dari dengan dia dulu hanya harus ingin ini itu iya jadi juga kalau kami kita '
    'lagi lain lalu lebih mana masih mau maaf nanti oke pada para saat saja sama sangat saya '
    'sebagai sedang sekarang semua sih silakan soal sudah supaya tadi tapi tentang terima kasih '
    'tersebut tidak untuk yang'.split()
)


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
        self._answer_words: dict[str, frozenset[str]] = {}
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

    def relayed(self, delegation_id: str, message_id: str, answer: str = '') -> None:
        """The governed answer `message_id` (text `answer`) was handed to GPT-Live for this delegation."""
        self._answers[delegation_id] = message_id
        self._answer_words[delegation_id] = frozenset(_content_words(answer))

    def _grounded_in(self, start_ms: int, text: str) -> str | None:
        """The relayed delegation this speech repeats, by its words, among those asked before it began.

        Timing alone cannot tell: GPT-Live says its filler at once and the answer seconds later,
        often after the caller has said something, and it answers follow-ups from an answer it
        already holds.
        """
        words = set(_content_words(text))
        if len(words) < GROUNDED_MIN_WORDS:
            return None
        best: tuple[float, int, str] | None = None
        for at_ms, delegation_id in self._delegations:
            answer_words = self._answer_words.get(delegation_id)
            if at_ms > start_ms or not answer_words:
                continue
            share = len(words & answer_words) / len(words)
            if share >= GROUNDED_SHARE and (best is None or (share, at_ms) > best[:2]):
                best = (share, at_ms, delegation_id)
        return best[2] if best else None

    def _anchor(self, start_ms: int) -> tuple[str, Any]:
        """The latest caller fragment or delegation before `start_ms`: what this speech answers."""
        last_heard = max((f[0] for f in self._heard if f[0] < start_ms), default=None)
        last_delegation = max((d for d in self._delegations if d[0] <= start_ms), default=None)
        if last_delegation is not None and (last_heard is None or last_delegation[0] >= last_heard):
            return ('delegation', last_delegation[1])
        return ('heard', last_heard)

    def _utterances(self) -> list[tuple[int, str]]:
        """GPT-Live's speech joined into utterances: (start, text).

        Transcript deltas carry no item id and no end-of-turn event (OpenAI's live guide), so an
        utterance is cut by timing alone: a pause longer than `UTTERANCE_GAP_MS`, or a pause of at
        least `CALLER_PAUSE_MS` in which the caller started speaking. Caller sound that overlaps
        GPT-Live's own speech (echo, a cough, talking over it) never cuts an utterance: on the
        2026-10-02 acceptance call it split one sentence into five turns and labelled the tail of a
        relayed answer `self_answered`.
        """
        utterances: list[tuple[int, str]] = []
        last_end: int | None = None
        for start_ms, end_ms, text in sorted(self._said):
            gap = None if last_end is None else start_ms - last_end
            caller_in_pause = (
                gap is not None
                and gap >= CALLER_PAUSE_MS
                and any(last_end <= heard_start < start_ms for heard_start, _, _ in self._heard)
            )
            if utterances and gap is not None and gap <= UTTERANCE_GAP_MS and not caller_in_pause:
                utterances[-1] = (utterances[-1][0], utterances[-1][1] + text)
            else:
                utterances.append((start_ms, text))
            last_end = end_ms if last_end is None else max(last_end, end_ms)
        return utterances

    def turns(self) -> list[dict[str, Any]]:
        """GPT-Live's utterances grouped into turns, each `relayed`, `pending` or `self_answered`.

        An utterance answers whatever came last before it began: a delegation, or the caller. One
        that would be `self_answered` is `relayed` instead when its words come from an answer
        already handed over; such turns carry `matched: 'content'`.
        """
        turns: list[dict[str, Any]] = []
        key_of_last: tuple[str, Any] | None = None
        for start_ms, text in self._utterances():
            anchor = self._anchor(start_ms)
            matched = False
            if anchor[0] != 'delegation':
                grounded = self._grounded_in(start_ms, text)
                if grounded is not None:
                    anchor, matched = ('delegation', grounded), True
            if turns and anchor == key_of_last:
                turns[-1]['spoken'] += ' ' + text
                if matched:
                    turns[-1]['matched'] = 'content'
                continue
            key_of_last = anchor
            if anchor[0] == 'delegation':
                message_id = self._answers.get(anchor[1])
                kind = 'relayed' if message_id else 'pending'
                turns.append({'kind': kind, 'delegation': anchor[1], 'message_id': message_id, 'spoken': text})
                if matched:
                    turns[-1]['matched'] = 'content'
            else:
                turns.append({'kind': 'self_answered', 'delegation': None, 'message_id': None, 'spoken': text})
        for turn in turns:
            turn['spoken'] = ' '.join(turn['spoken'].split())
        return turns


def _content_words(text: str) -> list[str]:
    """The words of `text` that say what it is about: lower-cased, three letters or more, not common."""
    words = re.findall(r'[0-9a-zà-ÿ]+', text.lower())
    return [w for w in words if len(w) >= 3 and w not in _COMMON_WORDS]
