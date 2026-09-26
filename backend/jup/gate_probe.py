"""`gate_probe`: an `external` tool that does nothing, so the approval gate can be proven live.

ADR-0013's gate is only as trustworthy as the last time someone watched it stop a call. Proving it
with a real External Call would mean causing a real effect, so this tool has none: it returns its
own arguments and touches nothing. It is classed `external` in its source (`tools/gate_probe.py`),
so every call to it goes through the gate, and it stays in production as a regression check for
the card, rejection, timeout and unattended refusal (A5 + E5 spec, user story 31).

Admin-only twice over: the stored tool has no access grants, and this module refuses any other
role, the same way `portfolio_status` does.
"""

from jup.portfolio import OPERATING_LAYER_ROLE

REFUSAL = (
    'Refused: gate_probe is an admin-only test tool, and this account is not an admin. '
    'Tell the user plainly; it has no effect for anyone to miss.'
)


def gate_probe(role: str | None, message: str = '', token: str = '') -> str:
    """Echo the arguments back. That is the whole of it."""
    if role != OPERATING_LAYER_ROLE:
        return REFUSAL
    return f'gate_probe ran and did nothing. It received message={message!r} token={token!r}.'
