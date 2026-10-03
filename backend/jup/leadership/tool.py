"""The assistant's read of Ruang Pimpinan (P3): the same views, the same grants, as plain text.

`tools/jup_leadership.py` is the stored wrapper; every rule lives here and is tested in
`tests/test_leadership_tool.py`. Three rules:

- **The page's grants, re-checked on every call.** A tool receives the user, not their permissions,
  so they are resolved here exactly as the router does (`get_permissions` seeded with
  `policy.DEFAULT_PERMISSIONS`), and each view is served only if `policy.may_read` allows it. The
  admin role grants nothing, as on the page.
- **The page's data path.** The configured dataset through `reader.read_overview`, with recorded
  actions when the server reads them from the records store. A dataset that fails validation is
  reported unavailable, never read around.
- **Citations travel with the figures.** Each metric and assumption names its source file and slides,
  and the status line says the figures are a draft and unverified, so the model can say so.

In a Ruang Pimpinan panel call the tool is also told which tab is open beside it (`chat_id`): the
chat's signed `jup.voice` mark names the view, and when it is genuine, on the caller's own chat, and
the caller may read that view, the text names it first. It is a hint, never a grant.

Every call writes one `leadership_read` audit line with `surface='assistant'` (ids only).
"""

from __future__ import annotations

import asyncio
import copy
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jup import voice
from jup.governance import audit
from jup.leadership import policy
from jup.leadership.reader import ACTIONS_SOURCES, DatasetUnavailable, load_dataset, read_overview

SCOPE_ID = 'jup-consolidated'
VIEW_NAMES = {'board': 'Direksi & Komisaris', 'rka': 'RKA & Realisasi'}

UNKNOWN_USER = 'Pengguna tidak dikenali.'
NO_ACCESS = (
    'Akun ini tidak memiliki akses ke Ruang Pimpinan untuk bagian yang diminta. '
    'Sampaikan ke pengguna bahwa aksesnya diatur oleh administrator; jangan menebak isinya.'
)
UNAVAILABLE = 'Data Ruang Pimpinan sedang tidak tersedia di server. Jangan menebak angkanya.'

_KINDS = {'actual': 'realisasi', 'budget': 'anggaran/target', 'forecast': 'prognosa', 'scenario': 'skenario'}
_STATES = {
    'in_progress': 'berjalan',
    'completion_submitted': 'penyelesaian diajukan',
    'closed': 'ditutup',
    'returned': 'dikembalikan',
    'cancelled': 'dibatalkan',
}


class Source:
    """Where the tool reads from. Production values; tests pass their own."""

    def __init__(
        self,
        dataset: Callable[[], dict[str, Any]] | None = None,
        permissions: Callable[[str], Any] | None = None,
        recorded: Callable[[], list[dict[str, Any]] | None] | None = None,
        chat: Callable[[str], Any] | None = None,
        secret: Callable[[], str] | None = None,
    ) -> None:
        self._dataset = dataset
        self._permissions = permissions
        self._recorded = recorded
        self._chat = chat
        self._secret = secret

    async def chat(self, chat_id: str) -> tuple[Any, str | None]:
        """`(meta, owner id)` of a chat, or `(None, None)` when it does not exist."""
        if self._chat is not None:
            found = self._chat(chat_id)
            return (await found) if asyncio.iscoroutine(found) else found
        from open_webui.models.chats import Chats

        chat = await Chats.get_chat_by_id(chat_id)
        return (chat.meta, chat.user_id) if chat is not None else (None, None)

    def secret(self) -> str:
        if self._secret is not None:
            return self._secret()
        from open_webui.env import WEBUI_SECRET_KEY

        return WEBUI_SECRET_KEY

    def dataset(self) -> dict[str, Any]:
        """The configured dataset; raises `DatasetUnavailable` when it is off, missing or untrusted."""
        if self._dataset is not None:
            return self._dataset()
        if os.environ.get('JUP_LEADERSHIP_ENABLED', '').strip().lower() not in ('1', 'true'):
            raise DatasetUnavailable('Ruang Pimpinan is not enabled on this server.')
        path = os.environ.get('JUP_LEADERSHIP_SAMPLE_FILE', '').strip()
        if not path:
            raise DatasetUnavailable('No leadership dataset is configured on this server.')
        return load_dataset(Path(path))

    def recorded(self) -> list[dict[str, Any]] | None:
        """The records store's register when the server reads actions from it, else `None` (sample)."""
        if self._recorded is not None:
            return self._recorded()
        source = os.environ.get('JUP_LEADERSHIP_ACTIONS_SOURCE', '').strip().lower() or 'sample'
        if source not in ACTIONS_SOURCES:
            raise DatasetUnavailable('The Ruang Pimpinan actions source is misconfigured on this server.')
        if source == 'sample':
            return None
        from jup.leadership import migrate
        from jup.leadership.reader import recorded_actions
        from open_webui.internal.db import engine

        if not migrate.schema_ready():
            raise DatasetUnavailable('The Ruang Pimpinan records store is not ready on this server.')
        with engine.connect() as connection:
            return recorded_actions(connection)

    async def permissions(self, user_id: str) -> dict[str, Any]:
        if self._permissions is not None:
            permissions = self._permissions(user_id)
            if asyncio.iscoroutine(permissions):
                permissions = await permissions
            return permissions
        from open_webui.utils.access_control import get_permissions

        return await get_permissions(user_id, copy.deepcopy(policy.DEFAULT_PERMISSIONS))


