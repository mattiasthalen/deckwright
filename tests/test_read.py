"""The read: the narrowing, the judgements kept for it, and the theme: C15, C16, C21, E9."""

from __future__ import annotations

import csv
import io
import json

import pytest
from conftest import (
    CARD_FIELDS,
    CATEGORIES,
    COMMANDER,
    EXIT_USAGE,
    MANABOX,
    category,
    escaped,
    manabox_csv,
    manabox_row,
    printing,
    read_page,
    scryfall_card,
    write_file,
)


@pytest.fixture
def player(tmp_path):
    folder = tmp_path / "player"
    folder.mkdir()
    return folder


def manabox_rows() -> list[str]:
    """manabox.csv's rows, as text, without its header."""
    return MANABOX.read_bytes().decode("utf-8").split("\r\n")[1:-1]


def by_name(read: dict) -> dict[str, dict]:
    names = [e["name"] for e in read["cards"]]
    assert len(names) == len(set(names)), f"a card is listed more than once: {names}"
    return {e["name"]: e for e in read["cards"]}


def judged(entry: dict) -> tuple[list[str] | None, bool | None]:
    return entry.get("categories"), entry.get("serves_theme")


# C15, E9 -----------------------------------------------------------------------------


def test_read_narrows_to_deck(deck, player):
    extra = [
        manabox_row(scryfall_card("Black Lotus"), 1),  # colourless, banned
        manabox_row(scryfall_card("Lightning Bolt"), 2),  # red: outside Meren's colours
        manabox_row(scryfall_card("Command Tower"), 1),  # a nonbasic land, colourless
        manabox_row(scryfall_card("Sol Ring"), 1, "Old Meren", "deck"),  # held back: none available
    ]
    deck.collection(write_file(player, "export.csv", manabox_csv(*manabox_rows(), *extra)))
    deck.new()

    proc = deck.run("read")
    read = json.loads(proc.stdout)
    assert next(iter(read)) == "unjudged", "unjudged is the output's first key, so a cut-off output still shows it"
    cards = by_name(read)

    # Every available card within Meren's colour identity (black-green) and legal in Commander,
    # lands and nonlands alike: computed from the rows and their printings, then spot-checked.
    identity = {"B", "G"}
    expected = set()
    for row in csv.DictReader(io.StringIO(MANABOX.read_text(encoding="utf-8"), newline="")):
        card = printing(row["Set code"].lower(), row["Collector number"])
        legal = card["legalities"]["commander"] == "legal"
        if legal and set(card["color_identity"]) <= identity and card["layout"] != "token":
            expected.add(card["name"])
    expected.add("Command Tower")
    assert set(cards) - {COMMANDER} == expected

    for name in ("Forest", "Swamp", "Uncharted Haven", "Mudflat Village", "Command Tower"):
        assert name in cards, f"{name} is a land within Meren's colours: lands are read too"
    for name in ("Vampiric Tutor", "Starscape Cleric", "Bakersbane Duo", "Feed the Cycle"):
        assert name in cards
    for name in ("Island", "Plains", "Mountain", "Wick, the Whorled Mind", "Zoraline, Cosmos Caller", "Lightning Bolt"):
        assert name not in cards, f"{name} is outside Meren's colour identity"
    assert "Prophet of Kruphix" not in cards and "Black Lotus" not in cards, "banned in Commander"
    assert "Sol Ring" not in cards, "no copy of it is available"

    for name, entry in cards.items():
        assert set(entry["card"]) == CARD_FIELDS, f"{name}: the fixed fields, exactly"
        assert entry["card"]["name"] == name
        assert entry["available"] >= 1
        assert judged(entry) == (None, None), f"{name} has a judgement before any was recorded"
    assert cards["Forest"]["available"] == 15 and cards["Uncharted Haven"]["available"] == 14
    assert cards["Forest"]["card"]["type_line"] == "Basic Land — Forest"
    assert read["unjudged"] == len(read["cards"])

    # E9: no available card within the commander's colours: the narrowing is empty.
    deck.collection(write_file(player, "blue.txt", "14 Island\n2 Lightning Bolt\n1 Plains\n"))
    read = deck.read()
    assert read["cards"] == [] and read["unjudged"] == 0


# C16 ---------------------------------------------------------------------------------


