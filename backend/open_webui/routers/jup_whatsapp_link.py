"""Linking a WhatsApp number from the web app (E9.2, #103; spec #101).

A signed-in user holding `jup.channel.use` gets a Link Code here and sends it from WhatsApp; the
gateway then calls `POST /api/jup/channel/link` (`routers/jup_channel.py`), which writes the Mapping.
This router only issues the code, reports the link (`•••• 1234`, since when) and removes it.

Unlinking needs no grant: someone whose grant was revoked must still be able to cut a lost phone off.

Mounted at `/api/v1/whatsapp-link` (`main.py`), outside the Channel prefix the IAP middleware keeps
for the gateway.
"""

from __future__ import annotations

import asyncio
import copy
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from jup.channel import DEFAULT_PERMISSIONS, may_use_channel
from jup.channel_links import links, web
from jup.governance import audit
from jup.iap_identity import channels_enabled
from open_webui.utils.access_control import get_permissions
from open_webui.utils.auth import get_verified_user

router = APIRouter()


async def may_link(user=Depends(get_verified_user)) -> bool:
    """The grant, with the Channel kill switch on: without both, a link could never be used."""
    if not channels_enabled():
        return False
    return may_use_channel(await get_permissions(user.id, copy.deepcopy(DEFAULT_PERMISSIONS)))


def _engine() -> Any:
    from jup.channel_links.migrate import schema_ready
    from open_webui.internal.db import engine

    if not schema_ready():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, 'whatsapp_link_unavailable')
    return engine


def _now_ms() -> int:
    return int(time.time() * 1000)


@router.get('')
async def get_link(user=Depends(get_verified_user), allowed: bool = Depends(may_link)) -> dict[str, Any]:
    """`available` False hides the section; else whether a number is linked, its last four digits, since when."""
    if not allowed:
        return {'available': False}
    found = await asyncio.to_thread(links.status, _engine(), user.id)
    if found is None:
        return {'available': True, 'linked': False}
    return {'available': True, 'linked': True, 'hint': found.hint, 'since': found.since}


@router.post('/code')
async def issue_code(user=Depends(get_verified_user), allowed: bool = Depends(may_link)) -> dict[str, Any]:
    """A fresh ten-minute Link Code, replacing any earlier one, with the `wa.me` link that sends it."""
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'whatsapp_link_not_allowed')
    issued = await asyncio.to_thread(links.issue_code, _engine(), user.id, _now_ms())
    return {
        'code': issued.code,
        'expires_at': issued.expires_at,
        'wa_link': web.wa_link(web.whatsapp_number(), issued.code),
        'disclosure': web.DISCLOSURE,
    }


@router.delete('')
async def unlink(user=Depends(get_verified_user)) -> dict[str, bool]:
    """Cuts the linked number off at once. Needs no grant."""
    identity_hash = await asyncio.to_thread(links.unlink, _engine(), user.id)
    if identity_hash is None:
        return {'unlinked': False}
    audit('channel_link', channel=links.WHATSAPP, identity_hash=identity_hash, user=user.id, outcome='unlinked')
    return {'unlinked': True}
