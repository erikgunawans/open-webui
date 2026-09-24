"""Ruang Pimpinan P2 records: actions and their events, evidence, closure, snapshots, baselines, imports.

The schema is written out here rather than taken from `jup.leadership.models`, so this revision
stays what production ran even after the models move on. The repository tests hold the migrated
schema and the models to the same columns, nullability, keys and unique constraints (ADR-0014).

Revision ID: jl0002
Revises: jl0001
Create Date: 2026-09-24
"""

import sqlalchemy as sa
from alembic import op

revision = 'jl0002'
down_revision = 'jl0001'
branch_labels = None
depends_on = None

_ID = 64
_USER = 255


def _id(name: str = 'id', *args, **kwargs) -> sa.Column:
    return sa.Column(name, sa.String(_ID), *args, **kwargs)


def _fk(name: str, target: str, nullable: bool = False) -> sa.Column:
    return _id(name, sa.ForeignKey(target), nullable=nullable)


def _user(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(_USER), nullable=nullable)


def _ms(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.BigInteger, nullable=nullable)


def upgrade() -> None:
    op.create_table(
        'leadership_action',
        _id(primary_key=True),
        sa.Column('title', sa.Text, nullable=False),
        _user('pic_user_id', nullable=True),
        sa.Column('pic_label', sa.Text, nullable=False),
        sa.Column('state', sa.String(32), nullable=False),
        sa.Column('original_due', sa.String(32), nullable=True),
        sa.Column('original_due_precision', sa.String(16), nullable=True),
        sa.Column('current_due', sa.String(32), nullable=True),
        sa.Column('current_due_precision', sa.String(16), nullable=True),
        sa.Column('version', sa.Integer, nullable=False),
        _user('created_by'),
        _ms('created_at'),
        _ms('updated_at'),
    )
    op.create_table(
        'leadership_action_event',
        _id(primary_key=True),
        _fk('action_id', 'leadership_action.id'),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('kind', sa.String(64), nullable=False),
        sa.Column('payload', sa.Text, nullable=False),
        sa.Column('reason', sa.Text, nullable=True),
        _user('author_user_id'),
        _ms('created_at'),
        sa.Column('idempotency_key', sa.String(128), nullable=True),
        sa.UniqueConstraint('action_id', 'version', name='uq_leadership_action_event_version'),
        sa.UniqueConstraint('action_id', 'idempotency_key', name='uq_leadership_action_event_idempotency'),
    )
    op.create_table(
        'leadership_evidence',
        _id(primary_key=True),
        _fk('action_id', 'leadership_action.id'),
        sa.Column('revision', sa.Integer, nullable=False),
        _fk('event_id', 'leadership_action_event.id'),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('storage_key', sa.Text, nullable=True),
        sa.Column('url', sa.Text, nullable=True),
        sa.Column('filename', sa.Text, nullable=True),
        sa.Column('content_type', sa.String(255), nullable=True),
        sa.Column('size_bytes', sa.BigInteger, nullable=True),
        sa.Column('sha256', sa.String(64), nullable=True),
        _user('submitted_by'),
        _ms('created_at'),
        sa.UniqueConstraint('action_id', 'revision', name='uq_leadership_evidence_revision'),
    )
    op.create_table(
        'leadership_closure_request',
        _id(primary_key=True),
        _fk('action_id', 'leadership_action.id'),
        _fk('evidence_id', 'leadership_evidence.id'),
        _fk('event_id', 'leadership_action_event.id'),
        sa.Column('status', sa.String(16), nullable=False),
        _user('requested_by'),
        _ms('created_at'),
        _ms('resolved_at', nullable=True),
    )
    op.create_table(
        'leadership_closure_decision',
        _id(primary_key=True),
        _fk('request_id', 'leadership_closure_request.id'),
        _fk('evidence_id', 'leadership_evidence.id'),
        _fk('event_id', 'leadership_action_event.id', nullable=True),
        sa.Column('decision', sa.String(16), nullable=False),
        sa.Column('reason', sa.Text, nullable=True),
        _user('reviewer_user_id'),
        _ms('created_at'),
    )
    op.create_table(
        'leadership_snapshot',
        _id(primary_key=True),
        sa.Column('view_key', sa.String(16), nullable=False),
        sa.Column('meeting_label', sa.Text, nullable=False),
        sa.Column('meeting_date', sa.String(10), nullable=True),
        _user('created_by'),
        _ms('created_at'),
    )
    op.create_table(
        'leadership_snapshot_version',
        _id(primary_key=True),
        _fk('snapshot_id', 'leadership_snapshot.id'),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('state', sa.String(16), nullable=False),
        sa.Column('change_kind', sa.String(16), nullable=False),
        _fk('previous_version_id', 'leadership_snapshot_version.id', nullable=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        _user('created_by'),
        _ms('created_at'),
        sa.UniqueConstraint('snapshot_id', 'version', name='uq_leadership_snapshot_version'),
    )
    op.create_table(
        'leadership_rka_baseline',
        _id(primary_key=True),
        sa.Column('record_kind', sa.String(16), nullable=False),
        sa.Column('label', sa.Text, nullable=False),
        sa.Column('period_start', sa.String(10), nullable=False),
        sa.Column('period_end', sa.String(10), nullable=False),
        _fk('supersedes_id', 'leadership_rka_baseline.id', nullable=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        _user('approved_by', nullable=True),
        _ms('approved_at', nullable=True),
        _user('created_by'),
        _ms('created_at'),
    )
    op.create_table(
        'leadership_import_batch',
        _id(primary_key=True),
        sa.Column('source_filename', sa.Text, nullable=False),
        sa.Column('source_sha256', sa.String(64), nullable=False),
        sa.Column('meeting_date', sa.String(10), nullable=True),
        sa.Column('status', sa.String(16), nullable=False),
        _user('uploaded_by'),
        _ms('created_at'),
        sa.UniqueConstraint('source_sha256', name='uq_leadership_import_batch_source'),
    )
    op.create_table(
        'leadership_import_candidate',
        _id(primary_key=True),
        _fk('batch_id', 'leadership_import_batch.id'),
        sa.Column('candidate_key', sa.String(255), nullable=False),
        sa.Column('payload', sa.Text, nullable=False),
        _fk('matched_action_id', 'leadership_action.id', nullable=True),
        sa.Column('match_kind', sa.String(16), nullable=False),
        sa.Column('conflict', sa.Text, nullable=True),
        sa.Column('review_state', sa.String(16), nullable=False),
        _user('reviewed_by', nullable=True),
        _ms('reviewed_at', nullable=True),
        sa.UniqueConstraint('batch_id', 'candidate_key', name='uq_leadership_import_candidate_key'),
    )
    op.create_table(
        'leadership_external_ref',
        _id(primary_key=True),
        _fk('action_id', 'leadership_action.id'),
        sa.Column('source_document', sa.Text, nullable=False),
        sa.Column('slide', sa.String(64), nullable=False),
        sa.Column('external_id', sa.String(255), nullable=False),
        _user('confirmed_by'),
        _ms('confirmed_at'),
        sa.UniqueConstraint('source_document', 'slide', 'external_id', name='uq_leadership_external_ref'),
    )


def downgrade() -> None:
    for table in (
        'leadership_external_ref',
        'leadership_import_candidate',
        'leadership_import_batch',
        'leadership_rka_baseline',
        'leadership_snapshot_version',
        'leadership_snapshot',
        'leadership_closure_decision',
        'leadership_closure_request',
        'leadership_evidence',
        'leadership_action_event',
        'leadership_action',
    ):
        op.drop_table(table)
