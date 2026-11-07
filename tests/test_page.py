"""The deck page and its decklist: AC8, AC9, AC10, E2, E8, E11."""

from __future__ import annotations

import re
import shutil
import time

from conftest import CATEGORIES, COMMANDER, EXIT_UNREACHABLE, Deckwright, count_of, escaped, read_page

PLAYER_TEXT = "Flying. When this creature enters, draw a card."


def build_with_player_text(deck: Deckwright, unreachable_url: str):
    deck.new()
    deck.add("Command Tower")
    deck.add("Swamp", count=18)
    deck.add("Forest", count=17)
    deck.add("Sol Ring", "Ramp")
    deck.add("Ravenous Chupacabra", "Targeted disruption", "Plan")
    deck.add("Sign in Blood", "Card advantage")
    deck.add("Pernicious Deed", "Mass disruption")
    deck.add("Vampiric Tutor", "Plan")
    deck.add("Lightning Bolt", "Targeted disruption")
    # E2: Scryfall is out of reach; the player gives the card's text.
    deck.add("Homebrew Owl", "Card advantage", api=unreachable_url, expect=EXIT_UNREACHABLE)
    deck.run(
        "add", "Homebrew Owl", "--from-player", PLAYER_TEXT, "--category", "Card advantage", "Plan", api=unreachable_url
    )


# AC8 ---------------------------------------------------------------------------------


def test_page_deterministic(tmp_path, deck, unreachable_url):
    build_with_player_text(deck, unreachable_url)
    first = deck.cwd / "first.html"
    deck.run("page", "--out", str(first), api=unreachable_url)
    time.sleep(1.1)
    deck.run("page", "--out", "second.html", api=unreachable_url)

    # The same deck file somewhere else, at another time, from another folder.
    other = tmp_path / "other-folder"
    other.mkdir()
    shutil.copy2(deck.deck_file, other / "deck.json")
    Deckwright(other, unreachable_url).run("page", "--out", "third.html")

    a = first.read_bytes()
    assert a == (deck.cwd / "second.html").read_bytes()
    assert a == (other / "third.html").read_bytes()
    assert str(deck.cwd).encode() not in a and str(tmp_path).encode() not in a, "no paths on the page"


# AC9 ---------------------------------------------------------------------------------


def test_page_content(deck, unreachable_url):
    build_with_player_text(deck, unreachable_url)
    tally = deck.tally(api=unreachable_url)
    raw = deck.page(api=unreachable_url)
    page = read_page(raw)

    assert COMMANDER in page.section("commander")

    for (name, target), counted in zip(CATEGORIES, tally["categories"]):
        text = page.category(name)
        assert count_of(text, counted["count"], target), f"{name} should show {counted['count']} / {target}: {text!r}"
        for card in counted["cards"]:
            assert card in text, f"{card} counts in {name} and should be listed there"
    assert "Sign in Blood" not in page.category("Ramp")

    total = page.section("total")
    assert count_of(total, tally["total"], 100), total
    assert tally["total"] == 1 + 1 + 18 + 17 + 7

    checks = page.section("checks")
    assert "Lightning Bolt" in checks

    bracket = page.section("bracket")
    assert "Vampiric Tutor" in bracket
    assert re.search(r"target\D{0,40}2(?!\d)", bracket, re.I), bracket
    assert re.search(r"lowest\D{0,40}3(?!\d)", bracket, re.I), bracket

    assert "Homebrew Owl" in page.section("player-text")

    decklist = page.section("decklist")
    assert decklist.strip().startswith("// COMMANDER")
    assert page.decklist_children == 0, "the decklist is plain text inside one element, no markup inside"
    assert escaped(decklist.strip()) in raw

    # The copy button is the page's only script.
    assert page.buttons >= 1
    assert len(page.scripts) <= 1
    assert all("src" not in attrs for attrs in page.scripts), "no script loaded from elsewhere"
    assert "clipboard" in raw


def test_page_marks_player_text(deck, unreachable_url):
    build_with_player_text(deck, unreachable_url)
    page = read_page(deck.page(api=unreachable_url))
    marked = page.section("player-text")
    assert "Homebrew Owl" in marked
    for looked_up in ("Sol Ring", "Vampiric Tutor", "Ravenous Chupacabra", COMMANDER):
        assert looked_up not in marked, f"{looked_up} came from a lookup, not from the player"
    assert "Homebrew Owl" in page.category("Card advantage")
    assert "Homebrew Owl" in page.category("Plan")
    assert "1 Homebrew Owl" in page.section("decklist").splitlines()


# E8 ----------------------------------------------------------------------------------


def test_page_partial_deck(deck, unreachable_url):
    deck.new()
    deck.add("Swamp", count=20)
    deck.add("Forest", count=18)
    deck.add("Sol Ring", "Ramp")
    deck.add("Mana Vault", "Ramp")
    page = read_page(deck.page(api=unreachable_url))

    assert count_of(page.section("total"), 41, 100), page.section("total")
    assert "over" not in page.section("total").lower()
    assert count_of(page.category("Lands"), 38, 38)
    assert count_of(page.category("Ramp"), 2, 10)
    for name, target in CATEGORIES[2:]:
        assert count_of(page.category(name), 0, target), f"{name} is open and should show 0 / {target}"


# AC10, E11 ---------------------------------------------------------------------------


def test_import_format(deck):
    deck.new()
    deck.add("Vampiric Tutor", "Plan")
    deck.add("Swamp", count=10)
    deck.add("Forest", count=15)
    deck.add("Sol Ring", "Ramp")
    deck.add("Forest", count=5)  # E11: 20 Forest in all, one row
    deck.add("Command Tower")
    raw = deck.page()
    decklist = read_page(raw).section("decklist").strip("\n")

    assert decklist.splitlines() == [
        "// COMMANDER",
        "1 Meren of Clan Nel Toth",
        "",
        "// MAINBOARD",
        "1 Command Tower",
        "20 Forest",
        "1 Sol Ring",
        "10 Swamp",
        "1 Vampiric Tutor",
    ]
    assert not re.search(r"\([A-Za-z0-9]{2,6}\)", decklist), "no set codes"
    assert deck.tally()["total"] == 1 + 1 + 20 + 1 + 10 + 1
