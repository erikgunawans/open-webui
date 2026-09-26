#!/usr/bin/env bash
# Push the JUP record tree to the bucket Cloud Run mounts read-only.
#
# This is a COPY, not a live view. A record committed in erikgunawans/jup is not on the
# dashboard until this runs. `--check` tells you whether that has fallen behind, without
# writing anything.
set -euo pipefail

JUP_TREE="${JUP_TREE:-$HOME/jup}"
BUCKET="${BUCKET:-gs://jup-ops-records}"
PROJECT="${PROJECT:-jup-ops}"
DIRS="records deliverables SOURCES"
# Single files at the tree's root. DECISIONS.md is read by the decisions-register MCP server
# (backend/jup_mcp/decisions.py) from /srv/jup/DECISIONS.md on the same read-only mount.
FILES="DECISIONS.md"
MANIFEST_OBJECT="$BUCKET/.sync-manifest.json"

# Filesystem junk that must never reach the bucket, and must never be compared.
#
# This is a correctness fix, not tidiness. The two halves of this script look at
# DIFFERENT things: the write path rsyncs a working FILESYSTEM from a Mac, while the CI
# gate compares against a git CHECKOUT. `.DS_Store` is in ~/jup/.gitignore, so it exists
# on the filesystem and can never exist in the checkout — rsync published it once, and
# from then on CI reported permanent, unfixable drift ("Would remove ....DS_Store") for
# a file no commit could ever add. Deleting the object alone would not hold: the next
# local sync would upload it again.
#
# Excluding on BOTH paths is what makes the local writer and the CI reader agree about
# what the tree contains. Every gitignored file rsync can see has this same shape.
#
# Must stay defined above the --check path, which uses it first.
JUNK_RE='(^|/)(\.DS_Store|Thumbs\.db|\._[^/]*)$'

MODE=sync
case "${1:-}" in
  --check) MODE=check ;;
  '') ;;
  *) echo "usage: $(basename "$0") [--check]" >&2; exit 2 ;;
esac

[ -d "$JUP_TREE/records" ] || { echo "no records/ under $JUP_TREE" >&2; exit 1; }
for file in $FILES; do [ -f "$JUP_TREE/$file" ] || { echo "no $file under $JUP_TREE" >&2; exit 1; }; done

local_head() { git -C "$JUP_TREE" rev-parse --short HEAD; }

dirty() { git -C "$JUP_TREE" status --porcelain $DIRS $FILES | grep -q .; }

# --------------------------------------------------------------------------- check
# Read-only. Exits 1 when the bucket disagrees with the local tree, so it can gate a
# commit or a cron without ever touching deployed state.
if [ "$MODE" = check ]; then
  status=0

  deployed=$(gcloud storage cat "$MANIFEST_OBJECT" --project="$PROJECT" 2>/dev/null \
    | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("commit","?"), d.get("synced_at","?"))' 2>/dev/null || true)
  if [ -n "$deployed" ]; then
    echo "deployed: $deployed"
  else
    echo "deployed: unknown (no .sync-manifest.json in $BUCKET — written by the next sync)"
  fi
  echo "local:    $(local_head)$(dirty && echo ' (WORKING TREE DIRTY — diff below is against uncommitted content)')"

  for dir in $DIRS; do
    # --dry-run makes this read-only; --checksums-only stops mtime churn reading as drift,
    # since an rsync'd object never carries the local file's mtime.
    # Only content changes count. `--checksums-only` stops an rsync'd object's mtime
    # (never the local file's) reading as a difference, but rsync still proposes to
    # SET mtime on byte-identical objects — counting that would make this cry wolf on
    # a tree that is genuinely in sync, and a gate that cries wolf gets ignored.
    out=$(gcloud storage rsync "$JUP_TREE/$dir" "$BUCKET/$dir" \
      --recursive --delete-unmatched-destination-objects --checksums-only --dry-run \
      --exclude="$JUNK_RE" \
      --project="$PROJECT" 2>&1 \
      | grep -E '^Would (copy|delete|remove)' || true)
    if [ -n "$out" ]; then
      echo "DRIFT in $dir/:"
      echo "$out" | sed 's/^/  /'
      status=1
    fi
  done

  for file in $FILES; do
    # A byte comparison: rsync is directory-shaped, and one file needs no more than this.
    if ! gcloud storage cat "$BUCKET/$file" --project="$PROJECT" 2>/dev/null | cmp -s - "$JUP_TREE/$file"; then
      echo "DRIFT: $file differs from the bucket (or is missing there)"
      status=1
    fi
  done

  if [ "$status" -eq 0 ]; then
    echo "in sync: the bucket matches $JUP_TREE for $DIRS $FILES"
  else
    echo "" >&2
    echo "the dashboard is serving something other than the local tree." >&2
    echo "run '$(basename "$0")' with no arguments to push (writes to deployed infrastructure)." >&2
  fi
  exit "$status"
fi

# ---------------------------------------------------------------------------- sync
# Refuse to publish a tree that disagrees with its own repo. A dashboard built from
# uncommitted edits has no author, no date and no diff behind it.
if dirty; then
  echo "refusing to sync: uncommitted changes under records/, deliverables/, SOURCES/ or in $FILES" >&2
  git -C "$JUP_TREE" status --short $DIRS $FILES >&2
  exit 1
fi

HEAD_SHA=$(local_head)
echo "syncing from $JUP_TREE @ $HEAD_SHA"

for dir in $DIRS; do
  gcloud storage rsync "$JUP_TREE/$dir" "$BUCKET/$dir" \
    --recursive --delete-unmatched-destination-objects \
    --exclude="$JUNK_RE" \
    --project="$PROJECT"
done

for file in $FILES; do
  gcloud storage cp "$JUP_TREE/$file" "$BUCKET/$file" --project="$PROJECT"
done

# Stamp what was published, so --check can name the deployed commit rather than only
# saying "differs". Written last: a manifest for a sync that failed would lie.
python3 -c "
import json, subprocess, sys, datetime
print(json.dumps({
    'commit': '$HEAD_SHA',
    'synced_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
    'dirs': '$DIRS'.split(),
    'files': '$FILES'.split(),
}))" | gcloud storage cp - "$MANIFEST_OBJECT" --project="$PROJECT"

echo "synced."
