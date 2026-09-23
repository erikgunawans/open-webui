"""Alembic environment for Ruang Pimpinan's tables (ADR-0014).

Only `jup.leadership.migrate.run_leadership_migrations` runs this. It passes a live connection on
the vendor engine, and the graph records its position in `jup_alembic_version`, never in the
vendor's `alembic_version`. Offline (SQL script) mode is not supported.
"""

from alembic import context

from jup.leadership.migrate import VERSION_TABLE

if context.is_offline_mode():
    raise RuntimeError('Ruang Pimpinan migrations run online only, through jup.leadership.migrate')

connection = context.config.attributes.get('connection')
if connection is None:
    raise RuntimeError('Ruang Pimpinan migrations need a connection from jup.leadership.migrate')

context.configure(connection=connection, target_metadata=None, version_table=VERSION_TABLE)
with context.begin_transaction():
    context.run_migrations()
