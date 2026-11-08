"""Lookups from Scryfall's Default Cards bulk file: C1, C2, C3, C4, C5, C38, E10, E11.

The bulk file is the only source behind the per-card cache: no lookup asks `cards/…`. The stand-in
serves `/bulk-data` and, on a second host, the gzipped JSON Lines file its `default_cards` entry
lists (conftest.py). tests/README.md fixes where the file is kept and how its age is read.
"""

from __future__ import annotations

import gzip
import json
import re
import shutil

import pytest
from conftest import (
    BULK_FILE,
    BULK_PATH,
    CARD_FIELDS,
    COMMANDER,
    EXIT_NOT_RECORDED,
    EXIT_UNREACHABLE,
    ROOT,
    WEEK,
    Deckwright,
    bulk_cards,
    category,
    jsonl_gz,
    place_bulk,
    printing,
    read_page,
    scryfall_card,
)


def lookup(deck, *names, **kw) -> list[dict]:
    entries = deck.json("lookup", *names, **kw)
    assert isinstance(entries, list) and len(entries) == len(names), entries
    assert [e["query"] for e in entries] == list(names)
    return entries


def assert_fixed_fields(card: dict, sc: dict):
    """S1's fixed fields of a single-faced card, from its Scryfall object."""
    assert set(card) == CARD_FIELDS, f"fields must be exactly {sorted(CARD_FIELDS)}, got {sorted(card)}"
    assert card["name"] == sc["name"]
    assert card["mana_cost"] == sc["mana_cost"]
    assert card["type_line"] == sc["type_line"]
    assert card["oracle_text"] == sc["oracle_text"]
    assert sorted(card["color_identity"]) == sorted(sc["color_identity"])
    assert card["commander_legality"] == sc["legalities"]["commander"]
    assert card["game_changer"] is sc["game_changer"]


def prefill_commander(deck):
    """The commander in the per-card cache, S1's layout, so a deck can be started with no bulk file."""
    deck.cache.mkdir(exist_ok=True)
    (deck.cache / "meren-of-clan-nel-toth.json").write_text(json.dumps(scryfall_card(COMMANDER)), encoding="utf-8")


def said(proc) -> str:
    return proc.stdout + proc.stderr


def assert_unreachable_message(proc, name: str):
    text = said(proc)
    assert name in text, f"the message names the card: {text!r}"
    assert re.search(r"scryfall", text, re.I) and re.search(r"reach", text, re.I), (
        f"the message says Scryfall could not be reached: {text!r}"
    )
    assert re.search(r"nothing\b.{0,40}\brecorded", text, re.I | re.S), (
        f"the message says nothing was recorded: {text!r}"
    )
    assert "Traceback" not in proc.stderr, proc.stderr


# C1 ----------------------------------------------------------------------------------


def test_bulk_lookup_found(deck, scryfall):
    place_bulk(deck.cache)
    scryfall.cards_refused = True

    names = (
        "Sol Ring", "Vampiric Tutor", "Bloodline Keeper", "Elbrus, the Binding Blade", "Starscape Cleric", "Cultivate",
    )
    entries = lookup(deck, *names)
    assert [e["result"] for e in entries] == ["found"] * len(names), entries
    sol, tutor, keeper, elbrus, cleric, cultivate = (e["card"] for e in entries)

    assert_fixed_fields(sol, scryfall_card("Sol Ring"))
    assert_fixed_fields(tutor, scryfall_card("Vampiric Tutor"))
    assert tutor["game_changer"] is True and sol["game_changer"] is False
    assert_fixed_fields(cultivate, printing("trc", "460"))

    # Faces as at S1: every face's text, front first; a back face with no cost adds nothing.
    sc = scryfall_card("Bloodline Keeper")
    assert set(keeper) == CARD_FIELDS
    assert keeper["name"] == "Bloodline Keeper // Lord of Lineage"
    assert keeper["mana_cost"] == "{2}{B}{B}"
    front, back = sc["card_faces"]
    assert keeper["oracle_text"].index(front["oracle_text"]) < keeper["oracle_text"].index(back["oracle_text"])
    assert elbrus["mana_cost"] == "{7}"

    # The file holds a token printing under the same name; a lookup is of the card.
    assert_fixed_fields(cleric, printing("blb", "116"))

    assert not scryfall.card_requests, f"a lookup asked cards/…: {[r.path for r in scryfall.card_requests]}"
    assert not scryfall.requests and not scryfall.data_requests, "a fresh bulk file needs no request at all"

    # Starting a deck and recording a card read the same file.
    deck.new()
    deck.add("Sol Ring", "Ramp")
    assert category(deck.tally(), "Ramp")["cards"] == ["Sol Ring"]
    assert not scryfall.requests and not scryfall.data_requests


