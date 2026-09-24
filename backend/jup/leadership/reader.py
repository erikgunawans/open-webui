"""The shared read path for Ruang Pimpinan: one dataset, two views, no copies.

Both the human API and, from P3, the assistant's tools read through here, so the two cannot
disagree about a value, an id or a source. Three rules live in this module:

- A view serves its actions by resolving `action_ids` against one `actions` list. An action cited
  by the Board and the RKA view is the same record in both, never two records that drift.
- Each metric carries `variance` from `records.calculate_variance`, which answers only for a
  like-for-like comparison and is `None` otherwise. A client never computes it.
- A source is returned only through a view that declares it in `context.source_ids`. Knowing an
  id is not access; the other view's citations stay behind the other view's grant.

Loading refuses anything it cannot fully validate. A malformed dataset must surface as
unavailable, never as a clean report with holes in it.

**Where a view's actions come from (P2 T7)** is one server setting, never a request's choice, and
every overview says which (`actions_source`):

- `sample` (the default, P1's behaviour): the dataset's own actions, as labelled as before.
- `records`: the action register in the records store (ADR-0014). The Board view shows the whole
  register; the RKA view shows the recorded actions its dataset section references, since nothing
  else says which actions belong to the RKA. An empty register is served empty with its reason;
  it never falls back to the sample.

Metrics, context and assumptions stay the dataset's in both modes, under the dataset's own
`data_mode` label, until an import replaces them (ADR-0014).
"""

import copy
import datetime as dt
import json
from pathlib import Path
from typing import Any

from jup.leadership.records import InvalidDataset, calculate_variance, validate_dataset


class DatasetUnavailable(Exception):
    """The dataset could not be read or trusted.

    The message is safe to serve: it names what went wrong in general terms and never the path.
    """


def load_dataset(path: Path) -> dict[str, Any]:
    """Read and validate the dataset at `path`, or raise `DatasetUnavailable`."""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except OSError as error:
        raise DatasetUnavailable('The leadership dataset could not be read.') from error
    except ValueError as error:
        raise DatasetUnavailable('The leadership dataset is not valid JSON.') from error
    if not isinstance(data, dict):
        raise DatasetUnavailable('The leadership dataset is malformed.')
    try:
        validate_dataset(data)
    except InvalidDataset as error:
        raise DatasetUnavailable('The leadership dataset failed validation.') from error
    return data


ACTIONS_SOURCES = ('sample', 'records')


