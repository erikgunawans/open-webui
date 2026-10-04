# jup-gateway

The Channel gateway (E7, spec #84; E9, spec #101): it verifies a Teams or WhatsApp message, maps
the sender to one JUP user, and asks ent-os for the answer on that user's behalf through
`POST /api/jup/channel/turn`. Bun and TypeScript only.

- `src/teams.ts` — the inbound handler: Bot Framework token, JUP tenant only, 1:1 chats only, a
  200 at once, then typing, the turn and the reply. Refusals all get one neutral text.
- `src/entos.ts` — the ent-os client. IAP is in external-identities mode, so it signs in with an
  Identity Platform custom token signed as `jup-gateway` itself.
- `src/botframework.ts` — the real Teams adapters (token check, Bot Connector, Graph mapping).
- `src/whatsapp.ts` — the WhatsApp handler: Meta's `X-Hub-Signature-256` over the raw body, our
  phone number id only, a 200 at once, redeliveries dropped by message id, then read + typing and
  either `hubungkan <6 digits>` (link, on behalf of `link-code:<code>:<hash>`) or a turn (on behalf
  of `whatsapp:<hash>`; ent-os resolves the number's hash to the user, ADR-0012 amendment 2).
- `src/meta.ts` — the real WhatsApp adapter (Cloud API v25.0 sender).
- `src/hash.ts` — HMAC-SHA256 of identities and conversations; raw Teams ids and phone numbers
  never reach ent-os.

```sh
bun install
bun test                 # handler and client tests, with fakes
bun run typecheck
bun run dev              # GATEWAY_DEV=1: no token/signature check, replies printed, DEV_MAPPING=oid=email,…
```

Production settings (#90): `JUP_TENANT_ID`, `BOT_APP_ID`, `BOT_APP_SECRET`, `ENTOS_URL`,
`GATEWAY_SERVICE_ACCOUNT`, `IDENTITY_PLATFORM_API_KEY`, `GATEWAY_HMAC_KEY`. WhatsApp (#105):
`WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`;
until all four are set, `/api/whatsapp` answers 401.