# C2 ----------------------------------------------------------------------------------


def test_bulk_download_once(deck, scryfall):
    assert lookup(deck, "Sol Ring")[0]["result"] == "found"

    assert [r.path for r in scryfall.requests] == ["/bulk-data"], "one listing request, and no cards/… request"
    assert [r.path for r in scryfall.data_requests] == [BULK_PATH], (
        "the file downloaded is the one /bulk-data lists for default_cards, not the first one listed"
    )
    for r in [*scryfall.requests, *scryfall.data_requests]:
        agent = r.headers.get("user-agent", "")
        assert re.match(r"deckwright/\d", agent), f"User-Agent must name deckwright and its version: {agent!r}"
        assert "python-urllib" not in agent.lower()
        assert r.headers.get("accept", "").strip(), f"every request carries an Accept header: {r.headers}"
    assert "application/json" in scryfall.requests[0].headers.get("accept", "")

    assert (deck.cache / BULK_FILE).is_file(), f"the bulk file is kept as {BULK_FILE} in the cache folder"

    # Later lookups, in later runs, and the deck commands, make no request.
    lookup(deck, "Vampiric Tutor", "Forest")
    deck.new()
    deck.add("Sol Ring", "Ramp")
    deck.run("tally")
    assert len(scryfall.requests) == 1 and len(scryfall.data_requests) == 1, (
        [r.path for r in scryfall.requests],
        [r.path for r in scryfall.data_requests],
    )


# C3 ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("age", "downloaded"),
    [(WEEK + 60, True), (2 * WEEK, True), (WEEK - 3600, False), (60, False)],
    ids=["a week and a minute", "two weeks", "an hour short of a week", "a minute"],
)
def test_bulk_refresh_after_a_week(deck, scryfall, age, downloaded):
    # The cached file is older than Cultivate's printing; the one Scryfall lists now has it.
    stale = [c for c in bulk_cards() if c["name"] != "Cultivate"]
    place_bulk(deck.cache, stale, age=age)

    entry = lookup(deck, "Cultivate")[0]
    if downloaded:
        assert [r.path for r in scryfall.data_requests] == [BULK_PATH], "a file a week old or more is fetched again"
        assert entry["result"] == "found", "and the new file is the one read"
        assert lookup(deck, "Cultivate")[0]["result"] == "found"
        assert len(scryfall.data_requests) == 1, "the new file is fresh: fetched once"
    else:
        assert not scryfall.requests and not scryfall.data_requests, "a file younger than a week is reused"
        assert entry["result"] != "found", "the cached file is the one read"


# C4 ----------------------------------------------------------------------------------


