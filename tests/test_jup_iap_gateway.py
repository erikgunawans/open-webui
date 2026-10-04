"""The channel gateway acts only on behalf of a mapped user, never as itself (E7.2, #86).

ADR-0012's amendment of 2026-10-04 names the tests its implementation must carry, so that a lost
auth rule fails here rather than in production. They run at the ASGI seam, as the rest of the IAP
login's tests do (`test_jup_iap_identity.py`): a raw scope in, a recording inner app, and the user
lookup and grant check injected, so no runtime tree is needed.

The fifth test in the ADR (IAP overwrites a client-supplied identity header) is a property of the
live load balancer and is checked there, not assumed here.
"""

import json

import pytest

from jup.governance import CHANNEL_LINK_STATE_ATTR, CHANNEL_TURN_STATE_ATTR, CHANNEL_USER_STATE_ATTR
from jup.iap_identity import (
    CHANNEL_API_PREFIX,
    CHANNELS_ENABLED_ENV,
    GATEWAY_PRINCIPAL_ENV,
    LINK_PATH,
    ON_BEHALF_OF_HEADER,
    IapIdentityHeaderMiddleware,
)

EMAIL_HEADER = b'x-goog-authenticated-user-email'
ID_HEADER = b'x-goog-authenticated-user-id'
GATEWAY = 'jup-gateway@jup-ops.iam.gserviceaccount.com'
TURN_PATH = f'{CHANNEL_API_PREFIX}turn'
ON = {GATEWAY_PRINCIPAL_ENV: GATEWAY, CHANNELS_ENABLED_ENV: 'true'}


class FakeUser:
    def __init__(self, id: str, email: str, role: str = 'admin') -> None:
        self.id = id
        self.email = email
        self.role = role


ERIK = FakeUser('u-erik', 'erik@axiara.ai')
STAFF = FakeUser('u-staff', 'staf@jakarta-utilitas.com', role='user')
PENDING = FakeUser('u-new', 'baru@jakarta-utilitas.com', role='pending')


class FakeUsers:
    """Stands in for `open_webui.models.users.Users`: lookups only, and it records any write."""

    def __init__(self, *users: FakeUser) -> None:
        self._by_email = {user.email: user for user in users}
        self.lookups: list[str] = []
        self.writes: list[str] = []

    async def get_user_by_email(self, email: str) -> FakeUser | None:
        self.lookups.append(email)
        return self._by_email.get(email)

    async def get_user_by_id(self, user_id: str) -> FakeUser | None:
        self.lookups.append(user_id)
        return next((user for user in self._by_email.values() if user.id == user_id), None)

    async def insert_new_user(self, *args, **kwargs) -> None:
        self.writes.append('insert_new_user')


class Granted:
    """The `jup.channel.use` lookup, true for the given user ids."""

    def __init__(self, *user_ids: str) -> None:
        self.user_ids = set(user_ids)

    async def __call__(self, user: FakeUser) -> bool:
        return user.id in self.user_ids


class RecordingApp:
    def __init__(self) -> None:
        self.scopes: list[dict] = []

    async def __call__(self, scope: dict, receive, send) -> None:
        self.scopes.append(scope)


