"""The Mapping tables: linked numbers, live Link Codes, and wrong-code attempts (E9.1, #102).

Written out rather than taken from `jup.channel_links.models`, so a later model change cannot rewrite
what this revision created.

Revision ID: jw0001
Revises:
Create Date: 2026-10-04
"""

import sqlalchemy as sa
from alembic import op

revision = 'jw0001'
down_revision = None
branch_labels = None
depends_on = None

_HASH = 64
_USER = 255


def upgrade() -> None:
    op.create_table(
        'jup_channel_link',
        sa.Column('channel', sa.String(16), primary_key=True),
        sa.Column('identity_hash', sa.String(_HASH), primary_key=True),
        sa.Column('user_id', sa.String(_USER), nullable=False),
        sa.Column('hint', sa.String(8), nullable=False),
        sa.Column('created_at', sa.BigInteger, nullable=False),
        sa.UniqueConstraint('channel', 'user_id', name='uq_jup_channel_link_user'),
    )
    op.create_table(
        'jup_channel_link_code',
        sa.Column('code_hash', sa.String(_HASH), primary_key=True),
        sa.Column('user_id', sa.String(_USER), nullable=False, unique=True),
        sa.Column('expires_at', sa.BigInteger, nullable=False),
        sa.Column('used_at', sa.BigInteger, nullable=True),
    )
    op.create_table(
        'jup_channel_link_failure',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('identity_hash', sa.String(_HASH), nullable=False),
        sa.Column('at', sa.BigInteger, nullable=False),
    )
    op.create_index('ix_jup_channel_link_failure_identity_hash', 'jup_channel_link_failure', ['identity_hash'])


def downgrade() -> None:
    op.drop_index('ix_jup_channel_link_failure_identity_hash', 'jup_channel_link_failure')
    op.drop_table('jup_channel_link_failure')
    op.drop_table('jup_channel_link_code')
    op.drop_table('jup_channel_link')
