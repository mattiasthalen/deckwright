"""Lookups from Scryfall's Default Cards bulk file: C1, C2, C3, C4, C5, C38, E10, E11.

The bulk file is the only source behind the per-card cache: no lookup asks `cards/…`. The stand-in
serves `/bulk-data` and, on a second host, the gzipped JSON Lines file its `default_cards` entry
lists (conftest.py). tests/README.md fixes where the file is kept and how its age is read.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import subprocess
import time

import pytest
from conftest import (
    BULK_FILE,
    BULK_PATH,
    CARD_FIELDS,
    COMMANDER,
    EXIT_NOT_RECORDED,
    EXIT_UNREACHABLE,
    ROOT,
    S4_FIELDS,
    WEEK,
    Deckwright,
    bulk_cards,
    category,
    jsonl_gz,
    manabox_csv,
    manabox_row,
    place_bulk,
    printing,
    read_page,
    scryfall_card,
    with_reversible,
    write_file,
)


def lookup(deck, *names, **kw) -> list[dict]:
    entries = deck.json("lookup", *names, **kw)
    assert isinstance(entries, list) and len(entries) == len(names), entries
    assert [e["query"] for e in entries] == list(names)
    return entries


def assert_fixed_fields(card: dict, sc: dict):
    """S1's fixed fields of a single-faced card, from its Scryfall object."""
    assert set(card) - S4_FIELDS == CARD_FIELDS, f"fields must be exactly {sorted(CARD_FIELDS)}, got {sorted(card)}"
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
    assert set(keeper) - S4_FIELDS == CARD_FIELDS
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
    assert set(misspelt["card"]) - S4_FIELDS == CARD_FIELDS
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


# A1, P1: where printings share a name, the playable one answers ---------------------------

# Each is (query, the shadowing printing, the card the query must find, its type line). The
# shadows are a Jumpstart theme card (layout `front_card`, type "Card"), an art-series card whose
# faces carry the card's name, and an Un-set card whose name is the card's once normalised.
SHADOWED = [
    ("Inferno", ("ffdn", "8"), "Inferno", "Instant"),
    ("Demonic Tutor", ("acmm", "64"), "Demonic Tutor", "Sorcery"),
    ("Clear the Mind", ("unk", "UU11a"), "Clear the Mind", "Sorcery"),
]


@pytest.mark.parametrize("first", [True, False], ids=["shadows first in the file", "shadows last in the file"])
def test_bulk_lookup_playable_printing_wins(deck, scryfall, first):
    shadows = [printing(*shadow) for _, shadow, _, _ in SHADOWED]
    ids = {c["id"] for c in shadows}
    rest = [c for c in bulk_cards() if c["id"] not in ids]
    place_bulk(deck.cache, shadows + rest if first else rest + shadows)

    entries = lookup(deck, *(query for query, _, _, _ in SHADOWED))
    for entry, (query, _, name, type_line) in zip(entries, SHADOWED):
        assert entry["result"] == "found", entry
        card = entry["card"]
        assert (card["name"], card["type_line"], card["commander_legality"]) == (name, type_line, "legal"), (
            f"{query!r} is the playable card, not a printing that shares its name: {card}"
        )
    assert not scryfall.requests and not scryfall.data_requests

    deck.new()
    for query, *_ in SHADOWED:
        deck.add(query, "Plan")
    assert deck.tally()["checks"]["commander_legality"] == [], "every card recorded is the legal one"


# A5, P2 ------------------------------------------------------------------------------


@pytest.mark.parametrize("where", ["first", "last", "only"], ids=lambda w: f"reversible {w} in the file")
def test_bulk_lookup_reversible_printing(deck, where):
    reversible = printing("sld", "1512")
    assert reversible["layout"] == "reversible_card"
    place_bulk(deck.cache, with_reversible(reversible, where))

    entry = lookup(deck, "Sol Ring")[0]
    assert entry["result"] == "found"
    assert_fixed_fields(entry["card"], scryfall_card("Sol Ring"))


# A2 ----------------------------------------------------------------------------------


def _side_by_side(deck, *args, runs: int = 6) -> list:
    procs = [deck.spawn(*args) for _ in range(runs)]
    done = []
    for proc in procs:
        out, err = proc.communicate(timeout=90)
        done.append((proc.returncode, out, err))
    return done


