#!/usr/bin/env bash
# Push the JUP record tree to the bucket Cloud Run mounts read-only.
#
# This is a COPY, not a live view. A record committed in erikgunawans/jup is not on the
# dashboard until this runs. Until issue #9 lands, that second step is yours to remember.
set -euo pipefail

JUP_TREE="${JUP_TREE:-$HOME/jup}"
BUCKET="${BUCKET:-gs://jup-ops-records}"
PROJECT="${PROJECT:-jup-ops}"

[ -d "$JUP_TREE/records" ] || { echo "no records/ under $JUP_TREE" >&2; exit 1; }

# Refuse to publish a tree that disagrees with its own repo. A dashboard built from
# uncommitted edits has no author, no date and no diff behind it.
if git -C "$JUP_TREE" status --porcelain records deliverables SOURCES | grep -q .; then
  echo "refusing to sync: uncommitted changes under records/, deliverables/ or SOURCES/" >&2
  git -C "$JUP_TREE" status --short records deliverables SOURCES >&2
  exit 1
fi

echo "syncing from $JUP_TREE @ $(git -C "$JUP_TREE" rev-parse --short HEAD)"
for dir in records deliverables SOURCES; do
  gcloud storage rsync "$JUP_TREE/$dir" "$BUCKET/$dir" \
    --recursive --delete-unmatched-destination-objects --project="$PROJECT"
done
echo "synced."
