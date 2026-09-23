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
"""

import copy
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


def read_overview(dataset: dict[str, Any], view: str) -> dict[str, Any]:
    """Everything one view shows, as a copy the caller may change freely.

    Raises `KeyError` for a view the dataset does not have; the router has already refused any
    view name outside the supported set, so reaching that here is a dataset shape problem.
    """
    section = dataset['views'][view]
    actions = {action['id']: action for action in dataset['actions']}
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
        'actions': [copy.deepcopy(actions[action_id]) for action_id in section['action_ids']],
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