@pytest.mark.parametrize("bulk_there", [False, True], ids=["first download", "bulk file there, nothing else"])
def test_bulk_concurrent_first_lookups(deck, scryfall, bulk_there):
    """Two commands at once in one folder never share a temporary file: none fails, and the kept
    file is whole (A2)."""
    if bulk_there:
        place_bulk(deck.cache)
    scryfall.delay = 0.5

    for code, out, err in _side_by_side(deck, "lookup", "Sol Ring"):
        assert "Traceback" not in err, err
        assert code == 0, (code, out, err)
        assert json.loads(out)[0]["result"] == "found", out

    kept = gzip.decompress((deck.cache / BULK_FILE).read_bytes()).decode("utf-8")
    names = {json.loads(line)["name"] for line in kept.splitlines() if line.strip()}
    assert names == {c["name"] for c in bulk_cards()}, "the kept file is whole"
    leftovers = [p.name for p in deck.cache.iterdir() if p.name.endswith((".part", ".tmp"))]
    assert not leftovers, f"no temporary file is left behind: {leftovers}"
    assert lookup(deck, "Vampiric Tutor")[0]["result"] == "found", "and a later command reads it"


# A3 ----------------------------------------------------------------------------------


@pytest.mark.parametrize("how", ["out of reach", "rate-limited", "blocked by a proxy"])
def test_bulk_stale_file_when_unreachable(deck, scryfall, unreachable_url, how):
    """A bulk file a week old or more is fetched again; when that fails, the file there answers."""
    place_bulk(deck.cache, age=2 * WEEK)
    runner = deck.offline(unreachable_url) if how == "out of reach" else deck
    scryfall.limit = how == "rate-limited"
    scryfall.refuse = how == "blocked by a proxy"

    entry = lookup(runner, "Sol Ring")[0]
    assert entry["result"] == "found", entry
    assert_fixed_fields(entry["card"], scryfall_card("Sol Ring"))
    prefill_commander(deck)
    runner.new()
    runner.add("Sol Ring", "Ramp")
    assert category(runner.tally(), "Ramp")["cards"] == ["Sol Ring"]
    assert (deck.cache / BULK_FILE).is_file(), "the stale file is kept, not dropped"


# M1, A8 ------------------------------------------------------------------------------


@pytest.mark.parametrize("shape", ["ManaBox CSV", "list of lines"])
def test_bulk_refresh_after_a_week_collection(deck, scryfall, tmp_path, shape):
    """`collection` refreshes a bulk file a week old, as a lookup does, for a CSV too (M1)."""
    stale = [c for c in bulk_cards() if c["name"] != "Cultivate"]
    place_bulk(deck.cache, stale, age=WEEK + 60)
    player = tmp_path / "player"
    player.mkdir()
    if shape == "ManaBox CSV":
        handed = write_file(player, "export.csv", manabox_csv(manabox_row(printing("trc", "460"), 2)))
    else:
        handed = write_file(player, "list.txt", "2 Cultivate\n")

    report = deck.collection(handed)
    assert [r.path for r in scryfall.data_requests] == [BULK_PATH], "a file a week old is fetched again"
    assert report["matched"] == 1, f"and the new file is the one read: {report}"
    cards = deck.available()["cards"]
    assert [(c["name"], c["owned"]) for c in cards] == [("Cultivate", 2)]


# M5 ----------------------------------------------------------------------------------


def test_bulk_rate_limited_said(deck, scryfall):
    """A 429 is exit 3, and the message says Scryfall rate-limited the script and to wait."""
    scryfall.limit = True
    proc = deck.run("lookup", "Sol Ring", expect=EXIT_UNREACHABLE)
    text = said(proc)
    assert "Traceback" not in proc.stderr, proc.stderr
    assert "Sol Ring" in text, text
    assert re.search(r"rate.?limit", text, re.I), f"the message says it was rate-limited: {text!r}"
    assert re.search(r"\bwait", text, re.I), f"the message says to wait: {text!r}"
    assert not (deck.cache / BULK_FILE).exists()


# P3 ----------------------------------------------------------------------------------


