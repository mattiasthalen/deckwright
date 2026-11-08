#!/usr/bin/env bash
# Copies the case's starting workspace into the run's empty working directory: a lookup
# cache pre-filled in the layout tests/README.md fixes, so the cards the script names are
# answered without the network. Only fixture/ is copied; graders/ stays out of reach.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d "$here/fixture" ]; then
  echo "scaffold: no fixture/ beside ${BASH_SOURCE[0]}" >&2
  exit 1
fi
cp -R "$here/fixture/." .
