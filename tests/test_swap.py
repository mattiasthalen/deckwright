"""`swap 'OUT' 'IN' --why 'TEXT'`: AC11, AC12, AC13, E3–E7, E16 (P1, P4).

A swap takes OUT out and puts IN in, in one step, and records `{out, in, why}` in the deck file's
`swaps`, in the order made (P4). It prints the tally. What its output adds to the tally, and the
maybeboard's layout, are fixed in tests/README.md.
"""

from __future__ import annotations

import json
import re
import shutil

from conftest import (
    COMMANDER,
    EXIT_NOT_RECORDED,
    EXIT_UNREACHABLE,
    EXIT_USAGE,
    MANABOX,
    Deckwright,
    assert_refused,
    category,
    read_page,
    said,
)


def full_deck(deck: Deckwright) -> Deckwright:
    deck.new()
    deck.add("Sol Ring", "Ramp")
    deck.add("Sign in Blood", "Card advantage")
    deck.add("Ravenous Chupacabra", "Targeted disruption", "Plan")
    deck.add("Command Tower")
    deck.fill()
    return deck


def names_in(tally: dict) -> set[str]:
    return {name for c in tally["categories"] for name in c["cards"]}


# AC11 --------------------------------------------------------------------------------


def test_swap_is_one_step(deck):
    full_deck(deck)
    proc = deck.swap("Sign in Blood", "Feed the Cycle", "Removal over draw", "--category", "Targeted disruption")
    tally = json.loads(proc.stdout)
    assert tally["total"] == 100, "one out, one in: the total is kept"
    assert "Sign in Blood" not in category(tally, "Card advantage")["cards"]
    assert "Feed the Cycle" in category(tally, "Targeted disruption")["cards"]
    for key, value in deck.tally().items():
        assert tally[key] == value, f"it prints the tally: {key}"
    assert deck.stored()["swaps"] == [{"out": "Sign in Blood", "in": "Feed the Cycle", "why": "Removal over draw"}]

    # Names as the deck and the lookup spell them, whatever the player typed.
    deck.swap("ravenous chupacabra", "nocturnal hunger", "Cheaper", "--category", "Targeted disruption")
    assert deck.stored()["swaps"][1] == {"out": "Ravenous Chupacabra", "in": "Nocturnal Hunger", "why": "Cheaper"}
    assert deck.tally()["total"] == 100


def test_swap_is_one_step_no_category(deck):
    """P1: with no --category and no read, the card goes in as `add` records it, under no category."""
    full_deck(deck)
    deck.swap("Sign in Blood", "Feed the Cycle", "Removal over draw")
    tally = deck.tally()
    assert tally["total"] == 100
    assert "Feed the Cycle" not in names_in(tally), "it does not take over the outgoing card's categories"


def test_swap_is_one_step_categories_from_the_read(deck):
    """P1: on a deck with a read, no --category takes the read's categories, and a card the read has
    not judged is refused, exactly as `add` does."""
    deck.collection(MANABOX)
    rats = deck.named("Rat Pack")
    rats.judge([{"name": "Feed the Cycle", "categories": ["Targeted disruption"], "serves_theme": True}])
    rats.add("Sign in Blood", "Card advantage")
    rats.add("Sol Ring", "Ramp")
    rats.fill()

    before = rats.deck_file.read_bytes()
    proc = rats.run("swap", "Sign in Blood", "Nocturnal Hunger", "--why", "Removal", expect=None)
    assert_refused(proc, rats, before, EXIT_USAGE)
    assert "judge" in said(proc) and "--category" in said(proc), said(proc)

    rats.swap("Sign in Blood", "Feed the Cycle", "Removal")
    assert "Feed the Cycle" in category(rats.tally(), "Targeted disruption")["cards"]
    assert rats.stored()["judgements"]["Feed the Cycle"]["serves_theme"] is True

    rats.run("swap", "Sol Ring", "Nocturnal Hunger", "--why", "On theme", "--category", "Plan",
             "--serves-theme", "yes")
    assert "Nocturnal Hunger" in category(rats.tally(), "Plan")["cards"]
    assert rats.stored()["judgements"]["Nocturnal Hunger"]["serves_theme"] is True


