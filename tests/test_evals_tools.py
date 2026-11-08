"""The eval scaffolds' shared bulk file: `evals/tools/bulk-cache.sh DEST` (M2, S1).

The script is run with a stand-in `curl` first on `PATH`: asked for `/bulk-data` it prints a
listing whose `default_cards` entry is the address the test chose; asked for anything else it logs
the call and writes a small gzip file where `-o` says. So a test sees whether the script fetched
the address the listing gave, without the network.
"""

from __future__ import annotations

import gzip
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import ROOT

TOOL = ROOT / "evals" / "tools" / "bulk-cache.sh"
NETWORK_CASES = [
    "bend-the-template", "build-a-deck", "card-traps", "collection-rats", "not-owned-declined", "theme-conflict",
    "theme-ideas",
]

FAKE_CURL = r"""#!/usr/bin/env bash
out=""
url=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -H|--max-time|--proto) shift 2 ;;
    -*) shift ;;
    *) url="$1"; shift ;;
  esac
done
if [ "$url" = "https://api.scryfall.com/bulk-data" ]; then
  oracle='{"type": "oracle_cards", "jsonl_download_uri": "https://data.scryfall.io/oracle.jsonl.gz"}'
  printf '{"data": [%s, {"type": "default_cards", "jsonl_download_uri": "%s"}]}' "$oracle" "$FAKE_URI"
  exit 0
fi
echo "$url" >> "$FAKE_LOG"
printf '{"name": "Sol Ring"}\n' | gzip > "$out"
"""

pytestmark = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("bash", "flock", "gzip", "python3")), reason="needs bash, flock, gzip, python3"
)


@pytest.fixture
def host(tmp_path) -> dict:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    curl = bin_dir / "curl"
    curl.write_text(FAKE_CURL, encoding="utf-8")
    curl.chmod(0o755)
    return {
        "bin": bin_dir,
        "cache": tmp_path / "host-cache",
        "log": tmp_path / "curl.log",
        "run": tmp_path / "run",
    }


def bulk_cache(host: dict, uri: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PATH": f"{host['bin']}{os.pathsep}{os.environ['PATH']}",
        "DECKWRIGHT_EVALS_CACHE": str(host["cache"]),
        "FAKE_URI": uri,
        "FAKE_LOG": str(host["log"]),
    }
    cwd = cwd or host["run"]
    cwd.mkdir(exist_ok=True)
    return subprocess.run(["bash", str(TOOL), *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=60)


def downloads(host: dict) -> list[str]:
    return host["log"].read_text(encoding="utf-8").splitlines() if host["log"].exists() else []


# M2 ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri",
    ["https://data.scryfall.io/default-cards/default-cards-20261108100757.jsonl.gz", "https://scryfall.com/x.jsonl.gz"],
)
def test_bulk_cache_copies_into_destination(host, uri):
    proc = bulk_cache(host, uri, "deckwright-cache")
    assert proc.returncode == 0, proc.stderr
    copied = host["run"] / "deckwright-cache" / "default-cards.jsonl.gz"
    assert gzip.decompress(copied.read_bytes()) == b'{"name": "Sol Ring"}\n'
    assert downloads(host) == [uri], "the address the listing gave is the one fetched"

    # A second run, in another run's folder, copies the host's file with no download.
    again = host["run"].parent / "run-2"
    proc = bulk_cache(host, uri, "deckwright-cache", cwd=again)
    assert proc.returncode == 0, proc.stderr
    assert (again / "deckwright-cache" / "default-cards.jsonl.gz").read_bytes() == copied.read_bytes()
    assert downloads(host) == [uri]


def test_bulk_cache_needs_destination(host):
    proc = bulk_cache(host, "https://data.scryfall.io/x.jsonl.gz")
    assert proc.returncode != 0
    assert not downloads(host)


@pytest.mark.parametrize("case", NETWORK_CASES)
def test_bulk_cache_scaffolds_call_it(case):
    """Each network case's scaffold hands the copy to bulk-cache.sh, rather than repeating it."""
    text = (ROOT / "evals" / case / "scaffold.sh").read_text(encoding="utf-8")
    assert '"$here/../tools/bulk-cache.sh" deckwright-cache' in text, text
    assert "default-cards.jsonl.gz" not in text.split("bulk-cache.sh", 2)[-1], "no copy of its own"
    assert "cp \"$bulk\"" not in text


def test_bulk_cache_not_in_the_offline_case():
    assert "bulk-cache" not in (ROOT / "evals" / "lookup-unavailable" / "scaffold.sh").read_text(encoding="utf-8")


# S1 ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri",
    [
        "http://data.scryfall.io/default-cards/x.jsonl.gz",
        "file:///etc/passwd",
        "https://evil.example/x.jsonl.gz",
        "https://data.scryfall.io.evil.example/x.jsonl.gz",
        "https://scryfall.io@evil.example/x.jsonl.gz",
        "https://notscryfall.io/x.jsonl.gz",
        "-o/tmp/owned",
        "",
    ],
)
def test_bulk_cache_refuses_other_hosts(host, uri):
    proc = bulk_cache(host, uri, "deckwright-cache")
    assert proc.returncode != 0, f"{uri!r} was accepted: {proc.stderr}"
    assert not downloads(host), f"{uri!r} was fetched"
    assert not (host["run"] / "deckwright-cache" / "default-cards.jsonl.gz").exists()
    assert not (host["cache"] / "default-cards.jsonl.gz").exists()
