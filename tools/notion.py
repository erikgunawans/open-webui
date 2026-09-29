"""
title: Notion (read-only)
author: JUP operating layer (ent-os-new-jup)
version: 1.0.0
risk_class: read
description: Read-only. Searches and reads the Notion pages Erik has shared with the JUP integration: his JUP work notes and meeting notes (D25).
"""

# This file is the tool as stored in the app's DB; deploy/gcp/sync-tools.ts pushes it. Tool code
# is exec'd in the backend where nothing tests it, so it stays a wrapper: every rule, the admin
# gate included, lives in `jup.notion` and is tested there (tests/test_jup_notion.py).

from jup.notion import read_notion_page as _read_notion_page
from jup.notion import search_notion as _search_notion


class Tools:
    async def search_notion(self, query: str, __user__: dict | None = None) -> str:
        """
        Search Erik's Notion notes (JUP work notes and meeting notes) by words from a page's title or text. Returns matching pages with title, link and page id. Use it when the user asks about something recorded in Notion, such as a meeting's notes or a work note; then read the page before quoting it.
        :param query: Words to look for, for example "rapat direksi september" or "SPBG".
        :return: Matching pages, or a message saying why Notion could not be searched.
        """
        return await _search_notion((__user__ or {}).get('role'), query)

    async def read_notion_page(self, page: str, __user__: dict | None = None) -> str:
        """
        Read one Notion page as text: its title, its link and its content. Cite the page title and link in the answer. Sub-pages are named but not read; read them separately if needed.
        :param page: The page id from search_notion, or a notion.so page link.
        :return: The page text starting with its title and link, or a message saying why it could not be read.
        """
        return await _read_notion_page((__user__ or {}).get('role'), page)
