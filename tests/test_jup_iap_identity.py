"""The IAP login's two fork-owned pieces, tested without a server.

ADR-0012 put both in `backend/jup/` precisely so they could be tested like this: the header
normalizer and the admin allowlist are pure ASGI and pure functions, with the one vendor
dependency (`Users`) injected rather than imported at module scope. So this file needs no
runtime tree and runs in CI's `--only-group dev` job, where the whole suite is seconds.

What is *not* here is the registration — whether `main.py` actually installs either of
these. That is the failure this decision was chosen for, and it lives in
`tests/test_jup_iap_registration.py`, which has to import the app to see it.
"""

import sys

import pytest

from jup.admin_allowlist import (
    ADMIN_ALLOWLIST_ENV,
    AdminAllowlistMiddleware,
    admin_allowlist_from_env,
    ensure_admin,
    parse_admin_allowlist,
)
from jup.iap_identity import (
    IAP_HEADERS,
    IapIdentityHeaderMiddleware,
    normalize_headers,
    normalize_iap_value,
)

EMAIL_HEADER = b'x-goog-authenticated-user-email'
ID_HEADER = b'x-goog-authenticated-user-id'


def http_scope(*headers: tuple[bytes, bytes], type: str = 'http') -> dict:
    """A scope with just the parts these middlewares read."""
    return {'type': type, 'path': '/api/v1/portfolio', 'headers': list(headers)}


class RecordingApp:
    """An inner ASGI app that remembers the scope it was handed, and nothing else."""

    def __init__(self) -> None:
        self.scopes: list[dict] = []

    async def __call__(self, scope: dict, receive, send) -> None:
        self.scopes.append(scope)

    @property
    def headers(self) -> list[tuple[bytes, bytes]]:
        assert len(self.scopes) == 1, f'expected one downstream call, got {len(self.scopes)}'
        return self.scopes[0]['headers']


class FakeUser:
    def __init__(self, id: str, email: str, role: str) -> None:
        self.id = id
        self.email = email
        self.role = role


class FakeUsers:
    """Stands in for `open_webui.models.users.Users`, recording what was asked of it."""

    def __init__(self, *users: FakeUser) -> None:
        self._by_email = {user.email: user for user in users}
        self.lookups: list[str] = []
        self.promotions: list[tuple[str, str]] = []

    async def get_user_by_email(self, email: str) -> FakeUser | None:
        self.lookups.append(email)
        return self._by_email.get(email)

    async def update_user_role_by_id(self, id: str, role: str) -> None:
        self.promotions.append((id, role))
        for user in self._by_email.values():
            if user.id == id:
                user.role = role


class ExplodingUsers:
    """The database being unreachable, which must not turn a working page into a 500."""

    async def get_user_by_email(self, email: str):
        raise RuntimeError('no database')


# --------------------------------------------------------------------------------------
# normalize_iap_value
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        ('accounts.google.com:erik@axiara.ai', 'erik@axiara.ai'),
        ('accounts.google.com:103547991597142817347', '103547991597142817347'),
        # The provider portion can carry a path, so the separator is the LAST colon.
        ('securetoken.google.com/jup-ops:erik@axiara.ai', 'erik@axiara.ai'),
        # Already bare — the shape when something upstream of us has already stripped it.
        ('erik@axiara.ai', 'erik@axiara.ai'),
        ('', ''),
        ('accounts.google.com: erik@axiara.ai ', 'erik@axiara.ai'),
    ],
)
def test_the_provider_prefix_is_stripped_and_a_bare_value_is_left_alone(raw: str, expected: str) -> None:
    assert normalize_iap_value(raw) == expected


@pytest.mark.parametrize('raw', ['accounts.google.com:', 'accounts.google.com:   ', ':'])
def test_an_empty_suffix_passes_through_untouched_rather_than_becoming_an_empty_address(raw: str) -> None:
    """A malformed identity must reach the vendor's validation, not be normalized into one.

    `auths.py:736` creates an account from this value. Handing it `''` turns a header the
    vendor would have refused into a user row it accepts — a malformed identity becoming a
    malformed *account*, which is far harder to notice than a rejected request.
    """
    assert normalize_iap_value(raw) == raw


# --------------------------------------------------------------------------------------
# normalize_headers
# --------------------------------------------------------------------------------------


def test_both_iap_headers_are_normalized_and_everything_else_is_passed_through_in_order() -> None:
    normalized = normalize_headers(
        [
            (b'host', b'non-jupe.jup.co.id'),
            (EMAIL_HEADER, b'accounts.google.com:erik@axiara.ai'),
            (b'cookie', b'token=abc:def'),
            (ID_HEADER, b'accounts.google.com:1035479915'),
        ]
    )

    assert normalized == [
        (b'host', b'non-jupe.jup.co.id'),
        (EMAIL_HEADER, b'erik@axiara.ai'),
        # A colon in an unrelated header is none of this function's business.
        (b'cookie', b'token=abc:def'),
        (ID_HEADER, b'1035479915'),
    ]


