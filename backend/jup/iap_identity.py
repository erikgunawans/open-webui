"""Normalize IAP's identity headers once, at our own boundary, so no vendor file is patched.

ADR-0012 is the decision this module implements. IAP sends the authenticated identity as
`accounts.google.com:erik@axiara.ai` — the provider, a colon, then the address. Open WebUI
reads that header raw, in three places:

    routers/auths.py:393   refuses password changes while trusted-header mode is on
    routers/auths.py:736   creates and authenticates the account from the header
    utils/auth.py:415      re-checks the header against `user.email` on EVERY request

The third is why this is a middleware and not a patch. Stripping the prefix only at the
signin path produces a *correct* account and then 401s every subsequent request, because
`utils/auth.py` is still comparing `erik@axiara.ai` against the raw prefixed value. The
symptom is being signed out immediately after signing in — a session bug to anyone reading
it, and nothing points at a prefix.

Rewriting the header before routing means all three sites read a clean value and none of
them is touched. The vendor surface becomes one registration line in `main.py`, whose
absence a test can see. That is the whole argument for this shape: a dropped vendor auth
patch is a production login loop, and a dropped registration line is a failing test.

The prefix is IAP's convention. Translating another system's convention at our own edge is
fork-owned work by definition, which is why this lives in `backend/jup/` and not in a diff
against `open_webui`.

**The channel gateway (ADR-0012 amendment 2026-10-04, E7).** `jup-gateway` reaches ent-os through
the same load balancer and IAP as a person, as its own service account, so IAP's header names the
gateway. Left alone, `auths.py:736` would create an account for it and answer as it. So this
middleware, which already reads the identity once before routing, recognises that one principal
(`JUP_GATEWAY_PRINCIPAL`) and lets it act only on behalf of an existing, non-`pending` user who
holds `jup.channel.use`, only on the Channel API prefix, and only while `JUP_CHANNELS_ENABLED` is on.
Then the email header is rewritten to that user's address and every vendor read site sees the
director, exactly as if they had signed in. Any other case is a 403 here, before routing, and no
account is ever created. For everyone else `X-JUP-On-Behalf-Of` is stripped, so a signed-in person
cannot become someone else by sending it.
"""

import json
import logging
import os
from collections.abc import Awaitable, Callable, Iterable, Mapping
from typing import Any

from jup.governance import CHANNEL_TURN_STATE_ATTR, CHANNEL_USER_STATE_ATTR

log = logging.getLogger(__name__)

# The headers IAP prefixes. The email header is the one the fork authenticates from; the ID
# header carries the same provider prefix in front of a numeric subject and is normalized
# for consistency, so nothing downstream has to know that only one of them was handled.
IAP_HEADERS: tuple[bytes, ...] = (
    b'x-goog-authenticated-user-email',
    b'x-goog-authenticated-user-id',
)
_EMAIL_HEADER, _ID_HEADER = IAP_HEADERS

#: The gateway's service-account email. Unset means no request is ever treated as the gateway.
GATEWAY_PRINCIPAL_ENV = 'JUP_GATEWAY_PRINCIPAL'
#: The kill switch for every Channel, read per request like `jup.voice.enabled`.
CHANNELS_ENABLED_ENV = 'JUP_CHANNELS_ENABLED'
#: Who the gateway is acting for. Honoured from the gateway principal only; stripped from everyone else.
ON_BEHALF_OF_HEADER = b'x-jup-on-behalf-of'
#: The only paths the gateway principal may reach (`routers/jup_channel.py` is mounted here).
CHANNEL_API_PREFIX = '/api/jup/channel/'

#: What a refused gateway request gets back. The reason goes to the audit line only (spec #84).
REFUSED_DETAIL = 'channel_refused'

GrantCheck = Callable[[Any], Awaitable[bool]]
Audit = Callable[..., None]


def normalize_iap_value(raw: str) -> str:
    """Strip IAP's `<provider>:` prefix, or return the value untouched when it has none.

    `rsplit` on the last colon rather than the first: the provider portion can itself
    contain a path (`securetoken.google.com/some-project:user`), and neither an email
    address nor a numeric subject can contain a colon, so the last one is always the
    separator.

    A value whose suffix is empty (`accounts.google.com:`) is returned **unchanged**. The
    conservative reading of a malformed identity is to pass it through and let the vendor's
    own validation refuse it. Normalizing it to `''` would hand `auths.py` an empty string
    to create an account from, which is how a malformed header becomes a malformed user
    rather than a rejected request.
    """
    if ':' not in raw:
        return raw
    suffix = raw.rsplit(':', 1)[1].strip()
    if not suffix:
        return raw
    return suffix


