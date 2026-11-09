"""Lookups: AC4, E1, E12. Run against the recorded Scryfall responses, never the network.

Since the bulk lookups, these hold the lookup's results and the per-card cache; the request
etiquette S1's AC4a held for `cards/named` is now the bulk file's, in test_bulk.py (C2), and the
S1 tests that asserted `cards/named` requests were moved there or deleted.
"""

from __future__ import annotations

import hashlib
import json

from conftest import (
    BULK_FILE,
    CARD_FIELDS,
    COMMANDER,
    EXIT_NOT_RECORDED,
    EXIT_UNREACHABLE,
    RECORDED,
    S4_FIELDS,
    category,
    scryfall_card,
)


def lookup(deck, *names, **kw) -> list[dict]:
    entries = deck.json("lookup", *names, **kw)
    assert isinstance(entries, list) and len(entries) == len(names), entries
    assert [e["query"] for e in entries] == list(names)
    return entries


def assert_single_face(card: dict, sc: dict):
    assert set(card) - S4_FIELDS == CARD_FIELDS, f"fields must be exactly {sorted(CARD_FIELDS)}, got {sorted(card)}"
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
    assert set(keeper) - S4_FIELDS == CARD_FIELDS
    assert keeper["name"] == "Bloodline Keeper // Lord of Lineage"
    assert keeper["type_line"] == sc["type_line"]
    front, back = sc["card_faces"]
    assert front["oracle_text"] in keeper["oracle_text"]
    assert back["oracle_text"] in keeper["oracle_text"]
    assert keeper["oracle_text"].index(front["oracle_text"]) < keeper["oracle_text"].index(back["oracle_text"])
    assert front["mana_cost"] in keeper["mana_cost"]
    assert keeper["color_identity"] == ["B"]
    assert keeper["game_changer"] is False


def test_lookup_fields_back_face_without_cost(deck):
    # Both backs have no mana cost: the card's cost is the front's, with nothing joined after it.
    keeper, elbrus = (e["card"] for e in lookup(deck, "Bloodline Keeper", "Elbrus, the Binding Blade"))
    assert keeper["mana_cost"] == "{2}{B}{B}"
    assert elbrus["mana_cost"] == "{7}"


def test_lookup_fields_same_every_time(deck, unreachable_url):
    names = ("Sol Ring", "Vampiric Tutor", "Bloodline Keeper", "Black Lotus")
    first = deck.run("lookup", *names).stdout
    # The second run is answered from the cache, with Scryfall out of reach: same bytes.
    second = deck.offline(unreachable_url).run("lookup", *names).stdout
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

    entries = lookup(deck.offline(unreachable_url), "Sol Ring", "Meren of Clan Nel Toth", "Vampiric Tutr")
    assert [e["result"] for e in entries] == ["found", "found", "closest_match"]
    assert_single_face(entries[0]["card"], scryfall_card("Sol Ring"))
    assert sorted(entries[1]["card"]["color_identity"]) == ["B", "G"]
    assert entries[2]["card"]["name"] == "Vampiric Tutor"


def test_lookup_fields_cache_override(tmp_path, deck, unreachable_url):
    elsewhere = tmp_path / "elsewhere-cache"
    deck.run("lookup", "Sol Ring", env={"DECKWRIGHT_CACHE": str(elsewhere)})
    assert (elsewhere / BULK_FILE).is_file(), "the bulk file is kept in $DECKWRIGHT_CACHE"
    assert not (deck.cwd / "deckwright-cache").exists()
    again = lookup(deck, "Sol Ring", api=unreachable_url, env={"DECKWRIGHT_CACHE": str(elsewhere)})
    assert again[0]["result"] == "found"


def _hashed(query: str) -> str:
    return hashlib.sha256(query.casefold().encode("utf-8")).hexdigest()[:12]


