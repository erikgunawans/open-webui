"""Legal's review of the contract cards: the queue behind the "Kartu Kontrak" tab, and every change.

The router checks the `review` grant; this module holds the rules and is tested without a server.

- **Every change names the version it was made against.** The version moves with a conditional
  UPDATE in the same transaction as its event, so two reviewers editing one card cannot both land:
  the second gets `Conflict` and reloads.
- **Editing changes approval.** An edit to an approved card (a field, the individual parties) puts
  it back to `draft`: what Legal approved is no longer what the card says. Dates, units and links
  are metadata beside the card and leave the state alone.
- **Approve is hash-guarded.** The reviewer sends the SHA-256 of the card they read; approving a card
  that changed since refuses with `Conflict`, even at the same version.
- **Return needs a reason**, kept on the event.
- **The individual-party list is the masking list.** Fixing it relinks the parties, and every view
  masks from the links, so a fix re-masks every answer from then on.

Every change writes one event; `jup_contract_event` stays append-only.
"""

import json
import re
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, delete, exists, func, insert, or_, select, update

from jup.contracts import cards
from jup.contracts.models import LINK_KINDS, STATES, contract, contract_link, party, party_link
from jup.contracts.repository import (
    _append_event,
    _date,
    _link_parties,
    _searchable,
    _sha256,
    canonical_json,
    events,
    parties,
)

FLAGS: tuple[str, ...] = ('perorangan', 'manual', 'low_ocr')
MAX_LIMIT = 100
MAX_TEXT = 20000
MAX_REASON = 2000
_UNIT = re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')


class Conflict(Exception):
    """The card moved since the reviewer loaded it. Reload and redo."""


class Invalid(ValueError):
    """The change itself is malformed. The message says how."""


def _now_ms() -> int:
    return int(time.time() * 1000)


def card_sha256(current_card: str | None) -> str | None:
    return _sha256(current_card) if current_card is not None else None


# --- Reading ---------------------------------------------------------------------------------------


def _flag_clause(flag: str) -> Any:
    if flag == 'perorangan':
        return exists().where(party_link.c.contract_id == contract.c.id)
    if flag == 'manual':
        return contract.c.manual_check_pages != '[]'
    if flag == 'low_ocr':
        return contract.c.low_confidence_pages != '[]'
    raise Invalid(f'The filters are {", ".join(FLAGS)}.')


def _keyword_clause(q: str) -> Any:
    pattern = f'%{q.lower()}%'
    return or_(
        *(
            func.lower(func.coalesce(column, '')).like(pattern)
            for column in (contract.c.partner, contract.c.contract_number, contract.c.title, contract.c.number)
        )
    )


def _summary(row: dict[str, Any], individuals: int) -> dict[str, Any]:
    return {
        'id': row['id'],
        'run': row['run'],
        'number': row['number'],
        'partner': row['partner'],
        'contract_number': row['contract_number'],
        'title': row['title'],
        'doc_type': row['doc_type'],
        'state': row['state'],
        'version': row['version'],
        'end_date': row['end_date'],
        'units': json.loads(row['units']),
        'individuals': individuals,
        'manual_pages': len(json.loads(row['manual_check_pages'])),
        'low_ocr_pages': len(json.loads(row['low_confidence_pages'])),
        'updated_at': row['updated_at'],
    }


