"""The contract tables migrate on their own alembic graph, like Ruang Pimpinan's (ADR-0014).

Own versions directory, own version table (`jup_contracts_alembic_version`), the vendor's engine, run
after the vendor upgrade. Separate from the leadership graph on purpose: a broken contract migration
disables the contract knowledge base and nothing else — not chat, and not Ruang Pimpinan.

A failure is logged, `schema_ready()` answers False, and the contract tool and routes refuse until the
next successful boot.
"""

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / 'migrations'
VERSION_TABLE = 'jup_contracts_alembic_version'

_schema_ready = False


def schema_ready() -> bool:
    """True once this process has brought the contract schema to its head."""
    return _schema_ready


def run_contract_migrations(engine: Any) -> bool:
    """Upgrade the contract graph to head on `engine`; never raises.

    Returns:
        True when the schema is at head, False when the upgrade failed (logged with its cause).
    """
    global _schema_ready
    try:
        from alembic import command
        from alembic.config import Config

        config = Config()
        config.set_main_option('script_location', str(MIGRATIONS_DIR))
        config.set_main_option('path_separator', 'os')
        with engine.begin() as connection:
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
    except Exception:
        log.exception('Contract KB migrations failed; contracts stay unavailable and the app keeps running')
        _schema_ready = False
        return False
    _schema_ready = True
    return True
