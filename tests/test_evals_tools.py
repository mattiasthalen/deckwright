"""The eval tools: the scaffolds' shared bulk file, `evals/tools/bulk-cache.sh DEST` (M2, S1); S4's number
check, `evals/tools/review-numbers.mjs` (AC22); and S4's fixture deck files, read as the code reads them.

The script is run with a stand-in `curl` first on `PATH`: asked for `/bulk-data` it prints a
listing whose `default_cards` entry is the address the test chose; asked for anything else it logs
the call and writes a small gzip file where `-o` says. So a test sees whether the script fetched
the address the listing gave, without the network.
"""

from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import ROOT, Deckwright, category

TOOL = ROOT / "evals" / "tools" / "bulk-cache.sh"
NETWORK_CASES = [
    "bend-the-template", "build-a-deck", "card-traps", "collection-rats", "not-owned-declined", "theme-conflict",
    "theme-ideas", "review-a-deck", "review-with-collection", "fantasy-deck", "ninety-nine", "review-a-deck-picked-up",
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

needs_shell = pytest.mark.skipif(
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


@needs_shell
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


@needs_shell
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


@needs_shell
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


# S4: the number check (AC22) -----------------------------------------------------------
#
#   node evals/tools/review-numbers.mjs DECK_FILE TALLY_FILE
#
# reads the written review (`review.text`) of a kept run's deck file, strips the name of every card
# the deck file names (the commander, the cards, the swaps and the maybeboard), drops turn spans
# ("turns 4–6", "turns 7+", "turns 7 and on"; a single "turn 8" is not a span), and fails (exit 1)
# on any number left that neither the stored measures (`review.measures`) nor the tally (that run's
# `deck.py tally` stdout, saved to TALLY_FILE) carries, at any depth, printing each such number on a
# line of its own. Exit 0 when every number is carried; exit 2 when the deck file has no written
# review. A number is a run of digits, with a decimal part where there is one (`2.94`).

NUMBERS = ROOT / "evals" / "tools" / "review-numbers.mjs"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

MEASURES = {
    "curve": [{"mana_value": 1, "count": 7}, {"mana_value": 2, "count": 14}, {"mana_value": 3, "count": 19}],
    "average_mana_value": 2.94,
    "colours": [{"colour": "B", "pips": 41, "sources": 23}, {"colour": "G", "pips": 18, "sources": 19}],
    "lands_without_mana": ["Evolving Wilds"],
    "types": {"creature": 31, "instant": 11, "sorcery": 9, "artifact": 4, "enchantment": 8, "planeswalker": 0,
              "land": 37},
    "theme_density": {"serving": 40, "of": 99},
    "not_counted": [],
}
TALLY = {
    "deck_size": 100,
    "total": 100,
    "categories": [
        {"name": "Lands", "target": 38, "count": 37, "cards": []},
        {"name": "Ramp", "target": 10, "count": 5, "cards": []},
        {"name": "Targeted disruption", "target": 12, "count": 16, "cards": []},
    ],
    "checks": {"singleton": [], "color_identity": [], "commander_legality": [], "commander": []},
    "bracket": {"target": 2, "lowest": 2, "game_changers": [], "over": False, "game_changers_allowed": 0},
}


def numbers_check(tmp_path, text: str | None, *, cards=("Evolving Wilds", "Sol Ring"), swaps=(), board=()):
    deck = {
        "name": "Meren Recursion",
        "commander": {"name": "Meren of Clan Nel Toth"},
        "cards": [{"card": {"name": name}, "count": 1, "categories": []} for name in cards],
        "swaps": [{"out": o, "in": i, "why": "w"} for o, i in swaps],
        "maybeboard": [{"name": n, "replaces": r, "why": "w"} for n, r in board],
        "review": {"measures": MEASURES, **({} if text is None else {"text": text})},
    }
    deck_file, tally_file = tmp_path / "deck.json", tmp_path / "tally.json"
    deck_file.write_text(json.dumps(deck, ensure_ascii=False), encoding="utf-8")
    tally_file.write_text(json.dumps(TALLY), encoding="utf-8")
    return subprocess.run(
        ["node", str(NUMBERS), str(deck_file), str(tally_file)], capture_output=True, text=True, timeout=60
    )


@needs_node
def test_review_numbers_carried(tmp_path):
    text = (
        "The curve peaks at 3 with 19 cards; the average mana value is 2.94 over 37 lands.\n\n"
        "Ramp is 5 against a target of 10, and Targeted disruption 16 against 12. Black wants 41 pips "
        "from 23 sources. 40 of 99 cards serve the theme, in a 100-card deck at bracket 2."
    )
    proc = numbers_check(tmp_path, text)
    assert proc.returncode == 0, proc.stdout + proc.stderr


@needs_node
@pytest.mark.parametrize(
    "text, stray",
    [
        ("Ramp is 6 short of its target.", "6"),  # 10 - 5, worked out by the writer: not printed by measure
        ("About 30% of the deck is creatures.", "30"),
        ("The average is 2.9.", "2.9"),
        ("It wins on turn 6 with 23 sources.", "6"),  # one turn is not a span
    ],
)
def test_review_numbers_stray(tmp_path, text, stray):
    proc = numbers_check(tmp_path, text)
    assert proc.returncode == 1, f"{stray} is carried by nothing measure or the tally printed: {proc.stdout}"
    assert stray in proc.stdout.split(), f"the number is named, alone on its line: {proc.stdout!r}"


@needs_node
def test_review_numbers_exempt(tmp_path):
    """Card names are stripped before numbers are read, and turn spans, closed or open-ended, are no count."""
    text = (
        "Borrowing 100,000 Arrows draws on turns 4–6, and +2 Mace holds the ground on turns 13-15. "
        "Late, Ulamog, the Ceaseless Hunger ends it on turns 21+, or turns 25 and on; "
        "1996 World Champion is on the maybeboard."
    )
    proc = numbers_check(
        tmp_path, text, cards=("Borrowing 100,000 Arrows",), swaps=[("Sol Ring", "+2 Mace")],
        board=[("1996 World Champion", "+2 Mace")],
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


@needs_node
def test_review_numbers_no_review(tmp_path):
    proc = numbers_check(tmp_path, None)
    assert proc.returncode == 2, proc.stdout + proc.stderr


# S4: the eval cases' deck files --------------------------------------------------------
#
# Written by evals/tools/make-review-decks.py, by deck.py against the bulk file, so a fixture the
# code can no longer read fails here and not in an eval.

REVIEW_DECKS = {
    "review-a-deck": 100,
    "review-with-collection": 100,
    "fantasy-deck": 100,
    "ninety-nine": 99,
    "review-a-deck-picked-up": 100,
}


@pytest.mark.parametrize("case", list(REVIEW_DECKS))
def test_review_fixture_decks_open(tmp_path, unreachable_url, case):
    fixture = ROOT / "evals" / case / "fixture"
    deck_file = fixture / "decks" / "meren-recursion.json"
    assert deck_file.is_file(), f"run evals/tools/make-review-decks.py to write {deck_file.relative_to(ROOT)}"
    work = tmp_path / "work"
    shutil.copytree(fixture, work)
    deck = Deckwright(work, unreachable_url, deck_path="decks/meren-recursion.json")

    tally = deck.tally()
    assert tally["name"] == "Meren Recursion"
    assert tally["total"] == REVIEW_DECKS[case]
    assert all(not flagged for flagged in tally["checks"].values()), tally["checks"]
    assert tally["bracket"]["lowest"] == 2 and not tally["bracket"]["game_changers"], tally["bracket"]
    stored = json.loads(deck_file.read_text(encoding="utf-8"))
    if case == "review-a-deck-picked-up":
        assert set(stored["review"]) == {"measures", "text"}, "a finished deck: reviewed"
    else:
        assert "review" not in stored, "the review is the run's to make"

    if REVIEW_DECKS[case] == 100:
        measured = deck.measure()
        assert measured["lands_without_mana"] == ["Evolving Wilds"]
        assert category(tally, "Ramp")["count"] < category(tally, "Ramp")["target"], "Ramp is planted short"
        assert category(tally, "Targeted disruption")["count"] > category(tally, "Targeted disruption")["target"]
        assert measured["theme_density"]["of"] == 99
    else:
        assert all(c["count"] >= c["target"] for c in tally["categories"]), "every category done at 99"
        assert deck.run("measure", expect=None).returncode == 2, "99 of 100 is refused"
    if case in ("review-with-collection", "fantasy-deck"):
        assert tally["not_owned"] is (case == "fantasy-deck")
        assert (fixture / "collection.txt").is_file()
    if case == "review-with-collection":
        assert stored["maybeboard"] == [
            {"name": "Sheoldred, Whispering One", "replaces": "Grisly Salvage", "why": stored["maybeboard"][0]["why"]}
        ]