def normalize_headers(headers: Iterable[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    """Return the ASGI header list with every IAP identity header normalized.

    Header names in an ASGI scope are lowercase bytes, so the comparison is exact and needs
    no case folding. Values are latin-1 per the ASGI spec, and latin-1 maps all 256 byte
    values, so neither the decode nor the re-encode can fail and neither is guarded. A guard
    here would be unreachable code asserting a safety it never provides.
    """
    normalized: list[tuple[bytes, bytes]] = []
    for name, value in headers:
        if name not in IAP_HEADERS:
            normalized.append((name, value))
            continue
        decoded = normalize_iap_value(value.decode('latin-1'))
        normalized.append((name, decoded.encode('latin-1')))
    return normalized


def gateway_principal(env: Mapping[str, str] | None = None) -> str:
    """The configured gateway principal, lowercased, or `''` when there is none."""
    source = os.environ if env is None else env
    return (source.get(GATEWAY_PRINCIPAL_ENV) or '').strip().lower()


def channels_enabled(env: Mapping[str, str] | None = None) -> bool:
    """The kill switch: on only for an explicit `1` or `true`."""
    source = os.environ if env is None else env
    return (source.get(CHANNELS_ENABLED_ENV) or '').strip().lower() in ('1', 'true')


def on_channel_prefix(path: Any) -> bool:
    """Whether `path` is under the Channel API prefix, with no `..` segment to climb out of it."""
    return isinstance(path, str) and path.startswith(CHANNEL_API_PREFIX) and '..' not in path.split('/')


def _identity(headers: Iterable[tuple[bytes, bytes]]) -> str:
    """The normalised, lowercased identity email, or `''` when there is none."""
    for name, value in headers:
        if name == _EMAIL_HEADER:
            return normalize_iap_value(value.decode('latin-1')).strip().lower()
    return ''


async def _default_grant(user: Any) -> bool:
    import copy

    from jup.channel import DEFAULT_PERMISSIONS, may_use_channel
    from open_webui.utils.access_control import get_permissions

    return may_use_channel(await get_permissions(user.id, copy.deepcopy(DEFAULT_PERMISSIONS)))


def _default_audit(event: str, **fields: Any) -> None:
    from jup.governance import audit

    audit(event, **fields)


class IapIdentityHeaderMiddleware:
    """Pure ASGI middleware rewriting IAP's identity headers before anything routes.

    Deliberately not a `BaseHTTPMiddleware`: that wraps the request after the scope is
    built, and `utils/auth.py` reads `request.headers`, which is a view over the scope. The
    rewrite has to happen in the scope itself for all three read sites to see it.

    The scope is copied rather than mutated in place. Starlette hands the same scope object
    to everything downstream, and a middleware that edits its caller's dict is a debugging
    problem the first time two of them disagree.
    """

    def __init__(
        self,
        app: Callable[..., Awaitable[None]],
        *,
        env: Mapping[str, str] | None = None,
        users: Any = None,
        may_use_channel: GrantCheck | None = None,
        audit: Audit | None = None,
    ) -> None:
        self.app = app
        # Injected in tests; in production the env is read per request and the vendor's `Users`
        # is imported on first use, so a process that never sees the gateway never pays for it.
        self._env = env
        self._users = users
        self._may_use_channel = may_use_channel or _default_grant
        self._audit = audit or _default_audit

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get('type') not in ('http', 'websocket'):
            await self.app(scope, receive, send)
            return
        headers = scope.get('headers') or []
        principal = gateway_principal(self._env)
        if principal and _identity(headers) == principal:
            await self._as_gateway(scope, headers, receive, send)
            return
        if not any(name in IAP_HEADERS or name == ON_BEHALF_OF_HEADER for name, _ in headers):
            await self.app(scope, receive, send)
            return
        scope = dict(scope)
        scope['headers'] = [item for item in normalize_headers(headers) if item[0] != ON_BEHALF_OF_HEADER]
        await self.app(scope, receive, send)

    async def _as_gateway(self, scope: dict, headers: list, receive: Callable, send: Callable) -> None:
        """Admit the gateway on behalf of one mapped user, or refuse it here, before routing."""
        user, reason = await self._mapped_user(scope, headers)
        if user is None:
            self._audit('channel_turn', outcome='refused', reason=reason, path=scope.get('path'))
            await _refuse(scope, send)
            return
        rewritten = [item for item in headers if item[0] not in (ON_BEHALF_OF_HEADER, _EMAIL_HEADER, _ID_HEADER)]
        rewritten.append((_EMAIL_HEADER, str(user.email).encode('latin-1')))
        scope = dict(scope)
        scope['headers'] = rewritten
        scope['state'] = {
            **(scope.get('state') or {}),
            CHANNEL_TURN_STATE_ATTR: True,
            CHANNEL_USER_STATE_ATTR: user.id,
        }
        await self.app(scope, receive, send)

    async def _mapped_user(self, scope: dict, headers: list) -> tuple[Any, str]:
        """`(user, '')` when the gateway may act for the named user, else `(None, reason)`."""
        if scope.get('type') != 'http':
            return None, 'gateway_not_http'
        if not channels_enabled(self._env):
            return None, 'channels_disabled'
        if not on_channel_prefix(scope.get('path')):
            return None, 'gateway_off_prefix'
        values = [value for name, value in headers if name == ON_BEHALF_OF_HEADER]
        email = values[0].decode('latin-1').strip().lower() if len(values) == 1 else ''
        if not email:
            return None, 'no_on_behalf_of'
        try:
            user = await self._lookup(email)
            if user is None:
                return None, 'unknown_user'
            if getattr(user, 'role', None) == 'pending':
                return None, 'pending_user'
            if await self._may_use_channel(user) is not True:
                return None, 'not_granted'
        except Exception:
            log.exception('jup.iap_identity could not check the gateway on-behalf-of user')
            return None, 'lookup_failed'
        return user, ''

    async def _lookup(self, email: str) -> Any:
        if self._users is None:
            from open_webui.models.users import Users

            self._users = Users
        return await self._users.get_user_by_email(email)


async def _refuse(scope: dict, send: Callable) -> None:
    if scope.get('type') == 'websocket':
        await send({'type': 'websocket.close', 'code': 1008})
        return
    body = json.dumps({'detail': REFUSED_DETAIL}).encode()
    await send(
        {
            'type': 'http.response.start',
            'status': 403,
            'headers': [(b'content-type', b'application/json'), (b'content-length', str(len(body)).encode())],
        }
    )
    await send({'type': 'http.response.body', 'body': body})
