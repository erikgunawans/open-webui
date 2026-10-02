"""The contract tables, as SQLAlchemy Core on the fork's own metadata.

The schema production has comes from `migrations/versions/`; `tests/test_contract_repository.py`
holds the two to the same columns, nullability, keys and unique constraints. Types follow the
leadership tables so both databases behave the same:

- **Timestamps** are epoch milliseconds in a BigInteger.
- **Cards and payloads** are canonical JSON in Text, so the bytes a hash covers are never
  re-serialised by a dialect's JSON type.
- **Dates** are ISO `YYYY-MM-DD` strings: a contract date has no time and no timezone.

`jup_contract_event` is append-only: no code path updates or deletes it.

Individual parties (D2) live in `jup_contract_party` with a code that is unique across all
contracts, so an answer citing two contracts can never show two different people as the same
"Perorangan A", and unmasking after the answer is unambiguous. The same person in several contracts
keeps one code (`name_key` is the normalised name).
"""

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Integer, MetaData, String, Table, Text, UniqueConstraint

metadata = MetaData()

_ID = 64
_USER = 255

STATES: tuple[str, ...] = ('draft', 'approved', 'returned')


def _id(name: str = 'id', *args, **kwargs) -> Column:
    return Column(name, String(_ID), *args, **kwargs)


contract = Table(
    'jup_contract',
    metadata,
    _id(primary_key=True),
    # The OneDrive item the PDF came from: stable across runs, so a re-import updates, never duplicates.
    Column('source_item_id', String(_USER), nullable=False, unique=True),
    # The run and its zero-padded number, e.g. ('full', '0042'): where the card, OCR and PDF sit.
    Column('run', String(32), nullable=False),
    Column('number', String(16), nullable=False),
    Column('source_object', Text, nullable=False),
    Column('source_web_url', Text, nullable=True),
    # JSON list of folder names under SCAN PERJANJIAN, then the file name.
    Column('source_path', Text, nullable=False),
    Column('source_file', Text, nullable=False),
    Column('page_count', Integer, nullable=False),
    # JSON lists of page numbers.
    Column('low_confidence_pages', Text, nullable=False),
    Column('manual_check_pages', Text, nullable=False),
    Column('model', String(64), nullable=True),
    # Searchable copies of four card fields, from the current card. Masked on the way out like the card.
    Column('partner', Text, nullable=True),
    Column('contract_number', Text, nullable=True),
    Column('title', Text, nullable=True),
    Column('doc_type', Text, nullable=True),
    # The card as drafted, never edited, and its hash; the card as it stands after Legal's edits.
    Column('draft_card', Text, nullable=True),
    Column('draft_sha256', String(64), nullable=True),
    Column('current_card', Text, nullable=True),
    Column('state', String(16), nullable=False),
    Column('start_date', String(10), nullable=True),
    Column('end_date', String(10), nullable=True),
    Column('auto_renewal', Boolean, nullable=True),
    # JSON list of unit codes (D4: set by Legal in the review screen; empty until then).
    Column('units', Text, nullable=False),
    # Equal to the version of the latest event.
    Column('version', Integer, nullable=False),
    Column('created_at', BigInteger, nullable=False),
    Column('updated_at', BigInteger, nullable=False),
    UniqueConstraint('run', 'number', name='uq_jup_contract_run_number'),
)

contract_event = Table(
    'jup_contract_event',
    metadata,
    _id(primary_key=True),
    _id('contract_id', ForeignKey('jup_contract.id'), nullable=False),
    Column('version', Integer, nullable=False),
    Column('kind', String(64), nullable=False),
    Column('payload', Text, nullable=False),
    Column('reason', Text, nullable=True),
    Column('actor', String(_USER), nullable=False),
    Column('at', BigInteger, nullable=False),
    UniqueConstraint('contract_id', 'version', name='uq_jup_contract_event_version'),
)

party = Table(
    'jup_contract_party',
    metadata,
    _id(primary_key=True),
    # "Perorangan A", "Perorangan B", … "Perorangan AA": unique across every contract.
    Column('code', String(32), nullable=False, unique=True),
    Column('name', Text, nullable=False),
    Column('name_key', String(_USER), nullable=False, unique=True),
    Column('created_at', BigInteger, nullable=False),
)

party_link = Table(
    'jup_contract_party_link',
    metadata,
    _id('contract_id', ForeignKey('jup_contract.id'), primary_key=True),
    _id('party_id', ForeignKey('jup_contract_party.id'), primary_key=True),
)
