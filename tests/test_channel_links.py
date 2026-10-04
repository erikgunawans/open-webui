"""Linking a WhatsApp number (E9.1, #101): the Mapping graph, and `jup.channel_links.links` through
its functions on a scratch database with a fixed clock.

Runs on SQLite, and on Postgres too when `JUP_TEST_POSTGRES_URL` names one
(`postgresql+psycopg://…`). Needs the runtime (alembic, sqlalchemy): skipped under `--only-group dev`.
"""

import os
from pathlib import Path

import pytest

# A skip mark would not stop the imports below.
pytest.importorskip('sqlalchemy', reason='the runtime tree is not installed')
pytest.importorskip('alembic', reason='the runtime tree is not installed')

from jup.channel_links import links, migrate, models  # noqa: E402

NOW = 1_790_000_000_000
MINUTE = 60_000
A = 'a' * 64
B = 'b' * 64


def _engines(tmp_path: Path):
    from sqlalchemy import create_engine

    yield 'sqlite', create_engine(f'sqlite:///{tmp_path / "links.db"}')
    url = os.environ.get('JUP_TEST_POSTGRES_URL')
    if url:
        engine = create_engine(url)
        with engine.begin() as conn:
            for table in ('jup_channel_link', 'jup_channel_link_code', 'jup_channel_link_failure'):
                conn.exec_driver_sql(f'DROP TABLE IF EXISTS {table}')
            conn.exec_driver_sql(f'DROP TABLE IF EXISTS {migrate.VERSION_TABLE}')
        yield 'postgres', engine


@pytest.fixture(params=['sqlite', 'postgres'])
def engine(request, tmp_path: Path):
    for name, candidate in _engines(tmp_path):
        if name == request.param:
            assert migrate.run_channel_link_migrations(candidate) is True
            return candidate
    pytest.skip('JUP_TEST_POSTGRES_URL is not set')


def codes(*values: str):
    it = iter(values)
    return lambda: next(it)


# --- the graph -----------------------------------------------------------------------------------


def test_the_graph_reaches_head_twice_and_matches_the_models(engine) -> None:
    from sqlalchemy import inspect, text

    assert migrate.run_channel_link_migrations(engine) is True
    with engine.connect() as conn:
        assert [r[0] for r in conn.execute(text(f'SELECT version_num FROM {migrate.VERSION_TABLE}'))] == ['jw0001']
    inspector = inspect(engine)
    assert not {'alembic_version', 'jup_alembic_version', 'jup_contracts_alembic_version'} & set(
        inspector.get_table_names()
    )
    for table in models.metadata.sorted_tables:
        columns = {c['name']: c['nullable'] for c in inspector.get_columns(table.name)}
        assert columns == {c.name: c.nullable for c in table.columns}, table.name
        assert set(inspector.get_pk_constraint(table.name)['constrained_columns']) == {
            c.name for c in table.primary_key
        }


def test_a_failure_is_contained() -> None:
    class _Broken:
        def begin(self):
            raise RuntimeError('database is down')

    assert migrate.run_channel_link_migrations(_Broken()) is False
    assert migrate.schema_ready() is False


# --- issuing and claiming ------------------------------------------------------------------------


def test_a_sent_code_links_the_number_to_the_user_who_issued_it(engine) -> None:
    issued = links.issue_code(engine, 'u-erik', NOW, draw=codes('482913'))
    assert issued.code == '482913'
    assert issued.expires_at == NOW + 10 * MINUTE

    assert links.code_owner(engine, '482913', A, NOW + MINUTE) == 'u-erik'
    claimed = links.claim(engine, '482913', A, '1234', NOW + MINUTE)

    assert claimed == links.Claimed(user_id='u-erik', relinked=False)
    assert links.resolve(engine, A) == 'u-erik'
    assert links.status(engine, 'u-erik') == links.LinkStatus(hint='1234', since=NOW + MINUTE)


def test_the_code_is_not_stored_in_clear(engine) -> None:
    from sqlalchemy import select

    links.issue_code(engine, 'u-erik', NOW, draw=codes('482913'))
    with engine.connect() as conn:
        stored = conn.execute(select(models.link_code.c.code_hash)).scalar_one()
    assert '482913' not in stored and len(stored) == 64


