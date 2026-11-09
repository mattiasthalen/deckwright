#!/usr/bin/env bash
# Copies the calibration's deck file into the run's empty working directory, so the judge reads it
# at decks/meren-recursion.json as the case's grader does. Only fixture/ is copied.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp -R "$here/fixture/." .
