#!/usr/bin/env bash
# Copies the case's starting workspace into the run's empty working directory: a lookup
# cache pre-filled in the layout tests/README.md fixes, so the cards the script names are
# answered without the network, and the Default Cards bulk file every other lookup reads,
# from the one kept on the host (../tools/bulk-cache.sh). Only fixture/ is copied; graders/
# stays out of reach.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d "$here/fixture" ]; then
  echo "scaffold: no fixture/ beside ${BASH_SOURCE[0]}" >&2
  exit 1
fi
cp -R "$here/fixture/." .
bulk="$("$here/../tools/bulk-cache.sh")"
mkdir -p deckwright-cache
cp "$bulk" deckwright-cache/default-cards.jsonl.gz
