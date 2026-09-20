"""Who is `admin`, declared rather than inherited from insertion order.

ADR-0012 settled this: the existing mechanism is "be the only row in the table". The fork
promotes the first account it ever creates and closes the signup window in the same
transaction, which worked exactly once and does not survive a second person. An admin set
that depends on which row was inserted first is not a rule, it is an outcome.

`JUP_ADMIN_EMAILS` is the rule. It is a comma-separated list, and membership in it is the
only thing that makes an account `admin`.

**Why the role is settled on a request rather than at startup.** Startup looks like the
obvious place: changing the list is an env var change, which on Cloud Run is a new revision,
which restarts every instance. But the account of someone newly added to the list usually
does not exist yet — they have never signed in. A startup pass would find nothing to
promote, they would then sign in, and they would land on `DEFAULT_USER_ROLE`, which leaves
exactly the person the list was edited for stuck as `pending`. Settling on a request covers
both cases with one mechanism: the account exists by then, whether it was created a month
ago or by this very signin.

A per-process set records the addresses already settled, so an allowlisted user costs one
database read once per instance rather than one per request. This module never demotes. Removing someone from the list does not strip a role, because
"the list shrank" and "this instance started before the list grew" are indistinguishable
from here, and guessing wrong in that direction removes an administrator mid-session.
Demotion is a deliberate act, and it belongs in the admin UI where it is visible.
"""

import logging
import os
from collections.abc import Awaitable, Callable

from jup.iap_identity import IAP_HEADERS, normalize_iap_value

log = logging.getLogger(__name__)

ADMIN_ALLOWLIST_ENV = 'JUP_ADMIN_EMAILS'
_EMAIL_HEADER = b'x-goog-authenticated-user-email'


def parse_admin_allowlist(raw: str | None) -> frozenset[str]:
    """Parse the comma-separated list into lowercase addresses.

    Lowercased because every vendor read site lowercases the header before comparing, so a
    list that did not would silently fail to match a capitalized entry. Blank entries are
    dropped rather than rejected: a trailing comma is a typo, not a configuration error
    worth refusing to boot over.
    """
    if not raw:
        return frozenset()
    return frozenset(part.strip().lower() for part in raw.split(',') if part.strip())


def admin_allowlist_from_env(env: dict[str, str] | None = None) -> frozenset[str]:
    """The allowlist as configured, read from the environment."""
    source = os.environ if env is None else env
    return parse_admin_allowlist(source.get(ADMIN_ALLOWLIST_ENV))


async def ensure_admin(email: str, allowlist: frozenset[str], users) -> bool:
    """Promote `email` to `admin` when the list says so. Returns whether it changed a role.

    `users` is injected rather than imported at module scope so this is testable without the
    vendor runtime, and so the import cost is not paid by a process that never calls it.

    An address not in the list is left entirely alone — this is not the place that decides
    someone should *stop* being an administrator.
    """
    normalized = email.strip().lower()
    if not normalized or normalized not in allowlist:
        return False
    user = await users.get_user_by_email(normalized)
    if user is None:
        return False
    if user.role == 'admin':
        return False
    await users.update_user_role_by_id(user.id, 'admin')
    log.info('promoted %s to admin from %s', normalized, ADMIN_ALLOWLIST_ENV)
    return True


class AdminAllowlistMiddleware:
    """Settle the signed-in identity's role once per address, per process.

    Runs *after* the inner app so that a first-ever trusted-header signin has already
    created the account by the time the role is checked. Reading the header before routing
    would be one request too early for exactly the person this exists to serve.

    A failure here is logged and swallowed. The role is a permission, not the request: an
    allowlist that cannot reach the database should not turn a working page into a 500. The
    consequence of swallowing is that the user stays on their current role and the next
    request from them retries, because a failed attempt is not recorded as settled.
    """

    def __init__(self, app: Callable[..., Awaitable[None]], allowlist: frozenset[str] | None = None) -> None:
        self.app = app
        self.allowlist = admin_allowlist_from_env() if allowlist is None else allowlist
        self._settled: set[str] = set()

    def _pending_email(self, scope: dict) -> str | None:
        """The signed-in address, when it is allowlisted and not already settled here."""
        if not self.allowlist or scope.get('type') != 'http':
            return None
        for name, value in scope.get('headers') or []:
            if name != _EMAIL_HEADER:
                continue
            email = normalize_iap_value(value.decode('latin-1', 'ignore')).strip().lower()
            if email and email in self.allowlist and email not in self._settled:
                return email
        return None

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        email = self._pending_email(scope)
        await self.app(scope, receive, send)
        if email is None:
            return
        try:
            from open_webui.models.users import Users

            await ensure_admin(email, self.allowlist, Users)
        except Exception:
            log.exception('could not settle the admin role for %s', email)
            return
        self._settled.add(email)


__all__ = [
    'ADMIN_ALLOWLIST_ENV',
    'AdminAllowlistMiddleware',
    'IAP_HEADERS',
    'admin_allowlist_from_env',
    'ensure_admin',
    'parse_admin_allowlist',
]
