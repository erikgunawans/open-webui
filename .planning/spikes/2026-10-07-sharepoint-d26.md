# Spike: SharePoint under D26 (2026-10-07)

Run in JUP's own tenant (`fc521bfb-…`) as Erik (Global Administrator), on throwaway objects only:
app registration **Asisten JUP - SharePoint spike** (`b05e9e7e-8796-489a-8106-e2292250da7f`) and
site **Spike Asisten JUP** (`/sites/SpikeAsistenJUP`, dummy files). QHSE-JUP was not touched.
Both are to be deleted after the JUP IT request is written.

## Result: D26 works as designed

| # | Probe (delegated token, scopes `Sites.Selected` + `Files.SelectedOperations.Selected`) | Result |
|---|---|---|
| 1 | Sign-in, auth code + PKCE S256, Entra v2, no `resource` parameter | 200, refresh token issued |
| 2 | Get site by path, default drive | 200 |
| 3 | List folder children | 200 |
| 4 | Drive search `/drives/{id}/root/search(q=)` | 200, 3 hits |
| 5 | Search API `/search/query` with `path:` filter | 200, 3 hits |
| 6 | Download: docx, text PDF, scan PDF, csv, txt | 200 each |
| 7 | Upload into `Keluaran Asisten JUP` (PUT and upload session) | 201 / 200 |
| 8 | Same name again, `conflictBehavior=rename` | 201 → `spike-d26 1.txt`, `spike-d26 2.txt` |
| 9 | Upload outside the folder | **403 from Microsoft** |
| 10 | A site the app was not granted | **403** |

Microsoft's per-API permission tables do not list delegated `Sites.Selected` for any of these calls;
only the "Selected scopes" overview says it works. The probes are the evidence, not the docs.

## The grants that work

1. Admin consent for the two delegated scopes (v2 `/adminconsent` with `scope=`).
2. Site read: `POST /sites/{site-id}/permissions` `{"roles":["read"],"grantedToIdentities":[{"application":{…}}]}`.
3. Folder write: `POST /sites/{site-id}/lists/{list-id}/items/{folder-item-id}/permissions`
   `{"roles":["write"],"grantedToV2":{"application":{…}}}`. This breaks inheritance on the folder.

**Trap:** `POST /drives/{id}/root:/<folder>:/permissions` with the same body returns **201 and does
nothing**: no unique permission appears on the folder and uploads stay 403. Use the list-item endpoint.
Grants 2 and 3 need `Sites.FullControl.All` (Graph Explorer, Erik's own consent).

## Vendor side (from code, `backend/open_webui/utils/oauth.py`)

- `oauth_2.1_static` skips DCR; discovery starts at the MCP server's
  `/.well-known/oauth-protected-resource`, whose `authorization_servers` must be
  `https://login.microsoftonline.com/<tenant>/v2.0`; the third candidate URL is Entra's OIDC document,
  and it validates against `mcp.shared.auth.OAuthMetadata`.
- PKCE S256 is on by default; `client_secret_post` is supported by Entra.
- `resource` is omitted automatically because the scopes start with `https://graph.microsoft.com/`
  (Entra v2 rejects it, AADSTS901002). Set `oauth_resource_parameter: omit` anyway.
- Not yet exercised end to end: the vendor's own callback with the real app URL as redirect URI.
  That is the first ticket of the build, not a reason to block the IT request.

## Other facts

- Library URL follows the site language: `Dokumen Berbagi`, not `Shared Documents`. Address the
  default drive (`/sites/{id}/drive`), never the path.
- Scan PDF has no text layer (pdftotext → 1 byte): `baca_dokumen` detects it and answers "hasil pindai".
