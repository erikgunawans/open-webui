"""Validate the illustrative Ruang Pimpinan dataset before any dashboard trusts it.

This module is intentionally a pure-stdlib boundary around a JSON-shaped dict. The reader
is not a normalizer: it refuses records that would make a leadership page cite unreachable
sources, mix live data into an illustrative view, or perform arithmetic over incomparable
periods. Callers keep their own objects; validation walks the structure without mutating it.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal
from typing import Any, NoReturn

# Figures travel as strings so a board number never passes through binary floating point on
# its way to a subtraction. The pattern is deliberately narrower than what `Decimal` accepts:
# `Decimal` also takes 'NaN', 'Infinity', exponents, a leading '+', surrounding whitespace and
# non-ASCII digits, and a locale string such as '1.234,5' is exactly the ambiguity (thousands
# separator or decimal point?) that must be refused rather than guessed. `[0-9]`, not `\d`,
# because `\d` matches every Unicode digit and `Decimal('١٤٤')` would happily read 144.
_DECIMAL_RE = re.compile(r'-?[0-9]+(\.[0-9]+)?')

# `date.fromisoformat` also accepts compact '20260918' and week dates on 3.11+, so the shape
# is pinned first; only a plain calendar date is a date in these records.
_ISO_DATE_RE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')

_COVERAGES = {'partial', 'complete'}
_SOURCE_VISIBILITIES = {'visible', 'hidden'}
_DOCUMENT_STATUSES = {'presented', 'draft', 'approved'}
_VERIFICATION_STATUSES = {'unverified', 'verified'}
_ACTION_STATES = {'in_progress', 'completion_submitted', 'closed', 'returned', 'cancelled'}
_DUE_PRECISIONS = {'month', 'year', 'year_range', 'date'}
_VIEW_KEYS = {'board', 'rka'}
_CONTEXT_KINDS = {'current', 'meeting', 'source_example'}
_COMPARISON_KINDS = {'same_period_budget', 'narrative_only', 'prior_period'}
_READING_UNITS = {'IDR_billion', 'percent'}
_READING_KINDS = {'actual', 'budget', 'forecast', 'scenario'}
_DEFINITION_STATUSES = {'candidate', 'approved'}
_MODULE_STATES = {'unavailable', 'suggested', 'source_example', 'available'}


class InvalidDataset(ValueError):
    """The dataset cannot be rendered without making an unsafe claim.

    The message always opens with the JSON path of the offending value, so the person fixing
    the seed is pointed at one field rather than handed a traceback.
    """


def validate_dataset(dataset: dict) -> None:
    """Refuse an invalid leadership dataset without changing the caller's object."""
    if not isinstance(dataset, dict):
        _fail('dataset', 'must be an object')

    # `type(...) is int` rather than isinstance: `True == 1` in Python, and a boolean version
    # is a writer bug, not version 1.
    schema_version = _required(dataset, 'schema_version', '')
    if type(schema_version) is not int or schema_version != 1:
        _fail('schema_version', 'must be exactly integer 1')

    # This reader serves example material only. A live or verified dataset needs provenance
    # checks this module does not perform, so it is refused here rather than rendered as if
    # an illustrative seed could vouch for it.
    _require_literal(_required(dataset, 'data_mode', ''), 'data_mode', {'illustrative'})
    _require_literal(_required(dataset, 'coverage', ''), 'coverage', _COVERAGES)
    _require_str(_required(dataset, 'dataset_id', ''), 'dataset_id')
    _require_str(_required(dataset, 'revision', ''), 'revision')

    source_ids = _validate_sources(_required(dataset, 'sources', ''))
    actions_by_id = _validate_actions(_required(dataset, 'actions', ''), source_ids)
    _validate_views(_required(dataset, 'views', ''), source_ids, actions_by_id)


