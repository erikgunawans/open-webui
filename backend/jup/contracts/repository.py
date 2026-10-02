"""Reads and writes on the contract tables. Sync Core on the vendor engine; routers call it in a threadpool.

A card arrives from a drafting run as a draft. Legal's work is never overwritten by a later run: once a
card is edited, approved or returned, a new draft is stored beside it (`draft_card`) and an event says
so, but the card everyone reads (`current_card`) stays Legal's.
"""

import hashlib
import json
import re
import time
import uuid
from typing import Any

from sqlalchemy import func, insert, select, update

from jup.contracts import cards
from jup.contracts.models import STATES, contract, contract_event, party, party_link


def canonical_json(value: Any) -> str:
    """Sorted keys, no whitespace, UTF-8 kept: the bytes a hash covers."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def party_code(index: int) -> str:
    """The `index`-th masking code, counting A … Z, AA … ZZ, AAA … like spreadsheet columns."""
    letters = ''
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord('A') + rest) + letters
    return f'Perorangan {letters}'


def name_key(name: str) -> str:
    """One person, however the draft spelled the spacing and case of their name."""
    return re.sub(r'\s+', ' ', name).strip().casefold()


def _searchable(card: dict[str, Any] | None) -> dict[str, Any]:
    return {
        'partner': cards.text(card, 'mitra'),
        'contract_number': cards.text(card, 'nomor_pks'),
        'title': cards.text(card, 'judul'),
        'doc_type': cards.text(card, 'jenis_dokumen'),
    }


def _append_event(
    connection: Any, contract_id: str, version: int, kind: str, payload: dict, actor: str, reason: str | None = None
) -> None:
    connection.execute(
        insert(contract_event).values(
            id=str(uuid.uuid4()),
            contract_id=contract_id,
            version=version,
            kind=kind,
            payload=canonical_json(payload),
            reason=reason,
            actor=actor,
            at=_now_ms(),
        )
    )


def _link_parties(connection: Any, contract_id: str, names: list[str]) -> None:
    for name in names:
        key = name_key(name)
        found = connection.execute(select(party.c.id).where(party.c.name_key == key)).scalar()
        if found is None:
            count = connection.execute(select(func.count()).select_from(party)).scalar() or 0
            found = str(uuid.uuid4())
            connection.execute(
                insert(party).values(
                    id=found,
                    code=party_code(count),
                    name=re.sub(r'\s+', ' ', name).strip(),
                    name_key=key,
                    created_at=_now_ms(),
                )
            )
        linked = connection.execute(
            select(party_link.c.party_id).where(party_link.c.contract_id == contract_id, party_link.c.party_id == found)
        ).first()
        if linked is None:
            connection.execute(insert(party_link).values(contract_id=contract_id, party_id=found))


def import_record(engine: Any, record: dict[str, Any], *, run: str, actor: str) -> str:
    """Store one drafting-run record. Returns created, updated, unchanged or redraft_held."""
    card = record.get('card') if isinstance(record.get('card'), dict) else None
    draft = canonical_json(card) if card is not None else None
    draft_hash = _sha256(draft) if draft is not None else None
    now = _now_ms()
    with engine.begin() as connection:
        existing = (
            connection.execute(select(contract).where(contract.c.source_item_id == record['itemId'])).mappings().first()
        )
        if existing is None:
            contract_id = str(uuid.uuid4())
            connection.execute(
                insert(contract).values(
                    id=contract_id,
                    source_item_id=record['itemId'],
                    run=run,
                    number=str(record['n']),
                    source_object=record['gcs'],
                    source_web_url=record.get('webUrl'),
                    source_path=canonical_json(list(record.get('path') or [])),
                    source_file=record.get('file') or '',
                    page_count=int(record.get('pages') or 0),
                    low_confidence_pages=canonical_json(list(record.get('ocrLowConfidencePages') or [])),
                    manual_check_pages=canonical_json(list((card or {}).get(cards.MANUAL_PAGES) or [])),
                    model=record.get('model'),
                    draft_card=draft,
                    draft_sha256=draft_hash,
                    current_card=draft,
                    state='draft',
                    units='[]',
                    version=1,
                    created_at=now,
                    updated_at=now,
                    **_searchable(card),
                )
            )
            _append_event(
                connection,
                contract_id,
                1,
                'imported',
                {'run': run, 'number': str(record['n']), 'draft_sha256': draft_hash},
                actor,
            )
            _link_parties(connection, contract_id, cards.individuals(card))
            return 'created'

        if existing['draft_sha256'] == draft_hash:
            return 'unchanged'

        version = existing['version'] + 1
        untouched = existing['state'] == 'draft' and existing['current_card'] == existing['draft_card']
        values: dict[str, Any] = {
            'draft_card': draft,
            'draft_sha256': draft_hash,
            'version': version,
            'updated_at': now,
        }
        if untouched:
            values.update(
                current_card=draft,
                model=record.get('model'),
                manual_check_pages=canonical_json(list((card or {}).get(cards.MANUAL_PAGES) or [])),
                **_searchable(card),
            )
        connection.execute(update(contract).where(contract.c.id == existing['id']).values(**values))
        kind = 'redrafted' if untouched else 'redraft_held'
        _append_event(connection, existing['id'], version, kind, {'run': run, 'draft_sha256': draft_hash}, actor)
        if untouched:
            _link_parties(connection, existing['id'], cards.individuals(card))
        return 'updated' if untouched else 'redraft_held'


def set_state(engine: Any, contract_id: str, state: str, *, actor: str, reason: str | None = None) -> None:
    """Move a card to `state`, with an event. The review screen's approve/return build on this."""
    if state not in STATES:
        raise ValueError(f'{state!r} is not a card state')
    with engine.begin() as connection:
        current = connection.execute(select(contract.c.version).where(contract.c.id == contract_id)).scalar()
        if current is None:
            raise LookupError(contract_id)
        connection.execute(
            update(contract)
            .where(contract.c.id == contract_id)
            .values(state=state, version=current + 1, updated_at=_now_ms())
        )
        _append_event(connection, contract_id, current + 1, state, {}, actor, reason)


