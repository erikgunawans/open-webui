"""Import a drafting run's cards from the legal-kb bucket, mounted read-only on the service.

`root` is the mount (`JUP_CONTRACTS_DIR`, `/srv/legal-kb` in production); a run's cards are
`<root>/<run>/cards/<n>.json`, written by `deploy/gcp/legal-kb/run.ts`, and its dates are
`<root>/<run>/dates/<n>.json`, written by `dates.ts`. Nothing is copied out of the
bucket except into the Jakarta database, and the log carries counts only.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from jup.contracts import repository

log = logging.getLogger(__name__)

_RUN = re.compile(r'^[a-z0-9][a-z0-9_-]{0,31}$')


def import_run(engine: Any, root: Path | str, run: str, *, actor: str) -> dict[str, int]:
    """Store every card of `run`. Returns counts per outcome; unreadable files are counted, not fatal."""
    if not _RUN.match(run):
        raise ValueError(f'{run!r} is not a run name')
    directory = Path(root) / run / 'cards'
    counts = {'created': 0, 'updated': 0, 'unchanged': 0, 'redraft_held': 0, 'unreadable': 0, 'dated': 0}
    for path in sorted(directory.glob('*.json')):
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(record, dict) or not record.get('itemId') or not record.get('n'):
                raise ValueError('not a card record')
        except (OSError, ValueError):
            counts['unreadable'] += 1
            continue
        counts[repository.import_record(engine, record, run=run, actor=actor)] += 1
    # Structured dates from the dates pass (`dates.ts`), when it has run. A missing or broken file is
    # simply no dates; Legal's own dates are never overwritten.
    for path in sorted((Path(root) / run / 'dates').glob('*.json')):
        try:
            dates = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(dates, dict) and repository.apply_dates_record(
            engine, run=run, number=path.stem, record=dates, actor=actor
        ):
            counts['dated'] += 1
    log.info('contract import run=%s %s', run, counts)
    return counts