def test_a_repeated_identity_header_is_normalized_in_every_position() -> None:
    """ASGI headers are a list, not a mapping, so a name can legitimately appear twice."""
    normalized = normalize_headers(
        [
            (EMAIL_HEADER, b'accounts.google.com:first@axiara.ai'),
            (EMAIL_HEADER, b'accounts.google.com:second@axiara.ai'),
        ]
    )

    assert normalized == [(EMAIL_HEADER, b'first@axiara.ai'), (EMAIL_HEADER, b'second@axiara.ai')]


def test_a_high_byte_value_survives_the_round_trip() -> None:
    """latin-1 maps all 256 byte values, which is why the decode carries no guard."""
    normalized = normalize_headers([(EMAIL_HEADER, b'accounts.google.com:\xe9rik@axiara.ai')])

    assert normalized == [(EMAIL_HEADER, b'\xe9rik@axiara.ai')]


# --------------------------------------------------------------------------------------
# IapIdentityHeaderMiddleware
# --------------------------------------------------------------------------------------


async def test_the_downstream_app_sees_a_bare_address() -> None:
    inner = RecordingApp()
    scope = http_scope((b'host', b'non-jupe.jup.co.id'), (EMAIL_HEADER, b'accounts.google.com:erik@axiara.ai'))

    await IapIdentityHeaderMiddleware(inner)(scope, None, None)

    assert inner.headers == [(b'host', b'non-jupe.jup.co.id'), (EMAIL_HEADER, b'erik@axiara.ai')]


async def test_the_callers_scope_is_not_mutated() -> None:
    """Starlette hands one scope object around; editing it in place is a cross-layer surprise."""
    inner = RecordingApp()
    original = [(EMAIL_HEADER, b'accounts.google.com:erik@axiara.ai')]
    scope = http_scope(*original)

    await IapIdentityHeaderMiddleware(inner)(scope, None, None)

    assert scope['headers'] == original
    assert inner.scopes[0] is not scope


async def test_a_websocket_scope_is_normalized_too() -> None:
    """`utils/auth.py` runs on the socket path as well, so it needs the same clean value."""
    inner = RecordingApp()

    await IapIdentityHeaderMiddleware(inner)(
        http_scope((EMAIL_HEADER, b'accounts.google.com:erik@axiara.ai'), type='websocket'), None, None
    )

    assert inner.headers == [(EMAIL_HEADER, b'erik@axiara.ai')]


@pytest.mark.parametrize(
    'scope',
    [
        {'type': 'lifespan'},
        http_scope((b'host', b'non-jupe.jup.co.id')),
        http_scope(),
        {'type': 'http', 'path': '/'},
    ],
    ids=['lifespan', 'no-iap-header', 'no-headers', 'headers-key-absent'],
)
async def test_a_scope_with_nothing_to_rewrite_is_forwarded_as_is(scope: dict) -> None:
    """Including lifespan, which has no `headers` key at all and must not be indexed."""
    inner = RecordingApp()

    await IapIdentityHeaderMiddleware(inner)(scope, None, None)

    assert inner.scopes == [scope]
    assert inner.scopes[0] is scope


async def test_receive_and_send_are_handed_down_untouched() -> None:
    """This middleware rewrites identity, not the message stream."""
    seen = {}

    async def inner(scope, receive, send):
        seen['receive'] = receive
        seen['send'] = send

    async def receive():  # pragma: no cover - identity only
        return {}

    async def send(message):  # pragma: no cover - identity only
        return None

    await IapIdentityHeaderMiddleware(inner)(
        http_scope((EMAIL_HEADER, b'accounts.google.com:erik@axiara.ai')), receive, send
    )

    assert seen == {'receive': receive, 'send': send}


def test_the_id_header_is_covered_as_well_as_the_email_one() -> None:
    """Guards the tuple itself: dropping either name is a silent regression for that header."""
    assert IAP_HEADERS == (EMAIL_HEADER, ID_HEADER)
    assert all(name == name.lower() for name in IAP_HEADERS), 'ASGI header names are lowercase bytes'


