#!/usr/bin/env bash
# Copies the case's starting workspace into the run's empty working directory: a 99-card deck file in decks/ (Meren Recursion, every category at its target),
# written by deck.py itself (../tools/make-review-decks.py), and the Default Cards bulk file every
# lookup reads, from the one kept on the host (../tools/bulk-cache.sh). Only fixture/ is copied;
# graders/ stays out of reach.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d "$here/fixture" ]; then
  echo "scaffold: no fixture/ beside ${BASH_SOURCE[0]}" >&2
  exit 1
fi
cp -R "$here/fixture/." .
"$here/../tools/bulk-cache.sh" deckwright-cache >/dev/null