class Sent:
    """Collects what the middleware sends when it answers by itself."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def __call__(self, message: dict) -> None:
        self.messages.append(message)

    @property
    def status(self) -> int:
        return self.messages[0]['status']

    @property
    def body(self) -> dict:
        return json.loads(b''.join(m.get('body', b'') for m in self.messages[1:]))


def scope(*headers: tuple[bytes, bytes], path: str = TURN_PATH, type: str = 'http') -> dict:
    return {'type': type, 'path': path, 'headers': list(headers)}


def as_gateway(on_behalf_of: str | None = None, *extra: tuple[bytes, bytes], path: str = TURN_PATH) -> dict:
    headers = [(EMAIL_HEADER, f'accounts.google.com:{GATEWAY}'.encode()), (ID_HEADER, b'accounts.google.com:1234')]
    if on_behalf_of is not None:
        headers.append((ON_BEHALF_OF_HEADER, on_behalf_of.encode()))
    return scope(*headers, *extra, path=path)


class FakeLinks:
    """Stands in for `jup.channel_links`: linked hashes, live codes, and the calls made."""

    def __init__(self, linked: dict[str, str] | None = None, codes: dict[str, str] | None = None) -> None:
        self.linked = linked or {}
        self.codes = codes or {}
        self.calls: list[tuple] = []

    async def resolve(self, identity_hash: str) -> str | None:
        self.calls.append(('resolve', identity_hash))
        return self.linked.get(identity_hash)

    async def code_owner(self, code: str, identity_hash: str) -> str | None:
        self.calls.append(('code_owner', code, identity_hash))
        return self.codes.get(code)


async def run(scope_: dict, *, env: dict | None = None, users: FakeUsers | None = None, granted=None, links=None):
    inner, sent = RecordingApp(), Sent()
    users = users if users is not None else FakeUsers(ERIK, STAFF, PENDING)
    middleware = IapIdentityHeaderMiddleware(
        inner,
        env=ON if env is None else env,
        users=users,
        may_use_channel=granted or Granted(ERIK.id),
        links=links if links is not None else FakeLinks(),
    )
    await middleware(scope_, None, sent)
    return inner, sent, users


def header(scope_: dict, name: bytes) -> list[bytes]:
    return [value for key, value in scope_['headers'] if key == name]


def refused(inner: RecordingApp, sent: Sent) -> bool:
    return not inner.scopes and sent.status == 403 and sent.body == {'detail': 'channel_refused'}


# --- the ADR's tests ------------------------------------------------------------------------------


async def test_1_the_gateway_as_itself_is_refused_and_no_account_is_made():
    inner, sent, users = await run(as_gateway())

    assert refused(inner, sent)
    assert users.writes == []
    assert users.lookups == []


@pytest.mark.parametrize('on_behalf_of', ['', '   '])
async def test_1_a_blank_on_behalf_of_value_is_the_gateway_as_itself(on_behalf_of):
    inner, sent, _ = await run(as_gateway(on_behalf_of))

    assert refused(inner, sent)


@pytest.mark.parametrize(
    'address',
    ['nobody@jakarta-utilitas.com', PENDING.email, STAFF.email],
    ids=['unknown', 'pending', 'ungranted'],
)
async def test_2_on_behalf_of_an_unknown_pending_or_ungranted_address_is_refused(address):
    inner, sent, users = await run(as_gateway(address))

    assert refused(inner, sent)
    assert users.writes == []


async def test_2_a_failed_lookup_refuses_rather_than_admitting():
    class Broken(FakeUsers):
        async def get_user_by_email(self, email):
            raise RuntimeError('database unreachable')

    inner, sent, _ = await run(as_gateway(ERIK.email), users=Broken())

    assert refused(inner, sent)


async def test_2_a_failed_grant_check_refuses_rather_than_admitting():
    async def broken(user):
        raise RuntimeError('database unreachable')

    inner, sent, _ = await run(as_gateway(ERIK.email), granted=broken)

    assert refused(inner, sent)


async def test_3_anyone_elses_on_behalf_of_header_is_stripped_and_they_stay_themselves():
    signed_in = scope(
        (EMAIL_HEADER, b'accounts.google.com:staf@jakarta-utilitas.com'),
        (ON_BEHALF_OF_HEADER, ERIK.email.encode()),
    )

    inner, _, users = await run(signed_in)

    (forwarded,) = inner.scopes
    assert header(forwarded, ON_BEHALF_OF_HEADER) == []
    assert header(forwarded, EMAIL_HEADER) == [b'staf@jakarta-utilitas.com']
    assert CHANNEL_TURN_STATE_ATTR not in (forwarded.get('state') or {})
    assert users.lookups == []


async def test_3_the_header_is_stripped_with_no_identity_at_all():
    inner, _, _ = await run(scope((ON_BEHALF_OF_HEADER, ERIK.email.encode()), path='/api/v1/chats'))

    (forwarded,) = inner.scopes
    assert header(forwarded, ON_BEHALF_OF_HEADER) == []


async def test_3_the_header_is_stripped_when_no_gateway_is_configured():
    signed_in = scope((EMAIL_HEADER, b'staf@jakarta-utilitas.com'), (ON_BEHALF_OF_HEADER, ERIK.email.encode()))

    inner, _, _ = await run(signed_in, env={})

    (forwarded,) = inner.scopes
    assert header(forwarded, ON_BEHALF_OF_HEADER) == []


@pytest.mark.parametrize('switch', [None, '', 'false', '0', 'no'])
async def test_4_the_kill_switch_off_refuses_the_gateway_for_everyone(switch):
    env = {GATEWAY_PRINCIPAL_ENV: GATEWAY}
    if switch is not None:
        env[CHANNELS_ENABLED_ENV] = switch

    inner, sent, users = await run(as_gateway(ERIK.email), env=env)

    assert refused(inner, sent)
    assert users.lookups == []


@pytest.mark.parametrize(
    'path',
    ['/api/v1/chats/new', '/api/jup/channel', '/api/jup/channelx/turn', f'{CHANNEL_API_PREFIX}../../v1/chats', '/'],
)
async def test_the_gateway_off_the_channel_prefix_is_refused(path):
    inner, sent, users = await run(as_gateway(ERIK.email, path=path))

    assert refused(inner, sent)
    assert users.lookups == []


async def test_the_gateway_on_a_websocket_is_closed():
    inner, sent, _ = await run({**as_gateway(ERIK.email), 'type': 'websocket'})

    assert inner.scopes == []
    assert sent.messages == [{'type': 'websocket.close', 'code': 1008}]


# --- a mapped, granted user -----------------------------------------------------------------------


async def test_a_mapped_granted_user_is_rewritten_and_marked():
    inner, _, users = await run(as_gateway(ERIK.email, (b'content-type', b'application/json')))

    (forwarded,) = inner.scopes
    assert header(forwarded, EMAIL_HEADER) == [b'erik@axiara.ai']
    assert header(forwarded, ON_BEHALF_OF_HEADER) == []
    # The gateway's own subject must not ride along with the director's address.
    assert header(forwarded, ID_HEADER) == []
    assert header(forwarded, b'content-type') == [b'application/json']
    assert forwarded['state'][CHANNEL_TURN_STATE_ATTR] is True
    assert forwarded['state'][CHANNEL_USER_STATE_ATTR] == ERIK.id
    assert users.lookups == ['erik@axiara.ai']
    assert users.writes == []


async def test_the_address_is_matched_case_insensitively_and_the_stored_one_is_used():
    inner, _, users = await run(as_gateway('  Erik@Axiara.AI '))

    (forwarded,) = inner.scopes
    assert users.lookups == ['erik@axiara.ai']
    assert header(forwarded, EMAIL_HEADER) == [ERIK.email.encode()]


async def test_the_principal_is_matched_case_insensitively():
    env = {GATEWAY_PRINCIPAL_ENV: GATEWAY.upper(), CHANNELS_ENABLED_ENV: '1'}

    inner, _, _ = await run(as_gateway(ERIK.email), env=env)

    (forwarded,) = inner.scopes
    assert header(forwarded, EMAIL_HEADER) == [ERIK.email.encode()]


async def test_the_existing_request_state_is_kept_and_the_callers_scope_is_not_mutated():
    original = as_gateway(ERIK.email)
    original['state'] = {'other': 1}

    inner, _, _ = await run(original)

    (forwarded,) = inner.scopes
    assert forwarded['state'] == {'other': 1, CHANNEL_TURN_STATE_ATTR: True, CHANNEL_USER_STATE_ATTR: ERIK.id}
    assert original['state'] == {'other': 1}
    assert header(original, ON_BEHALF_OF_HEADER) == [ERIK.email.encode()]


async def test_the_mark_is_set_only_for_the_gateway():
    signed_in = scope((EMAIL_HEADER, b'accounts.google.com:erik@axiara.ai'))

    inner, _, _ = await run(signed_in)

    (forwarded,) = inner.scopes
    assert CHANNEL_TURN_STATE_ATTR not in (forwarded.get('state') or {})


async def test_a_director_calling_the_channel_prefix_directly_is_not_marked():
    """The route refuses an unmarked request, so a browser cannot make itself a Channel Turn."""
    inner, _, _ = await run(scope((EMAIL_HEADER, b'erik@axiara.ai'), path=TURN_PATH))

    (forwarded,) = inner.scopes
    assert CHANNEL_TURN_STATE_ATTR not in (forwarded.get('state') or {})


# --- the refusal's audit line ---------------------------------------------------------------------


async def test_a_refusal_is_audited_with_its_reason_and_never_the_address():
    lines: list[tuple[str, dict]] = []
    inner, sent = RecordingApp(), Sent()
    middleware = IapIdentityHeaderMiddleware(
        inner,
        env=ON,
        users=FakeUsers(ERIK, STAFF),
        may_use_channel=Granted(ERIK.id),
        audit=lambda event, **fields: lines.append((event, fields)),
    )

    await middleware(as_gateway(STAFF.email), None, sent)

    assert lines == [('channel_turn', {'outcome': 'refused', 'reason': 'not_granted', 'request_path': TURN_PATH})]
    assert '@' not in json.dumps(lines)
    assert sent.body == {'detail': 'channel_refused'}


async def test_the_refusal_reaches_the_real_audit_trail(tmp_path, monkeypatch):
    """No injected audit: the line must land in the governance file (`path` there is the file)."""
    trail = tmp_path / 'audit.jsonl'
    monkeypatch.setenv('JUP_GOVERNANCE_AUDIT', str(trail))
    inner, sent = RecordingApp(), Sent()
    middleware = IapIdentityHeaderMiddleware(inner, env=ON, users=FakeUsers(ERIK), may_use_channel=Granted())

    await middleware(as_gateway(ERIK.email), None, sent)

    (line,) = [json.loads(raw) for raw in trail.read_text().splitlines()]
    assert (line['event'], line['outcome'], line['reason'], line['request_path']) == (
        'channel_turn',
        'refused',
        'not_granted',
        TURN_PATH,
    )


# --- amendment 2: a WhatsApp number, and a Link Code (E9.1, #102) -------------------------------------

NUMBER = 'c' * 64
OTHER = 'd' * 64


async def test_a_linked_number_is_admitted_as_its_user_for_a_turn():
    links = FakeLinks(linked={NUMBER: ERIK.id})
    inner, _, _ = await run(as_gateway(f'whatsapp:{NUMBER}'), links=links)

    (forwarded,) = inner.scopes
    assert header(forwarded, EMAIL_HEADER) == [ERIK.email.encode()]
    assert forwarded['state'][CHANNEL_TURN_STATE_ATTR] is True
    assert forwarded['state'][CHANNEL_USER_STATE_ATTR] == ERIK.id
    assert CHANNEL_LINK_STATE_ATTR not in forwarded['state']


@pytest.mark.parametrize(
    'linked',
    [{}, {NUMBER: PENDING.id}, {NUMBER: STAFF.id}, {NUMBER: 'u-deleted'}],
    ids=['unlinked', 'pending', 'ungranted', 'deleted-user'],
)
async def test_6_an_unlinked_number_or_one_linked_to_an_unqualified_user_is_refused(linked):
    inner, sent, users = await run(as_gateway(f'whatsapp:{NUMBER}'), links=FakeLinks(linked=linked))

    assert refused(inner, sent)
    assert users.writes == []


async def test_a_link_code_admits_its_issuer_on_the_link_path_with_the_link_mark_only():
    links = FakeLinks(codes={'482913': ERIK.id})
    inner, _, _ = await run(as_gateway(f'link-code:482913:{NUMBER}', path=LINK_PATH), links=links)

    (forwarded,) = inner.scopes
    assert forwarded['state'][CHANNEL_LINK_STATE_ATTR] == {'code': '482913', 'identity_hash': NUMBER}
    assert forwarded['state'][CHANNEL_USER_STATE_ATTR] == ERIK.id
    assert CHANNEL_TURN_STATE_ATTR not in forwarded['state']
    assert links.calls == [('code_owner', '482913', NUMBER)]


@pytest.mark.parametrize('path', [TURN_PATH, f'{LINK_PATH}/', f'{CHANNEL_API_PREFIX}links'])
async def test_7_a_link_code_anywhere_but_the_link_path_is_refused_unlooked(path):
    links = FakeLinks(codes={'482913': ERIK.id})
    inner, sent, _ = await run(as_gateway(f'link-code:482913:{NUMBER}', path=path), links=links)

    assert refused(inner, sent)
    assert links.calls == []


async def test_8_a_code_the_directory_does_not_own_is_refused():
    # Expired, used, unknown and over-the-limit all reach the middleware as no owner.
    inner, sent, _ = await run(as_gateway(f'link-code:000000:{NUMBER}', path=LINK_PATH), links=FakeLinks())

    assert refused(inner, sent)


async def test_8_a_code_issued_by_a_user_who_lost_the_grant_is_refused():
    links = FakeLinks(codes={'482913': STAFF.id})
    inner, sent, _ = await run(as_gateway(f'link-code:482913:{NUMBER}', path=LINK_PATH), links=links)

    assert refused(inner, sent)


@pytest.mark.parametrize(
    'value',
    [
        f'whatsapp:{NUMBER.upper()}',
        f'whatsapp:{NUMBER[:-1]}',
        'whatsapp:',
        f'link-code:48291:{NUMBER}',
        f'link-code:482913:{NUMBER.upper()}',
        f'link-code:482913{NUMBER}',
        f'teams:{NUMBER}',
        f'mailto:{ERIK.email}',
    ],
)
async def test_9_a_malformed_value_is_refused_without_a_lookup(value):
    links = FakeLinks(linked={NUMBER: ERIK.id, NUMBER.upper(): ERIK.id}, codes={'482913': ERIK.id})
    path = LINK_PATH if value.startswith('link-code') else TURN_PATH
    inner, sent, users = await run(as_gateway(value, path=path), links=links)

    assert refused(inner, sent)
    assert links.calls == []
    assert users.lookups == []


async def test_a_failing_directory_refuses_rather_than_admitting():
    class Broken(FakeLinks):
        async def resolve(self, identity_hash):
            raise RuntimeError('the Channel Mapping schema is not ready')

    inner, sent, _ = await run(as_gateway(f'whatsapp:{NUMBER}'), links=Broken())

    assert refused(inner, sent)


async def test_the_kill_switch_refuses_a_linked_number_too():
    links = FakeLinks(linked={NUMBER: ERIK.id})
    inner, sent, _ = await run(as_gateway(f'whatsapp:{NUMBER}'), env={GATEWAY_PRINCIPAL_ENV: GATEWAY}, links=links)

    assert refused(inner, sent)
    assert links.calls == []
