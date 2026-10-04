"""Linking a WhatsApp number to a user, and reading the link back (E9.1, #101).

**A user links by sending a Link Code from the number** (decided with Erik 2026-10-04). The web app
issues a six-digit code, live for `CODE_MINUTES`, one per user; the user sends `hubungkan <code>` from
WhatsApp, where Meta has already verified the sender's number; the gateway passes the code and the
number's HMAC; `claim` links them. A new proof of possession replaces whatever either side was
linked to before (`relinked`): one number per user, one user per number.

**Guessing stops at the sender.** Every wrong code is a row in `jup_channel_link_failure`; after
`MAX_FAILURES` in `FAILURE_WINDOW_MINUTES` a sender's codes are refused unchecked, the right one
too, on every instance.

Functions take a SQLAlchemy engine (the vendor's, in production) and `now_ms`, so tests run on a
scratch SQLite or Postgres with a fixed clock. Nothing here sees a phone number.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, delete, func, insert, or_, select, update

from jup.channel_links.models import link, link_code, link_failure

WHATSAPP = 'whatsapp'
CODE_MINUTES = 10
MAX_FAILURES = 5
FAILURE_WINDOW_MINUTES = 10

CODE = re.compile(r'[0-9]{6}')
IDENTITY_HASH = re.compile(r'[0-9a-f]{64}')
HINT = re.compile(r'[0-9]{4}')


@dataclass(frozen=True)
class IssuedCode:
    code: str
    expires_at: int


@dataclass(frozen=True)
class Claimed:
    user_id: str
    #: The number or the user was linked to something else before this claim.
    relinked: bool


@dataclass(frozen=True)
class LinkStatus:
    hint: str
    since: int


def _hash(code: str) -> str:
    return hashlib.sha256(code.encode('ascii')).hexdigest()


def _minutes(n: int) -> int:
    return n * 60 * 1000


def issue_code(
    engine: Any, user_id: str, now_ms: int, draw: Callable[[], str] = lambda: f'{secrets.randbelow(10**6):06d}'
) -> IssuedCode:
    """A fresh Link Code for `user_id`, replacing any code they had. Retries on a clash with another user's."""
    expires_at = now_ms + _minutes(CODE_MINUTES)
    with engine.begin() as conn:
        conn.execute(delete(link_code).where(link_code.c.user_id == user_id))
        # Spent and expired codes free their value for reuse.
        conn.execute(delete(link_code).where(or_(link_code.c.used_at.is_not(None), link_code.c.expires_at <= now_ms)))
        for _ in range(20):
            code = draw()
            taken = conn.execute(select(link_code.c.user_id).where(link_code.c.code_hash == _hash(code))).first()
            if taken is None:
                conn.execute(insert(link_code).values(code_hash=_hash(code), user_id=user_id, expires_at=expires_at))
                return IssuedCode(code=code, expires_at=expires_at)
    raise RuntimeError('no free Link Code after 20 draws')


def _live_owner(conn: Any, code: str, now_ms: int) -> str | None:
    row = conn.execute(
        select(link_code.c.user_id).where(
            link_code.c.code_hash == _hash(code), link_code.c.used_at.is_(None), link_code.c.expires_at > now_ms
        )
    ).first()
    return row[0] if row else None


def _recent_failures(conn: Any, identity_hash: str, now_ms: int) -> int:
    since = now_ms - _minutes(FAILURE_WINDOW_MINUTES)
    return conn.execute(
        select(func.count())
        .select_from(link_failure)
        .where(link_failure.c.identity_hash == identity_hash, link_failure.c.at > since)
    ).scalar_one()


def code_owner(engine: Any, code: str, identity_hash: str, now_ms: int) -> str | None:
    """The user who issued `code` while it is live, else None. A miss counts against the sender;
    a sender over the limit gets None without the code being looked at."""
    if not CODE.fullmatch(code or '') or not IDENTITY_HASH.fullmatch(identity_hash or ''):
        return None
    with engine.begin() as conn:
        if _recent_failures(conn, identity_hash, now_ms) >= MAX_FAILURES:
            return None
        owner = _live_owner(conn, code, now_ms)
        if owner is None:
            conn.execute(insert(link_failure).values(identity_hash=identity_hash, at=now_ms))
            # Old attempts are only ever read inside the window; drop them as we go.
            conn.execute(delete(link_failure).where(link_failure.c.at <= now_ms - _minutes(FAILURE_WINDOW_MINUTES)))
        return owner


def claim(engine: Any, code: str, identity_hash: str, hint: str, now_ms: int) -> Claimed | None:
    """Spends `code` and links its user to the number, in one transaction. None when the code is not live.

    The caller has already been admitted on behalf of this code's user (`code_owner`); this checks the
    code again under the same transaction, so a code is spent exactly once even if two claims race.
    """
    if not IDENTITY_HASH.fullmatch(identity_hash or '') or not HINT.fullmatch(hint or ''):
        raise ValueError('identity_hash must be 64 lowercase hex and hint four digits')
    with engine.begin() as conn:
        user_id = _live_owner(conn, code, now_ms)
        if user_id is None:
            return None
        spent = conn.execute(
            update(link_code)
            .where(link_code.c.code_hash == _hash(code), link_code.c.used_at.is_(None))
            .values(used_at=now_ms)
        ).rowcount
        if spent != 1:
            return None
        replaced = conn.execute(
            delete(link).where(
                link.c.channel == WHATSAPP,
                or_(link.c.identity_hash == identity_hash, link.c.user_id == user_id),
            )
        ).rowcount
        conn.execute(
            insert(link).values(
                channel=WHATSAPP, identity_hash=identity_hash, user_id=user_id, hint=hint, created_at=now_ms
            )
        )
    return Claimed(user_id=user_id, relinked=replaced > 0)


def resolve(engine: Any, identity_hash: str) -> str | None:
    """The user a number is linked to, or None."""
    if not IDENTITY_HASH.fullmatch(identity_hash or ''):
        return None
    with engine.connect() as conn:
        row = conn.execute(
            select(link.c.user_id).where(and_(link.c.channel == WHATSAPP, link.c.identity_hash == identity_hash))
        ).first()
    return row[0] if row else None


def status(engine: Any, user_id: str) -> LinkStatus | None:
    with engine.connect() as conn:
        row = conn.execute(
            select(link.c.hint, link.c.created_at).where(link.c.channel == WHATSAPP, link.c.user_id == user_id)
        ).first()
    return LinkStatus(hint=row[0], since=row[1]) if row else None


def unlink(engine: Any, user_id: str) -> str | None:
    """Removes the user's link; returns the identity hash it had, for the audit line, or None."""
    with engine.begin() as conn:
        row = conn.execute(
            select(link.c.identity_hash).where(link.c.channel == WHATSAPP, link.c.user_id == user_id)
        ).first()
        if row is None:
            return None
        conn.execute(delete(link).where(link.c.channel == WHATSAPP, link.c.user_id == user_id))
    return row[0]


__all__ = [
    'CODE_MINUTES',
    'FAILURE_WINDOW_MINUTES',
    'MAX_FAILURES',
    'WHATSAPP',
    'Claimed',
    'IssuedCode',
    'LinkStatus',
    'claim',
    'code_owner',
    'issue_code',
    'resolve',
    'status',
    'unlink',
]
