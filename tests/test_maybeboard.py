"""`maybeboard add 'IN' --replaces 'OUT' --why 'TEXT'` and `maybeboard remove 'NAME'`: AC14, E8–E11 (P4).

The maybeboard is the deck file's `maybeboard` list, `{name, replaces, why}`, names as the lookup
spells them (P4). It counts towards nothing, so it changes no count and no review.
"""

from __future__ import annotations

import json
import re
import shutil

from conftest import COMMANDER, EXIT_NOT_RECORDED, EXIT_UNREACHABLE, EXIT_USAGE, Deckwright, assert_refused, said


def full_deck(deck: Deckwright, started: bool = False) -> Deckwright:
    if not started:
        deck.new()
    deck.add("Sol Ring", "Ramp")
    deck.add("Sign in Blood", "Card advantage")
    deck.add("Command Tower")
    deck.fill()
    return deck


def board(deck: Deckwright) -> list[dict]:
    return deck.stored().get("maybeboard", [])


def counted(deck: Deckwright) -> dict:
    tally = deck.tally()
    return {key: tally[key] for key in ("total", "categories", "checks", "bracket")}


# AC14 --------------------------------------------------------------------------------


def test_add_and_remove(deck):
    full_deck(deck)
    tally = counted(deck)

    deck.maybeboard_add("smugglers copter", "Sign in Blood", "Draws and swings")
    deck.maybeboard_add("Demonic Tutor", "Sol Ring", "Finds anything")
    assert board(deck) == [
        {"name": "Smuggler's Copter", "replaces": "Sign in Blood", "why": "Draws and swings"},
        {"name": "Demonic Tutor", "replaces": "Sol Ring", "why": "Finds anything"},
    ], "recorded in the order added, by the names the lookup and the deck give"
    assert counted(deck) == tally, "the maybeboard counts towards nothing"

    # Re-pairing is a remove, then an add.
    deck.maybeboard_remove("Smuggler's Copter")
    deck.maybeboard_add("Smuggler's Copter", "Sol Ring", "A better pair")
    assert board(deck) == [
        {"name": "Demonic Tutor", "replaces": "Sol Ring", "why": "Finds anything"},
        {"name": "Smuggler's Copter", "replaces": "Sol Ring", "why": "A better pair"},
    ]
    deck.maybeboard_remove("Demonic Tutor")
    deck.maybeboard_remove("Smuggler's Copter")
    assert board(deck) == []
    assert counted(deck) == tally


def test_add_and_remove_named_deck(deck):
    """A named deck's maybeboard is its own: `--deck` comes after the subcommand (tests/README.md)."""
    rats = deck.named("Rat Pack")
    full_deck(rats, started=True)
    rats.maybeboard_add("Demonic Tutor", "Sol Ring", "Finds anything")
    assert [e["name"] for e in board(rats)] == ["Demonic Tutor"]
    rats.maybeboard_remove("Demonic Tutor")
    assert board(rats) == []


# E8–E11 ------------------------------------------------------------------------------


def test_refuses_card_in_deck(deck):
    full_deck(deck)
    before = deck.deck_file.read_bytes()
    proc = deck.run("maybeboard", "add", "Sol Ring", "--replaces", "Sign in Blood", "--why", "x", expect=None)
    assert_refused(proc, deck, before)


def test_refuses_card_already_on_it(deck):
    full_deck(deck)
    deck.maybeboard_add("Demonic Tutor", "Sol Ring", "Finds anything")
    before = deck.deck_file.read_bytes()
    proc = deck.run("maybeboard", "add", "Demonic Tutor", "--replaces", "Sign in Blood", "--why", "x", expect=None)
    assert_refused(proc, deck, before)


def test_refuses_replaces_not_in_deck(deck):
    full_deck(deck)
    before = deck.deck_file.read_bytes()
    proc = deck.run("maybeboard", "add", "Demonic Tutor", "--replaces", "Lightning Bolt", "--why", "x", expect=None)
    assert_refused(proc, deck, before)


def test_refuses_remove_absent(deck):
    full_deck(deck)
    deck.maybeboard_add("Demonic Tutor", "Sol Ring", "Finds anything")
    before = deck.deck_file.read_bytes()
    assert_refused(deck.run("maybeboard", "remove", "Sol Ring", expect=None), deck, before)
    assert_refused(deck.run("maybeboard", "remove", "Vampiric Tutor", expect=None), deck, before)


def test_lookup_failure_changes_nothing(deck, unreachable_url):
    full_deck(deck)
    before = deck.deck_file.read_bytes()
    for name in ("Xyzzy Plover Quux", "Vampiric Tutr"):  # not found; only a closest match
        proc = deck.run("maybeboard", "add", name, "--replaces", "Sol Ring", "--why", "x", expect=None)
        assert_refused(proc, deck, before, EXIT_NOT_RECORDED)

    shutil.rmtree(deck.cache)  # no bulk file to answer for Scryfall
    offline = deck.offline(unreachable_url)
    proc = offline.run("maybeboard", "add", "Demonic Tutor", "--replaces", "Sol Ring", "--why", "x", expect=None)
    assert_refused(proc, deck, before, EXIT_UNREACHABLE)
    assert re.search(r"reach", said(proc), re.I), said(proc)
    assert "from-player" not in said(proc), "the maybeboard has no --from-player path, so the message offers none"
    proc = offline.run(
        "maybeboard", "add", "Demonic Tutor", "--replaces", "Sol Ring", "--why", "x", "--from-player", "t", expect=None
    )
    assert_refused(proc, deck, before, EXIT_USAGE, by_argparse=True)


def test_refuses_the_commander(deck):
    """R18: the commander is in the deck, so it is never on the maybeboard."""
    full_deck(deck)
    before = deck.deck_file.read_bytes()
    proc = deck.run("maybeboard", "add", COMMANDER, "--replaces", "Sign in Blood", "--why", "x", expect=None)
    assert_refused(proc, deck, before)


def test_remove_flags_orphaned_maybeboard_entries(deck):
    """R17: `remove` of the card a maybeboard entry replaces prints the entry as `orphaned_maybeboard`, as
    `swap` does, and leaves it as it was; a remove that leaves copies of the card orphans nothing."""
    full_deck(deck)
    deck.maybeboard_add("Demonic Tutor", "Sign in Blood", "Finds the combo")
    deck.maybeboard_add("Feed the Cycle", "Swamp", "Removal over a land")
    entries = board(deck)

    partial = json.loads(deck.run("remove", "Swamp", "--count", "1").stdout)
    assert "orphaned_maybeboard" not in partial, "Swamps are left, so the entry still has its card"

    out = json.loads(deck.run("remove", "Sign in Blood").stdout)
    assert out["orphaned_maybeboard"] == [
        {"name": "Demonic Tutor", "replaces": "Sign in Blood", "why": "Finds the combo"}
    ], out.get("orphaned_maybeboard")
    assert board(deck) == entries, "the entries are left for the player to drop or pair anew"
