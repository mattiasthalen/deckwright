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
    S4_FIELDS,
    Deckwright,
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
        assert set(entry["card"]) - S4_FIELDS == CARD_FIELDS, f"{name}: the fixed fields, exactly"
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


def test_read_narrows_to_deck_commander_left_out(deck, player):
    """Re-plan item 4: the commander is the deck's already, so the read never lists it, even with
    copies of it in the collection, matched by name whatever the collection's spelling."""
    rows = [manabox_row(scryfall_card(COMMANDER), 2), manabox_row(scryfall_card("Vampiric Tutor"), 1)]
    deck.collection(write_file(player, "export.csv", manabox_csv(*rows)))
    built = deck.named("Commander Owned")
    assert COMMANDER in {c["name"] for c in built.available()["cards"]}, "the collection holds the commander"

    read = built.read()
    names = [e["name"] for e in read["cards"]]
    assert "Vampiric Tutor" in names
    assert not [n for n in names if "meren" in n.casefold()], f"the commander is left out of the read: {names}"
    assert read["unjudged"] == len(read["cards"]) == 1

    # The collection as lines, in another case and punctuation: still the commander, still left out.
    report = deck.collection(write_file(player, "lines.txt", "1 MEREN OF CLAN NEL-TOTH\n1 vampiric tutor\n"))
    assert report["matched"] == 2, report
    assert COMMANDER in {c["name"] for c in built.available()["cards"]}
    read = built.read()
    names = [e["name"] for e in read["cards"]]
    assert names == ["Vampiric Tutor"], f"the commander is left out of the read: {names}"


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

    # Judged again with both fields, a card's judgement is replaced. A field left out is kept:
    # test_read_judgements_recorded_field_left_out.
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


def test_read_judgements_recorded_unjudged_add_refused(deck, player):
    """Re-plan item 4: on a deck with a read, `add` of a card the read has not judged, given no
    --category, counted by no type-line category and not in the deck, would count nowhere. It is
    refused with exit 2, naming judge and --category, and nothing is recorded."""
    deck.collection(MANABOX)
    built = deck.named("Judged Read")
    built.judge([{"name": "Starscape Cleric", "categories": ["Card advantage"], "serves_theme": True}])

    before = built.deck_file.read_bytes()
    proc = built.add("Sol Ring", expect=EXIT_USAGE)
    said = proc.stdout + proc.stderr
    assert "Traceback" not in said
    assert "judge" in said and "--category" in said, f"the message names judge and --category: {said!r}"
    assert built.deck_file.read_bytes() == before, "nothing is recorded"
    assert built.tally()["total"] == 1

    # A land counts in Lands from its type line: recorded, unjudged and with no --category.
    built.add("Command Tower")
    assert "Command Tower" in category(built.tally(), "Lands")["cards"]
    # A judged card takes the read's categories.
    built.add("Starscape Cleric")
    # --category given: recorded under it.
    built.add("Sol Ring", "Ramp")
    assert "Sol Ring" in category(built.tally(), "Ramp")["cards"]
    # Already in the deck: more copies, with no --category.
    built.add("Sol Ring")
    ramp = category(built.tally(), "Ramp")
    assert ramp["cards"] == ["Sol Ring"] and ramp["count"] == 2, f"two copies, under the categories kept: {ramp}"

    # A deck with no read records as before: one never judged, beside a kept collection ...
    unread = deck.named("No Read Yet")
    unread.add("Sol Ring")
    assert unread.tally()["total"] == 2
    # ... and one in a folder with no collection at all.
    bare = Deckwright(player, deck.api)
    bare.new()
    bare.add("Sol Ring")
    assert bare.tally()["total"] == 2


def test_read_judgements_recorded_field_left_out(deck):
    """D1: a judgement that leaves out `categories` keeps the categories recorded before, as a new
    theme re-judges theme fit only (B-18, ADR-0003); one that leaves out `serves_theme` keeps that."""
    deck.collection(MANABOX)
    rats = deck.named("Theme Changes")
    rats.judge([
        {"name": "Starscape Cleric", "categories": ["Card advantage", "Plan"], "serves_theme": True},
        {"name": "Uncharted Haven", "categories": ["Ramp"], "serves_theme": False},
        {"name": "Feed the Cycle", "categories": ["Targeted disruption"]},
    ])

    # A new theme: theme fit judged again, categories not given.
    rats.run("theme", "Bats, not rats")
    rats.judge([{"name": "Starscape Cleric", "serves_theme": False}, {"name": "Uncharted Haven", "serves_theme": True}])
    cards = by_name(rats.read())
    assert judged(cards["Starscape Cleric"]) == (["Card advantage", "Plan"], False), "the categories are kept"
    assert judged(cards["Uncharted Haven"]) == (["Ramp"], True)

    # Categories given, theme fit not: the theme fit recorded before is kept.
    rats.judge([{"name": "Uncharted Haven", "categories": ["Ramp", "Card advantage"]}])
    cards = by_name(rats.read())
    assert judged(cards["Uncharted Haven"]) == (["Ramp", "Card advantage"], True), "the theme fit is kept"
    assert judged(cards["Feed the Cycle"]) == (["Targeted disruption"], None), "a field never given stays absent"

    # A yes with no category still takes the categories the read kept.
    rats.add("Starscape Cleric")
    tally = rats.tally()
    assert "Starscape Cleric" in category(tally, "Card advantage")["cards"]
    assert "Starscape Cleric" in category(tally, "Plan")["cards"]


def test_read_judgements_recorded_whole_name_first(deck, player):
    """R2-A3: with Demonic Tutor and Emeritus of Woe // Demonic Tutor both in the read, a judgement
    of "Demonic Tutor" is the card of that name, not the card with a face of that name."""
    rows = [manabox_row(scryfall_card("Demonic Tutor"), 1), manabox_row(printing("sos", "80"), 1)]
    deck.collection(write_file(player, "export.csv", manabox_csv(*rows)))
    built = deck.named("Two Tutors")
    assert {"Demonic Tutor", "Emeritus of Woe // Demonic Tutor"} <= set(by_name(built.read()))

    built.judge([{"name": "Demonic Tutor", "categories": ["Plan"], "serves_theme": True}])
    cards = by_name(built.read())
    assert judged(cards["Demonic Tutor"]) == (["Plan"], True), "the judgement is Demonic Tutor's"
    assert judged(cards["Emeritus of Woe // Demonic Tutor"]) == (None, None), "and not Emeritus of Woe's"


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
