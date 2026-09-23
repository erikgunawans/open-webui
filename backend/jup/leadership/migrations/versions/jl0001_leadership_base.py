"""Ruang Pimpinan base: the graph's first revision, creating nothing.

It exists so `jup_alembic_version` holds a position from the first boot, and every table P2 adds
arrives as a child of a revision that production has already recorded (ADR-0014).

Revision ID: jl0001
Revises:
Create Date: 2026-09-24
"""

revision = 'jl0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
