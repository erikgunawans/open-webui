#!/usr/bin/env bash
# ADR-0016 step 2: the Entra OIDC provider in Identity Platform on jup-ops.
#
# Run it yourself in a real terminal (Terminal.app / iTerm), NOT through `! ` in Claude Code:
# the secret is read with `read -rs`, which gets EOF there. The secret goes from your paste
# straight to the Identity Platform API. It is never echoed, written to a file, or put on a
# command line.
#
# First run creates provider `oidc.entra-jup`. A later run (a rotated secret) replaces only the
# client secret. Either way it is a production write: running it is the OK.
set -euo pipefail

PROJECT=jup-ops
PROVIDER=oidc.entra-jup
TENANT=fc521bfb-40c2-4b87-95a7-65e0e888fdf8
CLIENT_ID=095f7f79-2430-4cff-8363-560bb063b3e1
ISSUER="https://login.microsoftonline.com/${TENANT}/v2.0"
API="https://identitytoolkit.googleapis.com/v2/projects/${PROJECT}/oauthIdpConfigs"
AFTER="$(cd "$(dirname "$0")/../.." && pwd)/.planning/entra-provider-after-$(date +%F).json"

if [[ ! -t 0 ]]; then
  echo "Needs a real terminal (stdin is not a TTY). Run it from Terminal.app, not '! '." >&2
  exit 1
fi
command -v jq >/dev/null || { echo "jq is required." >&2; exit 1; }

echo "Account: $(gcloud config get-value account 2>/dev/null)   Project: ${PROJECT}"
TOKEN=$(gcloud auth print-access-token)
auth=(-H "Authorization: Bearer ${TOKEN}" -H "x-goog-user-project: ${PROJECT}" -H "Content-Type: application/json")

existing=$(curl -s -o /dev/null -w '%{http_code}' "${auth[@]}" "${API}/${PROVIDER}")
if [[ "$existing" == 200 ]]; then
  mode=rotate
  echo "Provider ${PROVIDER} exists: this run replaces its client secret only."
else
  mode=create
  echo "Provider ${PROVIDER} does not exist: this run creates it."
  echo "  issuer    ${ISSUER}"
  echo "  client id ${CLIENT_ID}"
  echo "  flow      authorization code"
fi

echo
echo "Paste the NEW client secret Value from Entra (input is hidden), then Enter:"
IFS= read -rs SECRET
echo
[[ -n "$SECRET" ]] || { echo "Empty secret; nothing written." >&2; exit 1; }
echo "Received ${#SECRET} characters."
read -rp "Write it to ${PROVIDER} on ${PROJECT} now? [y/N] " ok
[[ "$ok" == y || "$ok" == Y ]] || { unset SECRET; echo "Aborted; nothing written."; exit 1; }

if [[ "$mode" == create ]]; then
  body=$(printf '%s' "$SECRET" | jq -Rs --arg cid "$CLIENT_ID" --arg iss "$ISSUER" \
    '{displayName:"Microsoft (JUP)", enabled:true, clientId:$cid, issuer:$iss, clientSecret:., responseType:{code:true, idToken:false}}')
  url="${API}?oauthIdpConfigId=${PROVIDER}"
  method=POST
else
  body=$(printf '%s' "$SECRET" | jq -Rs '{clientSecret:.}')
  url="${API}/${PROVIDER}?updateMask=clientSecret"
  method=PATCH
fi
unset SECRET

resp=$(mktemp)
code=$(printf '%s' "$body" | curl -s -o "$resp" -w '%{http_code}' -X "$method" "${auth[@]}" --data-binary @- "$url")
unset body
if [[ "$code" != 200 ]]; then
  echo "Failed: HTTP ${code}" >&2
  jq 'walk(if type == "object" then del(.clientSecret) else . end)' "$resp" >&2 || true
  rm -f "$resp"
  exit 1
fi
rm -f "$resp"

curl -s "${auth[@]}" "${API}/${PROVIDER}" | jq '.clientSecret = (if .clientSecret then "(set, redacted)" else "(missing)" end)' | tee "$AFTER"
echo
echo "Done (${mode}). Redacted record: ${AFTER}"
echo "Next: ask JUP IT to delete the OLD secret in Entra, and delete ~/Downloads/'Entra Microsoft.txt'."