def test_a_code_is_spent_once(engine) -> None:
    links.issue_code(engine, 'u-erik', NOW, draw=codes('482913'))
    assert links.claim(engine, '482913', A, '1234', NOW) is not None

    assert links.claim(engine, '482913', B, '5678', NOW) is None
    assert links.code_owner(engine, '482913', B, NOW) is None
    assert links.resolve(engine, B) is None


def test_an_expired_code_does_nothing(engine) -> None:
    links.issue_code(engine, 'u-erik', NOW, draw=codes('482913'))
    later = NOW + 10 * MINUTE

    assert links.code_owner(engine, '482913', A, later) is None
    assert links.claim(engine, '482913', A, '1234', later) is None


def test_a_new_code_replaces_the_users_old_one(engine) -> None:
    links.issue_code(engine, 'u-erik', NOW, draw=codes('111111'))
    links.issue_code(engine, 'u-erik', NOW, draw=codes('222222'))

    assert links.code_owner(engine, '111111', A, NOW) is None
    assert links.code_owner(engine, '222222', A, NOW) == 'u-erik'


def test_a_code_value_taken_by_another_user_is_drawn_again(engine) -> None:
    links.issue_code(engine, 'u-erik', NOW, draw=codes('111111'))
    issued = links.issue_code(engine, 'u-rully', NOW, draw=codes('111111', '333333'))

    assert issued.code == '333333'
    assert links.code_owner(engine, '111111', A, NOW) == 'u-erik'


def test_a_new_number_replaces_the_users_old_one(engine) -> None:
    links.issue_code(engine, 'u-erik', NOW, draw=codes('111111'))
    links.claim(engine, '111111', A, '1234', NOW)
    links.issue_code(engine, 'u-erik', NOW, draw=codes('222222'))

    claimed = links.claim(engine, '222222', B, '5678', NOW)

    assert claimed == links.Claimed(user_id='u-erik', relinked=True)
    assert links.resolve(engine, A) is None
    assert links.resolve(engine, B) == 'u-erik'


def test_a_number_proven_by_another_user_moves_to_them(engine) -> None:
    links.issue_code(engine, 'u-erik', NOW, draw=codes('111111'))
    links.claim(engine, '111111', A, '1234', NOW)
    links.issue_code(engine, 'u-rully', NOW, draw=codes('222222'))

    claimed = links.claim(engine, '222222', A, '1234', NOW)

    assert claimed == links.Claimed(user_id='u-rully', relinked=True)
    assert links.resolve(engine, A) == 'u-rully'
    assert links.status(engine, 'u-erik') is None


def test_unlinking_removes_the_link_and_names_the_number_hash(engine) -> None:
    links.issue_code(engine, 'u-erik', NOW, draw=codes('111111'))
    links.claim(engine, '111111', A, '1234', NOW)

    assert links.unlink(engine, 'u-erik') == A
    assert links.resolve(engine, A) is None
    assert links.unlink(engine, 'u-erik') is None


# --- guessing ------------------------------------------------------------------------------------


def test_five_wrong_codes_stop_the_sender_even_with_the_right_one(engine) -> None:
    links.issue_code(engine, 'u-erik', NOW, draw=codes('482913'))
    for guess in ('000001', '000002', '000003', '000004', '000005'):
        assert links.code_owner(engine, guess, A, NOW) is None

    assert links.code_owner(engine, '482913', A, NOW + MINUTE) is None
    # Another sender is not affected, and the window passes.
    assert links.code_owner(engine, '482913', B, NOW + MINUTE) == 'u-erik'
    later = NOW + 10 * MINUTE + 1
    links.issue_code(engine, 'u-erik', later, draw=codes('654321'))
    assert links.code_owner(engine, '654321', A, later) == 'u-erik'


@pytest.mark.parametrize(
    ('code', 'identity'),
    [('48291', A), ('4829134', A), ('48291a', A), ('482913', 'A' * 64), ('482913', 'a' * 63), ('482913', '')],
)
def test_malformed_input_is_refused_without_a_lookup(engine, code, identity) -> None:
    links.issue_code(engine, 'u-erik', NOW, draw=codes('482913'))
    assert links.code_owner(engine, code, identity, NOW) is None


def test_claim_refuses_a_malformed_hint(engine) -> None:
    links.issue_code(engine, 'u-erik', NOW, draw=codes('482913'))
    with pytest.raises(ValueError):
        links.claim(engine, '482913', A, '+62812', NOW)