def calculate_variance(card: dict) -> str | None:
    """Actual minus budget for one metric card, or None when the two are not comparable.

    Never a ratio: a percentage of a negative budget (a planned loss) reads backwards, and a
    margin already in percent would become a percent of a percent. Every dimension that makes
    two readings the same quantity must match exactly; otherwise there is no variance to show,
    and None tells the page to say so rather than print a number that means nothing.
    Assumes a card that `validate_dataset` has already accepted.
    """
    if card['comparison_kind'] != 'same_period_budget':
        return None
    primary, baseline = card['primary'], card.get('baseline')
    if baseline is None or primary['value'] is None or baseline['value'] is None:
        return None
    if primary['kind'] != 'actual' or baseline['kind'] != 'budget':
        return None
    dimensions = ('unit', 'scope_id', 'period_start', 'period_end')
    if any(primary[key] != baseline[key] for key in dimensions):
        return None
    return str(Decimal(primary['value']) - Decimal(baseline['value']))


def _validate_sources(value: Any) -> set[str]:
    sources = _require_list(value, 'sources')
    ids: set[str] = set()
    for index, source in enumerate(sources):
        path = f'sources[{index}]'
        source = _require_dict(source, path)
        source_id = _require_str(_required(source, 'id', path), f'{path}.id')
        if source_id in ids:
            _fail(f'{path}.id', f'duplicate source id {source_id!r}')
        ids.add(source_id)
        _require_str(_required(source, 'filename', path), f'{path}.filename')
        _require_date(_required(source, 'document_date', path), f'{path}.document_date')
        _validate_physical_slides(_required(source, 'physical_slides', path), f'{path}.physical_slides')
        _require_literal(_required(source, 'visibility', path), f'{path}.visibility', _SOURCE_VISIBILITIES)
        _require_literal(_required(source, 'document_status', path), f'{path}.document_status', _DOCUMENT_STATUSES)
        _require_literal(
            _required(source, 'verification_status', path),
            f'{path}.verification_status',
            _VERIFICATION_STATUSES,
        )
    return ids


def _validate_actions(value: Any, source_ids: set[str]) -> dict[str, dict[str, Any]]:
    actions = _require_list(value, 'actions')
    actions_by_id: dict[str, dict[str, Any]] = {}
    for index, action in enumerate(actions):
        path = f'actions[{index}]'
        action = _require_dict(action, path)
        action_id = _require_str(_required(action, 'id', path), f'{path}.id')
        if action_id in actions_by_id:
            _fail(f'{path}.id', f'duplicate action id {action_id!r}')
        _require_str(_required(action, 'title', path), f'{path}.title')
        _require_str(_required(action, 'owner_label', path), f'{path}.owner_label')
        _require_literal(_required(action, 'state', path), f'{path}.state', _ACTION_STATES)
        _require_date(_required(action, 'source_as_of', path), f'{path}.source_as_of')
        _validate_due(_required(action, 'due', path), f'{path}.due')
        _require_str(_required(action, 'progress_summary', path), f'{path}.progress_summary')
        _validate_source_refs(_required(action, 'source_ids', path), f'{path}.source_ids', source_ids)
        _require_literal(
            _required(action, 'verification_status', path),
            f'{path}.verification_status',
            _VERIFICATION_STATUSES,
        )
        _require_bool(_required(action, 'history_complete', path), f'{path}.history_complete')
        _require_list(_required(action, 'completion_evidence', path), f'{path}.completion_evidence')
        closure = _required(action, 'closure', path)
        if closure is not None:
            _require_dict(closure, f'{path}.closure')
        actions_by_id[action_id] = action
    return actions_by_id