def test_read_judgements_recorded(deck, player):
    deck.collection(MANABOX)
    graveyard = deck.named("Graveyard Value")
    other = deck.named("Second Meren")

    before = graveyard.deck_file.read_bytes()
    other_before = other.deck_file.read_bytes()
    judgements = [
        {"name": "Vampiric Tutor", "categories": ["Plan"], "serves_theme": True},
        {"name": "Starscape Cleric", "categories": ["Card advantage", "Plan"], "serves_theme": True},
        {"name": "Mudflat Village", "categories": [], "serves_theme": False},
        {"name": "Uncharted Haven", "categories": ["Ramp"]},
        {"name": "Bakersbane Duo", "categories": ["Lands"], "serves_theme": False},
    ]
    graveyard.judge(judgements)
    assert graveyard.deck_file.read_bytes() != before, "judgements are kept in the deck's file"
    assert other.deck_file.read_bytes() == other_before, "and only in that deck's"
    assert graveyard.tally()["total"] == 1, "a judgement records no card: only a yes does"

    # A later command, of another kind, keeps them.
    graveyard.run("target", "Ramp", "9")
    graveyard.run("tally")
    cards = {e["name"]: e for e in graveyard.read()["cards"]}
    assert judged(cards["Vampiric Tutor"]) == (["Plan"], True)
    assert judged(cards["Starscape Cleric"]) == (["Card advantage", "Plan"], True)
    assert judged(cards["Mudflat Village"]) == ([], False), "none is a judgement too"
    assert judged(cards["Uncharted Haven"]) == (["Ramp"], None)
    assert graveyard.read()["unjudged"] == len(cards) - len(judgements)

    unjudged = other.read()
    assert all(judged(e) == (None, None) for e in unjudged["cards"]), "another deck's read is its own"
    assert unjudged["unjudged"] == len(unjudged["cards"])

    # Judged again, a card's judgement is replaced.
    graveyard.judge([{"name": "Vampiric Tutor", "categories": ["Card advantage"], "serves_theme": False}])
    cards = {e["name"]: e for e in graveyard.read()["cards"]}
    assert judged(cards["Vampiric Tutor"]) == (["Card advantage"], False)

    # A category the template does not have is refused, and nothing is recorded.
    mid = graveyard.deck_file.read_bytes()
    proc = graveyard.run("judge", json.dumps([{"name": "Feed the Cycle", "categories": ["Rampp"]}]), expect=EXIT_USAGE)
    assert "Traceback" not in proc.stderr
    assert graveyard.deck_file.read_bytes() == mid

    # A yes with no category given takes the read's; one given says otherwise.
    graveyard.add("Starscape Cleric")
    graveyard.add("Vampiric Tutor", "Plan")
    # Lands still counts from the type line, whatever the read said.
    graveyard.add("Uncharted Haven")
    graveyard.add("Mudflat Village")
    graveyard.add("Bakersbane Duo")
    tally = graveyard.tally()
    assert "Starscape Cleric" in category(tally, "Card advantage")["cards"]
    assert "Starscape Cleric" in category(tally, "Plan")["cards"]
    assert "Vampiric Tutor" in category(tally, "Plan")["cards"]
    assert "Vampiric Tutor" not in category(tally, "Card advantage")["cards"], "the categories given replace the read's"
    lands = category(tally, "Lands")["cards"]
    assert "Uncharted Haven" in lands and "Mudflat Village" in lands
    assert "Bakersbane Duo" not in lands, "a creature judged under Lands does not count there"
    assert "Uncharted Haven" in category(tally, "Ramp")["cards"]


# C21 ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "theme",
    ["Bloomburrow rats", "Lands matter: 45 lands and no ramp", "Ramp 0, Plan 50 & a deck size of 60"],
    ids=["rats", "lands matter", "numbers in the theme"],
)
def test_theme_leaves_targets(deck, theme):
    deck.collection(MANABOX)
    themed = deck.named("Themed")
    before = themed.tally()
    plan = "Drain each opponent with <Bat> tokens & recur them from the graveyard."

    themed.run("theme", theme)
    themed.run("plan", plan)
    themed.judge([{"name": "Starscape Cleric", "categories": ["Plan"], "serves_theme": True}])
    themed.add("Starscape Cleric")

    tally = themed.tally()
    assert [(c["name"], c["target"]) for c in tally["categories"]] == CATEGORIES, "the template's, whatever the theme"
    assert [c["counts_when"] for c in tally["categories"]] == [c["counts_when"] for c in before["categories"]]
    assert tally["deck_size"] == 100 and tally["bracket"]["target"] == 2

    # The theme and the plan sentence are on the deck page.
    page = read_page(themed.page())
    assert theme in page.section("theme")
    assert plan in page.section("plan")
    assert escaped(plan) in page.raw, "the plan sentence is escaped as text"