def test_bulk_download_interrupted_said(deck, scryfall):
    """A download cut short of its Content-Length is said to be cut off, not a file that is not a bulk file."""
    scryfall.cut_off = True
    proc = deck.run("lookup", "Sol Ring", expect=EXIT_UNREACHABLE)
    text = said(proc)
    assert "Traceback" not in proc.stderr, proc.stderr
    assert re.search(r"cut (off|short)|incomplete|interrupted|truncated", text, re.I), (
        f"the message says the download was cut off: {text!r}"
    )
    assert not re.search(r"not a bulk file", text, re.I), text
    assert not (deck.cache / BULK_FILE).exists()
    leftovers = [p.name for p in deck.cache.iterdir()] if deck.cache.exists() else []
    assert not [n for n in leftovers if n.endswith((".part", ".tmp", ".gz"))], f"no partial file is kept: {leftovers}"


# S2 ----------------------------------------------------------------------------------


def test_bulk_download_over_the_cap(deck, scryfall):
    """A download larger than the cap (the builder's, under 2 GiB) is refused: exit 3, nothing kept,
    rather than read until the disk or the time runs out. The stand-in claims 100 GiB and sends 3."""
    scryfall.huge = True
    started = time.monotonic()
    proc = deck.run("lookup", "Sol Ring", expect=EXIT_UNREACHABLE)
    took = time.monotonic() - started
    assert "Traceback" not in proc.stderr, proc.stderr
    assert took < 25, f"refused, not read for {took:.0f} s"
    assert re.search(r"larger|too large|too big|over the cap|exceed", said(proc), re.I), (
        f"the message says the file is larger than the cap: {said(proc)!r}"
    )
    assert not re.search(r"cut (off|short)", said(proc), re.I), said(proc)
    assert not (deck.cache / BULK_FILE).exists()
    leftovers = [p.name for p in deck.cache.iterdir()] if deck.cache.exists() else []
    assert not [n for n in leftovers if n.endswith((".part", ".tmp", ".gz"))], leftovers


def test_bulk_download_over_the_cap_claimed(deck, scryfall):
    """R2-D5: a `Content-Length` past the cap is refused from the header, before the body is read:
    exit 3 at once, saying the file is larger than the cap (not that it was cut off), nothing kept.
    The stand-in claims 100 GiB and sends a byte every 0.1 s, so a script that reads first waits."""
    scryfall.claims_over_cap = True
    started = time.monotonic()
    proc = deck.run("lookup", "Sol Ring", expect=EXIT_UNREACHABLE)
    took = time.monotonic() - started
    text = said(proc)
    assert "Traceback" not in proc.stderr, proc.stderr
    assert took < 10, f"refused from the Content-Length, not after reading for {took:.0f} s"
    assert re.search(r"larger|too large|too big|over the cap|exceed", text, re.I), (
        f"the message says the file is larger than the cap: {text!r}"
    )
    assert not re.search(r"cut (off|short)", text, re.I), text
    assert not (deck.cache / BULK_FILE).exists()
    leftovers = [p.name for p in deck.cache.iterdir()] if deck.cache.exists() else []
    assert not [n for n in leftovers if n.endswith((".part", ".tmp", ".gz"))], leftovers


# R2-M1 -------------------------------------------------------------------------------

# Blank lines a bulk file may hold and a reader skips: enough that reading them all takes seconds.
SLOW_LINES = 120_000_000


def test_bulk_stale_file_not_read_before_download(deck, scryfall):
    """R2-M1: a bulk file a week old, with no saved index for it, is about to be replaced, so a
    lookup downloads the new one without reading the old one first. The old file here is
    readable gzip of only blank lines, which a reader skips one by one for seconds before finding
    no card; the control is the same lookup with no old file at all."""
    started = time.monotonic()
    deck.run("lookup", "Sol Ring", env={"DECKWRIGHT_CACHE": str(deck.cwd / "control-cache")})
    control = time.monotonic() - started

    deck.cache.mkdir()
    old = deck.cache / BULK_FILE
    old.write_bytes(gzip.compress(b"\n" * SLOW_LINES, compresslevel=9, mtime=0))
    then = time.time() - 2 * WEEK
    os.utime(old, (then, then))

    started = time.monotonic()
    entry = json.loads(deck.run("lookup", "Sol Ring").stdout)[0]
    took = time.monotonic() - started
    assert entry["result"] == "found", entry
    assert len(scryfall.downloads) == 2, "the control and the lookup each downloaded once"
    assert took < control + 3, (
        f"the old file was read before the download: {took:.1f} s against {control:.1f} s with none"
    )