def _validate_views(
    value: Any,
    source_ids: set[str],
    actions_by_id: dict[str, dict[str, Any]],
) -> None:
    views = _require_dict(value, 'views')
    if not views:
        _fail('views', 'must contain at least one view')

    metric_ids: set[str] = set()
    assumption_ids: set[str] = set()
    for view_key, view in views.items():
        view_path = f'views.{view_key}'
        if view_key not in _VIEW_KEYS:
            _fail(view_path, 'is not a supported view')
        view = _require_dict(view, view_path)
        context_source_ids = _validate_context(_required(view, 'context', view_path), view_path, view_key, source_ids)
        _validate_metrics(
            _required(view, 'metrics', view_path),
            f'{view_path}.metrics',
            source_ids,
            context_source_ids,
            metric_ids,
        )
        _validate_action_refs(
            _required(view, 'action_ids', view_path),
            f'{view_path}.action_ids',
            actions_by_id,
            context_source_ids,
        )
        _validate_assumptions(
            _required(view, 'assumptions', view_path),
            f'{view_path}.assumptions',
            source_ids,
            actions_by_id,
            context_source_ids,
            assumption_ids,
        )
        _validate_module_states(_required(view, 'module_states', view_path), f'{view_path}.module_states')


def _validate_context(value: Any, view_path: str, view_key: str, source_ids: set[str]) -> set[str]:
    path = f'{view_path}.context'
    context = _require_dict(value, path)
    _require_str(_required(context, 'id', path), f'{path}.id')
    _require_literal(_required(context, 'kind', path), f'{path}.kind', _CONTEXT_KINDS)
    workspace = _require_str(_required(context, 'workspace', path), f'{path}.workspace')
    if workspace != view_key:
        _fail(f'{path}.workspace', f'must equal {view_key!r}')
    _require_str(_required(context, 'scope_id', path), f'{path}.scope_id')
    period_start = _require_date(_required(context, 'period_start', path), f'{path}.period_start')
    period_end = _require_date(_required(context, 'period_end', path), f'{path}.period_end')
    _require_ordered_dates(period_start, period_end, f'{path}.period_start')
    _require_str(_required(context, 'label', path), f'{path}.label')
    _require_str(_required(context, 'report_status', path), f'{path}.report_status')
    return _validate_source_refs(_required(context, 'source_ids', path), f'{path}.source_ids', source_ids)


def _validate_metrics(
    value: Any,
    path: str,
    source_ids: set[str],
    context_source_ids: set[str],
    metric_ids: set[str],
) -> None:
    metrics = _require_list(value, path)
    for index, metric in enumerate(metrics):
        metric_path = f'{path}[{index}]'
        metric = _require_dict(metric, metric_path)
        metric_id = _require_str(_required(metric, 'id', metric_path), f'{metric_path}.id')
        if metric_id in metric_ids:
            _fail(f'{metric_path}.id', f'duplicate metric id {metric_id!r}')
        metric_ids.add(metric_id)
        _require_str(_required(metric, 'label', metric_path), f'{metric_path}.label')
        _validate_reading(_required(metric, 'primary', metric_path), f'{metric_path}.primary')
        baseline = _required(metric, 'baseline', metric_path)
        if baseline is not None:
            _validate_reading(baseline, f'{metric_path}.baseline')
        _require_literal(
            _required(metric, 'comparison_kind', metric_path),
            f'{metric_path}.comparison_kind',
            _COMPARISON_KINDS,
        )
        comparison_note = _required(metric, 'comparison_note', metric_path)
        if comparison_note is not None:
            _require_str(comparison_note, f'{metric_path}.comparison_note')
        _require_literal(
            _required(metric, 'verification_status', metric_path),
            f'{metric_path}.verification_status',
            _VERIFICATION_STATUSES,
        )
        _validate_source_refs(
            _required(metric, 'source_ids', metric_path),
            f'{metric_path}.source_ids',
            source_ids,
            context_source_ids,
        )


