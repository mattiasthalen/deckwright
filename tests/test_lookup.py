"""Lookups: AC4, AC4a, E1, E12. Run against the recorded Scryfall responses, never the network."""

from __future__ import annotations

import json
import re

from conftest import (
    CARD_FIELDS,
    EXIT_NOT_RECORDED,
    EXIT_UNREACHABLE,
    RECORDED,
    scryfall_card,
)


def lookup(deck, *names, **kw) -> list[dict]:
    entries = deck.json("lookup", *names, **kw)
    assert isinstance(entries, list) and len(entries) == len(names), entries
    assert [e["query"] for e in entries] == list(names)
    return entries


def assert_single_face(card: dict, sc: dict):
    assert set(card) == CARD_FIELDS, f"fields must be exactly {sorted(CARD_FIELDS)}, got {sorted(card)}"
    assert card["name"] == sc["name"]
    assert card["mana_cost"] == sc["mana_cost"]
    assert card["type_line"] == sc["type_line"]
    assert card["oracle_text"] == sc["oracle_text"]
    assert sorted(card["color_identity"]) == sorted(sc["color_identity"])
    assert card["commander_legality"] == sc["legalities"]["commander"]
    assert card["game_changer"] is sc["game_changer"]


# AC4 ---------------------------------------------------------------------------------


def test_lookup_fields(deck):
    entries = lookup(deck, "Sol Ring", "Vampiric Tutor", "Bloodline Keeper")
    assert [e["result"] for e in entries] == ["found", "found", "found"]

    sol, tutor, keeper = (e["card"] for e in entries)
    assert_single_face(sol, scryfall_card("Sol Ring"))
    assert_single_face(tutor, scryfall_card("Vampiric Tutor"))
    assert sol["game_changer"] is False
    assert tutor["game_changer"] is True
    assert tutor["color_identity"] == ["B"]
    assert sol["color_identity"] == []
    assert sol["commander_legality"] == "legal"

    # E12: a double-faced card keeps every face's text, as one card.
    sc = scryfall_card("Bloodline Keeper")
    assert set(keeper) == CARD_FIELDS
    assert keeper["name"] == "Bloodline Keeper // Lord of Lineage"
    assert keeper["type_line"] == sc["type_line"]
    front, back = sc["card_faces"]
    assert front["oracle_text"] in keeper["oracle_text"]
    assert back["oracle_text"] in keeper["oracle_text"]
    assert keeper["oracle_text"].index(front["oracle_text"]) < keeper["oracle_text"].index(back["oracle_text"])
    assert front["mana_cost"] in keeper["mana_cost"]
    assert keeper["color_identity"] == ["B"]
    assert keeper["game_changer"] is False


def test_lookup_fields_same_every_time(deck, unreachable_url):
    names = ("Sol Ring", "Vampiric Tutor", "Bloodline Keeper", "Black Lotus")
    first = deck.run("lookup", *names).stdout
    # The second run is answered from the cache, with Scryfall out of reach: same bytes.
    second = deck.run("lookup", *names, api=unreachable_url).stdout
    assert first == second
    lotus = json.loads(first)[3]["card"]
    assert lotus["commander_legality"] == "banned"


def test_lookup_fields_from_prefilled_cache(deck, unreachable_url):
    """The eval scaffolds pre-fill the cache this way; the script must read it before the network."""
    cache = deck.cwd / "deckwright-cache"
    cache.mkdir()
    for name, key in [("Sol Ring", "sol-ring"), ("Meren of Clan Nel Toth", "meren-of-clan-nel-toth")]:
        (cache / f"{key}.json").write_text(json.dumps(scryfall_card(name)), encoding="utf-8")
    # A misspelling cached under its own key holds the card Scryfall's fuzzy match gave.
    (cache / "vampiric-tutr.json").write_text(json.dumps(scryfall_card("Vampiric Tutor")), encoding="utf-8")

    entries = lookup(deck, "Sol Ring", "Meren of Clan Nel Toth", "Vampiric Tutr", api=unreachable_url)
    assert [e["result"] for e in entries] == ["found", "found", "closest_match"]
    assert_single_face(entries[0]["card"], scryfall_card("Sol Ring"))
    assert sorted(entries[1]["card"]["color_identity"]) == ["B", "G"]
    assert entries[2]["card"]["name"] == "Vampiric Tutor"