def test_bulk_lookup_results_as_s1(deck, scryfall):
    scryfall.cards_refused = True
    deck.new()
    before = deck.deck_file.read_bytes()

    entries = lookup(deck, "Lim-Dul's Vault", "Smuggler’s Copter", "smugglers copter", "SOL RING")
    assert [e["result"] for e in entries] == ["found"] * 4, entries
    expected = ["Lim-Dûl's Vault", "Smuggler's Copter", "Smuggler's Copter", "Sol Ring"]
    assert [e["card"]["name"] for e in entries] == expected

    # A face name finds its card, normalised as a whole name is.
    faces = lookup(deck, "Bloodline Keeper", "lord of lineage", "Forum's Favor")
    assert [e["result"] for e in faces] == ["found"] * 3, faces
    assert [e["card"]["name"] for e in faces] == [
        "Bloodline Keeper // Lord of Lineage",
        "Bloodline Keeper // Lord of Lineage",
        "Honorbound Page // Forum's Favor",
    ]

    misspelt, missing = lookup(deck, "Vampiric Tutr", "Xyzzy Plover Quux")
    assert misspelt["result"] == "closest_match"
    assert misspelt["card"]["name"] == "Vampiric Tutor", "the closest match names the other card"
    assert set(misspelt["card"]) == CARD_FIELDS
    assert missing["result"] == "not_found"
    assert "card" not in missing
    assert deck.deck_file.read_bytes() == before, "a lookup writes nothing to the deck"

    # Nothing is recorded until the player confirms a real card by its exact name.
    deck.add("Vampiric Tutr", "Plan", expect=EXIT_NOT_RECORDED)
    deck.add("Xyzzy Plover Quux", "Plan", expect=EXIT_NOT_RECORDED)
    assert deck.deck_file.read_bytes() == before
    deck.add("Vampiric Tutor", "Plan")
    deck.add("Lim-Dul's Vault", "Card advantage")
    tally = deck.tally()
    assert category(tally, "Plan")["cards"] == ["Vampiric Tutor"]
    assert category(tally, "Card advantage")["cards"] == ["Lim-Dûl's Vault"], "the recorded name is Scryfall's"
    assert not scryfall.card_requests


# C5 ----------------------------------------------------------------------------------


def _no_default_cards(scryfall):
    """A listing whose default_cards entry points at a file the data host does not have: a 500."""
    listing = scryfall.listing()
    for entry in listing["data"]:
        entry["jsonl_download_uri"] = scryfall.data_url + "/default-cards/missing.jsonl.gz"
    return lambda: listing


@pytest.mark.parametrize("how", ["out of reach", "blocked by a proxy", "rate-limited", "server error"])
def test_bulk_unreachable(deck, scryfall, unreachable_url, how):
    prefill_commander(deck)
    runner = deck.offline(unreachable_url) if how == "out of reach" else deck
    runner.new()
    before = deck.deck_file.read_bytes()
    if how == "blocked by a proxy":
        scryfall.refuse = True
    elif how == "rate-limited":
        scryfall.limit = True
    elif how == "server error":
        scryfall.listing = _no_default_cards(scryfall)

    proc = runner.run("lookup", "Sol Ring", expect=EXIT_UNREACHABLE)
    assert_unreachable_message(proc, "Sol Ring")

    proc = runner.add("Sol Ring", "Ramp", expect=EXIT_UNREACHABLE)
    assert_unreachable_message(proc, "Sol Ring")
    assert deck.deck_file.read_bytes() == before, "nothing is written to the deck"
    assert not (deck.cache / BULK_FILE).exists(), "nothing is kept as a bulk file from a failed download"
    assert not scryfall.card_requests, "no fallback to cards/…"

    # The player's text still records the card, as at S1.
    runner.run(
        "add", "Sol Ring", "--from-player", "{T}: Add {C}{C}.", "--type-line", "Artifact", "--category", "Ramp",
    )
    assert category(runner.tally(), "Ramp")["cards"] == ["Sol Ring"]
    assert "Sol Ring" in read_page(runner.page()).section("player-text")

    # A failed reach is never kept: once Scryfall answers, the card is found.
    scryfall.refuse = scryfall.limit = False
    if how == "server error":
        del scryfall.listing
    assert lookup(deck, "Sol Ring")[0]["result"] == "found"


# C38 ---------------------------------------------------------------------------------


