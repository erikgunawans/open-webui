"""Alembic environment for the contract tables (ADR-0014 pattern).

Only `jup.contracts.migrate.run_contract_migrations` runs this. It passes a live connection on the
vendor engine, and the graph records its position in `jup_contracts_alembic_version`, never in the
vendor's `alembic_version` or Ruang Pimpinan's `jup_alembic_version`. Offline mode is not supported.
"""

from alembic import context

from jup.contracts.migrate import VERSION_TABLE

if context.is_offline_mode():
    raise RuntimeError('Contract migrations run online only, through jup.contracts.migrate')

connection = context.config.attributes.get('connection')
if connection is None:
    raise RuntimeError('Contract migrations need a connection from jup.contracts.migrate')

context.configure(connection=connection, target_metadata=None, version_table=VERSION_TABLE)
with context.begin_transaction():
    context.run_migrations()