# S4: AC7 -----------------------------------------------------------------------------

BASE = "a290734"  # S3, whose index (format 2) keeps no `cmc` and no `produced_mana`


def base_script(tmp_path):
    """deck.py as it was at S3, or None where the repository's history is not there to read it."""
    shown = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{BASE}:plugins/deckwright/skills/interview/deck.py"],
        capture_output=True,
    )
    if shown.returncode != 0:
        return None
    folder = tmp_path / "s3-skill"
    folder.mkdir()
    (folder / "deck.py").write_bytes(shown.stdout)
    return folder / "deck.py"


def test_index_carries_cmc_and_produced_mana(deck, scryfall, unreachable_url):
    place_bulk(deck.cache)
    entries = lookup(deck, "Sol Ring", "Evolving Wilds", "Command Tower", "Bloodline Keeper", "Egon, God of Death")
    sol, wilds, tower, keeper, egon = (e["card"] for e in entries)
    assert set(sol) == CARD_FIELDS | S4_FIELDS, f"the fixed fields and S4's two: {sorted(sol)}"
    assert (sol["cmc"], sol["produced_mana"]) == (1, ["C"])
    assert (wilds["cmc"], wilds["produced_mana"]) == (0, []), "no produced_mana in Scryfall's data: an empty list"
    assert tower["produced_mana"] == ["B", "G", "R", "U", "W"], "as Scryfall lists them"
    assert keeper["cmc"] == 4 and keeper["produced_mana"] == []
    assert egon["cmc"] == 3, "a modal double-faced card's mana value is its front face's, as Scryfall gives it"

    # The deck's card facts carry them too: `measure` counts from them with no lookup of its own.
    deck.new()
    deck.add("Sol Ring")
    deck.add("Evolving Wilds")
    deck.fill()
    measured = deck.measure(api=unreachable_url)
    assert measured["lands_without_mana"] == ["Evolving Wilds"]
    assert {float(e["mana_value"]): e["count"] for e in measured["curve"] if e["count"]} == {1.0: 1}

    # No new endpoint: a fresh bulk file needed no request, and none was ever made beside the two known.
    assert not scryfall.requests and not scryfall.data_requests, [r.path for r in scryfall.requests]


def test_index_carries_cmc_and_produced_mana_s3_index_rebuilt(deck, scryfall, tmp_path):
    """An index kept by S3's script, for the very bulk file there is now, is rebuilt rather than read."""
    script = base_script(tmp_path)
    if script is None:
        pytest.skip(f"the repository's history does not hold {BASE}")
    place_bulk(deck.cache)
    s3 = Deckwright(deck.cwd, scryfall.url, script=script)
    assert "cmc" not in lookup(s3, "Sol Ring")[0]["card"], "S3's lookup has no cmc"
    kept = {p.name for p in deck.cache.iterdir()}
    assert kept - {BULK_FILE}, f"S3 kept an index beside the bulk file: {kept}"

    sol = lookup(deck, "Sol Ring")[0]["card"]
    assert (sol["cmc"], sol["produced_mana"]) == (1, ["C"]), "the S3 index was rebuilt, not read"
    assert not scryfall.downloads, "rebuilding the index reads the bulk file there; it downloads nothing"
    assert {r.path for r in scryfall.requests} <= {"/bulk-data"}


def test_index_carries_cmc_and_produced_mana_from_card_cache(deck, unreachable_url):
    """A per-card cache file holds a whole Scryfall card object, so it answers with both fields too."""
    deck.cache.mkdir()
    (deck.cache / "evolving-wilds.json").write_text(json.dumps(scryfall_card("Evolving Wilds")), encoding="utf-8")
    wilds = lookup(deck.offline(unreachable_url), "Evolving Wilds")[0]["card"]
    assert (wilds["cmc"], wilds["produced_mana"]) == (0, [])