# AC12 --------------------------------------------------------------------------------


def test_card_into_deck_leaves_maybeboard(deck):
    full_deck(deck)
    deck.maybeboard_add("Feed the Cycle", "Sign in Blood", "Cheaper removal")
    deck.maybeboard_add("Nocturnal Hunger", "Sol Ring", "Instant speed")

    out = json.loads(deck.swap("Sign in Blood", "Feed the Cycle", "Removal over draw").stdout)
    assert out["left_maybeboard"] == ["Feed the Cycle"], "the swap's output says the card came off the maybeboard"
    assert [e["name"] for e in deck.stored()["maybeboard"]] == ["Nocturnal Hunger"]

    out = json.loads(deck.add("Nocturnal Hunger").stdout)
    assert out["left_maybeboard"] == ["Nocturnal Hunger"], "so does add's"
    assert deck.stored().get("maybeboard", []) == []

    # A swap or add of a card that was never on the maybeboard says nothing of it.
    assert "left_maybeboard" not in json.loads(deck.add("Forest").stdout)
    assert "left_maybeboard" not in json.loads(deck.swap("Forest", "Swamp", "More black").stdout)


# AC13 --------------------------------------------------------------------------------


def test_swap_flags_orphaned_maybeboard_entries(deck):
    full_deck(deck)
    deck.maybeboard_add("Demonic Tutor", "Sign in Blood", "Finds the combo")
    deck.maybeboard_add("Nocturnal Hunger", "Sol Ring", "Instant speed")
    deck.maybeboard_add("Feed the Cycle", "Sign in Blood", "Cheaper")
    board = deck.stored()["maybeboard"]

    out = json.loads(deck.swap("Sign in Blood", "Vampiric Tutor", "A tutor").stdout)
    assert out["orphaned_maybeboard"] == [
        {"name": "Demonic Tutor", "replaces": "Sign in Blood", "why": "Finds the combo"},
        {"name": "Feed the Cycle", "replaces": "Sign in Blood", "why": "Cheaper"},
    ], "each entry whose replaces went out, in maybeboard order"
    assert deck.stored()["maybeboard"] == board, "and they are left as they were"

    assert "orphaned_maybeboard" not in json.loads(deck.swap("Forest", "Swamp", "More black").stdout)


# E3–E7 -------------------------------------------------------------------------------


def test_refuses_out_not_in_deck(deck):
    full_deck(deck)
    before = deck.deck_file.read_bytes()
    assert_refused(deck.run("swap", "Lightning Bolt", "Feed the Cycle", "--why", "x", expect=None), deck, before)


def test_refuses_in_already_in_deck(deck):
    full_deck(deck)
    before = deck.deck_file.read_bytes()
    proc = deck.run("swap", "Sign in Blood", "Sol Ring", "--why", "x", expect=None)
    assert_refused(proc, deck, before)
    assert "Sol Ring" in said(proc), said(proc)


def test_basic_land_swap(deck):
    full_deck(deck)
    lands = category(deck.tally(), "Lands")["count"]
    deck.swap("Sign in Blood", "Swamp", "More lands")
    tally = deck.tally()
    assert tally["total"] == 100
    assert category(tally, "Lands")["count"] == lands + 1, "one more Swamp"
    assert "Sign in Blood" not in names_in(tally)
    assert deck.stored()["swaps"] == [{"out": "Sign in Blood", "in": "Swamp", "why": "More lands"}]


def test_unreachable_changes_nothing(deck, unreachable_url):
    full_deck(deck)
    shutil.rmtree(deck.cache)  # no bulk file to answer for Scryfall
    offline = deck.offline(unreachable_url)
    before = deck.deck_file.read_bytes()
    proc = offline.run("swap", "Sign in Blood", "Feed the Cycle", "--why", "x", expect=None)
    assert_refused(proc, deck, before, EXIT_UNREACHABLE)
    assert "Feed the Cycle" in said(proc) and re.search(r"reach", said(proc), re.I), said(proc)
    assert "from-player" not in said(proc), "swap has no --from-player path, so the message offers none"

    proc = offline.run("swap", "Sign in Blood", "Feed the Cycle", "--why", "x", "--from-player", "t", expect=None)
    assert_refused(proc, deck, before, EXIT_USAGE, by_argparse=True)