def test_bulk_card_cache_first(deck, unreachable_url):
    """S1's per-card cache, laid out as tests/README.md has fixed it since S1, answers first."""
    cache = deck.cache
    cache.mkdir()
    for name, key in [("Sol Ring", "sol-ring"), (COMMANDER, "meren-of-clan-nel-toth")]:
        (cache / f"{key}.json").write_text(json.dumps(scryfall_card(name)), encoding="utf-8")
    (cache / "vampiric-tutr.json").write_text(json.dumps(scryfall_card("Vampiric Tutor")), encoding="utf-8")

    offline = deck.offline(unreachable_url)
    entries = lookup(offline, "Sol Ring", COMMANDER, "Vampiric Tutr")
    assert [e["result"] for e in entries] == ["found", "found", "closest_match"]
    assert_fixed_fields(entries[0]["card"], scryfall_card("Sol Ring"))
    assert entries[2]["card"]["name"] == "Vampiric Tutor"

    offline.new()
    offline.add("Sol Ring", "Ramp")
    assert category(offline.tally(), "Ramp")["cards"] == ["Sol Ring"]
    assert not (cache / BULK_FILE).exists(), "no bulk file was needed, so none was fetched"


S1_EVAL_CACHES = sorted((ROOT / "evals").glob("*/fixture/deckwright-cache"))


@pytest.mark.parametrize("fixture", S1_EVAL_CACHES, ids=[p.parent.parent.name for p in S1_EVAL_CACHES])
def test_bulk_card_cache_first_eval_fixtures(tmp_path, scryfall, unreachable_url, fixture):
    """Each S1 eval case's pre-filled cache, copied as its scaffold copies it, answers with no network."""
    work = tmp_path / "work"
    shutil.copytree(fixture.parent, work)
    offline = Deckwright(work, unreachable_url)
    for path in sorted(fixture.glob("*.json")):
        query = path.stem.replace("-", " ")  # an ASCII key read back as the query that made it
        entry = lookup(offline, query)[0]
        cached = json.loads(path.read_text(encoding="utf-8"))
        assert entry["card"]["name"] == cached["name"], f"{path.name} answers {query!r}"


# E10 ---------------------------------------------------------------------------------


def test_bulk_download_interrupted(deck, scryfall):
    prefill_commander(deck)
    deck.new()
    before = deck.deck_file.read_bytes()
    scryfall.cut_off = True

    proc = deck.run("lookup", "Sol Ring", expect=EXIT_UNREACHABLE)
    assert "Traceback" not in proc.stderr, proc.stderr
    deck.add("Sol Ring", "Ramp", expect=EXIT_UNREACHABLE)
    assert deck.deck_file.read_bytes() == before, "nothing is recorded from a cut-off download"
    assert not (deck.cache / BULK_FILE).exists(), "the partial file is never kept as the bulk file"
    tries = len(scryfall.downloads)
    assert tries >= 1

    scryfall.cut_off = False
    assert lookup(deck, "Sol Ring")[0]["result"] == "found"
    assert len(scryfall.downloads) > tries, "the next lookup downloads again"
    assert b"Sol Ring" in gzip.decompress((deck.cache / BULK_FILE).read_bytes())


# E11 ---------------------------------------------------------------------------------


def _damaged(how: str) -> bytes:
    # Sol Ring is the file's last line, so a reader that stops at the first match still meets the damage.
    cards = sorted(bulk_cards(), key=lambda c: c["name"] == "Sol Ring")
    whole = jsonl_gz(cards)
    return {
        "not gzip": b"this is not a gzip file\n",
        "cut short": whole[: len(whole) // 2],
        "not JSON lines": gzip.compress(b"<html>not a card</html>\n", mtime=0),
        "empty": b"",
    }[how]


@pytest.mark.parametrize("how", ["not gzip", "cut short", "not JSON lines", "empty"])
def test_bulk_cache_unreadable(deck, scryfall, how):
    deck.cache.mkdir()
    (deck.cache / BULK_FILE).write_bytes(_damaged(how))

    entry = lookup(deck, "Sol Ring")[0]
    assert entry["result"] == "found", entry
    assert len(scryfall.downloads) == 1, "an unreadable bulk file is treated as absent and downloaded again"
    kept = gzip.decompress((deck.cache / BULK_FILE).read_bytes()).decode("utf-8")
    assert any(json.loads(line)["name"] == "Sol Ring" for line in kept.splitlines() if line.strip()), (
        "the damaged file is replaced by the downloaded one"
    )
