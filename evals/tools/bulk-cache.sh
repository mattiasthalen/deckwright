#!/usr/bin/env bash
# Prints the path of one Scryfall Default Cards file kept on this host for every eval run, first
# downloading it when there is none or it is 7 days old or more. Each network case's scaffold copies
# it into its run's lookup cache, laid out as tests/README.md fixes (deckwright-cache/
# default-cards.jsonl.gz), so no run downloads 81 MB and no run needs data.scryfall.io: the runs'
# network grant stays api.scryfall.com alone. Parallel scaffolds (-j 8) take a lock, so one downloads
# and the rest wait for it. Any failure exits non-zero, and the scaffold with it: a run never starts
# without the file.
set -euo pipefail
dir="${DECKWRIGHT_EVALS_CACHE:-$HOME/.cache/deckwright-evals}"
file="$dir/default-cards.jsonl.gz"
agent="deckwright-evals/0.1"
mkdir -p "$dir"
exec 9>"$dir/.lock"
flock 9
# find -mmin +N is "more than N minutes": a week is 10080, so +10079 is "a week or more".
if [ ! -s "$file" ] || [ -n "$(find "$file" -mmin +10079)" ]; then
  part="$(mktemp "$dir/default-cards.XXXXXX.part")"
  chmod 644 "$part"
  trap 'rm -f "$part"' EXIT
  uri="$(curl -fsS --max-time 60 -H "User-Agent: $agent" -H "Accept: application/json" \
    https://api.scryfall.com/bulk-data |
    python3 -I -c 'import json, sys; print(next(b["jsonl_download_uri"] for b in json.load(sys.stdin)["data"] if b["type"] == "default_cards"))')"
  echo "bulk-cache: downloading $uri" >&2
  curl -fsS --max-time 1800 -H "User-Agent: $agent" -H "Accept: */*" -o "$part" "$uri"
  gzip -t "$part"
  mv -f "$part" "$file"
  trap - EXIT
fi
echo "$file"