def _validate_reading(value: Any, path: str) -> None:
    reading = _require_dict(value, path)
    decimal_value = _required(reading, 'value', path)
    if decimal_value is None:
        _require_str(_required(reading, 'missing_reason', path), f'{path}.missing_reason')
    else:
        _require_decimal_str(decimal_value, f'{path}.value')
        missing_reason = _required(reading, 'missing_reason', path)
        if missing_reason is not None:
            _require_str(missing_reason, f'{path}.missing_reason')
    _require_literal(_required(reading, 'unit', path), f'{path}.unit', _READING_UNITS)
    _require_literal(_required(reading, 'kind', path), f'{path}.kind', _READING_KINDS)
    period_start = _require_date(_required(reading, 'period_start', path), f'{path}.period_start')
    period_end = _require_date(_required(reading, 'period_end', path), f'{path}.period_end')
    _require_ordered_dates(period_start, period_end, f'{path}.period_start')
    _require_str(_required(reading, 'scope_id', path), f'{path}.scope_id')
    _require_literal(_required(reading, 'definition_status', path), f'{path}.definition_status', _DEFINITION_STATUSES)


def _validate_assumptions(
    value: Any,
    path: str,
    source_ids: set[str],
    actions_by_id: dict[str, dict[str, Any]],
    context_source_ids: set[str],
    assumption_ids: set[str],
) -> None:
    assumptions = _require_list(value, path)
    for index, assumption in enumerate(assumptions):
        assumption_path = f'{path}[{index}]'
        assumption = _require_dict(assumption, assumption_path)
        assumption_id = _require_str(_required(assumption, 'id', assumption_path), f'{assumption_path}.id')
        if assumption_id in assumption_ids:
            _fail(f'{assumption_path}.id', f'duplicate assumption id {assumption_id!r}')
        assumption_ids.add(assumption_id)
        _require_str(_required(assumption, 'label', assumption_path), f'{assumption_path}.label')
        _require_str(_required(assumption, 'target_note', assumption_path), f'{assumption_path}.target_note')
        _require_str(_required(assumption, 'watch_note', assumption_path), f'{assumption_path}.watch_note')
        _validate_source_refs(
            _required(assumption, 'source_ids', assumption_path),
            f'{assumption_path}.source_ids',
            source_ids,
            context_source_ids,
        )
        _validate_action_refs(
            _required(assumption, 'action_ids', assumption_path),
            f'{assumption_path}.action_ids',
            actions_by_id,
            context_source_ids,
        )
        _require_literal(
            _required(assumption, 'verification_status', assumption_path),
            f'{assumption_path}.verification_status',
            _VERIFICATION_STATUSES,
        )


def _validate_module_states(value: Any, path: str) -> None:
    states = _require_list(value, path)
    ids: set[str] = set()
    for index, module_state in enumerate(states):
        state_path = f'{path}[{index}]'
        module_state = _require_dict(module_state, state_path)
        state_id = _require_str(_required(module_state, 'id', state_path), f'{state_path}.id')
        if state_id in ids:
            _fail(f'{state_path}.id', f'duplicate module state id {state_id!r}')
        ids.add(state_id)
        _require_str(_required(module_state, 'label', state_path), f'{state_path}.label')
        _require_literal(_required(module_state, 'state', state_path), f'{state_path}.state', _MODULE_STATES)
        _require_str(_required(module_state, 'reason', state_path), f'{state_path}.reason')


def _validate_due(value: Any, path: str) -> None:
    due = _require_dict(value, path)
    precision = _require_literal(_required(due, 'precision', path), f'{path}.precision', _DUE_PRECISIONS)
    _require_str(_required(due, 'label', path), f'{path}.label')
    if precision == 'month':
        _require_int(_required(due, 'year', path), f'{path}.year')
        month = _require_int(_required(due, 'month', path), f'{path}.month')
        if not 1 <= month <= 12:
            _fail(f'{path}.month', 'must be between 1 and 12')
    elif precision == 'year':
        _require_int(_required(due, 'year', path), f'{path}.year')
    elif precision == 'year_range':
        start_year = _require_int(_required(due, 'start_year', path), f'{path}.start_year')
        end_year = _require_int(_required(due, 'end_year', path), f'{path}.end_year')
        if start_year > end_year:
            _fail(f'{path}.start_year', 'must be before or equal to end_year')
    elif precision == 'date':
        _require_date(_required(due, 'date', path), f'{path}.date')