def get_contract(
    engine: Any, *, run: str | None = None, number: str | None = None, contract_id: str | None = None
) -> dict[str, Any] | None:
    statement = select(contract)
    if contract_id is not None:
        statement = statement.where(contract.c.id == contract_id)
    else:
        statement = statement.where(contract.c.run == run, contract.c.number == number)
    with engine.connect() as connection:
        row = connection.execute(statement).mappings().first()
    return dict(row) if row else None


def events(engine: Any, contract_id: str) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(
            select(contract_event).where(contract_event.c.contract_id == contract_id).order_by(contract_event.c.version)
        ).mappings()
        return [dict(row) for row in rows]


def parties(engine: Any, contract_id: str) -> list[dict[str, Any]]:
    """The individual parties of one contract, with their codes, in code order."""
    with engine.connect() as connection:
        rows = connection.execute(
            select(party.c.code, party.c.name)
            .join(party_link, party_link.c.party_id == party.c.id)
            .where(party_link.c.contract_id == contract_id)
            .order_by(party.c.created_at, party.c.code)
        ).mappings()
        return [dict(row) for row in rows]


_ISO_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_RENEWAL = {'ya': True, 'tidak': False}


def _date(value: Any) -> str | None:
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        return None
    try:
        import datetime as dt

        dt.date.fromisoformat(value)
    except ValueError:
        return None
    return value


def set_dates(
    engine: Any,
    contract_id: str,
    *,
    start: str | None,
    end: str | None,
    auto_renewal: bool | None,
    actor: str,
    kind: str = 'dates_set',
    payload: dict[str, Any] | None = None,
) -> bool:
    """Record structured dates with an event. Returns False when nothing changed.

    `dates_set` comes from the dates pass and never overrides a `dates_edited` (Legal's own entry).
    """
    with engine.begin() as connection:
        row = connection.execute(select(contract).where(contract.c.id == contract_id)).mappings().first()
        if row is None:
            raise LookupError(contract_id)
        if kind == 'dates_set':
            edited = connection.execute(
                select(contract_event.c.id).where(
                    contract_event.c.contract_id == contract_id, contract_event.c.kind == 'dates_edited'
                )
            ).first()
            if edited is not None:
                return False
        if (row['start_date'], row['end_date'], row['auto_renewal']) == (start, end, auto_renewal):
            return False
        version = row['version'] + 1
        connection.execute(
            update(contract)
            .where(contract.c.id == contract_id)
            .values(start_date=start, end_date=end, auto_renewal=auto_renewal, version=version, updated_at=_now_ms())
        )
        _append_event(
            connection,
            contract_id,
            version,
            kind,
            {'start': start, 'end': end, 'auto_renewal': auto_renewal, **(payload or {})},
            actor,
        )
        return True


def apply_dates_record(engine: Any, *, run: str, number: str, record: dict[str, Any], actor: str) -> bool:
    """Apply a dates-pass record (`deploy/gcp/legal-kb/dates.ts`). Invalid dates count as unknown."""
    row = get_contract(engine, run=run, number=number)
    if row is None:
        return False
    return set_dates(
        engine,
        row['id'],
        start=_date(record.get('tanggal_mulai')),
        end=_date(record.get('tanggal_berakhir')),
        auto_renewal=_RENEWAL.get(record.get('perpanjangan_otomatis')),
        actor=actor,
        payload={'confidence': record.get('keyakinan')},
    )
