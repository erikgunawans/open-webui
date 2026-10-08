"""Rapat Direksi meetings on the server: the Corsec's Notulen, one row per meeting (D27 step 1).

The schema is written out here rather than taken from `jup.leadership.models`, so this revision
stays what production ran even after the models move on. The repository tests hold the migrated
schema and the models to the same columns, nullability, keys and unique constraints (ADR-0014).

Revision ID: jl0003
Revises: jl0002
Create Date: 2026-10-08
"""

import sqlalchemy as sa
from alembic import op

revision = 'jl0003'
down_revision = 'jl0002'
branch_labels = None
depends_on = None

_ID = 64
_USER = 255


def upgrade() -> None:
    op.create_table(
        'leadership_meeting',
        sa.Column('id', sa.String(_ID), primary_key=True),
        sa.Column('owner_user_id', sa.String(_USER), nullable=False),
        sa.Column('document', sa.Text, nullable=False),
        sa.Column('revision', sa.Integer, nullable=False),
        sa.Column('closed_at', sa.BigInteger, nullable=True),
        sa.Column('reopenings', sa.Text, nullable=False),
        sa.Column('created_by', sa.String(_USER), nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
        sa.Column('updated_by', sa.String(_USER), nullable=False),
        sa.Column('updated_at', sa.BigInteger, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('leadership_meeting')