def _validate_physical_slides(value: Any, path: str) -> None:
    slides = _require_list(value, path)
    if not slides:
        _fail(path, 'must not be empty')
    for index, slide in enumerate(slides):
        slide_path = f'{path}[{index}]'
        if _require_int(slide, slide_path) <= 0:
            _fail(slide_path, 'must be a positive integer')


def _validate_source_refs(
    value: Any,
    path: str,
    source_ids: set[str],
    context_source_ids: set[str] | None = None,
) -> set[str]:
    refs = _require_list(value, path)
    resolved: set[str] = set()
    for index, ref in enumerate(refs):
        ref_path = f'{path}[{index}]'
        source_id = _require_str(ref, ref_path)
        if source_id not in source_ids:
            _fail(ref_path, f'unknown source id {source_id!r}')
        if context_source_ids is not None and source_id not in context_source_ids:
            _fail(ref_path, f'source id {source_id!r} is outside this view context')
        resolved.add(source_id)
    return resolved


def _validate_action_refs(
    value: Any,
    path: str,
    actions_by_id: dict[str, dict[str, Any]],
    context_source_ids: set[str],
) -> None:
    action_ids = _require_list(value, path)
    for index, ref in enumerate(action_ids):
        ref_path = f'{path}[{index}]'
        action_id = _require_str(ref, ref_path)
        action = actions_by_id.get(action_id)
        if action is None:
            _fail(ref_path, f'unknown action id {action_id!r}')
        # Reachability: the API will refuse to show a source outside the view's own list, so an
        # action whose evidence lives elsewhere would render with a citation nobody can open.
        # The action's `source_ids` were already type-checked by `_validate_actions`.
        for source_id in action['source_ids']:
            if source_id not in context_source_ids:
                _fail(ref_path, f'action source id {source_id!r} is outside this view context')


def _required(record: dict[Any, Any], key: str, path: str) -> Any:
    if key not in record:
        _fail(_join(path, key), 'is required')
    return record[key]


def _require_dict(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, 'must be an object')
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, 'must be a list')
    return value


def _require_bool(value: Any, path: str) -> bool:
    if type(value) is not bool:
        _fail(path, 'must be a boolean')
    return value


def _require_int(value: Any, path: str) -> int:
    if type(value) is not int:
        _fail(path, 'must be an integer')
    return value


def _require_str(value: Any, path: str) -> str:
    if not isinstance(value, str):
        _fail(path, 'must be a string')
    if value == '':
        _fail(path, 'must not be empty')
    return value


def _require_literal(value: Any, path: str, allowed: set[str]) -> str:
    value = _require_str(value, path)
    if value not in allowed:
        _fail(path, f'must be one of {sorted(allowed)!r}')
    return value


def _require_date(value: Any, path: str) -> dt.date:
    value = _require_str(value, path)
    if not _ISO_DATE_RE.fullmatch(value):
        _fail(path, 'must be an ISO date in YYYY-MM-DD form')
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidDataset(f'{path}: must be a valid ISO date') from exc


def _require_ordered_dates(period_start: dt.date, period_end: dt.date, path: str) -> None:
    if period_start > period_end:
        _fail(path, 'must be before or equal to period_end')


def _require_decimal_str(value: Any, path: str) -> str:
    if not isinstance(value, str) or not _DECIMAL_RE.fullmatch(value):
        _fail(path, 'must be a finite decimal string')
    if not Decimal(value).is_finite():
        _fail(path, 'must be a finite decimal string')
    return value


def _join(path: str, key: str) -> str:
    if not path:
        return key
    return f'{path}.{key}'


def _fail(path: str, message: str) -> NoReturn:
    raise InvalidDataset(f'{path}: {message}')
