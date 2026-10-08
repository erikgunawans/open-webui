"""Ruang Pimpinan's tables, as SQLAlchemy Core (ADR-0014).

This is what the code reads and writes through. The schema production actually has comes from the
leadership migration graph (`migrations/versions/`), and `tests/test_leadership_repository.py`
holds the two to the same columns, nullability, keys and unique constraints on SQLite and on
Postgres 16. The metadata is the fork's own, never the vendor's, so nothing here can leak into the
vendor's autogenerate or its alembic graph.

Types are chosen to behave identically on both databases:

- **Timestamps** are epoch milliseconds in a BigInteger, as the vendor stores its own, so neither
  dialect's timezone handling can shift a board record.
- **Structured content** (event payloads, snapshot and baseline content, import candidates) is
  canonical JSON in Text. The bytes are what a content hash covers, so a dialect's JSON type must
  not re-serialise them.
- **Money never touches a float.** Figures travel as decimal strings inside that JSON, the same
  rule `records.py` applies; there is no Float column (a test holds that).

Five tables are append-only: `action_event`, `evidence`, `closure_decision`, `snapshot_version`
and `rka_baseline`. No code path updates or deletes them; a source-reading test holds that too. A
change to any of them is a new row that points at the one it replaces.
"""

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, MetaData, String, Table, Text, UniqueConstraint

metadata = MetaData()

# Ids are opaque strings: an action's id is stable across imports and views (ACT-01), and user ids
# are the vendor's.
_ID = 64
_USER = 255


def _id(name: str = 'id', *args, **kwargs) -> Column:
    return Column(name, String(_ID), *args, **kwargs)


action = Table(
    'leadership_action',
    metadata,
    _id(primary_key=True),
    Column('title', Text, nullable=False),
    # The PIC is a user id plus the label the deck used. The id may be unknown until the PIC
    # identity mapping is decided; the label never is.
    Column('pic_user_id', String(_USER), nullable=True),
    Column('pic_label', Text, nullable=False),
    Column('state', String(32), nullable=False),
    # Due dates keep their precision ('month', 'year', 'year_range', 'day'); the original is never
    # overwritten, only the current one moves, and each move is a reasoned event.
    Column('original_due', String(32), nullable=True),
    Column('original_due_precision', String(16), nullable=True),
    Column('current_due', String(32), nullable=True),
    Column('current_due_precision', String(16), nullable=True),
    # The optimistic version: equal to the version of the latest event.
    Column('version', Integer, nullable=False),
    Column('created_by', String(_USER), nullable=False),
    Column('created_at', BigInteger, nullable=False),
    Column('updated_at', BigInteger, nullable=False),
)

action_event = Table(
    'leadership_action_event',
    metadata,
    _id(primary_key=True),
    _id('action_id', ForeignKey('leadership_action.id'), nullable=False),
    # Events are ordered by this, never by client time.
    Column('version', Integer, nullable=False),
    Column('kind', String(64), nullable=False),
    Column('payload', Text, nullable=False),
    Column('reason', Text, nullable=True),
    Column('author_user_id', String(_USER), nullable=False),
    Column('created_at', BigInteger, nullable=False),
    Column('idempotency_key', String(128), nullable=True),
    # A second writer at the same version cannot land even if the version check were bypassed.
    UniqueConstraint('action_id', 'version', name='uq_leadership_action_event_version'),
    # NULL keys never collide, on either database.
    UniqueConstraint('action_id', 'idempotency_key', name='uq_leadership_action_event_idempotency'),
)

evidence = Table(
    'leadership_evidence',
    metadata,
    _id(primary_key=True),
    _id('action_id', ForeignKey('leadership_action.id'), nullable=False),
    Column('revision', Integer, nullable=False),
    _id('event_id', ForeignKey('leadership_action_event.id'), nullable=False),
    Column('kind', String(16), nullable=False),  # 'file' or 'link'
    # A server-generated key under `leadership/evidence/`; the client filename is metadata only.
    Column('storage_key', Text, nullable=True),
    Column('url', Text, nullable=True),
    Column('filename', Text, nullable=True),
    Column('content_type', String(255), nullable=True),
    Column('size_bytes', BigInteger, nullable=True),
    Column('sha256', String(64), nullable=True),
    Column('submitted_by', String(_USER), nullable=False),
    Column('created_at', BigInteger, nullable=False),
    UniqueConstraint('action_id', 'revision', name='uq_leadership_evidence_revision'),
)

closure_request = Table(
    'leadership_closure_request',
    metadata,
    _id(primary_key=True),
    _id('action_id', ForeignKey('leadership_action.id'), nullable=False),
    # The exact evidence revision under review; a later revision makes pending decisions stale.
    _id('evidence_id', ForeignKey('leadership_evidence.id'), nullable=False),
    _id('event_id', ForeignKey('leadership_action_event.id'), nullable=False),
    # What closing would mean: 'completed', 'cancelled' (reason required) or 'superseded' (links
    # the replacement). All three pass the same BOD gate.
    Column('closure_kind', String(16), nullable=False),
    _id('replacement_action_id', ForeignKey('leadership_action.id'), nullable=True),
    Column('status', String(16), nullable=False),
    Column('requested_by', String(_USER), nullable=False),
    Column('created_at', BigInteger, nullable=False),
    Column('resolved_at', BigInteger, nullable=True),
)

