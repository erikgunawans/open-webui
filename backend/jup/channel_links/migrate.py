"""The Mapping tables migrate on their own alembic graph, like the contract tables (ADR-0014).

Own versions directory, own version table (`jup_channel_links_alembic_version`), the vendor's engine, run
after the vendor upgrade. Separate from the leadership graph on purpose: a broken Mapping migration
disables WhatsApp linking and nothing else.

A failure is logged, `schema_ready()` answers False, and the link routes and the middleware refuse until the
next successful boot.
"""

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent / 'migrations'
VERSION_TABLE = 'jup_channel_links_alembic_version'

_schema_ready = False


def schema_ready() -> bool:
    """True once this process has brought the Mapping schema to its head."""
    return _schema_ready


def run_channel_link_migrations(engine: Any) -> bool:
    """Upgrade the Mapping graph to head on `engine`; never raises.

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
        log.exception('Channel Mapping migrations failed; WhatsApp linking stays unavailable and the app keeps running')
        _schema_ready = False
        return False
    _schema_ready = True
    return True
