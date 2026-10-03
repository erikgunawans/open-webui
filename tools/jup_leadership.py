"""
title: Ruang Pimpinan JUP (read-only)
author: JUP operating layer (ent-os-new-jup)
version: 1.1.0
risk_class: read
description: Read-only. Reads what Ruang Pimpinan shows this user: the Board view (Direksi & Komisaris) and the RKA view (RKA & Realisasi), with figures, assumptions, follow-ups and their source slides.
"""

# This file is the tool as stored in the app's DB; deploy/gcp/sync-tools.ts pushes it. Tool code
# is exec'd in the backend where nothing tests it, so it stays a wrapper: every rule — the page's
# grants, the dataset path, citations — lives in `jup.leadership.tool` and is tested there
# (tests/test_leadership_tool.py).

from jup.leadership.tool import read_leadership as _read_leadership


class Tools:
    async def read_ruang_pimpinan(
        self, view: str = '', __user__: dict | None = None, __chat_id__: str | None = None
    ) -> str:
        """
        Read Ruang Pimpinan, JUP's leadership room, as this user is allowed to see it: "board" is the Direksi & Komisaris view (realisasi vs anggaran, arahan rapat, tindak lanjut), "rka" is the RKA & Realisasi view (RKA 2027 targets: pendapatan, laba bersih, margin, arus kas, and the key drivers such as WTP KBB, CNG, SPBE, biomassa, pendanaan). Use it for any question about board figures, the RKA, targets, assumptions or follow-ups. Cite the source file and slides it gives, and say the figures are a draft and unverified.
        :param view: "board", "rka", or empty for every view this user may read.
        :return: The views as text, or a message saying why they cannot be shown.
        """
        return await _read_leadership(__user__, view, chat_id=__chat_id__)
