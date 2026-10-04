"""Channel Mappings that ent-os keeps itself: a WhatsApp number, as the gateway's HMAC, linked to one user (E9, #101).

Teams needs no table: the gateway resolves an Entra id to an email through Graph. WhatsApp has no
company identity, so a signed-in user proves a number is theirs by sending a Link Code from it, and
the Mapping is stored here. The number itself never reaches ent-os; only its HMAC (computed in the
gateway, one key for every Channel) and its last four digits, so the web app can say which number is
linked.

The IAP middleware resolves a Mapping before routing (ADR-0012 amendment 2): the gateway names a
sender as `whatsapp:<hash>`, or, on the link path only, as `link-code:<code>:<hash>`.
"""
