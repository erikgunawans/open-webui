# Request to JUP IT: an Entra app registration for None-JUPe sign-in

None-JUPe (`https://non-jupe.jup.co.id`), JUP's AI assistant, will let JUP staff sign in with their
existing Microsoft 365 account. Google Cloud Identity Platform connects to Entra ID over OpenID
Connect. We need one app registration in JUP's Entra tenant. It takes about 15 minutes. ADR-0016 has
the design.

## Summary

| Field | Value |
|-------|-------|
| Name | `None-JUPe` |
| Supported account types | **Accounts in this organizational directory only** (single tenant) |
| Redirect URI | Platform **Web**: `https://jup-ops.firebaseapp.com/__/auth/handler` |
| API permissions | Microsoft Graph, delegated: `openid`, `email`, `profile`, with admin consent |
| Optional claim | `email` in the ID token |
| Client secret | 12 or 24 months |

**Role needed:** Application Administrator or Cloud Application Administrator (or Global
Administrator). Either role can also grant the admin consent in step 4.

## Step by step

Labels follow the English Microsoft Entra admin center.

### 1. Create the app registration

1. Open `https://entra.microsoft.com` and sign in as an administrator.
2. In the left menu: **Entra ID → App registrations** (older layout: **Identity → Applications →
   App registrations**).
3. Click **+ New registration**.
4. Fill in:
   - **Name:** `None-JUPe`. Staff see this name on the Microsoft sign-in page.
   - **Supported account types:** **Accounts in this organizational directory only (single
     tenant)**.
   - **Redirect URI:** under *Select a platform* choose **Web**, then enter
     `https://jup-ops.firebaseapp.com/__/auth/handler`. Copy it exactly, including `/__/`.
5. Click **Register**.

### 2. Note the two IDs

The app's **Overview** page opens. Copy:

- **Application (client) ID**
- **Directory (tenant) ID**

### 3. Create the client secret

1. In the app's menu: **Certificates & secrets → Client secrets → + New client secret**.
2. **Description:** `None-JUPe IAP`. **Expires:** 365 days (12 months) or 730 days (24 months).
3. Click **Add**.
4. **Copy the `Value` column at once**, not `Secret ID`. It is shown only once. If the page closes
   before you copy it, delete that secret and create a new one.
5. Note the **Expires** date. Sign-in stops working when the secret expires, so please set a
   reminder about a month before.

### 4. API permissions and admin consent

1. In the app's menu: **API permissions**. `User.Read` is usually there already; leave it.
2. Click **+ Add a permission → Microsoft Graph → Delegated permissions**.
3. Under **OpenId permissions**, tick `email`, `openid` and `profile`, then **Add permissions**.
4. Click **Grant admin consent for \<JUP tenant name\>** → **Yes**.
5. Check that the **Status** column shows a green tick, *Granted for …*, on all four. Staff are then
   not asked to consent individually.

### 5. The email claim in the ID token

1. In the app's menu: **Token configuration → + Add optional claim**.
2. **Token type:** **ID**. Tick `email`, then **Add**.
3. If asked to turn on the Microsoft Graph `email` permission, tick it and click **Add**.
4. Check the staff email attribute: **Entra ID → Users →** a staff member **→ Properties → Contact
   information → Email**. It must be their `@jakarta-utilitas.com` address, because that is the
   address the app account is created under. Users with an Exchange Online mailbox normally have it
   filled in already. Please check at least `erik@jakarta-utilitas.com`.

Nothing changes under **Authentication**. The app uses the authorization code flow, so implicit
grant (*Access tokens* and *ID tokens*) stays unticked.

### 6. Limit who can sign in (optional, recommended)

1. Open **Entra ID → Enterprise applications → All applications** and search for `None-JUPe`. If it
   does not show, clear the *Application type* filter.
2. **Properties → Assignment required? = Yes → Save**.
3. **Users and groups → + Add user/group → Users → None Selected**, pick
   `erik@jakarta-utilitas.com` first, then **Select → Assign**. That account signs in first, to test
   the setup before any other staff.
4. Other staff (or one security group) can be assigned the same way once Erik's test sign-in works.

Without this step, every account in the tenant can reach the sign-in step. The app still holds new
accounts as pending until a JUP administrator approves them.

## Please send back

- **Directory (tenant) ID** (step 2)
- **Application (client) ID** (step 2)
- **Client secret value** (step 3), through a secure channel: in person, by phone, or a one-time
  view link. **Not** plain email or chat.
- The secret's expiry date (step 3)

The two IDs are not secret and can go by email.

## What changes for staff

Nothing needs installing. Staff open `https://non-jupe.jup.co.id`, choose Microsoft, and sign in
with their usual work account. On first sign-in the account waits for approval from the JUP
administrator.

## Received from JUP IT — 2026-09-26

| Value | |
|-------|---|
| Directory (tenant) ID | `fc521bfb-40c2-4b87-95a7-65e0e888fdf8`. Verified: Microsoft's public discovery for `jakarta-utilitas.com` returns this tenant (issuer `https://login.microsoftonline.com/fc521bfb-40c2-4b87-95a7-65e0e888fdf8/v2.0`). |
| Application (client) ID | `095f7f79-2430-4cff-8363-560bb063b3e1` |
| Client secret | Received. **Never written to this repo.** It goes only into the Identity Platform OIDC provider configuration. |
| Secret expiry date | **Not supplied.** Ask JUP IT. |

The OIDC issuer for the Identity Platform provider is therefore
`https://login.microsoftonline.com/fc521bfb-40c2-4b87-95a7-65e0e888fdf8/v2.0`.

Not yet confirmed with JUP IT: that steps 4–6 were done (admin consent granted, the `email` optional
claim, and whether assignment is required with Erik assigned). The first test sign-in will show the
first two.