def read_overview(dataset: dict[str, Any], view: str, recorded: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Everything one view shows, as a copy the caller may change freely.

    With `recorded` (the register from `recorded_actions`), the view's actions are the records';
    without it, they are the dataset's sample actions. The answer says which.

    Raises `KeyError` for a view the dataset does not have; the router has already refused any
    view name outside the supported set, so reaching that here is a dataset shape problem.
    """
    section = dataset['views'][view]
    if recorded is None:
        by_id = {action['id']: action for action in dataset['actions']}
        view_actions = [copy.deepcopy(by_id[action_id]) for action_id in section['action_ids']]
        source, note = 'sample', None
    else:
        referenced = set(section['action_ids'])
        view_actions = [copy.deepcopy(action) for action in recorded if view == 'board' or action['id'] in referenced]
        source = 'records'
        note = None if view_actions else 'No action is recorded for this view yet.'
    metrics = []
    for metric in section['metrics']:
        served = copy.deepcopy(metric)
        served['variance'] = calculate_variance(metric)
        metrics.append(served)
    return {
        'schema_version': dataset['schema_version'],
        'data_mode': dataset['data_mode'],
        'coverage': dataset['coverage'],
        'revision': dataset['revision'],
        'context': copy.deepcopy(section['context']),
        'metrics': metrics,
        'actions': view_actions,
        'actions_source': source,
        'actions_note': note,
        'assumptions': copy.deepcopy(section['assumptions']),
        'module_states': copy.deepcopy(section['module_states']),
    }


def read_source(dataset: dict[str, Any], view: str, source_id: str) -> dict[str, Any] | None:
    """The citation for `source_id` if `view` declares it, else `None`.

    The record is citation metadata: a filename, a date and physical slide numbers. It is never a
    path the server will open.
    """
    if source_id not in dataset['views'][view]['context']['source_ids']:
        return None
    for source in dataset['sources']:
        if source['id'] == source_id:
            return copy.deepcopy(source)
    return None


# --- the recorded register (P2 T7) ----------------------------------------------------------

_MONTHS_ID = (
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
    'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember',
)  # fmt: skip


def due_view(value: str | None, precision: str | None) -> dict[str, Any] | None:
    """A recorded due date in the dataset's shape, labelled in Indonesian. None when none is known."""
    if value is None or precision is None:
        return None
    if precision == 'date':
        day = dt.date.fromisoformat(value)
        return {'precision': 'date', 'label': f'{day.day} {_MONTHS_ID[day.month - 1]} {day.year}', 'date': value}
    if precision == 'month':
        year, month = int(value[:4]), int(value[5:7])
        return {'precision': 'month', 'label': f'{_MONTHS_ID[month - 1]} {year}', 'year': year, 'month': month}
    if precision == 'year':
        return {'precision': 'year', 'label': value, 'year': int(value)}
    start, end = (int(part) for part in value.split('/'))
    return {'precision': 'year_range', 'label': f'{start}–{end}', 'start_year': start, 'end_year': end}


def recorded_actions(connection: Any) -> list[dict[str, Any]]:
    """The records store's register, oldest first, in the dataset's action shape plus the record itself.

    `verification_status` is `verified` only for an action an import reviewer confirmed (it has a
    reviewed external reference). `history_complete` is true: the event log is the whole history.
    """
    from sqlalchemy import func, select

    from jup.leadership.actions import REPORTING_TZ
    from jup.leadership.models import action, action_event, closure_request, evidence, external_ref

    rows = list(connection.execute(select(action).order_by(action.c.created_at, action.c.id)).mappings())
    confirmed = set(connection.execute(select(external_ref.c.action_id).distinct()).scalars())
    progress: dict[str, str] = {}
    for event in connection.execute(
        select(action_event.c.action_id, action_event.c.payload)
        .where(action_event.c.kind == 'progress_submitted')
        .order_by(action_event.c.version)
    ).mappings():
        progress[event['action_id']] = json.loads(event['payload'])['data']['narrative']
    evidence_counts = dict(
        connection.execute(select(evidence.c.action_id, func.count()).group_by(evidence.c.action_id)).all()
    )
    requests: dict[str, dict[str, Any]] = {}
    for request in connection.execute(select(closure_request).order_by(closure_request.c.created_at)).mappings():
        requests[request['action_id']] = request

    register = []
    for row in rows:
        request = requests.get(row['id'])
        register.append(
            {
                'id': row['id'],
                'title': row['title'],
                'owner_label': row['pic_label'],
                'state': row['state'],
                'source_as_of': dt.datetime.fromtimestamp(row['updated_at'] / 1000, REPORTING_TZ).date().isoformat(),
                'due': due_view(row['current_due'], row['current_due_precision']),
                'progress_summary': progress.get(row['id']),
                'source_ids': [],
                'verification_status': 'verified' if row['id'] in confirmed else 'unverified',
                'history_complete': True,
                'completion_evidence': [],
                'closure': None
                if request is None
                else {
                    'request_id': request['id'],
                    'kind': request['closure_kind'],
                    'status': request['status'],
                    'replacement_action_id': request['replacement_action_id'],
                },
                'record': {
                    'version': row['version'],
                    'pic_user_id': row['pic_user_id'],
                    'original_due': due_view(row['original_due'], row['original_due_precision']),
                    'evidence_revisions': evidence_counts.get(row['id'], 0),
                },
            }
        )
    return register
