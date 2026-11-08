"""The tally, the checks and the bracket: AC5, AC6, AC7, AC9a, E3, E5, E6, E9, E10."""

from __future__ import annotations

import json
import re
import tomllib
from datetime import date

from conftest import CATEGORIES, SKILL_DIR, category, read_page, scryfall_card


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


def test_lands_from_type_line_front_face(deck):
    # Its front is a Legendary Enchantment; only the back, Atzal, Cave of Eternity, is a Land.
    deck.new()
    deck.add("Journey to Eternity")
    tally = deck.tally()
    assert category(tally, "Lands")["count"] == 0, "the type line rule reads the front face only"
    assert category(tally, "Lands")["cards"] == []
    assert tally["total"] == 1 + 1


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


def test_bracket_floor_over(deck):
    deck.new()
    deck.add("Sol Ring", "Ramp")
    # Over only when the Game Changers need a bracket above the target: lowest > max(target, 2).
    assert deck.tally()["bracket"]["over"] is False, "target 2, none"
    deck.run("bracket", "1")
    assert deck.tally()["bracket"]["over"] is False, "target 1, none: no deck is below bracket 2"

    deck.add("Vampiric Tutor", "Plan")
    deck.run("bracket", "2")
    assert deck.tally()["bracket"]["over"] is True, "target 2, one"
    deck.run("bracket", "3")
    assert deck.tally()["bracket"]["over"] is False, "target 3, one"

    for name in ("Demonic Tutor", "Mana Vault", "Ancient Tomb"):
        deck.add(name, "Ramp")
    bracket = deck.tally()["bracket"]
    assert (bracket["lowest"], bracket["over"]) == (4, True), "target 3, four"


def test_bracket_floor_commander_counted_once(deck):
    deck.new(commander="Vampiric Tutor")
    deck.add("Vampiric Tutor", "Plan")
    deck.add("Demonic Tutor", "Plan")
    deck.add("Mana Vault", "Ramp")
    bracket = deck.tally()["bracket"]
    assert bracket["game_changers"] == ["Demonic Tutor", "Mana Vault", "Vampiric Tutor"], "once per name"
    assert bracket["lowest"] == 3, "three Game Changers by name, not four"

    deck.add("Grim Monolith", "Ramp")
    assert deck.tally()["bracket"]["lowest"] == 4, "the commander counts: four names"


def test_bracket_floor_commander_counts(deck):
    deck.new(commander="Vampiric Tutor")
    deck.add("Demonic Tutor", "Plan")
    deck.add("Mana Vault", "Ramp")
    deck.add("Grim Monolith", "Ramp")
    bracket = deck.tally()["bracket"]
    assert bracket["game_changers"] == ["Demonic Tutor", "Grim Monolith", "Mana Vault", "Vampiric Tutor"]
    assert bracket["lowest"] == 4


def test_checks_up_to_n_copies(deck):
    deck.new()
    deck.add("Seven Dwarves", "Plan", count=7)
    assert "Seven Dwarves" not in deck.tally()["checks"]["singleton"], "its text allows up to seven"
    deck.add("Seven Dwarves", "Plan")
    assert "Seven Dwarves" in deck.tally()["checks"]["singleton"], "eight is above seven"


def test_checks_commander(deck):
    deck.new()
    assert deck.tally()["checks"]["commander"] == [], "Meren is a legendary creature"

    deck.new(commander="Llanowar Elves")
    deck.add("Forest", count=10)
    assert deck.tally()["checks"]["commander"] == ["Llanowar Elves"], "not legendary"
    assert "Llanowar Elves" in read_page(deck.page()).section("checks")


def test_checks_commander_front_face(deck):
    # Its front is a Legendary Artifact; only the back is a creature, so it cannot lead.
    deck.new(commander="Elbrus, the Binding Blade")
    assert deck.tally()["checks"]["commander"] == ["Elbrus, the Binding Blade // Withengar Unbound"]


def test_checks_commander_can_be_your_commander(deck, unreachable_url):
    # A card whose text lets it lead is not flagged, whatever its type line.
    elves = scryfall_card("Llanowar Elves")
    elves["oracle_text"] += "\nLlanowar Elves can be your commander."
    cache = deck.cwd / "deckwright-cache"
    cache.mkdir()
    (cache / "llanowar-elves.json").write_text(json.dumps(elves), encoding="utf-8")
    deck.new(commander="Llanowar Elves")
    assert deck.tally(api=unreachable_url)["checks"]["commander"] == []


