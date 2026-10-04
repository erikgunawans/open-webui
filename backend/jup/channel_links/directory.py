"""The Mappings as the IAP middleware reads them: `jup.iap_identity.LinkDirectory` on the vendor engine.

`jup.channel_links.links` is synchronous, like the contract tables' code, so each call runs in a
worker thread. Until the Mapping graph has reached its head in this process, every call raises:
the middleware turns that into a refusal (`lookup_failed`), never an admission.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any


def _vendor_engine() -> Any:
    from open_webui.internal.db import engine

    return engine


class EngineDirectory:
    def __init__(self, engine: Callable[[], Any] = _vendor_engine, now_ms: Callable[[], int] | None = None) -> None:
        self._engine = engine
        self._now_ms = now_ms or (lambda: int(time.time() * 1000))

    def _ready_engine(self) -> Any:
        from jup.channel_links.migrate import schema_ready

        if not schema_ready():
            raise RuntimeError('the Channel Mapping schema is not ready')
        return self._engine()

    async def resolve(self, identity_hash: str) -> str | None:
        from jup.channel_links import links

        return await asyncio.to_thread(links.resolve, self._ready_engine(), identity_hash)

    async def code_owner(self, code: str, identity_hash: str) -> str | None:
        from jup.channel_links import links

        return await asyncio.to_thread(links.code_owner, self._ready_engine(), code, identity_hash, self._now_ms())
