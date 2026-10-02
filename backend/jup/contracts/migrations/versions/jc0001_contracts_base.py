"""Contract KB base: contracts, their append-only events, and individual parties with global codes.

The schema is written out here rather than taken from `jup.contracts.models`, so this revision stays
what production ran even after the models move on. `tests/test_contract_repository.py` holds the
migrated schema and the models to the same columns, nullability, keys and unique constraints.

Revision ID: jc0001
Revises:
Create Date: 2026-10-02
"""

import sqlalchemy as sa
from alembic import op

revision = 'jc0001'
down_revision = None
branch_labels = None
depends_on = None

_ID = 64
_USER = 255


def _id(name: str = 'id', *args, **kwargs) -> sa.Column:
    return sa.Column(name, sa.String(_ID), *args, **kwargs)


def upgrade() -> None:
    op.create_table(
        'jup_contract',
        _id(primary_key=True),
        sa.Column('source_item_id', sa.String(_USER), nullable=False, unique=True),
        sa.Column('run', sa.String(32), nullable=False),
        sa.Column('number', sa.String(16), nullable=False),
        sa.Column('source_object', sa.Text, nullable=False),
        sa.Column('source_web_url', sa.Text, nullable=True),
        sa.Column('source_path', sa.Text, nullable=False),
        sa.Column('source_file', sa.Text, nullable=False),
        sa.Column('page_count', sa.Integer, nullable=False),
        sa.Column('low_confidence_pages', sa.Text, nullable=False),
        sa.Column('manual_check_pages', sa.Text, nullable=False),
        sa.Column('model', sa.String(64), nullable=True),
        sa.Column('partner', sa.Text, nullable=True),
        sa.Column('contract_number', sa.Text, nullable=True),
        sa.Column('title', sa.Text, nullable=True),
        sa.Column('doc_type', sa.Text, nullable=True),
        sa.Column('draft_card', sa.Text, nullable=True),
        sa.Column('draft_sha256', sa.String(64), nullable=True),
        sa.Column('current_card', sa.Text, nullable=True),
        sa.Column('state', sa.String(16), nullable=False),
        sa.Column('start_date', sa.String(10), nullable=True),
        sa.Column('end_date', sa.String(10), nullable=True),
        sa.Column('auto_renewal', sa.Boolean, nullable=True),
        sa.Column('units', sa.Text, nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
        sa.Column('updated_at', sa.BigInteger, nullable=False),
        sa.UniqueConstraint('run', 'number', name='uq_jup_contract_run_number'),
    )
    op.create_table(
        'jup_contract_event',
        _id(primary_key=True),
        _id('contract_id', sa.ForeignKey('jup_contract.id'), nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('kind', sa.String(64), nullable=False),
        sa.Column('payload', sa.Text, nullable=False),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('actor', sa.String(_USER), nullable=False),
        sa.Column('at', sa.BigInteger, nullable=False),
        sa.UniqueConstraint('contract_id', 'version', name='uq_jup_contract_event_version'),
    )
    op.create_table(
        'jup_contract_party',
        _id(primary_key=True),
        sa.Column('code', sa.String(32), nullable=False, unique=True),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('name_key', sa.String(_USER), nullable=False, unique=True),
        sa.Column('created_at', sa.BigInteger, nullable=False),
    )
    op.create_table(
        'jup_contract_party_link',
        _id('contract_id', sa.ForeignKey('jup_contract.id'), primary_key=True),
        _id('party_id', sa.ForeignKey('jup_contract_party.id'), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table('jup_contract_party_link')
    op.drop_table('jup_contract_party')
    op.drop_table('jup_contract_event')
    op.drop_table('jup_contract')