def test_not_found_changes_nothing(deck):
    full_deck(deck)
    before = deck.deck_file.read_bytes()
    for name in ("Xyzzy Plover Quux", "Vampiric Tutr"):  # not found; only a closest match
        proc = deck.run("swap", "Sign in Blood", name, "--why", "x", expect=None)
        assert_refused(proc, deck, before, EXIT_NOT_RECORDED)


# E16 ---------------------------------------------------------------------------------


def test_swaps_recorded_in_order(deck):
    full_deck(deck)
    deck.swap("Sign in Blood", "Feed the Cycle", "Removal over draw")
    deck.swap("Feed the Cycle", "Nocturnal Hunger", "Instant speed after all")
    assert deck.stored()["swaps"] == [
        {"out": "Sign in Blood", "in": "Feed the Cycle", "why": "Removal over draw"},
        {"out": "Feed the Cycle", "in": "Nocturnal Hunger", "why": "Instant speed after all"},
    ]
    swaps = read_page(deck.page()).section("swaps")
    first, second = swaps.find("Removal over draw"), swaps.find("Instant speed after all")
    assert 0 <= first < second, f"the page lists both, in the order made: {swaps!r}"
    assert swaps.find("Sign in Blood") < first and swaps.find("Nocturnal Hunger") > first, swaps


def test_refuses_the_commander_in(deck):
    """R18: the commander is in the deck already, so it cannot come in by swap."""
    full_deck(deck)
    before = deck.deck_file.read_bytes()
    assert_refused(deck.run("swap", "Sol Ring", COMMANDER, "--why", "x", expect=None), deck, before)


def test_refuses_a_basic_land_for_itself(deck):
    """R24: a swap of a card for itself changes nothing, so it is refused, a basic land too (a basic may
    otherwise come in while copies of it are in the deck)."""
    full_deck(deck)
    before = deck.deck_file.read_bytes()
    assert_refused(deck.run("swap", "Swamp", "Swamp", "--why", "x", expect=None), deck, before)


def test_refuses_a_card_for_itself_by_any_spelling(deck, unreachable_url):
    """R39: OUT and IN are the same card whatever the spelling: a player's-text `forest` swapped for the
    looked-up Forest is refused, a basic land too."""
    deck.new()
    deck.add("Sol Ring", "Ramp")
    deck.offline(unreachable_url).run("add", "forest", "--from-player", "", "--type-line", "Basic Land — Forest")
    before = deck.deck_file.read_bytes()
    assert_refused(deck.run("swap", "forest", "Forest", "--why", "x", expect=None), deck, before)


# Bloodline Keeper recorded from the player's text, under its front face's name only (R46–R48).
KEEPER_TYPED = ("Bloodline Keeper", "--from-player", "Flying.", "--type-line", "Legendary Creature — Vampire")


def keeper_by_face_name(deck: Deckwright, unreachable_url: str) -> None:
    """A full deck holding Bloodline Keeper from the player's text, under its front face's name only."""
    full_deck(deck)
    deck.run("remove", "Swamp", "--count", "1")
    deck.offline(unreachable_url).run("add", *KEEPER_TYPED)


def test_refuses_a_card_for_itself_by_a_face_name(deck, unreachable_url):
    """R46: OUT recorded under a face name and IN looked up to the whole card are one card: refused."""
    keeper_by_face_name(deck, unreachable_url)
    before = deck.deck_file.read_bytes()
    assert_refused(deck.run("swap", "Bloodline Keeper", "Bloodline Keeper", "--why", "x", expect=None), deck, before)


def test_refuses_in_already_in_deck_by_a_face_name(deck, unreachable_url):
    """R47: a card in the deck under a face name the player typed is in the deck: it cannot come in."""
    keeper_by_face_name(deck, unreachable_url)
    before = deck.deck_file.read_bytes()
    proc = deck.run("swap", "Sign in Blood", "Bloodline Keeper", "--why", "x", expect=None)
    assert_refused(proc, deck, before)
    assert "already in the deck" in said(proc), said(proc)
