"""Alembic environment for the Mapping tables (ADR-0014 pattern).

Only `jup.channel_links.migrate.run_channel_link_migrations` runs this. It passes a live connection on the
vendor engine, and the graph records its position in `jup_channel_links_alembic_version`, never in the
vendor's `alembic_version` or the other fork graphs' tables. Offline mode is not supported.
"""

from alembic import context

from jup.channel_links.migrate import VERSION_TABLE

if context.is_offline_mode():
    raise RuntimeError('Channel Mapping migrations run online only, through jup.channel_links.migrate')

connection = context.config.attributes.get('connection')
if connection is None:
    raise RuntimeError('Channel Mapping migrations need a connection from jup.channel_links.migrate')

context.configure(connection=connection, target_metadata=None, version_table=VERSION_TABLE)
with context.begin_transaction():
    context.run_migrations()
