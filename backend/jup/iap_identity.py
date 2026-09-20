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
"""

from collections.abc import Awaitable, Callable, Iterable

# The headers IAP prefixes. The email header is the one the fork authenticates from; the ID
# header carries the same provider prefix in front of a numeric subject and is normalized
# for consistency, so nothing downstream has to know that only one of them was handled.
IAP_HEADERS: tuple[bytes, ...] = (
    b'x-goog-authenticated-user-email',
    b'x-goog-authenticated-user-id',
)


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
    no case folding. Values are latin-1 per the ASGI spec; an address that somehow is not
    decodable is left alone rather than guessed at.
    """
    normalized: list[tuple[bytes, bytes]] = []
    for name, value in headers:
        if name not in IAP_HEADERS:
            normalized.append((name, value))
            continue
        try:
            decoded = value.decode('latin-1')
        except UnicodeDecodeError:
            normalized.append((name, value))
            continue
        normalized.append((name, normalize_iap_value(decoded).encode('latin-1')))
    return normalized


class IapIdentityHeaderMiddleware:
    """Pure ASGI middleware rewriting IAP's identity headers before anything routes.

    Deliberately not a `BaseHTTPMiddleware`: that wraps the request after the scope is
    built, and `utils/auth.py` reads `request.headers`, which is a view over the scope. The
    rewrite has to happen in the scope itself for all three read sites to see it.

    The scope is copied rather than mutated in place. Starlette hands the same scope object
    to everything downstream, and a middleware that edits its caller's dict is a debugging
    problem the first time two of them disagree.
    """

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get('type') not in ('http', 'websocket'):
            await self.app(scope, receive, send)
            return
        headers = scope.get('headers') or []
        if not any(name in IAP_HEADERS for name, _ in headers):
            await self.app(scope, receive, send)
            return
        scope = dict(scope)
        scope['headers'] = normalize_headers(headers)
        await self.app(scope, receive, send)
