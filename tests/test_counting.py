"""The tally, the checks and the bracket: AC5, AC6, AC7, AC9a, E3, E5, E6, E9, E10."""

from __future__ import annotations

import re
import tomllib
from datetime import date

from conftest import CATEGORIES, SKILL_DIR, category, read_page


def test_tally(deck, unreachable_url):
    deck.new()
    deck.add("Ravenous Chupacabra", "Targeted disruption", "Plan")  # E9: one card, two categories
    deck.add("Sol Ring", "Ramp")
    deck.add("Swamp", count=60)
    deck.add("Forest", count=40)

    # The tally never needs the network.
    first = deck.run("tally", api=unreachable_url).stdout
    second = deck.run("tally", api=unreachable_url).stdout
    assert first == second, "the same deck gives the same tally"

    tally = deck.tally()
    assert [(c["name"], c["target"]) for c in tally["categories"]] == CATEGORIES
    assert tally["deck_size"] == 100

    targeted = category(tally, "Targeted disruption")
    plan = category(tally, "Plan")
    assert targeted["count"] == 1 and targeted["cards"] == ["Ravenous Chupacabra"]
    assert plan["count"] == 1 and plan["cards"] == ["Ravenous Chupacabra"]
    assert category(tally, "Ramp")["count"] == 1
    assert category(tally, "Lands")["count"] == 100
    assert category(tally, "Card advantage")["count"] == 0
    assert category(tally, "Card advantage")["cards"] == []

    # The total counts the commander and every copy, and a card in two categories once.
    assert tally["total"] == 1 + 1 + 1 + 60 + 40  # E10: 103, over the deck size

    # E10: the page says so, and nothing was removed.
    page = read_page(deck.page())
    total = page.section("total")
    assert re.search(r"(?<!\d)103\s*/\s*100(?!\d)", total), total
    assert "over" in total.lower(), f"the page should say the deck is over its size: {total!r}"
    decklist = page.section("decklist")
    assert "60 Swamp" in decklist and "40 Forest" in decklist

    # A changed target is used by every later tally.
    deck.run("target", "Ramp", "8")
    after = deck.tally()
    assert category(after, "Ramp")["target"] == 8
    assert category(after, "Plan")["target"] == 30


def test_lands_from_type_line(deck):
    deck.new()
    deck.add("Command Tower", "Ramp")  # a land recorded under Ramp
    deck.add("Sol Ring", "Lands")  # a nonland recorded under Lands
    deck.add("Forest", count=5)  # a basic recorded under nothing
    deck.add("Bloodline Keeper", "Plan")  # two faces, neither a land

    tally = deck.tally()
    lands = category(tally, "Lands")
    assert sorted(lands["cards"]) == ["Command Tower", "Forest"]
    assert lands["count"] == 6
    assert category(tally, "Ramp")["cards"] == ["Command Tower"]
    assert tally["total"] == 1 + 1 + 1 + 5 + 1, "a recorded card counts in the total whatever its categories"


def test_checks(deck):
    deck.new()
    deck.add("Sol Ring", "Ramp")
    deck.add("Sol Ring", "Ramp")  # E6: named twice
    deck.add("Lightning Bolt", "Targeted disruption")  # E5: red, outside a black-green commander
    deck.add("Black Lotus", "Ramp")  # banned in Commander
    deck.add("Swamp", count=30)  # basics are exempt from singleton
    deck.add("Relentless Rats", "Plan", count=3)  # its text allows any number

    tally = deck.tally()
    checks = tally["checks"]
    assert checks["singleton"] == ["Sol Ring"]
    assert checks["color_identity"] == ["Lightning Bolt"]
    assert checks["commander_legality"] == ["Black Lotus"]

    # Flagged, never removed.
    assert tally["total"] == 1 + 2 + 1 + 1 + 30 + 3
    page = read_page(deck.page())
    decklist = page.section("decklist")
    for row in ("2 Sol Ring", "1 Lightning Bolt", "1 Black Lotus", "30 Swamp", "3 Relentless Rats"):
        assert row in decklist.splitlines(), row
    flagged = page.section("checks")
    for name in ("Sol Ring", "Lightning Bolt", "Black Lotus"):
        assert name in flagged, f"{name} should be flagged in the page's checks"
    assert "Relentless Rats" not in flagged
    assert "Swamp" not in flagged


def test_checks_pass_on_a_clean_deck(deck):
    deck.new()
    deck.add("Sol Ring", "Ramp")
    deck.add("Swamp", count=10)
    checks = deck.tally()["checks"]
    assert checks == {**checks, "singleton": [], "color_identity": [], "commander_legality": []}


def test_bracket_floor(deck):
    rules = tomllib.loads((SKILL_DIR / "brackets.toml").read_text(encoding="utf-8"))
    source = rules["source"]
    assert isinstance(source, str) and re.search(r"Wizards|WotC", source), "the rules file names WotC's document"
    when = rules["date"]
    assert isinstance(when, date) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(when)), when

    deck.new()
    deck.add("Sol Ring", "Ramp")
    bracket = deck.tally()["bracket"]
    assert bracket == {**bracket, "target": 2, "lowest": 2, "game_changers": []}

    # E3: one Game Changer in a bracket 2 deck.
    deck.add("Vampiric Tutor", "Plan")
    bracket = deck.tally()["bracket"]
    assert (bracket["target"], bracket["lowest"], bracket["game_changers"]) == (2, 3, ["Vampiric Tutor"])
    page = read_page(deck.page())
    assert "Vampiric Tutor" in page.section("bracket")
    assert "1 Vampiric Tutor" in page.section("decklist").splitlines(), "nothing is removed"

    deck.add("Demonic Tutor", "Plan")
    deck.add("Ancient Tomb", "Ramp")
    bracket = deck.tally()["bracket"]
    assert bracket["lowest"] == 3
    assert sorted(bracket["game_changers"]) == ["Ancient Tomb", "Demonic Tutor", "Vampiric Tutor"]

    deck.add("Mana Vault", "Ramp")
    bracket = deck.tally()["bracket"]
    assert bracket["lowest"] == 4
    assert len(bracket["game_changers"]) == 4

    # The player sets another target.
    deck.run("bracket", "4")
    assert deck.tally()["bracket"]["target"] == 4
