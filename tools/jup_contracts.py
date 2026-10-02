"""
title: Kontrak JUP (read-only)
author: JUP operating layer (ent-os-new-jup)
version: 1.0.0
risk_class: read
description: Read-only. Searches and reads JUP's contract cards (drafted from the scanned agreements in SCAN PERJANJIAN) and, where allowed, their OCR pages.
"""

# This file is the tool as stored in the app's DB; deploy/gcp/sync-tools.ts pushes it. Tool code
# is exec'd in the backend where nothing tests it, so it stays a wrapper: every rule — the reader's
# grants, withheld fields, masking of individuals — lives in `jup.contracts.tool` and is tested there
# (tests/test_contract_tool.py).

from jup.contracts.tool import get_contract as _get_contract
from jup.contracts.tool import read_contract_pages as _read_contract_pages
from jup.contracts.tool import search_contracts as _search_contracts


class Tools:
    async def search_contracts(
        self,
        query: str = '',
        ends_within_days: int | None = None,
        state: str | None = None,
        __user__: dict | None = None,
    ) -> str:
        """
        Search JUP's contract cards by partner, contract number, title, document type or words in the card. Returns up to ten matches, each with its reference in square brackets, partner, number, end date when known, and the card's review state. Use it for any question about JUP's agreements (PKS, addenda, gas sale, land lease, loans). Then read the card with get_contract before answering.
        :param query: Words that must all appear, for example "PAM Jaya" or "sewa lahan Rorotan". Leave empty to list by the other filters.
        :param ends_within_days: Only contracts whose recorded end date falls within this many days from today, for example 180.
        :param state: Only cards in this review state: "draft", "approved" or "returned".
        :return: Matching contracts, or a message saying why none can be shown.
        """
        return await _search_contracts(__user__, query, ends_within_days, state)

    async def get_contract(self, ref: str, __user__: dict | None = None) -> str:
        """
        Read one contract card: partner, number, title, dates, rights and obligations, value and payment, term and renewal, termination, default and damages, confidentiality, force majeure, dispute resolution, validity, and related documents, each with its source page. Always tell the user the card's review state, and cite the reference and page numbers. Fields the tool marks as withheld must be reported as withheld, never guessed.
        :param ref: The contract reference from search_contracts, for example "0042".
        :return: The card, or a message saying why it cannot be shown.
        """
        return await _get_contract(__user__, ref)

    async def read_contract_pages(self, ref: str, pages: str, __user__: dict | None = None) -> str:
        """
        Read the OCR text of up to five pages of one contract, to quote a clause or check a card field against its source. Cite the page numbers.
        :param ref: The contract reference, for example "0042".
        :param pages: The pages, for example "3" or "3-5".
        :return: The page text, or a message saying why it cannot be shown.
        """
        return await _read_contract_pages(__user__, ref, pages)