def test_lookup_fields_cache_key_non_ascii(deck, unreachable_url):
    # Pre-filled, as S1 cached them: two all-non-ASCII queries, keyed by their hash alone, and one
    # with an ASCII part, each read from its own file.
    cache = deck.cwd / "deckwright-cache"
    cache.mkdir()
    queries = [
        ("稲妻", "", "Lightning Bolt"),
        ("Молния", "", "Sol Ring"),
        ("Lim-Dûl's Vault", "lim-d-l-s-vault-", "Vampiric Tutor"),
    ]
    for query, ascii_key, card in queries:
        (cache / f"{ascii_key}{_hashed(query)}.json").write_text(json.dumps(scryfall_card(card)), encoding="utf-8")
    entries = lookup(deck.offline(unreachable_url), *(q for q, _, _ in queries))
    assert [e["card"]["name"] for e in entries] == ["Lightning Bolt", "Sol Ring", "Vampiric Tutor"]


# E1 ----------------------------------------------------------------------------------


def test_lookup_not_found(deck):
    deck.new()
    before = deck.deck_file.read_bytes()

    missing, misspelt = lookup(deck, "Xyzzy Plover Quux", "Vampiric Tutr")
    assert missing["result"] == "not_found"
    assert "card" not in missing
    assert misspelt["result"] == "closest_match"
    assert misspelt["card"]["name"] == "Vampiric Tutor"
    assert set(misspelt["card"]) - S4_FIELDS == CARD_FIELDS
    assert deck.deck_file.read_bytes() == before, "a lookup writes nothing to the deck"

    # Nothing is recorded until the player confirms a real card by its exact name.
    deck.add("Xyzzy Plover Quux", "Plan", expect=EXIT_NOT_RECORDED)
    deck.add("Vampiric Tutr", "Plan", expect=EXIT_NOT_RECORDED)
    assert deck.deck_file.read_bytes() == before
    deck.add("Vampiric Tutor", "Plan")
    assert deck.deck_file.read_bytes() != before


def test_lookup_found_normalised(deck):
    # Scryfall answers all three exact requests 200; each is the card, not another card.
    entries = lookup(deck, "Lim-Dul's Vault", "Smuggler’s Copter", "smugglers copter")
    assert [e["result"] for e in entries] == ["found", "found", "found"], entries
    assert [e["card"]["name"] for e in entries] == ["Lim-Dûl's Vault", "Smuggler's Copter", "Smuggler's Copter"]

    deck.new()
    deck.add("Lim-Dul's Vault", "Card advantage")
    deck.add("Smuggler’s Copter", "Card advantage")
    deck.add("smugglers copter", "Card advantage")
    card_advantage = category(deck.tally(), "Card advantage")
    assert card_advantage["cards"] == ["Lim-Dûl's Vault", "Smuggler's Copter"], "the recorded name is Scryfall's"
    assert card_advantage["count"] == 3


def test_lookup_not_found_is_not_unreachable(deck, unreachable_url):
    # Scryfall out of reach with nothing cached is exit 3, never "not found". The other ways of
    # being out of reach, and the bulk file's part in it, are test_bulk.py's (C5).
    proc = deck.run("lookup", "Lightning Bolt", api=unreachable_url, expect=EXIT_UNREACHABLE)
    assert "Lightning Bolt" in proc.stdout + proc.stderr, "the message names the card"
    # A failed reach is never cached: once Scryfall answers, the card is found.
    assert lookup(deck, "Lightning Bolt")[0]["result"] == "found"


def test_lookup_not_found_is_not_unreachable_for_the_commander(deck, unreachable_url):
    new = ("new", "--template", "commander", "--commander", COMMANDER)
    proc = deck.run(*new, api=unreachable_url, expect=EXIT_UNREACHABLE)
    said = proc.stdout + proc.stderr
    assert COMMANDER in said, "the message names the card"
    assert "from-player" not in said, f"a commander cannot be recorded from the player's text: {said!r}"
    assert not deck.deck_file.exists()


def test_recordings_are_present():
    """Guard against a pruned fixture directory, which would make the stand-in 500 on everything."""
    assert len(list(RECORDED.glob("named-*.json"))) >= 20