def queue(
    engine: Any,
    *,
    state: str | None = None,
    flag: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """One page of the queue, individual parties first, then manual-check, then by number.

    `counts` are over the whole table, so the filter chips stay put while a filter is on.
    """
    if state is not None and state not in STATES:
        raise Invalid(f'The states are {", ".join(STATES)}.')
    limit = max(1, min(int(limit), MAX_LIMIT))
    offset = max(0, int(offset))
    conditions = []
    if state is not None:
        conditions.append(contract.c.state == state)
    if flag is not None:
        conditions.append(_flag_clause(flag))
    if q and q.strip():
        conditions.append(_keyword_clause(q.strip()))
    where = and_(*conditions) if conditions else None

    individuals = (
        select(func.count())
        .select_from(party_link)
        .where(party_link.c.contract_id == contract.c.id)
        .scalar_subquery()
        .label('individuals')
    )
    statement = select(contract, individuals)
    total = select(func.count()).select_from(contract)
    if where is not None:
        statement = statement.where(where)
        total = total.where(where)
    statement = (
        statement.order_by(
            (individuals > 0).desc(), (contract.c.manual_check_pages != '[]').desc(), contract.c.run, contract.c.number
        )
        .limit(limit)
        .offset(offset)
    )

    with engine.connect() as connection:
        rows = connection.execute(statement).mappings().all()
        counted = connection.execute(total).scalar() or 0
        counts = {
            flag_name: connection.execute(
                select(func.count()).select_from(contract).where(_flag_clause(flag_name))
            ).scalar()
            or 0
            for flag_name in FLAGS
        }
        by_state = dict(connection.execute(select(contract.c.state, func.count()).group_by(contract.c.state)).all())
    counts.update({name: by_state.get(name, 0) for name in STATES})
    return {
        'total': counted,
        'limit': limit,
        'offset': offset,
        'counts': counts,
        'items': [_summary(dict(row), row['individuals']) for row in rows],
    }


def links(engine: Any, contract_id: str) -> list[dict[str, Any]]:
    """Documents tied to this contract, both directions: what amends it and what it amends."""
    with engine.connect() as connection:
        outgoing = connection.execute(
            select(contract_link.c.kind, contract.c.id, contract.c.run, contract.c.number, contract.c.title)
            .join(contract, contract.c.id == contract_link.c.related_id)
            .where(contract_link.c.contract_id == contract_id)
        ).mappings()
        found = [{**dict(row), 'direction': 'related'} for row in outgoing]
        incoming = connection.execute(
            select(contract_link.c.kind, contract.c.id, contract.c.run, contract.c.number, contract.c.title)
            .join(contract, contract.c.id == contract_link.c.contract_id)
            .where(contract_link.c.related_id == contract_id)
        ).mappings()
        found.extend({**dict(row), 'direction': 'main'} for row in incoming)
    return found


def detail(engine: Any, contract_id: str) -> dict[str, Any] | None:
    """Everything the review screen shows for one card. Unmasked: the router masks for a reader without `names`."""
    with engine.connect() as connection:
        row = connection.execute(select(contract).where(contract.c.id == contract_id)).mappings().first()
    if row is None:
        return None
    row = dict(row)
    current = json.loads(row['current_card']) if row['current_card'] else None
    draft = json.loads(row['draft_card']) if row['draft_card'] else None
    return {
        'contract': _summary(row, 0)
        | {
            'start_date': row['start_date'],
            'auto_renewal': row['auto_renewal'],
            'page_count': row['page_count'],
            'manual_check_pages': json.loads(row['manual_check_pages']),
            'low_confidence_pages': json.loads(row['low_confidence_pages']),
            'model': row['model'],
        },
        'card': current,
        'card_sha256': card_sha256(row['current_card']),
        # A later drafting run's card, held beside Legal's work (`redraft_held`).
        'draft_card': draft if row['draft_card'] != row['current_card'] else None,
        'parties': parties(engine, contract_id),
        'links': links(engine, contract_id),
        'events': [{**event, 'payload': json.loads(event['payload'])} for event in events(engine, contract_id)],
    }


# --- Writing ---------------------------------------------------------------------------------------


@dataclass
class _Locked:
    row: dict[str, Any]
    version: int


def _bump(connection: Any, contract_id: str, expected_version: int, **values: Any) -> _Locked:
    """Move the version on by one if it is still `expected_version`, with `values`; else Conflict."""
    row = connection.execute(select(contract).where(contract.c.id == contract_id)).mappings().first()
    if row is None:
        raise LookupError(contract_id)
    version = int(expected_version) + 1
    result = connection.execute(
        update(contract)
        .where(contract.c.id == contract_id, contract.c.version == int(expected_version))
        .values(version=version, updated_at=_now_ms(), **values)
    )
    if result.rowcount != 1:
        raise Conflict(contract_id)
    return _Locked(row=dict(row), version=version)


def _check_text(value: Any, what: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Invalid(f'{what} is empty.')
    if len(value) > limit:
        raise Invalid(f'{what} is longer than {limit} characters.')
    return value.strip()


def _check_pages(value: Any, page_count: int) -> list[int]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(page, int) and not isinstance(page, bool) for page in value):
        raise Invalid('Pages are a list of page numbers.')
    if any(page < 1 or page > page_count for page in value):
        raise Invalid(f'Pages run from 1 to {page_count}.')
    return sorted(set(value))


def _state_after_edit(state: str) -> str:
    return 'draft' if state == 'approved' else state


def edit_field(
    engine: Any,
    contract_id: str,
    field: str,
    *,
    text: Any,
    pages: Any,
    expected_version: int,
    actor: str,
) -> dict[str, Any]:
    """Replace one card field. An approved card goes back to draft."""
    if field not in cards.FIELDS:
        raise Invalid(f'{field!r} is not a card field.')
    with engine.begin() as connection:
        row = connection.execute(select(contract).where(contract.c.id == contract_id)).mappings().first()
        if row is None:
            raise LookupError(contract_id)
        value = {'isi': _check_text(text, 'The field text'), 'halaman': _check_pages(pages, row['page_count'])}
        card = json.loads(row['current_card']) if row['current_card'] else _empty_card()
        before = card.get(field)
        if before == value:
            return {'version': row['version'], 'state': row['state'], 'changed': False}
        card[field] = value
        stored = canonical_json(card)
        state = _state_after_edit(row['state'])
        locked = _bump(connection, contract_id, expected_version, current_card=stored, state=state, **_searchable(card))
        _append_event(
            connection,
            contract_id,
            locked.version,
            'field_edited',
            {'field': field, 'before': before, 'after': value, 'state_before': row['state'], 'state_after': state},
            actor,
        )
    return {'version': locked.version, 'state': state, 'changed': True, 'card_sha256': _sha256(stored)}


def _empty_card() -> dict[str, Any]:
    card: dict[str, Any] = {name: {'isi': 'tidak tercantum', 'halaman': []} for name in cards.FIELDS}
    card[cards.MANUAL_PAGES] = []
    card[cards.INDIVIDUALS] = []
    return card


def approve(engine: Any, contract_id: str, *, card_sha256: str, expected_version: int, actor: str) -> dict[str, Any]:
    """Approve exactly the card the reviewer read."""
    with engine.begin() as connection:
        row = connection.execute(select(contract).where(contract.c.id == contract_id)).mappings().first()
        if row is None:
            raise LookupError(contract_id)
        if row['current_card'] is None:
            raise Invalid('This contract has no card to approve.')
        if _sha256(row['current_card']) != card_sha256:
            raise Conflict(contract_id)
        locked = _bump(connection, contract_id, expected_version, state='approved')
        _append_event(
            connection,
            contract_id,
            locked.version,
            'approved',
            {'card_sha256': card_sha256, 'state_before': row['state']},
            actor,
        )
    return {'version': locked.version, 'state': 'approved'}


def return_card(engine: Any, contract_id: str, *, reason: Any, expected_version: int, actor: str) -> dict[str, Any]:
    """Send a card back, with the reason on the event."""
    reason = _check_text(reason, 'The reason', MAX_REASON)
    with engine.begin() as connection:
        locked = _bump(connection, contract_id, expected_version, state='returned')
        _append_event(
            connection, contract_id, locked.version, 'returned', {'state_before': locked.row['state']}, actor, reason
        )
    return {'version': locked.version, 'state': 'returned'}


def set_units(engine: Any, contract_id: str, units: Any, *, expected_version: int, actor: str) -> dict[str, Any]:
    """The units this contract belongs to (D4: the basis for per-unit grants later)."""
    if not isinstance(units, list) or not all(isinstance(unit, str) and _UNIT.match(unit) for unit in units):
        raise Invalid('Units are short lowercase codes: letters, digits, "-" and "_".')
    units = sorted(set(units))
    with engine.begin() as connection:
        locked = _bump(connection, contract_id, expected_version, units=canonical_json(units))
        _append_event(
            connection,
            contract_id,
            locked.version,
            'units_set',
            {'before': json.loads(locked.row['units']), 'after': units},
            actor,
        )
    return {'version': locked.version, 'units': units}


def set_dates(
    engine: Any,
    contract_id: str,
    *,
    start: Any,
    end: Any,
    auto_renewal: Any,
    expected_version: int,
    actor: str,
) -> dict[str, Any]:
    """Legal's own dates (`dates_edited`): a later dates pass never overrides them."""
    if any(value is not None and _date(value) is None for value in (start, end)):
        raise Invalid('Dates are YYYY-MM-DD or empty.')
    if auto_renewal is not None and not isinstance(auto_renewal, bool):
        raise Invalid('Auto-renewal is true, false or empty.')
    if start and end and end < start:
        raise Invalid('The end date is before the start date.')
    with engine.begin() as connection:
        locked = _bump(
            connection, contract_id, expected_version, start_date=start, end_date=end, auto_renewal=auto_renewal
        )
        _append_event(
            connection,
            contract_id,
            locked.version,
            'dates_edited',
            {
                'start': start,
                'end': end,
                'auto_renewal': auto_renewal,
                'before': {
                    'start': locked.row['start_date'],
                    'end': locked.row['end_date'],
                    'auto_renewal': locked.row['auto_renewal'],
                },
            },
            actor,
        )
    return {'version': locked.version}


def set_parties(engine: Any, contract_id: str, names: Any, *, expected_version: int, actor: str) -> dict[str, Any]:
    """Fix the individual-party list; masking follows the new links. An approved card goes back to draft."""
    if not isinstance(names, list) or len(names) > 50:
        raise Invalid('Names are a list of at most 50.')
    cleaned: list[str] = []
    for name in names:
        name = re.sub(r'\s+', ' ', _check_text(name, 'A name', 200))
        if name.casefold() not in {kept.casefold() for kept in cleaned}:
            cleaned.append(name)
    with engine.begin() as connection:
        row = connection.execute(select(contract).where(contract.c.id == contract_id)).mappings().first()
        if row is None:
            raise LookupError(contract_id)
        card = json.loads(row['current_card']) if row['current_card'] else _empty_card()
        before_codes = sorted(
            connection.execute(
                select(party.c.code)
                .join(party_link, party_link.c.party_id == party.c.id)
                .where(party_link.c.contract_id == contract_id)
            ).scalars()
        )
        card[cards.INDIVIDUALS] = cleaned
        stored = canonical_json(card)
        state = _state_after_edit(row['state'])
        locked = _bump(connection, contract_id, expected_version, current_card=stored, state=state)
        connection.execute(delete(party_link).where(party_link.c.contract_id == contract_id))
        _link_parties(connection, contract_id, cleaned)
        after_codes = sorted(
            connection.execute(
                select(party.c.code)
                .join(party_link, party_link.c.party_id == party.c.id)
                .where(party_link.c.contract_id == contract_id)
            ).scalars()
        )
        # Codes only: the event table never carries a name.
        _append_event(
            connection,
            contract_id,
            locked.version,
            'parties_set',
            {'before': before_codes, 'after': after_codes, 'state_before': row['state'], 'state_after': state},
            actor,
        )
    return {'version': locked.version, 'state': state, 'codes': after_codes, 'card_sha256': _sha256(stored)}


def link(
    engine: Any, contract_id: str, related_id: str, *, kind: str, expected_version: int, actor: str
) -> dict[str, Any]:
    """Tie `related_id` (e.g. an addendum) to `contract_id`."""
    if kind not in LINK_KINDS:
        raise Invalid(f'The link kinds are {", ".join(LINK_KINDS)}.')
    if related_id == contract_id:
        raise Invalid('A contract cannot be linked to itself.')
    with engine.begin() as connection:
        found = connection.execute(select(contract.c.id).where(contract.c.id == related_id)).first()
        if found is None:
            raise Invalid('The related contract does not exist.')
        taken = connection.execute(
            select(contract_link.c.kind).where(
                or_(
                    and_(contract_link.c.contract_id == contract_id, contract_link.c.related_id == related_id),
                    and_(contract_link.c.contract_id == related_id, contract_link.c.related_id == contract_id),
                )
            )
        ).first()
        if taken is not None:
            raise Invalid('These two contracts are already linked.')
        locked = _bump(connection, contract_id, expected_version)
        connection.execute(
            insert(contract_link).values(
                contract_id=contract_id, related_id=related_id, kind=kind, actor=actor, created_at=_now_ms()
            )
        )
        _append_event(
            connection, contract_id, locked.version, 'link_added', {'related_id': related_id, 'kind': kind}, actor
        )
    return {'version': locked.version}


def unlink(engine: Any, contract_id: str, related_id: str, *, expected_version: int, actor: str) -> dict[str, Any]:
    with engine.begin() as connection:
        existing = connection.execute(
            select(contract_link.c.kind).where(
                contract_link.c.contract_id == contract_id, contract_link.c.related_id == related_id
            )
        ).scalar()
        if existing is None:
            raise Invalid('These two contracts are not linked.')
        locked = _bump(connection, contract_id, expected_version)
        connection.execute(
            delete(contract_link).where(
                contract_link.c.contract_id == contract_id, contract_link.c.related_id == related_id
            )
        )
        _append_event(
            connection, contract_id, locked.version, 'link_removed', {'related_id': related_id, 'kind': existing}, actor
        )
    return {'version': locked.version}