def _figure(reading: dict[str, Any] | None) -> str:
    if not reading:
        return 'tidak ada'
    if reading.get('value') is None:
        return f'belum tersedia ({reading.get("missing_reason") or "tanpa alasan"})'
    number = reading['value'].replace('.', ',')
    text = f'Rp{number} miliar' if reading['unit'] == 'IDR_billion' else f'{number}%'
    period = f'{reading["period_start"]} s.d. {reading["period_end"]}'
    return f'{text} ({_KINDS.get(reading["kind"], reading["kind"])}, {period})'


def _cite(source_ids: list[str], sources: dict[str, dict[str, Any]]) -> str:
    cited = []
    for source_id in source_ids:
        source = sources.get(source_id)
        if source:
            slides = ', '.join(str(n) for n in source['physical_slides'])
            cited.append(f'"{source["filename"]}" slide {slides}')
    return '; '.join(cited) or 'tanpa sumber'


def _view_text(view: str, overview: dict[str, Any], sources: dict[str, dict[str, Any]]) -> str:
    context = overview['context']
    lines = [
        f'## {VIEW_NAMES[view]} — {context["label"]}',
        f'Periode {context["period_start"]} s.d. {context["period_end"]}; status laporan {context["report_status"]}; '
        f'data {overview["data_mode"]}, cakupan {overview["coverage"]}, belum terverifikasi kecuali disebut lain.',
        '',
        '### Angka utama',
    ]
    for metric in overview['metrics']:
        line = f'- {metric["label"]}: {_figure(metric["primary"])}'
        if metric.get('baseline'):
            line += f'; pembanding {_figure(metric["baseline"])}'
        if metric.get('variance') is not None:
            line += f'; selisih {metric["variance"].replace(".", ",")}'
        if metric.get('comparison_note'):
            line += f'. {metric["comparison_note"]}'
        line += f' [{metric["verification_status"]}; sumber: {_cite(metric["source_ids"], sources)}]'
        lines.append(line)
    if overview['assumptions']:
        lines += ['', '### Asumsi dan pendorong']
        for item in overview['assumptions']:
            lines.append(
                f'- {item["label"]}: {item["target_note"]} Pantau: {item["watch_note"]} '
                f'[sumber: {_cite(item["source_ids"], sources)}]'
            )
    lines += ['', '### Tindak lanjut']
    if overview['actions']:
        for action in overview['actions']:
            due = (action.get('due') or {}).get('label') or 'tanpa tenggat'
            state = _STATES.get(action.get('state'), action.get('state'))
            line = f'- {action["title"]} — {action.get("owner_label") or "tanpa penanggung jawab"}, tenggat {due}, {state}.'
            if action.get('progress_summary'):
                line += f' {action["progress_summary"]}'
            lines.append(line)
    else:
        lines.append(f'- Belum ada. {overview.get("actions_note") or ""}'.rstrip())
    unavailable = [m['label'] for m in overview['module_states'] if m['state'] == 'unavailable']
    if unavailable:
        lines += ['', 'Belum tersedia di Ruang Pimpinan: ' + ', '.join(unavailable) + '.']
    return '\n'.join(lines)


async def _open_view(source: Source, chat_id: Any, user_id: str) -> str | None:
    """The tab open beside the caller's own panel call, when its mark is genuine."""
    if not isinstance(chat_id, str) or not chat_id:
        return None
    try:
        meta, owner = await source.chat(chat_id)
    except Exception:
        return None
    if owner != user_id:
        return None
    return voice.leadership_context_view(meta, chat_id=chat_id, user_id=user_id, secret=source.secret())


async def read_leadership(
    user: dict | None, view: str = '', source: Source | None = None, *, chat_id: str | None = None
) -> str:
    """The views of Ruang Pimpinan this user may read (or just `view`), as text for the model."""
    source = source or Source()
    user_id = (user or {}).get('id')
    if not user_id:
        return UNKNOWN_USER
    wanted = view.strip().lower() if view else ''
    if wanted and wanted not in VIEW_NAMES:
        return f'Bagian "{view}" tidak dikenal. Pilih "board" (Direksi & Komisaris) atau "rka" (RKA & Realisasi).'
    permissions = await source.permissions(user_id)
    views = [v for v in ([wanted] if wanted else list(VIEW_NAMES)) if policy.may_read(permissions, v, SCOPE_ID)]
    if not views:
        audit('leadership_read', user=user_id, surface='assistant', view=wanted or None, result='refused')
        return NO_ACCESS
    try:
        dataset, recorded = await asyncio.to_thread(lambda: (source.dataset(), source.recorded()))
    except DatasetUnavailable:
        audit('leadership_read', user=user_id, surface='assistant', view=wanted or None, result='unavailable')
        return UNAVAILABLE
    sources = {s['id']: s for s in dataset['sources']}
    open_view = await _open_view(source, chat_id, user_id)
    if open_view not in views:
        open_view = None
    else:
        views = [open_view, *(v for v in views if v != open_view)]
    parts = [_view_text(v, read_overview(dataset, v, recorded), sources) for v in views]
    audit('leadership_read', user=user_id, surface='assistant', views=views, open_view=open_view, result='served')
    if open_view:
        parts.insert(
            0,
            f'Pengguna sedang membuka tab "{VIEW_NAMES[open_view]}" di Ruang Pimpinan; '
            '"ini", "tab ini" atau "halaman ini" merujuk ke tab tersebut.',
        )
    parts.append(
        'Sebutkan sumber (nama berkas dan slide) dan bahwa angka masih draft/belum terverifikasi. '
        'Jangan menambah angka yang tidak ada di sini.'
    )
    return '\n\n'.join(parts)