def test_add_from_player_type_line(deck, unreachable_url):
    deck.new()
    deck.run(
        "add", "Forest", "--count", "20", "--from-player", "({T}: Add {G}.)", "--type-line", "Basic Land — Forest",
        api=unreachable_url,
    )
    tally = deck.tally()
    lands = category(tally, "Lands")
    assert (lands["count"], lands["cards"]) == (20, ["Forest"]), "the player's type line puts it in Lands"
    assert tally["checks"]["singleton"] == [], "a basic land from the player's text is exempt from singleton"


def test_add_from_player_then_looked_up(deck, unreachable_url):
    deck.new()
    deck.run("add", "Homebrew Owl", "--from-player", "Flying.", "--category", "Plan", api=unreachable_url)
    deck.run(
        "add", "Lightning Bolt", "--from-player", "Deal 3 damage to any target.", "--category", "Targeted disruption",
        api=unreachable_url,
    )
    # Scryfall is back: the same name looked up replaces the player's text with the card.
    deck.add("Lightning Bolt")
    tally = deck.tally()
    targeted = category(tally, "Targeted disruption")
    assert (targeted["count"], targeted["cards"]) == (2, ["Lightning Bolt"]), "copies and categories are kept"
    assert tally["checks"]["color_identity"] == ["Lightning Bolt"], "the card is now Scryfall's: red"
    assert tally["total"] == 1 + 1 + 2

    page = read_page(deck.page())
    marked = page.section("player-text")
    assert "Homebrew Owl" in marked
    assert "Lightning Bolt" not in marked, "the player-text mark is dropped"
    assert "2 Lightning Bolt" in page.section("decklist").splitlines()

    # Recorded from the player's text by its front face's name, then looked up: the same entry.
    deck.run("add", "Bloodline Keeper", "--from-player", "Flying.", "--category", "Plan", api=unreachable_url)
    deck.add("Bloodline Keeper")
    plan = category(deck.tally(), "Plan")
    assert plan["cards"] == ["Bloodline Keeper // Lord of Lineage", "Homebrew Owl"], "one entry, not a second"
    assert plan["count"] == 3
    assert "Bloodline Keeper" not in read_page(deck.page()).section("player-text")


def test_add_two_categories_flags(deck):
    deck.new()
    deck.run("add", "Ravenous Chupacabra", "--category", "Targeted disruption", "--category", "Plan")
    tally = deck.tally()
    assert category(tally, "Targeted disruption")["cards"] == ["Ravenous Chupacabra"], "the first --category is kept"
    assert category(tally, "Plan")["cards"] == ["Ravenous Chupacabra"]


def test_add_from_player_no_ascii_names(deck, unreachable_url):
    deck.new()
    deck.run("add", "稲妻", "--from-player", "Deal 3 damage to any target.", api=unreachable_url)
    deck.run("add", "Молния", "--from-player", "Deal 3 damage to any target.", api=unreachable_url)
    rows = read_page(deck.page()).section("decklist").splitlines()
    assert "1 稲妻" in rows and "1 Молния" in rows, f"two names, two entries: {rows}"
    assert deck.tally()["total"] == 1 + 2

    deck.run("remove", "Молния")
    rows = read_page(deck.page()).section("decklist").splitlines()
    assert "1 稲妻" in rows and not any("Молния" in r for r in rows), f"only Молния is removed: {rows}"
    assert deck.tally()["total"] == 1 + 1


def test_add_from_player_type_line_any_case(deck, unreachable_url):
    deck.new()
    deck.run(
        "add", "Forest", "--count", "20", "--from-player", "({T}: Add {G}.)", "--type-line", "basic land — forest",
        api=unreachable_url,
    )
    tally = deck.tally()
    assert category(tally, "Lands")["count"] == 20, "the type line is read without regard to case"
    assert tally["checks"]["singleton"] == []


def test_bracket_floor_game_changers_allowed(deck):
    deck.new()
    allowed = {}
    for target in (1, 2, 3, 4, 5):
        deck.run("bracket", str(target))
        allowed[target] = deck.tally()["bracket"].get("game_changers_allowed", "absent")
    # From brackets.toml: bracket 2 allows none, 3 allows three, 4 and 5 have no limit; 1 is judged as 2.
    assert allowed == {1: 0, 2: 0, 3: 3, 4: "absent", 5: "absent"}


def test_remove_by_face_name(deck):
    deck.new()
    deck.add("Bloodline Keeper", "Plan")
    deck.add("Sol Ring", "Ramp")
    deck.run("remove", "Bloodline Keeper")
    tally = deck.tally()
    assert category(tally, "Plan")["cards"] == [], "the double-faced card is removed by its front face's name"
    assert tally["total"] == 1 + 1

    deck.add("Bloodline Keeper", "Plan")
    deck.run("remove", "lord of lineage")
    assert category(deck.tally(), "Plan")["cards"] == [], "or by its back face's, normalised"
