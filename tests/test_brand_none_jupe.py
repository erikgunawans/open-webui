"""The app is branded None-JUPe: its name carries no suffix and its marks are the logo system's.

Both halves fail silently. An upstream merge that restores `WEBUI_NAME += ' (Open WebUI)'` renames
the product back without an error, and a static asset edited in one copy but not the other serves
differently depending on which directory the build picks up. Removing the branding rests on LICENSE
clause 4 and the fifty-user ceiling (ADR-0001).
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
ENV = ROOT / 'backend' / 'open_webui' / 'env.py'
STATIC_DIRS = (ROOT / 'static' / 'static', ROOT / 'backend' / 'open_webui' / 'static')
ASSETS = (
    'none-jupe-mark.png',
    'none-jupe-mark-white.png',
    'favicon.png',
    'favicon-96x96.png',
    'favicon.ico',
    'favicon.svg',
    'logo.png',
    'splash.png',
    'splash-dark.png',
    'apple-touch-icon.png',
    'web-app-manifest-192x192.png',
    'web-app-manifest-512x512.png',
    'site.webmanifest',
)


def test_the_name_is_not_suffixed_with_open_webui() -> None:
    assert "WEBUI_NAME += ' (Open WebUI)'" not in ENV.read_text(encoding='utf-8')


def test_deploy_names_the_app_none_jupe() -> None:
    deploy = (ROOT / 'deploy' / 'gcp' / 'deploy.sh').read_text(encoding='utf-8')
    assert 'WEBUI_NAME: "None-JUPe"' in deploy


@pytest.mark.parametrize('name', ASSETS)
def test_both_static_copies_serve_the_same_asset(name: str) -> None:
    first, second = (directory / name for directory in STATIC_DIRS)
    assert first.read_bytes() == second.read_bytes(), f'{name} differs between the two static dirs'


def test_the_bangjayaos_marks_are_gone() -> None:
    for directory in STATIC_DIRS:
        assert not list(directory.glob('bangjayaos-*')), f'BangJayaOS mark left in {directory}'


def test_the_asisten_jup_marks_are_gone() -> None:
    for directory in STATIC_DIRS:
        assert not list(directory.glob('asisten-jup-*')), f'Asisten JUP mark left in {directory}'