def test_lookup_fields_cache_override(tmp_path, deck, unreachable_url):
    elsewhere = tmp_path / "elsewhere-cache"
    deck.run("lookup", "Sol Ring", env={"DECKWRIGHT_CACHE": str(elsewhere)})
    assert (elsewhere / "sol-ring.json").is_file()
    assert not (deck.cwd / "deckwright-cache").exists()
    again = lookup(deck, "Sol Ring", api=unreachable_url, env={"DECKWRIGHT_CACHE": str(elsewhere)})
    assert again[0]["result"] == "found"


# AC4a --------------------------------------------------------------------------------


def test_lookup_etiquette(deck, scryfall):
    # Five requests from one run: four exact, and one fuzzy after the misspelling's miss.
    lookup(deck, "Sol Ring", "Vampiric Tutor", "Vampiric Tutr", "Bloodline Keeper")
    assert not scryfall.unrecorded, f"requests outside cards/named exact-then-fuzzy: {scryfall.unrecorded}"
    reqs = scryfall.requests
    assert len(reqs) == 5, [(r.path, r.query) for r in reqs]
    assert [list(r.query) for r in reqs] == [["exact"], ["exact"], ["exact"], ["fuzzy"], ["exact"]]

    for r in reqs:
        agent = r.headers.get("user-agent", "")
        assert re.match(r"deckwright/\d", agent), f"User-Agent must name deckwright and its version: {agent!r}"
        assert "python-urllib" not in agent.lower()
        assert "application/json" in r.headers.get("accept", ""), r.headers

    gaps = [b.at - a.at for a, b in zip(reqs, reqs[1:])]
    # At most 10 a second: 100 ms between the script's requests. Timed here at arrival, so 20 ms
    # is allowed for the first connection's setup, which shortens the first gap as seen here.
    assert min(gaps) >= 0.08, f"requests too close together: {[round(g, 3) for g in gaps]}"


def test_lookup_etiquette_fetches_once(deck, scryfall):
    lookup(deck, "Sol Ring")
    lookup(deck, "Sol Ring")
    deck.new()
    deck.add("Sol Ring", "Ramp")
    sol_requests = [r for r in scryfall.requests if r.query.get("exact") == ["Sol Ring"]]
    assert len(sol_requests) == 1, "a card is fetched once; later lookups read the cache"


# E1 ----------------------------------------------------------------------------------


def test_lookup_not_found(deck):
    deck.new()
    before = deck.deck_file.read_bytes()

    missing, misspelt = lookup(deck, "Xyzzy Plover Quux", "Vampiric Tutr")
    assert missing["result"] == "not_found"
    assert "card" not in missing
    assert misspelt["result"] == "closest_match"
    assert misspelt["card"]["name"] == "Vampiric Tutor"
    assert set(misspelt["card"]) == CARD_FIELDS
    assert deck.deck_file.read_bytes() == before, "a lookup writes nothing to the deck"

    # Nothing is recorded until the player confirms a real card by its exact name.
    deck.add("Xyzzy Plover Quux", "Plan", expect=EXIT_NOT_RECORDED)
    deck.add("Vampiric Tutr", "Plan", expect=EXIT_NOT_RECORDED)
    assert deck.deck_file.read_bytes() == before
    deck.add("Vampiric Tutor", "Plan")
    assert deck.deck_file.read_bytes() != before


def test_lookup_not_found_is_not_unreachable(deck, unreachable_url, scryfall):
    deck.new()
    before = deck.deck_file.read_bytes()

    proc = deck.run("lookup", "Lightning Bolt", api=unreachable_url, expect=EXIT_UNREACHABLE)
    assert "Lightning Bolt" in proc.stdout + proc.stderr, "the message names the card"

    deck.add("Lightning Bolt", "Targeted disruption", api=unreachable_url, expect=EXIT_UNREACHABLE)
    assert deck.deck_file.read_bytes() == before

    # A proxy that blocks the host is unreachable too, not "not found".
    scryfall.refuse = True
    deck.run("lookup", "Lightning Bolt", expect=EXIT_UNREACHABLE)
    scryfall.refuse = False

    # A failed reach is never cached: once Scryfall answers, the card is found.
    assert lookup(deck, "Lightning Bolt")[0]["result"] == "found"


def test_recordings_are_present():
    """Guard against a pruned fixture directory, which would make the stand-in 500 on everything."""
    assert len(list(RECORDED.glob("named-*.json"))) >= 20
