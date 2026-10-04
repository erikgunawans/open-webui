"""The Mapping tables, as SQLAlchemy Core on the fork's own metadata (ADR-0014 pattern).

The schema production has comes from `migrations/versions/`; `tests/test_channel_links.py` holds the
two to the same columns, keys and unique constraints. Timestamps are epoch milliseconds in a
BigInteger, as in the other fork tables.

- `jup_channel_link`: one row per linked number. Unique per (channel, identity hash) and per
  (channel, user): one number per user and one user per number.
- `jup_channel_link_code`: the user's one live Link Code, stored as its SHA-256, never in clear.
- `jup_channel_link_failure`: one row per wrong code, per sender, so guessing stops across every
  ent-os instance (live scales to four).
"""

from sqlalchemy import BigInteger, Column, Integer, MetaData, String, Table, UniqueConstraint

metadata = MetaData()

_HASH = 64
_USER = 255

link = Table(
    'jup_channel_link',
    metadata,
    Column('channel', String(16), primary_key=True),
    Column('identity_hash', String(_HASH), primary_key=True),
    Column('user_id', String(_USER), nullable=False),
    # The number's last four digits, for "•••• 1234" in the web app. Never the whole number.
    Column('hint', String(8), nullable=False),
    Column('created_at', BigInteger, nullable=False),
    UniqueConstraint('channel', 'user_id', name='uq_jup_channel_link_user'),
)

link_code = Table(
    'jup_channel_link_code',
    metadata,
    Column('code_hash', String(_HASH), primary_key=True),
    Column('user_id', String(_USER), nullable=False, unique=True),
    Column('expires_at', BigInteger, nullable=False),
    Column('used_at', BigInteger, nullable=True),
)

link_failure = Table(
    'jup_channel_link_failure',
    metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('identity_hash', String(_HASH), nullable=False, index=True),
    Column('at', BigInteger, nullable=False),
)
