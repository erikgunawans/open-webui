# Request to JUP IT: an Entra app registration for Asisten JUP sign-in

Asisten JUP (`https://non-jupe.jup.co.id`) will let JUP staff sign in with their existing Microsoft
365 account. Google Cloud Identity Platform connects to Entra ID over OpenID Connect. We need one
app registration in JUP's Entra tenant. ADR-0016 has the design.

## Please create

**Microsoft Entra admin center → App registrations → New registration**

| Field | Value |
|-------|-------|
| Name | `Asisten JUP` |
| Supported account types | **Accounts in this organizational directory only** (single tenant) |
| Redirect URI | Platform **Web**: `https://jup-ops.firebaseapp.com/__/auth/handler` |

Then:

1. **Certificates & secrets → New client secret.** 12 or 24 months. Note the expiry date: sign-in
   stops working when the secret expires.
2. **API permissions:** Microsoft Graph delegated `openid`, `email`, `profile` (usually present by
   default). Grant admin consent so staff are not asked individually.
3. **Token configuration:** make sure the ID token carries `email`. Each user's `mail` attribute in
   Entra must be their `@jakarta-utilitas.com` address, because that is the address the account is
   created under.
4. Optional, recommended: **Enterprise applications → Asisten JUP → Properties → Assignment
   required = Yes**, then assign only the staff who should have access. Without it, every account in
   the tenant can reach the sign-in step. The app still holds new accounts as pending until an
   admin approves them. If you turn this on, please assign `erik@jakarta-utilitas.com` first. That
   account signs in first, to test the setup before any other staff.

## Please send back

- **Directory (tenant) ID**
- **Application (client) ID**
- **Client secret value**, through a secure channel, not plain email or chat
- The secret's expiry date

## What changes for staff

Nothing needs installing. Staff open `https://non-jupe.jup.co.id`, choose Microsoft, and sign in
with their usual work account. On first sign-in the account waits for approval from the JUP
administrator.
