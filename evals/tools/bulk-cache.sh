#!/usr/bin/env bash
# Usage: bulk-cache.sh DEST
#
# Copies one Scryfall Default Cards file, kept on this host for every eval run, into the folder
# DEST as DEST/default-cards.jsonl.gz, the layout tests/README.md fixes for the lookup cache, and
# prints that path. The host's copy is downloaded first when there is none or it is 7 days old or
# more. Each network case's scaffold calls it with its run's cache folder (deckwright-cache), so no
# run downloads 81 MB and no run needs data.scryfall.io: the runs' network grant stays
# api.scryfall.com alone. Parallel scaffolds (-j 8) take a lock, so one downloads and the rest wait
# for it. The download address comes from Scryfall's listing and is fetched only when it is https on
# a scryfall.io or scryfall.com host. Any failure exits non-zero, and the scaffold with it: a run
# never starts without the file.
set -euo pipefail
if [ "$#" -ne 1 ] || [ -z "$1" ]; then
  echo "usage: bulk-cache.sh DEST (the run's cache folder)" >&2
  exit 2
fi
dest="$1"
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
  if ! [[ "$uri" =~ ^https://([a-z0-9-]+\.)*scryfall\.(io|com)/[^[:space:]]*$ ]]; then
    echo "bulk-cache: refusing to download $uri: not https on a scryfall.io or scryfall.com host" >&2
    exit 1
  fi
  echo "bulk-cache: downloading $uri" >&2
  curl -fsS --proto '=https' --max-time 1800 -H "User-Agent: $agent" -H "Accept: */*" -o "$part" "$uri"
  gzip -t "$part"
  mv -f "$part" "$file"
  trap - EXIT
fi
mkdir -p "$dest"
cp "$file" "$dest/default-cards.jsonl.gz"
echo "$dest/default-cards.jsonl.gz"