closure_decision = Table(
    'leadership_closure_decision',
    metadata,
    _id(primary_key=True),
    _id('request_id', ForeignKey('leadership_closure_request.id'), nullable=False),
    _id('evidence_id', ForeignKey('leadership_evidence.id'), nullable=False),
    _id('event_id', ForeignKey('leadership_action_event.id'), nullable=True),
    Column('decision', String(16), nullable=False),  # 'close', 'return' or 'reopen'
    Column('reason', Text, nullable=True),
    Column('reviewer_user_id', String(_USER), nullable=False),
    Column('created_at', BigInteger, nullable=False),
)

snapshot = Table(
    'leadership_snapshot',
    metadata,
    _id(primary_key=True),
    Column('view_key', String(16), nullable=False),
    Column('meeting_label', Text, nullable=False),
    Column('meeting_date', String(10), nullable=True),
    Column('created_by', String(_USER), nullable=False),
    Column('created_at', BigInteger, nullable=False),
)

# Publishing and correcting are new versions, never edits: a published version repeats its draft's
# content and hash, and a correction links the version it replaces.
snapshot_version = Table(
    'leadership_snapshot_version',
    metadata,
    _id(primary_key=True),
    _id('snapshot_id', ForeignKey('leadership_snapshot.id'), nullable=False),
    Column('version', Integer, nullable=False),
    Column('state', String(16), nullable=False),  # 'draft' or 'published'
    Column('change_kind', String(16), nullable=False),  # 'draft', 'publication' or 'correction'
    _id('previous_version_id', ForeignKey('leadership_snapshot_version.id'), nullable=True),
    Column('content', Text, nullable=False),
    Column('content_hash', String(64), nullable=False),
    Column('created_by', String(_USER), nullable=False),
    Column('created_at', BigInteger, nullable=False),
    UniqueConstraint('snapshot_id', 'version', name='uq_leadership_snapshot_version'),
)

rka_baseline = Table(
    'leadership_rka_baseline',
    metadata,
    _id(primary_key=True),
    # 'baseline' for an approved RKA; a forecast or a later revision is its own record.
    Column('record_kind', String(16), nullable=False),
    Column('label', Text, nullable=False),
    Column('period_start', String(10), nullable=False),
    Column('period_end', String(10), nullable=False),
    _id('supersedes_id', ForeignKey('leadership_rka_baseline.id'), nullable=True),
    Column('content', Text, nullable=False),
    Column('content_hash', String(64), nullable=False),
    Column('approved_by', String(_USER), nullable=True),
    Column('approved_at', BigInteger, nullable=True),
    Column('created_by', String(_USER), nullable=False),
    Column('created_at', BigInteger, nullable=False),
)

import_batch = Table(
    'leadership_import_batch',
    metadata,
    _id(primary_key=True),
    Column('source_filename', Text, nullable=False),
    # Re-importing the same file is a no-op, not a second batch.
    Column('source_sha256', String(64), nullable=False),
    Column('meeting_date', String(10), nullable=True),
    Column('status', String(16), nullable=False),
    Column('uploaded_by', String(_USER), nullable=False),
    Column('created_at', BigInteger, nullable=False),
    UniqueConstraint('source_sha256', name='uq_leadership_import_batch_source'),
)

import_candidate = Table(
    'leadership_import_candidate',
    metadata,
    _id(primary_key=True),
    _id('batch_id', ForeignKey('leadership_import_batch.id'), nullable=False),
    Column('candidate_key', String(255), nullable=False),
    Column('payload', Text, nullable=False),
    _id('matched_action_id', ForeignKey('leadership_action.id'), nullable=True),
    Column('match_kind', String(16), nullable=False),  # 'external_ref', 'new' or 'conflict'
    # Conflicting values are stored and shown, never auto-resolved.
    Column('conflict', Text, nullable=True),
    Column('review_state', String(16), nullable=False),
    Column('reviewed_by', String(_USER), nullable=True),
    Column('reviewed_at', BigInteger, nullable=True),
    UniqueConstraint('batch_id', 'candidate_key', name='uq_leadership_import_candidate_key'),
)

# One Rapat Direksi meeting: the Corsec's Notulen as one document (D27). Written whole on every
# save, each save naming the revision it was based on, so two machines never overwrite each other.
meeting = Table(
    'leadership_meeting',
    metadata,
    _id(primary_key=True),
    Column('owner_user_id', String(_USER), nullable=False),
    # The Notulen document exactly as the client holds it (records, session, plan, notes), checked
    # structurally before it is stored. JSON in Text, like every other structured column here.
    Column('document', Text, nullable=False),
    Column('revision', Integer, nullable=False),
    # Tutup rapat on the server, and every Buka kembali with its reason (a JSON list).
    Column('closed_at', BigInteger, nullable=True),
    Column('reopenings', Text, nullable=False),
    Column('created_by', String(_USER), nullable=False),
    Column('created_at', BigInteger, nullable=False),
    Column('updated_by', String(_USER), nullable=False),
    Column('updated_at', BigInteger, nullable=False),
)

# The only way an imported row matches an existing action: a reviewed reference from a source
# deck and slide to an owner-confirmed id.
external_ref = Table(
    'leadership_external_ref',
    metadata,
    _id(primary_key=True),
    _id('action_id', ForeignKey('leadership_action.id'), nullable=False),
    Column('source_document', Text, nullable=False),
    Column('slide', String(64), nullable=False),
    Column('external_id', String(255), nullable=False),
    Column('confirmed_by', String(_USER), nullable=False),
    Column('confirmed_at', BigInteger, nullable=False),
    UniqueConstraint('source_document', 'slide', 'external_id', name='uq_leadership_external_ref'),
)
