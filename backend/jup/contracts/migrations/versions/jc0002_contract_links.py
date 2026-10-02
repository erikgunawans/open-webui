"""Contract links: an addendum (or other related document) tied to the contract it amends.

Written out rather than taken from `jup.contracts.models`, like jc0001.

Revision ID: jc0002
Revises: jc0001
Create Date: 2026-10-02
"""

import sqlalchemy as sa
from alembic import op

revision = 'jc0002'
down_revision = 'jc0001'
branch_labels = None
depends_on = None

_ID = 64
_USER = 255


def upgrade() -> None:
    op.create_table(
        'jup_contract_link',
        sa.Column('contract_id', sa.String(_ID), sa.ForeignKey('jup_contract.id'), primary_key=True),
        sa.Column('related_id', sa.String(_ID), sa.ForeignKey('jup_contract.id'), primary_key=True),
        sa.Column('kind', sa.String(32), nullable=False),
        sa.Column('actor', sa.String(_USER), nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('jup_contract_link')
