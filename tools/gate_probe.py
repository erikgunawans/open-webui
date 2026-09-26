"""
title: JUP gate probe
author: JUP operating layer (ent-os-new-jup)
version: 1.0.0
risk_class: external
description: Admin-only test tool. Does nothing except echo its arguments; classed external so every call goes through the approval gate.
"""

# This file is the tool as stored in the app's DB; deploy/gcp/sync-tools.ts pushes it. It stays a
# wrapper: the admin check and the echo live in `jup.gate_probe` and are tested there.
# `risk_class: external` above is the point of the tool (jup.tool_policy, ADR-0013).

from jup.gate_probe import gate_probe as _gate_probe


class Tools:
    def gate_probe(self, message: str = '', token: str = '', __user__: dict | None = None) -> str:
        """
        Admin-only test of JUP's approval gate. It has no effect of any kind: it only echoes its arguments. Call it only when an admin asks to test the approval gate.
        :param message: Any text to echo back.
        :param token: A made-up secret-looking value, to check that the approval card masks it. Never pass a real secret.
        :return: The arguments, echoed.
        """
        return _gate_probe((__user__ or {}).get('role'), message, token)
