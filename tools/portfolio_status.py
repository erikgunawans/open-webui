"""
title: JUP portfolio status
author: JUP operating layer (ent-os-new-jup)
version: 1.0.0
risk_class: read
description: Read-only. Current Gate, blockers, engagements and tier-labelled figures for JUP projects, computed from the gate-assessment records.
"""

# This file is the tool as stored in the app's DB; deploy/gcp/sync-tools.ts pushes it. Tool code
# is exec'd in the backend where nothing tests it, so it stays a wrapper: every rule, the admin
# gate included, lives in `jup.portfolio_tool` and is tested there.

from jup.portfolio_tool import portfolio_status as _portfolio_status


class Tools:
    def portfolio_status(self, project: str = '', __user__: dict | None = None) -> str:
        """
        Get the current stage-gate status of JUP projects from the gate-assessment records: the Current Gate (computed, never stored), every assessment with verdict, date and signer, the requirements blocking each project, the engagements it waits on and their stage, and figures grouped by certainty tier. Use this for any question about where a JUP project stands, what is blocking it, or which gate it holds. Prefer it over searching documents for gate state.
        :param project: Optional project id or name to filter by, for example "spbg" or "gas-spbg-reactivation". Leave empty for the whole portfolio.
        :return: Markdown describing the portfolio, including what it does not prove.
        """
        return _portfolio_status((__user__ or {}).get('role'), project)
