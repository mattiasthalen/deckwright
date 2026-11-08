"""Cards recorded beyond what the collection has available: C27, E12, E13."""

from __future__ import annotations

import re

import pytest
from conftest import Deckwright, manabox_csv, manabox_row, read_page, scryfall_card, write_file


@pytest.fixture
def player(tmp_path):
    folder = tmp_path / "player"
    folder.mkdir()
    return folder


def ownership(tally: dict) -> dict[str, tuple[int, int]]:
    cards = tally["ownership"]["cards"]
    names = [c["name"] for c in cards]
    assert len(names) == len(set(names)), f"a card is listed more than once: {names}"
    return {c["name"]: (c["owned"], c["not_owned"]) for c in cards}


def totals(tally: dict) -> tuple[int, int]:
    return tally["ownership"]["owned"], tally["ownership"]["not_owned"]


def shows(section: str, label: str, owned: int, not_owned: int) -> bool:
    """Whether the page's ownership section shows `<label> … N owned … M not owned`."""
    pattern = rf"{re.escape(label)}\D{{0,40}}?(?<!\d){owned} owned\D{{0,40}}?(?<!\d){not_owned} not owned"
    return re.search(pattern, section, re.I) is not None


# C27, E12 ----------------------------------------------------------------------------


def test_not_owned_marked(deck, player):
    deck.collection(write_file(player, "cards.txt", "12 Forest\n1 Sol Ring\n1 Vampiric Tutor\n"))
    built = deck.named("Owned or Not")
    built.add("Forest", count=15)  # E12: 12 owned, 3 after a yes to cards not owned
    built.add("Sol Ring", "Ramp")
    built.add("Mana Vault", "Ramp")  # not in the collection at all
    built.add("Swamp", count=2)

    tally = built.tally()
    assert ownership(tally) == {
        "Forest": (12, 3),
        "Mana Vault": (0, 1),
        "Sol Ring": (1, 0),
        "Swamp": (0, 2),
    }, "every recorded card, the commander apart, with its copies owned and not owned"
    assert totals(tally) == (13, 6)
    assert sum(o + n for o, n in ownership(tally).values()) == tally["total"] - 1

    page = read_page(built.page())
    section = page.section("ownership")
    assert shows(section, "Forest", 12, 3), section
    assert shows(section, "Mana Vault", 0, 1), section
    assert shows(section, "Swamp", 0, 2), section
    assert shows(section, "Total", 13, 6), section
    assert "15 Forest" in page.section("decklist").splitlines(), "the decklist holds every copy recorded"


def test_not_owned_marked_deck_binder(deck, player):
    rows = [
        manabox_row(scryfall_card("Sol Ring"), 1, "Trade binder", "binder"),
        manabox_row(scryfall_card("Sol Ring"), 1, "Vren deck", "deck"),
    ]
    deck.collection(write_file(player, "export.csv", manabox_csv(*rows)))
    deck.new()
    deck.add("Sol Ring", "Ramp", count=2)
    assert ownership(deck.tally()) == {"Sol Ring": (1, 1)}, "a copy held back in a deck binder is not available"

    deck.run("available", "--deck", "deck.json", "--include", "Vren deck")
    assert ownership(deck.tally()) == {"Sol Ring": (2, 0)}, "the deck's filter decides what it owns"


def test_not_owned_marked_only_with_a_collection(tmp_path, scryfall):
    work = tmp_path / "no-collection"
    work.mkdir()
    plain = Deckwright(work, scryfall.url)
    plain.new()
    plain.add("Forest", count=15)
    assert "ownership" not in plain.tally(), "without a collection there is nothing to own"
    assert "section:ownership" not in read_page(plain.page()).texts


# E13 ---------------------------------------------------------------------------------


def test_not_owned_removed_first(deck, player):
    deck.collection(write_file(player, "cards.txt", "12 Forest\n"))
    built = deck.named("Removals")
    built.add("Forest", count=15)

    built.run("remove", "Forest", "--count", "2")
    tally = built.tally()
    assert ownership(tally) == {"Forest": (12, 1)}, "the copies not owned go first"
    assert totals(tally) == (12, 1)

    built.run("remove", "Forest", "--count", "2")
    tally = built.tally()
    assert ownership(tally) == {"Forest": (11, 0)}
    assert totals(tally) == (11, 0)
    assert shows(read_page(built.page()).section("ownership"), "Total", 11, 0)
