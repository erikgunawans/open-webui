"""Ruang Pimpinan's own tables migrate on their own alembic graph (ADR-0014).

The vendor graph runs `upgrade head` at config import, and a fork revision placed in it has to be
re-pointed, and the deployed database re-stamped, at every quarterly rebase (ADR-0007). This graph
never shares a head with upstream: it has its own versions directory and its own version table,
`jup_alembic_version`, in the same database.

It runs on the vendor's engine, so SQLCipher, IAM token auth and SSL parameters behave exactly as
they do for the vendor tables, and it runs after the vendor upgrade because `main.py` calls it
after importing the config.

A failure here is contained on purpose. The vendor treats a migration error as fatal, which is
right for the tables chat depends on; a broken leadership migration must not take chat down with
it. The runner logs the failure, `schema_ready()` answers False, and the section's workflow routes
refuse with 503 until the next successful boot.
"""

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / 'migrations'
VERSION_TABLE = 'jup_alembic_version'

_schema_ready = False


def schema_ready() -> bool:
    """True once this process has brought the leadership schema to its head."""
    return _schema_ready


def run_leadership_migrations(engine: Any) -> bool:
    """Upgrade the leadership graph to head on `engine`; never raises.

    Returns:
        True when the schema is at head, False when the upgrade failed (logged with its cause).
    """
    global _schema_ready
    try:
        from alembic import command
        from alembic.config import Config

        config = Config()
        config.set_main_option('script_location', str(MIGRATIONS_DIR))
        with engine.begin() as connection:
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
    except Exception:
        log.exception('Ruang Pimpinan migrations failed; the section stays unavailable and the app keeps running')
        _schema_ready = False
        return False
    _schema_ready = True
    return True
