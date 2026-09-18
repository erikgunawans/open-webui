# Track upstream Open WebUI, rebasing quarterly

We follow `upstream/main` and rebase onto each minor release, quarterly. Every patch against vendor
code (ADR-0002) stays minimal and surgical precisely because it must survive that rebase.

Pinning to v0.11.3 and taking security fixes by hand was rejected: a BUMD deployment sitting on an
unpatched version is the exact finding that fails the security review this system exists to pass. A
hard fork was rejected because we are not rebuilding RAG, 13 vector stores, 22 search providers and
the admin surface in order to own them.

## Consequences

A standing quarterly job with a named owner — a commitment, not an intention.

**ADR-0002 depends on this decision.** Its attachment point was chosen partly for low upstream churn
(`utils/chat.py`, nine touches in twelve months), and that reasoning holds only while we rebase. If
this ADR is ever reversed, revisit ADR-0002: the cleanest attachment point and the most stable one
are not the same file.

**The check to run after every rebase** is `uv run --only-group dev pytest tests/test_boot.py`: a
fork migration colliding with an upstream one leaves alembic with two heads, and since migrations
run at config-import time the application does not start at all. Tracked as #8.