# --------------------------------------------------------------------------------------
# parse_admin_allowlist / admin_allowlist_from_env
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('raw', 'expected'),
    [
        (None, frozenset()),
        ('', frozenset()),
        ('   ', frozenset()),
        (',,', frozenset()),
        ('erik@axiara.ai', frozenset({'erik@axiara.ai'})),
        (' erik@axiara.ai , ops@axiara.ai ', frozenset({'erik@axiara.ai', 'ops@axiara.ai'})),
        ('erik@axiara.ai,', frozenset({'erik@axiara.ai'})),
        # Lowercased because every vendor read site lowercases before comparing.
        ('Erik@Axiara.AI', frozenset({'erik@axiara.ai'})),
        ('erik@axiara.ai,erik@axiara.ai', frozenset({'erik@axiara.ai'})),
    ],
)
def test_the_allowlist_parses_to_lowercase_addresses(raw: str | None, expected: frozenset[str]) -> None:
    assert parse_admin_allowlist(raw) == expected


def test_the_allowlist_reads_its_env_var_by_name() -> None:
    assert ADMIN_ALLOWLIST_ENV == 'JUP_ADMIN_EMAILS'
    assert admin_allowlist_from_env({ADMIN_ALLOWLIST_ENV: 'Erik@Axiara.ai'}) == frozenset({'erik@axiara.ai'})
    assert admin_allowlist_from_env({}) == frozenset()


def test_an_unset_env_var_yields_an_empty_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default has to be "nobody", not "everybody" — asserted against the real environment."""
    monkeypatch.delenv(ADMIN_ALLOWLIST_ENV, raising=False)

    assert admin_allowlist_from_env() == frozenset()


# --------------------------------------------------------------------------------------
# ensure_admin
# --------------------------------------------------------------------------------------


async def test_an_allowlisted_account_is_promoted_once() -> None:
    users = FakeUsers(FakeUser('u1', 'erik@axiara.ai', 'pending'))
    allowlist = frozenset({'erik@axiara.ai'})

    assert await ensure_admin('erik@axiara.ai', allowlist, users) is True
    assert users.promotions == [('u1', 'admin')]
    # Second call finds the role already settled and writes nothing.
    assert await ensure_admin('erik@axiara.ai', allowlist, users) is False
    assert users.promotions == [('u1', 'admin')]


@pytest.mark.parametrize('email', ['Erik@Axiara.AI', '  erik@axiara.ai  '])
async def test_the_address_is_normalized_before_it_is_matched(email: str) -> None:
    users = FakeUsers(FakeUser('u1', 'erik@axiara.ai', 'pending'))

    assert await ensure_admin(email, frozenset({'erik@axiara.ai'}), users) is True
    assert users.promotions == [('u1', 'admin')]


@pytest.mark.parametrize('email', ['someone@example.com', '', '   '])
async def test_an_address_outside_the_list_is_never_looked_up(email: str) -> None:
    """Not merely "not promoted": an off-list request must cost no database read at all."""
    users = FakeUsers(FakeUser('u1', 'erik@axiara.ai', 'pending'))

    assert await ensure_admin(email, frozenset({'erik@axiara.ai'}), users) is False
    assert users.lookups == []
    assert users.promotions == []


async def test_an_allowlisted_address_with_no_account_yet_is_a_no_op() -> None:
    """Someone added to the list who has never signed in. The next request retries."""
    users = FakeUsers()

    assert await ensure_admin('erik@axiara.ai', frozenset({'erik@axiara.ai'}), users) is False
    assert users.lookups == ['erik@axiara.ai']
    assert users.promotions == []


async def test_removal_from_the_list_does_not_demote() -> None:
    """Deliberate, per ADR-0012: "the list shrank" and "this instance predates the list
    growing" are indistinguishable here, and guessing wrong strips an admin mid-session."""
    users = FakeUsers(FakeUser('u1', 'erik@axiara.ai', 'admin'))

    assert await ensure_admin('erik@axiara.ai', frozenset(), users) is False
    assert users.promotions == []
    assert users._by_email['erik@axiara.ai'].role == 'admin'


# --------------------------------------------------------------------------------------
# AdminAllowlistMiddleware
# --------------------------------------------------------------------------------------


def test_the_allowlist_defaults_to_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ADMIN_ALLOWLIST_ENV, 'erik@axiara.ai')

    assert AdminAllowlistMiddleware(RecordingApp()).allowlist == frozenset({'erik@axiara.ai'})


@pytest.mark.parametrize(
    ('scope', 'allowlist', 'expected'),
    [
        (
            http_scope((EMAIL_HEADER, b'accounts.google.com:erik@axiara.ai')),
            frozenset({'erik@axiara.ai'}),
            'erik@axiara.ai',
        ),
        # Already normalized by the middleware registered outside this one.
        (http_scope((EMAIL_HEADER, b'erik@axiara.ai')), frozenset({'erik@axiara.ai'}), 'erik@axiara.ai'),
        (http_scope((EMAIL_HEADER, b'ERIK@AXIARA.AI')), frozenset({'erik@axiara.ai'}), 'erik@axiara.ai'),
        (http_scope((EMAIL_HEADER, b'someone@example.com')), frozenset({'erik@axiara.ai'}), None),
        (http_scope((b'host', b'non-jupe.jup.co.id')), frozenset({'erik@axiara.ai'}), None),
        (http_scope((EMAIL_HEADER, b'erik@axiara.ai')), frozenset(), None),
        (http_scope((EMAIL_HEADER, b'erik@axiara.ai'), type='websocket'), frozenset({'erik@axiara.ai'}), None),
        ({'type': 'lifespan'}, frozenset({'erik@axiara.ai'}), None),
    ],
    ids=['prefixed', 'bare', 'uppercase', 'off-list', 'no-header', 'empty-allowlist', 'websocket', 'lifespan'],
)
def test_which_requests_carry_a_role_worth_settling(scope: dict, allowlist: frozenset[str], expected) -> None:
    assert AdminAllowlistMiddleware(RecordingApp(), allowlist)._pending_email(scope) == expected


async def test_the_role_is_settled_after_the_inner_app_has_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """Order is the point: a first-ever signin creates the account inside that call.

    Checking the role before routing would be one request too early for exactly the person
    the allowlist exists to serve.
    """
    users = FakeUsers(FakeUser('u1', 'erik@axiara.ai', 'pending'))
    order: list[str] = []

    async def inner(scope, receive, send):
        order.append(f'inner:{users._by_email["erik@axiara.ai"].role}')

    monkeypatch.setitem(sys.modules, 'open_webui.models.users', _module_exposing(Users=users))
    middleware = AdminAllowlistMiddleware(inner, frozenset({'erik@axiara.ai'}))

    await middleware(http_scope((EMAIL_HEADER, b'accounts.google.com:erik@axiara.ai')), None, None)

    assert order == ['inner:pending'], 'the role was settled before the account could exist'
    assert users.promotions == [('u1', 'admin')]


async def test_a_settled_address_costs_no_further_database_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    users = FakeUsers(FakeUser('u1', 'erik@axiara.ai', 'pending'))
    monkeypatch.setitem(sys.modules, 'open_webui.models.users', _module_exposing(Users=users))
    middleware = AdminAllowlistMiddleware(RecordingApp(), frozenset({'erik@axiara.ai'}))
    scope = http_scope((EMAIL_HEADER, b'accounts.google.com:erik@axiara.ai'))

    for _ in range(3):
        await middleware(scope, None, None)

    assert users.lookups == ['erik@axiara.ai'], 'the per-process settled set is not holding'


async def test_a_failure_to_settle_is_swallowed_and_retried_next_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """A permission that cannot be read must not turn a working page into a 500 — and the
    address must not be recorded as settled, or the retry never happens."""
    monkeypatch.setitem(sys.modules, 'open_webui.models.users', _module_exposing(Users=ExplodingUsers()))
    inner = RecordingApp()
    middleware = AdminAllowlistMiddleware(inner, frozenset({'erik@axiara.ai'}))
    scope = http_scope((EMAIL_HEADER, b'accounts.google.com:erik@axiara.ai'))

    await middleware(scope, None, None)
    await middleware(scope, None, None)

    assert len(inner.scopes) == 2, 'the request must still be served'
    assert middleware._settled == set(), 'a failed attempt was recorded as settled, so it never retries'


async def test_an_off_list_request_never_imports_the_vendor_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """The import is lazy so a process that never promotes anyone never pays for it."""

    def explode(*args, **kwargs):  # pragma: no cover - asserted by not being called
        raise AssertionError('open_webui.models.users was imported for an off-list request')

    monkeypatch.setitem(sys.modules, 'open_webui.models.users', _module_exposing(__getattr__=explode))
    inner = RecordingApp()

    await AdminAllowlistMiddleware(inner, frozenset({'erik@axiara.ai'}))(
        http_scope((EMAIL_HEADER, b'someone@example.com')), None, None
    )

    assert len(inner.scopes) == 1


def _module_exposing(**attributes):
    """A throwaway stand-in for a vendor module, for `monkeypatch.setitem(sys.modules, ...)`.

    `from open_webui.models.users import Users` resolves out of `sys.modules` on the full
    dotted name without importing a parent, so one entry is enough and the vendor tree is
    never touched — which is what lets this file run under `--only-group dev`.
    """
    import types

    module = types.ModuleType('open_webui.models.users')
    for name, value in attributes.items():
        setattr(module, name, value)
    return module
